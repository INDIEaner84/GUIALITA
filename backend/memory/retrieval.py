"""GUIALITA Memory Graph Foundation - Deterministisches Memory-Retrieval + Graph.

Kernkomponente:
  - MemoryIndexer: Indiziert Messages → memories + entities + relations
  - MemoryRetriever: Brute-Force Cosine-Similarity Suche
  - ContextBuilder: Baut begrenzten Kontext (Memories + History)
  - GraphRetriever: 1-Hop-Traversal über Entitäten

Verfahren:
  1. Nachricht wird gepersistiert
  2. Indexierung: Tokenisierung → Feature-Hashing → BLOB in SQLite
  3. Entity-Extraktion → entities-Tabelle
  4. Relation-Extraktion → relations-Tabelle
  5. Suche: Cosine-Similarity aller Memories gegen Query
  6. Graph-Suche: 1-Hop-Traversal einer Entität
  7. Kontext: Top-k Memories + recent history → LLM

Kein neuronales Modell, kein Vektor-DB, kein GraphRAG.
Deterministisch, versioniert, sperrbar.
"""

import logging
import os
from typing import List, Optional, Set, Tuple

from .embed import EMBEDDING_VERSION, bytes_to_embedding, cosine_similarity, embed, embed_to_bytes
from .extractor import extract_entities, extract_relations

log = logging.getLogger("guialita.memory.retrieval")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Defaults (können durch config/memory.yaml überschrieben werden)
DEFAULT_TOP_K = 4
DEFAULT_MIN_SCORE = 0.15
DEFAULT_MAX_RETRIEVAL_CHARS = 6000
DEFAULT_DIMENSIONS = 512


def _load_config() -> dict:
    """Lädt retrieval-Konfiguration aus config/memory.yaml."""
    try:
        import yaml
        cfg_path = os.path.join(BASE_DIR, "config", "memory.yaml")
        if os.path.isfile(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception:
        pass
    return {}


class MemoryIndexer:
    """Indiziert Messages in die memories-Tabelle + Graph (entities/relations)."""

    def __init__(self, store):
        self.store = store

    def index_message(self, message: dict) -> Optional[dict]:
        """Indiziert eine einzelne Nachricht. Liefert memory dict oder None.

        Nach der Memory-Indizierung werden Entitäten und Beziehungen extrahiert.
        """
        role = message.get("role", "")
        content = (message.get("content") or "").strip()
        msg_id = message.get("id", "")
        session_id = message.get("session_id", "")

        if role not in ("user", "assistant"):
            return None
        if not content or not msg_id or not session_id:
            return None
        if self.store.has_memory_for_message(msg_id):
            return None

        embedding_bytes = embed_to_bytes(content, DEFAULT_DIMENSIONS)
        memory_id = f"MEM-{msg_id[4:]}" if msg_id.startswith("MSG-") else f"MEM-{msg_id}"

        result = self.store.insert_memory(
            memory_id=memory_id,
            source_message_id=msg_id,
            session_id=session_id,
            content=content,
            embedding=embedding_bytes,
            embedding_version=EMBEDDING_VERSION,
            metadata={"role": role, "model_id": message.get("model_id")},
        )

        if result:
            self._index_graph(content, memory_id)

        return result

    def _index_graph(self, content: str, memory_id: str) -> None:
        """Extrahiert und speichert Entitäten + Beziehungen für ein Memory."""
        try:
            entities, relations = extract_entities(content), []
            entity_names = {e["canonical_name"] for e in entities}
            if entity_names:
                relations = extract_relations(content, entity_names)

            entity_map: dict = {}
            for ent in entities:
                stored = self.store.upsert_entity(
                    canonical_name=ent["canonical_name"],
                    entity_type=ent["entity_type"],
                    extraction_version=ent["extraction_version"],
                )
                if stored:
                    entity_map[ent["canonical_name"]] = stored["id"]

            for rel in relations:
                src_id = entity_map.get(rel["source_name"])
                tgt_id = entity_map.get(rel["target_name"])
                if src_id and tgt_id and src_id != tgt_id:
                    self.store.upsert_relation(
                        source_entity_id=src_id,
                        relation_type=rel["relation_type"],
                        target_entity_id=tgt_id,
                        source_memory_id=memory_id,
                        extraction_version=rel["extraction_version"],
                    )
        except Exception as e:
            log.warning("Graph-Indizierung fehlgeschlagen für %s: %s", memory_id, e)

    def index_messages(self, messages: list) -> int:
        """Indiziert mehrere Messages. Liefert Anzahl erfolgreich indizierter."""
        count = 0
        for msg in messages:
            result = self.index_message(msg)
            if result:
                count += 1
        return count


class MemoryRetriever:
    """Brute-Force Cosine-Similarity Suche über alle Memories."""

    def __init__(self, store):
        self.store = store

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        min_score: float = DEFAULT_MIN_SCORE,
        exclude_message_ids: Optional[set] = None,
        exclude_session_ids: Optional[set] = None,
    ) -> list:
        """Sucht relevante Memories für eine Query.

        Args:
            query: Suchtext
            top_k: Maximalzahl Ergebnisse
            min_score: Mindest-Ähnlichkeit
            exclude_message_ids: Diese Message-IDs ausschließen
            exclude_session_ids: Diese Session-IDs ausschließen
        """
        if not query or not query.strip():
            return []

        query_embedding = embed(query, DEFAULT_DIMENSIONS)
        all_memories = self.store.get_all_memories()

        if not all_memories:
            return []

        exclude_msg = exclude_message_ids or set()
        exclude_sess = exclude_session_ids or set()

        scored: list = []
        for mem in all_memories:
            if mem["id"] in exclude_msg:
                continue
            if mem["session_id"] in exclude_sess:
                continue
            try:
                mem_embedding = bytes_to_embedding(mem["embedding"], DEFAULT_DIMENSIONS)
                score = cosine_similarity(query_embedding, mem_embedding)
            except Exception as e:
                log.warning("Embedding-Decode-Fehler für %s: %s", mem["id"], e)
                continue
            if score < min_score:
                continue
            scored.append({
                "memory_id": mem["id"],
                "source_message_id": mem["source_message_id"],
                "session_id": mem["session_id"],
                "content": mem["content"],
                "score": round(score, 4),
                "reason": "feature_hashing_similarity",
                "created_at": mem["created_at"],
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]


class ContextBuilder:
    """Baut begrenzten Kontext: Retrieved Memories + Recent History."""

    def __init__(self, store, top_k: int = None, min_score: float = None,
                 max_retrieval_chars: int = None):
        cfg = _load_config().get("memory", {}).get("retrieval", {})
        self.top_k = top_k or cfg.get("top_k", DEFAULT_TOP_K)
        self.min_score = min_score or cfg.get("min_score", DEFAULT_MIN_SCORE)
        self.max_retrieval_chars = max_retrieval_chars or cfg.get(
            "max_context_chars", DEFAULT_MAX_RETRIEVAL_CHARS
        )

    def build(
        self,
        query: str,
        current_session_id: str,
        recent_history: list,
        retriever: MemoryRetriever,
    ) -> Tuple[list, dict]:
        """Baut den vollständigen LLM-Kontext.

        Rückgabe:
          llm_messages: Liste der Nachrichten für das LLM
          retrieval_info: Metadaten über die Retrieval-Ergebnisse
        """
        recent_msg_ids = {m["id"] for m in recent_history}

        retrieved = retriever.search(
            query=query,
            top_k=self.top_k,
            min_score=self.min_score,
            exclude_message_ids=recent_msg_ids,
            exclude_session_ids={current_session_id},
        )

        total_chars = 0
        memory_messages: list = []
        for mem in retrieved:
            content = mem["content"]
            if total_chars + len(content) > self.max_retrieval_chars:
                break
            memory_messages.append({
                "role": "system",
                "content": f"[Relevante frühere Information] {content}",
            })
            total_chars += len(content) + 32

        llm_messages = memory_messages + [
            {"role": m["role"], "content": m["content"]}
            for m in recent_history
            if m["role"] in ("user", "assistant", "system")
        ]

        retrieval_info = {
            "retrieved_count": len(memory_messages),
            "total_candidates": len(retrieved),
            "top_k": self.top_k,
            "min_score": self.min_score,
            "max_retrieval_chars": self.max_retrieval_chars,
            "memories": retrieved[:len(memory_messages)],
        }

        return llm_messages, retrieval_info


class GraphRetriever:
    """1-Hop-Graph-Traversale für eine Entität."""

    def __init__(self, store):
        self.store = store

    def traverse(self, entity_name: str) -> dict:
        """1-Hop-Traversale für eine Entität nach Name.

        Liefert: {
            entity: {...},
            outgoing: [{relation, target, memory_content}],
            incoming: [{relation, source, memory_content}],
            entity_count, relation_count
        }
        """
        entity = self.store.get_entity_by_name(entity_name)
        if entity is None:
            return {
                "entity": None,
                "outgoing": [],
                "incoming": [],
                "entity_count": self.store.count_entities(),
                "relation_count": self.store.count_relations(),
            }

        rels = self.store.get_entity_relations(entity["id"])

        def _enrich(rel_list: list) -> list:
            result = []
            for r in rel_list:
                mem = self.store.get_memory(r.get("source_memory_id", ""))
                result.append({
                    "relation_id": r["id"],
                    "relation_type": r["relation_type"],
                    "source_entity_id": r["source_entity_id"],
                    "target_entity_id": r["target_entity_id"],
                    "target_name": r.get("target_name") or r.get("source_name", ""),
                    "target_type": r.get("target_type") or r.get("source_type", ""),
                    "source_memory_id": r["source_memory_id"],
                    "memory_content": mem["content"][:200] if mem else "",
                    "created_at": r["created_at"],
                })
            return result

        return {
            "entity": entity,
            "outgoing": _enrich(rels["outgoing"]),
            "incoming": _enrich(rels["incoming"]),
            "entity_count": self.store.count_entities(),
            "relation_count": self.store.count_relations(),
        }
