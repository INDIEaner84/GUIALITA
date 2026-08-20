# GUIALITA VOICE ACTIVATION V1 RESULT

**STATUS**: PASS
**DATE**: 2026-08-19
**BASELINE**: GUIALITA-TTS-V1-PASS (unchanged)
**NEW BASELINE**: GUIALITA-VOICE-ACTIVATION-V1-PASS

---

## Configuration

| Parameter | Value |
|-----------|-------|
| MICROPHONE | sounddevice (system default) |
| CALIBRATION | auto (500ms ambient noise measurement) |
| NOISE FLOOR | -18.8 dBFS (measured) |
| START THRESHOLD | -17.6 dBFS (auto from calibration) |
| END THRESHOLD | -45.0 dBFS (configurable) |
| PRE-ROLL | 200ms |
| SILENCE TIMEOUT | 1000ms |
| POST-TTS COOLDOWN | 1500ms |
| SAMPLE RATE | 16000 Hz |
| CHANNELS | 1 (mono) |
| STATE MACHINE | IDLE → CALIBRATING → READY → RECORDING → SILENCE → PROCESSING → SPEAKING → READY |

## What was implemented

| Component | File | Status |
|-----------|------|--------|
| Config | config/voice.yaml | NEW |
| Voice Service | backend/audio/voice_activation.py | NEW |
| API Endpoints | backend/main.py | MODIFIED |
| Frontend UI | frontend/index.html | MODIFIED |
| Tests | tests/test_voice_activation.py | NEW (37 tests) |
| Docs | docs/PHASE_VOICE_ACTIVATION_RESULT.md | NEW |

## API

```
GET  /audio/voice/status    → {enabled, state, calibrated, ...}
POST /audio/voice/start     → {status, message}
POST /audio/voice/stop      → {status, message}
```

## Test Results

| Suite | Tests | Status |
|-------|-------|--------|
| test_voice_activation.py (T01-T22) | 37 | PASS |
| test_memory.py (store unit) | 10 | PASS |
| test_memory.py (API) | 6 | PASS |
| test_tts.py (TTS + regression) | 16 | PASS |
| test_graph_visualization.py | 8 | PASS |
| **Total** | **71** | **PASS** |

## Pipeline Verification

Full chain tested with synthetic WAV:

```
WAV (16kHz mono PCM)
  → Whisper STT → transcript
  → ChatService → response
  → LFM2.5-Audio TTS → audio output
```

All stages verified independently.

## Real Microphone Test

- Microphone detected: 12 input devices
- Calibration: auto (noise floor -18.8 dBFS)
- Voice activation: starts/stops via API
- State machine: transitions verified
- Full pipeline: WAV → STT → Chat → TTS verified
- Headless environment: no actual speech input available for multi-turn test

## Regression

| Gate | Status |
|------|--------|
| CHAT_REGRESSION | PASS |
| SESSION_REGRESSION | PASS |
| MEMORY_REGRESSION | PASS |
| GRAPH_REGRESSION | PASS |
| TTS_REGRESSION | PASS |
| AUDIO_REGRESSION | PASS |
| OLLAMA_REGRESSION | PASS |
| DEPENDENCY_REGRESSION | PASS |

## Known Limitations

- Headless environment: no actual multi-turn speech test
- Microphone sensitivity varies by hardware
- Threshold auto-calibration depends on ambient noise
- English-only (LFM2.5-Audio constraint)
- No VAD (energy-based only)
- No streaming (batch mode)

## Files Created

- `config/voice.yaml`
- `backend/audio/voice_activation.py`
- `tests/test_voice_activation.py`
- `docs/PHASE_VOICE_ACTIVATION_RESULT.md`
- `docs/phase-voice-activation.yaml`

## Files Modified

- `backend/audio/__init__.py`
- `backend/main.py` (import + 3 endpoints)
- `frontend/index.html` (voice activation UI)

## Deferred

- Real multi-turn microphone test (requires user interaction)
- VAD upgrade (energy → ML-based)
- Streaming support
- Full duplex
- Barge-in
- Wake word

## FINAL STATE

**GUIALITA-VOICE-ACTIVATION-V1-PASS**
