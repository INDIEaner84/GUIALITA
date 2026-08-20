"""GUIALITA Memory Foundation - Testsuite (T01-T15).

Unit-Tests (T01-T10): MemoryStore direkt, eigene temporäre DB.
API-Tests (T11-T15): gegen laufendes Backend (http://localhost:8080).
T16 (echter Backend-Neustart) wird manuell verifiziert (docs/PHASE_MEMORY_SESSION_RESULT.md).
"""

import os
import sys
import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

BASE_URL = os.environ.get("GUIALITA_URL", "http://localhost:8080")

from backend.memory.store import MemoryStore  # noqa: E402


def http_get(path: str):
    req = urllib.request.Request(BASE_URL + path)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, json.loads(r.read().decode())


def http_post(path: str, payload: dict):
    req = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.status, json.loads(r.read().decode())


class TestStoreUnit(unittest.TestCase):
    """T01-T10: Store-Ebene, temporäre DB."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="guialita_mem_")
        self.db_path = os.path.join(self.tmp, "test.db")
        self.store = MemoryStore(self.db_path)

    def tearDown(self):
        self.store.close()
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_t01_create_session(self):
        s = self.store.create_session()
        self.assertTrue(s["id"].startswith("SES-"))
        self.assertEqual(s["status"], "ACTIVE")
        self.assertEqual(s["created_at"], s["updated_at"])

    def test_t02_persist_user_message(self):
        s = self.store.create_session()
        m = self.store.append_message(s["id"], "user", "Hallo")
        self.assertTrue(m["id"].startswith("MSG-"))
        self.assertEqual(m["role"], "user")
        self.assertEqual(m["content"], "Hallo")
        self.assertEqual(m["generation_id"], 1)

    def test_t03_persist_assistant_message(self):
        s = self.store.create_session()
        u = self.store.append_message(s["id"], "user", "Hallo")
        a = self.store.append_message(s["id"], "assistant", "Hi", model_id="granite-3b")
        self.assertTrue(a["id"].startswith("MSG-"))
        self.assertEqual(a["role"], "assistant")
        self.assertEqual(a["generation_id"], 2)
        self.assertEqual(a["model_id"], "granite-3b")
        self.assertEqual(self.store.count_messages(s["id"]), 2)

    def test_t04_database_close_reopen(self):
        s = self.store.create_session()
        self.store.append_message(s["id"], "user", "Nachricht vor Neustart")
        self.store.append_message(s["id"], "assistant", "Antwort vor Neustart")
        self.store.close()
        reopened = MemoryStore(self.db_path)
        try:
            self.assertEqual(reopened.count_messages(s["id"]), 2)
        finally:
            reopened.close()

    def test_t05_recover_session(self):
        s = self.store.create_session()
        self.store.close()
        reopened = MemoryStore(self.db_path)
        try:
            got = reopened.get_session(s["id"])
            self.assertIsNotNone(got)
            self.assertEqual(got["id"], s["id"])
        finally:
            reopened.close()

    def test_t06_continue_recovered_session(self):
        s = self.store.create_session()
        self.store.append_message(s["id"], "user", "Alt")
        self.store.append_message(s["id"], "assistant", "Antwort")
        self.store.close()
        reopened = MemoryStore(self.db_path)
        try:
            reopened.append_message(s["id"], "user", "Neu")
            msgs = reopened.get_messages(s["id"])
            self.assertEqual(len(msgs), 3)
            self.assertEqual([m["role"] for m in msgs], ["user", "assistant", "user"])
            self.assertEqual([m["generation_id"] for m in msgs], [1, 2, 3])
        finally:
            reopened.close()

    def test_t07_message_ordering(self):
        s = self.store.create_session()
        for i in range(5):
            self.store.append_message(s["id"], "user" if i % 2 == 0 else "assistant", f"m{i}")
        msgs = self.store.get_messages(s["id"])
        self.assertEqual([m["content"] for m in msgs], ["m0", "m1", "m2", "m3", "m4"])
        recent = self.store.get_recent_messages(s["id"], 3)
        self.assertEqual([m["content"] for m in recent], ["m2", "m3", "m4"])

    def test_t08_session_isolation(self):
        a = self.store.create_session()
        b = self.store.create_session()
        self.store.append_message(a["id"], "user", "nur A")
        self.assertEqual(self.store.count_messages(a["id"]), 1)
        self.assertEqual(self.store.count_messages(b["id"]), 0)
        self.assertEqual(self.store.get_messages(b["id"]), [])

    def test_t09_concurrent_append(self):
        s = self.store.create_session()
        errors = []

        def worker(n):
            try:
                for i in range(25):
                    self.store.append_message(s["id"], "user", f"t{n}-{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(self.store.count_messages(s["id"]), 100)
        ids = [m["id"] for m in self.store.get_messages(s["id"])]
        self.assertEqual(len(ids), len(set(ids)), "Keine doppelten Message-IDs")
        gens = [m["generation_id"] for m in self.store.get_messages(s["id"])]
        self.assertEqual(gens, sorted(gens), "generation_id fortlaufend, kollisionsfrei")

    def test_t10_duplicate_handling(self):
        s = self.store.create_session()
        m1 = self.store.append_message(s["id"], "user", "duplikat")
        m2 = self.store.append_message(s["id"], "user", "duplikat")
        self.assertNotEqual(m1["id"], m2["id"])
        self.assertEqual(self.store.count_messages(s["id"]), 2)


class TestMemoryAPI(unittest.TestCase):
    """T11-T15: API-Ebene gegen laufendes Backend."""

    def test_t11_post_sessions(self):
        status, data = http_post("/sessions", {})
        self.assertEqual(status, 200)
        self.assertTrue(data["session_id"].startswith("SES-"))
        self.assertEqual(data["status"], "ACTIVE")

    def test_t12_get_sessions(self):
        _, data = http_get("/sessions")
        self.assertIn("sessions", data)
        self.assertGreaterEqual(len(data["sessions"]), 1)
        first = data["sessions"][0]
        self.assertIn("id", first)
        self.assertIn("created_at", first)

    def test_t13_get_session_messages(self):
        _, created = http_post("/sessions", {})
        sid = created["session_id"]
        status, data = http_get(f"/sessions/{sid}/messages")
        self.assertEqual(status, 200)
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["messages"], [])
        self.assertEqual(data["session"]["id"], sid)

    def test_t14_chat_without_session_id(self):
        status, data = http_post("/chat", {"message": "Sag nur: OK", "model": "granite-3b"})
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["session_id"].startswith("SES-"), "Session wird automatisch erzeugt")
        self.assertIn("response", data)

    def test_t15_chat_with_session_id(self):
        _, created = http_post("/sessions", {})
        sid = created["session_id"]
        status, data = http_post("/chat", {"message": "Sag nur: OK", "model": "granite-3b", "session_id": sid})
        self.assertEqual(status, 200)
        self.assertEqual(data["session_id"], sid)
        self.assertGreaterEqual(data["history_used"], 1)
        _, msgs = http_get(f"/sessions/{sid}/messages")
        self.assertEqual(msgs["count"], 2, "user + assistant persistiert")
        self.assertEqual([m["role"] for m in msgs["messages"]], ["user", "assistant"])

    def test_t15b_chat_unknown_session_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            http_post("/chat", {"message": "test", "model": "granite-3b", "session_id": "SES-nichtda"})
        self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)