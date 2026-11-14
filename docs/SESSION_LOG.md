# GUIALITA — Nachvollziehbarkeitsprotokoll

Dieses Protokoll dokumentiert kurz und sachlich Änderungen, Prüfungen und offene
Punkte. Es enthält bewusst keine internen Gedankengänge, sondern nur Entscheidungen,
Evidenz und Ergebnisse.

## 2026-08-22 — Setup und Voice-Pipeline

### Ausgangslage

- Branch: `arena/01a029c4-guialita`
- Ausgangscommit: `1d9bd437aff903f026acf6f4d836930409d9a09a`
- Repository war sauber.
- Dokumentierter Baseline-Stand: `GUIALITA-VOICE-ACTIVATION-V1-PASS`.
- Lokale Modelle und Runtime waren in dieser Sandbox nicht vorhanden.

### Analyse

- Python-Code kompilierte erfolgreich.
- Historische Dokumentation meldete abgeschlossene Phasen für Chat, Sessions,
  Memory, Graph, STT, TTS und Voice Activation.
- Die bestehende Route `/audio/chat` umging `ChatService` und verlor dadurch bei
  Audio-Anfragen Session-/Memory-Integration.
- Installation war durch absolute Pfade und fehlende Dependency-Datei schwer
  reproduzierbar.

### Änderungen

Commit: `8bb9500 Make voice pipeline session-aware and improve local setup`

- `/audio/chat` auf `ChatService` umgestellt.
- `session_id`, Memory Retrieval und Indexierung für Audio-Chat ergänzt.
- Base64-, WAV- und Größenvalidierung ergänzt.
- Leere Transkripte werden sauber behandelt.
- `AudioChatRequest` und erweiterte Antwortdaten ergänzt.
- TTS validiert Eingaben vor dem Verfügbarkeitscheck.
- `requirements.txt` hinzugefügt.
- Read-only-Diagnose `scripts/doctor.py` hinzugefügt.
- Start-/Stop-Skripte auf portable Projektpfade umgestellt.
- README auf den tatsächlichen Projektstand aktualisiert.

### Prüfungen

- `python3 -m compileall -q backend scripts tests`: PASS
- `git diff --check`: PASS
- Isolierte Store-/Audio-Tests: 15/15 PASS
- Vollständige Tests in der Sandbox nicht ausführbar: fehlende Python-Pakete,
  Backend, Modelle und lokale Audio-Runtimes.

### Offene Punkte

- Abhängigkeiten und lokale Modelle auf dem Zielrechner installieren.
- Vollständige Test-Suite gegen echte Runtime ausführen.
- Physischer Mikrofon-/Lautsprecher-Test für Voice Activation.
- Latenz reduzieren und Streaming prüfen.
- Dokumentations-Baselines vereinheitlichen.

## 2026-08-22 — Voice-Wiedergabe stabilisiert

- Temporäre WAV-Dateien der Voice-TTS-Wiedergabe werden jetzt garantiert in
  `finally` gelöscht, auch wenn Sounddevice oder WAV-Lesen fehlschlägt.
- Dadurch werden temporäre Dateien bei wiederholten Voice-Turns nicht mehr
  angesammelt.
- Python-Kompilierung und die isolierten 15 Store-/Audio-Tests bleiben PASS.

## 2026-08-22 — Robustheit für laufende lokale Installationen

- TTS-Verfügbarkeit wird nach einem fehlgeschlagenen Startcheck erneut geprüft,
  falls Modelle oder Runtime später bereitgestellt werden.
- Audio-Chat-Requests haben Größen-, Dauer- und Payload-Grenzen.
- Ungültige Audio-JSON-Requests behalten die bisherige HTTP-400-Semantik.

## 2026-08-22 — Portable Modellpfade

- Modell- und Whisper-Pfade unterstützen jetzt `~` und Umgebungsvariablen.
- `GUIALITA_WHISPER_CLI` kann den Whisper-Binary-Pfad ohne Codeänderung setzen.
- Relative Pfade werden weiterhin sicher relativ zum Repository aufgelöst.

## 2026-08-22 — Lokale Testumgebung eingerichtet

- Projekt-Venv `.venv` angelegt (ignoriert, nicht im Git).
- `requirements.txt` erfolgreich installiert.
- Contract- und reine Store-/Filename-Tests: PASS.
- Ausgewählte Integrations-/Audiotests wurden ausgeführt und korrekt als
  umgebungsabhängig sichtbar: Backend war nicht gestartet, `espeak-ng` fehlt,
  lokale Modelle und Whisper-/LFM-Runtimes fehlen.
- Ergebnis: `20 passed`, `20 failed` in diesem gemischten Lauf; die Fehler sind
  keine neuen Codefehler, sondern fehlende externe Voraussetzungen.

## 2026-08-22 — M4 Testharness

- `pytest.ini` mit Testkategorien und klarer Testkonfiguration ergänzt.
- `scripts/test.py` ergänzt: Standardlauf ist hardware- und serverfrei; `--live`
  aktiviert die externen Runtime-/Backend-Tests.
- Unit-Layer erfolgreich: **39 passed**.
- Vollständiger Live-Layer bleibt bis zur Verfügbarkeit von Backend, Modellen,
  Whisper, TTS und `espeak-ng` blockiert.

## 2026-08-22 — M5 Performance-Baseline

- `scripts/benchmark.py` ergänzt.
- Misst deterministische lokale Komponenten ohne Modell- oder Hardwarezugriff.
- Optional kann mit `--live` nur der Health-Endpunkt eines bereits laufenden
  Backends gemessen werden; Chat-Inferenz wird nicht ungefragt gestartet.
- Memory-Embedding-Baseline in der Sandbox: Median **0,02 ms**.
- Python-Kompilierung und `git diff --check`: PASS.

## 2026-08-22 — M5 Auditierbarkeit

- Technisches Audit-Modul `backend/audit.py` ergänzt.
- Erfolgreiche Text- und Audio-Turns werden mit Session, Modell, Laufzeiten und
  Runtime als JSONL protokolliert.
- Inhalte werden standardmäßig nicht gespeichert; explizites Opt-in ist über
  `GUIALITA_AUDIT_INCLUDE_CONTENT=1` möglich.
- Audit-Fehler blockieren niemals den Chat.
- Unit-Layer auf **41 passed** erweitert.

## 2026-08-22 — Session-Export und Audit-Abfrage

- `GET /sessions/{session_id}/export` ergänzt.
- Export enthält Session, vollständige Nachrichten und technische Audit-Events.
- `GET /audit/events` ergänzt, inklusive Session-Filter und Limit.
- Audit bleibt standardmäßig inhaltsfrei; der Session-Export enthält die
  Nachrichten ausdrücklich, weil er als Benutzerexport gedacht ist.
- Audit-Filtertest ergänzt; Unit-Layer: **42 passed**.

## 2026-08-22 — Lesbarer Session-Export

- `GET /sessions/{session_id}/export.md` ergänzt.
- Export enthält Gesprächsverlauf und technische Ereignisse als herunterladbare
  Markdown-Datei.
- Routenprüfung, Kompilierung und 42-Tests-Lauf: PASS.

## 2026-08-22 — Single Source of Truth

- `docs/GUIALITA_STATE.yaml` als einzige verbindliche Statusquelle festgelegt.
- `GUIALITA_PHASE_STATUS.md` und `HEARTBEAT.md` sind ausdrücklich Ansichten.
- `SESSION_LOG.md` bleibt chronologische Evidenz, nicht der aktuelle Zustand.
- State-Datei auf M5 Audit/Export und den laufenden Performance-Milestone
  aktualisiert.
- Der bisherige widersprüchliche Hard-Stop-Status wurde auf die aktuelle
  explizite Weiterarbeitsfreigabe angepasst.

## 2026-08-22 — Audit-Performance-Zusammenfassung

- `GET /audit/summary` ergänzt.
- Aggregiert Ereignisanzahl, Erfolge, Fehler und mittlere STT-/Chat-/Gesamtzeiten.
- Summary-Test ergänzt; Unit-Layer auf **43 passed** erweitert.

## 2026-08-22 — Mock-End-to-End-Pipeline

- `tests/test_chat_service.py` ergänzt.
- Fake-LLM testet den vollständigen ChatService-Flow ohne Modelle:
  Session-Erzeugung, Nachrichtenpersistenz, History-Weitergabe und Session-
  Validierung.
- Unit-Layer nach Installation der lokalen Venv: **46 passed**.

## 2026-08-22 — Statusdokumentation synchronisiert

- `GUIALITA_PHASE_STATUS.md` als reine Ansicht neu aufgebaut.
- Kanonischer State auf den tatsächlich implementierten Phase-1C-Batch-Flow
  aktualisiert: Voice → STT → Chat → TTS = PASS.
- Vision und Desktop-Control bleiben ausdrücklich nicht kanonisch aktiviert.
- M4/M5 und die verbleibenden Hardware-/Runtime-Blocker sind jetzt einheitlich
  ausgewiesen.

## 2026-11-13 — ADR-002: Agenten-Orchestrierung (Entwurf, historisch)

### Ziel

Architekturentscheidung für die geplante MUSCAL-Orchestrierungsschicht
festhalten, bevor Code entsteht. Dieser Eintrag beschreibt den Stand **vor**
P1/P2 und vor den P3–P6-Werkzeugen; die Fortschreibung steht unten.

### Änderungen

- `docs/adr/ADR-002-agent-orchestration.md` neu angelegt, Status **PROPOSED**.
- Keine Codeänderung, keine Änderung an `GUIALITA_STATE.yaml`, keine
  Aufhebung von `prohibitions`.

### Befunde

- Zum Entwurfszeitpunkt war MUSCAL `future_target: PLANNED`; Laden, Wechseln,
  Trainieren und Benchmark-Orchestrierung existierten noch nicht.
- `testing.ci_note` nennt „sieben von neun" Suiten mit Voraussetzungen,
  `known_risks` nennt „8 von 9". Die Voraussetzungstabelle in
  `REGRESSION_CONTRACT.md` belegt **8 von 9**; die `ci_note` ist falsch.
- `scripts/benchmark.py` misst ausschließlich `memory.embed` und optional
  `GET /health`; keine Turn-, Wechsel- oder Modellvergleichsmessung.

### Entscheidungen im Entwurf

D1 Eval-Harness vor Orchestrierung · D2 Rollen als Konfiguration, kein LoRA
als Rollenidentität · D3 Lifecycle mit VRAM-Budget, Wechsel als Kostenstelle ·
D4 MUSCAL beginnt als CLI/HTTP · D5 Verifikation lokal, Cloud nur für Code ·
D6 Prozessisolation · D7 SSOT-Zahlen vorher konsolidieren.

### Offen zum Zeitpunkt des Entwurfs

- Freigabe für P3–P6 (neue Schichten) stand aus. Die CLI/HTTP-Werkzeuge wurden
  später als Selbsttests umgesetzt; `prohibitions`, `hard_stop` und
  `next_authorized_phase` blieben unverändert (siehe Eintrag „P3–P6 umgesetzt").
- P0 (`voice_forensics_v1` nachmessen) und P1 (SSOT-Zahlen) waren ohne neue
  Freigabe möglich.

## 2026-11-13 — P1/P2 umgesetzt: Inventar korrigiert, Benchmark pro Stufe

### Ziel

Die in ADR-002 als freigabefrei markierten Schritte umsetzen: Zahlen der SSOT
gegen die Realität abgleichen (P1) und den Benchmark von einer Alibi-Messung zu
einer Stufenmessung machen (P2).

### Änderungen

- `scripts/run_all_tests.py`
  - `count_test_functions` zählt per `ast` statt per Regex `\s+def test`.
  - `test_audit.py`, `test_chat_service.py`, `test_audio_contract.py` sind in
    `SUITES` aufgenommen; sie standen in der SSOT, liefen aber nie.
  - neue Fähigkeit `deps` (pydantic/fastapi importierbar).
  - neuer Befehl `--check-state`: gleicht Runner-Inventar gegen
    `docs/GUIALITA_STATE.yaml` ab, Exitcode 1 bei Abweichung.
- `scripts/benchmark.py` neu geschrieben: Stufen getrennt (Embedding, Chat,
  TTS, STT/Turn aus dem Audit-Log), Perzentile, `--compare`, `--json`.
  Fehlende Messungen erscheinen als `—`, nicht als 0 ms.
- `tests/test_benchmark.py` neu (10 Tests, reine Standardbibliothek).
- `.github/workflows/state-consistency.yml` neu: CI-Abgleich Inventar ↔ SSOT,
  ohne Backend, GPU oder Modelle.
- `docs/GUIALITA_STATE.yaml`: `testing`-Block ersetzt (177 Funktionen,
  13 Suiten, Ursachen der Korrektur, `suite_inventory` konsolidiert),
  `known_risks` und `ci_note` korrigiert, `meta.updated` gesetzt.
- `docs/BASELINES/REGRESSION_CONTRACT.md`: Tabelle und Summe korrigiert,
  Korrekturabschnitt 2026-11-13 ergänzt, alte 141 als überholt markiert.
- `docs/adr/ADR-002-agent-orchestration.md`: Abschnitt „Umsetzungsstand".

### Befunde

- Die Zahl 141 war falsch. Ursachen: (a) der Zähler erfasste nur eingerückte
  TestCase-Methoden, `test_process_audio.py` meldete 5 statt 14,
  `test_capture.py` 0 statt 6; (b) drei Suiten des Hauptzweigs standen nicht
  in der Runner-Liste und liefen nie.
- Zwischenstand nach diesem Eintrag: **177 Testfunktionen in 13 Suiten**.
- `ci_note` sagte „sieben von neun", `known_risks` „8 von 9" — beide falsch;
  zutreffend waren damals **8 von 13**, heute **8 von 19** Suiten mit
  Laufzeitvoraussetzung (Fortschreibung unten).

### Läufe (Sandbox, ohne Modelle, GPU, Mikrofon)

- `python3 scripts/run_all_tests.py --check-state` → „Keine Abweichung", RC 0
- `python3 scripts/run_all_tests.py` → 1 PASS (`test_benchmark.py` 10/10),
  12 NOT EXECUTED, 0 FAIL. Kein FAIL durch fehlende Python-Pakete mehr.
- `python3 tests/test_benchmark.py` → 10 Tests, OK
- `python3 scripts/benchmark.py` → lokale Messung nicht möglich (numpy fehlt
  in der Sandbox), sauber ausgewiesen statt als 0 ms
- `python3 scripts/benchmark.py --live` → RC 2, „nicht durchgeführt"

### Offen zum Zeitpunkt des Eintrags

- **P0** — Nachmessung der Sprachlatenz auf der Referenzmaschine. In dieser
  Umgebung nicht durchführbar (keine GPU, kein Mikrofon, keine Modelle).
- **P3–P6** — Eval-Harness, Lifecycle-Manager, Rollen-Registry und MUSCAL-CLI
  waren zu diesem Zeitpunkt noch nicht umgesetzt. Fortgeschrieben im nächsten
  Eintrag. `prohibitions` blieben unverändert.

## 2026-11-13 — P3–P6 umgesetzt: Eval, Lifecycle, Rollen, MUSCAL CLI/HTTP

### Ziel

Die ADR-002-Werkzeuge so weit liefern, wie es ohne GPU, Backend, Mikrofon und
Modelle beweisbar ist — ohne eine Hardware-Abnahme zu behaupten und ohne die
`prohibitions` oder `current.hard_stop` anzutasten.

### Änderungen

- `config/roles.json` (maschinelle Quelle) und generiertes
  `config/roles.yaml` (ADR-002 D2) mit vier Rollen; `evals/roles/*.json` mit
  vier Rollen-Suiten; `evals/golden.json` generiert. Generatoren:
  `scripts/build_golden.py`, `scripts/build_roles.py`.
- `scripts/eval.py`: Golden Set, Grader inklusive `min_list_len`, `--dry-run`,
  `--live --model`, `--compare`, p50/p95, Ressourcen-Snapshot mit expliziter
  „nicht gemessen"-Markierung.
- `config/model_budget.json` und `scripts/modelsctl.py`: dreivertiges
  VRAM-Urteil (`fits`/`too_big`/`unknown`), `budget`, `plan`, `status`,
  `health`, `switch`, `load`, `start`, `stop`, `unload`. Prozesse werden nur an
  `start.sh`/`stop.sh` delegiert; Ollama bleibt unangetastet.
- `scripts/roles.py`: Registry-Validierung, JSON↔YAML-Abgleich, Rollenwechsel
  `router → planner` ohne Modellwechsel. Invariante: Auditor hat kein
  Schreibrecht, mutierende Tools brauchen `requires_approval`.
- `scripts/muscal.py`: sequenzielle Kette als CLI und HTTP (`serve`), Audit-Log,
  STOP-Datei, Schrittgrenze, Staging-Guard, Schema-Prüfung pro Rolle. Kein
  Desktop-Adapter, keine parallelen Agenten, keine Cloud-Inferenz.
- `scripts/check_docs.py`: prüft aktuelle Zahlen, Grenzen und generierte
  Artefakte über SSOT, Regression Contract, Bootstrap, ADR, dieses Protokoll
  und den CI-Workflow hinweg.
- Sechs neue Testsuiten (`test_eval.py`, `test_modelsctl.py`, `test_roles.py`,
  `test_muscal.py`, `test_muscal_http.py`, `test_doc_consistency.py`) mit
  zusammen 130 Testfunktionen, alle ohne Backend und ohne Drittpakete.
- `scripts/run_all_tests.py`, `docs/GUIALITA_STATE.yaml`,
  `docs/BASELINES/REGRESSION_CONTRACT.md`, `docs/GUIALITA_SESSION_BOOTSTRAP.md`,
  `docs/adr/ADR-002-agent-orchestration.md`, `.gitignore`,
  `.github/workflows/state-consistency.yml` und `README.md` nachgezogen.

### Prüfungen (Sandbox, ohne Hardware)

```text
python3 scripts/eval.py --dry-run                 → 19 Aufgaben, alle Urteile wie erwartet
python3 scripts/eval.py --dry-run --all-suites    → 4 Rollen-Suiten OK
python3 scripts/build_golden.py --check           → OK
python3 scripts/build_roles.py --check            → OK
python3 scripts/roles.py validate --check-mirror  → OK
python3 scripts/modelsctl.py budget              → UNKNOWN bleibt UNKNOWN, RC 0
python3 scripts/muscal.py run "..." --dry-run     → Kette ok, RC 0
python3 scripts/muscal.py serve (Thread-Test)     → /health, /pipelines, /guard, POST /run OK
python3 scripts/check_docs.py                    → OK
python3 scripts/run_all_tests.py --check-state    → Keine Abweichung, RC 0
python3 scripts/run_all_tests.py                  → 7 PASS, 12 NOT EXECUTED, 0 FAIL
```

### Befunde

- Zum Zeitpunkt des Eintrags verbindlich: **307 Testfunktionen in 19 Suiten**; `--check-state`
  gleicht Runner und SSOT maschinell ab.
- Acht Suiten brauchen weiterhin Backend, Modelle, GPU, Mikrofon oder
  espeak-ng; vier weitere brauchen nur die Python-Abhängigkeiten. Ohne diese
  Pakete meldet der vollständige Sandbox-Lauf 7 PASS, 12 NOT EXECUTED, 0 FAIL.
  Kein Test aus einer NOT-EXECUTED-Suite wurde als bestanden gezählt.
- `evals/golden.json` und `config/roles.yaml` sind generiert; ihre Quellen
  können nicht mehr unbemerkt auseinanderlaufen.
- MUSCAL bleibt CLI/HTTP, kein Desktop-Adapter. `prohibitions`,
  `current.hard_stop: true` und `next_authorized_phase: NONE` sind unverändert.

### Offen

- **P0** — Voice-Turn-Nachmessung auf der Referenzmaschine.
- **Live-Abnahme** — `eval.py --live/--compare`, `modelsctl.py
  switch/start/stop`, `muscal.py --live`, HTTP ohne `dry_run`, echte
  VRAM-Belegung und alle GPU-Latenzen. Implementiert, aber ohne Hardware
  nicht gemessen.

## 2026-11-13 — Abschluss-Sweep: Historie wiederhergestellt, Dokumentenabdeckung erweitert

### Ausgangslage

Zu Beginn dieses Arbeitsabschnitts zeigte der lokale Zweig nur den
Basis-Commit `4b3762b`, obwohl `origin/arena/f82209dd-guialita` bereits auf
`12afaed` stand. Alle Dateiänderungen lagen als Arbeitsbaum vor.

### Prüfung statt Überschreiben

- `git fetch origin arena/f82209dd-guialita` → `FETCH_HEAD = 12afaed`.
- `git add -A && git write-tree` → `7536723c10d4e7f739e85b7b45a42b5832d495ce`.
- `git rev-parse FETCH_HEAD^{tree}` → derselbe Hash. **Der Arbeitsbaum war
  bitgleich mit dem gepushten Commit.** Erst danach wurde der lokale Zweig per
  `git reset --hard FETCH_HEAD` wieder auf `12afaed` gesetzt und das Tracking
  auf `origin/arena/f82209dd-guialita` gestellt. Keine Datei ging verloren.

### Änderungen

- `scripts/check_docs.py` prüft jetzt **13** aktuelle Dokumente statt 7:
  zusätzlich `README.md`, `docs/SINGLE_SOURCE_OF_TRUTH.md`,
  `docs/GUIALITA_PHASE_STATUS.md`, `docs/LFM25_AUDIO_AUDIT.md`,
  `docs/LFM25_AUDIO_AUDIT_V2.md` und `PROTOTYPEN/README.md`. Für jedes sind
  Pflichtformulierungen hinterlegt; die alte README-Testvoraussetzung und die
  alte Phasenplan-Überschrift werden als veraltete Aktualitätsbehauptungen
  abgelehnt (Muster stehen in `scripts/check_docs.py`).
- `docs/LFM25_AUDIO_AUDIT.md` und `..._V2.md` haben einen Kopf
  „Historischer Beleg (2026-08-19)". Ihre Aussagen „NICHT IMPLEMENTIERT"
  bleiben unverändert und sind jetzt zeitlich eingeordnet — keine stillschweigende
  Korrektur forensischer Berichte.
- `config/roles.json`: Coder-Prompt „unrelated Stellen" → „unbeteiligter
  Stellen"; `config/roles.yaml` neu generiert.
- `docs/adr/ADR-002-agent-orchestration.md`: Umbruch und Anführungszeichen im
  Umsetzungsstand korrigiert.
- `tests/test_doc_consistency.py`: bestehende fünf Tests prüfen die neue
  Abdeckung mit, ohne die Gesamtzahl zu verändern.

### Läufe (Sandbox)

```text
python3 -m compileall -q backend scripts tests        → RC 0
python3 scripts/run_all_tests.py --check-state         → Keine Abweichung (307/19)
python3 scripts/check_docs.py                         → OK, 13 Dokumente
python3 scripts/build_golden.py --check                → OK
python3 scripts/build_roles.py --check                 → OK
python3 scripts/roles.py validate --check-mirror       → OK
python3 scripts/eval.py --dry-run                     → 19/19 Urteile wie erwartet
python3 scripts/eval.py --dry-run --all-suites         → 4/4 OK
python3 scripts/run_all_tests.py --only <7 Suiten>    → 7 PASS, 0 FAIL
python3 scripts/muscal.py serve --host 0.0.0.0 --port 8099 (Live Preview):
  GET  /health          → 200 {"status":"ok","backend":"stub"}
  GET  /pipelines       → 200, 4 Rollen, 2 Ketten
  GET  /guard?path=/etc/passwd → 200 {"allowed":false,...}
  POST /run             → 200, ['ok','ok','ok','ok'], warnings []
  POST /run ohne task   → 400 {"error":"Feld 'task' fehlt oder ist leer"}
```

### Offen

Unverändert: P0, alle Live-/GPU-Messungen, `current.hard_stop: true`,
`next_authorized_phase: NONE`, `prohibitions`. Die Live Preview nutzt den
Stub und ist **kein** Modellnachweis.

## 2026-11-13 — Live-Contract gegen das echte Backend-Schema geprüft

### Ausgangslage

Die Live-Pfade von `eval.py`, `modelsctl.py` und `muscal.py` waren bisher nur
kompiliert und im Trockenlauf geprüft. Ohne Backend blieb unbelegt, ob ihre
Requests und Response-Parser zum tatsächlichen Vertrag in
`backend/models/schemas.py` und `backend/manager.py` passen.

### Prüfung des Vertrags

- `ChatRequest` verlangt nur `message`; `model` und `session_id` sind optional.
  Alle drei Clients senden genau diese Form — kein 422-Risiko.
- `ChatResponse` liefert `status`, `response`, `model`, `latency_ms`. Die Clients
  lesen `response` und `latency_ms`; `ErrorResponse` trägt `status: "error"`.
- `GET /models` liefert `available` = **Datei vorhanden**, nicht „im VRAM
  geladen". `modelsctl.py` behauptete an zwei Stellen einen Ladezustand. Fix:
  `--loaded A,B` für `plan`/`switch`, sonst ausdrücklich „UNBEKANNT" mit
  genannter Annahme; `status` weist auf die Bedeutung von `available` hin.
- `modelsctl.py start` meldete Erfolg, sobald `/health` antwortete — auch bei
  `primary_runtime.status: offline`. Jetzt Exitcode 1 mit klarer Begründung.
- `eval.py` und `muscal.py` behandelten eine 200-Antwort mit `status: "error"`
  als leere Modellantwort. Beide werfen jetzt einen benannten Fehler.

### Neuer Selbsttest

`scripts/contract_check.py` startet ein Fake-Backend auf `127.0.0.1:0`, das
`/health`, `/models` und `POST /chat` mit den echten Feldern bedient. Geprüft
werden Request-Aufbau, Rollenprompt, `--model`-Override, `eval.run_live`,
`muscal.run_pipeline`, `modelsctl status/health/plan/switch`, Fehlerantworten,
404 bei unbekanntem Modell und die offline-Runtime bei `start`.

```text
python3 scripts/contract_check.py → OK, RC 0
  ChatRequest/ChatResponse, /health, /models, /chat
  Clients: eval.py, modelsctl.py, muscal.py
  Fake-Modelle: granite-3b, granite-8b, lfm-vision-3b
```

Die Werte des Fake-Backends (`latency_ms: 12.5`) sind synthetisch. Der Lauf
belegt die **Vertragsform**, keine Inferenz, keine VRAM-Belegung, keine echte
Wechselzeit.

### Weitere Prüfungen

```text
python3 -m compileall -q backend scripts tests        → RC 0
python3 scripts/run_all_tests.py --check-state         → Keine Abweichung (307/19)
python3 scripts/check_docs.py                         → OK, 13 Dokumente
python3 scripts/build_golden.py --check                → OK
python3 scripts/build_roles.py --check                 → OK
python3 scripts/roles.py validate --check-mirror       → OK
python3 scripts/eval.py --dry-run                     → 19/19
python3 scripts/run_all_tests.py --only <7 Suiten>    → 7 PASS, 0 FAIL
```

Die drei betroffenen Testsuiten wurden um Zusatzsprüche erweitert, **ohne neue
Testfunktionen**: 25/33/26 Tests, Gesamtzahl blieb 307/19.

### Offen

Unverändert: P0, Live-Inferenz, echte VRAM-/Latenzmessung,
`current.hard_stop: true`, `next_authorized_phase: NONE`, `prohibitions`.

## Externe CI-Gegenprobe und `main`-Abgleich (2026-11-13)

Ziel: nach dem lokalen Abschluss nicht erneut Zahlen behaupten, sondern den
Remote-Zustand und die Integrationsfähigkeit prüfen. Keine Codeänderung an den
Werkzeugen.

### Evidenz

```text
gh run view 43621040654                       → completed / success, event push
  Job „Inventar, Werkzeuge ↔ SSOT"           → 16/16 Schritte success,
  davon 10 Prüfschritte (u. a. Standardbibliothek-Suiten, Golden Set,
  Rollen-YAML, Registry, Eval, VRAM-Budget, MUSCAL-Trockenlauf,
  Live-Contract, check_docs.py), 6 Setup-/Post-/Abschlussschritte
gh run list --branch arena/f82209dd-guialita → 6 × success (Snapshot)
  43408033608 (7b6ca86), 43425145999 (12afaed),
  43618536071 (03c0522), 43621040654 (9b0e498),
  43622338506 (005755b), 43622915315 (56e3597)
gh pr list --state all                       → kein PR für diesen Branch
gh api .../workflows/state-consistency.yml   → State Consistency | active
```

### Befund: `main` ist nicht mehr die Basis

`git fetch origin main` liefert `7caea0e` (Merge PR #4). Seit `4b3762b` sind
dort fünf Commits mit Mock-Test-Adapter, `scripts/local_update.sh` und
`AGENTS.md` dazugekommen. Deren SSOT nennt **145 Testfunktionen in 9 Suiten**;
`tests/test_api.py` hat dort 27 statt 23 Testfunktionen.

```text
git merge-base HEAD FETCH_HEAD               → 4b3762b
git merge-tree --write-tree HEAD FETCH_HEAD  → RC 1, 4 Konflikte
  README.md, docs/GUIALITA_STATE.yaml,
  docs/HEARTBEAT.md, docs/SESSION_LOG.md
Auto-Merging (beidseitig geändert): .gitignore, scripts/run_all_tests.py
```

Ein Merge ergäbe rechnerisch **311 Testfunktionen in 19 Suiten** — also weder
307/19 noch 145/9. Ohne gemeinsame Neubaseline wäre `--check-state` danach
nicht mehr belastbar. Details und Fahrplan: `docs/INTEGRATION_STATUS.md`.

### Fortschreibung nach Freigabe

Dieser Befund blieb als Ausgangslage stehen. Nach ausdrücklicher Freigabe
wurde `origin/main@7caea0e` in diesen Branch integriert; siehe den Eintrag
„Integration von `origin/main`" weiter unten. `current.hard_stop: true`,
`next_authorized_phase: NONE` und `prohibitions` blieben unverändert. Die
externen CI-Läufe belegen nur diesen Branch — keine Inferenz, kein VRAM,
keine Hardware- oder Modellabnahme.

---

## Historische Belege aus `main` (Sessions `arena/ba3bbc69` und `arena/180fbd4a`)

Die folgenden Abschnitte stammen aus `origin/main@7caea0e`. Ihre Zahlen
(145 Testfunktionen in 9 Suiten, 6 PASS / 3 NOT_EXECUTED, `test_api.py`
23 → 27) beschreiben den Stand jener Session und sind **kein aktueller
Status**. Maßgeblich ist `docs/GUIALITA_STATE.yaml` mit **311 Testfunktionen
in 19 Suiten**.

## 2026-11-13 — Lokales Update + Verifikation (Mock-Adapter, local_update.sh, AGENTS.md)

**Auftrag:** komplettes lokales Update über einen OpenCode-Anweisungsprompt, so
dass alles lokal getestet ist und läuft.

**Branch/Commit:** `arena/ba3bbc69-guialita`, Basis `4b3762b`.
**Umgebung dieses Laufs:** Sandbox ohne GPU, ohne GGUF-Modelle, ohne
whisper.cpp, ohne `llama-liquid-audio-cli`, ohne PortAudio, ohne `espeak-ng`;
Python 3.11.2, `.venv` mit fastapi/uvicorn/pydantic/httpx/PyYAML/numpy/pytest/
sounddevice. `llama-cpp-python` nicht installiert. Ollama nicht erreichbar
(SHARED SERVICE, unverändert gelassen).

### Änderungen

- **`backend/adapters/mock_adapter.py` (neu):** deterministischer Test-Adapter
  ohne Modell/GPU, Antwortmarker `MOCK-LLM-OK`. Aktivierung über
  `GUIALITA_MOCK_LLM=1` oder Modell `mock-1b` (`adapter: mock` in
  `config/models.yaml`). Kein Runtime-Ersatz, keine Produktfähigkeit.
- **`backend/manager.py`:** Mock-Adapter eingebunden; Mock-Modelle brauchen
  keine Datei und sind immer `available`; `/health` meldet `mock_runtime`,
  `/diagnostics` meldet `mock_llm_enabled`. Modulweit gecachtes `BASE_DIR`
  entfernt, damit `GUIALITA_ROOT` zur Laufzeit wirkt.
- **`backend/main.py`:** deprecatedes `@app.on_event("shutdown")` durch
  `lifespan`-Handler ersetzt (sauberes Schließen von Manager/Store, Start-Log
  mit Host/Port/Mock-Status). `capabilities.llm_mock` wird nur **zusätzlich**
  gemeldet — `llm` bleibt ohne echte Runtime `false`, `ready_for_voice_turn`
  damit korrekt `false`.
- **`backend/audit.py`:** Audit-Pfad wird jetzt über `GUIALITA_DATA_ROOT`
  aufgelöst statt hart auf `<repo>/data/audit.jsonl`. `GUIALITA_AUDIT_PATH`
  hat weiterhin Vorrang. Damit landen Laufzeitdaten nicht mehr versehentlich im
  Repository (`.gitignore` um `data/*.jsonl`, `data/exports/` ergänzt).
- **`backend/chat_service.py` (frozen-Schicht `memory_session`, Freeze-v2-
  Nachweis siehe unten):** `status()` meldete `embedding_version: 512` —
  das war die Dimension, nicht die Version. Korrigiert auf `EMBEDDING_VERSION`
  (= 1), Dimension zusätzlich als `embedding_dimensions`; `enabled` folgt jetzt
  `config/memory.yaml` statt fest `True`; `database_available` wird geprüft
  statt behauptet.
- **`tests/test_api.py`:** 4 neue Mock-Tests (Flag-Report, voller Chat-Loop mit
  Persistenzprüfung, Determinismus, Export ohne Inhalts-Leakage) und ein
  Diagnose-Test auf Mock-Modelle erweitert. Runtime-abhängige Tests
  (`test_granite_model_available`, `test_real_lfm_response`, `test_stt_online`,
  `test_valid_wav_transcribes`, `test_audio_chat_full_pipeline`) überspringen
  sich mit Begründung, wenn `/diagnostics` die Fähigkeit als fehlend meldet.
  **Kein Test wurde gelöscht oder abgeschwächt:** Auf einer Maschine mit
  Modell/whisper.cpp laufen alle unverändert; der Skip greift nur, wo der Test
  sonst zwangsläufig fehlschlägt. Testzahl 23 → 27.
- **`scripts/run_all_tests.py`:** neue Fähigkeit `mock`, Voraussetzung `llm`
  gilt als erfüllt durch echte Runtime **oder** Mock; solche Läufe werden als
  `PASS (mock)` gekennzeichnet, Skips getrennt gezählt und im Report
  (`suites_via_mock_adapter`, `tests_skipped_graded`) ausgewiesen. Die
  Mock-Kennzeichnung ist bewusst eng gebunden (Mock aktiv **und** Suite gewertet
  **und** echte Voraussetzung fehlt) — ein erster Entwurf kennzeichnete auch
  Läufe ohne Mock, das ist korrigiert.
- **`tests/test_capture.py` (Defektreparatur):** `reset_inbox()` leerte
  `audio/inbox/` vollständig und löschte damit bei jedem Lauf die versionierte
  Beispieldatei `audio/inbox/audio_20260819_141715_001.json` — auch dann, wenn
  die Suite mangels Mikrofon/`espeak-ng` gar nicht ausgewertet wurde. Jetzt
  werden ausschließlich `*.wav` entfernt (alle Auswertungen der Suite zählen
  nur WAVs). Nachweis: Suite läuft, Fixture bleibt, `git status audio/` leer.
- **`scripts/local_update.sh` (neu):** ein Kommando für venv → Abhängigkeiten →
  `compileall` → `doctor.py` → Backend-Start → `/health`-Warte →
  `run_all_tests.py` → Unit-Schicht → sauberes Beenden → Fazit. Optionen
  `--mock`, `--no-install`, `--keep-running`, `--pull`. Native optionale
  Pakete (`llama-cpp-python`, `sounddevice`) schlagen nicht mehr den ganzen
  Lauf fehl.
- **`AGENTS.md` (neu):** verbindlicher OpenCode-Anweisungsprompt — Regeln
  (Ollama SHARED, kein Runtime-Austausch, `NOT_EXECUTED ≠ PASS`, Freeze v2,
  keine Pfad-Hardcodierung), 8-Schritte-Ablauf, erwartete Test-Matrix,
  Mock-Grenzen, Fehlerdiagnose, Definition of Done, Verbotsliste.
- **`README.md` / `.env.example`:** Schnellstart über `local_update.sh`,
  Testklassifizierung und Mock-Modus dokumentiert; `GUIALITA_MOCK_LLM`,
  `GUIALITA_AUDIT_PATH`, `GUIALITA_AUDIT_INCLUDE_CONTENT` ergänzt.

### Evidenz — Freeze-Policy v2 (Schicht `memory_session`)

Beide Läufe mit laufendem Backend und `GUIALITA_MOCK_LLM=1`, je Suite genau ein
Lauf:

| Suite | VORHER (chat_service.py = `4b3762b`) | NACHHER (korrigiert) |
|---|---|---|
| `test_memory.py` | `Ran 16 … OK` | `Ran 16 … OK` |
| `test_memory_retrieval.py` | `Ran 17 … OK (skipped=4)` | `Ran 17 … OK (skipped=4)` |
| `test_memory_graph.py` | `Ran 14 … OK (skipped=2)` | `Ran 14 … OK (skipped=2)` |

Bedingungen 1 und 2 erfüllt (grüner Lauf vorher, grüner Lauf nachher, Testzahl
unverändert); Bedingung 3 erfüllt durch diesen Eintrag und die Commit-Message.

### Evidenz — Testlauf `bash scripts/local_update.sh --mock --no-install`

```
Fähigkeiten: backend=ja  llm=nein  mock=ja  tts=nein  stt=nein
             mikrofon=nein  espeak=nein  lfm-audio-runtime=nein
ready_for_voice_turn: False   fehlend: llm, stt, tts

test_voice_activation.py    PASS           37/37
test_memory.py              PASS (mock)    16/16
test_memory_retrieval.py    PASS (mock)    13/17 (4 skip)
test_memory_graph.py        PASS (mock)    12/14 (2 skip)
test_graph_visualization.py PASS            8/13 (5 skip)
test_api.py                 PASS (mock)    22/27 (5 skip)
test_tts.py                 NOT EXECUTED   fehlt: TTS-Runtime
test_capture.py             NOT EXECUTED   fehlt: Mikrofon/PortAudio, espeak-ng
test_process_audio.py       NOT EXECUTED   fehlt: LFM-Audio-Runtime, espeak-ng

Suiten PASS 6 | FAIL 0 | NOT EXECUTED 3
Testfunktionen 145 | bewertbar ausgeführt 124 | bestanden 108 |
fehlgeschlagen 0 | übersprungen 16
Unit-Schicht scripts/test.py: UNIT PASS (46 Tests)
Exit-Code 0
```

Ohne Mock (kein Modell, kein `llama-cpp-python`) bleiben `test_memory`,
`test_memory_retrieval`, `test_memory_graph` und `test_api` `NOT_EXECUTED`;
das ist Umgebung, kein Codefehler.

### Evidenz — API-Rauchprobe (Backend mit Mock, Port 8080)

- `GET /health` → `api: online`, `default_model: granite-3b`,
  `primary_runtime.status: offline`, `mock_runtime.status: online`, `latency_ms`
- `GET /models` → 7 Modelle, `mock-1b` als einziges `available` (ohne GGUF)
- `GET /diagnostics` → Pfade absolut und aufgelöst, `exists` je Modell,
  `missing_capabilities: [llm, stt, tts]`, `ready_for_voice_turn: false`
- `POST /chat` leer → `400 empty_message`; unbekanntes Modell → `404
  unknown_model` mit Modellliste; ohne Modell im Mock-Modus → `200` mit
  `runtime: mock`, `session_id`, `message_id`, `retrieval`
- `POST /memory/search` leer → `400`; `POST /audio/transcribe` mit
  `application/json` → `415`; `POST /audio/tts` leer → `400`;
  `POST /audio/chat` mit ungültigem JSON → `400 invalid_json`
- `POST /sessions` → `SES-…`; `GET /sessions/{id}/messages` → 2 Nachrichten
  nach einem Chat; `GET /sessions/{id}/export` und `.md` → Session + Verlauf +
  technische Ereignisse
- `GET /memory/status` → `enabled: true`, `embedding_version: 1`,
  `embedding_dimensions: 512`, `database_available: true`
- `GET /memory/graph` → 6 Entitäten, 13 Relationen nach zwei Mock-Chats;
  unbekannte Entität → `404 unknown_entity`
- `GET /audit/summary` und `/audit/events` → nur Metadaten (`event`, `status`,
  `model`, `latency_ms`, `session_id`); keine `response`/`transcript`/`content`
- `GET /` und `/graph` → `200 text/html`
- Shutdown-Log: `GUIALITA Backend sauber beendet`, keine
  `on_event`-Deprecation-Warning mehr

### Offene Punkte

- Echte Runtime-Abnahme (LLM-Inferenz, whisper.cpp-STT, LFM-Audio-TTS,
  Mikrofon, `espeak-ng`) steht auf dieser Maschine weiter aus: 3 Suiten
  `NOT_EXECUTED`, 16 Tests `skip`.
- Gate `voice_forensics_v1` bleibt `OPEN`; die Neuvermessung des Sprach-Turns
  (`scripts/measure_voice_turn.py --record --turns 3`) ist weiter ausstehend und
  braucht die Zielhardware.
- `llama-cpp-python` wurde in dieser Umgebung nicht gebaut; der CUDA-Nachweis
  der Referenzmaschine bleibt unverändert gültig und wurde hier nicht berührt.

## 2026-11-13 — Umgebungs-Wiederherstellung, main-Abgleich und Session-Abschluss

**Auftrag:** aktuelles `main` ziehen, alles Konflikt-frei anpassen, Session
schließen und archivieren. Autorisierung durch den Nutzer für Commit, Push,
PR und Merge.

### Befund: verlorene Umgebung, zurückgesetzter Branch-Zeiger

Zwischen den Arbeitsabschnitten waren die gitignored-Pfade `.venv/`, `data/`
und `scripts/logs/` nicht mehr vorhanden, Port 8080 war frei und `python3`
hatte kein `fastapi`. Zusätzlich stand der lokale Branch-Zeiger wieder auf der
Basis `4b3762b`, der Commit `5e68392` war lokal kein gültiges Objekt mehr
(`fatal: Not a valid object name`), lag aber unverändert auf dem Remote:

```
git ls-remote origin refs/heads/arena/ba3bbc69-guialita
5e683923436e0d1006d0f40ca558cabaa35c2d4c
```

Der Arbeitsbaum enthielt alle 18 Dateien des Updates.

### Wiederherstellung (verlustfrei, ohne `--hard`, ohne force-push)

1. `git fetch origin arena/ba3bbc69-guialita`
2. Nachweis, dass nichts verloren geht — 15 getrackte Dateien ohne Diff gegen
   `FETCH_HEAD`, die 3 neuen Dateien byte-identisch gegen die Commit-Blobs:
   `AGENTS.md`, `scripts/local_update.sh`, `backend/adapters/mock_adapter.py`
3. erst danach `git reset --mixed FETCH_HEAD` (setzt den Zeiger, fasst den
   Arbeitsbaum nicht an)
4. `.venv` neu erstellt und Kernpakete installiert; `llama-cpp-python` bewusst
   nicht gebaut (in dieser Umgebung nicht nötig und nicht baubar)

Ergebnis: HEAD `5e68392`, Arbeitsbaum sauber, identisch mit Remote.
Abgeleitet wurde daraus `testing.reproducibility` in `GUIALITA_STATE.yaml`:
gitignored-Pfade sind in Agent-/CI-Umgebungen nicht garantiert vorhanden, die
Verifikation ist nach jedem Umgebungswechsel neu auszuführen.

### main-Abgleich — kein Integrationsbedarf

```
git fetch origin --prune
git log --oneline HEAD..origin/main      → leer (main hat keine neuen Commits)
git merge-base --is-ancestor origin/main HEAD → JA
git merge-base HEAD origin/main          → 4b3762b (= Spitze von origin/main)
```

`origin/main` steht unverändert auf `4b3762b`, dem Ausgangspunkt dieser Branch.
Es gab daher nichts zu ziehen und nichts anzupassen; ein Merge ist
Konflikt-frei (fast-forward möglich). Einziger Remote-Zweig neben `main` ist
`arena/ba3bbc69-guialita`. Delta: 18 Dateien, 1183 Einfügungen, 43 Löschungen.

### Evidenz — Verifikation nach der Wiederherstellung

```
GET /health                → 200  api: online · mock: online · latency 1.98 ms
GET /                      → 200  text/html, 26630 Bytes
GET /graph                 → 200  text/html, 17856 Bytes
POST /chat                 → 200  status: success · runtime: mock · Session + Memory indiziert
GET /diagnostics           → capabilities llm/stt/tts = false, llm_mock = true
                             ready_for_voice_turn: false
compileall                 → OK
scripts/doctor.py          → READY (7 Modelle konfiguriert, mock-1b verfügbar, TTS MISSING)
scripts/test.py            → UNIT PASS (46)
scripts/run_all_tests.py   → 6 PASS · 0 FAIL · 3 NOT_EXECUTED · Exit 0
                             145 Funktionen · 124 bewertbar · 108 bestanden ·
                             0 fehlgeschlagen · 16 skip
```

Vorschau-Tauglichkeit geprüft, weil die Ausgabe über einen fremden Host läuft:
Anfragen mit fremdem `Host:`-Header → `200` (keine Host-Allowlist),
CORS-Präflight → `200` mit `access-control-allow-origin: *`, Frontend nutzt
ausschließlich relative `fetch()`-Pfade (0 hardcodierte `localhost`-Aufrufe).

Regression der Reparatur aus dem vorherigen Abschnitt bestätigt:
`audio/inbox/audio_20260819_141715_001.json` überlebt den `test_capture.py`-Lauf,
`data/` bleibt ignoriert, `git status` leer.

### Offene Punkte (unverändert, nicht durch diese Session entstanden)

- Echte Runtime-Abnahme fehlt weiterhin: keine GGUF-Modelle, kein
  `llama-cpp-python`, kein whisper.cpp, kein LFM-Audio, kein PortAudio, kein
  `espeak-ng`. 3 Suiten `NOT_EXECUTED`, 16 Tests `skip`. Auf der Referenz-
  maschine ist `bash scripts/local_update.sh` ohne `--mock` auszuführen.
- Gate `voice_forensics_v1` bleibt `OPEN`; die Neuvermessung
  (`scripts/measure_voice_turn.py --record --turns 3`) braucht die Zielhardware.
- `next_authorized_phase: NONE` und `hard_stop: true` bleiben bestehen. Diese
  Session hat keine neue Phase autorisiert oder begonnen.
- Beobachtung ohne Änderung: `POST /audio/tts` meldet bei nicht verfügbarer
  Runtime `500` mit sauberer Fehlerstruktur (`tts_failed`). Semantisch wäre
  `503` treffender; die Änderung wurde nicht vorgenommen, weil kein Test den
  Code festlegt und sie den API-Vertrag verschieben würde — Entscheidung
  bewusst vertagt, nicht übersehen.

### Abschluss

Session wird archiviert. Branch `arena/ba3bbc69-guialita` wird per PR in `main`
überführt (Autorisierung durch den Nutzer erteilt). `docs/INTEGRITY_MARKER.txt`
und alle `docs/PHASE_*`-Berichte bleiben unverändert: sie sind historische
Belege und werden nach ihrer Erstellung nicht mehr geändert.

## 2026-11-13 — GUI-/Prototypen-Vorschau, main-Integration (`1bee303`) und Session-Abschluss (`arena/180fbd4a-guialita`)

**Auftrag:** GUI und Prototypen in der Live-Vorschau öffnen, anschließend das
aktuelle `origin/main` ziehen, Konflikt-frei abgleichen, verifizieren und die
Session per Commit, Push, PR und Merge abschließen (Autorisierung erteilt).

### 1. Ausgangslage und `main`-Abgleich

- Branch: `arena/180fbd4a-guialita` (ursprünglich abgezweigt von `4b3762b`)
- `git fetch origin main` zeigte den neu gemergten Stand `1bee303`
  (Merge von PR #3 `arena/ba3bbc69-guialita`: `AGENTS.md`, `scripts/local_update.sh`,
  `backend/adapters/mock_adapter.py`, Lifespan- und Audit-/Memory-Korrekturen).
- Integration erfolgte Konflikt-frei per Fast-Forward (`git merge --ff-only origin/main`
  von `4b3762b` auf `1bee303`).

### 2. Live-Vorschau (GUI + Prototypen)

- Produktive GUI (`backend/main.py` mit `GUIALITA_MOCK_LLM=1`) auf `0.0.0.0:8080`
  gestartet (`/` → HTTP 200, `/graph` → HTTP 200, `/health` → HTTP 200).
- Drei isolierte Next.js-Erkundungsprototypen unter `PROTOTYPEN/` zur Ansicht
  auf `0.0.0.0:3001` (`local-lfm-api-foundation` inkl. internem Mock-LFM-Server
  auf `127.0.0.1:8000`), `0.0.0.0:3002` (`local-multimodal-desktop-agent`) und
  `0.0.0.0:3003` (`multimodal-ui-builder-agent (Kopie 1)`) gestartet (alle HTTP 200).
- Keine getrackten Dateien unter `PROTOTYPEN/` verändert; `node_modules/` und
  `.next/` bleiben gemäß `.gitignore` unversioniert.

### 3. Kleine Korrektur in `scripts/test.py`

- **Befund:** Wenn der Unit-Lauf in `scripts/test.py` fehlschlug (`unit_rc != 0`,
  z. B. bei fehlendem `pytest`), gab das Skript trotz Exit-Code `1` am Ende
  unbedingt `Overall: PASS (unit layer only; use --live for runtime tests)` aus.
- **Änderung:** `Overall:` gibt nun wahrheitsgemäß `PASS` nur bei `rc == 0` und
  sonst `BLOCKED/FAIL` aus (sowohl im Standard- als auch im `--live`-Modus).

### 4. Evidenz — Frischer Verifikationslauf auf `1bee303` + Fix

```
python -m compileall -q backend scripts tests → OK (Exit 0)
scripts/doctor.py                             → Result: READY (7 Modelle, mock-1b verfügbar, TTS MISSING)
scripts/test.py                               → UNIT: PASS · Overall: PASS (46 passed)
scripts/run_all_tests.py (GUIALITA_MOCK_LLM=1):
  test_voice_activation.py    PASS                37/37
  test_memory.py              PASS (mock)         16/16
  test_memory_retrieval.py    PASS (mock)  13/17 (4 skip)
  test_memory_graph.py        PASS (mock)  12/14 (2 skip)
  test_graph_visualization.py PASS          8/13 (5 skip)
  test_api.py                 PASS (mock)  22/27 (5 skip)
  test_tts.py                 NOT EXECUTED  fehlt: TTS-Runtime
  test_capture.py             NOT EXECUTED  fehlt: Mikrofon / PortAudio, espeak-ng
  test_process_audio.py       NOT EXECUTED  fehlt: LFM-Audio-Runtime, espeak-ng

  Suiten PASS: 6 | FAIL: 0 | NOT EXECUTED: 3
  Testfunktionen: 145 | bewertbar ausgeführt: 124 | bestanden: 108 |
  fehlgeschlagen: 0 | übersprungen (skip): 16 | Exit-Code: 0
```

### 5. Offene Punkte (unverändert)

- Echte Runtime-Abnahme (GGUF-Modelle, `llama-cpp-python`, whisper.cpp,
  `llama-liquid-audio-cli`, PortAudio, `espeak-ng`) bleibt auf der
  Referenzmaschine ohne `--mock` auszuführen (`bash scripts/local_update.sh`).
- Gate `voice_forensics_v1` bleibt `OPEN` (`scripts/measure_voice_turn.py --record --turns 3`
  auf Zielhardware erforderlich).
- `next_authorized_phase: NONE` und `hard_stop: true` in `docs/GUIALITA_STATE.yaml`
  bleiben unverändert bestehen; `docs/INTEGRITY_MARKER.txt` und alle
  `docs/PHASE_*`-Berichte bleiben unangetastet.

---

## 2026-11-13 — Integration von `origin/main` (freigegeben)

**Freigabe:** ausdrücklich für Merge, gemeinsame Neubaseline und PR. Nicht
enthalten: Änderung von `hard_stop`, `prohibitions`,
`next_authorized_phase`, Hardware- oder Live-Abnahme.

### Vorgehen

```text
git fetch origin main                         → 7caea0e (Merge PR #4)
git merge --no-commit --no-ff FETCH_HEAD      → 4 Konflikte
  README.md, docs/GUIALITA_STATE.yaml,
  docs/HEARTBEAT.md, docs/SESSION_LOG.md
Auto-Merge (beidseitig geändert): .gitignore, scripts/run_all_tests.py
```

### Zusammengeführt

- Aus `main`: `AGENTS.md`, `scripts/local_update.sh`,
  `backend/adapters/mock_adapter.py`, Diagnose-/Audit-Korrekturen,
  Mock-Klassifizierung `PASS (mock)` im Runner, Reproduzierbarkeitsregel.
- Aus diesem Branch: AST-Zählung, `deps`-Fähigkeit, 19 Suiten,
  `--check-state`, ADR-002-Werkzeuge, `contract_check.py`, 13 geprüfte
  Dokumente.
- `scripts/run_all_tests.py` trägt jetzt **beides**: 19 Suiten mit
  `satisfied()`/`MOCK_SATISFIES` und `--check-state`. Kein Textkonflikt,
  aber bewusst nachgeprüft.
- `docs/SESSION_LOG.md` und `docs/HEARTBEAT.md` führen beide Session-Reihen;
  historische Zahlen (145/9, 307/19) wurden nicht umgeschrieben.

### Neue Baseline

| | vor der Integration | nach der Integration |
|---|---|---|
| `test_api.py` | 23 | **27** |
| Gesamt | 307 / 19 | **311 Testfunktionen in 19 Suiten** |

`ci_capable` in der SSOT ist jetzt `partial`: sieben Suiten laufen in CI,
zwölf bleiben in der nackten Sandbox NOT_EXECUTED. Der Mock-Adapter ergänzt
`PASS (mock)`, ersetzt aber keine Runtime-Abnahme.

### Evidenz

```text
python3 scripts/run_all_tests.py --check-state  → Keine Abweichung (311/19)
python3 scripts/check_docs.py                  → OK über 13 Dokumente
python3 scripts/contract_check.py              → OK
python3 scripts/run_all_tests.py --only <7>   → 7 PASS, 0 FAIL
python3 scripts/run_all_tests.py              → 7 PASS, 12 NOT EXECUTED, 0 FAIL
python3 -m compileall -q backend scripts tests → RC 0
git diff --check                              → RC 0
```

Alle Zahlen in SSOT, Regression Contract, Bootstrap, ADR-002, Heartbeat,
README und `tests/test_doc_consistency.py` sind auf 311/19 nachgezogen.
`current.hard_stop: true`, `next_authorized_phase: NONE`, sieben
`prohibitions` und `future_target: PLANNED` sind unverändert.

### Nicht belegt

Keine Inferenz, kein Modell, keine GPU, kein VRAM, keine echte Latenz,
kein STT/TTS, keine Audio-Abnahme. `contract_check.py` bleibt ein
Vertragsnachweis mit synthetischen Werten. Live-Abnahme bleibt offen.

## Nachvollziehbarkeitsregel

- Quellcodeänderungen werden über Git-Commits gespeichert.
- Test- und Diagnoseergebnisse werden in diesem Protokoll bzw. separaten
  Ergebnisdokumenten festgehalten.
- Eine Chat-Session oder interne Überlegungen werden nicht automatisch in Git
  geschrieben. Auf Wunsch wird pro Arbeitsabschnitt ein sachlicher Eintrag mit
  Ziel, Änderung, Evidenz und offenen Punkten ergänzt.
