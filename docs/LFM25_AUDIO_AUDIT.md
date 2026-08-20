# GUIALITA — LFM2.5-Audio Capability Audit

**Mode**: Forensic / Read-Only
**Date**: 2026-08-19
**Baseline**: GUIALITA-GRAPH-VISUALIZATION-V1-PASS (unverändert)
**Status**: ANALYSIS ONLY — keine Implementierung

---

## 1. LFM2.5-Audio Capability Summary

### Modell-Spezifikation

| Property | Value | Source |
|----------|-------|--------|
| Parameters | 1.5B (1.2B LM + 115M audio encoder) | FACT — HuggingFace Model Card |
| Audio Encoder | FastConformer (canary-180m-flash) | FACT — HuggingFace |
| Audio Detokenizer | LFM-based, 8 codebooks, Mimi-compatible | FACT — HuggingFace |
| Context Length | 32K tokens | FACT — LiquidAI Docs |
| Audio Input | 16kHz (mel spectrogram, 128 bins) | FACT — ONNX Repo |
| Audio Output | 24kHz (8 codebooks × 2049 tokens) | FACT — ONNX Repo |
| Supported Language | English | FACT — LiquidAI Specs |
| License | LFM Open License v1.0 | FACT — HuggingFace |

### Fähigkeiten (mit Evidenz-Label)

| # | Capability | Status | Source | Local Support | GUIALITA |
|---|-----------|--------|--------|---------------|----------|
| 1 | Speech-to-Text (ASR) | **FACT** | LiquidAI Docs, HuggingFace, WER 7.53 avg | llama-liquid-audio-cli | process_audio.py (batch) |
| 2 | Text-to-Speech (TTS) | **FACT** | LiquidAI Docs, 4 voices (US/UK male/female) | llama-liquid-audio-cli | NICHT implementiert |
| 3 | Audio Understanding | **FACT** | HuggingFace: multi-intent, function calling | llama-liquid-audio-cli | NICHT implementiert |
| 4 | Audio Generation (TTS) | **FACT** | LiquidAI Docs, --output flag | llama-liquid-audio-cli | NICHT implementiert |
| 5 | Audio-to-Text | **FACT** | synonym mit ASR | vorhanden | teilweise (batch) |
| 6 | Text-to-Audio | **FACT** | synonym mit TTS | vorhanden | NICHT implementiert |
| 7 | Audio-to-Audio | **HYPOTHESIS** | Interleaved Mode: audio in → audio+text out | teilweise | NICHT implementiert |
| 8 | Streaming Input | **UNKNOWN** | Kein Streaming in llama.cpp Runner (WIP PR #18641) | NEIN | NEIN |
| 9 | Streaming Output | **UNKNOWN** | PR #18641 "Do Not Merge", Server-Mode experimentell | NEIN | NEIN |
| 10 | Realtime Interaction | **HYPOTHESIS** | Blog: "real-time conversation in mind" | NEIN (batch only) | NEIN |
| 11 | Voice Activity Detection | **UNKNOWN** | Kein VAD im Modell dokumentiert | NEIN | eigenes VAD (audio_capture.py) |
| 12 | Turn Detection | **UNKNOWN** | Kein Turn-Detection dokumentiert | NEIN | NEIN |
| 13 | Interruption / Barge-in | **UNKNOWN** | Keine Evidenz | NEIN | NEIN |
| 14 | Conversation Continuity | **HYPOTHESIS** | Interleaved Mode + ChatState API | potential (liquid-audio pkg) | NEIN |

---

## 2. Local Runtime Analysis

### Vorhandene Dateien

```
models/lfm-audio-1.5b/
  LFM2.5-Audio-1.5B-Q4_0.gguf          695 MB  (Hauptmodell)
  mmproj-LFM2.5-Audio-1.5B-Q4_0.gguf   219 MB  (Multimodal Projection)
  vocoder-LFM2.5-Audio-1.5B-Q4_0.gguf  108 MB  (Vocoder/Detokenizer)
  tokenizer-LFM2.5-Audio-1.5B-Q4_0.gguf 50 MB  (Audio Tokenizer)
  ──────────────────────────────────────────────
  Gesamt:                               ~1.07 GB

runtime/liquid-audio/
  llama-liquid-audio-cli       1.3 MB    (CLI Runner)
  llama-liquid-audio-server    1.4 MB    (Server Runner)
  libllama.so                  3.1 MB    (llama.cpp library)
  libmtmd.so                   937 KB    (Multimodal library)
  libliquid-audio.so           2.5 MB    (Audio library)
  libggml*.so                  ~15 MB    (GGML backends)
  ──────────────────────────────────────────────
  Gesamt:                      ~25 MB
```

### Runtime-Status

| Komponente | Status | Evidenz |
|-----------|--------|---------|
| llama-liquid-audio-cli | **vorhanden** | OBSERVED — Datei existiert, 1.3MB |
| llama-liquid-audio-server | **vorhanden** | OBSERVED — Datei existiert, 1.4MB |
| llama-cpp-python Audio API | **NICHT VORHANDEN** | VERIFIED — stt_whisper.py Dokumentation |
| liquid-audio Python Package | **NICHT INSTALLIERT** | OBSERVED — kein Eintrag in requirements |
| PR #18641 (llama.cpp upstream) | **DRAFT / DO NOT MERGE** | VERIFIED — GitHub PR Status |
| Server-Mode | **experimentell** | OBSERVED — PR #18641, Building-Errors dokumentiert |

### Unterstützte APIs (llama-liquid-audio-cli)

```bash
# ASR
./llama-liquid-audio-cli -m ... -sys "Perform ASR." --audio $INPUT_WAV

# TTS
./llama-liquid-audio-cli -m ... -sys "Perform TTS." -p "Text" --output $OUTPUT_WAV

# Interleaved (audio→text+audio)
./llama-liquid-audio-cli -m ... -sys "Respond with interleaved text and audio." \
  --audio $INPUT_WAV --output $OUTPUT_WAV
```

**WICHTIG**: Alle Modi sind **Batch-Modus** (Datei → Datei). Kein Streaming.

---

## 3. Existing GUIALITA Audio State

### Was funktioniert

| Komponente | Status | Details |
|-----------|--------|---------|
| Mikrofon-Capture | **PASS** | audio_capture.py, sounddevice, VAD, WAV |
| WAV-Validierung | **PASS** | process_audio.py, Header-Check, Pegel, Dauer |
| Whisper STT | **PASS** | stt_whisper.py, whisper.cpp, /audio/transcribe |
| Audio Chat | **PASS** | /audio/chat → STT → ChatService → Response |
| LFM2.5-Audio ASR | **PASS** | process_audio.py, Batch-WAV → Transcript |
| Session Integration | **PASS** | ChatService, Memory, Graph |

### Was ist nur vorbereitet

| Komponente | Status | Details |
|-----------|--------|---------|
| LFM2.5-Audio TTS | **VORBEREITET** | Modell vorhanden, Runtime vorhanden, aber kein Endpoint |
| LFM2.5-Audio Interleaved | **VORBEREITET** | Modell vorhanden, aber kein Endpoint |
| llama-liquid-audio-server | **VORBEREITET** | Binary vorhanden, aber nicht gestartet |

### Was wurde bisher getestet

| Test | Status | Ergebnis |
|------|--------|----------|
| LFM2.5-Audio ASR (Batch) | **VERIFIED** | "GUIALITA uses Granite for everything." → korrekter Transcript |
| Whisper STT (API) | **VERIFIED** | /audio/transcribe funktioniert |
| Mikrofon Capture | **VERIFIED** | WAV-Inkrement, VAD-Trigger |

---

## 4. STT Capability

### Offizielle Leistung (ASR)

| Benchmark | WER | Quelle |
|-----------|-----|--------|
| LibriSpeech-clean | 1.95 | FACT — HuggingFace |
| LibriSpeech-other | 4.30 | FACT — HuggingFace |
| GigaSpeech | 10.47 | FACT — HuggingFace |
| TED-LIUM | 3.47 | FACT — HuggingFace |
| **Durchschnitt** | **7.53** | FACT — HuggingFace |

### Vergleich

| Modell | WER avg | Audio Output | Open |
|--------|---------|-------------|------|
| LFM2.5-Audio-1.5B | 7.53 | Yes | Yes |
| Whisper-large-V3 | 7.44 | No (ASR only) | Yes |
| Qwen2.5-Omni-3B | 7.90 | Yes | Yes |

**Bewertung**: LFM2.5-Audio ASR ist vergleichbar mit Whisper-large-V3 (7.53 vs 7.44 WER).

### Lokaler Support

- **Vorhanden**: Ja (llama-liquid-audio-cli)
- **Getestet**: Ja (process_audio.py, Batch-Modus)
- **Echtzeit**: NEIN (nur Batch-Datei-Input)
- **Streaming**: NEIN

---

## 5. TTS Capability

### Offizielle Leistung

| Feature | Details | Quelle |
|---------|---------|--------|
| Output Rate | 24kHz | FACT — LiquidAI |
| Voices | US male, US female, UK male, UK female | FACT — LiquidAI Docs |
| Detokenizer | 8x schneller als LFM2 Mimi (LFM-based) | FACT — LiquidAI Blog |
| INT4 Qualität | STOI 0.89, UTMOS 3.53 | FACT — LiquidAI Blog |

### TTS Quality (DNSMOS)

| Model | STOI | UTMOS | DNSMOS p.838 | DNSMOS p.808 |
|-------|------|-------|-------------|-------------|
| LFM2.5 INT4 | 0.89 | 3.53 | 3.09 | 3.66 |
| LFM2 Mimi FP32 | 0.89 | 3.65 | 3.12 | 3.68 |

**Bewertung**: Gute Qualität, vergleichbar mit LFM2 Mimi bei deutlich geringerer Latenz.

### Lokaler Support

- **Vorhanden**: Ja (llama-liquid-audio-cli mit --output)
- **Getestet**: NEIN (in GUIALITA noch nicht)
- **Echtzeit**: NEIN (Batch: Text → Datei)
- **Streaming**: NEIN

---

## 6. Streaming Capability

### Offizielle Dokumentation

| Feature | Status | Quelle |
|---------|--------|--------|
| generate_interleaved() | Generator (yield tokens) | FACT — liquid-audio Python API |
| llama-liquid-audio-server | Server-Mode (HTTP) | OBSERVED — Binary vorhanden |
| llama.cpp PR #18641 | **DRAFT / DO NOT MERGE** | VERIFIED — GitHub |
| mtmd_audio_streaming_istft | Merged in PR #18645 | VERIFIED — GitHub |

### Kritische Einschränkung

```
PR #18641 Titel: "[Do Not Merge] model : LFM2.5-Audio-1.5B"
Status: Draft
Commits: 53
Hinweis: "This PR is intended to provide a functional implementation
         until necessary infrastructure is implemented."
```

**FACT**: Der llama.cpp Audio-Runner ist WIP und nicht produktionsbereit.

### Streaming in GUIALITA

| Komponente | Streaming | Status |
|-----------|-----------|--------|
| audio_capture.py | Ja (sounddevice callback) | PASS |
| whisper.cpp | NEIN (Batch) | PASS (akzeptabel) |
| llama-liquid-audio-cli | NEIN (Batch) | Limitiert |
| llama-liquid-audio-server | Unklar (experimentell) | WIP |
| liquid-audio Python | Ja (Generator) | Nicht installiert |

---

## 7. Realtime Capability

### Definitionen

| Kategorie | Definition | LFM2.5-Audio Status |
|-----------|-----------|---------------------|
| A: Push-to-Talk | User drückt Knopf, spricht, Modell antwortet | **MÖGLICH** (Batch: WAV → TTS) |
| B: Voice Activated | VAD trigger, Aufnahme, Modell antwortet | **MÖGLICH** (mit externem VAD) |
| C: Streaming STT | Audio wird live transkribiert | **NEIN** (Batch only) |
| D: Streaming TTS | Text wird live zu Audio | **NEIN** (Batch only) |
| E: Streaming Audio Conversation | Audio-in → Audio-out live | **HYPOTHESIS** (Blog: "real-time") |
| F: Full Duplex | Beide Seiten gleichzeitig | **NEIN** |
| G: Barge-in | Unterbrechung während Antwort | **NEIN** |
| H: Continuous Loop | Autonome Konversation | **HYPOTHESIS** (Interleaved Mode) |

### Realistische Bewertung

LFM2.5-Audio kann auf dem aktuellen Runner (llama-liquid-audio-cli) **nur Batch-Verarbeitung**:
1. WAV-Datei aufnehmen (externes VAD nötig)
2. CLI aufrufen: `llama-liquid-audio-cli --audio input.wav`
3. Warten auf Ergebnis (Transcript oder Audio)
4. Text an ChatService senden
5. Antwort generieren
6. TTS generieren (separater CLI-Aufruf)

**Keine der obigen Realtime-Kategorien (C-H) wird durch den aktuellen Runner unterstützt.**

---

## 8. VAD / Turn Detection

### Offiziell

- **Kein VAD im Modell** dokumentiert
- **Kein Turn Detection** dokumentiert
- **Keine Interruption/Barge-in** dokumentiert

### GUIALITA (bestehend)

| Komponente | Status | Details |
|-----------|--------|---------|
| Level-basiertes VAD | **PASS** | audio_capture.py, RMS/Peak, -35 dBFS |
| Silence-Timeout | **PASS** | 700ms → Ende der Äußerung |
| Pre-Roll | **PASS** | 400ms Puffer |
| Max-Dauer | **PASS** | 30s Timeout |

**Bewertung**: GUIALITA hat bereits ein funktionierendes VAD. LFM2.5-Audio bräuchte dieses extern.

---

## 9. GTX 1080 Ti Feasibility

### Hardware

| Resource | Verfügbar | Benötigt | Status |
|----------|-----------|----------|--------|
| VRAM | 11 GB | ~1.07 GB (Q4_0) | OK |
| CUDA | Ja | Ja | OK |
| RAM | ~32 GB | ~2-4 GB | OK |
| CPU | Intel/AMD | Any | OK |

### VRAM-Berechnung

```
LFM2.5-Audio-1.5B Q4_0:
  Hauptmodell:     695 MB
  mmproj:          219 MB
  Vocoder:         108 MB
  Tokenizer:        50 MB
  KV Cache (32K): ~200 MB (geschätzt)
  ─────────────────────
  Gesamt:        ~1.27 GB

Parallel mit:
  Granite 3B:      2.1 GB
  Ollama:          ~2 GB (je nach Modell)
  ─────────────────────
  Gesamt:         ~5.4 GB von 11 GB
  Verbleibend:    ~5.6 GB
```

**FACT**: VRAM ist NICHT der Flaschenhals. LFM2.5-Audio passt komfortabel neben Granite und Ollama.

### Gleichzeitige Modelle

| Szenario | VRAM | Status |
|----------|------|--------|
| LFM2.5-Audio + Granite 3B | ~3.4 GB | OK |
| LFM2.5-Audio + Granite 3B + Ollama | ~5.4 GB | OK |
| LFM2.5-Audio + Granite 8B | ~6.4 GB | OK |
| LFM2.5-Audio + Granite 8B + Ollama | ~8.4 GB | OK (knapp) |

### Kritischer Engpass

**NICHT VRAM, sondern:**
1. **Kein Streaming** — Batch-Modus erzwungene Pausen
2. **Kein VAD** — externes System nötig
3. **Kein Barge-in** — Modell kann nicht unterbrochen werden
4. **WIP Runner** — PR #18641 ist "Do Not Merge"
5. **Nur English** — kein Deutsch

---

## 10. Architecture Comparison

### ARCHITECTURE A: Whisper → Text LLM → TTS

```
Audio In → [Whisper STT] → Text → [Granite LLM] → Text → [TTS] → Audio Out
```

| Aspect | Bewertung |
|--------|-----------|
| Latenz | ~2-5s (STT 1-2s + LLM 0.5-2s + TTS 0.5-1s) |
| VRAM | Whisper ~1GB + Granite ~2GB + TTS ~0.5GB = ~3.5GB |
| Komplexität | Hoch (3 separate Systeme) |
| Qualität | Hoch (Whisper WER 7.44, Granite stark) |
| Stabilität | Hoch (jede Komponente einzeln testbar) |
| Streaming | Möglich (Whisper live, TTS chunked) |
| Session Integration | Einfach (Text-In/Text-Out) |
| Memory Integration | Einfach (Text-basiert) |
| Vision Integration | Einfach (Text-basiert) |
| **Status in GUIALITA** | **Funktional** |

### ARCHITECTURE B: LFM2.5-Audio allein

```
Audio In → [LFM2.5-Audio] → Audio Out (Text+Audio interleaved)
```

| Aspect | Bewertung |
|--------|-----------|
| Latenz | ~1-3s (theoretisch, Batch-Modus: >5s) |
| VRAM | ~1.3GB |
| Komplexität | Niedrig (1 Modell) |
| Qualität | Gut (ASR 7.53 WER, TTS 3.53 UTMOS) |
| Stabilität | Niedrig (WIP Runner, PR "Do Not Merge") |
| Streaming | NEIN (Batch only) |
| Session Integration | SCHWIERIG (Audio → Audio, kein Text-Zwischenschritt) |
| Memory Integration | SCHWIERIG (Audio-basiert, kein Text-Embedding) |
| Vision Integration | MÖGLICH (Multimodal) |
| **Status in GUIALITA** | **NICHT IMPLEMENTIERT** |

### ARCHITECTURE C: Hybrid

```
Audio In → [LFM2.5-Audio ASR] → Text → [Granite LLM] → Text → [LFM2.5-Audio TTS] → Audio Out
         oder
Audio In → [Whisper STT] → Text → [Granite LLM] → Text → [LFM2.5-Audio TTS] → Audio Out
         oder
Audio In → [LFM2.5-Audio Interleaved] → Audio+Text → [Granite] → Text → [LFM2.5-Audio TTS] → Audio Out
```

| Aspect | Bewertung |
|--------|-----------|
| Latenz | ~2-4s |
| VRAM | ~3-4GB |
| Komplexität | Mittel (2 Systeme) |
| Qualität | Hoch (beste Kombination) |
| Stabilität | Mittel (LFM-Teil WIP) |
| Streaming | Teilweise (Whisper live + TTS chunked) |
| Session Integration | Einfach (Text-basiert) |
| Memory Integration | Einfach (Text-basiert) |
| Vision Integration | Einfach (Text-basiert) |
| **Status in GUIALITA** | **TEILWEISE** |

---

## 11. Empfohlene Architektur

### EMPFEHLUNG: HYBRID (Architecture C) mit schrittweiser Migration

**Phase 1 (sofort)**: Behalte bestehende Architecture A (Whisper + Granite)
- Funktioniert, stabil, getestet
- Session/Memory/Graph Integration existiert

**Phase 2 (nächster Schritt)**: Füge LFM2.5-Audio TTS hinzu
- ersetzt separate TTS-Komponente
- gleiche Text-Schnittstelle
- LFM2.5-Audio TTS ist Produktionsreif (Q4_0, 8x schneller als LFM2)

**Phase 3 (optional)**: Ersetze Whisper durch LFM2.5-Audio ASR
- wenn PR #18641 upstream gemerged ist
- wenn Streaming verfügbar ist
- wenn Deutsch-Support vorhanden ist

**Phase 4 (zukünftig)**: Interleaved Mode
- wenn Runner stabil ist
- wenn VAD/Turn Detection implementiert ist
- wenn Barge-in implementiert ist

### Begründung

1. **LFM2.5-Audio kann die Voice-Pipeline NICHT alleine übernehmen**
   - Nur English
   - Kein VAD/Turn Detection
   - Kein Streaming (Batch only)
   - Runner WIP (PR "Do Not Merge")

2. **LFM2.5-Audio TTS ist der wertvollste First-Use-Case**
   - 8x schneller als Vorgänger
   - 4 Stimmen
   - Gute Qualität (UTMOS 3.53)
   - Einfach zu integrieren (Text → Audio)

3. **Whisper bleibt zuverlässig für STT**
   - WER 7.44 (fast identisch mit LFM2.5 7.53)
   - Produktionserprobt
   - Keine Abhängigkeit von WIP-Runner

---

## 12. Missing Components

| Komponente | Status | Priorität |
|-----------|--------|-----------|
| LFM2.5-Audio TTS Endpoint | Nicht implementiert | Hoch |
| TTS → Audio Response Pipeline | Nicht implementiert | Hoch |
| Audio Response im Frontend | Nicht implementiert | Hoch |
| VAD für Interleaved Mode | Nicht implementiert | Niedrig |
| Turn Detection | Nicht implementiert | Niedrig |
| Barge-in | Nicht implementiert | Niedrig |
| Streaming Audio I/O | Nicht implementiert (WIP) | Niedrig |
| Deutsch-Support | Nicht vorhanden | Unklar |
| liquid-audio Python Package | Nicht installiert | Mittel |

---

## 13. Minimal Implementation Scope

### Für TTS Integration

1. **Neuer Endpoint**: `POST /audio/tts` — nimmt Text, liefert WAV
2. **Neuer Adapter**: `LFMAudioTTSAdapter` — wraps llama-liquid-audio-cli
3. **Frontend**: Audio-Player für TTS-Antworten
4. **Config**: TTS voice, system prompt
5. **Tests**: T01-T10

### Für ASR Integration (optional)

1. **Neuer Adapter**: `LFMAudioASRAdapter` — wraps llama-liquid-audio-cli
2. **Endpoint**: `POST /audio/transcribe-lfm` — Vergleich mit Whisper
3. **Tests**: Vergleichstests

### NICHT implementieren (jetzt)

- Interleaved Mode (WIP)
- Streaming (WIP)
- VAD/Turn Detection (nicht dokumentiert)
- Barge-in (nicht dokumentiert)

---

## 14. Risiken

| Risiko | Schwere | Wahrscheinlichkeit |
|--------|---------|-------------------|
| PR #18641 wird nicht upstream gemerged | Hoch | Mittel |
| Runner-Build ändert sich (WIP Status) | Mittel | Hoch |
| TTS-Qualität für Deutsch unbekannt | Mittel | Hoch |
| Kein Streaming → spürbare Pausen | Hoch | Gewiss |
| VRAM-Konflikt bei gleichzeitigen Modellen | Niedrig | Niedrig |
| liquid-audio Package Inkompatibilität | Mittel | Niedrig |

---

## 15. Offene Fragen

1. **Deutsch-Support**: Unterstützt LFM2.5-Audio Deutsch? (Offiziell: nur English)
2. **TTS Latenz**: Wie schnell ist TTS auf GTX 1080 Ti? (keine offiziellen Zahlen)
3. **Server-Mode Stabilität**: Funktioniert llama-liquid-audio-server zuverlässig?
4. **liquid-audio Package**: Ist es kompatibel mit der lokalen Python-Umgebung?
5. **Interleaved Mode**: Wann wird PR #18641 produktionsreif?

---

## 16. Empfehlung

### LFM2.5-Audio als primäre Voice Engine?

**NEIN** — nicht als alleinige Engine.

### Begründung

1. **Nur English** — GUIALITA ist ein deutsches Projekt (System-Prompts auf Deutsch)
2. **Kein Streaming** — Batch-Modus erzwungene Pausen von >5s
3. **Kein VAD/Turn Detection** — externes System weiterhin nötig
4. **Runner WIP** — PR #18641 ist "Do Not Merge", keine Production-Garantie
5. **Kein Barge-in** — Konversationseinschränkung

### Empfohlene Architektur

**HYBRID (Architecture C)**:
- **STT**: Whisper (bewährt, WER 7.44)
- **LLM**: Granite (lokal, bewährt)
- **TTS**: LFM2.5-Audio (8x schneller als Vorgänger, 4 Stimmen)
- **VAD**: Bestehendes audio_capture.py

### Nächster Schritt

LFM2.5-Audio TTS als zusätzlichen Output-Kanal implementieren.
Bestehende Whisper-STT + Granite-LLM Pipeline beibehalten.

---

## 17. Evidence Labels

| Aussage | Label |
|---------|-------|
| LFM2.5-Audio hat 1.5B Parameter | FACT |
| ASR WER 7.53 Durchschnitt | FACT |
| TTS Output 24kHz | FACT |
| 4 Stimmen (US/UK male/female) | FACT |
| Nur English unterstützt | FACT |
| PR #18641 ist "Do Not Merge" | FACT |
| Kein VAD im Modell | FACT |
| Kein Streaming im Runner | FACT |
| llama-cpp-python hat keine Audio-API | VERIFIED |
| VRAM ~1.3GB für Q4_0 | INFERENCE |
| GTX 1080 Ti kann Modell laden | INFERENCE |
| Interleaved Mode könnte Realtime ermöglichen | HYPOTHESIS |
| TTS könnte Pipeline verbessern | PROPOSAL |
| Deutsch-Support ist unklar | UNKNOWN |

---

**LFM_AUDIO_AUDIT: PASS**

Keine Implementierung. Keine Dependency-Änderung. Kein Modell-Download.
Bestehende GUIALITA-Baseline unverändert.
