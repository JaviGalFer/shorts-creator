# Proposal: Voice Provider Benchmark

## Problem

The current production voice (`edge_tts` → `es-ES-AlvaroNeural`) is functional but lacks the naturalness and expressiveness desired for historical storytelling. Need a reproducible evaluation framework to compare TTS providers and select a primary voice.

## Scope

**In scope:**
- TTS provider interface definition
- Benchmark script using current Constantinopla narration (~27s)
- Audio generation and measurement for available providers
- Comparison table with objective metrics
- Documentation of commercial licensing status

**Out of scope (for this change):**
- Asset modifications
- Visual render pipeline changes
- Subtitle/timing changes
- Image pipeline changes
- Duration changes
- Production voice switch (requires human review of samples)

## Solution

1. Define `TTSProvider` abstract interface with standard methods
2. Implement adapters for: edge_tts, ElevenLabs, Google Cloud TTS, Azure Speech, Piper
3. Run benchmark with identical text (Constantinopla voiceover)
4. Measure: duration, silence, sample rate, file size, timing support, cost, commercial status
5. Produce comparison table and recommendation
6. All adapters prepared; unconfigured providers marked `PENDIENTE_DE_VALIDAR`

## Success Criteria

- Interface defined and implemented
- Benchmark runs without errors for available providers
- Comparison table complete with real measurements
- Primary voice + fallback recommended
- Production voice unchanged until human approval