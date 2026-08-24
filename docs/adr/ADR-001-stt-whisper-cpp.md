# ADR-001 — whisper.cpp als STT-Runtime

**Status**: ACCEPTED
**Datum**: 2026-08-20
**Kontext**: Phase 1B → Voice Activation V1
**Ersetzt**: die ursprüngliche Annahme aus Phase 1B, LFM2.5-Audio übernehme den
STT-Pfad des Sprachassistenten

---

## Entscheidung

GUIALITA verwendet **whisper.cpp (`whisper-cli`, Modell `ggml-base.bin`)** als
Speech-to-Text-Runtime der Live-Sprachschleife.

LFM2.5-Audio bleibt die **TTS**-Runtime. Es wird nicht durch etwas anderes
ersetzt, und es wird nicht zusätzlich als STT eingesetzt.

## Aktuelle reale Laufzeitkette

```text
Mikrofon (16 kHz mono)
    ↓
whisper.cpp            → STT          (CPU, Sprache: de)
    ↓
Granite 4.1 3B         → Kognition    (llama-cpp-python, CUDA, 41/41 Layer)
    ↓
LFM2.5-Audio-1.5B      → TTS          (llama-liquid-audio-cli, CPU)
    ↓
Audioausgabe
```

Rollenverteilung, unmissverständlich:

| Komponente | Rolle | Status |
|---|---|---|
| whisper.cpp | STT der Live-Schleife | CURRENT |
| Granite 4.1 3B | Textkognition | CURRENT |
| LFM2.5-Audio-1.5B | TTS | CURRENT |
| LFM2.5-Audio-1.5B | Batch-ASR in `scripts/process_audio.py` (Phase 1B) | CURRENT, separater Pfad |
| LFM Vision (VL-3B / VL-1.6B) | Perzeption | FUTURE, nicht angebunden |

## Begründung

1. **Kein Audio-Input in llama-cpp-python.** Version 0.3.35 besitzt keine
   Audio-API. LFM2.5-Audio ist über den primären Runtime-Adapter nicht als
   STT ansprechbar (belegt in `docs/LFM25_AUDIO_AUDIT_V2.md`).
2. **Der offizielle Liquid-Runner ist WIP und CPU-only.**
   `llama-liquid-audio-cli` stammt aus llama.cpp PR #18641, läuft
   ausschließlich auf CPU und wird pro Aufruf neu geladen. Als Batch-Werkzeug
   in Phase 1B akzeptabel, für die Live-Schleife zu langsam.
3. **Sprachabdeckung.** Die ASR von LFM2.5-Audio ist EN-fokussiert; deutsche
   Eingaben werden grob transkribiert (dokumentiert in
   `docs/GUIALITA_STATE.yaml`, `known_issues`). whisper.cpp `ggml-base`
   transkribiert Deutsch brauchbar.
4. **Bereits vorhanden.** whisper.cpp war lokal gebaut und einsatzbereit —
   keine zusätzliche schwere Abhängigkeit.

## Konsequenzen

**Positiv**

- Deutscher STT-Pfad funktioniert im Live-Betrieb.
- Klare Trennung der Zuständigkeiten pro Modalität.
- Keine neue Python-Abhängigkeit (Aufruf per Subprozess).

**Negativ / offen**

- whisper.cpp läuft CPU-gebunden: **~14 s pro Transkription**
  (gemessen in Voice Forensics V1). Zweitgrößter Latenzposten nach dem LLM.
- Zwei getrennte Audio-Runtimes (whisper.cpp + llama-liquid-audio-cli) statt
  einer einheitlichen.
- `whisper-cli` ist eine externe Systemabhängigkeit, nicht per pip
  installierbar. Pfad über `GUIALITA_WHISPER_CLI` (siehe `.env.example`).

## Verworfene Alternativen

| Alternative | Grund der Ablehnung |
|---|---|
| LFM2.5-Audio als Live-STT | Keine Audio-API in llama-cpp-python; CPU-only-Runner; EN-fokussierte ASR |
| Cloud-STT | Projektgrundsatz: rein lokal, keine Cloud-Dienste |
| faster-whisper / GPU-Whisper | Neue schwere Abhängigkeit; nicht evaluiert — bleibt Kandidat für die Latenzoptimierung |

## Revisionsauslöser

Diese Entscheidung wird neu bewertet, wenn eine der folgenden Bedingungen
eintritt:

- llama-cpp-python erhält eine stabile Audio-Input-API,
- der Liquid-Audio-Runner erhält GPU-Unterstützung und verlässliche
  Mehrsprachigkeit,
- die STT-Latenz wird zum dominierenden Engpass (aktuell dominiert das LLM).

## Belege

- `docs/LFM25_AUDIO_AUDIT_V2.md` — fehlende Audio-API
- `docs/PHASE_1B_WAV_LFM_AUDIO.md` — Batch-ASR-Pfad mit LFM2.5-Audio
- `docs/PHASE_VOICE_FORENSICS_V1_RESULT.md` — STT-Latenz ~14 s, CPU-gebunden
- `config/models.yaml` — `stt.engine: whisper.cpp`
- `config/voice.yaml` — `stt_engine: whisper`
