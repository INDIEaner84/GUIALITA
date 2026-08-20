# GUIALITA Phase 1A — Audio Capture

## Status

PASS

## Date

2026-08-18

## Mission

Kleinstmöglicher Audio-Capture-Baustein:

    Mikrofon -> kontinuierliche Überwachung -> Sprache/Aktivität erkennen
    -> automatische Aufnahme -> Sprachpause -> WAV speichern

Kein STT, kein TTS, kein LFM, keine Chat-Integration in dieser Phase.
Die WAV ist das Endprodukt.

## Baseline

- `GUIALITA-PHASE-0-PASS` (9/9)
- `GUIALITA-PHASE-0.5-PASS` (18/18 inkl. Audio-Endpunkte aus Phase 1 STEP 1-7)
- Vorliegende Phase unverändert erhalten

## Forensic Inspection (Ergebnisse)

| Komponente | Befund |
|------------|--------|
| OS | Linux Mint 22.3 (XFCE) |
| Audio-Server | PulseAudio (`/run/user/1000/pulse/native`) |
| Default-Mikrofon | ZOOM H2n USB (`alsa_input.usb-...H2n...analog-stereo`, 48 kHz, s16le, RUNNING) |
| Weitere Inputs | HDA Intel PCH ALC898 Analog + Alt Analog |
| Python im venv | numpy 2.5.2 vorhanden; sounddevice/pyaudio fehlten |
| PortAudio System-Lib | vorhanden (`libportaudio.so.2`) |
| Neue Dependency | `sounddevice 0.5.6` (minimal, bindet vorhandene libportaudio, kein großer Stack) |
| Tools | file, ffprobe, sox, paplay, aplay, ffmpeg, espeak-ng vorhanden |

## Architektur

```
    Microphone Input (sounddevice/PortAudio, float32, 16 kHz mono)
                        ↓
              Audio Monitor / VAD (LevelDetector)
                        ↓
                  SPEECH DETECTED
                        ↓
                   WAV Recorder (Pre-Roll-Puffer)
                        ↓
                  SILENCE DETECTED
                        ↓
        WAV-Datei + JSON-Metadaten (audio/inbox/)
```

Capture ist logisch unabhängig vom LLM. Kein Modell wird geladen,
keine GPU-Nutzung.

### State Machine

    IDLE → MONITORING → SPEECH_DETECTED → RECORDING → FINALIZING → SAVED → MONITORING

## Level Detection (VAD)

Einfacher robuster RMS/Peak-Mechanismus (kein Cloud-VAD):

| Parameter | Wert | Bedeutung |
|-----------|------|-----------|
| speech_threshold_db | -35.0 | RMS über Schwelle → Speech |
| silence_threshold_db | -45.0 | RMS unter Schwelle → Silence |
| minimum_speech_ms | 400 | Mindest-Sprachdauer vor Aufnahmestart |
| silence_timeout_ms | 700 | Pause → Satzende |
| maximum_recording_ms | 30000 | Sicherheitsgrenze Aufnahmedauer |
| pre_roll_ms | 400 | Pre-Roll-Puffer (erste Silbe wird nicht abgeschnitten) |

Alle Werte per CLI überschreibbar (`--threshold`, `--silence-threshold`,
`--silence`, `--max-duration`, `--pre-roll`).

Die Detektor-Schnittstelle (`LevelDetector.process(samples) → dict`)
ist austauschbar durch ein echtes VAD (z. B. Silero), ohne den Worker
zu verändern.

### Bekannter Fix in dieser Phase

Der dB-Pegel wurde zunächst auf 16-bit-Full-Scale (32768) berechnet,
obwohl sounddevice float32-Samples im Bereich [-1.0, 1.0] liefert.
Daraus resultierte ein Pegelversatz von ~90 dB und nie ausgelöste
Aufnahmen. Behoben durch `db_from_amplitude(value, full_scale=1.0)`
für float32-Samples; die WAV-Validierung rechnet weiterhin mit
full_scale=32768 auf den gelesenen int16-Daten.

## WAV Format

- PCM, 16-bit, mono, 16000 Hz
- Gültig per `file` und `ffprobe` (pcm_s16le, 1ch, 16 kHz) verifiziert
- Name: `audio_YYYYMMDD_HHMMSS_NNN.wav` (zeitbasiert + laufende Nr., keine Benutzereingaben)
- Ablage: `audio/inbox/`

## Metadaten

Je Aufnahme entsteht `audio_..._NNN.json`:

```json
{
  "filename": "audio_20260818_195522_001.wav",
  "timestamp": "2026-08-18T19:55:22",
  "duration_ms": 5420,
  "sample_rate": 16000,
  "channels": 1,
  "sample_width": 16,
  "peak_db": -3.2,
  "rms_db": -20.5,
  "trigger": "level",
  "device": 15,
  "thresholds": { "speech_threshold_db": -35.0, "silence_threshold_db": -45.0, ... }
}
```

Keine Transkription, keine LLM-Daten.

## Audio-Qualitätscheck

Nach jeder Aufnahme wird die WAV geprüft: Existenz, Größe, Header,
Channels, Sample-Rate, Sample-Width, Framecount, RMS/Peak.
Klassifikation: PASS / EMPTY / SILENT / FAIL.
SILENT-Dateien werden nach `audio/failed/` verschoben.

## CLI

    python scripts/audio_capture.py                      # Standardlauf
    python scripts/audio_capture.py --debug              # Level-Logging
    python scripts/audio_capture.py --list-devices       # Geräte anzeigen
    python scripts/audio_capture.py --device 15          # bestimmtes Gerät
    python scripts/audio_capture.py --max-recordings 5   # begrenzter Lauf
    python scripts/audio_capture.py --threshold -30 --silence 1000 --max-duration 20000

Der Prozess öffnet das Mikrofon ausschließlich nach explizitem Start
(keine versteckte Aktivierung). Beendigung: Ctrl+C (SIGINT) → sauberes
Schließen des Streams, laufende Aufnahme wird verworfen.

## Testumgebung (automatisiert)

Für reproduzierbare Tests wird ein virtuelles Mikrofon verwendet:

    pactl load-module module-null-sink sink_name=guialita_vmic ...
    # ~/.asoundrc:
    pcm.guialita_vmic { type pulse; device "guialita_vmic.monitor" }

espeak-ng erzeugt Sprach-WAVs, `paplay --device=guialita_vmic` speist
sie in den Capture ein.

## Testplan-Ergebnisse

| Test | Erwartung | Ergebnis |
|------|-----------|----------|
| TEST 1 Mikrofon erkannt | PASS | PASS (H2n USB default, HDA ALC898, virtuelles Mikro) |
| TEST 2 Capture starten | MONITORING | PASS |
| TEST 3 Stille (10 s) | keine WAV | PASS (0 WAV) |
| TEST 4 kurze Sprache | 1 WAV | PASS (Format 1ch/16 bit/16 kHz/26880 frames) |
| TEST 5 längerer Satz | 1 WAV | PASS |
| TEST 6 Pause im Satz | 1 WAV | PASS |
| TEST 7 Hintergrundgeräusch | möglichst kein Falschtrigger | Manuell: Schwellen -35/-45 dBFS konfigurierbar; virtuelle Tests sauber |
| TEST 8 maximale Länge | max-Dauer greift | PASS (2980 ms bei 2500 ms Limit inkl. Pre-Roll + Abschluss) |
| TEST 9 WAV-Validierung | file/ffprobe gültig | PASS (pcm_s16le, mono, 16 kHz, 5.42 s) |
| TEST 10 mehrere Aufnahmen | 5 eindeutige WAVs | PASS (5/5 eindeutig) |

Automatisierte Suite: `tests/test_capture.py` → 7/7 PASS.

## Performance

| Metrik | Wert |
|--------|------|
| CPU (Monitoring, 8 s Fenster) | 1.9 % |
| RAM (Monitoring) | ~51 MB, stabil (50.8 → 52.7 MB) |
| Kein LLM/Audio-Modell geladen | ✓ |
| GPU-Nutzung | keine |

## Regression

| Prüfung | Ergebnis |
|---------|----------|
| Desktop-Starter (`~/.local/share/applications/GUIALITA.desktop`) | ✓ vorhanden |
| scripts/start.sh | ✓ Backend startet, Modell verfügbar, Browser öffnet |
| scripts/stop.sh | ✓ beendet nur GUIALITA |
| /health | ✓ online |
| GPU-Detektion | ✓ (llama-cpp-python, CUDA) |
| Text-Chat | ✓ (llamacpp, Antwort "OK") |
| API-Testsuite | 18/18 PASS |
| Ollama HTTP | ✓ 0.30.10 |
| Ollama PID nach GUIALITA-Stop | identisch (2492667) → Isolation PASS |

## Privacy

- Mikrofon nur bei explizitem Start aktiv, danach kontinuierlich bis Stop
- Keine Cloud, keine Netzwerkübertragung, keine automatische Aktivierung
- WAVs sind gewollte Testartefakte dieser Phase; später Verarbeitung/Löschung
- Keine Audiohistorie über inbox/failed hinaus

## Known Issues

1. Werte wie `-300 dBFS` im Debug-Log: numerisches Rauschen des leeren
   Pulse-Puffers (float32-Denormale), kein echtes Signal. Harmlos.
2. Puffer-/Timing-Artefakte beim Schreiben ins Log via nohup: stdout wird
   gepuffert; für Live-Debug `python -u` verwenden.
3. Automatisierte Tests benötigen das virtuelle Mikrofon (PulseAudio
   module-null-sink + .asoundrc); auf anderen Systemen manuelle Tests.
4. Der Sounddevice-Device-Index ist systemabhängig (`--list-devices`).

## Known Risks

1. Schwellen -35/-45 dBFS sind für das H2n + virtuelle Umgebung
   validiert; bei stark verrauschten Umgebungen ggf. anheben.
2. ZOOM H2n als Default-Mikrofon wird von anderen Anwendungen mitgenutzt;
   Capture öffnet den Stream dann ggf. nur mit Verzögerung.
3. PulseAudio-Suspendierung inaktiver Quellen: Bei langen Stillephasen
   kann der erste Trigger verzögert ankommen (beobachtet im Testbetrieb).
4. Bei parallelem Betrieb (Capture + Backend) keine Wechselwirkung;
   bisher keine Konflikte festgestellt.

## Files Created

- `scripts/audio_capture.py`
- `tests/test_capture.py`
- `audio/inbox/` (Zielverzeichnis für WAVs)

## Files Modified

- (keine Phase-0/0.5 Dateien verändert)
- `~/.asoundrc` (Test-Hilfsmittel: virtuelles Mikrofon, optional)
- venv: `sounddevice 0.5.6` installiert (neue, begründete Dependency)

## Rollback

Phase 1A ist vollständig reversibel:

    rm scripts/audio_capture.py tests/test_capture.py
    /home/hz/.guialita-venv/bin/pip uninstall sounddevice
    # optional: .asoundrc entfernen, pactl unload-module module-null-sink

Baseline (`GUIALITA-PHASE-0.5-PASS`) bleibt unberührt.

## Nächste Phase (nicht automatisch starten)

    PHASE 1B: WAV → LFM2.5-Audio → Transkript → WAV/Metadata umbenennen
    PHASE 1C: Voice → LFM → TTS

Nur nach separater Freigabe implementieren.