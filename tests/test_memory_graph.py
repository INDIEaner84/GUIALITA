"""GUIALITA Memory Graph Foundation - Testsuite (T01-T14).

Unit-Tests (T01-T10): Store + Extractor direkte Ebene.
API-Tests (T11-T12): gegen laufendes Backend.
Regression (T13-T14): bestehende Suites unverändert.
"""

import os
import sys
import json
import tempfile
import unittest
import urllib.request
import urllib.error

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

BASE_URL = os.environ.get("GUIALITA_URL", "http://localhost:8080")

from backend.memory.store import MemoryStore  # noqa: E402
from backend.memory.extractor import extract_entities, extract_relations, extract_from_memory  # noqa: E402
from backend.memory.retrieval import MemoryIndexer, GraphRetriever  # noqa: E402


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


class TestGraphStore(unittest.TestCase):
    """T01-T05: Store-Ebene für Entities und Relations."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="guialita_graph_")
        self.db_path = os.path.join(self.tmp, "test.db")
        self.store = MemoryStore(self.db_path)

    def tearDown(self):
        self.store.close()
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_t01_entity_creation(self):
        """T01: Entity wird korrekt erstellt."""
        ent = self.store.upsert_entity("GUIALITA", "project")
        self.assertIsNotNone(ent)
        self.assertEqual(ent["canonical_name"], "GUIALITA")
        self.assertEqual(ent["entity_type"], "project")
        self.assertTrue(ent["id"].startswith("ENT-"))

    def test_t02_duplicate_entity_normalization(self):
        """T02: Duplicate Entity wird normalisiert (INSERT OR IGNORE)."""
        e1 = self.store.upsert_entity("Granite", "model")
        e2 = self.store.upsert_entity("Granite", "model")
        self.assertIsNotNone(e1)
        self.assertIsNotNone(e2)
        self.assertEqual(e1["id"], e2["id"])
        self.assertEqual(self.store.count_entities(), 1)

    def test_t03_relation_creation(self):
        """T03: Relation wird korrekt erstellt."""
        e1 = self.store.upsert_entity("GUIALITA", "project")
        e2 = self.store.upsert_entity("Granite", "model")
        s = self.store.create_session()
        msg = self.store.append_message(s["id"], "user", "GUIALITA uses Granite.")
        mem = self.store.insert_memory(
            memory_id="MEM-test01", source_message_id=msg["id"],
            session_id=s["id"], content="GUIALITA uses Granite.",
            embedding=b"\x00" * 4096, embedding_version=1,
        )
        rel = self.store.upsert_relation(
            source_entity_id=e1["id"], relation_type="uses",
            target_entity_id=e2["id"], source_memory_id=mem["id"],
        )
        self.assertIsNotNone(rel)
        self.assertEqual(rel["relation_type"], "uses")
        self.assertTrue(rel["id"].startswith("REL-"))

    def test_t04_relation_deduplication(self):
        """T04: Duplikate Relationen werden dedupliziert."""
        e1 = self.store.upsert_entity("GUIALITA", "project")
        e2 = self.store.upsert_entity("Granite", "model")
        s = self.store.create_session()
        msg = self.store.append_message(s["id"], "user", "test")
        mem = self.store.insert_memory(
            memory_id="MEM-test02", source_message_id=msg["id"],
            session_id=s["id"], content="test",
            embedding=b"\x00" * 4096, embedding_version=1,
        )
        r1 = self.store.upsert_relation(e1["id"], "uses", e2["id"], mem["id"])
        r2 = self.store.upsert_relation(e1["id"], "uses", e2["id"], mem["id"])
        self.assertIsNotNone(r1)
        self.assertIsNotNone(r2)
        self.assertEqual(r1["id"], r2["id"])
        self.assertEqual(self.store.count_relations(), 1)

    def test_t05_provenance_preservation(self):
        """T05: Provenance (source_memory_id) wird erhalten."""
        e1 = self.store.upsert_entity("GUIALITA", "project")
        e2 = self.store.upsert_entity("Granite", "model")
        s = self.store.create_session()
        msg = self.store.append_message(s["id"], "user", "test")
        mem = self.store.insert_memory(
            memory_id="MEM-test03", source_message_id=msg["id"],
            session_id=s["id"], content="test",
            embedding=b"\x00" * 4096, embedding_version=1,
        )
        rel = self.store.upsert_relation(e1["id"], "uses", e2["id"], mem["id"])
        self.assertEqual(rel["source_memory_id"], mem["id"])


class TestExtractor(unittest.TestCase):
    """T06-T07: Entity- und Relation-Extraktion."""

    def test_t06_entity_extraction(self):
        """T06: Entitäten werden aus Text extrahiert."""
        entities, _ = extract_from_memory("GUIALITA uses Granite for ASR.")
        names = {e["canonical_name"] for e in entities}
        self.assertIn("GUIALITA", names)
        self.assertTrue(
            "granite" in names or "Granite" in names or "granite-3b" in names,
            f"Erwartet 'granite'/'Granite'/'granite-3b' in {names}"
        )

    def test_t07_relation_extraction(self):
        """T07: Beziehungen werden aus Text extrahiert."""
        entities, relations = extract_from_memory("GUIALITA uses Granite.")
        entity_names = {e["canonical_name"] for e in entities}
        self.assertGreater(len(entity_names), 0)
        self.assertGreater(len(relations), 0)
        rel_types = {r["relation_type"] for r in relations}
        self.assertTrue(
            "uses" in rel_types or "related_to" in rel_types,
            f"Erwartet 'uses' oder 'related_to', erhalten: {rel_types}"
        )


class TestGraphRetrieval(unittest.TestCase):
    """T08-T10: 1-Hop-Traversale."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="guialita_graph_")
        self.db_path = os.path.join(self.tmp, "test.db")
        self.store = MemoryStore(self.db_path)
        self.indexer = MemoryIndexer(self.store)
        self.graph = GraphRetriever(self.store)

    def tearDown(self):
        self.store.close()
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_t08_1hop_traversal(self):
        """T08: 1-Hop-Traversale liefert verbundene Entitäten."""
        s = self.store.create_session()
        msg = self.store.append_message(s["id"], "user", "GUIALITA uses Granite.")
        self.indexer.index_message(msg)

        result = self.graph.traverse("GUIALITA")
        self.assertIsNotNone(result["entity"])
        self.assertEqual(result["entity"]["canonical_name"], "GUIALITA")
        self.assertGreater(len(result["outgoing"]), 0)

    def test_t09_irrelevant_entity_no_relations(self):
        """T09: Unbekannte Entity liefert keine falschen Relationen."""
        s = self.store.create_session()
        msg = self.store.append_message(s["id"], "user", "GUIALITA uses Granite.")
        self.indexer.index_message(msg)

        result = self.graph.traverse("NichtVorhanden")
        self.assertIsNone(result["entity"])
        self.assertEqual(result["outgoing"], [])
        self.assertEqual(result["incoming"], [])

    def test_t10_persistence_after_reopen(self):
        """T10: Graph überlebt DB-Neustart."""
        s = self.store.create_session()
        msg = self.store.append_message(s["id"], "user", "GUIALITA uses Granite.")
        self.indexer.index_message(msg)
        self.store.close()

        reopened = MemoryStore(self.db_path)
        try:
            graph = GraphRetriever(reopened)
            result = graph.traverse("GUIALITA")
            self.assertIsNotNone(result["entity"])
            self.assertGreater(len(result["outgoing"]), 0)
        finally:
            reopened.close()


class TestGraphAPI(unittest.TestCase):
    """T11-T12: API-Ebene gegen laufendes Backend."""

    def test_t11_memory_status_with_graph(self):
        """T11: GET /memory/status liefert entity_count und relation_count."""
        status, data = http_get("/memory/status")
        self.assertEqual(status, 200)
        self.assertIn("entity_count", data)
        self.assertIn("relation_count", data)

    def test_t12_memory_graph_endpoint(self):
        """T12: GET /memory/graph/{entity} liefert Graph-Daten."""
        _, sess = http_post("/sessions", {})
        sid = sess["session_id"]
        http_post("/chat", {
            "message": "GUIALITA uses Granite for everything.",
            "model": "granite-3b",
            "session_id": sid,
        })
        status, data = http_get("/memory/graph/GUIALITA")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "success")
        self.assertIsNotNone(data["entity"])
        self.assertEqual(data["entity"]["canonical_name"], "GUIALITA")


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
    """T13-T14: Bestehende Suites laufen unverändert."""

    def test_t13_existing_memory_retrieval(self):
        """T13: tests/test_memory_retrieval.py — unverändert."""
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_DIR, "tests", "test_memory_retrieval.py")],
            capture_output=True, text=True, cwd=PROJECT_DIR, timeout=300,
        )
        self.assertEqual(result.returncode, 0, f"test_memory_retrieval.py fehlgeschlagen:\n{result.stdout[-500:]}")

    def test_t14_existing_memory_tests(self):
        """T14: tests/test_memory.py — unverändert."""
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_DIR, "tests", "test_memory.py")],
            capture_output=True, text=True, cwd=PROJECT_DIR, timeout=120,
        )
        self.assertEqual(result.returncode, 0, f"test_memory.py fehlgeschlagen:\n{result.stdout[-500:]}")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
