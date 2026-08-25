# GUIALITA — Lokale kognitive/Audio-Runtime

GUIALITA ist eine vollständig lokale Runtime mit HTTP-Schnittstelle für Chat,
Memory und Audio-Pipeline.

```text
Mikrofon → whisper.cpp (STT) → Granite/LFM-Kognition → LFM2.5-Audio (TTS)
                                      ↕
                         SQLite: Session · Memory · Graph
```

Der **verbindliche Projektzustand** steht ausschließlich in:

```text
docs/GUIALITA_STATE.yaml
```

README, Phase-Reports und Protokolle sind Hilfs- bzw. Evidenzdokumente. Wenn
sich Angaben widersprechen, gilt `docs/GUIALITA_STATE.yaml`.

---

## Neue Session / Arbeitsbeginn

Empfohlene Reihenfolge:

```bash
git status --short --branch
# Nur bei sauberer Arbeitskopie und vorhandener Remote-Branch:
git pull --ff-only

sed -n '1,220p' docs/GUIALITA_SESSION_BOOTSTRAP.md
sed -n '1,260p' docs/GUIALITA_STATE.yaml
python3 scripts/doctor.py
python3 scripts/run_all_tests.py --list
```

Wichtig:

- Nicht auf einen anderen Branch wechseln, wenn die Arbeitsumgebung einen festen
  Branch vorgibt.
- Nach einem Pull oder Maschinenwechsel den State erneut lesen.
- Keine neue Phase aus der Existenz von Dateien ableiten. Autorisierung steht im
  State.

---

## Schnellstart

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
bash scripts/setup_local.sh
GUIALITA_VENV="$PWD/.venv" bash scripts/start.sh
```

Danach prüfen:

```bash
curl -s http://localhost:8080/diagnostics | python3 -m json.tool
```

Stoppen:

```bash
bash scripts/stop.sh
```

`stop.sh` beendet nur GUIALITA-Prozesse. Ollama ist ein optionaler Shared
Service und wird nicht gestoppt oder umkonfiguriert.

---

## Lokale Konfiguration

Maschinenspezifische Pfade gehören in `.env` und nicht ins Git. Vorlage:

```bash
cp .env.example .env
```

Wichtige Variablen:

```text
GUIALITA_ROOT
GUIALITA_MODEL_ROOT
GUIALITA_EXTERNAL_MODEL_ROOT
GUIALITA_RUNTIME_ROOT
GUIALITA_DATA_ROOT
GUIALITA_WHISPER_CLI
GUIALITA_VENV
```

Pfadauflösung und Defaults sind in `backend/paths.py` implementiert.

Externe, nicht per pip installierbare Komponenten:

- `whisper.cpp` / `whisper-cli` für Live-STT
- `llama-liquid-audio-cli` für LFM2.5-Audio-TTS
- Modelldateien wie GGUF/BIN
- optional Ollama als Shared Service auf Port 11434

---

## Diagnose

```bash
python3 scripts/doctor.py
```

Der Doctor ist read-only. Er lädt keine Modelle herunter, startet keine Services
und verändert Ollama nicht.

Backend-Diagnose bei laufendem Server:

```bash
curl -s http://localhost:8080/diagnostics | python3 -m json.tool
```

---

## Tests

Die primäre Testinventur läuft ohne Backend:

```bash
python3 scripts/run_all_tests.py --list
```

Alle Suiten:

```bash
python3 scripts/run_all_tests.py
```

Viele Tests benötigen Backend, Modelle, GPU, Mikrofon, `espeak-ng` oder lokale
Audio-Runtimes. Der Runner unterscheidet deshalb `PASS`, `FAIL` und
`NOT_EXECUTED`. Tests aus `NOT_EXECUTED`-Suiten zählen nicht als bestanden.

Einzelne Suite:

```bash
python3 tests/test_api.py
```

---

## Offenes Performance-Gate

Die aktuell empfohlene Nachmessung steht im State. Auf der Zielmaschine mit
Modellen, Mikrofon und Audio-Runtime:

```bash
python3 scripts/measure_voice_turn.py --record --turns 3
```

Das Skript schreibt einen Report nach:

```text
docs/measurements/voice-turn-<zeitstempel>.yaml
```

Erst danach sollten die Werte in `docs/GUIALITA_STATE.yaml` übertragen und das
zugehörige Gate bewertet werden.

---

## Projektstruktur

```text
backend/      FastAPI, Modellmanager, ChatService, Memory, Audio
config/       Modell- und Voice-Konfiguration
docs/         State, ADRs, Baselines, Phase-Reports, Protokolle
frontend/     statisches HTML/JS-Frontend
scripts/      Start/Stop, Setup, Diagnose, Tests, Messungen
tests/        unittest-/pytest-basierte Suiten
PROTOTYPEN/   nicht angebundene Prototypen
```

---

## Dokumentationsregeln

- `docs/GUIALITA_STATE.yaml` ist die einzige verbindliche Statusquelle.
- Phase-Reports sind historische Evidenz und werden nicht rückwirkend geändert.
- Architekturentscheidungen gehören als ADR nach `docs/adr/`.
- Keine Modelle, Datenbanken, WAVs, Logs oder Binaries ins Git.
- Vision, Desktop-/Browser-Control, MUSCAL, WebSocket und Streaming sind nicht
  aus README-Hinweisen autorisiert. Maßgeblich ist immer der State.
