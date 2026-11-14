# GUIALITA — Milestone Heartbeat

Sachliche Fortschrittsansicht. Verbindliche Quelle ist `GUIALITA_STATE.yaml`.
Aktualisiert nach jedem abgeschlossenen autonomen Arbeitsabschnitt; keine
internen Gedankengänge, nur Status, Evidenz und nächste Schritte.
Zuletzt fortgeschrieben: 2026-11-13.

## Aktueller Stand — 2026-11-13 (Kurzfassung)

- **311 Testfunktionen in 19 Suiten**; `run_all_tests.py --check-state`
  meldet keine Abweichung. `origin/main@7caea0e` ist integriert: Mock-Test-
  Adapter, `scripts/local_update.sh` und `AGENTS.md` sind übernommen, ohne die
  AST-Zählung oder eine der 19 Suiten zu verlieren.
- Vollständiger Sandbox-Lauf ohne Mock: **7 PASS, 12 NOT EXECUTED, 0 FAIL**.
  Kein Test aus einer `NOT_EXECUTED`-Suite wurde als bestanden gezählt.
  Mit `GUIALITA_MOCK_LLM=1` werden zusätzliche Chat-, Memory- und API-Pfade
  als `PASS (mock)` ausgewiesen — das ist keine Runtime-Abnahme.
- ADR-002 P3–P6: Eval-Harness, VRAM-Budget/Lifecycle, Rollen-Registry und
  MUSCAL CLI/HTTP sind als Selbsttests im Trockenlauf geprüft.
  `scripts/contract_check.py` belegt zusätzlich die Live-Clients gegen das
  echte HTTP-Schema. Live-Pfade, echte VRAM-Messung und Hardware-Latenzen sind
  **nicht abgenommen**.
- **P0** (Voice-Turn-Nachmessung) bleibt offen; `current.hard_stop: true`,
  `next_authorized_phase: NONE` und `prohibitions` sind unverändert.
- MUSCAL bleibt CLI/HTTP, kein Desktop-Adapter, keine parallelen Agenten.
- Extern geprüft: `gh run view 43621040654` → `success`, 16/16 Schritte des
  Workflows `State Consistency` grün (10 Prüfschritte); alle folgenden
  Push-Läufe auf diesem Branch ebenfalls grün, auf dem Merge-Commit
  `54c521d` zusätzlich der Pull-Request-Run `43626127557`. **PR #5** wurde
  zur Übernahme nach `main` eröffnet (bei Erstellung `MERGEABLE`); der
  vorbestehende externe `Auto PR Review`-Check ist wie schon bei PR #3/#4 rot
  (`UNSTABLE`), kein Regression. Details und Verlauf:
  `docs/INTEGRATION_STATUS.md`.
- Aus `main` übernommen: `AGENTS.md`, `scripts/local_update.sh`,
  `backend/adapters/mock_adapter.py`, Diagnose-/Audit-Korrekturen und die
  Reproduzierbarkeitsregel. Details der `main`-Sessions stehen in `docs/SESSION_LOG.md` als
  historische Belege; maßgeblich bleibt `docs/GUIALITA_STATE.yaml`.

## Historischer Status — 2026-08-22 (nicht maßgeblich)

Dieser Abschnitt ist der damalige Heartbeat. Die Zahlen 39/46, die Angabe
`scripts/test.py` als „Layered Test Runner" und die offenen M4/M5-Punkte sind
historisch und wurden inzwischen über `scripts/run_all_tests.py`, die SSOT und
`docs/SESSION_LOG.md` ersetzt.

**Milestone:** M5 — Performance-Baseline

| Bereich | Status |
|---|---|
| Text-Chat, Sessions, Memory, Graph | PASS laut Baseline-Dokumentation |
| Audio → STT → Chat | implementiert |
| Audio-Chat mit Session/Memory | verbessert und integriert |
| TTS-Eingabevalidierung | verbessert |
| Voice-Wiedergabe-Aufräumen | verbessert |
| Portable Modell-/Whisper-Pfade | implementiert |
| Lokale Venv/Dependencies | installiert in Sandbox |
| Unit-/Contract-Tests | PASS — 39 Tests über `scripts/test.py` |
| Vollständige Runtime-Tests | BLOCKED: Backend, Modelle, Whisper, espeak-ng |
| Layered Test Runner | implementiert: `scripts/test.py` |
| Deterministischer Benchmark | implementiert: `scripts/benchmark.py` |
| Memory-Embedding-Baseline | median 0,02 ms in Sandbox |
| Technisches Audit | aktiv: `data/audit.jsonl` (Metadaten standardmäßig) |
| Unit-/Contract-Testbasis | PASS — 46 Tests über `scripts/test.py` |
| Mock-Chat-/Memory-Pipeline | PASS — Session, History, Persistenz |
| Session-Export | implementiert: `/sessions/{id}/export` |
| Audit-Abfrage | implementiert: `/audit/events` |
| Markdown-Sessionexport | implementiert: `/sessions/{id}/export.md` |
| Performance-Auswertung | implementiert: `/audit/summary` |
| Git-Nachvollziehbarkeit | aktiv |

## Abgeschlossene Milestones

### M1 — Auditierbare Basis

- `requirements.txt` hinzugefügt
- `scripts/doctor.py` hinzugefügt
- README aktualisiert
- Änderungsprotokoll `docs/SESSION_LOG.md` eingeführt

### M2 — Konsistente Audio-Pipeline

- `/audio/chat` nutzt `ChatService`
- Session-ID, History, Retrieval und Memory-Indexierung bleiben bei Voice-Turns
  erhalten
- Request-, WAV-, Base64- und Größenvalidierung ergänzt

### M3 — Laufzeitrobustheit

- TTS erkennt später verfügbare lokale Assets
- temporäre Voice-WAV-Dateien werden garantiert gelöscht
- portable Pfadauflösung für Modelle und Whisper ergänzt
- isolierte Tests bleiben erfolgreich

## Historische Milestone-Planung (2026-08-22)

M4 und M5 sind in `docs/GUIALITA_STATE.yaml` inzwischen als PASS geführt. Die
folgende Liste bleibt als Planungsbeleg stehen, nicht als aktuelle Aufgabenliste.

### M4 — Testharness

- Unit-, API-, Runtime- und Hardwaretests klar trennen
- fehlende Voraussetzungen als `SKIPPED/BLOCKED` melden
- Audio-Contract- und Session-Regression erweitern

### M5 — Performance

- Warm-Start für LLM, STT und TTS
- Latenzprofiling
- Streaming evaluieren

### M6 — Real-World Voice Acceptance

- echter Mikrofon-Mehrturn-Test
- Echo-/Self-trigger-Prüfung
- deutsche Transkriptionsqualität

### M7 — Kontrollierte multimodale Erweiterung

- Vision-Prototypen prüfen
- Desktop-Control nur mit Sicherheitsbestätigung integrieren

## Ausführungshinweis

Der Agent kann keine neuen Chat-Nachrichten außerhalb eines aktiven Turns senden.
Dieses Dokument ist deshalb der persistente Heartbeat im Repository. Jeder weitere
Arbeitsabschnitt wird hier mit Milestone, Ergebnis und Blockern ergänzt.
