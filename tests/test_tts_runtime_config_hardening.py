"""Runtime configuration hardening for provider-specific TTS.

Proves project-.env resolution reaches the provider, provider-specific voice
wins over the implicit Edge default, and secrets never persist to metadata.
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from shorts_creator.audio import generator
from shorts_creator.audio import tts_provider as tp


async def _synth(text, output_path, options=None):
    Path(str(output_path)).write_bytes(b"\xff\xfb" + b"\x00" * 5000)
    r = MagicMock()
    r.timing_data = {"word_boundaries": [
        {"startSec": .1, "endSec": .6, "text": "Hola"},
        {"startSec": .7, "endSec": 1.3, "text": "mundo"},
    ], "sentence_boundaries": [], "timing_source": "elevenlabs_normalized_alignment"}
    return r


class TestEffectiveVoice:
    def _run(self, tmp_path, monkeypatch, *, tts_provider, voice=None, env=None):
        job = tmp_path / "job"
        job.mkdir()
        (job / "scenes").mkdir()
        meta_path = job / "metadata.json"
        meta = {"jobId": "cfg", "script": {"scenes": [
            {"sceneNumber": 1, "voiceover": "Hola mundo", "targetDurationSec": 6},
        ]}}
        meta_path.write_text(json.dumps(meta))
        for k, v in (env or {}).items():
            monkeypatch.setitem(generator._ENV, k, v)
        monkeypatch.setattr(generator, "_get_mp3_duration", lambda p: (6.0, "ffprobe_local"))
        provider = MagicMock()
        provider.is_available = lambda: True
        provider.synthesize_with_timing_async = _synth
        with patch("shorts_creator.audio.generator.get_provider") as mock_gp:
            mock_gp.return_value = provider
            exit_code = asyncio.run(generator.generate_audio(
                metadata_path=meta_path, voice=voice, tts_provider=tts_provider,
                subtitle_timing_provider="auto",
            ))
        data = json.loads(meta_path.read_text())
        return exit_code, data, mock_gp

    def test_edge_default_voice_alvaro(self, tmp_path, monkeypatch):
        _, _, mock_gp = self._run(tmp_path, monkeypatch, tts_provider="edge_tts")
        assert mock_gp.call_args.kwargs["voice"] == "es-ES-AlvaroNeural"

    def test_edge_explicit_tts_voice_env(self, tmp_path, monkeypatch):
        _, _, mock_gp = self._run(
            tmp_path, monkeypatch, tts_provider="edge_tts",
            env={"TTS_VOICE": "es-ES-ElviraNeural"},
        )
        assert mock_gp.call_args.kwargs["voice"] == "es-ES-ElviraNeural"

    def test_elevenlabs_voice_id_wins_over_edge_default(self, tmp_path, monkeypatch):
        _, _, mock_gp = self._run(
            tmp_path, monkeypatch, tts_provider="elevenlabs",
            env={"ELEVENLABS_VOICE_ID": "abc123"},
        )
        assert mock_gp.call_args.kwargs["voice"] == "abc123"
        assert mock_gp.call_args.kwargs["voice"] != "es-ES-AlvaroNeural"

    def test_explicit_cli_voice_overrides_provider_voice(self, tmp_path, monkeypatch):
        _, _, mock_gp = self._run(
            tmp_path, monkeypatch, tts_provider="elevenlabs", voice="xyz789",
            env={"ELEVENLABS_VOICE_ID": "abc123"},
        )
        assert mock_gp.call_args.kwargs["voice"] == "xyz789"

    def test_secret_and_voice_persist_correctly_no_api_key(self, tmp_path, monkeypatch):
        _, data, _ = self._run(
            tmp_path, monkeypatch, tts_provider="elevenlabs",
            env={"ELEVENLABS_API_KEY": "secret-api", "ELEVENLABS_VOICE_ID": "abc123"},
        )
        assert data["audio"]["provider"] == "elevenlabs"
        assert data["audio"]["voice"] == "abc123"
        serialized = json.dumps(data)
        assert "secret-api" not in serialized
        assert "api_key" not in serialized

    def test_initial_and_regeneration_consistent(self, tmp_path, monkeypatch):
        _, data, _ = self._run(
            tmp_path, monkeypatch, tts_provider="elevenlabs",
            env={"ELEVENLABS_VOICE_ID": "abc123"},
        )
        config = generator.resolve_audio_regeneration_config(data)
        assert config["tts_provider"] == "elevenlabs"
        assert config["voice"] == "abc123"


class TestEnvResolution:
    def test_env_only_api_key_reaches_provider(self, tmp_path, monkeypatch):
        mock_gp = self._run_generated(
            tmp_path, monkeypatch,
            env={"ELEVENLABS_API_KEY": "env-key", "ELEVENLABS_VOICE_ID": "abc123"},
        )
        assert mock_gp.call_args.kwargs["api_key"] == "env-key"

    def test_env_only_model_id_reaches_provider(self, tmp_path, monkeypatch):
        mock_gp = self._run_generated(
            tmp_path, monkeypatch,
            env={"ELEVENLABS_MODEL_ID": "eleven_multilingual_v3", "ELEVENLABS_VOICE_ID": "abc123"},
        )
        assert mock_gp.call_args.kwargs["model_id"] == "eleven_multilingual_v3"

    def test_edge_gets_no_provider_kwargs(self, tmp_path, monkeypatch):
        mock_gp = self._run_generated(tmp_path, monkeypatch, tts_provider="edge_tts")
        assert "api_key" not in mock_gp.call_args.kwargs
        assert "model_id" not in mock_gp.call_args.kwargs

    def _run_generated(self, tmp_path, monkeypatch, *, tts_provider="elevenlabs", env=None):
        job = tmp_path / "job"
        job.mkdir()
        (job / "scenes").mkdir()
        meta_path = job / "metadata.json"
        meta = {"jobId": "cfg2", "script": {"scenes": [
            {"sceneNumber": 1, "voiceover": "Hola mundo", "targetDurationSec": 6},
        ]}}
        meta_path.write_text(json.dumps(meta))
        for k, v in (env or {}).items():
            monkeypatch.setitem(generator._ENV, k, v)
        monkeypatch.setattr(generator, "_get_mp3_duration", lambda p: (6.0, "ffprobe_local"))
        provider = MagicMock()
        provider.is_available = lambda: True
        provider.synthesize_with_timing_async = _synth
        with patch("shorts_creator.audio.generator.get_provider") as mock_gp:
            mock_gp.return_value = provider
            asyncio.run(generator.generate_audio(
                metadata_path=meta_path, voice=None, tts_provider=tts_provider,
                subtitle_timing_provider="auto",
            ))
        return mock_gp


class TestDefensiveNormalizer:
    def test_non_string_characters_rejected(self):
        for chars in (["H", None], ["H", 42], [None]):
            al = {"characters": chars,
                  "character_start_times_seconds": [0.0] * len(chars),
                  "character_end_times_seconds": [0.1] * len(chars)}
            assert tp._is_valid_alignment(al) is False
            assert tp._normalize_character_alignment_to_words(al) == []


class TestMalformedBase64:
    def _provider(self):
        return tp.ElevenLabsProvider(api_key="k", voice_id="abc123", model_id="eleven_multilingual_v2")

    def _resp(self, audio_b64):
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.json = MagicMock(return_value={"audio_base64": audio_b64})
        return mock

    def test_invalid_base64_fails_explicitly(self, tmp_path):
        provider = self._provider()
        out = tmp_path / "scene.mp3"
        with patch("requests.post") as mock_post:
            mock_post.return_value = self._resp("!!!not-base64!!!")
            with pytest.raises(RuntimeError, match="invalid audio_base64"):
                asyncio.run(provider.synthesize_with_timing_async(
                    "Hola", str(out), tp.TTSOptions(voice="abc123")
                ))
        assert not out.exists()