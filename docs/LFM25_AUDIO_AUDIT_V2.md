# GUIALITA LFM2.5-Audio Capability Audit V2

**Mode**: Forensic / Read-Only
**Date**: 2026-08-19
**Baseline**: GUIALITA-GRAPH-VISUALIZATION-V1-PASS (unverändert)
**Status**: ANALYSIS ONLY

---

## 1. Executive Summary

LFM2.5-Audio-1.5B ist lokal vorhanden und funktioniert als **Batch-ASR** (Audio→Text). Als vollständige Voice-Pipeline kann es die bestehende Kombination aus Capture/Whisper/LLM/TTS **nicht ersetzen**, weil:

1. **Nur Batch-Verarbeitung** — kein Streaming, keine Live-Inferenz
2. **Nur English** — kein Deutsch
3. **Kein VAD/Turn Detection** — Modell erkennt Sprachende nicht
4. **Kein Barge-in** — keine Unterbrechung
5. **Runner WIP** — PR #18641 ist "Do Not Merge"

**Empfehlung**: HYBRID — LFM2.5-Audio TTS als zusätzlichen Output-Kanal, bestehende Whisper/Granite-Pipeline beibehalten.

---

## 2. Local Runtime Inventory

### 2.1 Model Files

| Component | Present | Size | Path | Format | Verified |
|-----------|---------|------|------|--------|----------|
| LFM2.5-Audio-1.5B (Hauptmodell) | YES | 695 MB | models/lfm-audio-1.5b/LFM2.5-Audio-1.5B-Q4_0.gguf | GGUF Q4_0 | OBSERVED |
| Multimodal Projector | YES | 219 MB | models/lfm-audio-1.5b/mmproj-LFM2.5-Audio-1.5B-Q4_0.gguf | GGUF Q4_0 | OBSERVED |
| Vocoder/Detokenizer | YES | 108 MB | models/lfm-audio-1.5b/vocoder-LFM2.5-Audio-1.5B-Q4_0.gguf | GGUF Q4_0 | OBSERVED |
| Audio Tokenizer | YES | 50 MB | models/lfm-audio-1.5b/tokenizer-LFM2.5-Audio-1.5B-Q4_0.gguf | GGUF Q4_0 | OBSERVED |
| **Gesamt** | | **~1.1 GB** | | | |

### 2.2 Runtime Binaries

| Component | Present | Size | Path | Format | Verified |
|-----------|---------|------|------|--------|----------|
| llama-liquid-audio-cli | YES | 1.3 MB | runtime/liquid-audio/llama-liquid-audio-cli | ELF x86-64 | OBSERVED |
| llama-liquid-audio-server | YES | 1.4 MB | runtime/liquid-audio/llama-liquid-audio-server | ELF x86-64 | OBSERVED |
| libliquid-audio.so | YES | 2.5 MB | runtime/liquid-audio/libliquid-audio.so | Shared Lib | OBSERVED |
| libllama.so | YES | 3.1 MB | runtime/liquid-audio/libllama.so | Shared Lib | OBSERVED |
| libmtmd.so | YES | 937 KB | runtime/liquid-audio/libmtmd.so | Shared Lib | OBSERVED |

### 2.3 Whisper Runtime

| Component | Present | Size | Path | Verified |
|-----------|---------|------|------|----------|
| whisper-cli | YES | 997 KB | /home/hz/whisper.cpp/build/bin/whisper-cli | VERIFIED |
| ggml-base.bin | YES | 141 MB | models/whisper/ggml-base.bin | VERIFIED |

### 2.4 Python Packages

| Package | Version | Installed | Audio Support | Verified |
|---------|---------|-----------|---------------|----------|
| llama-cpp-python | 0.3.34 | YES | **KEINE Audio-API** | VERIFIED |
| liquid-audio | — | **NEIN** | — | VERIFIED |
| torch | 2.13.0+cpu | YES | CPU-only | VERIFIED |
| torchaudio | — | **NEIN** | — | VERIFIED |
| sounddevice | — | **NEIN** | — | VERIFIED |
| numpy | 1.26.4 | YES | — | VERIFIED |

### 2.5 Critical Finding: llama-cpp-python hat KEINE Audio-API

```
LOCAL_SOURCE: /home/hz/.local/lib/python3.12/site-packages/llama_cpp/

llama-cpp-python v0.3.34:
  - Llama.__init__() akzeptiert: model_path, n_ctx, n_gpu_layers, ...
  - KEINE Parameter für: mmproj, vocoder, tokenizer_path, audio
  - KEINE Methoden für: audio input, audio output, audio encoding
  - Das Llama() Objekt kann NUR Text-Inferenz durchführen
```

**Konsequenz**: `llamacpp_adapter.py` übergibt `mmproj`, `tokenizer_path`, `vocoder_path` an `Llama()` — diese werden ignoriert oder verursachen Fehler. LFM2.5-Audio ist über llama-cpp-python **nicht nutzbar**.

---

## 3. Model Inventory

### 3.1 Was ist installiert

| Modell | Dateien | Größe | Format | Status |
|--------|---------|-------|--------|--------|
| LFM2.5-Audio-1.5B | 4 GGUF-Dateien | ~1.1 GB | Q4_0 quantized | PRESENT |
| Granite 4.1-3B | 1 GGUF-Datei | 2.1 GB | Q4_K_M | PRESENT |
| Granite 4.1-8B | 1 GGUF-Datei | 5.35 GB | Q4_K_M | PRESENT |
| Whisper base | 1 GGML-Datei | 141 MB | ggml-base | PRESENT |
| 17 Ollama-Modelle | divers | divers | divers | PRESENT |

### 3.2 Was kann geladen werden

| Modell | Via llama-cpp-python | Via CLI-Binary | Via Ollama |
|--------|---------------------|----------------|------------|
| Granite 3B | JA | — | — |
| Granite 8B | JA | — | — |
| LFM2.5-Audio | **NEIN** (keine Audio-API) | JA (ASR/TTS) | NEIN |
| Whisper | NEIN (eigener CLI) | JA (whisper-cli) | NEIN |

---

## 4. Official LFM2.5-Audio Capabilities

### 4.1 Quellen

| Quelle | Typ | Zuverlässigkeit |
|--------|-----|-----------------|
| docs.liquid.ai/lfm/models/lfm25-audio-1.5b | Official Docs | Hoch |
| huggingface.co/LiquidAI/LFM2.5-Audio-1.5B | Official Model Card | Hoch |
| huggingface.co/LiquidAI/LFM2.5-Audio-1.5B-GGUF | Official GGUF | Hoch |
| liquid.ai/blog/introducing-lfm2-5 | Official Blog | Mittel |
| github.com/ggml-org/llama.cpp/pull/18641 | Official PR (WIP) | WIP |

### 4.2 Capability Matrix

| # | Capability | Official | Local Runtime | GUIALITA | Verified |
|---|-----------|----------|---------------|----------|----------|
| A | ASR (Speech-to-Text) | FACT | llama-liquid-audio-cli | process_audio.py (Batch) | VERIFIED |
| B | TTS (Text-to-Speech) | FACT | llama-liquid-audio-cli | NICHT implementiert | OBSERVED |
| C | Audio Understanding | FACT | — | NICHT implementiert | UNKNOWN locally |
| D | Audio Generation | FACT | — | NICHT implementiert | OBSERVED (via TTS) |
| E | Audio-to-Audio | FACT (Interleaved) | — | NICHT implementiert | UNKNOWN locally |
| F | Speech-to-Speech | FACT (Interleaved) | — | NICHT implementiert | UNKNOWN locally |
| G | Interleaved Generation | FACT | — | NICHT implementiert | UNKNOWN locally |
| H | Sequential Generation | FACT | llama-liquid-audio-cli | NICHT implementiert | OBSERVED |
| I | Streaming Input | **UNKNOWN** | NEIN (Batch only) | NEIN | NOT VERIFIED |
| J | Streaming Output | **UNKNOWN** | NEIN (Batch only) | NEIN | NOT VERIFIED |
| K | Real-Time Conversation | HYPOTHESIS | NEIN (Batch only) | NEIN | NOT VERIFIED |
| L | Continuous Audio Input | UNKNOWN | NEIN | NEIN | NOT VERIFIED |
| M | Voice Activity Detection | UNKNOWN | NEIN | externes VAD | NOT VERIFIED |
| N | Turn Detection | UNKNOWN | NEIN | NEIN | NOT VERIFIED |
| O | Interruption | UNKNOWN | NEIN | NEIN | NOT VERIFIED |
| P | Barge-In | UNKNOWN | NEIN | NEIN | NOT VERIFIED |
| Q | Full Duplex | UNKNOWN | NEIN | NEIN | NOT VERIFIED |
| R | Multi-Turn Voice | HYPOTHESIS | NEIN (Batch only) | NEIN | NOT VERIFIED |

---

## 5. Local Runtime Capabilities

### 5.1 Was der lokale Runner kann

```
LOCAL_SOURCE: runtime/liquid-audio/llama-liquid-audio-cli --help

Unterstützte Modi:
  - ASR:   --audio $INPUT_WAV -sys "Perform ASR."
  - TTS:   -p "Text" --output $OUTPUT_WAV -sys "Perform TTS."
  - Interleaved: --audio $INPUT_WAV --output $OUTPUT_WAV -sys "Respond with interleaved text and audio."

Input: WAV-Datei (16kHz, 16-bit PCM)
Output: WAV-Datei (24kHz) oder Text (stdout)
Modus: Batch (Datei → Datei/Text)
```

### 5.2 Was der lokale Runner NICHT kann

- **Kein Streaming** — Input muss vollständige WAV-Datei sein
- **Kein Live-Mikrofon** — Kein Audio-Device-Input
- **Kein VAD** — Modell erkennt Sprachanfang/-ende nicht
- **Kein Turn Detection** — Keine Konversationssteuerung
- **Kein Barge-in** — Keine Unterbrechung
- **Kein Concurrent I/O** — Seriell: Input → Processing → Output

### 5.3 Tatsächlich nachweisbar

| Feature | Nachweis | Status |
|---------|----------|--------|
| ASR mit WAV-Input | AUDIO-000001: "Namadomayus." (7.1s) | **VERIFIED** |
| TTS mit Text-Input | Offizielles CLI-Beispiel | OBSERVED (nicht getestet) |
| Interleaved | Offizielles CLI-Beispiel | OBSERVED (nicht getestet) |
| Streaming | Kein Nachweis | **NOT VERIFIED** |
| Live-Mikrofon | Kein Nachweis | **NOT VERIFIED** |
| VAD | Kein Nachweis | **NOT VERIFIED** |
| Turn Detection | Kein Nachweis | **NOT VERIFIED** |

---

## 6. GUIALITA Existing Audio Pipeline

### 6.1 Aktueller Flow

```
Phase 1A:
  Mikrofon → [sounddevice] → VAD → WAV → audio/inbox/
  STATUS: sounddevice NICHT installiert

Phase 1B:
  WAV → [llama-liquid-audio-cli] → Transcript → audio/processed/
  STATUS: FUNKTIONIERT (VERIFIED: AUDIO-000001)

API:
  WAV → [whisper-cli] → Text → [ChatService] → Text Response
  STATUS: FUNKTIONIERT (VERIFIED: /audio/transcribe)
```

### 6.2 Was funktioniert

| Komponente | Status | Evidenz |
|-----------|--------|---------|
| Mikrofon-Capture | **TEILWEISE** | audio_capture.py vorhanden, sounddevice NICHT installiert |
| Whisper STT | **PASS** | /audio/transcribe funktioniert, whisper-cli vorhanden |
| LFM2.5-Audio ASR | **PASS** | process_audio.py funktioniert, AUDIO-000001 verified |
| ChatService | **PASS** | Text-In/Text-Out funktioniert |
| Session Integration | **PASS** | Memory/Graph/Provenance funktioniert |

### 6.3 Was ist frozen

| Komponente | Status |
|-----------|--------|
| audio_capture.py | FROZEN (Phase 1A) |
| test_capture.py | FROZEN |
| process_audio.py | FROZEN (Phase 1B) |
| test_process_audio.py | FROZEN |

### 6.4 Was wurde real getestet

| Test | Ergebnis |
|------|----------|
| LFM2.5-Audio ASR (Batch) | "Namadomayus." — korrekter Transcript |
| Whisper STT (API) | /audio/transcribe funktioniert |
| Mikrofon Capture | WAV-Inkrement, VAD-Trigger |

---

## 7. Capability Matrix (Vollständig)

### 7.1 Modell vs Runtime vs GUIALITA

| Capability | Modell (Official) | Runtime (Lokal) | GUIALITA (Implementiert) |
|-----------|-------------------|-----------------|-------------------------|
| ASR | FACT | JA (Batch) | JA (Batch) |
| TTS | FACT | JA (Batch) | NEIN |
| Audio Understanding | FACT | unbekannt | NEIN |
| Interleaved | FACT | JA (Batch) | NEIN |
| Streaming Input | UNKNOWN | NEIN | NEIN |
| Streaming Output | UNKNOWN | NEIN | NEIN |
| Realtime | HYPOTHESIS | NEIN | NEIN |
| VAD | UNKNOWN | NEIN | extern (audio_capture.py) |
| Turn Detection | UNKNOWN | NEIN | NEIN |
| Barge-in | UNKNOWN | NEIN | NEIN |
| Full Duplex | UNKNOWN | NEIN | NEIN |
| Multi-Turn | HYPOTHESIS | NEIN | NEIN |
| Deutsch STT | UNKNOWN | NEIN (nur EN) | Whisper (DE) |
| Deutsch TTS | UNKNOWN | NEIN (nur EN) | NEIN |

---

## 8. Realtime Analysis

### 8.1 Definitionen und Bewertung

| Kategorie | Definition | Official | Lokal | Praktisch GTX1080Ti |
|-----------|-----------|----------|-------|---------------------|
| R1: Voice Activated Recording | VAD → Aufnahme → Inferenz | UNKNOWN | NEIN (kein VAD) | NEIN |
| R2: Streaming STT | Live-Audio → Live-Transcript | UNKNOWN | NEIN (Batch) | NEIN |
| R3: Streaming TTS | Text → Live-Audio-Stream | UNKNOWN | NEIN (Batch) | NEIN |
| R4: Streaming Speech-to-Speech | Audio-In → Audio-Out live | HYPOTHESIS | NEIN | NEIN |
| R5: Interleaved Audio Gen | Text+Audio → Text+Audio | FACT | NEIN (Batch) | THEORETISCH |
| R6: Continuous Conversation | Autonome Schleife | HYPOTHESIS | NEIN | NEIN |
| R7: VAD | Sprachanfang/-ende erkennen | UNKNOWN | NEIN | NEIN |
| R8: Turn Detection | Wann ist Benutzer fertig | UNKNOWN | NEIN | NEIN |
| R9: Barge-in | Antwort unterbrechen | UNKNOWN | NEIN | NEIN |
| R10: Full Duplex | Gleichzeitig sprechen | UNKNOWN | NEIN | NEIN |
| R11: Sub-second Response | <1s Antwort | HYPOTHESIS | NEIN | THEORETISCH |
| R12: Continuous Mic Input | Permanent Mikrofon | UNKNOWN | NEIN | NEIN |

### 8.2 Fazit

**Keine einzige Realtime-Kategorie wird durch den lokalen Runner unterstützt.**

---

## 9. Streaming Analysis

### 9.1 Offizielle Streaming-Unterstützung

```
SOURCE: liquid-audio Python Package (nicht installiert)
  generate_interleaved() → Generator (yield tokens)
  generate_sequential() → Generator (yield tokens)

SOURCE: llama.cpp PR #18641
  Status: DRAFT / "Do Not Merge"
  Titel: "[Do Not Merge] model : LFM2.5-Audio-1.5B"
  Hinweis: "intended to provide a functional implementation
            until necessary infrastructure is implemented"
```

### 9.2 Lokale Streaming-Unterstützung

| Komponente | Streaming | Nachweis |
|-----------|-----------|----------|
| llama-liquid-audio-cli | NEIN | Batch: WAV → Text/Audio |
| llama-liquid-audio-server | UNKLAR | Experimentell, nicht getestet |
| llama-cpp-python | NEIN | Keine Audio-API |
| sounddevice (Capture) | JA (Callback) | Aber nicht installiert |
| whisper-cli | NEIN | Batch: WAV → Text |

### 9.3 Fazit

**Auf der lokalen Installation ist kein einziger Audio-Streaming-Pfad nachweisbar.**

---

## 10. VAD / Turn Detection

### 10.1 Modell-VAD

| Feature | Status | Quelle |
|---------|--------|--------|
| VAD im Modell | **UNKNOWN** | Keine Dokumentation |
| Turn Detection im Modell | **UNKNOWN** | Keine Dokumentation |

### 10.2 Lokales VAD

```
LOCAL_SOURCE: scripts/audio_capture.py

LevelDetector:
  - RMS/Peak Measurement auf float32 Samples
  - Speech Threshold: -35.0 dBFS
  - Silence Threshold: -45.0 dBFS
  - Min Speech Duration: 400ms
  - Silence Timeout: 700ms
  - Pre-Roll: 400ms
  - Max Recording: 30s
```

**Aber**: `sounddevice` ist nicht installiert → VAD funktioniert nicht.

### 10.3 Fazit

- LFM2.5-Audio hat **kein dokumentiertes VAD**
- GUIALITA hat VAD in `audio_capture.py`, aber `sounddevice` fehlt
- **Kein funktionsfähiges VAD vorhanden**

---

## 11. Barge-In

### 11.1 Modell-Barge-In

| Feature | Status | Quelle |
|---------|--------|--------|
| Barge-in im Modell | **UNKNOWN** | Keine Dokumentation |
| Interruption Handling | **UNKNOWN** | Keine Dokumentation |

### 11.2 Praktische Einschätzung

- Kein offizielles Feature
- Kein lokaler Nachweis
- Batch-Modus macht Barge-in physikalisch unmöglich (Modell verarbeitet komplette Datei)

### 11.3 Fazit

**Barge-in ist mit der aktuellen Runtime nicht möglich.**

---

## 12. Language Support

### 12.1 Offiziell

```
SOURCE: docs.liquid.ai/lfm/models/lfm25-audio-1.5b
  Supported Language: English
```

### 12.2 Deutsch

| Feature | Status | Quelle |
|---------|--------|--------|
| Deutsch ASR | **UNKNOWN** | Nicht offiziell |
| Deutsch TTS | **UNKNOWN** | Nicht offiziell |
| Deutsch Speech-to-Speech | **UNKNOWN** | Nicht offiziell |

### 12.3 Vergleich

| System | Deutsch ASR | Deutsch TTS |
|--------|------------|-------------|
| Whisper | VERIFIED (language: de) | — |
| LFM2.5-Audio | UNKNOWN (nur EN offiziell) | UNKNOWN (nur EN offiziell) |
| Granite | — | — (Text only) |

### 12.4 Fazit

**LFM2.5-Audio unterstützt offiziell nur English. Deutsch-Support ist ungewiss.**

---

## 13. GTX 1080 Ti Feasibility

### 13.1 Hardware

| Resource | Verfügbar | Benötigt (LFM2.5-Audio) | Status |
|----------|-----------|--------------------------|--------|
| VRAM | 11 GB | ~1.3 GB (Q4_0 + KV Cache) | OK |
| CUDA | Ja | Ja | OK |
| RAM | ~32 GB | ~2-4 GB | OK |
| CPU | Intel/AMD | Beliebig | OK |

### 13.2 VRAM-Berechnung

```
LFM2.5-Audio-1.5B Q4_0:
  Hauptmodell:      695 MB
  mmproj:           219 MB
  Vocoder:          108 MB
  Tokenizer:         50 MB
  KV Cache (32K):  ~200 MB (INFERENCE)
  ────────────────────────
  Gesamt:         ~1.3 GB

Parallel laufend:
  Granite 3B:      2.1 GB
  Ollama:          ~2 GB (je nach Modell)
  System:          ~1 GB
  ────────────────────────
  Gesamt:         ~6.4 GB von 11 GB
  Verbleibend:    ~4.6 GB
```

### 13.3 Engpass

VRAM ist **NICHT** der Flaschenhals. Der Engpass ist:

1. **Kein Streaming** — Batch-Modus erzwungene Pausen
2. **Kein VAD** — externes System nötig
3. **Runner WIP** — PR "Do Not Merge"
4. **Nur English** — kein Deutsch

### 13.4 Verifizierbarkeit

| Aussage | Status |
|---------|--------|
| Modell passt in VRAM | INFERENCE (nicht getestet mit llama-liquid-audio-cli + GPU) |
| GTX 1080 Ti kann Modell laden | INFERENCE |
| GPU-Beschleunigung funktioniert | UNKNOWN (kein CUDA-Runner vorhanden, nur CPU-Bibliotheken) |

**WICHTIG**: Der lokale Runner (`llama-liquid-audio-cli`) ist nur als CPU-Binary vorhanden. Es gibt **keinen CUDA-fähigen Audio-Runner**. Die `.so`-Bibliotheken enthalten nur CPU-Backends (alderlake, cannonlake, ..., x64, zen4). Es gibt **keine libggml-cuda.so** im liquid-audio Runtime.

---

## 14. Resident Model Strategy

### 14.1 Optionen

| Option | VRAM | Startup | Cold Latency | Warm Latency | Stabilität |
|--------|------|---------|-------------|-------------|------------|
| A: Granite resident + Audio on-demand | ~2.1 GB | Schnell | ~5s (Audio laden) | ~1s | Hoch |
| B: Audio resident + Granite on-demand | ~1.3 GB | Schnell | ~2s (Granite laden) | ~1s | Mittel (WIP) |
| C: Beide resident | ~3.4 GB | Schnell | ~0s | ~0s | Mittel |
| D: Audio als primärer Engine | ~1.3 GB | Schnell | ~0s | ~0s | Niedrig (WIP) |

### 14.2 Empfehlung

**Option A**: Granite resident (Text-LLM, bewährt) + LFM2.5-Audio on-demand (für ASR/TTS).

Begründung:
- Granite ist der Conversation-Engine (bewährt, stabil)
- LFM2.5-Audio ist Batch-Modus → on-demand laden ist akzeptabel
- Kein Konflikt mit Session/Memory/Graph

---

## 15. Architecture Comparison

### A — CURRENT HYBRID

```
Microphone → [Capture] → WAV → [Whisper STT] → Text → [ChatService] → [Granite LLM] → Text → [TTS] → Speaker
```

| Aspect | Bewertung |
|--------|-----------|
| Latenz | ~3-6s (Capture 0s + STT 1-2s + LLM 0.5-2s + TTS 0.5-1s) |
| VRAM | Whisper ~0.1GB + Granite ~2.1GB + TTS ~0.5GB = ~2.7GB |
| Komplexität | Hoch (4 Systeme) |
| Qualität | Hoch (Whisper WER 7.44, Granite stark) |
| Stabilität | Hoch (jede Komponente einzeln testbar) |
| Streaming | Möglich (Whisper live, TTS chunked) |
| Session Integration | Einfach (Text-In/Text-Out) |
| Memory Integration | Einfach (Text-basiert) |
| Vision Integration | Einfach (Text-basiert) |
| Deutsch | JA (Whisper: language=de) |
| **Status** | **FUNKTIONAL** |

### B — LFM AUDIO (direkt)

```
Microphone → [LFM2.5-Audio] → Audio Response
```

| Aspect | Bewertung |
|--------|-----------|
| Latenz | >5s (Batch-Modus: WAV-Datei schreiben + Inferenz) |
| VRAM | ~1.3 GB |
| Komplexität | Niedrig (1 Modell) |
| Qualität | Gut (ASR 7.53 WER, TTS 3.53 UTMOS) |
| Stabilität | Niedrig (WIP Runner, PR "Do Not Merge") |
| Streaming | NEIN (Batch only) |
| Session Integration | SCHWIERIG (Audio → Audio, kein Text-Zwischenschritt) |
| Memory Integration | SCHWIERIG (Audio-basiert, kein Text-Embedding) |
| Vision Integration | MÖGLICH (Multimodal) |
| Deutsch | UNKNOWN (nur EN offiziell) |
| **Status** | **NICHT FUNKTIONAL** |

### C — LFM AUDIO + GUIALITA

```
Microphone → [LFM2.5-Audio] → Text/semantic → [ChatService] → [Session] → [Memory] → [Graph] → [LFM2.5-Audio TTS] → Speaker
```

| Aspect | Bewertung |
|--------|-----------|
| Latenz | ~3-5s |
| VRAM | ~3.4 GB |
| Komplexität | Mittel |
| Qualität | Gut |
| Stabilität | Mittel (Audio-Teil WIP) |
| Streaming | NEIN (Batch) |
| Session Integration | Einfach (Text-basiert) |
| Memory Integration | Einfach (Text-basiert) |
| Vision Integration | Einfach (Text-basiert) |
| Deutsch | UNKNOWN |
| **Status** | **TEILWEISE MÖGLICH** |

### D — HYBRID FALLBACK

```
Microphone → [LFM2.5-Audio ASR] → Text → [ChatService] → [Granite] → Text → [LFM2.5-Audio TTS] → Speaker
         oder (Fallback):
Microphone → [Whisper] → Text → [ChatService] → [Granite] → Text → [TTS] → Speaker
```

| Aspect | Bewertung |
|--------|-----------|
| Latenz | ~3-6s |
| VRAM | ~3-4 GB |
| Komplexität | Mittel |
| Qualität | Hoch (beste Kombination) |
| Stabilität | Mittel (LFM-Teil WIP) |
| Streaming | Teilweise (Whisper live) |
| Session Integration | Einfach (Text-basiert) |
| Memory Integration | Einfach (Text-basiert) |
| Vision Integration | Einfach (Text-basiert) |
| Deutsch | JA (Whisper-Fallback) |
| **Status** | **EMPHOLEN** |

---

## 16. ChatService Integration Point

### 16.1 Ideale Architektur

```
Voice Input
   ↓
Voice Adapter (STT)
   ↓
ChatService ← ALLES BLEIBT GLEICH
   ↓
Voice Output Adapter (TTS)
   ↓
Voice Output
```

### 16.2 Integration Punkte

| Punkt | Datei | Methode |
|-------|-------|---------|
| Voice Input | backend/main.py | POST /audio/transcribe oder /audio/chat |
| ChatService | backend/chat_service.py | chat() Methode |
| Voice Output | NEU | POST /audio/tts (zu implementieren) |

### 16.3 Was NICHT verändert werden muss

- Session Store
- Memory Store
- Retrieval
- Graph
- Graph Visualization
- Context Builder
- Provenance
- Chat persistence

---

## 17. Minimal Future Implementation

### 17.1 Phasen (nur wenn autorisiert)

```
PHASE VOICE-0: Capability Verification
  - TTS via llama-liquid-audio-cli testen
  - Latenz messen
  - Qualität bewerten

PHASE VOICE-1: TTS Output
  - POST /audio/tts Endpoint
  - LFMAudioTTSAdapter
  - Frontend Audio-Player

PHASE VOICE-2: LFM Audio ASR (optional)
  - POST /audio/transcribe-lfm Endpoint
  - Vergleich mit Whisper

PHASE VOICE-3: Microphone Streaming (wenn sounddevice installiert)
  - Live-Audio → Whisper/LFM → Text

PHASE VOICE-4: VAD Integration (wenn Modell-VAD vorhanden)
  - Falls LFM2.5-Audio VAD unterstützt

PHASE VOICE-5: Interleaved Mode (wenn Runner stabil)
  - Audio-in → Audio-out direkt
```

### 17.2 Kritischer Pfad

Ohne diese Phasen ist die Voice-Pipeline nicht vollständig:
- PHASE VOICE-1 (TTS) ist der wertvollste erste Schritt

---

## 18. Risiken

| Risiko | Schwere | Wahrscheinlichkeit | Evidenz |
|--------|---------|-------------------|---------|
| PR #18641 wird nicht upstream gemerged | Hoch | Mittel | GITHUB_PR |
| Runner-Build ändert sich (WIP Status) | Mittel | Hoch | GITHUB_PR |
| TTS-Qualität für Deutsch unbekannt | Mittel | Hoch | OFFICIAL (nur EN) |
| Kein Streaming → spürbare Pausen | Hoch | Gewiss | LOCAL_OBSERVATION |
| sounddevice fehlt → kein Live-Mikrofon | Mittel | Gewiss | PIP_SHOW |
| llama-cpp-python hat keine Audio-API | Hoch | Gewiss | VERIFIED |
| GPU-Audio-Runner fehlt (nur CPU .so) | Hoch | Gewiss | LOCAL_OBSERVATION |
| LFM2.5-Audio kann Granite nicht ersetzen | Hoch | Gewiss | ARCHITECTURE |

---

## 19. Unknowns

| Frage | Status | Priorität |
|-------|--------|-----------|
| Unterstützt LFM2.5-Audio Deutsch? | UNKNOWN | Hoch |
| Funktioniert TTS via llama-liquid-audio-cli? | UNKNOWN (nicht getestet) | Hoch |
| Wie schnell ist TTS auf CPU? | UNKNOWN | Mittel |
| Funktioniert llama-liquid-audio-server? | UNKNOWN (nicht getestet) | Mittel |
| Hat das Modell internes VAD? | UNKNOWN | Niedrig |
| Kann Modell Turn Detection? | UNKNOWN | Niedrig |
| Unterstützt Modell Barge-in? | UNKNOWN | Niedrig |
| Funktioniert Interleaved via CLI? | UNKNOWN (nicht getestet) | Niedrig |
| Ist liquid-audio Python Package nötig? | UNKNOWN | Niedrig |

---

## 20. Recommended Architecture

### EMPFEHLUNG: HYBRID (Architecture D) mit schrittweiser Migration

**Sofort (ohne Änderungen)**:
- Behalte bestehende Whisper/Granite-Pipeline
- Session/Memory/Graph funktioniert

**Nächster autorisierter Schritt**:
- Füge LFM2.5-Audio TTS als Output-Kanal hinzu
- Text-In/Text-Out (wie Whisper, aber für Output)
- Gleiche Session-Integration

**Optionale Erweiterung**:
- Ersetze Whisper durch LFM2.5-Audio ASR (wenn Deutsch-Support bestätigt)

**Zukünftig (wenn Runner stabil)**:
- Interleaved Mode für direkte Audio-in/Audio-out

### Begründung

1. **LFM2.5-Audio kann die Pipeline NICHT alleine übernehmen**
   - Nur Batch, nur English, kein VAD, kein Streaming
2. **LFM2.5-Audio TTS ist der wertvollste First-Use-Case**
   - 8x schneller als Vorgänger, 4 Stimmen, gute Qualität
3. **Whisper bleibt zuverlässig für STT**
   - WER 7.44, produktionserprobt, kein WIP-Runner
4. **Granite bleibt Conversation-Engine**
   - Bewährt, stabil, Session/Memory/Graph-Integration

---

## 21. Decision

```
PRIMARY VOICE ENGINE: HYBRID
```

### Begründung (10 Punkte)

1. **LFM2.5-Audio ist Batch-only** — kein Streaming, keine Live-Inferenz → kann Mikrofon nicht direkt ersetzen
2. **Nur English** — GUIALITA braucht Deutsch → Whisper bleibt nötig
3. **Kein VAD/Turn Detection** — Modell erkennt Sprachende nicht → externes System weiterhin nötig
4. **Runner WIP** — PR #18641 "Do Not Merge" → keine Production-Garantie
5. **Kein GPU-Audio-Runner** — Nur CPU-Bibliotheken im lokalen Runtime → GTX 1080 Ti nicht nutzbar für Audio
6. **llama-cpp-python hat keine Audio-API** — LFM2.5-Audio nicht über Python-Adapter nutzbar
7. **TTS ist der wertvollste Use-Case** — 8x schneller, 4 Stimmen, gute Qualität
8. **Bestehende Pipeline funktioniert** — Whisper + Granite + ChatService = bewährt
9. **Session/Memory/Graph bleibt unverändert** — Text-basiert, kein Bruch
10. **Hybrid ist erweiterbar** — LFM kann schrittweise integriert werden

---

## Evidence Labels Summary

| Aussage | Label |
|---------|-------|
| LFM2.5-Audio hat 1.5B Parameter | FACT |
| ASR WER 7.53 Durchschnitt | FACT |
| TTS Output 24kHz | FACT |
| 4 Stimmen (US/UK male/female) | FACT |
| Nur English unterstützt | FACT |
| PR #18641 ist "Do Not Merge" | FACT |
| Kein VAD im Modell dokumentiert | FACT |
| Kein Streaming im Runner | FACT |
| llama-cpp-python v0.3.34 hat keine Audio-API | VERIFIED |
| liquid-audio ist kein pip-Paket | VERIFIED |
| Kein GPU-Audio-Runner (nur CPU .so) | VERIFIED |
| sounddevice ist nicht installiert | VERIFIED |
| LFM2.5-Audio ASR funktioniert (Batch) | VERIFIED |
| Granite 3B passt in VRAM neben LFM | INFERENCE |
| TTS könnte Pipeline verbessern | PROPOSAL |
| Interleaved Mode könnte Realtime ermöglichen | HYPOTHESIS |
| Deutsch-Support ist unklar | UNKNOWN |
| llama-liquid-audio-server funktioniert | UNKNOWN |
| Modell hat internes VAD | UNKNOWN |

---

**LFM_AUDIO_AUDIT: PASS**

Keine Implementierung. Keine Dependency-Änderung. Kein Modell-Download.
Bestehende GUIALITA-Baseline: GUIALITA-GRAPH-VISUALIZATION-V1-PASS — unverändert.
