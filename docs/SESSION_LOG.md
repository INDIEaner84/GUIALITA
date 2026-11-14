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

- Verbindlich sind **307 Testfunktionen in 19 Suiten**; `--check-state`
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

## Nachvollziehbarkeitsregel

- Quellcodeänderungen werden über Git-Commits gespeichert.
- Test- und Diagnoseergebnisse werden in diesem Protokoll bzw. separaten
  Ergebnisdokumenten festgehalten.
- Eine Chat-Session oder interne Überlegungen werden nicht automatisch in Git
  geschrieben. Auf Wunsch wird pro Arbeitsabschnitt ein sachlicher Eintrag mit
  Ziel, Änderung, Evidenz und offenen Punkten ergänzt.
