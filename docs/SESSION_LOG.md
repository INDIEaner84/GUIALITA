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

## 2026-08-25 — Session-Übergabe und Dokumentationshärtung

### Ausgangslage

- Branch: `arena/01a03788-guialita`.
- Arbeitskopie war zu Sitzungsbeginn sauber.
- `git fetch origin` war möglich; `git pull --ff-only origin arena/01a03788-guialita`
  konnte nicht ausgeführt werden, weil die kurzlebige Remote-Branch nicht
  vorhanden war. Es wurde nicht auf `main` gewechselt.
- Kanonischer State gelesen: `current.hard_stop: true`,
  `current.recommended_next: voice_latency_remeasurement`.

### Prüfung

- `python3 scripts/run_all_tests.py --list`: 141 Testfunktionen in 9 Suiten.
- `python3 scripts/run_all_tests.py --only voice_activation`: `NOT_EXECUTED`,
  weil Python-Abhängigkeiten in der Sandbox fehlen.
- `python3 scripts/doctor.py`: `PARTIAL`, fehlende Python-Pakete und keine
  lokale Runtime-/Modellumgebung in der Sandbox.

### Änderungen

- README konsolidiert: keine veralteten absoluten Zielmaschinenpfade als
  Schnellstart, klare Verweise auf `GUIALITA_STATE.yaml`, Bootstrap, Doctor und
  Test-Runner.
- Bootstrap ergänzt: Zu Sitzungsbeginn Arbeitskopie aktualisieren/verifizieren,
  danach State lesen; bei fehlender kurzlebiger Remote-Branch nicht auf `main`
  wechseln.
- `scripts/doctor.py` meldet `PyYAML (import yaml)` statt nur `yaml`.

### Offene Punkte

- Voice-Latenz-Nachmessung bleibt der empfohlene nächste echte Zielmaschinen-
  Schritt: `python3 scripts/measure_voice_turn.py --record --turns 3`.
- Keine neue Feature-Phase wurde implementiert.

## Nachvollziehbarkeitsregel

- Quellcodeänderungen werden über Git-Commits gespeichert.
- Test- und Diagnoseergebnisse werden in diesem Protokoll bzw. separaten
  Ergebnisdokumenten festgehalten.
- Eine Chat-Session oder interne Überlegungen werden nicht automatisch in Git
  geschrieben. Auf Wunsch wird pro Arbeitsabschnitt ein sachlicher Eintrag mit
  Ziel, Änderung, Evidenz und offenen Punkten ergänzt.
