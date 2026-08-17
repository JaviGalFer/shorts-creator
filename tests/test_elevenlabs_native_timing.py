"""Slice 2: ElevenLabs native /with-timestamps + character-to-word normalization.

Covers the pure normalizer, the mocked ElevenLabs provider (no live API calls),
and per-scene generator integration with a native-timing result.
"""

import asyncio
import base64
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from shorts_creator.audio import generator
from shorts_creator.audio import tts_provider as tp


# ─────────────────────────────────────────────────────────────────────────────
# Pure character → word normalizer
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalizer:
    def _align(self, chars, starts, ends):
        return {
            "characters": chars,
            "character_start_times_seconds": starts,
            "character_end_times_seconds": ends,
        }

    def test_hola_mundo_two_words(self):
        chars = list("Hola mundo")
        starts = [0.0, 0.1, 0.2, 0.3, 0.35, 0.5, 0.6, 0.7, 0.8, 0.9]
        ends = [0.1, 0.2, 0.3, 0.4, 0.45, 0.6, 0.7, 0.8, 0.9, 1.0]
        words = tp._normalize_character_alignment_to_words(self._align(chars, starts, ends))
        assert [w["text"] for w in words] == ["Hola", "mundo"]
        assert words[0]["startSec"] == 0.0 and words[0]["endSec"] == 0.4
        assert words[1]["startSec"] == 0.5 and words[1]["endSec"] == 1.0

    def test_punctuation_retained(self):
        chars = list("Hola, mundo.")
        starts = list(range(12))
        starts = [float(s) / 10 for s in starts]
        ends = [s + 0.09 for s in starts]
        words = tp._normalize_character_alignment_to_words(self._align(chars, starts, ends))
        assert [w["text"] for w in words] == ["Hola,", "mundo."]

    def test_multiple_spaces(self):
        chars = list("a  b")
        words = tp._normalize_character_alignment_to_words(self._align(chars, [0, 1, 2, 3], [1, 2, 3, 4]))
        assert [w["text"] for w in words] == ["a", "b"]

    def test_leading_trailing_whitespace(self):
        chars = list(" hi ")
        words = tp._normalize_character_alignment_to_words(self._align(chars, [0, 1, 2, 3], [1, 2, 3, 4]))
        assert [w["text"] for w in words] == ["hi"]

    def test_accented_unicode(self):
        chars = list("¿Qué ocurrió?")
        starts = [float(i) for i in range(len(chars))]
        ends = [s + 0.5 for s in starts]
        words = tp._normalize_character_alignment_to_words(self._align(chars, starts, ends))
        assert [w["text"] for w in words] == ["¿Qué", "ocurrió?"]

    def test_single_word(self):
        chars = list("Hola")
        words = tp._normalize_character_alignment_to_words(self._align(chars, [0, 1, 2, 3], [1, 2, 3, 4]))
        assert [w["text"] for w in words] == ["Hola"]

    def test_empty_alignment(self):
        for al in ({}, {"characters": [], "character_start_times_seconds": [], "character_end_times_seconds": []}, None):
            assert tp._normalize_character_alignment_to_words(al) == []

    def test_mismatched_lengths(self):
        chars = ["a", "b", "c"]
        al = {"characters": chars, "character_start_times_seconds": [0, 1], "character_end_times_seconds": [0, 1]}
        assert tp._normalize_character_alignment_to_words(al) == []

    def test_non_numeric_timestamps(self):
        chars = list("abc")
        al = {"characters": chars, "character_start_times_seconds": ["x", 1, 2], "character_end_times_seconds": [1, 2, 3]}
        assert tp._normalize_character_alignment_to_words(al) == []

    def test_nan_inf(self):
        chars = list("ab")
        nan = float("nan")
        inf = float("inf")
        assert tp._normalize_character_alignment_to_words(
            {"characters": chars, "character_start_times_seconds": [nan, 1], "character_end_times_seconds": [1, 2]}
        ) == []
        assert tp._normalize_character_alignment_to_words(
            {"characters": chars, "character_start_times_seconds": [0, inf], "character_end_times_seconds": [1, 2]}
        ) == []

    def test_negative_timestamps(self):
        chars = list("ab")
        al = {"characters": chars, "character_start_times_seconds": [-1, 1], "character_end_times_seconds": [1, 2]}
        assert tp._normalize_character_alignment_to_words(al) == []

    def test_end_before_start(self):
        chars = list("ab")
        al = {"characters": chars, "character_start_times_seconds": [1, 1], "character_end_times_seconds": [0.5, 2]}
        assert tp._normalize_character_alignment_to_words(al) == []

    def test_backwards_movement(self):
        chars = list("abc")
        al = {"characters": chars, "character_start_times_seconds": [0, 3, 1], "character_end_times_seconds": [1, 4, 2]}
        assert tp._normalize_character_alignment_to_words(al) == []

    def test_normalized_preferred_over_raw(self):
        norm = self._align(["i"], [0.5], [0.9])
        raw = self._align(["x"], [0.1], [0.4])
        assert tp._is_valid_alignment(norm)
        assert tp._normalize_character_alignment_to_words(norm) == [{"text": "i", "startSec": 0.5, "endSec": 0.9}]

    def test_validation_normalized_vs_raw(self):
        valid = self._align(["a"], [0.0], [0.1])
        bad = self._align(["a"], [0.1], [0.05])
        assert tp._is_valid_alignment(valid) and not tp._is_valid_alignment(bad)


# ─────────────────────────────────────────────────────────────────────────────
# ElevenLabs provider (mocked HTTP)
# ─────────────────────────────────────────────────────────────────────────────

class TestElevenLabsProvider:
    def _provider(self, voice_id="eleven-voice-42", api_key="secret-key"):
        return tp.ElevenLabsProvider(api_key=api_key, voice_id=voice_id, model_id="eleven_multilingual_v2")

    def _resp(self, audio_b64=None, alignment=None, normalized=None, status=200):
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.status_code = status
        body = {}
        if audio_b64 is not None:
            body["audio_base64"] = audio_b64
        if alignment is not None:
            body["alignment"] = alignment
        if normalized is not None:
            body["normalized_alignment"] = normalized
        mock.json = MagicMock(return_value=body)
        mock.content = b"\xff\xfb" + b"\x00" * 4000
        return mock

    def test_endpoint_and_auth(self, tmp_path):
        provider = self._provider()
        audio = base64.b64encode(b"\xff\xfb" + b"\x00" * 4000).decode()
        with patch("requests.post") as mock_post:
            mock_post.return_value = self._resp(audio_b64=audio)
            asyncio.run(provider.synthesize_with_timing_async(
                "Hola", str(tmp_path / "scene.mp3"), tp.TTSOptions(voice="eleven-voice-42")
            ))
        url = mock_post.call_args.args[0]
        assert "eleven-voice-42/with-timestamps" in url
        headers = mock_post.call_args.kwargs["headers"]
        assert headers["xi-api-key"] == "secret-key"
        payload = mock_post.call_args.kwargs["json"]
        assert payload["model_id"] == "eleven_multilingual_v2"

    def test_valid_normalized_alignment_produces_word_boundaries(self, tmp_path):
        provider = self._provider()
        audio = base64.b64encode(b"\xff\xfb" + b"\x00" * 4000).decode()
        norm = {"characters": list("Hola mundo"), "character_start_times_seconds": [0, .1, .2, .3, .35, .5, .6, .7, .8, .9],
                "character_end_times_seconds": [.1, .2, .3, .4, .45, .6, .7, .8, .9, 1.0]}
        with patch("requests.post") as mock_post:
            mock_post.return_value = self._resp(audio_b64=audio, normalized=norm)
            result = asyncio.run(provider.synthesize_with_timing_async(
                "Hola mundo", str(tmp_path / "scene.mp3"), tp.TTSOptions(voice="eleven-voice-42")
            ))
        assert result.provider == "elevenlabs"
        assert result.voice == "eleven-voice-42"
        assert result.timing_data["timing_source"] == "elevenlabs_normalized_alignment"
        assert [w["text"] for w in result.timing_data["word_boundaries"]] == ["Hola", "mundo"]

    def test_raw_alignment_fallback_when_normalized_missing(self, tmp_path):
        provider = self._provider()
        audio = base64.b64encode(b"\xff\xfb" + b"\x00" * 4000).decode()
        raw = {"characters": ["a"], "character_start_times_seconds": [0.0], "character_end_times_seconds": [0.1]}
        with patch("requests.post") as mock_post:
            mock_post.return_value = self._resp(audio_b64=audio, alignment=raw, normalized=None)
            result = asyncio.run(provider.synthesize_with_timing_async(
                "a", str(tmp_path / "scene.mp3"), tp.TTSOptions(voice="eleven-voice-42")
            ))
        assert result.timing_data["timing_source"] == "elevenlabs_alignment"

    def test_missing_alignment_audio_still_valid(self, tmp_path):
        provider = self._provider()
        audio = base64.b64encode(b"\xff\xfb" + b"\x00" * 4000).decode()
        with patch("requests.post") as mock_post:
            mock_post.return_value = self._resp(audio_b64=audio)
            result = asyncio.run(provider.synthesize_with_timing_async(
                "Hola", str(tmp_path / "scene.mp3"), tp.TTSOptions(voice="eleven-voice-42")
            ))
        assert (tmp_path / "scene.mp3").exists()
        assert result.timing_data is None

    def test_malformed_alignment_falls_back_safely(self, tmp_path):
        provider = self._provider()
        audio = base64.b64encode(b"\xff\xfb" + b"\x00" * 4000).decode()
        bad = {"characters": ["a", "b"], "character_start_times_seconds": [0], "character_end_times_seconds": [1]}
        with patch("requests.post") as mock_post:
            mock_post.return_value = self._resp(audio_b64=audio, normalized=bad)
            result = asyncio.run(provider.synthesize_with_timing_async(
                "ab", str(tmp_path / "scene.mp3"), tp.TTSOptions(voice="eleven-voice-42")
            ))
        assert result.timing_data is None
        assert (tmp_path / "scene.mp3").exists()

    def test_missing_audio_base64_fails(self, tmp_path):
        provider = self._provider()
        with patch("requests.post") as mock_post:
            mock_post.return_value = self._resp(audio_b64=None)
            with pytest.raises(RuntimeError):
                asyncio.run(provider.synthesize_with_timing_async(
                    "Hola", str(tmp_path / "scene.mp3"), tp.TTSOptions(voice="eleven-voice-42")
                ))

    def test_http_error_propagates(self, tmp_path):
        provider = self._provider()
        with patch("requests.post") as mock_post:
            mock_post.return_value.raise_for_status.side_effect = Exception("HTTPError 401")
            with pytest.raises(Exception):
                asyncio.run(provider.synthesize_with_timing_async(
                    "Hola", str(tmp_path / "scene.mp3"), tp.TTSOptions(voice="eleven-voice-42")
                ))

    def test_no_live_api_call(self, tmp_path, monkeypatch):
        provider = self._provider()
        audio = base64.b64encode(b"\xff\xfb" + b"\x00" * 4000).decode()
        with patch("shorts_creator.audio.tts_provider.asyncio.to_thread") as mock_thread:
            mock_thread.side_effect = lambda fn, *a, **k: fn(*a, **k)
            with patch("requests.post") as mock_post:
                mock_post.return_value = self._resp(audio_b64=audio)
                result = asyncio.run(provider.synthesize_with_timing_async(
                    "Hola", str(tmp_path / "scene.mp3"), tp.TTSOptions(voice="eleven-voice-42")
                ))
                assert result is not None


# ─────────────────────────────────────────────────────────────────────────────
# Generator integration with an ElevenLabs-native result
# ─────────────────────────────────────────────────────────────────────────────

async def _eleven_native_synth(text, output_path, options=None):
    Path(str(output_path)).write_bytes(b"\xff\xfb" + b"\x00" * 5000)
    r = MagicMock()
    r.timing_data = {
        "word_boundaries": [
            {"startSec": 0.1, "endSec": 0.5, "text": "Test"},
            {"startSec": 0.6, "endSec": 1.4, "text": "narration"},
        ],
        "sentence_boundaries": [],
        "timing_source": "elevenlabs_normalized_alignment",
    }
    return r


def _make_meta(tmp_path):
    job = tmp_path / "job"
    job.mkdir()
    (job / "scenes").mkdir()
    meta_path = job / "metadata.json"
    meta = {"jobId": "test-eleven-native", "script": {"scenes": [
        {"sceneNumber": 1, "voiceover": "Test narration.", "targetDurationSec": 6.0},
    ]}}
    meta_path.write_text(json.dumps(meta))
    return meta_path


@pytest.fixture
def _probe(monkeypatch):
    monkeypatch.setattr(generator, "_get_mp3_duration", lambda p: (6.576, "ffprobe_local"))


class TestGeneratorIntegration:
    def test_elevenlabs_native_main_per_scene(self, tmp_path, _probe):
        meta_path = _make_meta(tmp_path)
        with patch("shorts_creator.audio.generator.get_provider") as mock_gp:
            mock_gp.return_value = MagicMock(synthesize_with_timing_async=_eleven_native_synth)
            exit_code = asyncio.run(generator.main_per_scene(
                meta_path, "eleven-voice-42", tts_provider="elevenlabs"
            ))
        assert exit_code == 0
        data = json.loads(meta_path.read_text())
        assert data["audio"]["provider"] == "elevenlabs"
        assert data["audio"]["voice"] == "eleven-voice-42"
        st = data["script"]["scenes"][0]["subtitleTiming"]
        assert st["timingSource"] == "elevenlabs_normalized_alignment"
        assert len(st["cues"]) >= 1
        entry = data["audio"]["scenes"][0]
        assert entry["activeAudioDurationSec"] == pytest.approx(1.55)
        assert entry["activeDurationSource"] == "subtitle_timing_last_cue_plus_guard"

    def test_edge_regression_timing_source(self, tmp_path, _probe):
        meta_path = _make_meta(tmp_path)

        async def edge_synth(text, output_path, options=None):
            Path(str(output_path)).write_bytes(b"\xff\xfb" + b"\x00" * 5000)
            r = MagicMock()
            r.timing_data = {"word_boundaries": [{"startSec": .1, "endSec": .5, "text": "Test"}],
                             "sentence_boundaries": [], "timing_source": "edge_tts_word_boundary"}
            return r

        with patch("shorts_creator.audio.generator.get_provider") as mock_gp:
            mock_gp.return_value = MagicMock(synthesize_with_timing_async=edge_synth)
            asyncio.run(generator.main_per_scene(meta_path, "es-ES-AlvaroNeural", tts_provider="edge_tts"))
        data = json.loads(meta_path.read_text())
        assert data["script"]["scenes"][0]["subtitleTiming"]["timingSource"] == "edge_tts_word_boundary"