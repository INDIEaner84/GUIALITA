#!/usr/bin/env python3
"""Tests für die HTTP-Schnittstelle von scripts/muscal.py (ADR-002 D4).

Der Server wird in einem Thread auf Port 0 gestartet. Es gibt keine externen
Pakete, kein Backend und keine Modellaufrufe — genau die Grenze, in der CI
belastbar prüfen kann.
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, "scripts"))

import muscal  # noqa: E402


class TestMuscalHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="muscal-http-tests-"))
        cls.stop_file = cls.tmp / "STOP"
        cls.roles = muscal.load_roles()["roles"]
        cls.server = muscal.serve_http(
            "127.0.0.1", 0, cls.roles, muscal.StubBackend(),
            cls.tmp / "runs", allow_write=False, max_steps=3,
            stop_file=cls.stop_file)
        cls.port = cls.server.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        if self.stop_file.exists():
            self.stop_file.unlink()

    def tearDown(self):
        if self.stop_file.exists():
            self.stop_file.unlink()

    def get(self, path):
        try:
            with urllib.request.urlopen(self.base + path, timeout=5) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def post(self, path, payload=None, raw=None):
        data = raw if raw is not None else json.dumps(payload or {}).encode("utf-8")
        request = urllib.request.Request(self.base + path, data=data, method="POST")
        request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def guard_query(self, path):
        return "/guard?" + urllib.parse.urlencode({"path": str(path)})

    def test_health_endpoint(self):
        status, body = self.get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["backend"], "stub")

    def test_pipelines_endpoint(self):
        status, body = self.get("/pipelines")
        self.assertEqual(status, 200)
        self.assertEqual(body["default_pipeline"], muscal.DEFAULT_PIPELINE)
        self.assertEqual(body["coder_pipeline"], muscal.CODER_PIPELINE)
        self.assertFalse(body["allow_write"])

    def test_guard_rejects_system_path(self):
        status, body = self.get(self.guard_query("/etc/passwd"))
        self.assertEqual(status, 200)
        self.assertFalse(body["allowed"])
        self.assertIn("/etc", body["reason"])

    def test_guard_allows_staging_path(self):
        target = self.tmp / "runs" / "staging-check" / "vorschlag.md"
        status, body = self.get(self.guard_query(target))
        self.assertEqual(status, 200)
        self.assertTrue(body["allowed"], body["reason"])

    def test_guard_requires_path_parameter(self):
        status, body = self.get("/guard")
        self.assertEqual(status, 400)
        self.assertIn("path", body["error"])

    def test_post_run_success(self):
        status, body = self.post("/run", {"task": "Latenz senken"})
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")
        self.assertEqual([s["status"] for s in body["steps"]], ["ok", "ok", "ok"])
        self.assertTrue(body["run_dir"])

    def test_post_run_missing_task(self):
        status, body = self.post("/run", {"pipeline": ["router"]})
        self.assertEqual(status, 400)
        self.assertIn("task", body["error"])

    def test_post_run_unknown_role(self):
        status, body = self.post("/run", {"task": "x", "pipeline": ["ghost"]})
        self.assertEqual(status, 400)
        self.assertEqual(body["unknown"], ["ghost"])

    def test_post_run_invalid_json(self):
        status, body = self.post("/run", raw=b"{kein json")
        self.assertEqual(status, 400)
        self.assertIn("JSON", body["error"])

    def test_post_unknown_endpoint(self):
        status, body = self.post("/nope", {})
        self.assertEqual(status, 404)

    def test_get_unknown_endpoint(self):
        status, body = self.get("/nope")
        self.assertEqual(status, 404)

    def test_stop_file_blocks_run(self):
        self.stop_file.write_text("halt", encoding="utf-8")
        status, body = self.post("/run", {"task": "x"})
        self.assertEqual(status, 409)
        self.assertIn("STOP", body["error"])

    def test_max_steps_is_capped_by_server(self):
        status, body = self.post("/run", {"task": "x",
                                          "pipeline": muscal.CODER_PIPELINE,
                                          "max_steps": 99})
        self.assertEqual(status, 409)
        self.assertEqual(body["status"], "aborted")
        self.assertTrue(any("gekappt" in w for w in body["warnings"]))

    def test_write_request_is_ignored_without_server_flag(self):
        status, body = self.post("/run", {"task": "x",
                                          "pipeline": ["router", "coder"],
                                          "allow_write": True})
        self.assertEqual(status, 200)
        coder = next(s for s in body["steps"] if s["role"] == "coder")
        self.assertFalse(coder["write"]["allowed"])
        self.assertTrue(any("nicht freigegeben" in w for w in body["warnings"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
