# GUIALITA — PHASE MEMORY RETRIEVAL V1 RESULT

Kanonischer Ergebnisbericht der deterministischen Memory-Retrieval-Schicht.

Klassifikation: FACT, OBSERVED, VERIFIED, INFERENCE, PROPOSAL, UNKNOWN, KNOWN LIMITATION, DEFERRED.

## STATUS

`GUIALITA MEMORY RETRIEVAL V1 = PASS` (VERIFIED)

## Baseline

`GUIALITA MEMORY SESSION = PASS`

## New Capability

Deterministisches Feature-Hashing Retriever System, das Messages indiziert und
relevante ältere Informationen aus allen Sessions in den LLM-Kontext einfügt.

## Files Created

| Datei | Beschreibung |
|-------|-------------|
| `backend/memory/embed.py` | Deterministisches Feature-Hashing (512-D, numpy) |
| `backend/memory/retrieval.py` | MemoryIndexer, MemoryRetriever, ContextBuilder |
| `tests/test_memory_retrieval.py` | T01-T17 Tests (Unit + API + Regression) |
| `docs/PHASE_MEMORY_RETRIEVAL_RESULT.md` | Dieser Bericht |
| `docs/phase-memory-retrieval.yaml` | Maschinenlesbarer Bericht |

## Files Modified

| Datei | Änderung |
|-------|----------|
| `backend/memory/schema.py` | SCHEMA_VERSION 2, memories-Tabelle, Migration V1→V2 |
| `backend/memory/store.py` | insert_memory, get_memory, get_all_memories, count_memories, has_memory_for_message, get_message |
| `backend/chat_service.py` | Retrieval-Integration: MemoryIndexer + MemoryRetriever + ContextBuilder, Fallback bei Fehler |
| `backend/main.py` | GET /memory/status, POST /memory/search, retrieval in ChatResponse |
| `backend/models/schemas.py` | MemoryStatusResponse, MemorySearchResponse, MemorySearchResult, ChatResponse.retrieval |
| `config/memory.yaml` | memory.embedding + memory.retrieval Sektionen |
| `docs/GUIALITA_STATE.yaml` | memory_retrieval: PASS |
| `docs/GUIALITA_SESSION_BOOTSTRAP.md` | Memory-Retrieval-Abschnitt |
| `docs/GUIALITA_PHASE_STATUS.md` | MEMORY_RETRIEVAL = PASS |

## SQLite Schema (V2)

Neue Tabelle `memories`:

```sql
CREATE TABLE memories (
    id                  TEXT PRIMARY KEY,       -- MEM-<hex>
    source_message_id   TEXT NOT NULL REFERENCES messages(id),
    session_id          TEXT NOT NULL REFERENCES sessions(id),
    content             TEXT NOT NULL,
    embedding           BLOB NOT NULL,           -- numpy float64 bytes
    embedding_version   INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT NOT NULL,            -- UTC ISO-8601
    metadata_json       TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_memories_session ON memories (session_id, created_at);
CREATE INDEX idx_memories_source ON memories (source_message_id);
```

Bestehende Tabellen (sessions, messages) bleiben unverändert und abwärtskompatibel.

## Embedding System (VERIFIED)

Methode: Deterministisches Feature-Hashing (kein neuronales Modell).

Verfahren:
1. Tokenisierung (lowercase, Alpha-Numerisch Split)
2. Feature-Hashing (SHA-256 pro Token → Dimension 0..511)
3. TF-Gewichtung (Anzahl pro Dimension)
4. L2-Normalisierung
5. BLOB in SQLite

Eigenschaften:
- Deterministisch (gleicher Text → gleicher Vektor, VERIFIED T01)
- CPU-only, kein Netzwerk, kein Download
- Versioniert (embedding_version=1)
- 512 Dimensionen
- numpy float64 (4 KB pro Memory)

KNOWN LIMITATION: Dies ist KEIN neuronales semantisches Embedding.
Die Qualität hängt von Token-Overlap ab. Für komplexe semantische
Abfragen ist ein späteres neuronales Embedding überlegen.

## API Endpoints (VERIFIED)

| Endpoint | Methode | Beschreibung |
|----------|---------|-------------|
| `/memory/status` | GET | Embedding-Version, Memory-Anzahl, DB-Status |
| `/memory/search` | POST | Query-basierte Suche mit top_k, session_id |

ChatPipeline: POST /chat arbeitet automatisch mit Retrieval.
retrieval-Feld in der Response zeigt abgerufene Memories.

## Tests

### Unit Tests (T01-T10) — VERIFIED PASS

| Test | Ergebnis |
|------|----------|
| T01 Gleicher Text → identischer Vektor | PASS |
| T02 Unterschiedlicher Text → unterschiedlicher Vektor | PASS |
| T03 Message → Memory indiziert und abrufbar | PASS |
| T04 Relevante Query → relevantes Memory | PASS |
| T05 Irrelevantes rankt unter relevatem | PASS |
| T06 Min-Score schließt Schwache aus | PASS |
| T07 top_k begrenzt Ergebnisse | PASS |
| T08 Provenance erhalten | PASS |
| T09 Cross-Session Retrieval | PASS |
| T10 Memory überlebt DB-Neustart | PASS |

### API Tests (T11-T13) — VERIFIED PASS

| Test | Ergebnis |
|------|----------|
| T11 GET /memory/status | PASS |
| T12 POST /memory/search | PASS |
| T13 Retrieval-Fehler bricht Chat nicht | PASS |

### Regression — VERIFIED PASS

| Suite | Ergebnis |
|-------|----------|
| T14 test_memory.py | 16/16 PASS |
| T15 test_api.py | 18/18 PASS |
| T16 test_capture.py | 7/7 PASS |
| T17 test_process_audio.py | 13/13 PASS |

## Real E2E (VERIFIED)

1. Session A erstellt: "Mein Projekt heißt GUIALITA." gespeichert
2. 12 unzusammenhängende Nachrichten (Witze) → Session A: 26 Messages
   → Originale Nachricht weit außerhalb des 10er-History-Fensters
3. Backend stop.sh + start.sh (PID 2718051 → neu, Ollama 2492667 unverändert)
4. Session B (neue Session): "Wie heißt mein Projekt?"
5. System retrieved 4 Memories aus Session A:
   - score=0.75: "Mein Projekt heißt GUIALITA." (dreifach vorhanden durch Wiederholung)
   - score=0.17: ein Witz (niedriger Score)
6. LFM-Antwort: "Ihr Projekt heißt GUIALITA." — korrekt basierend auf Retrieval-Kontext
7. history_used: 5 (4 abgerufene Memories + 1 User-Nachricht Session B)
8. SQLite-Verifikation: Memories korrekt persistiert, Provenance zeigt auf Session A

INFERENCE: Die korrekte Antwort in Session B ist nur mit abgerufenem
Kontext aus Session A erklärbar. Die Originale Nachricht "Mein Projekt
heißt GUIALITA." befand sich außerhalb des 10er-History-Fensters.
Retrieval lieferte den fehlenden Kontext.

## Chat Pipeline (VERIFIED)

```
POST /chat
  ↓ validate request
  ↓ resolve/create session
  ↓ persist user message
  ↓ retrieve relevant older memories (brute-force cosine similarity)
  ↓ load recent session history
  ↓ build bounded context: [Memories] + [History]
  ↓ call ModelManager
  ↓ persist assistant response
  ↓ index both messages (user + assistant)
  ↓ return response with retrieval metadata
```

Bei Retrieval-Fehler: Fallback auf reine History (Chat funktioniert weiter).

## Konfiguration (config/memory.yaml)

```yaml
memory:
  enabled: true
  embedding:
    version: 1
    dimensions: 512
  retrieval:
    top_k: 4
    min_score: 0.15
    max_retrieval_chars: 6000
    scope: global
```

## Known Limitations

- Feature-Hashing ist KEIN neuronales semantisches Embedding.
  Qualität hängt von Token-Overlap ab (GER/ENG toleriert, aber
  keine echte Semantik).
- Brute-Force Suche (alle Memories linear). Bei >10k Memories
  wird dies langsam (dann Vektor-DB nötig, DEFERRED).
- Memories werden nur aus User/Assistant Messages erzeugt (nicht System).
- Keine Aktualisierung/ Löschung von Memories bei Session-Änderungen.
- Retrieve-Scope ist global (alle Sessions), Provenance zeigt Herkunft.

## Deferred

- Neuronales Embedding-Modell (wenn >10k Memories)
- Vektor-DB (FAISS/Chroma) für performantere Suche
- Memory-Aktualisierung und -Löschung
- Semantische Zusammenfassung älterer Memories
- Graph Memory / GraphRAG
- Vision / TTS / Browser Automation
- MUSCAL Integration

## Ollama

PID vorher: 2492667
PID nachher: 2492667
Unverändert.

## Dependencies

Keine neuen Python-Pakete installiert.
Nur numpy (bereits vorhanden) + sqlite3 (stdlib).

## HARD STOP

Memory-Retrieval V1 abgeschlossen.

Kein Graph Memory.
Kein GraphRAG.
Kein Vision.
Kein TTS.
Kein Browser Automation.
Kein MUSCAL.

Die nächste Phase erfordert explizite Autorisierung.
