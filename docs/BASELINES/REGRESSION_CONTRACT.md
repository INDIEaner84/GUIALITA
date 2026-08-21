# GUIALITA Regression Contract

**Effective**: 2026-08-19
**Baseline**: GUIALITA-VOICE-ACTIVATION-V1-PASS
**Scope**: All future MUSCAL/GUIALITA changes

---

## Purpose

This contract defines which GUIALITA subsystems must not regress unless explicitly authorized. Any code change, refactor, dependency update, or new feature must pass all regression gates defined here before being considered complete.

---

## Regression Gates

```text
CHAT_REGRESSION       = FAIL if POST /chat broken
SESSION_REGRESSION    = FAIL if session continuity broken
MEMORY_REGRESSION     = FAIL if memory entities/relations inaccessible
GRAPH_REGRESSION      = FAIL if graph nodes/edges inaccessible
TTS_REGRESSION        = FAIL if POST /audio/tts broken
VOICE_REGRESSION      = FAIL if voice activation broken
AUDIO_REGRESSION      = FAIL if GET /audio/status broken
OLLAMA_REGRESSION     = FAIL if Ollama PID changed or config modified
DEPENDENCY_REGRESSION = FAIL if new heavy dependencies added
DIAGNOSTICS_REGRESSION = FAIL if GET /diagnostics broken or paths unresolved
```

## Test Suites (must all PASS)

| Suite | Tests | Voraussetzung | Deckt ab |
|---|---|---|---|
| `tests/test_voice_activation.py` | 37 | keine | Voice-Zustandsautomat, STT/Chat/TTS-Anbindung |
| `tests/test_api.py` | 23 | Backend | alle HTTP-Endpunkte inkl. /diagnostics |
| `tests/test_memory_retrieval.py` | 17 | Backend | Embedding + Retrieval |
| `tests/test_memory.py` | 16 | Backend | Session + Memory-Store |
| `tests/test_tts.py` | 16 | Backend, TTS-Runtime | TTS-Erzeugung + Regression |
| `tests/test_memory_graph.py` | 14 | Backend | Entities/Relationen + Graph-Abfrage |
| `tests/test_graph_visualization.py` | 13 | Backend | Graph-API + Frontend |
| `tests/test_process_audio.py` | 5 | LFM-Audio-Runtime, espeak-ng | WAV → Transkript (Batch) |
| `tests/test_capture.py` | 0 | Mikrofon, espeak-ng | Aufnahme (Prozedurskript, keine `test_*`-Methoden) |
| **Summe** | **141** | | **vollständige Regression** |

### Korrektur der Testzahl (2026-08-21)

Dieser Vertrag nannte zuvor **108** Tests, andere Dokumente 79, 71 bzw. 145.
Keine dieser Zahlen stimmte. Ursache: Drei Suiten starteten andere Suiten als
Subprozesse. Beim Lauf aller neun Suiten wurde `test_memory.py` **achtmal** und
`test_api.py` **sechsmal** ausgeführt — **35 Suite-Läufe statt 9**. Dieselben
Tests wurden mehrfach gezählt.

Die tatsächliche Zahl ist **141 Testfunktionen in 9 Suiten** (136 bei der Korrektur, +5 durch die Tests für `/diagnostics`).

Verbindlicher Lauf:

```bash
python3 scripts/run_all_tests.py          # jede Suite genau einmal
python3 scripts/run_all_tests.py --list   # Inventar ohne Ausführung
```

Verschachtelte Suite-Aufrufe sind standardmäßig deaktiviert
(`GUIALITA_TEST_NESTED=1` stellt das alte Verhalten wieder her).

### Bewertungsregel

```text
PASS          Suite vollständig bestanden
FAIL          echte Fehlschläge
NOT_EXECUTED  Voraussetzung fehlte (Backend, Mikrofon, GPU, Modelle, Runtime)
```

Tests aus einer `NOT_EXECUTED`-Suite dürfen **nicht** als bestanden gezählt
werden — auch dann nicht, wenn einzelne von ihnen durchliefen. Der Runner weist
sie deshalb getrennt aus.

## Subsystem Invariants

### Chat

- POST /chat returns `{status: "success", response: "..."}`
- Model field present in response
- Session ID present in response
- Latency measurable

### Session

- POST /sessions creates new session
- GET /sessions lists sessions
- Session ID persists across /chat requests
- History accessible via /sessions/{id}/messages

### Memory

- GET /memory/status returns entity_count and relation_count
- POST /memory/search returns results
- Memories indexed from chat messages

### Graph

- GET /memory/graph returns nodes and edges
- GET /memory/graph/{entity} returns entity with outgoing/incoming
- Provenance (source_memory_id) present on edges

### TTS

- GET /audio/tts/status returns available, model, voices
- POST /audio/tts with text returns audio/wav
- POST /audio/tts with empty text returns 400
- POST /audio/tts with invalid voice returns 400
- WAV valid (RIFF/WAVE, 24kHz, mono)

### Audio

- GET /audio/status returns online
- POST /audio/transcribe works (Whisper)
- POST /audio/chat works (STT + LLM)

### Voice Activation

- GET /audio/voice/status returns enabled, state, calibrated
- POST /audio/voice/start starts voice activation
- POST /audio/voice/stop stops voice activation
- State machine transitions correctly (IDLE → READY → RECORDING → PROCESSING → READY)
- Calibration runs on start
- Post-TTS cooldown prevents feedback loop

### Ollama

- PID unchanged
- No config modifications
- No model additions/removals

### Dependencies

- No new pip packages beyond what existed at TTS-V1-PASS
- Existing packages may be updated only if backward-compatible
- No new system-level dependencies

## Authorization Required

Changes to these require explicit authorization:

1. TTS model change (LFM2.5-Audio → different model)
2. TTS runtime change (llama-liquid-audio-cli → different runtime)
3. Session schema change (SQLite schema version bump)
4. Memory schema change (SQLite schema version bump)
5. Graph schema change (entities/relations structure)
6. Ollama configuration change
7. New heavy dependency (anything >10MB or with native extensions)

## Changes Permitted Without Authorization

1. Bug fixes that don't change API contracts
2. Performance improvements that don't change behavior
3. Documentation updates
4. Test additions (not modifications that weaken coverage)
5. Frontend cosmetic changes (colors, fonts, layout) that don't break functionality
6. Config value adjustments within documented ranges

## Enforcement

Before merging any change, run:

```bash
cd /media/hz/_Ext_Seagat/GUIALITA
/home/hz/.guialita-venv/bin/python -c "
import sys, unittest; sys.path.insert(0, '.')
from tests.test_tts import TestTTSService, TestTTSRegression
from tests.test_memory import *
from tests.test_api import *
from tests.test_graph_visualization import TestGraphVisualizationAPI
suite = unittest.TestSuite()
for cls in [TestTTSService, TestTTSRegression, TestGraphVisualizationAPI]:
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
result = unittest.TextTestRunner(verbosity=0).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
"
```

All tests must PASS. No exceptions.
