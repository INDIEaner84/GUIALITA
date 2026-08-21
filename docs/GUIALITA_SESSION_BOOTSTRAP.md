# GUIALITA — Session Bootstrap

Einstiegsdokument für eine neue Arbeitssitzung. Es enthält **keine
Statusangaben** — der Zustand steht ausschließlich in
[`docs/GUIALITA_STATE.yaml`](GUIALITA_STATE.yaml).

---

## 1. Zuerst lesen

| Reihenfolge | Datei | Zweck |
|---|---|---|
| 1 | `docs/GUIALITA_STATE.yaml` | **kanonischer Zustand** — Phasen, Baseline, offene Gates, Verbote |
| 2 | `docs/adr/` | getroffene Architekturentscheidungen |
| 3 | `docs/BASELINES/REGRESSION_CONTRACT.md` | was nicht regredieren darf |
| 4 | Phase-Reports nach Bedarf | historische Belege zu einzelnen Phasen |

Danach den Repository-Zustand selbst verifizieren (`git status`, Tests),
bevor irgendetwas geändert wird.

---

## 2. Was GUIALITA ist

Eine lokale kognitive/Audio-Runtime mit HTTP-Schnittstelle. Vollständig
lokal, keine Cloud-Dienste.

```text
Mikrofon → whisper.cpp (STT) → Granite 4.1 3B (Kognition) → LFM2.5-Audio (TTS)
                                        ↕
                        SQLite: Session · Memory · Graph
```

Rollen pro Modalität siehe `stt_architecture` in `GUIALITA_STATE.yaml` und
`docs/adr/ADR-001-stt-whisper-cpp.md`.

---

## 3. Einrichtung

```bash
git clone -b arena/01a01e70-guialita https://github.com/INDIEaner84/GUIALITA.git
cd GUIALITA

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # llama-cpp-python für GPU siehe Hinweis darin

bash scripts/setup_local.sh                 # sucht Modelle/Runtime, schreibt .env
bash scripts/start.sh                       # Backend + Browser
bash scripts/stop.sh                        # beendet NUR GUIALITA-Prozesse
```

`scripts/setup_local.sh` durchsucht Repo, Heimverzeichnis und eingehängte
Datenträger nach Granite, LFM-Audio, der Liquid-Runtime und `whisper-cli`
und schreibt die Fundstellen in `.env`. Es kopiert und löscht nichts.
`--dry-run` zeigt nur an, `--hint /pfad` ergänzt einen Suchort. Alternativ
`.env.example` von Hand kopieren.

**Hinweis exFAT**: Auf exFAT-Datenträgern gehen Ausführungsrechte und
Symlinks verloren. Das Repository gehört besser auf ein Linux-Dateisystem;
die Modelle können über `GUIALITA_EXTERNAL_MODEL_ROOT` auf der externen
Platte bleiben.

Ohne `.env` löst GUIALITA alles repository-relativ auf (`models/`,
`runtime/`, `data/`, `whisper-cli` aus `$PATH`). Maschinenspezifische Pfade
gehören in die lokale, nicht versionierte `.env`.

Konfigurierbare Variablen: `GUIALITA_ROOT`, `GUIALITA_MODEL_ROOT`,
`GUIALITA_EXTERNAL_MODEL_ROOT`, `GUIALITA_RUNTIME_ROOT`, `GUIALITA_DATA_ROOT`,
`GUIALITA_WHISPER_CLI`, `GUIALITA_VENV`. Aufgelöst in `backend/paths.py`.

---

## 4. Tests

Die Suiten sind eigenständige `unittest`-Skripte, kein pytest. **136
Testfunktionen in 9 Suiten**; 8 davon brauchen Backend, Modelle, GPU,
Mikrofon oder espeak-ng und sind daher nicht CI-fähig.

```bash
python3 scripts/run_all_tests.py          # alle Suiten, jede genau einmal
python3 scripts/run_all_tests.py --list   # Inventar ohne Ausführung
python3 scripts/run_all_tests.py --only memory tts
python3 tests/test_api.py                 # einzelne Suite (Backend nötig)
```

Der Runner stuft jede Suite als `PASS`, `FAIL` oder `NOT_EXECUTED` ein und
nennt bei `NOT_EXECUTED` die fehlende Voraussetzung. Tests aus einer
`NOT_EXECUTED`-Suite zählen **nicht** als bestanden.

Verschachtelte Suite-Aufrufe (eine Suite startet andere als Subprozess) sind
standardmäßig aus — sie verfälschten früher die Testzahlen.
`GUIALITA_TEST_NESTED=1` stellt das alte Verhalten her.

Umgebungsabhängige Tests: `GUIALITA_VENV_PY`, `GUIALITA_TEST_DEVICE_ID`.

Ein Test, der in der aktuellen Umgebung nicht laufen kann, ist
`NOT EXECUTED` — nicht `PASS` und nicht `FAIL`.

### Latenzmessung

```bash
python3 scripts/measure_voice_turn.py --record --turns 3   # Mikrofon
python3 scripts/measure_voice_turn.py --wav <datei.wav>    # reproduzierbar
python3 scripts/measure_voice_turn.py --text "…"           # ohne STT
```

Misst STT, LLM, Memory-Overhead und TTS einzeln, unterscheidet kalten und
warmen Turn und schreibt einen Report nach `docs/measurements/`. Stufen, die
nicht laufen können, werden als `NOT_EXECUTED` ausgewiesen — nie als `PASS`.

---

## 5. Konventionen

- **Ein Zustand, eine Datei.** Statusangaben gehören ausschließlich in
  `GUIALITA_STATE.yaml`. Neue Statustabellen in anderen Dokumenten sind der
  Grund, warum diese Datei existiert.
- **Phase-Reports sind unveränderlich.** Ein Report dokumentiert einen
  Zeitpunkt. Nachträgliche Korrektur ist Geschichtsfälschung — stattdessen
  neuen Report schreiben und `GUIALITA_STATE.yaml` aktualisieren.
- **Architekturentscheidungen als ADR**, nicht als Kommentar im Code.
- **Ollama ist ein SHARED SERVICE** (Port 11434) — wird erkannt, nie
  gestoppt, nie umkonfiguriert.
- **Keine Modelle, Datenbanken, WAVs, Logs oder Binaries in Git**
  (siehe `.gitignore`).
- Audio-Ablage: `audio/inbox/` → `audio/processed/`, Fehlerfälle
  `audio/failed/`.
- Doku-Konvention pro Phase: `docs/PHASE_*.md` (lesbar) +
  `docs/phase-*.yaml` (maschinenlesbar).

---

## 6. Grenzen

Verbote und Autorisierungspflichten stehen unter `prohibitions` in
`GUIALITA_STATE.yaml`. Kurzfassung: nichts implementieren, was dort nicht
freigegeben ist — insbesondere nicht Phase 1C, keine MUSCAL-Schichten, keine
Cloud-Anbindung. Autorisierung wird niemals aus der bloßen Existenz von
Dateien abgeleitet.
