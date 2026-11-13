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

## Nachvollziehbarkeitsregel

- Quellcodeänderungen werden über Git-Commits gespeichert.
- Test- und Diagnoseergebnisse werden in diesem Protokoll bzw. separaten
  Ergebnisdokumenten festgehalten.
- Eine Chat-Session oder interne Überlegungen werden nicht automatisch in Git
  geschrieben. Auf Wunsch wird pro Arbeitsabschnitt ein sachlicher Eintrag mit
  Ziel, Änderung, Evidenz und offenen Punkten ergänzt.
