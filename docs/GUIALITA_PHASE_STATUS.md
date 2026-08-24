# GUIALITA — Phasenstatus

Diese Datei enthält bewusst **keine** Statustabelle mehr.

Der Phasenstatus stand früher gleichzeitig hier, in
`docs/GUIALITA_SESSION_BOOTSTRAP.md` und in `docs/GUIALITA_STATE.yaml` — mit
widersprüchlichen Baseline-Angaben als Folge. Eine Kopie, die nicht
mitgepflegt wird, ist schlimmer als keine Kopie.

## Maßgeblich

**→ [`docs/GUIALITA_STATE.yaml`](GUIALITA_STATE.yaml)**

Dort stehen: Phasen, Status, Baseline, offene Gates, Verbote, bekannte
Probleme — maschinenlesbar und an genau einer Stelle.

```bash
# Schnellüberblick
grep -E "^\s+(title|status|gate_status):" docs/GUIALITA_STATE.yaml
```

## Statusvokabular

Die Bedeutung von `PASS`, `OBSERVED`, `DOCUMENTED`, `OPEN`, `UNKNOWN`,
`NOT_STARTED`, `BLOCKED`, `IN_PROGRESS` und
`PERFORMANCE_OPTIMIZATION_REQUIRED` ist in `GUIALITA_STATE.yaml` unter
`status_vocabulary` definiert. `UNKNOWN` wird nicht zu `PASS` umgedeutet.

## Historische Belege

Die Phase-Reports (`docs/PHASE_*.md`, `docs/phase-*.yaml`) und Baselines
(`docs/BASELINES/`) sind **unveränderliche historische Belege**. Sie geben den
Zustand ihres Entstehungszeitpunkts wieder — auch dann, wenn sie eine
inzwischen überholte Baseline nennen. Sie werden nicht nachträglich
korrigiert.

## Architekturentscheidungen

`docs/adr/` — beginnend mit
[ADR-001: whisper.cpp als STT-Runtime](adr/ADR-001-stt-whisper-cpp.md).
