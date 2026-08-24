# GUIALITA — Milestone Heartbeat

Sachliche Fortschrittsansicht. Verbindliche Quelle ist `GUIALITA_STATE.yaml`.
Aktualisiert nach jedem abgeschlossenen autonomen
Arbeitsabschnitt; keine internen Gedankengänge, nur Status, Evidenz und nächste
Schritte.

## Aktueller Status — 2026-08-22

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
