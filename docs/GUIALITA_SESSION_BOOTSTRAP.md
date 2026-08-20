# GUIALITA — Session Bootstrap

Dieses Dokument stellt den vollständigen Projektzustand für eine neue
ChatGPT/OpenCode-Session bereit. Es ersetzt KEINE Konversationshistorie,
sondern macht den Stand ohne sie nachvollziehbar.

---

## Canonical identity

GUIALITA ist das aktive Projekt. Lokaler lokaler LFM-Sprachassistent.
Repository-Wurzel: `/media/hz/_Ext_Seagat/GUIALITA/`

## Current state

```text
PHASE 0     PASS
PHASE 0.5   PASS
PHASE 1A    PASS
PHASE 1B    PASS
MEMORY      PASS
MEM-RET     PASS
MEM-GRAPH   PASS
GRAPH-VIS   PASS
TTS         PASS
PHASE 1C    NOT STARTED
```

## Current baseline

`GUIALITA-TTS-V1-PASS`

## Current hard stop

Memory-Session-Foundation + Memory-Retrieval V1 + Memory Graph Foundation sind abgeschlossen.

GraphRAG / Neural Embedding darf NICHT automatisch starten.

Eine explizite Autorisierung ist erforderlich.

## What MEMORY SESSION accomplished

- SQLite-Persistenz (stdlib, `data/guialita.db`, Rollback-Journal, kein WAL,
  busy_timeout 5000, Single-Writer-Lock, Schema V1 idempotent)
- Sessions (`SES-<uuidhex>`) + Messages (`MSG-<uuidhex>`, generation_id fortlaufend)
- ChatService: Session-Resolution, History-Persist, bounded recent history
  (recent_messages=10, max 12000 Zeichen, `config/memory.yaml`)
- API: POST/GET /sessions, GET /sessions/{id}/messages, /chat mit optionaler
  session_id (ohne → automatische neue Session)
- Adapter: chat(..., messages=None) abwärtskompatibel (llamacpp + ollama)
- Frontend: Session auto-erzeugen, session_id halten und mitsenden, Anzeige
- Echter Restart-Test PASS: „Mein Projekt heißt GUIALITA.“ → stop/start →
  „Wie heißt mein Projekt?“ → „Das Projekt heißt **GUIALITA**.“ (history_used=3)
- Tests: tests/test_memory.py 16/16 PASS; Regression API 18/18, Capture 7/7,
  Processing 13/13; Ollama-PID 2492667 unverändert

## What MEMORY RETRIEVAL accomplished

- Deterministisches Feature-Hashing Embedding (512-D, numpy, versioniert)
- memories-Tabelle in SQLite (Schema V2, Migration V1→V2 idempotent)
- MemoryIndexer: Indiziert user/assistant Messages automatisch nach Persistenz
- MemoryRetriever: Brute-Force Cosine-Similarity Suche über alle Sessions
- ContextBuilder: Baut LLM-Kontext aus [Memories] + [Recent History]
- Integration in ChatService: Retrieval → Kontext → LLM, Fallback bei Fehler
- API: GET /memory/status, POST /memory/search
- Cross-Session-Retrieval PASS: Session A Wissen → Session B (nach Restart) korrekt abgerufen
- Tests: test_memory_retrieval.py T01-T17 (10 Unit + 3 API + 4 Regression) PASS
- Real E2E PASS: "Mein Projekt heißt GUIALITA." → 26 Messages → Restart →
  Session B "Wie heißt mein Projekt?" → "Ihr Projekt heißt GUIALITA." (score=0.75)

## What MEMORY GRAPH accomplished

- Persistente Graph-Darstellung: entities + relations in SQLite (Schema V3)
- Deterministischer Entity-Extraktor (53 bekannte GUIALITA-Begriffe + Zitate + Pfade)
- Relation-Typen: uses, is_a, has, related_to (Co-occurrence Fallback)
- 1-Hop-Traversale (outgoing + incoming) mit Provenance
- Integration in MemoryIndexer: nach Memory-Persistenz → Entity-Extraktion → Graph
- API: GET /memory/graph/{entity_name}, /memory/status erweitert
- Graph-Retrieval ist OPTIONAL / INSPECTABLE (nicht automatisch im LLM)
- Tests: test_memory_graph.py T01-T14 (10 Unit + 2 API + 2 Regression) PASS
- Real E2E PASS: "GUIALITA uses Granite for everything." → Graph-Query →
  GUIALITA → uses → granite → Restart → Graph persistiert (22 outgoing relations)

## What GRAPH VISUALIZATION accomplished

- SVG-basierte Force-Directed-Visualisierung des Memory Graph (reines Vanilla JS)
- Farbcodierung nach Entity-Type: project (grün), model (blau), tool (gelb), concept (lila), path (grau)
- GET /memory/graph: Liefert bounded nodes+edges (max 100/250, max 500/1000)
- GET /graph: Frontend-Seite mit SVG-Visualisierung
- Features: Node selection → highlight connected, Edge selection → provenance, Entity search, Pan/Zoom, Refresh, Status display
- Provenance bei Edge-Auswahl: Relation, Source, Target, Source Memory ID
- Tests: test_graph_visualization.py T01-T13 (8 API + 5 Regression) PASS
- Real E2E PASS: /memory/graph liefert 43 nodes + 250 edges, /graph page 17842 bytes
- Ollama PID 2492667 unverändert

## What TTS accomplished

- LFM2.5-Audio-1.5B TTS via llama-liquid-audio-cli (Batch: Text → WAV)
- POST /audio/tts Endpoint: Text → WAV (24kHz, mono, 32-bit float)
- GET /audio/tts/status: Verfügbare Voices, Model-Info
- 4 Voices: us_female, us_male, uk_female, uk_male
- Frontend: "Vorlesen" Button nach jeder Assistant-Antwort
- Cold Latency ~5.4s, Warm Latency ~4.2s
- Tests: test_tts.py T01-T16 (11 TTS + 5 Regression) PASS
- Real E2E PASS: TTS generiert 313KB WAV, Chat/Memory/Graph unverändert
- Ollama PID 2492667 unverändert

## What Phase 1B accomplished

- WAV-Ingestion aus `audio/inbox/` mit Validierung (Header, 16-bit mono, Dauer, Pegel)
- Runtime-Verifikation: LFM2.5-Audio-1.5B (Architektur `lfm2`) mit offiziellem
  Liquid-AI-Runner (`llama-liquid-audio-cli`, CPU-only) — llama-cpp-python 0.3.35
  hat keine Audio-APIs und ist für Audio INKOMPATIBEL
- Echte lokale Audio-Inferenz (ASR, Systemprompt "Perform ASR.")
- Echter Transcript pro WAV (z. B. "Hello, Guliya.") — keine Mocks
- Strukturierte Metadaten (`AUDIO-XXXXXX.json`: audio_id, transcript, runtime,
  Latenz, Pegel, Status; confidence immer `null`)
- Sicheres Dateinamen-Design: `YYYYMMDD_HHMMSS__<slug>.wav`
  (slug: lowercase, max 60 Zeichen, keine Metazeichen, kollisionssicher)
- Atomisches Rename/Move nach `audio/processed/` NUR nach erfolgreicher Analyse;
  bei jedem Fehler bleibt das Original unverändert
- AUDIO-IDs kollisionssicher über `audio/.audio_id_counter`
- Modell-Lebenszyklus: Lädt pro Inferenz, wird danach freigegeben
  (VRAM konstant 4708 MiB, keine GPU-Nutzung)
- Tests: `tests/test_process_audio.py` 13/13 PASS (Testmatrix T1–T10)
- Regression: API 18/18, Capture 7/7, Chat, Ollama-Isolation

## What Phase 1A accomplished

- Kontinuierliches Mikrofon-Monitoring (nach explizitem Start)
- RMS/Peak/dBFS-Level-Detection (Schwellen: speech -35 dBFS, silence -45 dBFS)
- VAD-Abstraktion (`LevelDetector`, austauschbare Schnittstelle)
- Automatische Sprachstart-Erkennung (minimum_speech_ms = 400)
- Pre-Roll-Puffer (400 ms, verhindert abgeschnittene erste Silbe)
- Silence-Erkennung / Satzende (silence_timeout_ms = 700)
- Automatische WAV-Erzeugung (PCM s16le, mono, 16 kHz) nach `audio/inbox/`
- WAV-Validierung pro Aufnahme (Header, Format, Dauer, RMS/Peak; PASS/EMPTY/SILENT/FAIL)
- Validierung wiederholter Aufnahmen (5/5 eindeutige WAVs)
- Regressionsverifikation (API-Tests 18/18, Desktop-Starter, start/stop,
  GPU, Text-Chat, Ollama-Isolation)
- Performance: CPU ~1.9 % Monitoring, RAM ~51 MB stabil

## Hardware/runtime facts

Nur belegte Fakten aus dem Phase-1A-Ergebnis:

| Komponente | Wert |
|------------|------|
| OS | Linux Mint 22.3 (XFCE) |
| CPU | Intel Core i7-3930K (6C/12T) |
| RAM | 32 GB (31 GiB) |
| GPU | NVIDIA GeForce GTX 1080 Ti, 11 GB VRAM, Driver 535.288.01 |
| CUDA | 12.2 |
| Audio-Server | PulseAudio |
| Default-Mikrofon | ZOOM H2n USB (48 kHz Quelle; Capture resampled auf 16 kHz) |
| Python venv | `/home/hz/.guialita-venv` (numpy 2.5.2, sounddevice 0.5.6) |
| STT (bestehend aus früherer Arbeit) | whisper.cpp `whisper-cli`, Modell `ggml-base.bin` |
| TTS | espeak-ng (verfügbar) |
| Backend | FastAPI auf Port 8080 (llama-cpp-python, Modell granite-3b) |
| Ollama | SHARED Service Port 11434 (wird nie gestoppt) |
| Datenträger | `/media/hz/_Ext_Seagat` exFAT (keine Symlinks, kein Git) |

## Important architecture boundary

```text
AUDIO CAPTURE (Phase 1A)
    ↓
WAV INBOX
    ↓
[PHASE 1A COMPLETE]
    ↓
WAV → LFM2.5-Audio → TRANSCRIPT → PROCESSED (Phase 1B)
    ↓
[PHASE 1B COMPLETE]
    ↓
CHAT/API → ChatService → SQLite SESSION+MESSAGE (MEMORY)
    ↓
[MEMORY SESSION COMPLETE]
    ↓
HARD STOP
    ↓
nächste Phase: Memory-Retrieval (nur nach Autorisierung)
```

RAG/Graph/Embeddings liegen bewusst außerhalb des aktuellen Zustands.

## Next-session instructions

Eine neue Session MUSS:

1. `docs/GUIALITA_STATE.yaml` lesen.
2. `docs/GUIALITA_SESSION_BOOTSTRAP.md` lesen.
3. Die Phase-Reports lesen (`docs/GUIALITA_PHASE_1A_RESULT.md`,
   `docs/PHASE_1A_AUDIO_CAPTURE.md`, `docs/PHASE_1B_WAV_LFM_AUDIO.md`,
   `docs/PHASE_MEMORY_SESSION_RESULT.md`, `docs/PHASE_MEMORY_RETRIEVAL_RESULT.md`).
4. Den Repository-Zustand vor Änderungen verifizieren.
5. Phase 1A/1B/MEMORY/MEM-RET/MEM-GRAPH als abgeschlossen und eingefroren behandeln.
6. VOR GraphRAG / Neural Embedding explizite Autorisierung einholen.
7. Autorisierung NIE aus der bloßen Existenz von WAV-Dateien ableiten.

## Do not

- GraphRAG / Neural Embedding / Vektor-DB ohne Autorisierung implementieren
- Memory-RAG/Graph/Embeddings ohne Autorisierung implementieren
- Phase 1C implementieren (Voice → LFM → TTS)
- Den Capture-Code (1A) ohne Autorisierung verändern
- Den LFM-Audio-Verarbeiter (1B) ohne Autorisierung verändern
- Die Memory-Session-Schicht (backend/memory/, chat_service) ohne Autorisierung verändern
- Die Memory-Retrieval-Schicht (backend/memory/embed.py, retrieval.py) ohne Autorisierung verändern
- Die Memory-Graph-Schicht (backend/memory/extractor.py) ohne Autorisierung verändern
- Phase-0/0.5-Implementierung verändern
- Ollama stoppen oder verändern
- Cloud-STT/TTS verwenden
- LFM2.5-Audio stillschweigend durch Whisper/Cloud ersetzen

## Konventionen

- WAVs landen in `audio/inbox/` (1A-Artefakte), SILENT-Dateien in `audio/failed/`
- Capture-Skript: `scripts/audio_capture.py` (CLI: `--list-devices`, `--debug`,
  `--threshold`, `--silence`, `--max-duration`, `--device`, `--output`,
  `--max-recordings`, `--sample-rate`)
- LFM-Audio-Verarbeitung: `scripts/process_audio.py <wav>` (CLI: `--debug`,
  `--keep-original`, `--no-rename`, `--output`, `--model`, `--runner`)
- LFM-Runtime: `runtime/liquid-audio/llama-liquid-audio-cli` (offizieller
  Liquid-AI-Runner, CPU-only; Modell: `models/lfm-audio-1.5b/`)
- Automatisierte Capture-Tests: `tests/test_capture.py` (nutzt virtuelles
  Pulse-Mikrofon `guialita_vmic` aus `~/.asoundrc`)
- LFM-Audio-Tests: `tests/test_process_audio.py` (13 Tests, echte Inferenz)
- API-Tests: `tests/test_api.py` (18 Tests gegen laufendes Backend)
- Doku-Konvention: pro Phase eine README-ähnliche `PHASE_*.md` + maschinenlesbare
  `phase-*.yaml`; dazu `INTEGRITY_MARKER.txt` aus Phase 0.5
