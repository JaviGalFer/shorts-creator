"""Slice 1: generic per-scene TTS provider runtime selection.

Proves the selected provider reaches synthesis, Edge baseline is preserved,
provider metadata is truthful, and continuous mode rejects non-Edge providers.
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from shorts_creator.audio import generator


def _make_scene_meta(tmp_path, scenes_data=None):
    job = tmp_path / "job"
    job.mkdir()
    (job / "scenes").mkdir()
    meta_path = job / "metadata.json"
    scenes = scenes_data or [
        {"sceneNumber": 1, "voiceover": "Test narration.", "targetDurationSec": 6.0},
    ]
    meta = {"jobId": "test-tts-provider-001", "script": {"scenes": scenes}}
    meta_path.write_text(json.dumps(meta))
    return meta_path, job


def _write_audio(output_path):
    Path(str(output_path)).write_bytes(b"\xff\xfb" + b"\x00" * 5000)


async def _edge_synth(text, output_path, options=None):
    _write_audio(output_path)
    r = MagicMock()
    r.timing_data = {
        "word_boundaries": [
            {"startSec": 0.1, "endSec": 0.5, "text": "Test"},
            {"startSec": 0.6, "endSec": 1.2, "text": "narration"},
        ],
        "sentence_boundaries": [],
        "timing_source": "edge_tts_word_boundary",
    }
    return r


async def _bare_synth(text, output_path, options=None):
    _write_audio(output_path)
    return MagicMock(timing_data=None)


@pytest.fixture(autouse=True)
def _no_duration_probe(monkeypatch):
    monkeypatch.setattr(
        generator, "_get_mp3_duration", lambda p: (6.576, "ffprobe_local")
    )


class TestProviderSelection:
    def test_edge_provider_reaches_synthesis(self, tmp_path, monkeypatch):
        meta_path, _ = _make_scene_meta(tmp_path)
        with patch("shorts_creator.audio.generator.get_provider") as mock_gp:
            mock_gp.return_value = MagicMock(synthesize_with_timing_async=_edge_synth)
            exit_code = asyncio.run(
                generator.main_per_scene(
                    meta_path, "es-ES-AlvaroNeural", tts_provider="edge_tts"
                )
            )
        assert exit_code == 0
        call_args = mock_gp.call_args
        assert call_args.kwargs.get("voice") == "es-ES-AlvaroNeural"

    def test_elevenlabs_provider_reaches_synthesis(self, tmp_path, monkeypatch):
        meta_path, _ = _make_scene_meta(tmp_path)
        with patch("shorts_creator.audio.generator.get_provider") as mock_gp:
            mock_gp.return_value = MagicMock(synthesize_with_timing_async=_edge_synth)
            exit_code = asyncio.run(
                generator.main_per_scene(
                    meta_path, "es-ES-AlvaroNeural", tts_provider="elevenlabs"
                )
            )
        assert exit_code == 0
        assert mock_gp.call_args.args[0] == "elevenlabs"
        assert mock_gp.call_args.kwargs.get("voice") == "es-ES-AlvaroNeural"

    def test_generate_with_timestamps_uses_selected_provider(self):
        with patch("shorts_creator.audio.generator.get_provider") as mock_gp:
            mock_provider = MagicMock()
            mock_provider.synthesize_with_timing_async = _edge_synth
            mock_gp.return_value = mock_provider
            asyncio.run(
                generator.generate_audio_with_timestamps(
                    "Hola mundo.", "out.mp3", "es-ES-ElviraNeural",
                    tts_provider="elevenlabs",
                )
            )
        assert mock_gp.call_args.args[0] == "elevenlabs"
        assert mock_gp.call_args.kwargs.get("voice") == "es-ES-ElviraNeural"

    def test_no_hardcoded_edge_selection_in_runtime_source(self):
        source = generator.__file__
        src = Path(source).read_text()
        fn_start = src.index("async def generate_audio_with_timestamps")
        fn_src = src[fn_start:src.index("\n\n", fn_start)]
        assert 'get_provider("edge_tts"' not in fn_src
        assert 'get_provider(\'edge_tts\'' not in fn_src


class TestEdgeBaseline:
    def test_edge_word_boundary_metadata(self):
        from shorts_creator.audio.tts_provider import EdgeTTSProvider
        assert EdgeTTSProvider().metadata.timing_support == "word"

    def test_edge_synth_with_timing_async_emits_word_boundaries(self):
        from shorts_creator.audio.tts_provider import EdgeTTSProvider
        import edge_tts
        from edge_tts import SubMaker
        provider = EdgeTTSProvider(voice="es-ES-AlvaroNeural")

        async def fake_stream():
            yield {"type": "WordBoundary", "offset": 0, "duration": 4000000, "text": "Hola"}
            yield {"type": "WordBoundary", "offset": 4000000, "duration": 5000000, "text": "mundo"}

        calls = {}

        def fake_communicate(text, voice, **kwargs):
            calls["kwargs"] = kwargs
            return MagicMock(stream=fake_stream)

        monkey_orig = edge_tts.Communicate
        try:
            edge_tts.Communicate = fake_communicate
            result = asyncio.run(
                provider.synthesize_with_timing_async("Hola", "/tmp/e.mp3", generator.TTSOptions())
            )
        finally:
            edge_tts.Communicate = monkey_orig
        assert calls["kwargs"].get("boundary") == "WordBoundary"
        assert result.timing_data["timing_source"] == "edge_tts_word_boundary"

    def test_edge_per_scene_source_unchanged(self, tmp_path):
        meta_path, _ = _make_scene_meta(tmp_path)
        with patch("shorts_creator.audio.generator.get_provider") as mock_gp:
            mock_gp.return_value = MagicMock(synthesize_with_timing_async=_edge_synth)
            asyncio.run(
                generator.main_per_scene(
                    meta_path, "es-ES-AlvaroNeural", tts_provider="edge_tts"
                )
            )
        data = json.loads(meta_path.read_text())
        st = data["script"]["scenes"][0]["subtitleTiming"]
        assert st["timingSource"] == "edge_tts_word_boundary"
        assert len(st["cues"]) >= 1


class TestElevenLabsSlice1:
    def test_elevenlabs_metadata_does_not_claim_native_timing(self):
        from shorts_creator.audio.tts_provider import ElevenLabsProvider
        provider = ElevenLabsProvider(api_key="x")
        assert provider.metadata.timing_support == "none"

    def test_no_timing_data_falls_back_to_estimated(self, tmp_path):
        meta_path, _ = _make_scene_meta(tmp_path)
        with patch("shorts_creator.audio.generator.get_provider") as mock_gp:
            mock_gp.return_value = MagicMock(synthesize_with_timing_async=_bare_synth)
            exit_code = asyncio.run(
                generator.main_per_scene(
                    meta_path, "some-voice", tts_provider="elevenlabs"
                )
            )
        assert exit_code == 0
        data = json.loads(meta_path.read_text())
        st = data["script"]["scenes"][0]["subtitleTiming"]
        assert st["timingSource"] == "estimated"
        assert len(st["cues"]) >= 1

    def test_missing_credentials_fail_explicitly(self, tmp_path, capsys):
        meta_path, _ = _make_scene_meta(tmp_path)
        with patch("shorts_creator.audio.generator.get_provider") as mock_gp:
            mock_gp.return_value = MagicMock(is_available=lambda: False)
            exit_code = asyncio.run(
                generator.generate_audio(
                    metadata_path=meta_path,
                    voice="some-voice",
                    tts_provider="elevenlabs",
                    subtitle_timing_provider="auto",
                )
            )
        assert exit_code == 1
        assert "not available" in capsys.readouterr().out


class TestMetadataPersistence:
    def test_provider_and_voice_persisted(self, tmp_path):
        meta_path, _ = _make_scene_meta(tmp_path)
        with patch("shorts_creator.audio.generator.get_provider") as mock_gp:
            mock_gp.return_value = MagicMock(synthesize_with_timing_async=_edge_synth)
            asyncio.run(
                generator.main_per_scene(
                    meta_path, "voice-B", tts_provider="elevenlabs"
                )
            )
        data = json.loads(meta_path.read_text())
        assert data["audio"]["provider"] == "elevenlabs"
        assert data["audio"]["voice"] == "voice-B"

    def test_active_duration_source_is_provider_neutral(self, tmp_path):
        meta_path, _ = _make_scene_meta(tmp_path)
        with patch("shorts_creator.audio.generator.get_provider") as mock_gp:
            mock_gp.return_value = MagicMock(synthesize_with_timing_async=_edge_synth)
            asyncio.run(
                generator.main_per_scene(
                    meta_path, "es-ES-AlvaroNeural", tts_provider="edge_tts"
                )
            )
        data = json.loads(meta_path.read_text())
        entry = data["audio"]["scenes"][0]
        assert entry["activeDurationSource"] == "subtitle_timing_last_cue_plus_guard"
        assert entry["activeAudioDurationSec"] == pytest.approx(1.35)


class TestContinuousGuard:
    def test_continuous_edge_unchanged(self, tmp_path, monkeypatch):
        meta_path, _ = _make_scene_meta(tmp_path)
        called = {}

        async def fake_main_continuous(*args, **kwargs):
            called["yes"] = True
            return 0

        monkeypatch.setattr(generator, "main_continuous", fake_main_continuous)
        with patch("shorts_creator.audio.generator.get_provider") as mock_gp:
            mock_gp.return_value = MagicMock(is_available=lambda: True)
            exit_code = asyncio.run(
                generator.generate_audio(
                    metadata_path=meta_path,
                    voice="es-ES-AlvaroNeural",
                    tts_provider="edge_tts",
                    subtitle_timing_provider="auto",
                    continuous=True,
                )
            )
        assert exit_code == 0
        assert called["yes"]

    def test_continuous_non_edge_fails_explicitly(self, tmp_path, monkeypatch, capsys):
        meta_path, _ = _make_scene_meta(tmp_path)
        called = {}

        async def fake_main_continuous(*args, **kwargs):
            called["yes"] = True
            return 0

        monkeypatch.setattr(generator, "main_continuous", fake_main_continuous)
        with patch("shorts_creator.audio.generator.get_provider") as mock_gp:
            mock_gp.return_value = MagicMock(is_available=lambda: True)
            exit_code = asyncio.run(
                generator.generate_audio(
                    metadata_path=meta_path,
                    voice="some-voice",
                    tts_provider="elevenlabs",
                    subtitle_timing_provider="auto",
                    continuous=True,
                )
            )
        assert exit_code == 1
        assert "CONTINUOUS_TTS_PROVIDER_UNSUPPORTED" in capsys.readouterr().out
        assert "yes" not in called

    def test_continuous_non_edge_does_not_mutate_metadata(self, tmp_path, monkeypatch):
        meta_path, _ = _make_scene_meta(tmp_path)
        with patch("shorts_creator.audio.generator.get_provider") as mock_gp:
            mock_gp.return_value = MagicMock(is_available=lambda: True)
            asyncio.run(
                generator.generate_audio(
                    metadata_path=meta_path,
                    voice="some-voice",
                    tts_provider="elevenlabs",
                    subtitle_timing_provider="auto",
                    continuous=True,
                )
            )
        data = json.loads(meta_path.read_text())
        assert "audio" not in data
