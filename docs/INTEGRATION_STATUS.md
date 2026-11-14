# Integration nach `main` — Stand 2026-11-13

Dieses Dokument hält fest, was eine Zusammenführung dieses Branches mit `main`
tatsächlich kostet. Es ist **kein Phasenstatus**; maßgeblich für den
Projektzustand bleibt `docs/GUIALITA_STATE.yaml`. Es steht bewusst **nicht** in
`CURRENT_FILES` von `scripts/check_docs.py`: Es nennt absichtlich zwei
konkurrierende Zahlenstände nebeneinander und würde die Pflichtphrasenprüfung
der 13 aktuellen Dokumente verfälschen.

## Beteiligte Stände

| | Commit | Testinventar | Besonderheit |
|---|---|---|---|
| Merge-Basis | `4b3762b` | 141 / 9 (damals behauptet) | Ausgangspunkt beider Zweige |
| Dieser Branch | `9b0e498` | **307 Testfunktionen in 19 Suiten** | ADR-002 P1–P6, AST-Zählung, 7 Standardbibliothek-Suiten |
| `origin/main` | `7caea0e` | **145 Testfunktionen in 9 Suiten** | Mock-Test-Adapter, `local_update.sh`, `AGENTS.md` |

`main` ist seit dem Branching um fünf Commits weitergezogen
(`5e68392`, `5643df9`, `1bee303`, `4cde07a`, `7caea0e`); dieser Branch um vier
(`7b6ca86`, `12afaed`, `03c0522`, `9b0e498`). Beide Zweige haben unabhängig
versucht, dasselbe Testinventar zu konsolidieren — mit **unterschiedlichen
Ergebnissen**. Das ist der Kern des Konflikts, nicht bloß Text.

## Trocken gemessen

```text
git merge-base HEAD origin/main          → 4b3762b
git merge-tree --write-tree HEAD origin/main → RC 1
```

**4 Konfliktdateien:**

1. `README.md`
2. `docs/GUIALITA_STATE.yaml`
3. `docs/HEARTBEAT.md`
4. `docs/SESSION_LOG.md`

Automatisch zusammenführbar, aber von beiden Seiten geändert:
`.gitignore` und `scripts/run_all_tests.py`.

AST-Nachzählung auf `main`: `tests/test_api.py` hat **27** Testfunktionen
(dieser Branch: 23), `tests/test_capture.py` weiterhin 6. Ein Merge ergäbe
damit **311 Testfunktionen in 19 Suiten** — nicht 307 und nicht 145. Die
Zahlen in SSOT, Regression Contract, Bootstrap, Heartbeat, Session-Log,
ADR-002, README und `tests/test_doc_consistency.py` müssten gemeinsam
nachgezogen werden. Ein halb korrigierter Merge würde `--check-state` sofort
rot machen.

## Extern verifiziert: CI auf GitHub

Der Workflow `.github/workflows/state-consistency.yml` ist auf GitHub aktiv.
Alle vier Push-Läufe auf diesem Branch sind `success`:

| Run | Commit | Ergebnis |
|---|---|---|
| `43408033608` | `7b6ca86` | success |
| `43425145999` | `12afaed` | success |
| `43618536071` | `03c0522` | success |
| `43621040654` | `9b0e498` | success, **13/13 Schritte** |

`gh run view 43621040654` zeigt u. a. grün: Inventarabgleich, sieben
Standardbibliothek-Suiten, Golden Set, Rollen-YAML, Registry, Eval,
VRAM-Budget, MUSCAL-Trockenlauf, Live-Contract und Dokumenten-Konsistenz.
Das ist ein Nachweis für **diesen Branch**, nicht für `main` und nicht für
Hardware.

## Warum hier kein Merge und kein PR ausgeführt wurde

- Ein Merge importiert eine andere, ältere Testrealität (145/9) samt
  Mock-Adapter in einen Branch, dessen Zahlen gerade extern grün geprüft
  wurden. Ohne vollständige Neubaseline wäre anschließend keine Zahl mehr
  belastbar.
- Ein PR gegen `main` würde GitHub-seitig **„Konflikte"** anzeigen. Das als
  „fertig" auszugeben wäre genau die Art Erfolgsbehauptung ohne Evidenz, die
  dieses Projekt teuer bezahlt hat.
- `current.hard_stop: true`, `next_authorized_phase: NONE` und `prohibitions`
  bleiben unangetastet. Die Integration ist eine Review-Entscheidung, keine
  Implementierungsfreigabe.

## Konkreter Fahrplan (bei Freigabe)

1. `git merge --no-commit origin/main` auf diesem Branch; die vier
   Konfliktdateien manuell zusammenführen.
2. In `docs/GUIALITA_STATE.yaml` unser AST-Inventar als kanonisch behalten,
   aber `mock_adapter`, `update_and_verify_entry`, `agent_instructions` und
   `reproducibility` aus `main` übernehmen; `test_api.py` auf 27, Summe auf
   **311 / 19** setzen.
3. `scripts/run_all_tests.py` nach dem Auto-Merge prüfen: `deps`, `satisfied()`
   und `--check-state` müssen gleichzeitig funktionieren.
4. `docs/SESSION_LOG.md` und `docs/HEARTBEAT.md` chronologisch
   zusammenführen, nicht überschreiben; `README.md` beide Abschnitte behalten.
5. Alle Zahlen in `docs/BASELINES/REGRESSION_CONTRACT.md`,
   `docs/GUIALITA_SESSION_BOOTSTRAP.md`, `docs/adr/ADR-002-agent-orchestration.md`,
   `README.md` und `tests/test_doc_consistency.py` auf 311/19 nachziehen.
6. Erst danach: `--check-state`, `check_docs.py`, `contract_check.py`,
   vollständiger Runner, YAML/JSON-Validierung — und **dann** PR öffnen.

Bis dahin gilt: dieser Branch ist in sich konsistent, gepusht und extern grün.
