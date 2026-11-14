# GUIALITA — Milestone Heartbeat

Sachliche Fortschrittsansicht. Verbindliche Quelle ist `GUIALITA_STATE.yaml`.
Aktualisiert nach jedem abgeschlossenen autonomen
Arbeitsabschnitt; keine internen Gedankengänge, nur Status, Evidenz und nächste
Schritte.

## Aktueller Status — 2026-11-13

**Abschnitt:** Lokales Update + Verifikation (Agent-Anweisung `AGENTS.md`)

| Bereich | Status |
|---|---|
| Agent-Anweisungsprompt | implementiert: `AGENTS.md` (OpenCode lädt sie automatisch) |
| Update + Verifikation in einem Schritt | implementiert: `scripts/local_update.sh [--mock]` |
| Test-Adapter ohne Modell/GPU | implementiert: `backend/adapters/mock_adapter.py`, `GUIALITA_MOCK_LLM=1` |
| Testbestand | 145 Funktionen in 9 Suiten (`test_api.py` 23 → 27) |
| Testlauf Sandbox (mit Mock) | **6 PASS · 0 FAIL · 3 NOT_EXECUTED** — 108 bestanden, 16 skip, Exit 0 |
| Unit-Schicht `scripts/test.py` | PASS — 46 Tests |
| Backend-Start/Stop | PASS — `/health` online, `lifespan` statt deprecatedem `on_event` |
| API-Vertrag (400/404/415/500) | geprüft über Rauchprobe und `test_api.py` |
| Memory-Status-Korrektur | `embedding_version: 1` (war fälschlich 512) + `embedding_dimensions: 512` |
| Audit-Ablage | folgt jetzt `GUIALITA_DATA_ROOT`; `data/*.jsonl` ignoriert |
| Echte LLM-/STT-/TTS-Runtime | **nicht nachgewiesen** — keine Modelle, kein whisper.cpp, kein LFM-Audio |
| Voice-Turn-Neuvermessung (Gate) | weiter OPEN — braucht Zielhardware |
| `main`-Abgleich | keine neuen Commits auf `origin/main`; Merge Konflikt-frei (fast-forward) |
| Umgebungs-Wiederherstellung | Branch-Zeiger verlustfrei auf `5e68392` zurückgesetzt, `.venv` neu gebaut |
| Reproduzierbarkeitsregel | dokumentiert: gitignored-Pfade neu aufbauen, Verifikation neu ausführen |
| Vorschau-Tauglichkeit | geprüft: fremder `Host` → 200, CORS `*`, Frontend nur relative Pfade |
| Session-Abschluss | archiviert; Überführung nach `main` per PR (durch Nutzer autorisiert) |
| Folge-Session `arena/180fbd4a-guialita` | Fast-Forward auf `1bee303`, GUI + 3 Prototypen in Vorschau geprüft, `scripts/test.py` Overall-Ausgabe gehärtet, 6 PASS / 0 FAIL / 3 NOT_EXECUTED bestätigt |

Mock-Läufe werden als `PASS (mock)` ausgewiesen: Sie beweisen Chat-, Memory-,
Audit- und API-Pfad, **nicht** Inferenz, GPU, STT oder TTS.
Details und vollständige Evidenz: `docs/SESSION_LOG.md` (2026-11-13).

## Status — 2026-08-22 (vorangegangener Abschnitt)

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

## Nächste Milestones

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
