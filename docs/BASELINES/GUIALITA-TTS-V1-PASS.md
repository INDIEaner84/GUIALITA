# GUIALITA-TTS-V1-PASS — Baseline

**Immutable Baseline Identifier**: `GUIALITA-TTS-V1-PASS`
**Date**: 2026-08-19
**Status**: FROZEN — Regression Baseline
**Validated**: 2026-08-19 (this document)

---

## Model

| Property | Value |
|----------|-------|
| Name | LFM2.5-Audio-1.5B |
| Format | GGUF Q4_0 |
| Size | ~1.1 GB (4 files) |
| Path | models/lfm-audio-1.5b/ |

## Runtime

| Property | Value |
|----------|-------|
| Binary | llama-liquid-audio-cli |
| Path | runtime/liquid-audio/ |
| Mode | CPU (on-demand per request) |
| Library | libliquid-audio.so, libllama.so, libmtmd.so |

## Voice

| Property | Value |
|----------|-------|
| Default | us_female |
| Available | us_female, us_male, uk_female, uk_male |

## Performance

| Metric | Value |
|--------|-------|
| Cold Latency | ~5.4s |
| Warm Latency | ~4.2s |
| WAV Duration | 2-4s (text-dependent) |
| WAV Format | 24kHz, mono, 32-bit float |

## API

### GET /audio/tts/status

```json
{
  "available": true,
  "model": "LFM2.5-Audio-1.5B",
  "runtime": "llama-liquid-audio-cli",
  "voices": ["us_female", "us_male", "uk_female", "uk_male"],
  "default_voice": "us_female"
}
```

### POST /audio/tts

Request:
```json
{"text": "...", "voice": "us_female"}
```

Response: `audio/wav` with headers `X-TTS-Voice`, `X-TTS-Duration-S`, `X-TTS-Latency-Ms`, `X-TTS-Sample-Rate`.

Error responses:
- 400: empty text, invalid voice
- 500: TTS failure

## Frontend

- TTS button row appears after each assistant response
- Button label: "Vorlesen"
- Shows duration and latency after generation
- Audio plays automatically via `<audio>` element

## Test State

| Suite | Tests | Status |
|-------|-------|--------|
| test_tts.py (T01-T11) | 11 | PASS |
| test_tts.py (T12-T16 regression) | 5 | PASS |
| test_memory.py | 16 | PASS |
| test_api.py | 18 | PASS |
| test_graph_visualization.py | 8 | PASS |
| **Total** | **58** | **PASS** |

## Known Limitations

- **English only** — LFM2.5-Audio offiziell nur English
- **No streaming** — Batch mode (Text → File → Bytes)
- **Cold start ~5s** — Model loaded per request
- **No resident model** — on-demand loading
- **WIP runner** — PR #18641 (Draft) based

## Files Involved

### Created
- `backend/audio/__init__.py`
- `backend/audio/tts.py`
- `tests/test_tts.py`
- `docs/PHASE_TTS_RESULT.md`
- `docs/phase-tts.yaml`

### Modified
- `backend/main.py` (import + 2 endpoints)
- `frontend/index.html` (TTS button + handler + CSS)

## Regression Requirements

Any change to the GUIALITA codebase must not break:

1. TTS generation (POST /audio/tts produces valid WAV)
2. TTS status (GET /audio/tts/status returns correct info)
3. Chat functionality (POST /chat returns response)
4. Session continuity (session persists across requests)
5. Memory (entities and relations accessible)
6. Graph (nodes and edges accessible)
7. Audio status (GET /audio/status returns online)
8. Ollama (PID unchanged, no config changes)
9. No new heavy dependencies

## Process State (at validation)

| Process | PID | Status |
|---------|-----|--------|
| Ollama | 2492667 | RUNNING, UNCHANGED |
| GUIALITA Backend | (varies) | ONLINE |

## Validation Command

```bash
cd /media/hz/_Ext_Seagat/GUIALITA
/home/hz/.guialita-venv/bin/python -c "
import sys, unittest; sys.path.insert(0, '.')
from tests.test_tts import TestTTSService, TestTTSRegression
suite = unittest.TestSuite()
suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestTTSService))
suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestTTSRegression))
result = unittest.TextTestRunner(verbosity=0).run(suite)
print('PASS' if result.wasSuccessful() else 'FAIL')
"
```
