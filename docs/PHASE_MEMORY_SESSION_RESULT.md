# GUIALITA — PHASE MEMORY SESSION RESULT

Kanonischer Ergebnisbericht der minimalen persistenten Session-Foundation.

Klassifikation: FACT (implementiert), OBSERVED (beobachtet), VERIFIED (geprüft),
INFERENCE (Schlussfolgerung), PROPOSAL (Vorschlag), UNKNOWN (unbekannt).

## STATUS

`GUIALITA MEMORY SESSION FOUNDATION = PASS` (VERIFIED)

## Ziel

Eine Unterhaltung mit dem lokalen LFM überlebt einen Backend-Neustart und
kann anschließend fortgesetzt werden (Session + Message + ChatService).

## DATEIEN ERSTELLT

| Datei | Inhalt | Klassifikation |
|-------|--------|----------------|
| `backend/memory/__init__.py` | Paket-Marker | FACT |
| `backend/memory/schema.py` | Schema V1 (idempotent, sqlite3 stdlib) | FACT |
| `backend/memory/store.py` | MemoryStore (Persistence, Thread-safe, Single-Writer-Lock) | FACT |
| `backend/chat_service.py` | ChatService (Session-Resolution, History, Persistenz) | FACT |
| `config/memory.yaml` | recent_messages=10, max_context_chars=12000 | FACT |
| `tests/test_memory.py` | T01–T15 (+T15b) | FACT |
| `docs/PHASE_MEMORY_SESSION_RESULT.md` | dieser Bericht | FACT |
| `docs/phase-memory-session.yaml` | maschinenlesbarer Bericht | FACT |
| `data/guialita.db` | SQLite-DB (automatisch zur Laufzeit erzeugt) | OBSERVED |

## DATEIEN GEÄNDERT

| Datei | Änderung | Klassifikation |
|-------|----------|----------------|
| `backend/models/schemas.py` | ChatRequest.session_id, ChatResponse +session_id/message_id/history_*, SessionResponse | FACT |
| `backend/main.py` | POST/GET /sessions, GET /sessions/{id}/messages, /chat via ChatService | FACT |
| `backend/adapters/base.py` | chat(..., messages=None) abwärtskompatibel | FACT |
| `backend/adapters/llamacpp_adapter.py` | messages=None → altes Verhalten; sonst History | FACT |
| `backend/adapters/ollama_adapter.py` | dito | FACT |
| `backend/manager.py` | chat(..., messages=None) Durchreichung | FACT |
| `frontend/index.html` | Session-Anzeige, ensureSession(), session_id mitsenden | FACT |
| `docs/GUIALITA_STATE.yaml`, `GUIALITA_PHASE_STATUS.md`, `GUIALITA_SESSION_BOOTSTRAP.md` | Status-Persistenz | FACT |

NICHT verändert: 1A/1B-Pipeline, LFM-Runtime, Whisper, Modelle, Ollama, Desktop-Starter, start/stop.sh.

## SQLITE-SCHEMA (V1)

FACT: `schema_info` (version, applied_at), `sessions` (id SES-<uuidhex>, title, status,
created_at, updated_at, metadata_json), `messages` (id MSG-<uuidhex>, session_id FK,
role CHECK user/assistant/system, content, model_id, generation_id, created_at,
metadata_json), Index `idx_messages_session(session_id, created_at)`.

VERIFIED: idempotente Initialisierung (mehrfacher Start unkritisch), Standard-Rollback-
Journal (kein WAL), `busy_timeout=5000`, `PRAGMA foreign_keys=ON`, Single-Writer-Lock,
Zeitstempel UTC ISO-8601, generation_id fortlaufend pro Session (1,2,3,…).

## TESTS

VERIFIED: `tests/test_memory.py` → **16/16 PASS**

| Test | Ergebnis |
|------|----------|
| T01 create_session | PASS |
| T02 persist_user_message | PASS |
| T03 persist_assistant_message | PASS |
| T04 database_close_reopen | PASS |
| T05 recover_session | PASS |
| T06 continue_recovered_session | PASS |
| T07 message_ordering | PASS |
| T08 session_isolation | PASS |
| T09 concurrent_append (4 Threads × 25) | PASS (100 Messages, eindeutige IDs, generation_id sortiert) |
| T10 duplicate_handling | PASS |
| T11 POST /sessions | PASS |
| T12 GET /sessions | PASS |
| T13 GET /sessions/{id}/messages | PASS |
| T14 /chat ohne session_id | PASS (Session auto-erzeugt) |
| T15 /chat mit session_id | PASS (2 Messages persistiert, history_used≥1) |
| T15b /chat unbekannte Session → 404 | PASS |

## KRITISCHER ECHTTEST (VERIFIED)

OBSERVED, vollständig durchgeführt:

1. Session erzeugt: `SES-26caaf19726146138874f924b79fbff2`
2. Runde 1: „Mein Projekt heißt GUIALITA.“ → LFM antwortet (history_used=1)
3. `stop.sh` → Backend-PID 2634780 beendet, Port frei, **Ollama (PID 2492667) lief weiter**
4. `start.sh` → Backend-PID 2636741 online
5. Runde 2 mit derselben session_id: „Wie heißt mein Projekt?“ → LFM: „Das Projekt heißt **GUIALITA**.“ (history_used=3)
6. SQLite-Verifikation: 4 Messages in korrekter Reihenfolge (user1 gen=1, assistant1 gen=2, user2 gen=3, assistant2 gen=4), alle model_id granite-3b

INFERENCE: Die korrekte Antwort in Runde 2 ist nur mit übergebener persistierter
History erklärbar (history_used=3 = user1+assistant1+user2). Die Antwort enthält
„GUIALITA“ aus Runde 1. Dies ist die Beobachtung; der kausale Beweis liegt in der
gemessenen History-Übergabe (FACT) und der modellseitigen Antwort (OBSERVED).

## REGRESSION (VERIFIED)

| Suite | Ergebnis |
|-------|----------|
| `tests/test_api.py` (Phase 0/0.5) | 18/18 PASS |
| `tests/test_capture.py` (Phase 1A) | 7/7 PASS |
| `tests/test_process_audio.py` (Phase 1B) | 13/13 PASS |
| /health, /models, /chat, /audio/* | unverändert funktionsfähig |
| Desktop-Starter, start.sh, stop.sh | unverändert |
| Ollama-PID | 2492667 vor und nach, unverändert |

## EINSCHRÄNKUNGEN

- Kein RAG, keine Embeddings, kein Graph, keine Vector DB (bewusst).
- history_used ≤ recent_messages (10) und Zeichenbudget 12000; ältere Nachrichten fallen aus dem Kontext (bleiben aber in der DB).
- Kontext = reine Nachrichten-Historie; keine semantische Zusammenfassung.
- /audio/chat nutzt weiterhin den bisherigen Pfad (keine Session-Integration in dieser Phase).

## RISIKEN

- exFAT + SQLite: kein WAL; Journal-Dateien können bei hartem Abbruch zurückbleiben
  (SQLite ist darauf ausgelegt; Datenbestand bleibt konsistent).
- Zwei gleichzeitige Backend-Instanzen könnten dieselbe DB beschreiben
  (Single-Writer-Lock ist pro Prozess). Backend ist als Einzelprozess ausgelegt.
- Gesamtgröße der DB wächst mit Session-Zahl (derzeit ~14 Messages — unbedeutend).

## NÄCHSTE SINNVOLLE PHASE (PROPOSAL, nicht gestartet)

Memory-Retrieval (RAG, deterministisch) als nächste Stufe — nur nach expliziter
Anweisung. HARD STOP eingehalten.