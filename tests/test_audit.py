"""Unit tests for privacy-conscious audit events."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.audit import record, read_events, summary


class TestAudit(unittest.TestCase):
    def test_metadata_is_written_without_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            with patch.dict(os.environ, {"GUIALITA_AUDIT_PATH": str(path)}, clear=False):
                record("test_event", session_id="SES-test", content="secret")
            event = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(event["event"], "test_event")
            self.assertNotIn("content", event)

    def test_read_events_filters_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            with patch.dict(os.environ, {"GUIALITA_AUDIT_PATH": str(path)}, clear=False):
                record("one", session_id="SES-1")
                record("two", session_id="SES-2")
                events = read_events("SES-1")
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["event"], "one")

    def test_summary_calculates_latency(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            with patch.dict(os.environ, {"GUIALITA_AUDIT_PATH": str(path)}, clear=False):
                record("chat", session_id="SES-1", status="success", chat_ms=10, total_ms=20)
                record("audio", session_id="SES-1", status="success", chat_ms=30, total_ms=40)
                result = summary("SES-1")
            self.assertEqual(result["completed_count"], 2)
            self.assertEqual(result["average_chat_ms"], 20.0)

    def test_content_requires_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            with patch.dict(os.environ, {
                "GUIALITA_AUDIT_PATH": str(path),
                "GUIALITA_AUDIT_INCLUDE_CONTENT": "1",
            }, clear=False):
                record("test_event", transcript="hello")
            event = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(event["transcript"], "hello")


if __name__ == "__main__":
    unittest.main(verbosity=2)
