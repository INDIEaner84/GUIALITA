"""Mock end-to-end tests for text/voice-equivalent ChatService flow."""
import tempfile
import unittest
from pathlib import Path

from backend.chat_service import ChatService
from backend.memory.store import MemoryStore


class FakeManager:
    default_model = "fake-1b"

    def __init__(self):
        self.calls = []

    def chat(self, message, model_id=None, messages=None, **kwargs):
        self.calls.append({"message": message, "messages": messages or []})
        return {
            "response": f"FAKE: {message}",
            "model": model_id or self.default_model,
            "model_id": model_id or self.default_model,
            "runtime": "fake",
            "latency_ms": 1.0,
        }


class TestMockChatPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(str(Path(self.tmp.name) / "test.db"))
        self.manager = FakeManager()
        self.service = ChatService(self.manager, self.store)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_first_turn_persists_and_returns_session(self):
        result = self.service.chat("Mein Projekt heißt GUIALITA.")
        self.assertTrue(result["session_id"])
        self.assertEqual(result["response"], "FAKE: Mein Projekt heißt GUIALITA.")
        self.assertEqual(self.store.count_messages(result["session_id"]), 2)

    def test_second_turn_reuses_history(self):
        first = self.service.chat("Mein Projekt heißt GUIALITA.")
        second = self.service.chat("Wie heißt mein Projekt?", session_id=first["session_id"])
        self.assertEqual(second["session_id"], first["session_id"])
        self.assertGreaterEqual(second["history_used"], 3)
        self.assertEqual(self.store.count_messages(first["session_id"]), 4)
        self.assertGreaterEqual(len(self.manager.calls[1]["messages"]), 3)

    def test_unknown_session_is_rejected(self):
        with self.assertRaises(KeyError):
            self.service.chat("test", session_id="SES-does-not-exist")


if __name__ == "__main__":
    unittest.main(verbosity=2)
