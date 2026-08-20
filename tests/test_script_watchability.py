"""Tests for the script-watchability-v1 editorial contract (offline).

All assertions are prompt-content invariants; no LLM, network or provider calls.
"""

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from shorts_creator.script.generator import (  # noqa: E402
    SYSTEM_PROMPT_V2,
    VOICEOVER_COMPRESSION_SYSTEM_PROMPT,
    VOICEOVER_REPAIR_SYSTEM_PROMPT,
    _build_duration_prompt_instruction_v2,
    _build_voiceover_repair_prompt,
)


def _budget():
    return {
        "targetSec": 30,
        "minSec": 27,
        "maxSec": 33,
        "minimumWords": 50,
        "preferredWords": 60,
        "maximumWords": 65,
        "estimatedScenePauseMs": 350,
        "minSceneCount": 4,
        "preferredSceneCount": 5,
        "maxSceneCount": 6,
        "targetSceneDurationSec": 6,
        "sceneCount": 5,
    }


def _base_script(n=5):
    return {
        "title": "T",
        "hook": "Apertura",
        "summary": "S",
        "scenes": [
            {
                "sceneNumber": i,
                "purpose": "context",
                "narrativeFunction": "hook" if i == 1 else "setup",
                "voiceover": " ".join(f"palabra{i}_{j}" for j in range(1, 13)),
                "subtitle": "sub",
                "targetDurationSec": 6,
                "visualPlan": {
                    "_schemaVersion": 2,
                    "visualIntent": "explain",
                    "subjects": ["aurora boreal"],
                    "searchQueries": ["aurora borealis night sky"],
                    "assetPreferences": ["photograph"],
                    "visualSequence": [
                        {
                            "segmentIndex": 1,
                            "assetPreference": "photograph",
                            "mediaPreference": "IMAGE_PREFERRED",
                            "searchQuery": "aurora borealis night sky",
                            "durationFraction": 1.0,
                            "transition": "cut",
                        }
                    ],
                },
            }
            for i in range(1, n + 1)
        ],
    }


# ── Initial prompt: editorial contract ──────────────────────────────────────


class TestInitialPromptEditorialContract:
    def test_editorial_contract_section_present(self):
        assert "Contrato editorial (watchability)" in SYSTEM_PROMPT_V2
        assert "Cada frase debe aportar información o progresión" in SYSTEM_PROMPT_V2
        assert "mecanismo" in SYSTEM_PROMPT_V2.lower()
        assert "moralejas artificiales" in SYSTEM_PROMPT_V2

    def test_progression_guidance_present(self):
        assert "hook → contexto mínimo → mecanismo/tensión" in SYSTEM_PROMPT_V2
        assert "consecuencia/payoff → cierre" in SYSTEM_PROMPT_V2
        assert "lista independiente de hechos" in SYSTEM_PROMPT_V2

    def test_factuality_present(self):
        assert "nunca inventes cifras, fechas, nombres, mecanismos ni hechos" in SYSTEM_PROMPT_V2
        assert "explica el mecanismo con precisión" in SYSTEM_PROMPT_V2

    def test_hook_first_sentence_priority(self):
        assert "Hook (escena 1)" in SYSTEM_PROMPT_V2
        assert "razón concreta para seguir viendo" in SYSTEM_PROMPT_V2
        assert "escena 1 es el hook real" in SYSTEM_PROMPT_V2

    def test_anti_introduction(self):
        assert "Hoy vamos a hablar de..." in SYSTEM_PROMPT_V2
        assert "En este vídeo veremos..." in SYSTEM_PROMPT_V2
        assert "Te voy a contar..." in SYSTEM_PROMPT_V2
        assert "Prepárate para..." in SYSTEM_PROMPT_V2

    def test_anti_empty_clickbait(self):
        assert "muletilla vacía" in SYSTEM_PROMPT_V2
        assert "Lo que ocurre después" in SYSTEM_PROMPT_V2
        assert "sin clickbait sin payoff" in SYSTEM_PROMPT_V2

    def test_anti_moraleja_closing_patterns(self):
        assert "nos enseña que..." in SYSTEM_PROMPT_V2
        assert "es una lección" in SYSTEM_PROMPT_V2
        assert "así que la próxima vez..." in SYSTEM_PROMPT_V2
        assert "en conclusión..." in SYSTEM_PROMPT_V2

    def test_cta_not_obligatory(self):
        assert "No es obligatorio un CTA de seguimiento" in SYSTEM_PROMPT_V2
        assert "El CTA de seguimiento debe incluirse" not in SYSTEM_PROMPT_V2
        assert "El CTA debe" not in SYSTEM_PROMPT_V2

    def test_no_promotional_cta_demands(self):
        for banned in ("Síguenos para más", "No olvides dejar tu like", "Comenta"):
            assert banned not in SYSTEM_PROMPT_V2

    def test_generic_topical_question_explicitly_discouraged(self):
        s = " ".join(SYSTEM_PROMPT_V2.split())
        assert "pregunta que solo pregunta si el espectador conoce o sabe cómo funciona el tema" in s
        assert "NO es por sí sola un hook fuerte" in s
        assert "¿Sabes cómo funciona X?" in s
        assert "¿Te has preguntado cómo funciona X?" in s
        assert "¿Conoces X?" in s

    def test_question_with_concrete_content_remains_allowed(self):
        s = " ".join(SYSTEM_PROMPT_V2.split())
        assert "ni se prohíben las preguntas buenas" in s
        assert "salvo que la misma frase aporte de inmediato un hecho" in s
        assert "entregue contenido desde el primer momento" in s

    def test_generic_adjective_only_closing_discouraged(self):
        s = " ".join(SYSTEM_PROMPT_V2.split())
        assert "adjetivos genéricos" in s
        assert "X es eficiente y versátil" in s
        assert "X es increíble/fascinante" in s
        assert "por eso X es tan importante" in s

    def test_concrete_payoff_closing_preferred(self):
        s = " ".join(SYSTEM_PROMPT_V2.split())
        assert "última consecuencia concreta" in s
        assert "propiedad específica" in s
        assert "payoff" in s
        assert "implicación directa de lo explicado" in s


# ── CTA consistency across surfaces ─────────────────────────────────────────


class TestCtaConsistency:
    def test_duration_instruction_no_obligatory_cta(self):
        p = _build_duration_prompt_instruction_v2(_budget(), "balanced")
        assert "El CTA de seguimiento debe incluirse" not in p
        assert "El CTA debe" not in p
        assert "puede ser el cierre sin CTA" in p

    def test_repair_system_prompt_no_obligatory_cta(self):
        assert "El CTA de seguimiento debe incluirse" not in VOICEOVER_REPAIR_SYSTEM_PROMPT
        assert "llamadas a la acción" in VOICEOVER_REPAIR_SYSTEM_PROMPT  # as a prohibition

    def test_compression_system_prompt_shape_intact(self):
        assert "SOLO JSON" in VOICEOVER_COMPRESSION_SYSTEM_PROMPT
        assert "sceneNumber" in VOICEOVER_COMPRESSION_SYSTEM_PROMPT
        assert "voiceover" in VOICEOVER_COMPRESSION_SYSTEM_PROMPT
        assert "assetPreferences" not in VOICEOVER_COMPRESSION_SYSTEM_PROMPT
        assert "visualSequence" not in VOICEOVER_COMPRESSION_SYSTEM_PROMPT
        assert "No devuelvas" in VOICEOVER_COMPRESSION_SYSTEM_PROMPT


# ── REPAIR system prompt: EXPAND/COMPRESS policy ────────────────────────────


class TestRepairSystemPromptPolicy:
    def test_expand_policy(self):
        sp = VOICEOVER_REPAIR_SYSTEM_PROMPT
        assert "causa o mecanismo" in sp
        assert "detalle concreto relevante" in sp
        assert "consecuencia" in sp
        assert "ejemplo útil" in sp

    def test_expand_anti_filler(self):
        sp = VOICEOVER_REPAIR_SYSTEM_PROMPT
        assert "NO repitas lo mismo" in sp
        assert "reformules para ocupar espacio" in sp
        assert "NO añadas" in sp
        assert "moralejas, introducciones" in sp
        assert "ni inventes datos" in sp

    def test_compress_policy(self):
        sp = VOICEOVER_REPAIR_SYSTEM_PROMPT
        assert "1) redundancia" in sp
        assert "2) intensificadores" in sp
        assert "3) contexto prescindible" in sp
        assert "4) conectores" in sp
        assert "5) frases accesorias" in sp

    def test_compress_preservation(self):
        sp = VOICEOVER_REPAIR_SYSTEM_PROMPT
        assert "hook, hechos concretos, causa/efecto, mecanismo, payoff y tono" in sp
        assert "No conviertas un hook" in sp
        assert "introducción genérica" in sp

    def test_hook_payoff_preservation_expand(self):
        sp = VOICEOVER_REPAIR_SYSTEM_PROMPT
        assert "hook de la escena 1" in sp
        assert "payoff y el tono" in sp

    def test_no_bootstrap_keys_in_repair_system_prompt(self):
        sp = VOICEOVER_REPAIR_SYSTEM_PROMPT
        assert "minimumWords" not in sp
        assert "maximumWords" not in sp


# ── Generated repair prompt (direction-specific blocks) ─────────────────────


class TestGeneratedRepairPromptDirection:
    def _expand_prompt(self):
        return _build_voiceover_repair_prompt(
            _base_script(),
            direction="EXPAND",
            current_word_count=60,
            target_total_words=75,
            scene_word_targets=[15, 15, 15, 15, 15],
        )

    def _compress_prompt(self):
        return _build_voiceover_repair_prompt(
            _base_script(),
            direction="COMPRESS",
            current_word_count=60,
            target_total_words=45,
            scene_word_targets=[9, 9, 9, 9, 9],
        )

    def test_expand_policy_block_present(self):
        p = self._expand_prompt()
        assert "## Política editorial EXPAND" in p
        assert "causa o mecanismo, detalle concreto" in p
        assert "no añadas" in p
        assert "adjetivos, moralejas, introducciones" in p
        assert "ni inventes datos" in p

    def test_compress_policy_block_present(self):
        p = self._compress_prompt()
        assert "## Política editorial COMPRESS" in p
        assert "redundancia, intensificadores, contexto prescindible" in p
        assert "hook, hechos concretos, causa/efecto, mecanismo, payoff y tono" in p
        assert "No conviertas un hook concreto en una introducción genérica" in p

    def test_expand_block_absent_on_compress(self):
        p = self._compress_prompt()
        assert "## Política editorial EXPAND" not in p

    def test_compress_block_absent_on_expand(self):
        p = self._expand_prompt()
        assert "## Política editorial COMPRESS" not in p

    def test_repair_prompt_has_no_bootstrap_keys(self):
        for direction in ("EXPAND", "COMPRESS"):
            p = _build_voiceover_repair_prompt(
                _base_script(),
                direction=direction,
                current_word_count=60,
                target_total_words=45,
                scene_word_targets=[9, 9, 9, 9, 9],
            )
            assert "minimumWords" not in p
            assert "maximumWords" not in p

    def test_repair_prompt_preserves_structure_invariants(self):
        p = self._expand_prompt()
        assert '"sceneNumber"' in p
        assert '"voiceover"' in p
        assert "No modifiques ningún campo visual ni estructural" in p
        assert "No añadas ni elimines escenas" in p


# ── Contracts intact ────────────────────────────────────────────────────────


class TestContractsIntact:
    def test_duration_instruction_keeps_global_limit(self):
        p = _build_duration_prompt_instruction_v2(_budget(), "balanced")
        assert "LÍMITE ABSOLUTO" in p
        assert "no superes 65 palabras" in p
        assert "El límite global prevalece" in p

    def test_compression_prompt_keeps_preservation_policy(self):
        from shorts_creator.script.generator import _build_voiceover_compression_prompt

        # The preservation policy lives in the compression SYSTEM prompt.
        assert "el hook, los hechos concretos, la causa/efecto y el payoff" in VOICEOVER_COMPRESSION_SYSTEM_PROMPT
        assert "no conviertas un hook concreto en una introducción genérica" in VOICEOVER_COMPRESSION_SYSTEM_PROMPT

        script = _base_script()
        targets = [12, 12, 12, 12, 12]
        p = _build_voiceover_compression_prompt(
            script, _budget(), actual_word_count=72, scene_word_targets=targets,
            allow_generated_images=False,
        )
        assert "no puede superar 65 palabras" in p

    def test_repair_schema_intact(self):
        from shorts_creator.script.generator import _apply_voiceover_repair

        base = _base_script()
        before = base["scenes"][0]["visualPlan"]
        payload = {
            "scenes": [
                {"sceneNumber": i, "voiceover": f"nueva{i} " + "x" * 10}
                for i in range(1, 6)
            ]
        }
        merged, errs = _apply_voiceover_repair(
            base, payload, expected_scene_numbers=[1, 2, 3, 4, 5],
        )
        assert errs == []
        assert merged is not None
        # visualPlan is never touched by a repair.
        assert merged["scenes"][0]["visualPlan"] == before
        assert [s["sceneNumber"] for s in merged["scenes"]] == [1, 2, 3, 4, 5]