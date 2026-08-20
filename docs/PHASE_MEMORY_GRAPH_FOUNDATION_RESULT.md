# GUIALITA — PHASE MEMORY GRAPH FOUNDATION RESULT

Kanonischer Ergebnisbericht der Graph-Foundation-Schicht.

Klassifikation: FACT, OBSERVED, VERIFIED, INFERENCE, PROPOSAL, UNKNOWN, KNOWN LIMITATION, DEFERRED.

## STATUS

`GUIALITA MEMORY GRAPH FOUNDATION = PASS` (VERIFIED)

## Baseline

`GUIALITA-MEMORY-RETRIEVAL-V1-PASS`

## New Capability

Persistente Graph-Darstellung (Entitäten + Beziehungen) über der bestehenden
Memory-Schicht. Deterministische Entity-Extraktion, 1-Hop-Traversale, Provenance.

## Files Created

| Datei | Beschreibung |
|-------|-------------|
| `backend/memory/extractor.py` | Deterministischer Entity/Relations-Extraktor |
| `tests/test_memory_graph.py` | T01-T14 Tests (Unit + API + Regression) |
| `docs/PHASE_MEMORY_GRAPH_FOUNDATION_RESULT.md` | Dieser Bericht |
| `docs/phase-memory-graph-foundation.yaml` | Maschinenlesbarer Bericht |

## Files Modified

| Datei | Änderung |
|-------|----------|
| `backend/memory/schema.py` | SCHEMA_VERSION=3, entities + relations Tabellen, Migration V2→V3 |
| `backend/memory/store.py` | upsert_entity, get_entity, search_entities, upsert_relation, get_entity_relations, count_entities, count_relations |
| `backend/memory/retrieval.py` | MemoryIndexer integriert Graph-Indizierung, GraphRetriever (1-Hop) |
| `backend/main.py` | GET /memory/graph/{entity_name}, /memory/status erweitert |
| `backend/models/schemas.py` | MemoryStatusResponse + entity_count, relation_count |
| `docs/GUIALITA_STATE.yaml` | memory_graph: PASS |
| `docs/GUIALITA_SESSION_BOOTSTRAP.md` | Graph-Foundation-Abschnitt |
| `docs/GUIALITA_PHASE_STATUS.md` | MEMORY_GRAPH = PASS |

## SQLite Schema (V3)

Neue Tabellen:

```sql
CREATE TABLE entities (
    id                  TEXT PRIMARY KEY,       -- ENT-<hex>
    canonical_name      TEXT NOT NULL,
    entity_type         TEXT NOT NULL DEFAULT 'concept',
    extraction_version  INTEGER NOT NULL DEFAULT 1,
    metadata_json       TEXT NOT NULL DEFAULT '{}',
    created_at          TEXT NOT NULL,
    UNIQUE(canonical_name, entity_type)
);

CREATE TABLE relations (
    id                  TEXT PRIMARY KEY,       -- REL-<hex>
    source_entity_id    TEXT NOT NULL REFERENCES entities(id),
    relation_type       TEXT NOT NULL,
    target_entity_id    TEXT NOT NULL REFERENCES entities(id),
    source_memory_id    TEXT NOT NULL REFERENCES memories(id),
    extraction_version  INTEGER NOT NULL DEFAULT 1,
    metadata_json       TEXT NOT NULL DEFAULT '{}',
    created_at          TEXT NOT NULL,
    UNIQUE(source_entity_id, relation_type, target_entity_id, source_memory_id)
);
```

## Entity-Extraktion (VERIFIED)

Deterministisch, regelbasiert. Methoden:
1. Wortschatz-Abgleich (53 bekannte GUIALITA-Begriffe)
2. Anführungszeichen-Extraktion ("Term" / „Term")
3. Datei-Pfad-Erkennung
4. Konservative Großbuchstaben-Erkennung

KNOWN LIMITATION: Die Großbuchstaben-Erkennung erzeugt False Positives
(für "Sehr", "Mein", "Wie" etc.). Dies ist dokumentiert und akzeptabel.
Der Wortschatz-Abgleich liefert die präzisesten Ergebnisse.

## Relation-Typen

Kontrollierter Vokabular:
- `uses` — X nutzt Y
- `is_a` — X ist ein Y
- `has` — X hat Y
- `related_to` — X und Y sind verwandt (Co-occurrence Fallback)

## API Endpoints (VERIFIED)

| Endpoint | Methode | Beschreibung |
|----------|---------|-------------|
| `/memory/graph/{entity_name}` | GET | 1-Hop-Traversale einer Entität |
| `/memory/status` | GET | Erweitert um entity_count, relation_count |

## Tests

### Unit Tests (T01-T10) — VERIFIED PASS

| Test | Ergebnis |
|------|----------|
| T01 Entity Creation | PASS |
| T02 Duplicate Normalization | PASS |
| T03 Relation Creation | PASS |
| T04 Relation Deduplication | PASS |
| T05 Provenance Preservation | PASS |
| T06 Entity Extraction | PASS |
| T07 Relation Extraction | PASS |
| T08 1-Hop Traversal | PASS |
| T09 Irrelevant Entity | PASS |
| T10 Persistence After Reopen | PASS |

### API Tests (T11-T12) — VERIFIED PASS

| Test | Ergebnis |
|------|----------|
| T11 /memory/status mit Graph | PASS |
| T12 /memory/graph/{entity} | PASS |

### Regression — VERIFIED PASS

| Suite | Ergebnis |
|-------|----------|
| T13 test_memory_retrieval.py | 13/13 PASS |
| T14 test_memory.py | 16/16 PASS |
| test_api.py | 18/18 PASS |
| test_capture.py | 7/7 PASS |
| test_process_audio.py | 13/13 PASS |

## Real E2E (VERIFIED)

1. Memory gepseed: "GUIALITA uses Granite for everything."
2. Graph-Query: GET /memory/graph/GUIALITA
   - Entity: GUIALITA (project)
   - Outgoing: GUIALITA → uses → granite (score: korrekt)
   - 22 outgoing relations (inkl. Co-occurrence)
3. Backend stop.sh + start.sh
4. Post-Restart Query: gleiche Entity, gleiche Relationen
5. PERSISTED: YES — Graph überlebt Neustart

## Chat Pipeline

Graph-Indizierung ist integriert in MemoryIndexer:
  Memory → Entity-Extraktion → Entity-Registration → Relation-Registration

Graph-Retrieval ist OPTIONAL / INSPECTABLE:
  GET /memory/graph/{entity} — nicht automatisch im LLM-Kontext.

Bestehende Retrieval-Pipeline (Feature-Hashing) bleibt unverändert.

## Known Limitations

- False Positives bei der Großbuchstaben-Erkennung (dokumentiert)
- Co-occurrence erzeugt viele `related_to` Relationen
- 1-Hop-Traversale nur (keine Multi-Hop)
- Keine semantische Reasoning
- Keine Graph-Inferenz
- Keine autonomes Synthese

## Deferred

- GraphRAG (Query über Graph + LLM)
- Multi-Hop-Traversale
- Semantische Relation-Extraktion (via LLM)
- Entity-Löschung und -Aktualisierung
- Graph-Visualisierung
- Vision / TTS / Browser Automation
- MUSCAL Integration

## Dependencies

Keine neuen Python-Pakete installiert.
Nur numpy (bereits vorhanden) + sqlite3 (stdlib).

## Ollama

PID vorher: 2492667
PID nachher: 2492667
Unverändert.

## HARD STOP

Memory Graph Foundation V1 abgeschlossen.

Kein GraphRAG.
Kein Vision.
Kein TTS.
Kein Browser Automation.
Kein MUSCAL.

Die nächste Phase erfordert explizite Autorisierung.
