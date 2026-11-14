# Integration von `origin/main` — abgeschlossen am 2026-11-13

Dieses Dokument hält fest, wie die Zusammenführung dieses Branches mit `main`
tatsächlich durchgeführt wurde. Es ist **kein Phasenstatus**; maßgeblich für
den Projektzustand bleibt `docs/GUIALITA_STATE.yaml`. Es steht bewusst
**nicht** in `CURRENT_FILES` von `scripts/check_docs.py`: Es nennt absichtlich
frühere und aktuelle Zahlenstände nebeneinander und würde die
Pflichtphrasenprüfung der 13 aktuellen Dokumente verfälschen.

**Freigabe:** ausdrücklich für Merge, gemeinsame Neubaseline und PR. Nicht
enthalten: Änderung von `hard_stop`, `prohibitions`,
`next_authorized_phase`, Hardware- oder Live-Abnahme.

## Ausgangslage (vor dem Merge)

| | Commit | Testinventar | Besonderheit |
|---|---|---|---|
| Merge-Basis | `4b3762b` | 141 / 9 (damals behauptet) | Ausgangspunkt beider Zweige |
| Dieser Branch | `9b0e498` | **307 Testfunktionen in 19 Suiten** | ADR-002 P1–P6, AST-Zählung, 7 Standardbibliothek-Suiten |
| `origin/main` | `7caea0e` | **145 Testfunktionen in 9 Suiten** | Mock-Test-Adapter, `local_update.sh`, `AGENTS.md` |

`main` war seit dem Branching um fünf Commits weitergezogen
(`5e68392`, `5643df9`, `1bee303`, `4cde07a`, `7caea0e`); dieser Branch um
mehrere ADR-002-Commits. Beide Zweige hatten unabhängig versucht, dasselbe
Testinventar zu konsolidieren — mit **unterschiedlichen Ergebnissen**. Das war
der Kern des Konflikts, nicht bloß Text.

```text
git merge-base HEAD origin/main               → 4b3762b
git merge-tree --write-tree HEAD origin/main  → RC 1, 4 Konflikte
  README.md, docs/GUIALITA_STATE.yaml,
  docs/HEARTBEAT.md, docs/SESSION_LOG.md
Auto-Merging (beidseitig geändert): .gitignore, scripts/run_all_tests.py
```

AST-Nachzählung auf `main`: `tests/test_api.py` hatte **27** statt 23
Testfunktionen, `tests/test_capture.py` weiterhin 6. Rechnerisch — bei
Übernahme der `main`-Version von `test_api.py` — ergab sich **311
Testfunktionen in 19 Suiten**, also weder 307/19 noch 145/9.

## Durchführung

```text
git fetch origin main                         → 7caea0e
git merge --no-commit --no-ff FETCH_HEAD      → 4 Konflikte, wie vorhergesagt
```

Die vier Konflikte wurden **inhaltlich** aufgelöst, nicht durch „ours" oder
„theirs" überschrieben:

- `README.md`: kanonischer Runner-Aufruf mit 311/19 und `--check-state` aus
  diesem Branch, dazu die Klassifizierungstabelle, den Mock-Abschnitt und
  `local_update.sh` aus `main`. Die Formulierung „alle 9 Suiten" ist ersetzt.
- `docs/GUIALITA_STATE.yaml`: `test_functions_total: 311`, `suites: 19`,
  `test_api.py: 27`, AST-Zählung und `--check-state` behalten; neu
  `update_and_verify_entry`, `agent_instructions`, `mock_adapter`,
  `reproducibility` und `integration_2026_11_13` aus `main` bzw. diesem Lauf.
  `ci_capable` ist jetzt `partial` (vorher `false`, auf `main` `partial`).
- `docs/HEARTBEAT.md`: eine aktuelle Kurzfassung mit 311/19, beide
  Session-Reihen als Verweis auf `docs/SESSION_LOG.md`, historischer
  2026-08-22-Abschnitt erhalten.
- `docs/SESSION_LOG.md`: beide Session-Reihen chronologisch erhalten. Die
  Einträge aus `main` haben einen **Historischer-Beleg**-Kopf; die
  ADR-002-Einträge bleiben; ein neuer Abschnitt dokumentiert die Integration.

`scripts/run_all_tests.py` wurde ohne Textkonflikt automatisch
zusammengeführt und trägt jetzt **beides**: 19 Suiten mit `deps`,
AST-Zählung und `--check-state` aus diesem Branch sowie
`MOCK_SATISFIES`/`satisfied()`/`PASS (mock)` aus `main`. Das wurde bewusst
nachgeprüft, nicht als „grün = funktionsfähig" hingenommen.

## Ergebnis

| | vorher | jetzt |
|---|---|---|
| `test_api.py` | 23 | **27** |
| Gesamt | 307 / 19 | **311 Testfunktionen in 19 Suiten** |
| `ci_capable` | `false` | **`partial`** |
| Runner | 19 Suiten, AST | 19 Suiten, AST **+** Mock-Klassifizierung |

Alle Zahlen in SSOT, Regression Contract, Bootstrap, ADR-002, Heartbeat,
README und `tests/test_doc_consistency.py` sind auf 311/19 nachgezogen.
Historische Zahlen (145/9, 307/19, 141/9) wurden nicht umgeschrieben, sondern
als Zeitpunkt-Belege markiert.

Unverändert: `current.hard_stop: true`, `next_authorized_phase: NONE`, sieben
`prohibitions`, `future_target: PLANNED`. Kein Desktop-Adapter, keine
parallelen Agenten, keine Cloud-Inferenz.

## Verifikation

```text
python3 scripts/run_all_tests.py --check-state  → Keine Abweichung (311/19)
python3 scripts/check_docs.py                  → OK über 13 Dokumente
python3 scripts/contract_check.py              → OK
python3 scripts/build_golden.py --check        → OK
python3 scripts/build_roles.py --check         → OK
python3 scripts/roles.py validate --check-mirror → OK
python3 scripts/eval.py --dry-run --all-suites → OK
python3 scripts/run_all_tests.py --only <7>   → 7 PASS, 0 FAIL
python3 scripts/run_all_tests.py              → 7 PASS, 12 NOT EXECUTED, 0 FAIL
python3 -m compileall -q backend scripts tests → RC 0
git diff --check                              → RC 0
```

Der Workflow `State Consistency` ist auf GitHub `active` und auf dem
Merge-Commit `54c521d` zweimal grün: Push-Run `43626009032` und
Pull-Request-Run `43626127557` (je 16/16 Schritte). Details und weitere
Run-IDs stehen in `docs/SESSION_LOG.md`.

## PR #5

`gh pr create` → **PR #5** (`main` ← `arena/f82209dd-guialita`), bei
Erstellung `OPEN` und `mergeable: MERGEABLE`. Der trockene Gegen-Merge
(`git merge-tree --write-tree origin/main HEAD`) liefert RC 0 — die
Konflikte sind also auch aus Sicht von `main` aufgelöst.

`mergeStateStatus` war bei Erstellung `UNSTABLE`, weil der auf `pull_request` laufende
Workflow `Auto PR Review` (`.github/workflows/audit-pr.yml`, externe
OpenCode/OpenRouter-Action) mit `review → failure` endet. Das ist **kein
Fehler dieser Integration**: derselbe Check ist auf PR #3 und PR #4
ebenfalls fehlgeschlagen, und beide PRs wurden gemergt. Der für dieses
Repository maßgebliche Check `Inventar, Werkzeuge ↔ SSOT` ist auf dem
Pull-Request-Run `43626127557` grün. Der fremde Review-Workflow wurde nicht
geändert — das braucht eine eigene Freigabe und vermutlich ein konfiguriertes
Secret bzw. einen externen Dienst.

Die Übernahme nach `main` erfolgte anschließend als eigener, ausdrücklich
freigegebener Schritt über PR #5 — siehe den Abschluss unten.

## Abschluss: PR #5 gemergt

```text
gh pr merge 5 --merge                         → RC 0, MERGED
gh api repos/.../pulls/5                      → state: closed, merged: true
merge_commit_sha                              → d899919c900b8ebf9419a93e88c8bd58c19cb2c1
origin/main                                   → 7caea0e -> d899919
git merge-base --is-ancestor HEAD origin/main  → RC 0
gh run view 43642883664 (push auf main)       → completed / success
```

GitHub-Zeitstempel des Merges: `2026-11-14T21:27:08Z`. Das ist ein
Ereignis-Zeitstempel, **nicht** das Projektdatum der SSOT; `meta.updated`
bleibt `2026-11-13` und wurde nicht an die Sandbox-Uhr angepasst.

Zum Zeitpunkt des Merges waren der Baum des PR-Heads und der Baum von `main`
identisch (`b4aa59cc09f2cda6394324e99a38c4b78f6539a3`): alle Änderungen sind
vollständig übernommen. Der externe `review`-Check blieb rot, war aber nicht
blockierend (PR #3/#4 ebenso). `arena/f82209dd-guialita` wurde nicht gelöscht.

Dieser Abschluss wurde auf `arena/dfd44a8d-guialita` ergänzt, das von
`d899919` abzweigt. Die nachfolgenden Dokumentations-Commits erzeugen bewusst
einen neuen Baum; sie ändern kein Werkzeug und keine Testzahl.

## Grenzen

Die Läufe belegen Logik, Inventar, Dokumentenkonsistenz und den HTTP-Vertrag
dieses Branches. Sie belegen **keine** Inferenz, kein Modell, keine GPU, keine
VRAM-Belegung, keine echte Latenz, kein STT/TTS und keine Audio-Abnahme.
`scripts/contract_check.py` bleibt ein Vertragsnachweis mit synthetischen
Werten; `PASS (mock)` ist keine Runtime-Abnahme. P0 bleibt offen.

Nebenbefund aus den CI-Annotations: `actions/setup-python@v5` läuft noch auf
Node.js 20 und wird derzeit auf Node.js 24 erzwungen; `ubuntu-latest` soll auf
Ubuntu 26 wechseln. Die Pins wurden bewusst nicht blind angehoben — das ist
eine separate Review-Entscheidung, kein Konsistenzfehler.
