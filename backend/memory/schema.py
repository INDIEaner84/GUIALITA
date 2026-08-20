"""GUIALITA Memory Foundation - Schema (SQLite, stdlib only).

V1: sessions + messages
V2: memories (Feature-Hashing Embeddings)
V3: entities + relations (Graph Foundation)

Idempotente Schema-Erzeugung. Keine destruktiven Migrationen.
exFAT-Regeln: KEIN WAL, Standard-Rollback-Journal, busy_timeout, Single-Writer-Lock.
"""

SCHEMA_VERSION = 3

DDL_V1 = """
CREATE TABLE IF NOT EXISTS schema_info (
    version    INTEGER NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL DEFAULT 'Neue Session',
    status        TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS messages (
    id            TEXT PRIMARY KEY,
    session_id    TEXT NOT NULL REFERENCES sessions(id),
    role          TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content       TEXT NOT NULL,
    model_id      TEXT,
    generation_id INTEGER,
    created_at    TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_messages_session
    ON messages (session_id, created_at);
"""

DDL_V2 = """
CREATE TABLE IF NOT EXISTS memories (
    id                  TEXT PRIMARY KEY,
    source_message_id   TEXT NOT NULL REFERENCES messages(id),
    session_id          TEXT NOT NULL REFERENCES sessions(id),
    content             TEXT NOT NULL,
    embedding           BLOB NOT NULL,
    embedding_version   INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT NOT NULL,
    metadata_json       TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_memories_session
    ON memories (session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_memories_source
    ON memories (source_message_id);
"""

DDL_V3 = """
CREATE TABLE IF NOT EXISTS entities (
    id                  TEXT PRIMARY KEY,
    canonical_name      TEXT NOT NULL,
    entity_type         TEXT NOT NULL DEFAULT 'concept',
    extraction_version  INTEGER NOT NULL DEFAULT 1,
    metadata_json       TEXT NOT NULL DEFAULT '{}',
    created_at          TEXT NOT NULL,
    UNIQUE(canonical_name, entity_type)
);

CREATE TABLE IF NOT EXISTS relations (
    id                  TEXT PRIMARY KEY,
    source_entity_id    TEXT NOT NULL REFERENCES entities(id),
    relation_type       TEXT NOT NULL,
    target_entity_id    TEXT NOT NULL REFERENCES entities(id),
    source_memory_id    TEXT NOT NULL REFERENCES memories(id),
    extraction_version  INTEGER NOT NULL DEFAULT 1,
    metadata_json       TEXT NOT NULL DEFAULT '{}',
    created_at          TEXT NOT NULL,
    UNIQUE(source_entity_id, relation_type, target_entity_id, source_memory_id)
);

CREATE INDEX IF NOT EXISTS idx_entities_name
    ON entities (canonical_name);
CREATE INDEX IF NOT EXISTS idx_entities_type
    ON entities (entity_type);
CREATE INDEX IF NOT EXISTS idx_relations_source
    ON relations (source_entity_id);
CREATE INDEX IF NOT EXISTS idx_relations_target
    ON relations (target_entity_id);
CREATE INDEX IF NOT EXISTS idx_relations_memory
    ON relations (source_memory_id);
"""


def ensure_schema(conn) -> None:
    """Erzeugt das Schema idempotent (mehrfacher Aufruf ist sicher)."""
    from datetime import datetime, timezone
    conn.executescript(DDL_V1)
    row = conn.execute("SELECT COUNT(*) FROM schema_info").fetchone()
    if row[0] == 0:
        conn.execute(
            "INSERT INTO schema_info (version, applied_at) VALUES (?, ?)",
            (1, datetime.now(timezone.utc).isoformat()),
        )
    ver = schema_version(conn)
    if ver < 2:
        conn.executescript(DDL_V2)
    if ver < 3:
        conn.executescript(DDL_V3)
    if ver < SCHEMA_VERSION:
        conn.execute(
            "UPDATE schema_info SET version = ?, applied_at = ?",
            (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
        )
    conn.commit()


def schema_version(conn) -> int:
    row = conn.execute("SELECT version FROM schema_info ORDER BY version DESC LIMIT 1").fetchone()
    return row[0] if row else 0