#!/usr/bin/env python3
"""Benchmark script: compare TTS providers on identical narration text."""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

def _load_env():
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip("'\"")
            if key not in os.environ:
                os.environ[key] = val

_load_env()

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tts_provider import get_all_providers, get_available_providers, TTSOptions, _measure_audio


BENCHMARK_TEXT = (
    "Un día en 1453, Constantinopla cayó y con ella un imperio milenario. "
    "La ciudad fue asediada por el sultán Mehmed II y su ejército otomano. "
    "Los habitantes de la ciudad enfrentaron un destino aterrador durante el asedio. "
    "El 29 de mayo, las murallas cedieron. Constantinopla estaba perdida. "
    "La caída de Constantinopla cambió el curso de la historia mundial. "
    "Si quieres saber más sobre la historia, ¡síguenos para más contenido!"
)


def detect_silence(audio_path: str, threshold_amp: float = 0.01, min_silence_samples: int = 500) -> dict:
    from mutagen import File as MutagenFile
    import struct

    mf = MutagenFile(audio_path)
    if mf is None:
        return {"leading": 0.0, "trailing": 0.0, "internal": 0.0}

    sr = getattr(mf.info, 'sample_rate', 24000) if hasattr(mf, 'info') else 24000
    ch = getattr(mf.info, 'channels', 1) if hasattr(mf, 'info') else 1

    # Decode using ffmpeg subprocess (local) or fall back
    try:
        samples = []
        buf = mf.read(1024 * 1024)
        while buf:
            for i in range(0, len(buf) - 1, 2):
                val = struct.unpack('<h', buf[i:i+2])[0]
                if abs(val) > threshold_amp * 32767:
                    samples.append(1)
                else:
                    samples.append(0)
            buf = mf.read(1024 * 1024)
    except Exception:
        return {"leading": 0.0, "trailing": 0.0, "internal": 0.0}

    if not samples:
        return {"leading": 0.0, "trailing": 0.0, "internal": 0.0}

    # Find first non-silent sample
    first_voice = next((i for i, v in enumerate(samples) if v == 1), len(samples))
    # Find last non-silent sample
    last_voice = len(samples) - 1 - next((i for i, v in enumerate(reversed(samples)) if v == 1), len(samples))

    leading = first_voice / sr
    trailing = (len(samples) - last_voice) / sr

    # Internal silence: count silent runs between first_voice and last_voice
    internal = 0.0
    in_silence = False
    silence_start = 0
    for i in range(first_voice, last_voice + 1):
        if samples[i] == 0 and not in_silence:
            in_silence = True
            silence_start = i
        elif samples[i] == 1 and in_silence:
            in_silence = False
            silence_len = (i - silence_start) / sr
            if silence_len > min_silence_samples / sr:
                internal += silence_len

    return {"leading": round(leading, 3), "trailing": round(trailing, 3), "internal": round(internal, 3)}


def main():
    parser = argparse.ArgumentParser(description="Benchmark TTS providers")
    parser.add_argument("--output-dir", default="data/benchmarks/voice-provider-benchmark")
    parser.add_argument("--all", action="store_true", help="Try all providers including non-available")
    args = parser.parse_args()

    project_root = Path.cwd()
    output_dir = project_root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    all_providers = get_all_providers()
    if args.all:
        providers = all_providers
    else:
        providers = get_available_providers()

    print(f"Benchmark text ({len(BENCHMARK_TEXT)} chars):")
    print(f"  {BENCHMARK_TEXT[:80]}...")
    print()
    print(f"Providers to test: {len(providers)}")
    for name, prov in providers.items():
        meta = prov.metadata
        available = prov.is_available()
        print(f"  {name}: voice={meta.voice_id}, timing={meta.timing_support}, "
              f"cost=${meta.cost_per_1k_chars_usd}/1k, available={available}")

    results = []
    for name, prov in providers.items():
        meta = prov.metadata
        print(f"\n{'='*60}")
        print(f"Provider: {name}")
        print(f"{'='*60}")

        if not prov.is_available():
            print(f"  SKIP — not available (PENDIENTE_DE_VALIDAR)")
            results.append({
                "provider": name,
                "voice": meta.voice_id,
                "available": False,
                "status": "PENDIENTE_DE_VALIDAR",
            })
            continue

        try:
            base = output_dir / name
            base.mkdir(parents=True, exist_ok=True)
            safe_voice = meta.voice_id.replace('-', '_').replace(':', '_')
            raw_path = str(base / f"{name}_{safe_voice}.mp3")

            opts = TTSOptions(voice=meta.voice_id, format="mp3", sample_rate=24000)
            result = prov.synthesize(BENCHMARK_TEXT, raw_path, opts)

            silence = detect_silence(raw_path)
            result = _measure_audio(raw_path, name, meta.voice_id)
            result.silence_leading_sec = silence["leading"]
            result.silence_trailing_sec = silence["trailing"]
            result.silence_internal_sec = silence["internal"]

            results.append({
                "provider": name,
                "voice": meta.voice_id,
                "voice_name": meta.voice_name,
                "available": True,
                "status": "OK",
                "duration_sec": result.duration_sec,
                "sample_rate": result.sample_rate,
                "channels": result.channels,
                "bitrate_kbps": result.bitrate_kbps,
                "file_size_bytes": result.file_size_bytes,
                "file_size_kb": round(result.file_size_bytes / 1024, 1),
                "silence_leading_sec": result.silence_leading_sec,
                "silence_trailing_sec": result.silence_trailing_sec,
                "silence_internal_sec": result.silence_internal_sec,
                "silence_total_sec": round(
                    result.silence_leading_sec + result.silence_trailing_sec + result.silence_internal_sec, 3
                ),
                "raw_path": raw_path,
                "timing_support": meta.timing_support,
                "cost_per_1k_chars_usd": meta.cost_per_1k_chars_usd,
                "monthly_quota_chars": meta.monthly_quota_chars,
                "commercial_usage_status": meta.commercial_usage_status,
                "fallback_priority": meta.fallback_priority,
            })
            print(f"  Duration: {result.duration_sec:.3f}s")
            print(f"  Silence: L={result.silence_leading_sec:.3f}s "
                  f"T={result.silence_trailing_sec:.3f}s "
                  f"I={result.silence_internal_sec:.3f}s")
            print(f"  File: {Path(raw_path).name} ({result.file_size_bytes} bytes)")
            print(f"  Sample rate: {result.sample_rate}Hz, {result.channels}ch, "
                  f"{result.bitrate_kbps}kbps")
            print(f"  OK")

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                "provider": name,
                "voice": meta.voice_id,
                "available": True,
                "status": "ERROR",
                "error": str(e),
            })

    print(f"\n{'='*60}")
    print(f"BENCHMARK COMPLETE — {len(results)} providers tested")
    print(f"{'='*60}")

    results_path = output_dir / "benchmark_results.json"
    results_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")

    md = ["# TTS Provider Benchmark Results\n"]
    md.append(f"**Date**: {datetime.now().isoformat()}")
    md.append(f"**Text**: {len(BENCHMARK_TEXT)} chars from Constantinopla job\n")
    md.append("| Provider | Voice | Duration | S Rate | Ch | Size(KB) | Silence(L/T/I) | Timing | Cost/1k | Quota | Commercial | Priority | Status |")
    md.append("|----------|-------|----------|--------|----|----------|-----------------|--------|---------|-------|------------|----------|--------|")

    for r in results:
        if r.get("status") == "OK":
            silence = f"{r['silence_leading_sec']:.2f}/{r['silence_trailing_sec']:.2f}/{r['silence_internal_sec']:.2f}"
            md.append(
                f"| {r['provider']} | {r['voice_name']} | {r['duration_sec']:.2f}s "
                f"| {r['sample_rate']} | {r['channels']} | {r['file_size_kb']} "
                f"| {silence} | {r['timing_support']} "
                f"| ${r['cost_per_1k_chars_usd']:.3f} | {r['monthly_quota_chars']:,} "
                f"| {r['commercial_usage_status']} | {r['fallback_priority']} "
                f"| {r['status']} |"
            )
        else:
            md.append(
                f"| {r['provider']} | {r.get('voice','-')} | - | - | - | - "
                f"| - | - | - | - | - | - | {r['status']} |"
            )

    table_path = output_dir / "comparison_table.md"
    table_path.write_text("\n".join(md) + "\n")
    print(f"\nTable: {table_path}")
    print(f"JSON:  {results_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
