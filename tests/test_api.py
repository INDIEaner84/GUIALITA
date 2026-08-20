"""GUIALITA Phase 0 - Testsuite.

Voraussetzung: Backend laeuft auf http://localhost:8080
Start:  scripts/start.sh
"""

import sys
import os
import unittest
import json
import base64
import struct
import urllib.request
import urllib.error

BASE_URL = os.environ.get("GUIALITA_URL", "http://localhost:8080")
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_AUDIO = os.path.join(PROJECT_DIR, "tests", "data", "test_audio.wav")


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


def http_post_wav(path: str, data: bytes):
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "audio/wav"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.status, json.loads(r.read().decode())


def make_test_wav(path: str, duration_s: float = 1.0, sample_rate: int = 16000):
    """Erzeugt eine stille Test-WAV (16-bit PCM mono)."""
    n = int(duration_s * sample_rate)
    with open(path, "wb") as f:
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + n * 2))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))
        f.write(struct.pack("<H", 1))
        f.write(struct.pack("<H", 1))
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", sample_rate * 2))
        f.write(struct.pack("<H", 2))
        f.write(struct.pack("<H", 16))
        f.write(b"data")
        f.write(struct.pack("<I", n * 2))
        f.write(b"\x00\x00" * n)


class TestAPIHealth(unittest.TestCase):
    def test_health_returns_200(self):
        status, data = http_get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(data["api"], "online")

    def test_health_contains_runtimes(self):
        _, data = http_get("/health")
        self.assertIn("primary_runtime", data)
        self.assertIn("secondary_runtime", data)
        self.assertIn("models", data)


class TestModelConnectivity(unittest.TestCase):
    def test_models_listed(self):
        _, data = http_get("/models")
        self.assertGreater(len(data["models"]), 0)
        available = [m for m in data["models"] if m["available"]]
        self.assertGreater(len(available), 0, "Mindestens ein Modell muss verfuegbar sein")

    def test_granite_model_available(self):
        _, data = http_get("/models")
        granite = [m for m in data["models"] if m["id"] == "granite-3b"]
        self.assertEqual(len(granite), 1)
        self.assertTrue(granite[0]["available"])


class TestChatAPI(unittest.TestCase):
    def test_chat_empty_message_returns_400(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            http_post("/chat", {"message": "  "})
        self.assertEqual(ctx.exception.code, 400)

    def test_chat_unknown_model_returns_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            http_post("/chat", {"message": "test", "model": "gibts-nicht"})
        self.assertEqual(ctx.exception.code, 404)

    def test_chat_returns_success_format(self):
        status, data = http_post("/chat", {"message": "Sag nur: OK", "model": "granite-3b"})
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "success")
        self.assertIn("response", data)
        self.assertIn("model", data)
        self.assertIn("latency_ms", data)
        self.assertGreaterEqual(data["latency_ms"], 0)


class TestEndToEnd(unittest.TestCase):
    def test_real_lfm_response(self):
        """Browser/API -> Chat Request -> LFM -> Real Response"""
        status, data = http_post(
            "/chat",
            {
                "message": "Hallo LFM. Antworte exakt mit: LFM CONNECTION TEST OK",
                "model": "granite-3b",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "success")
        response = data["response"].strip().upper()
        self.assertIn("CONNECTION TEST OK", response)
        self.assertLess(data["latency_ms"], 120000, "Latenz unter 120s")

    def test_frontend_served(self):
        req = urllib.request.Request(BASE_URL + "/")
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode()
        self.assertEqual(r.status, 200)
        self.assertIn("GUIALITA", body)


class TestAudioStatus(unittest.TestCase):
    def test_audio_status_200(self):
        status, data = http_get("/audio/status")
        self.assertEqual(status, 200)
        self.assertIn("engine", data)
        self.assertIn("status", data)

    def test_stt_online(self):
        _, data = http_get("/audio/status")
        self.assertEqual(data["status"], "online")
        self.assertEqual(data["engine"], "whisper.cpp")


class TestAudioTranscribe(unittest.TestCase):
    def test_valid_wav_transcribes(self):
        status, data = http_post_wav("/audio/transcribe", open(TEST_AUDIO, "rb").read())
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "success")
        self.assertIn("transcript", data)
        self.assertGreater(len(data["transcript"]), 0, "Transcript darf nicht leer sein")
        self.assertGreaterEqual(data["transcription_ms"], 0)

    def test_wrong_content_type_415(self):
        req = urllib.request.Request(
            BASE_URL + "/audio/transcribe",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=30)
        self.assertEqual(ctx.exception.code, 415)

    def test_empty_audio_400(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            http_post_wav("/audio/transcribe", b"")
        self.assertEqual(ctx.exception.code, 400)

    def test_invalid_audio_format_400(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            http_post_wav("/audio/transcribe", b"X" * 500)
        self.assertEqual(ctx.exception.code, 400)


class TestAudioChat(unittest.TestCase):
    def test_audio_chat_invalid_json_400(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            http_post("/audio/chat", "kaputt")  # kein dict
        self.assertEqual(ctx.exception.code, 400)

    def test_audio_chat_empty_audio_400(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            http_post("/audio/chat", {"audio": "", "duration_s": 0})
        self.assertEqual(ctx.exception.code, 400)

    def test_audio_chat_full_pipeline(self):
        """Audio -> STT -> Transcript -> bestehende Chat-Pipeline -> LFM."""
        with open(TEST_AUDIO, "rb") as f:
            wav = f.read()
        payload = {
            "audio": base64.b64encode(wav).decode(),
            "duration_s": 1.0,
            "model": "granite-3b",
        }
        status, data = http_post("/audio/chat", payload)
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "success")
        self.assertIn("transcript", data)
        self.assertIn("response", data)
        self.assertIn("model", data)
        self.assertIn("transcription_ms", data)
        self.assertIn("chat_ms", data)
        self.assertIn("total_ms", data)
        self.assertEqual(data["chat_runtime"], "llamacpp")
        self.assertEqual(data["stt_runtime"], "whisper.cpp")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
