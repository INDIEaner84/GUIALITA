#!/usr/bin/env python3
"""Tests für scripts/muscal.py — sequenzielle Kette, Guard und Audit.

Der Schwerpunkt liegt nicht auf hübschen Ausgaben, sondern auf den Stellen, an
denen eine Orchestrierung unauffällig gefährlich wird: Schreibpfade, STOP-Datei,
Schrittgrenze, Auditor-Verdict und Audit-Log.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, "scripts"))

import muscal  # noqa: E402

ROLES = muscal.load_roles()["roles"]


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


class FailingBackend:
    name = "failing"

    def ask(self, role_name, message, role):
        raise RuntimeError("Backend nicht erreichbar")


class CustomBackend(muscal.StubBackend):
    name = "custom"

    def __init__(self, responses):
        super().__init__(responses)


class TestGuard(unittest.TestCase):

    def test_staging_path_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            allowed, reason = muscal.guard_write(staging / "vorschlag.md", staging)
            self.assertTrue(allowed, reason)

    def test_path_outside_staging_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            allowed, _ = muscal.guard_write(Path(tmp) / "anderswo.md", staging)
            self.assertFalse(allowed)

    def test_parent_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            allowed, _ = muscal.guard_write(staging / ".." / "aussen.md", staging)
            self.assertFalse(allowed)

    def test_system_prefix_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            allowed, reason = muscal.guard_write(Path("/etc/passwd"), staging)
            self.assertFalse(allowed)
            self.assertIn("/etc", reason)

    def test_no_staging_means_no_write(self):
        allowed, reason = muscal.guard_write(Path("/tmp/x"), None)
        self.assertFalse(allowed)
        self.assertIn("nicht erlaubt", reason)


class TestStop(unittest.TestCase):

    def test_stop_file_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            stop = Path(tmp) / "STOP"
            self.assertFalse(muscal.stop_requested(stop))
            stop.write_text("halt", encoding="utf-8")
            self.assertTrue(muscal.stop_requested(stop))

    def test_stop_aborts_before_first_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stop = root / "STOP"
            stop.write_text("halt", encoding="utf-8")
            result = muscal.run_pipeline("Aufgabe", ["router"], muscal.StubBackend(),
                                         ROLES, False, 5, root / "runs", stop)
            self.assertEqual(result["status"], "aborted")
            self.assertEqual(result["steps"][0]["status"], "aborted")


class TestSchemas(unittest.TestCase):

    def test_router_label_valid(self):
        ok, detail = muscal.check_output("router", "label", "code")
        self.assertTrue(ok, detail)

    def test_router_label_invalid(self):
        ok, detail = muscal.check_output("router", "label", "vielleicht")
        self.assertFalse(ok)
        self.assertIn("kein gültiges Label", detail)

    def test_numbered_plan(self):
        ok, detail = muscal.check_output("planner", "plan", "1. messen\n2. vergleichen")
        self.assertTrue(ok, detail)

    def test_vague_plan_is_rejected(self):
        ok, _ = muscal.check_output("planner", "plan", "irgendwie optimieren")
        self.assertFalse(ok)

    def test_coder_diff_requires_details(self):
        ok, detail = muscal.check_output("coder", "diff", muscal.STUB_RESPONSES["coder"])
        self.assertTrue(ok, detail)

    def test_coder_diff_without_block_is_rejected(self):
        ok, detail = muscal.check_output("coder", "diff", "Betroffen: a.py\nZeile zwei")
        self.assertFalse(ok)
        self.assertIn("Diff-Block", detail)

    def test_auditor_report_with_evidence(self):
        ok, detail = muscal.check_output("auditor", "report",
                                         '{"verdict":"pass","evidence":["test ok"]}')
        self.assertTrue(ok, detail)

    def test_auditor_pass_without_evidence_is_rejected(self):
        ok, detail = muscal.check_output("auditor", "report",
                                         '{"verdict":"pass","evidence":[]}')
        self.assertFalse(ok)
        self.assertIn("ohne Evidenz", detail)

    def test_auditor_fail_verdict_is_valid_report(self):
        ok, detail = muscal.check_output("auditor", "report",
                                         '{"verdict":"fail","evidence":["Fehler gefunden"]}')
        self.assertTrue(ok, detail)

    def test_extract_json_handles_preamble(self):
        parsed = muscal.extract_json('Bericht: {"verdict":"pass"} Danke.')
        self.assertEqual(parsed["verdict"], "pass")


class TestPipeline(unittest.TestCase):

    def test_default_pipeline_is_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = muscal.run_pipeline("Latenz senken", muscal.DEFAULT_PIPELINE,
                                         muscal.StubBackend(), ROLES, False, 5,
                                         Path(tmp))
            self.assertEqual(result["status"], "ok")
            self.assertEqual([s["status"] for s in result["steps"]], ["ok", "ok", "ok"])

    def test_coder_writes_only_into_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = muscal.run_pipeline("Optimiere", muscal.CODER_PIPELINE,
                                         muscal.StubBackend(), ROLES, True, 5, root)
            coder = next(s for s in result["steps"] if s["role"] == "coder")
            self.assertTrue(coder["write"]["allowed"])
            target = root / result["run_id"] / "staging" / "vorschlag.md"
            self.assertTrue(target.is_file())
            self.assertIn("```diff", target.read_text(encoding="utf-8"))

    def test_without_allow_write_nothing_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = muscal.run_pipeline("Optimiere", muscal.CODER_PIPELINE,
                                         muscal.StubBackend(), ROLES, False, 5,
                                         Path(tmp))
            coder = next(s for s in result["steps"] if s["role"] == "coder")
            self.assertFalse(coder["write"]["allowed"])
            self.assertFalse((Path(tmp) / result["run_id"] / "staging").exists())

    def test_max_steps_skips_remaining_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = muscal.run_pipeline("Aufgabe", muscal.DEFAULT_PIPELINE,
                                         muscal.StubBackend(), ROLES, False, 1,
                                         Path(tmp))
            self.assertEqual(result["status"], "aborted")
            self.assertEqual(result["steps"][-1]["status"], "skipped")

    def test_auditor_fail_ends_run_and_audit_log_agrees(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backend = CustomBackend({"auditor": '{"verdict":"fail","evidence":["Beleg"]}'})
            result = muscal.run_pipeline("Aufgabe", ["auditor"], backend, ROLES,
                                         False, 5, root)
            self.assertEqual(result["status"], "audit_failed")
            events = [json.loads(line) for line in
                      (root / result["run_id"] / "events.jsonl").read_text(
                          encoding="utf-8").splitlines()]
            step_end = next(e for e in events if e.get("event") == "step_end")
            self.assertEqual(step_end["status"], "audit_failed")

    def test_unknown_role_is_config_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = muscal.run_pipeline("Aufgabe", ["ghost"], muscal.StubBackend(),
                                         ROLES, False, 5, Path(tmp))
            self.assertEqual(result["status"], "config_error")

    def test_backend_exception_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = muscal.run_pipeline("Aufgabe", ["router"], FailingBackend(),
                                         ROLES, False, 5, Path(tmp))
            self.assertEqual(result["status"], "step_failed")
            self.assertIn("Backend nicht erreichbar", result["steps"][0]["reason"])

        # ErrorResponse (HTTP 200, status=error) darf nicht als leere Antwort
        # oder gar als Erfolg durchgehen.
        with mock.patch.object(muscal.urllib.request, "urlopen",
                               return_value=FakeHTTPResponse({
                                   "status": "error", "error": "contract",
                                   "details": "Fake-Fehler"})):
            with tempfile.TemporaryDirectory() as tmp:
                result = muscal.run_pipeline(
                    "Aufgabe", ["router"],
                    muscal.LiveBackend("http://fake.invalid", timeout=5),
                    ROLES, False, 5, Path(tmp))
                self.assertEqual(result["status"], "step_failed")
                self.assertIn("Backend-Fehler", result["steps"][0]["reason"])

    def test_build_message_contains_previous_steps(self):
        message = muscal.build_message(ROLES["planner"], "Aufgabe", [
            {"role": "router", "status": "ok", "response_head": "code"}])
        self.assertIn("Bisherige Schritte", message)
        self.assertIn("router (ok): code", message)

    def test_display_path_handles_paths_outside_repository(self):
        self.assertTrue(muscal.display_path(Path("/tmp/muscal-x")).startswith("/"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
