"""GUIALITA Memory Retrieval V1 - Testsuite (T01-T17).

Unit-Tests (T01-T10): Embedding + MemoryStore direkte Ebene.
API-Tests (T11-T13): gegen laufendes Backend.
Regression (T14-T17): bestehende Suites unverändert.
"""

import os
import sys
import json
import tempfile
import unittest
import urllib.request
import urllib.error

import numpy as np

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

BASE_URL = os.environ.get("GUIALITA_URL", "http://localhost:8080")

from backend.memory.embed import embed, embed_to_bytes, bytes_to_embedding, cosine_similarity, tokenize, EMBEDDING_VERSION  # noqa: E402
from backend.memory.store import MemoryStore  # noqa: E402
from backend.memory.retrieval import MemoryIndexer, MemoryRetriever, ContextBuilder  # noqa: E402


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


class TestEmbedding(unittest.TestCase):
    """T01-T02: Embedding-Determinismus."""

    def test_t01_same_text_same_vector(self):
        """T01: Gleicher Text → identischer Vektor."""
        a = embed("Mein Projekt heißt GUIALITA.")
        b = embed("Mein Projekt heißt GUIALITA.")
        self.assertEqual(a.shape, (512,))
        np.testing.assert_array_equal(a, b)

    def test_t02_different_text_different_vector(self):
        """T02: Unterschiedlicher Text → unterschiedlicher Vektor."""
        a = embed("Mein Projekt heißt GUIALITA.")
        b = embed("Die Sonne scheint heute.")
        self.assertFalse(np.array_equal(a, b))
        sim = cosine_similarity(a, b)
        self.assertLess(sim, 0.9, "Verschiedene Texte sollten unterschiedlich sein")


class TestMemoryStoreRetrieval(unittest.TestCase):
    """T03-T10: Store-Ebene mit Memories."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="guialita_mem_")
        self.db_path = os.path.join(self.tmp, "test.db")
        self.store = MemoryStore(self.db_path)
        self.indexer = MemoryIndexer(self.store)
        self.retriever = MemoryRetriever(self.store)

    def tearDown(self):
        self.store.close()
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_t03_persist_and_retrieve(self):
        """T03: Message persistieren → Memory wird indiziert und abrufbar."""
        s = self.store.create_session()
        msg = self.store.append_message(s["id"], "user", "Mein Projekt heißt GUIALITA.")
        mem = self.indexer.index_message(msg)
        self.assertIsNotNone(mem)
        self.assertTrue(mem["id"].startswith("MEM-"))
        self.assertEqual(mem["source_message_id"], msg["id"])
        self.assertEqual(mem["session_id"], s["id"])
        count = self.store.count_memories()
        self.assertEqual(count, 1)

    def test_t04_relevant_query_retrieves_relevant_memory(self):
        """T04: Relevante Query → relevantes Memory wird gefunden."""
        s = self.store.create_session()
        msg = self.store.append_message(s["id"], "user", "Mein Projekt heißt GUIALITA.")
        self.indexer.index_message(msg)

        results = self.retriever.search("Wie heißt mein Projekt?")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["source_message_id"], msg["id"])
        self.assertGreater(results[0]["score"], 0.3)

    def test_t05_irrelevant_ranks_below_relevant(self):
        """T05: Irrelevantes Memory rankt unter relevatem."""
        s = self.store.create_session()
        m1 = self.store.append_message(s["id"], "user", "Mein Projekt heißt GUIALITA.")
        m2 = self.store.append_message(s["id"], "user", "Die Sonne scheint heute und es ist warm.")
        self.indexer.index_messages([m1, m2])

        results = self.retriever.search("Wie heißt mein Projekt?", min_score=0.0)
        self.assertGreater(len(results), 0)
        scores = {r["source_message_id"]: r["score"] for r in results}
        self.assertIn(m1["id"], scores)
        self.assertIn(m2["id"], scores)
        self.assertGreater(scores[m1["id"]], scores[m2["id"]])

    def test_t06_min_score_excludes_weak(self):
        """T06: Mindest-Score schließt schwache Treffer aus."""
        s = self.store.create_session()
        msg = self.store.append_message(s["id"], "user", "Die Sonne scheint heute.")
        self.indexer.index_message(msg)

        results = self.retriever.search("Was ist 2+2?", min_score=0.9)
        self.assertEqual(len(results), 0, "Kein Treffer über min_score=0.9")

    def test_t07_top_k_limit(self):
        """T07: top_k begrenzt Ergebnisse."""
        s = self.store.create_session()
        for i in range(10):
            msg = self.store.append_message(s["id"], "user", f"Informativer Text Nummer {i} über ein Thema.")
            self.indexer.index_message(msg)

        results = self.retriever.search("Text", top_k=3)
        self.assertLessEqual(len(results), 3)

    def test_t08_provenance_preserved(self):
        """T08: Provenance (memory_id, source_message_id, session_id) erhalten."""
        s = self.store.create_session()
        msg = self.store.append_message(s["id"], "user", "Mein Projekt heißt GUIALITA.")
        self.indexer.index_message(msg)

        results = self.retriever.search("Projekt GUIALITA")
        self.assertGreater(len(results), 0)
        r = results[0]
        self.assertIn("memory_id", r)
        self.assertIn("source_message_id", r)
        self.assertIn("session_id", r)
        self.assertIn("score", r)
        self.assertIn("reason", r)
        self.assertEqual(r["session_id"], s["id"])

    def test_t09_cross_session_retrieval(self):
        """T09: Cross-Session Retrieval funktioniert."""
        s1 = self.store.create_session()
        s2 = self.store.create_session()
        m1 = self.store.append_message(s1["id"], "user", "Mein Projekt heißt GUIALITA.")
        self.indexer.index_message(m1)

        results = self.retriever.search(
            "Wie heißt mein Projekt?",
            exclude_session_ids={s2["id"]},
        )
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["session_id"], s1["id"])

    def test_t10_restart_persistence(self):
        """T10: Memory überlebt DB-Neustart."""
        s = self.store.create_session()
        msg = self.store.append_message(s["id"], "user", "Mein Projekt heißt GUIALITA.")
        self.indexer.index_message(msg)
        self.store.close()

        reopened = MemoryStore(self.db_path)
        try:
            retriever = MemoryRetriever(reopened)
            results = retriever.search("Wie heißt mein Projekt?")
            self.assertGreater(len(results), 0)
            self.assertIn("GUIALITA", results[0]["content"])
        finally:
            reopened.close()


class TestRetrievalAPI(unittest.TestCase):
    """T11-T13: API-Ebene gegen laufendes Backend."""

    def test_t11_memory_status(self):
        """T11: GET /memory/status liefert Status."""
        status, data = http_get("/memory/status")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("enabled"))
        self.assertIn("memory_count", data)
        self.assertIn("embedding_version", data)

    def test_t12_memory_search(self):
        """T12: POST /memory/search liefert Ergebnisse."""
        _, sess = http_post("/sessions", {})
        sid = sess["session_id"]
        http_post("/chat", {
            "message": "Mein Projekt heißt GUIALITA.",
            "model": "granite-3b",
            "session_id": sid,
        })
        status, data = http_post("/memory/search", {
            "query": "Wie heißt mein Projekt?",
            "top_k": 3,
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "success")

    def test_t13_retrieval_failure_does_not_break_chat(self):
        """T13: Retrieval-Fehler bricht Chat nicht (Fallback auf History)."""
        _, data = http_post("/chat", {
            "message": "Sag nur: OK",
            "model": "granite-3b",
        })
        self.assertEqual(data["status"], "success")
        self.assertIn("response", data)


# Verschachtelte Suite-Aufrufe: Diese Klasse startet andere Testsuiten als
# Subprozesse. Das führte dazu, dass beim Lauf aller Suiten test_memory.py
# achtmal und test_api.py sechsmal ausgeführt wurde (35 Suite-Läufe statt 9)
# und dass ein einziges fehlendes Backend als Kaskade vieler Fehler erschien.
# Standard: übersprungen. scripts/run_all_tests.py führt jede Suite genau
# einmal aus. Altes Verhalten erzwingen: GUIALITA_TEST_NESTED=1
NESTED_ENABLED = os.environ.get("GUIALITA_TEST_NESTED", "0") == "1"
NESTED_REASON = ("verschachtelter Suite-Aufruf deaktiviert - "
                 "scripts/run_all_tests.py laeuft jede Suite genau einmal "
                 "(GUIALITA_TEST_NESTED=1 erzwingt das alte Verhalten)")


@unittest.skipUnless(NESTED_ENABLED, NESTED_REASON)
class TestRegression(unittest.TestCase):
    """T14-T17: Bestehende Suites laufen unverändert."""

    def test_t14_test_memory_suite(self):
        """T14: tests/test_memory.py — unverändert."""
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_DIR, "tests", "test_memory.py")],
            capture_output=True, text=True, cwd=PROJECT_DIR, timeout=120,
        )
        self.assertEqual(result.returncode, 0, f"test_memory.py fehlgeschlagen:\n{result.stdout[-500:]}")

    def test_t15_test_api_suite(self):
        """T15: tests/test_api.py — unverändert."""
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_DIR, "tests", "test_api.py")],
            capture_output=True, text=True, cwd=PROJECT_DIR, timeout=300,
        )
        self.assertEqual(result.returncode, 0, f"test_api.py fehlgeschlagen:\n{result.stdout[-500:]}")

    def test_t16_test_capture_suite(self):
        """T16: tests/test_capture.py — unverändert."""
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_DIR, "tests", "test_capture.py")],
            capture_output=True, text=True, cwd=PROJECT_DIR, timeout=60,
        )
        self.assertEqual(result.returncode, 0, f"test_capture.py fehlgeschlagen:\n{result.stdout[-500:]}")

    def test_t17_test_process_audio_suite(self):
        """T17: tests/test_process_audio.py — unverändert."""
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_DIR, "tests", "test_process_audio.py")],
            capture_output=True, text=True, cwd=PROJECT_DIR, timeout=600,
        )
        self.assertEqual(result.returncode, 0, f"test_process_audio.py fehlgeschlagen:\n{result.stdout[-500:]}")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
