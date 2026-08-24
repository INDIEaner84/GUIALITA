"""Pure contract tests for the session-aware audio chat payload.

These tests do not need a running server, microphone, model, or audio runtime.
"""
import base64
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError
from backend.models.schemas import AudioChatRequest


class TestAudioChatRequest(unittest.TestCase):
    def test_defaults_and_session(self):
        req = AudioChatRequest(
            audio=base64.b64encode(b"RIFF....WAVE").decode(),
            session_id="SES-test",
            model="granite-3b",
        )
        self.assertEqual(req.session_id, "SES-test")
        self.assertEqual(req.duration_s, 0.0)

    def test_duration_must_be_non_negative(self):
        with self.assertRaises(ValidationError):
            AudioChatRequest(audio="abc", duration_s=-1)

    def test_duration_has_safe_upper_bound(self):
        with self.assertRaises(ValidationError):
            AudioChatRequest(audio="abc", duration_s=181)

    def test_payload_has_safe_upper_bound(self):
        with self.assertRaises(ValidationError):
            AudioChatRequest(audio="x" * 35_000_001)


if __name__ == "__main__":
    unittest.main(verbosity=2)
