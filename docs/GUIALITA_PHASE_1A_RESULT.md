# GUIALITA PHASE 1A RESULT

Kanonischer, menschenlesbarer Ergebnisbericht für PHASE 1A.
Gespeichert am 2026-08-18, unmittelbar nach Abschluss von Phase 1A.
Der Bericht bildet das gelieferte Testergebnis exakt ab — ohne Ausschmückung.

---

## STATUS: PASS

| Prüfpunkt | Ergebnis | Evidenz |
|-----------|----------|---------|
| MICROPHONE | PASS | ZOOM H2n USB (Default), HDA Intel ALC898, virtuelles Test-Mikrofon erkannt |
| CONTINUOUS MONITOR | PASS | Kontinuierlicher Stream nach explizitem Start; CPU ~1.9 %, RAM ~51 MB |
| LEVEL DETECTION | PASS | RMS/Peak/dBFS live im `--debug`-Modus sichtbar |
| VAD | PASS | LevelDetector (RMS/Level-Schwellen), austauschbare Schnittstelle |
| AUTOMATIC RECORDING | PASS | Speech-Start nach 400 ms Sprache, mit 400 ms Pre-Roll |
| SILENCE DETECTION | PASS | Speech-Ende nach 700 ms Stille |
| WAV | PASS | PCM s16le, mono, 16 kHz, `audio/inbox/` |
| WAV VALIDATION | PASS | `file`/`ffprobe` gültig; interner Check PASS/EMPTY/SILENT/FAIL |
| MULTIPLE RECORDINGS | PASS | 5/5 eindeutige WAV-Dateien |
| REGRESSION | PASS | API-Tests 18/18, Desktop-Starter, start.sh/stop.sh, /health, GPU, Text-Chat, Ollama-Isolation (PID unverändert) |

## Thresholds

| Parameter | Wert |
|-----------|------|
| speech_threshold_db | -35.0 dBFS |
| silence_threshold_db | -45.0 dBFS |
| minimum_speech_ms | 400 |
| silence_timeout_ms | 700 |
| maximum_recording_ms | 30000 |
| pre_roll_ms | 400 |

## Performance

| Metrik | Wert |
|--------|------|
| CPU (Monitoring, 8 s Fenster) | 1.9 % |
| RAM (Monitoring) | ~51 MB (50.8 → 52.7 MB, stabil) |
| GPU | keine Nutzung |

## Created artifacts

- `scripts/audio_capture.py`
- `tests/test_capture.py`
- `docs/PHASE_1A_AUDIO_CAPTURE.md`
- `docs/phase-1a-audio-capture.yaml`
- `audio/inbox/` (Test-WAVs + JSON-Metadaten als Artefakte)

## Known issues

- Debug-Log kann `-300 dBFS` zeigen: numerisches Rauschen leerer Pulse-Puffer, harmlos
- nohup puffert stdout; für Live-Debug `python -u` verwenden
- Audio-Device-Index ist systemabhängig (`--list-devices`)

## Known risks

- Schwellen für H2n/virtuelle Umgebung validiert; in lauten Umgebungen ggf. anheben
- PulseAudio-Quellen-Suspendierung kann den ersten Trigger verzögern
- Geteiltes Default-Mikrofon (H2n) kann Stream-Öffnung verzögern

## Baseline

`GUIALITA-PHASE-0.5-PASS` (regressionsgeprüft)

Neue Baseline nach dieser Phase: `GUIALITA-PHASE-1A-PASS`

## HARD STOP

Phase 1A ist abgeschlossen.

Phase 1B (WAV → LFM2.5-Audio → Transkript) ist `NOT_STARTED` und wird
NICHT automatisch gestartet. Explizite Autorisierung erforderlich.

Die nächste autorisierte Phase ist: KEINE (Warten auf Freigabe).
