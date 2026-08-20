"""GUIALITA Memory Foundation - Persistenz-Store (SQLite, stdlib only).

Reine Persistence-Schicht. Kennt weder LFM, Granite, Ollama noch Audio.
Thread-sicher via Single-Writer-Lock. Standard-Rollback-Journal (kein WAL).
"""

import json
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from .. import paths
from .schema import ensure_schema

log = logging.getLogger("guialita.memory")

BASE_DIR = paths.root()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


class MemoryStore:
    """SQLite-basierter Store für Sessions und Messages (Schema V1)."""

    def __init__(self, db_path: Optional[str] = None):
        # Vorrang: expliziter Parameter > GUIALITA_DB > GUIALITA_DATA_ROOT
        self.db_path = db_path or os.environ.get(
            "GUIALITA_DB", os.path.join(paths.data_root(), "guialita.db")
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=10,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout = 5000")
        self._conn.execute("PRAGMA foreign_keys = ON")
        with self._lock:
            ensure_schema(self._conn)
        log.info("MemoryStore bereit: %s", self.db_path)

    # ------------------------------------------------------------------ helpers

    def _fetch(self, sql: str, params: tuple = ()) -> Optional[dict]:
        row = self._conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def _fetch_all(self, sql: str, params: tuple = ()) -> list:
        return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    # ------------------------------------------------------------------ sessions

    def create_session(self, title: str = "Neue Session") -> dict:
        sid = new_id("SES")
        ts = _now()
        with self._lock:
            self._conn.execute(
                "INSERT INTO sessions (id, title, status, created_at, updated_at, metadata_json)"
                " VALUES (?, ?, 'ACTIVE', ?, ?, '{}')",
                (sid, title, ts, ts),
            )
            self._conn.commit()
        return self.get_session(sid)

    def get_session(self, session_id: str) -> Optional[dict]:
        return self._fetch("SELECT * FROM sessions WHERE id = ?", (session_id,))

    def list_sessions(self, limit: int = 50) -> list:
        return self._fetch_all(
            "SELECT id, title, status, created_at, updated_at, metadata_json"
            " FROM sessions ORDER BY updated_at DESC LIMIT ?",
            (int(limit),),
        )

    def update_session(self, session_id: str, title: Optional[str] = None,
                       status: Optional[str] = None) -> Optional[dict]:
        fields, params = [], []
        if title is not None:
            fields.append("title = ?")
            params.append(title)
        if status is not None:
            fields.append("status = ?")
            params.append(status)
        if not fields:
            return self.get_session(session_id)
        fields.append("updated_at = ?")
        params.append(_now())
        params.append(session_id)
        with self._lock:
            cur = self._conn.execute(
                f"UPDATE sessions SET {', '.join(fields)} WHERE id = ?", tuple(params)
            )
            self._conn.commit()
        return self.get_session(session_id) if cur.rowcount else None

    # ------------------------------------------------------------------ messages

    def append_message(self, session_id: str, role: str, content: str,
                       model_id: Optional[str] = None,
                       generation_id: Optional[int] = None,
                       metadata: Optional[dict] = None) -> Optional[dict]:
        """Hängt eine Nachricht an. generation_id wird automatisch fortlaufend vergeben."""
        if role not in ("user", "assistant", "system"):
            raise ValueError(f"Ungültige Rolle: {role}")
        mid = new_id("MSG")
        ts = _now()
        with self._lock:
            session = self._conn.execute(
                "SELECT id FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if session is None:
                return None
            if generation_id is None:
                row = self._conn.execute(
                    "SELECT COALESCE(MAX(generation_id), 0) + 1 AS next"
                    " FROM messages WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                generation_id = int(row["next"])
            self._conn.execute(
                "INSERT INTO messages (id, session_id, role, content, model_id,"
                " generation_id, created_at, metadata_json)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (mid, session_id, role, content, model_id, generation_id, ts,
                 json.dumps(metadata or {}, ensure_ascii=False)),
            )
            self._conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?", (ts, session_id)
            )
            self._conn.commit()
        return self._fetch(
            "SELECT id, session_id, role, content, model_id, generation_id,"
            " created_at, metadata_json FROM messages WHERE id = ?",
            (mid,),
        )

    def get_messages(self, session_id: str, limit: Optional[int] = None) -> list:
        sql = ("SELECT id, session_id, role, content, model_id, generation_id,"
               " created_at, metadata_json FROM messages"
               " WHERE session_id = ? ORDER BY generation_id ASC, created_at ASC")
        params: tuple = (session_id,)
        if limit is not None:
            sql += " LIMIT ?"
            params = (session_id, int(limit))
        return self._fetch_all(sql, params)

    def get_recent_messages(self, session_id: str, n: int = 10) -> list:
        """Letzte n Nachrichten einer Session (aufsteigend sortiert)."""
        rows = self._fetch_all(
            "SELECT id, session_id, role, content, model_id, generation_id,"
            " created_at, metadata_json FROM messages"
            " WHERE session_id = ? ORDER BY generation_id DESC, created_at DESC LIMIT ?",
            (session_id, int(n)),
        )
        rows.reverse()
        return rows

    def count_messages(self, session_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS c FROM messages WHERE session_id = ?", (session_id,)
        ).fetchone()
        return int(row["c"])

    # ------------------------------------------------------------------ misc

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass

    # ------------------------------------------------------------------ memories

    def insert_memory(self, memory_id: str, source_message_id: str,
                      session_id: str, content: str, embedding: bytes,
                      embedding_version: int = 1,
                      metadata: Optional[dict] = None) -> Optional[dict]:
        """Speichert ein Memory mit Embedding (BLOB)."""
        ts = _now()
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO memories (id, source_message_id, session_id,"
                    " content, embedding, embedding_version, created_at, metadata_json)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (memory_id, source_message_id, session_id, content,
                     embedding, embedding_version, ts,
                     json.dumps(metadata or {}, ensure_ascii=False)),
                )
                self._conn.commit()
                return self._fetch(
                    "SELECT id, source_message_id, session_id, content,"
                    " embedding_version, created_at, metadata_json"
                    " FROM memories WHERE id = ?", (memory_id,),
                )
            except Exception as e:
                log.warning("insert_memory fehlgeschlagen: %s", e)
                return None

    def get_memory(self, memory_id: str) -> Optional[dict]:
        return self._fetch(
            "SELECT id, source_message_id, session_id, content,"
            " embedding_version, created_at, metadata_json"
            " FROM memories WHERE id = ?", (memory_id,),
        )

    def get_all_memories(self) -> list:
        """Alle Memories mit Embedding (für Brute-Force Suche)."""
        rows = self._fetch_all(
            "SELECT id, source_message_id, session_id, content,"
            " embedding, embedding_version, created_at, metadata_json"
            " FROM memories ORDER BY created_at ASC"
        )
        return rows

    def count_memories(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS c FROM memories").fetchone()
        return int(row["c"])

    def has_memory_for_message(self, message_id: str) -> bool:
        """Prüft ob ein Memory für eine bestimmte Message existiert."""
        row = self._conn.execute(
            "SELECT COUNT(*) AS c FROM memories WHERE source_message_id = ?",
            (message_id,),
        ).fetchone()
        return int(row["c"]) > 0

    def get_message(self, message_id: str) -> Optional[dict]:
        """Einzelne Message nach ID."""
        return self._fetch(
            "SELECT id, session_id, role, content, model_id, generation_id,"
            " created_at, metadata_json FROM messages WHERE id = ?",
            (message_id,),
        )

    # ------------------------------------------------------------------ graph: entities

    def upsert_entity(self, canonical_name: str, entity_type: str = "concept",
                      extraction_version: int = 1,
                      metadata: Optional[dict] = None) -> Optional[dict]:
        """Insert-or-get Entity (Normalisierung via UNIQUE)."""
        ts = _now()
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT OR IGNORE INTO entities (id, canonical_name, entity_type,"
                    " extraction_version, metadata_json, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (new_id("ENT"), canonical_name, entity_type, extraction_version,
                     json.dumps(metadata or {}, ensure_ascii=False), ts),
                )
                self._conn.commit()
            except Exception as e:
                log.warning("upsert_entity fehlgeschlagen: %s", e)
                return None
        return self._fetch(
            "SELECT id, canonical_name, entity_type, extraction_version,"
            " metadata_json, created_at FROM entities"
            " WHERE canonical_name = ? AND entity_type = ?",
            (canonical_name, entity_type),
        )

    def get_entity(self, entity_id: str) -> Optional[dict]:
        return self._fetch(
            "SELECT id, canonical_name, entity_type, extraction_version,"
            " metadata_json, created_at FROM entities WHERE id = ?",
            (entity_id,),
        )

    def get_entity_by_name(self, canonical_name: str,
                           entity_type: Optional[str] = None) -> Optional[dict]:
        if entity_type:
            return self._fetch(
                "SELECT id, canonical_name, entity_type, extraction_version,"
                " metadata_json, created_at FROM entities"
                " WHERE canonical_name = ? AND entity_type = ?",
                (canonical_name, entity_type),
            )
        return self._fetch(
            "SELECT id, canonical_name, entity_type, extraction_version,"
            " metadata_json, created_at FROM entities WHERE canonical_name = ?",
            (canonical_name,),
        )

    def search_entities(self, query: str, limit: int = 10) -> list:
        """Sucht Entitäten nach Name (prefix + substring match)."""
        return self._fetch_all(
            "SELECT id, canonical_name, entity_type, extraction_version,"
            " metadata_json, created_at FROM entities"
            " WHERE canonical_name LIKE ? OR canonical_name LIKE ?"
            " ORDER BY canonical_name LIMIT ?",
            (f"%{query}%", f"{query}%", int(limit)),
        )

    def count_entities(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS c FROM entities").fetchone()
        return int(row["c"])

    # ------------------------------------------------------------------ graph: relations

    def upsert_relation(self, source_entity_id: str, relation_type: str,
                        target_entity_id: str, source_memory_id: str,
                        extraction_version: int = 1,
                        metadata: Optional[dict] = None) -> Optional[dict]:
        """Insert-or-get Relation (Normalisierung via UNIQUE)."""
        ts = _now()
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT OR IGNORE INTO relations (id, source_entity_id,"
                    " relation_type, target_entity_id, source_memory_id,"
                    " extraction_version, metadata_json, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (new_id("REL"), source_entity_id, relation_type,
                     target_entity_id, source_memory_id, extraction_version,
                     json.dumps(metadata or {}, ensure_ascii=False), ts),
                )
                self._conn.commit()
            except Exception as e:
                log.warning("upsert_relation fehlgeschlagen: %s", e)
                return None
        return self._fetch(
            "SELECT id, source_entity_id, relation_type, target_entity_id,"
            " source_memory_id, extraction_version, metadata_json, created_at"
            " FROM relations"
            " WHERE source_entity_id = ? AND relation_type = ?"
            " AND target_entity_id = ? AND source_memory_id = ?",
            (source_entity_id, relation_type, target_entity_id, source_memory_id),
        )

    def get_entity_relations(self, entity_id: str) -> list:
        """Holt alle 1-Hop-Relationen (outgoing + incoming) einer Entity."""
        outgoing = self._fetch_all(
            "SELECT r.id, r.source_entity_id, r.relation_type,"
            " r.target_entity_id, r.source_memory_id, r.extraction_version,"
            " r.metadata_json, r.created_at,"
            " e.canonical_name AS target_name, e.entity_type AS target_type"
            " FROM relations r"
            " JOIN entities e ON e.id = r.target_entity_id"
            " WHERE r.source_entity_id = ?"
            " ORDER BY r.created_at ASC",
            (entity_id,),
        )
        incoming = self._fetch_all(
            "SELECT r.id, r.source_entity_id, r.relation_type,"
            " r.target_entity_id, r.source_memory_id, r.extraction_version,"
            " r.metadata_json, r.created_at,"
            " e.canonical_name AS source_name, e.entity_type AS source_type"
            " FROM relations r"
            " JOIN entities e ON e.id = r.source_entity_id"
            " WHERE r.target_entity_id = ?"
            " ORDER BY r.created_at ASC",
            (entity_id,),
        )
        return {"outgoing": outgoing, "incoming": incoming}

    def count_relations(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS c FROM relations").fetchone()
        return int(row["c"])

    # ------------------------------------------------------------------ graph: full bounded graph

    def get_bounded_graph(self, max_nodes: int = 100, max_edges: int = 250) -> dict:
        """Liefert den gesamten Graphen begrenzt (für Visualisierung)."""
        total_entities = self.count_entities()
        total_relations = self.count_relations()

        nodes_raw = self._fetch_all(
            "SELECT id, canonical_name, entity_type FROM entities"
            " ORDER BY canonical_name LIMIT ?",
            (int(max_nodes),),
        )
        node_ids = [n["id"] for n in nodes_raw]

        if not node_ids:
            return {
                "nodes": [], "edges": [], "truncated": total_entities > 0,
                "entity_count": total_entities, "relation_count": total_relations,
                "displayed_nodes": 0, "displayed_edges": 0,
            }

        placeholders = ",".join("?" * len(node_ids))
        edges_raw = self._fetch_all(
            f"SELECT r.id, r.source_entity_id, r.relation_type,"
            f" r.target_entity_id, r.source_memory_id"
            f" FROM relations r"
            f" WHERE r.source_entity_id IN ({placeholders})"
            f" AND r.target_entity_id IN ({placeholders})"
            f" ORDER BY r.created_at ASC LIMIT ?",
            (*node_ids, *node_ids, int(max_edges)),
        )

        truncated = total_entities > max_nodes or total_relations > max_edges

        return {
            "nodes": [{"id": n["id"], "label": n["canonical_name"],
                        "entity_type": n["entity_type"]} for n in nodes_raw],
            "edges": [{"id": e["id"], "source": e["source_entity_id"],
                        "target": e["target_entity_id"],
                        "relation": e["relation_type"],
                        "source_memory_id": e["source_memory_id"]}
                       for e in edges_raw],
            "truncated": truncated,
            "entity_count": total_entities,
            "relation_count": total_relations,
            "displayed_nodes": len(nodes_raw),
            "displayed_edges": len(edges_raw),
        }