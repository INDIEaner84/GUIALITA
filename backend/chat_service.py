"""GUIALITA Memory Retrieval V1 - ChatService.

Zentrale Integrationsschicht zwischen API und ModelManager.

Flow:
    request
      ↓ session resolve
      ↓ user message persistieren
      ↓ retrieve relevant older memories
      ↓ recent history laden
      ↓ build bounded context (memories + history)
      ↓ LLM messages erzeugen
      ↓ bestehender ModelManager
      ↓ assistant response persistieren
      ↓ index messages (user + assistant)
      ↓ response

Bei Retrieval-Fehler: Fallback auf reine History (chat funktioniert weiter).
"""

import logging
import os
from typing import Optional

from backend.memory.retrieval import (
    ContextBuilder,
    MemoryIndexer,
    MemoryRetriever,
    DEFAULT_DIMENSIONS,
)

log = logging.getLogger("guialita.chat_service")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_RECENT_MESSAGES = 10
DEFAULT_MAX_CONTEXT_CHARS = 12000


class ChatService:
    """Wraps ModelManager mit persistenter Session-/Message-Historie + Retrieval."""

    def __init__(self, manager, store, recent_messages: int = None,
                 max_context_chars: int = None):
        self.manager = manager
        self.store = store
        self.recent_messages = recent_messages or self._load_recent_messages()
        self.max_context_chars = max_context_chars or DEFAULT_MAX_CONTEXT_CHARS
        self.indexer = MemoryIndexer(store)
        self.retriever = MemoryRetriever(store)
        self.context_builder = ContextBuilder(store)

    @staticmethod
    def _load_recent_messages() -> int:
        try:
            import yaml
            cfg_path = os.path.join(BASE_DIR, "config", "memory.yaml")
            if os.path.isfile(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                return int(cfg.get("chat", {}).get("recent_messages", DEFAULT_RECENT_MESSAGES))
        except Exception as e:
            log.warning("memory.yaml nicht lesbar (%s) - nutze Default %s",
                        e, DEFAULT_RECENT_MESSAGES)
        return DEFAULT_RECENT_MESSAGES

    # ------------------------------------------------------------------ public

    def chat(self, message: str, model_id: Optional[str] = None,
             session_id: Optional[str] = None, temperature: float = 0.7) -> dict:
        """Führt einen Chat aus. Ohne session_id wird eine neue Session erzeugt."""
        session = self._resolve_session(session_id)
        sid = session["id"]

        user_msg = self.store.append_message(
            sid, "user", message, model_id=model_id
        )

        history = self._load_history(sid)

        retrieval_info = None
        try:
            llm_messages, retrieval_info = self.context_builder.build(
                query=message,
                current_session_id=sid,
                recent_history=history,
                retriever=self.retriever,
            )
        except Exception as e:
            log.warning("Retrieval fehlgeschlagen, Fallback auf History: %s", e)
            llm_messages = [
                {"role": m["role"], "content": m["content"]}
                for m in history
                if m["role"] in ("user", "assistant", "system")
            ]

        try:
            result = self.manager.chat(
                message,
                model_id,
                messages=llm_messages,
                temperature=temperature,
            )
        except Exception:
            raise

        assistant_msg = self.store.append_message(
            sid, "assistant", result["response"],
            model_id=result.get("model_id") or model_id,
            metadata={
                "runtime": result.get("runtime", "llamacpp"),
                "latency_ms": result.get("latency_ms", 0.0),
                "load_ms": result.get("load_ms"),
                "inference_ms": result.get("inference_ms"),
            },
        )

        try:
            indexed = self.indexer.index_messages([user_msg, assistant_msg])
            if indexed > 0:
                log.info("%d Messages indiziert für Session %s", indexed, sid)
        except Exception as e:
            log.warning("Indexierung fehlgeschlagen (chat bleibt funktionsfähig): %s", e)

        return {
            "response": result["response"],
            "model": result["model"],
            "model_id": result.get("model_id") or model_id,
            "runtime": result.get("runtime", "llamacpp"),
            "latency_ms": result.get("latency_ms", 0.0),
            "session_id": sid,
            "session_status": session.get("status", "ACTIVE"),
            "message_id": assistant_msg["id"],
            "user_message_id": user_msg["id"],
            "history_used": len(llm_messages),
            "history_limit": self.recent_messages,
            "retrieval": retrieval_info,
        }

    def status(self) -> dict:
        """Liefert Memory-Status."""
        return {
            "enabled": True,
            "embedding_version": DEFAULT_DIMENSIONS,
            "memory_count": self.store.count_memories(),
            "database_available": True,
        }

    def search(self, query: str, top_k: int = 4,
               session_id: Optional[str] = None) -> list:
        """Sucht relevante Memories."""
        exclude = {session_id} if session_id else set()
        return self.retriever.search(
            query=query,
            top_k=top_k,
            exclude_session_ids=exclude,
        )

    # ------------------------------------------------------------------ internal

    def _resolve_session(self, session_id: Optional[str]) -> dict:
        if session_id:
            session = self.store.get_session(session_id)
            if session is None:
                raise KeyError(f"Unbekannte Session: {session_id}")
            return session
        return self.store.create_session()

    def _load_history(self, session_id: str) -> list:
        """Gebundelte recent history (Nachrichten + Zeichenlimit)."""
        messages = self.store.get_recent_messages(session_id, self.recent_messages)
        total = 0
        bounded: list = []
        for m in reversed(messages):
            total += len(m["content"]) + 16
            if total > self.max_context_chars and bounded:
                break
            bounded.append(m)
        bounded.reverse()
        return bounded
