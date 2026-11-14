# AGENTS.md — OpenCode-Anweisungsprompt für GUIALITA

> Diese Datei ist der **verbindliche Anweisungsprompt** für OpenCode (und jeden
> anderen Coding-Agenten) in diesem Repository. OpenCode lädt `AGENTS.md`
> automatisch als Projektinstruktion.
>
> Einzeiler für den kompletten Update-Lauf:
>
> ```bash
> opencode run "$(cat AGENTS.md)
>
> Führe jetzt den Abschnitt 'Arbeitsablauf: komplettes lokales Update' vollständig aus."
> ```
>
> Kurzform (wenn der Agent den Kontext schon hat):
>
> ```bash
> opencode run "GUIALITA komplett lokal updaten und verifizieren: bash scripts/local_update.sh --mock, danach scripts/run_all_tests.py ohne Mock, Ergebnis nach docs/SESSION_LOG.md. Regeln aus AGENTS.md einhalten."
> ```

---

## 1. Ziel der Anweisung

Bringe das lokale Repository in einen **nachweisbar lauffähigen** Zustand:

1. Abhängigkeiten installiert, Code syntaktisch sauber
2. Backend startet auf Port 8080 und beantwortet `/health`
3. Alle Testsuiten laufen **genau einmal** über `scripts/run_all_tests.py`
4. Jede Suite ist ehrlich klassifiziert: `PASS`, `FAIL` oder `NOT_EXECUTED`
5. Kein `FAIL` bleibt unerklärt; jeder `NOT_EXECUTED` hat eine konkrete Ursache
   (fehlendes Modell, fehlende Runtime, fehlende Hardware)
6. Das Ergebnis ist in `docs/SESSION_LOG.md` mit den echten Zahlen dokumentiert

**"Es läuft" heißt: nachgewiesen durch einen Testlauf auf dieser Maschine —
nicht durch Annahme, nicht durch einen alten Report.**

---

## 2. Verbindliche Projektregeln (nicht verhandelbar)

| Regel | Konsequenz |
|---|---|
| **Ollama ist ein SHARED SERVICE (Port 11434)** | Nur erkennen (`GET /api/tags`). Niemals starten, stoppen, konfigurieren, updaten oder Modelle darin löschen. |
| **Kein Cloud-/Netzwerk-LLM** | Keine API-Keys, keine externen LLM-Dienste, kein Download von Modellen als "Workaround". |
| **Kein Runtime-Austausch** | STT bleibt `whisper.cpp` (ADR-001), LLM bleibt `llama-cpp-python` primär / Ollama Fallback, TTS bleibt `llama-liquid-audio-cli`. Ein Wechsel braucht eine neue ADR. |
| **`docs/GUIALITA_STATE.yaml` ist die einzige Statusquelle** | Statusänderung zuerst dort, danach `docs/HEARTBEAT.md` / `docs/SESSION_LOG.md`. `GUIALITA_PHASE_STATUS.md` ist nur eine Ansicht. |
| **`NOT_EXECUTED` ≠ `PASS`** | Tests aus nicht ausgeführten Suiten dürfen niemals als bestanden dokumentiert werden. Der Runner weist sie getrennt aus — diese Trennung nicht verwischen. |
| **Freeze-Policy v2** | Eine `frozen: true`-Schicht darf nur geändert werden, wenn die zugehörige Suite **vorher PASS** lief, **nachher PASS** mit gleicher oder höherer Testzahl läuft und der Commit **beide Läufe** nennt. |
| **Bestehende Tests nicht löschen oder abschwächen** | Braucht explizite Autorisierung. Ein `skipTest` mit Begründung ist nur zulässig, wenn der Test auf einer Maschine mit vorhandener Runtime **unverändert** läuft. |
| **Keine neuen Fähigkeiten ohne Autorisierung** | Vision, Desktop-Control, MUSCAL, WebSocket-Streaming, Barge-in: nicht implementieren, nicht "vorbereiten". |
| **Keine Pfad-Hardcodierung** | Maschinenspezifische Pfade gehören in `.env` (siehe `.env.example`) und werden über `backend/paths.py` aufgelöst. Niemals absolute Pfade in `config/*.yaml`, Code oder Doku schreiben. |
| **Audit schreibt nur Metadaten** | `backend/audit.py` darf niemals Transcript/Response/Content persistieren, außer `GUIALITA_AUDIT_INCLUDE_CONTENT=1` ist explizit gesetzt. |

---

## 3. Arbeitsablauf: komplettes lokales Update

In dieser Reihenfolge ausführen. Jeder Schritt muss sein Ergebnis zeigen, bevor
der nächste beginnt.

### Schritt 0 — Ausgangszustand erfassen

```bash
git status --short
git log --oneline -3
git rev-parse --abbrev-ref HEAD
git fetch origin --prune
git log --oneline HEAD..origin/main          # leer = nichts zu integrieren
git merge-base --is-ancestor origin/main HEAD && echo "merge Konflikt-frei"
```

Erwartung: Branch bekannt, Arbeitsstand notiert. **Niemals** die Branch wechseln,
`git push --force` ausführen oder `.git` anfassen.

#### Umgebung kann zwischen Läufen verloren gehen

`.venv/`, `data/`, `scripts/logs/` und Caches sind gitignored und in
Agent-/CI-Umgebungen **nicht garantiert vorhanden**. Prüfen, bevor ein alter
Testbericht als Nachweis gilt:

```bash
ls -d .venv data scripts/logs 2>/dev/null
.venv/bin/python -c "import fastapi" 2>&1 | tail -1
curl -sf -m 3 localhost:8080/health >/dev/null && echo "Backend läuft" || echo "Backend steht"
```

Fehlt die Umgebung: neu aufbauen (`bash scripts/local_update.sh --mock`) und
**alle** Prüfungen neu ausführen. Ein historisches Ergebnis belegt den aktuellen
Stand nicht (siehe `docs/SINGLE_SOURCE_OF_TRUTH.md`).

#### Branch-Zeiger stimmt nicht mit dem Remote überein

Beobachtetes Muster: Arbeitsbaum enthält die Änderungen, der lokale Zeiger steht
aber auf der Basis, und der Commit liegt bereits auf dem Remote. **Erst
vergleichen, dann reparieren** — niemals blind `reset --hard` oder force-push:

```bash
git fetch origin <branch>
git diff FETCH_HEAD --stat                       # getrackte Dateien
git show FETCH_HEAD:<datei> | diff - <datei>     # je neuer/untracked Datei
git reset --mixed FETCH_HEAD                     # erst wenn alles identisch ist
```

`--mixed` versetzt nur Zeiger und Index, der Arbeitsbaum bleibt unangetastet.

### Schritt 1 — Ein-Kommando-Update (bevorzugt)

```bash
bash scripts/local_update.sh --mock
```

Das Skript erledigt: venv → Abhängigkeiten → `compileall` → `scripts/doctor.py`
→ Backend-Start → `/health`-Warte → `scripts/run_all_tests.py` → Unit-Schicht
→ sauberes Beenden → Fazit. Exit-Code `0` = kein FAIL.

Ohne Test-Adapter (echte Modelle sind vorhanden):

```bash
bash scripts/local_update.sh
```

### Schritt 2 — Manueller Pfad (nur wenn Schritt 1 nicht genutzt wird)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
bash scripts/setup_local.sh            # schreibt .env aus den Fundstellen dieser Maschine
.venv/bin/python -m compileall backend scripts tests
.venv/bin/python scripts/doctor.py
bash scripts/start.sh                  # bzw. --restart nach einem pull
curl -s localhost:8080/health
curl -s localhost:8080/diagnostics
.venv/bin/python scripts/run_all_tests.py
```

### Schritt 3 — Fähigkeitendiagnose lesen

```bash
curl -s localhost:8080/diagnostics | python3 -m json.tool
```

Pflichtprüfung:

- `environment`: alle `GUIALITA_*` aufgelöst, **kein** `${...}` übrig
- `models.<id>.path`: absolut **und** `exists` geprüft
- `capabilities`: `backend`, `llm`, `stt`, `tts` — was fehlt, ist eine
  Umgebungstatsache, kein Codefehler
- `ready_for_voice_turn`: nur `true`, wenn **keine** Fähigkeit fehlt
- `missing_capabilities` + `hint`: fehlen Pfade → `bash scripts/setup_local.sh`

### Schritt 4 — Testergebnis ehrlich auswerten

Erwartete Klassifizierung auf einer Maschine **ohne** Modelle/Audio-Hardware:

| Suite | Erwartung | Begründung |
|---|---|---|
| `test_voice_activation.py` | `PASS` | keine Voraussetzung |
| `test_graph_visualization.py` | `PASS` | nur Backend |
| `test_memory.py` | `PASS` (mit Mock) | nur Backend + Chat-Pfad |
| `test_memory_retrieval.py` | `PASS` (mit Mock) | nur Backend + Chat-Pfad |
| `test_memory_graph.py` | `PASS` (mit Mock) | nur Backend + Chat-Pfad |
| `test_api.py` | `PASS` (mit Mock) | Runtime-Tests springen mit Begründung |
| `test_tts.py` | `NOT_EXECUTED` | `llama-liquid-audio-cli` + LFM-Audio-Modell fehlen |
| `test_capture.py` | `NOT_EXECUTED` | Mikrofon/PortAudio + `espeak-ng` fehlen |
| `test_process_audio.py` | `NOT_EXECUTED` | LFM-Audio-Runtime + `espeak-ng` fehlen |

Abbruchkriterium: **jede** Suite mit `FAIL` muss repariert oder begründet werden.
Ein `FAIL` darf nicht durch Löschen, Kommentieren oder Abschwächen des Tests
beseitigt werden.

### Schritt 5 — Manuelle Rauchprobe des API-Vertrags

```bash
curl -s localhost:8080/health
curl -s localhost:8080/models
curl -s -X POST localhost:8080/sessions
curl -s -X POST localhost:8080/chat -H 'Content-Type: application/json' \
     -d '{"message":"Test","model":"granite-3b"}'
curl -s localhost:8080/memory/status
curl -s localhost:8080/memory/graph
curl -s localhost:8080/audit/summary
```

Erwartung: `400` bei leerer Nachricht, `404` bei unbekanntem Modell/Session,
`415` bei falschem Content-Type, `200` mit sauberer JSON-Struktur sonst.
Fehler haben immer `status`, `error`, `details` — niemals einen Stacktrace im
HTTP-Body.

### Schritt 6 — Frontend prüfen

Browser auf `http://localhost:8080/` (bzw. die Vorschau-URL des Agenten).
Prüfen: Statusanzeige (API/Modell), Modellauswahl gefüllt, Chat sendet und
antwortet, `/graph` rendert. Fehlt ein Modell, muss die UI es als `(fehlt)`
zeigen — nicht abstürzen.

### Schritt 7 — Aufräumen

```bash
bash scripts/stop.sh
```

Beendet **nur** GUIALITA-Prozesse. Ollama läuft weiter.

### Schritt 8 — Dokumentieren

1. `docs/GUIALITA_STATE.yaml` — nur wenn sich ein **Status** ändert
   (z. B. `testing.test_functions_total`, `suite_inventory`, neue Baseline).
2. `docs/SESSION_LOG.md` — **immer**: Datum, Branch/Commit, Befehle, echte
   Zahlen (PASS/FAIL/NOT_EXECUTED/Skips), Umgebung, offene Punkte.
3. `docs/HEARTBEAT.md` — Ansicht nachziehen, falls STATE sich änderte.
4. Commit mit Begründung; bei frozen-Schichten **beide Testläufe** nennen.

### Schritt 9 — Session abschließen (nur mit ausdrücklicher Autorisierung)

Merge in `main` ist keine Routinehandlung. Voraussetzung ist eine **explizite**
Freigabe des Nutzers für PR und Merge; ohne sie endet die Arbeit am Commit auf
der Arbeits-Branch. Vor dem Merge:

```bash
git fetch origin --prune
git log --oneline HEAD..origin/main    # leer = nichts zu integrieren
.venv/bin/python scripts/run_all_tests.py   # frischer Lauf, 0 FAIL
git status --short                     # leer = keine Laufzeitdaten staged
```

Regeln für den Abschluss:

- Divergiertes `main` **vor** dem Merge integrieren und Konflikt-Ursachen
  benennen; keine Konflikte durch Überschreiben fremder Änderungen lösen.
- Nur die aktuelle Arbeits-Branch pushen, nie eine andere.
- `docs/INTEGRITY_MARKER.txt` und `docs/PHASE_*` sind historische Belege und
  bleiben unverändert — auch beim Archivieren.
- Offene Punkte (fehlende Runtime-Abnahme, offene Gates) im Abschluss-Eintrag
  wiederholen, damit sie nicht mit dem Merge als erledigt gelten.

---

## 4. Mock-Modus (`GUIALITA_MOCK_LLM=1`)

**Was er ist:** ein deterministischer Test-Adapter
(`backend/adapters/mock_adapter.py`, Modell `mock-1b` in `config/models.yaml`),
der den vollen Pfad *Session → Memory → Retrieval → ChatService → Adapter →
Persistenz → Audit → Export* prüfbar macht, **ohne** GGUF-Modelle, ohne
`llama-cpp-python` und ohne GPU. Antworten tragen den Marker `MOCK-LLM-OK`.

**Was er beweist:** API-Vertrag, Fehlersemantik (400/404/415/500), Session- und
Message-Persistenz, Memory-Indexierung/Retrieval/Graph, Audit-Metadaten ohne
Inhalte, Export, Frontend-Anbindung.

**Was er NICHT beweist — und niemals behaupten darf:**

- keine echte LLM-Antwortqualität, keine Inferenz, keine Latenz des Modells
- keine GPU/CUDA-Funktion, kein `llama-cpp-python`
- kein STT (whisper.cpp), kein TTS (LFM-Audio), kein Mikrofon
- `ready_for_voice_turn` bleibt im Mock-Modus zwingend `false`

**Dokumentationspflicht:** Ein Lauf mit Mock wird als `PASS (mock)` ausgewiesen.
In `docs/SESSION_LOG.md` muss stehen, dass die echte Runtime dabei **nicht**
nachgewiesen wurde. Der Mock ist Testinfrastruktur, kein Runtime-Ersatz und
keine neue Produktfähigkeit.

---

## 5. Fehlerdiagnose (erst prüfen, dann ändern)

| Symptom | Wahrscheinliche Ursache | Aktion |
|---|---|---|
| `Connection refused` auf 8080 | Backend läuft nicht | `bash scripts/start.sh`; `scripts/logs/backend.log` lesen |
| `llama-cpp-python ist nicht installiert` | native Abhängigkeit fehlt/baut nicht | `pip install llama-cpp-python`; für Tests `--mock` nutzen |
| `Modelldatei fehlt: …gguf` | Pfade nicht eingerichtet | `bash scripts/setup_local.sh`, dann `/diagnostics` prüfen |
| `${GUIALITA_…}` im Pfad | Platzhalter nicht aufgelöst | `.env` aus `.env.example` erzeugen; `backend/paths.py` nutzen |
| `CLI fehlt: whisper-cli` | whisper.cpp nicht gebaut/verlinkt | `GUIALITA_WHISPER_CLI` in `.env` setzen |
| `PortAudio library not found` | `sounddevice` ohne Systembibliothek | `libportaudio2` installieren; Suite bleibt `NOT_EXECUTED` |
| Ollama `Connection refused` | Shared Service läuft nicht | **nicht** selbst starten/stoppen — Nutzer informieren |
| Deprecation-/Syntaxwarnung | Code-Alterung | Beheben, aber nur mit Testnachweis (Freeze-Policy) |

---

## 6. Abnahmekriterien (Definition of Done)

Der Auftrag gilt als erfüllt, wenn **alle** Punkte mit Ausgabe belegt sind:

- [ ] `compileall` ohne Fehler
- [ ] `scripts/doctor.py` gelaufen; fehlende Modelle/Runtimes sind benannt
- [ ] Backend startet und `/health` liefert `api: online`
- [ ] `/diagnostics`: alle Pfade absolut, aufgelöst, mit `exists`
- [ ] `scripts/run_all_tests.py`: **0 FAIL**, Exit-Code 0
- [ ] Jede `NOT_EXECUTED`-Suite hat eine konkrete, maschinenbezogene Ursache
- [ ] Skips sind begründet und zählen nicht als bestanden
- [ ] API-Rauchprobe (Schritt 5) zeigt die erwarteten Statuscodes
- [ ] Audit-Log enthält **keine** Nachrichten- oder Audioinhalte
- [ ] `docs/SESSION_LOG.md` enthält Datum, Befehle, echte Zahlen, offene Punkte
- [ ] Ollama wurde nicht verändert; es läuft weiter
- [ ] Arbeitsbaum enthält keine Laufzeitdaten (`.db`, `.jsonl`, `.wav`, Logs)

---

## 7. Verboten für den Agenten

- `git push --force`, Branch-Wechsel, `git reset --hard`, Umbenennen/Löschen des Repo-Roots
- Ollama stoppen, starten, konfigurieren, Modelle daraus löschen
- Tests löschen, auskommentieren, `assert` entfernen, um grün zu werden
- `docs/GUIALITA_STATE.yaml` auf `PASS` setzen ohne Testlauf auf dieser Maschine
- Erfundene Ergebnisse, Pfade, Versionen oder Latenzen dokumentieren
- Modelldateien, WAVs, Datenbanken oder Logs committen
- Neue Produktfähigkeiten (Vision, Desktop, Audio-Streaming, Musik) einbauen
- Absolute Maschinenpfade in Code, Konfiguration oder Doku schreiben

---

## 8. Referenz

| Zweck | Befehl / Datei |
|---|---|
| Komplettes lokales Update + Test | `bash scripts/local_update.sh [--mock] [--keep-running] [--pull]` |
| Alle Suiten genau einmal | `python3 scripts/run_all_tests.py` (Report: `--yaml`) |
| Nur bestimmte Suite | `python3 scripts/run_all_tests.py --only api` |
| Unit-Schicht ohne Backend | `python3 scripts/test.py` |
| Umgebungs-Check | `python3 scripts/doctor.py` |
| Backend starten / stoppen | `bash scripts/start.sh [--restart]` / `bash scripts/stop.sh` |
| Latenzmessung Sprach-Turn | `python3 scripts/measure_voice_turn.py --record --turns 3` |
| Lokale Einrichtung (`.env`) | `bash scripts/setup_local.sh [--dry-run] [--hint PFAD]` |
| Kanonischer Status | `docs/GUIALITA_STATE.yaml` |
| Pfadauflösung | `backend/paths.py`, `.env.example` |
| Modellkonfiguration | `config/models.yaml` |
| STT-Entscheid | `docs/adr/ADR-001-stt-whisper-cpp.md` |
