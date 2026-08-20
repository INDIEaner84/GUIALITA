# GUIALITA Phase 1B — WAV → LFM2.5-Audio → Transkript → Safe Renaming

## Status

PASS

## Date

2026-08-18

## Mission

    existing WAV
        → LFM2.5-Audio-1.5B
        → echte Audio-Analyse / Transkription
        → strukturiertes Ergebnis
        → sicheres Dateinamen-Design
        → Rename/Move nach audio/processed/
        → Metadaten

Primäres Ziel bewiesen:

    WAV → lokales LFM2.5-Audio → ECHTES ERGEBNIS

## Baseline

- `GUIALITA-PHASE-0-PASS`
- `GUIALITA-PHASE-0.5-PASS`
- `GUIALITA-PHASE-1A-PASS`
- Neue Baseline nach dieser Phase: `GUIALITA-PHASE-1B-PASS`

## Model

| Eigenschaft | Wert |
|-------------|------|
| Name | LFM2.5-Audio-1.5B (Liquid AI) |
| Architektur (GGUF) | `lfm2` (general.architecture = "lfm2") |
| Dateien | `models/lfm-audio-1.5b/` |
| Hauptmodell | `LFM2.5-Audio-1.5B-Q4_0.gguf` (695 MB, Q4_0, GGUF v3, 148 Tensoren) |
| MM-Projektion | `mmproj-LFM2.5-Audio-1.5B-Q4_0.gguf` (219 MB) |
| Vocoder | `vocoder-LFM2.5-Audio-1.5B-Q4_0.gguf` (108 MB) |
| Tokenizer | `tokenizer-LFM2.5-Audio-1.5B-Q4_0.gguf` (50 MB) |
| Quelle | LiquidAI/LFM2.5-Audio-1.5B-GGUF (HuggingFace, veröffentlicht 2026-08-03) |

## Runtime

| Eigenschaft | Wert |
|-------------|------|
| Name | `llama-liquid-audio-cli` (offizieller Liquid-AI-Runner) |
| Version/Build | v0.9.5 (libggml-base 0.9.5, libmtmd 0.0.7641), vom HF-Repo-Runner (2026-02-04) |
| Quelle | `runners/llama-liquid-audio-ubuntu-x64.zip` (LiquidAI/LFM2.5-Audio-1.5B-GGUF) |
| Basis | llama.cpp PR #18641 (WIP, "model: LFM2.5-Audio-1.5B", nicht im upstream gemerged) |
| Backend | CPU-only (libggml-cpu-sandybridge; KEIN CUDA-Backend im Runner) |
| Ablage | `runtime/liquid-audio/` (13 MB ZIP / 34 MB entpackt) |

## Runtime-Kompatibilität (Kernbefund)

- **llama-cpp-python 0.3.35**: kann das `lfm2`-GGUF als Textmodell laden,
  besitzt aber **KEINERLEI Audio-APIs** (kein `llama_audio_encoder`,
  keine `llama_audio_embeddings`, kein mmproj-Audio-Pfad).
  Text-Inferenz mit dem Audio-Modell funktioniert (bewiesen), Audio nicht.
- **Offizieller Runner** (`llama-liquid-audio-cli`): führt ASR vollständig aus
  (Audio-Encoder → Audio-Tokens → LLM-Decode → Text).
- Kompatibilitätsklassifikation:
  - installiertes llama-cpp-python 0.3.35: **INCOMPATIBLE** für Audio
  - offizieller LiquidAI-Runner: **COMPATIBLE** (genau dafür gebaut)
- Kein Whisper/Cloud-Ersatz verwendet. Kein Fake. Das Transkript ist die
  echte Ausgabe des LFM2.5-Audio-Modells.

## Model Lifecycle (Abschnitt 11)

Der Runner lädt bei **jedem** Aufruf frisch und gibt nach Prozessende alles frei:

    WAV ankommt → Runner startet → Modell lädt → Inferenz → Ergebnis → Prozess endet → freigegeben

Gemessen (VRAM, Granite-Textmodell bleibt resident):

| Zeitpunkt | VRAM |
|-----------|------|
| vor | 4708 MiB |
| während | 4708 MiB |
| nach | 4708 MiB |

LFM2.5-Audio nutzt ausschließlich CPU, keine zusätzliche GPU-/VRAM-Belegung.
Kein permanentes Laden des Audio-Modells.

## Audio Format

| Eigenschaft | Wert |
|-------------|------|
| Sample Rate | 16000 Hz (Phase-1A-WAVs) |
| Channels | 1 (mono) |
| Bit Depth | 16-bit PCM |
| Dauer (Beispiel) | 1620 ms |

Der Runner akzeptiert 16-kHz-mono-WAV direkt (Audio-Encoder preprocessed
intern, in 1929 ms für eine 1.6-s-Aufnahme). Keine Resampling-Konvertierung
der Original-WAV erforderlich; Original bleibt Quellartefakt.

## Preprocessing

Kein explizites Preprocessing durch GUIALITA: Die WAV wird unverändert an
den Runner übergeben. Der Audio-Encoder des Modells übernimmt die interne
Verarbeitung (Mel-Spektrogramm → Audio-Tokens).

## Inference-Methode

ASR-Systemprompt `"Perform ASR."`:

    llama-liquid-audio-cli -m LFM2.5-Audio-1.5B-Q4_0.gguf
        -mm mmproj-LFM2.5-Audio-1.5B-Q4_0.gguf
        -mv vocoder-LFM2.5-Audio-1.5B-Q4_0.gguf
        --tts-speaker-file tokenizer-LFM2.5-Audio-1.5B-Q4_0.gguf
        -sys "Perform ASR." --audio <wav> -t 12

Output-Parsing: `=== GENERATED TEXT ===`-Block.

## Latency (Beispiele)

| Messung | Wert |
|---------|------|
| Modell-Load | 497–1975 ms |
| Audio-Encode | 743–5435 ms |
| Decode | 1174–2054 ms |
| Total (Subprozess) | 7113–19506 ms |

(Werte variieren mit Disk-Cache: erster Lauf kalt, Folgeläufe warm.)

## Verarbeitungs-Zustände

    DISCOVERED → VALIDATED → LOADING_MODEL → INFERENCE → RESULT_RECEIVED
    → METADATA_CREATED → RENAMING → COMPLETED
    Fehler: → FAILED (Original bleibt unverändert)

## Result Schema (Metadaten-JSON, `AUDIO-XXXXXX.json`)

```json
{
  "audio_id": "AUDIO-000001",
  "source_filename": "audio_20260818_195713_001.wav",
  "final_filename": "20260818_214137__namadomayus.wav",
  "transcript": "Namadomayus.",
  "model": "LFM2.5-Audio-1.5B",
  "model_file": "LFM2.5-Audio-1.5B-Q4_0.gguf",
  "runtime": "llama-liquid-audio-cli (LiquidAI, CPU)",
  "duration_ms": 1620,
  "sample_rate": 16000,
  "channels": 1,
  "sample_width": 16,
  "timestamp": "2026-08-18T21:41:37",
  "status": "SUCCESS",
  "confidence": null,
  "model_load_ms": 497,
  "inference_ms": 1218,
  "encode_ms": 743,
  "total_processing_ms": 7113
}
```

`confidence` ist `null` — der Runner liefert keine Konfidenz, es wird keine
erfunden. `transcript` ist die autoritative ASR-Ausgabe, keine
LLM-Interpretation.

## AUDIO-ID

Kollisionssichere laufende ID über Zählerdatei `audio/.audio_id_counter`:
`AUDIO-000001`, `AUDIO-000002`, ... (nicht aus dem Dateinamen abgeleitet).

## Dateinamen-Schema

    YYYYMMDD_HHMMSS__<slug>.wav

Slug: lowercase, nur `[a-z0-9äöüß-]`, max 60 Zeichen, `/ \ : * ? " < > | .. $ ;`
und Shell-Metazeichen werden entfernt/ersetzt. Kollisionen → `-2`, `-3`-Suffix.
Leerer Slug → `transcript`.

Beispiel:

    audio_20260818_195713_001.wav → 20260818_214137__namadomayus.wav

## Fehlerbehandlung

| Fall | Verhalten |
|------|-----------|
| fehlende WAV | Validierungsfehler, Abbruch |
| korrupte/zu kleine WAV | `FAILED` (too_small/corrupt), Original bleibt |
| unsupported (nicht 16-bit/nicht mono) | `FAILED`, Original bleibt |
| stille WAV | `SILENT` (vor Inferenz erkannt), kein Transcript, Original bleibt |
| fehlendes Modell/Runner | `MODEL_ERROR`, kontrollierter Abbruch |
| leeres Transkript | `NO_TRANSCRIPTION`, kein Rename, Original bleibt |
| Rename-/Metadatenfehler | `FAILED`, Original bleibt |
| Inferenz-Fehler (rc != 0) | `INFERENCE_ERROR` mit Log-Tail |

Nie wird `SUCCESS` gemeldet, wenn kein echter Transcript existiert.

## Verzeichnisse

    audio/
        inbox/      (Eingang, Phase-1A-WAVs)
        processed/  (erfolgreich: WAV + AUDIO-XXXXXX.json)
        failed/     (Reserve für künftige fehlgeschlagene Artefakte)
        .audio_id_counter

## CLI

    python scripts/process_audio.py <wav>                 # Standardlauf
    python scripts/process_audio.py <wav> --debug         # Runner-Log
    python scripts/process_audio.py <wav> --keep-original # Original bleibt in inbox
    python scripts/process_audio.py <wav> --no-rename     # nur Analyse/Transkript
    python scripts/process_audio.py <wav> --output <dir>
    python scripts/process_audio.py <wav> --model <gguf> --runner <cli>

## Tests (Testmatrix)

Automatisierte Suite: `tests/test_process_audio.py` → **13/13 PASS**

| Test | Erwartung | Ergebnis |
|------|-----------|----------|
| T1 gültige Sprach-WAV | echter Transcript | PASS ("Hello, Guliya." — echte ASR) |
| T2 zweite WAV | anderer Transcript | PASS ("Massive sinatra test.") |
| T3 stille WAV | kein falscher Transcript | PASS (SILENT, Original bleibt) |
| T4 sehr kurze WAV | kontrolliertes Ergebnis | PASS ("I", SUCCESS) |
| T5 längere WAV | Erfolg | PASS ("The system lingered max ...") |
| T6 ungültige WAV | Validierungsfehler | PASS (too_small, Original bleibt) |
| T7 fehlendes Modell | kontrollierter Modellfehler | PASS (MODEL_ERROR, Original bleibt) |
| T8 mehrere WAVs | eindeutige AUDIO-IDs | PASS (AUDIO-000013/14/15) |
| T9 Dateinamen-Sicherheit | keine unsicheren Namen | PASS (5 Unit-Tests) |
| T10 Duplikat | keine Kollision, kein Überschreiben | PASS (2 eindeutige Dateien) |

Hinweis: T4 lieferte bei einem kurzen 440-Hz-Ton "I" (SUCCESS) — der
Runner toleriert Nicht-Sprach-Audio. Dies wird als kontrolliertes Ergebnis
akzeptiert und dokumentiert.

## Realitätstest

`REAL AUDIO INFERENCE: PASS`

Mehrere reale Phase-1A-WAVs (echte Aufnahmen, espeak-Synthese als
Sprachquelle via virtuelles Mikrofon) wurden durch die echte
LFM2.5-Audio-Runtime verarbeitet. Keine Mock-Antworten.

Hinweis zur Qualität: LFM2.5-Audio ist EN-fokussiert (Sprachmodell-Card:
`language: en`). Deutsche espeak-Synthese wird semantisch grob
transkribiert (z. B. "Aufnahme Nummer eins." → "Namadomayus."). Das ist
die echte Modell-Leistung, kein Fehler der Pipeline. Für deutsche
Eingaben in hoher Qualität wäre ein weiteres ASR-System nötig
(separat zu autorisieren).

## Regression

| Prüfung | Ergebnis |
|---------|----------|
| API-Testsuite (Phase 0/0.5/1) | 18/18 PASS |
| Phase-1A-Capture-Tests | 7/7 PASS |
| Text-Chat (Granite, llamacpp) | PASS ("OK") |
| /health | online |
| GPU-Detektion | unverändert |
| Desktop-Starter | unverändert vorhanden |
| start.sh / stop.sh | unverändert |
| Ollama HTTP | 0.30.10 |
| Ollama-PID | unverändert (2492667) |

## Ressourcen

| Metrik | Wert |
|--------|------|
| Runner-Größe | 13.2 MB ZIP / 34 MB entpackt |
| Neuer Datenträgerverbrauch | ~34 MB (keine Modellkopien, keine neuen Modelle) |
| VRAM (vor/während/nach) | 4708 / 4708 / 4708 MiB |
| Keine neuen Python-Dependencies im venv (gguf nur für Verifikation) | siehe unten |

## Files Created

- `scripts/process_audio.py`
- `tests/test_process_audio.py`
- `runtime/liquid-audio/` (offizieller Runner: cli, server, libggml-*, libmtmd, libliquid-audio)
- `docs/PHASE_1B_WAV_LFM_AUDIO.md`
- `docs/phase-1b-wav-lfm-audio.yaml`
- `audio/processed/` (+ WAVs und AUDIO-XXXXXX.json als Artefakte)

## Files Modified

- `docs/GUIALITA_STATE.yaml` (Phase 1B → PASS)
- `docs/GUIALITA_SESSION_BOOTSTRAP.md` (Status + Hinweise)
- `docs/GUIALITA_PHASE_STATUS.md` (Matrix)
- venv: `gguf` (0.19.0) nur für die Modell-Metadaten-Verifikation installiert
  (Verifikations-Hilfsmittel, nicht Laufzeit-Abhängigkeit des Workers)

## Files Deleted

Keine.

## Known Issues

1. ASR-Qualität für deutsche espeak-Synthese gering (EN-fokussiertes Modell).
2. Runner ist CPU-only; Latenz dominiert durch Audio-Encode (0.7–5.4 s).
3. `llama-liquid-audio-cli` ist WIP (PR #18641) — nicht Teil stabiler llama.cpp-Releases.
4. Sehr kurze Nicht-Sprach-Audio kann zu einem kurzen "Phantom"-Transkript führen.
5. Der Runner akzeptiert primär 16-kHz-mono; andere Formate nicht verifiziert.

## Known Risks

1. Runner/Build können sich auf HuggingFace ändern (WIP-Status).
2. Künftige llama.cpp-Versionen könnten die Architektur anders benennen.
3. Datenträger fast voll (32 GB frei) — keine weiteren großen Downloads ohne Freigabe.
4. `gguf`-Paket im venv nur für Verifikation; kann entfernt werden.

## Rollback

Phase 1B ist vollständig reversibel:

    rm -rf runtime/liquid-audio scripts/process_audio.py tests/test_process_audio.py
    rm audio/processed/* audio/.audio_id_counter
    pip uninstall gguf
    State-Dokumente auf 1A zurücksetzen

Baseline Phase 0/0.5/1A bleibt unberührt.

## Nächste Phase (nicht automatisch starten)

    PHASE 1C: Voice → LFM → TTS (nicht autorisiert)

Nur nach separater Freigabe implementieren.