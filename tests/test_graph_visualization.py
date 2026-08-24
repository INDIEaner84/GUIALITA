"""GUIALITA Graph Visualization V1 - Testsuite (T01-T13).

API-Tests (T01-T08): gegen laufendes Backend.
Regression (T09-T13): bestehende Suites unverändert.
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


class TestGraphVisualizationAPI(unittest.TestCase):
    """T01-T08: Graph-Visualisierung API."""

    def test_t01_graph_endpoint_returns_valid_graph(self):
        """T01: GET /memory/graph liefert validen Graph."""
        status, data = http_get("/memory/graph")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "success")
        self.assertIn("nodes", data)
        self.assertIn("edges", data)
        self.assertIn("truncated", data)
        self.assertIn("entity_count", data)
        self.assertIn("relation_count", data)

    def test_t02_nodes_correspond_to_real_entities(self):
        """T02: Nodes repräsentieren reale Entities."""
        _, data = http_get("/memory/graph")
        for node in data["nodes"]:
            self.assertIn("id", node)
            self.assertIn("label", node)
            self.assertIn("entity_type", node)
            self.assertTrue(len(node["label"]) > 0)

    def test_t03_edges_correspond_to_real_relations(self):
        """T03: Edges repräsentieren reale Relationen."""
        _, data = http_get("/memory/graph")
        node_ids = {n["id"] for n in data["nodes"]}
        for edge in data["edges"]:
            self.assertIn("id", edge)
            self.assertIn("source", edge)
            self.assertIn("target", edge)
            self.assertIn("relation", edge)
            self.assertIn("source_memory_id", edge)
            if node_ids:
                self.assertIn(edge["source"], node_ids, "Source node exists in graph")
                self.assertIn(edge["target"], node_ids, "Target node exists in graph")

    def test_t04_edge_provenance_exists(self):
        """T04: Edge-Provenance (source_memory_id) existiert."""
        _, data = http_get("/memory/graph")
        for edge in data["edges"]:
            self.assertTrue(
                edge["source_memory_id"].startswith("MEM-"),
                f"Provenance MEM- erwartet: {edge['source_memory_id']}"
            )

    def test_t05_bounded_graph_works(self):
        """T05: Begrenzter Graph funktioniert."""
        _, data = http_get("/memory/graph?max_nodes=5&max_edges=10")
        self.assertEqual(data["status"], "success")
        self.assertLessEqual(len(data["nodes"]), 5)
        self.assertLessEqual(len(data["edges"]), 10)

    def test_t06_empty_graph_works(self):
        """T06: Leerer Graph funktioniert (limit=0)."""
        status, data = http_get("/memory/graph?max_nodes=0&max_edges=0")
        self.assertEqual(status, 200)
        self.assertEqual(data["displayed_nodes"], 0)
        self.assertEqual(data["displayed_edges"], 0)

    def test_t07_entity_search_via_api(self):
        """T07: Entity-Suche via /memory/graph/{entity} funktioniert."""
        _, data = http_get("/memory/graph")
        if data["nodes"]:
            entity_name = data["nodes"][0]["label"]
            status, detail = http_get(f"/memory/graph/{entity_name}")
            self.assertEqual(status, 200)
            self.assertEqual(detail["status"], "success")
            self.assertEqual(detail["entity"]["canonical_name"], entity_name)

    def test_t08_unknown_entity_handled(self):
        """T08: Unbekannte Entity wird korrekt behandelt."""
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            http_get("/memory/graph/EXISTIERTNICHT999")
        self.assertEqual(ctx.exception.code, 404)


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
class TestGraphRegression(unittest.TestCase):
    """T09-T13: Bestehende Suites laufen unverändert."""

    def test_t09_graph_tests(self):
        """T09: tests/test_memory_graph.py — unverändert."""
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_DIR, "tests", "test_memory_graph.py")],
            capture_output=True, text=True, cwd=PROJECT_DIR, timeout=120,
        )
        self.assertEqual(result.returncode, 0, f"test_memory_graph.py:\n{result.stdout[-500:]}")

    def test_t10_retrieval_tests(self):
        """T10: tests/test_memory_retrieval.py — unverändert."""
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_DIR, "tests", "test_memory_retrieval.py")],
            capture_output=True, text=True, cwd=PROJECT_DIR, timeout=300,
        )
        self.assertEqual(result.returncode, 0, f"test_memory_retrieval.py:\n{result.stdout[-500:]}")

    def test_t11_session_tests(self):
        """T11: tests/test_memory.py — unverändert."""
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_DIR, "tests", "test_memory.py")],
            capture_output=True, text=True, cwd=PROJECT_DIR, timeout=120,
        )
        self.assertEqual(result.returncode, 0, f"test_memory.py:\n{result.stdout[-500:]}")

    def test_t12_api_tests(self):
        """T12: tests/test_api.py — unverändert."""
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_DIR, "tests", "test_api.py")],
            capture_output=True, text=True, cwd=PROJECT_DIR, timeout=300,
        )
        self.assertEqual(result.returncode, 0, f"test_api.py:\n{result.stdout[-500:]}")

    def test_t13_audio_tests(self):
        """T13: tests/test_capture.py + test_process_audio.py — unverändert."""
        import subprocess
        r1 = subprocess.run(
            [sys.executable, os.path.join(PROJECT_DIR, "tests", "test_capture.py")],
            capture_output=True, text=True, cwd=PROJECT_DIR, timeout=60,
        )
        self.assertEqual(r1.returncode, 0, f"test_capture.py:\n{r1.stdout[-300:]}")
        r2 = subprocess.run(
            [sys.executable, os.path.join(PROJECT_DIR, "tests", "test_process_audio.py")],
            capture_output=True, text=True, cwd=PROJECT_DIR, timeout=600,
        )
        self.assertEqual(r2.returncode, 0, f"test_process_audio.py:\n{r2.stdout[-300:]}")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
