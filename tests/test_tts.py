"""GUIALITA TTS V1 - Testsuite (T01-T16).

T01-T11: TTS-Service und API.
T12-T16: Regression — bestehende Funktionalität unverändert.
"""

import os
import sys
import json
import struct
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


def http_post_json(path: str, payload: dict):
    req = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        ct = r.headers.get("Content-Type", "")
        body = r.read()
        if "audio/wav" in ct:
            return r.status, body, dict(r.headers)
        return r.status, json.loads(body.decode()), dict(r.headers)


def parse_wav(data: bytes) -> dict:
    if len(data) < 44 or data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        return {"valid": False}
    channels = struct.unpack_from("<H", data, 22)[0]
    sample_rate = struct.unpack_from("<I", data, 24)[0]
    bits_per_sample = struct.unpack_from("<H", data, 34)[0]
    fmt_size = struct.unpack_from("<I", data, 16)[0]
    data_offset = 20 + fmt_size
    if data_offset + 8 > len(data):
        return {"valid": True, "channels": channels, "sample_rate": sample_rate, "bits_per_sample": bits_per_sample}
    data_size = struct.unpack_from("<I", data, data_offset + 4)[0]
    bytes_per_sample = channels * bits_per_sample // 8
    duration = data_size / (sample_rate * bytes_per_sample) if bytes_per_sample > 0 else 0.0
    return {
        "valid": True,
        "channels": channels,
        "sample_rate": sample_rate,
        "bits_per_sample": bits_per_sample,
        "data_size": data_size,
        "duration": duration,
    }


class TestTTSService(unittest.TestCase):
    """T01-T11: TTS-Service und API."""

    def test_t01_import(self):
        """T01: TTS-Service importierbar."""
        from backend.audio.tts import TTSService
        svc = TTSService()
        self.assertIsNotNone(svc)

    def test_t02_model_reachable(self):
        """T02: TTS-Modell erreichbar."""
        from backend.audio.tts import tts_service
        self.assertTrue(tts_service.is_available(), "TTS Modell nicht verfügbar")

    def test_t03_valid_text_produces_wav(self):
        """T03: Gültiger Text → WAV."""
        from backend.audio.tts import tts_service
        result = tts_service.synthesize("Hello, this is a test.")
        self.assertGreater(len(result["wav_bytes"]), 44)
        self.assertIn("sample_rate", result)
        self.assertIn("duration_s", result)

    def test_t04_wav_header_valid(self):
        """T04: WAV Header gültig."""
        from backend.audio.tts import tts_service
        result = tts_service.synthesize("Test.")
        info = parse_wav(result["wav_bytes"])
        self.assertTrue(info["valid"], "WAV Header ungültig")

    def test_t05_wav_sample_rate(self):
        """T05: WAV Sample Rate korrekt (24000)."""
        from backend.audio.tts import tts_service
        result = tts_service.synthesize("Test.")
        info = parse_wav(result["wav_bytes"])
        self.assertEqual(info["sample_rate"], 24000)

    def test_t06_wav_channels(self):
        """T06: WAV Channels korrekt (mono)."""
        from backend.audio.tts import tts_service
        result = tts_service.synthesize("Test.")
        info = parse_wav(result["wav_bytes"])
        self.assertEqual(info["channels"], 1)

    def test_t07_empty_text_rejected(self):
        """T07: Leerer Text wird abgelehnt."""
        from backend.audio.tts import tts_service
        with self.assertRaises(ValueError):
            tts_service.synthesize("")

    def test_t08_invalid_voice_rejected(self):
        """T08: Ungültige Voice wird abgelehnt."""
        from backend.audio.tts import tts_service
        with self.assertRaises(ValueError):
            tts_service.synthesize("Test.", voice="nonexistent_voice")

    def test_t09_api_tts(self):
        """T09: API /audio/tts funktioniert."""
        status, data, headers = http_post_json("/audio/tts", {"text": "Hello from API test."})
        self.assertEqual(status, 200)
        self.assertIsInstance(data, bytes)
        self.assertGreater(len(data), 44)
        headers_lower = {k.lower(): v for k, v in headers.items()}
        self.assertIn("x-tts-duration-s", headers_lower)

    def test_t10_realistic_text(self):
        """T10: Realistische Textprobe."""
        from backend.audio.tts import tts_service
        result = tts_service.synthesize(
            "GUIALITA ist ein lokaler LFM-Sprachassistent mit Session-Persistenz und Memory-Retrieval."
        )
        self.assertGreater(result["duration_s"], 0.5)
        self.assertGreater(len(result["wav_bytes"]), 1000)

    def test_t11_second_request_works(self):
        """T11: Zweite Anfrage funktioniert."""
        from backend.audio.tts import tts_service
        r1 = tts_service.synthesize("First request.")
        r2 = tts_service.synthesize("Second request.")
        self.assertGreater(len(r1["wav_bytes"]), 44)
        self.assertGreater(len(r2["wav_bytes"]), 44)


class TestTTSRegression(unittest.TestCase):
    """T12-T16: Bestehende Funktionalität unverändert."""

    def test_t12_existing_chat_works(self):
        """T12: Bestehender /chat funktioniert."""
        _, sess, _ = http_post_json("/sessions", {})
        sid = sess["session_id"]
        status, data, _ = http_post_json("/chat", {
            "message": "Say hello.",
            "model": "granite-3b",
            "session_id": sid,
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "success")
        self.assertIn("response", data)

    def test_t13_session_continuity(self):
        """T13: Session Continuity weiterhin PASS."""
        _, sess, _ = http_post_json("/sessions", {})
        sid = sess["session_id"]
        http_post_json("/chat", {"message": "My name is TestUser123.", "model": "granite-3b", "session_id": sid})
        status, data, _ = http_post_json("/chat", {
            "message": "What is my name?",
            "model": "granite-3b",
            "session_id": sid,
        })
        self.assertEqual(status, 200)
        self.assertIn("TestUser123", data.get("response", ""))

    def test_t14_memory_retrieval(self):
        """T14: Memory Retrieval weiterhin PASS."""
        status, data = http_get("/memory/status")
        self.assertEqual(status, 200)
        self.assertIn("entity_count", data)
        self.assertIn("relation_count", data)

    def test_t15_graph(self):
        """T15: Graph weiterhin PASS."""
        status, data = http_get("/memory/graph")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "success")
        self.assertIn("nodes", data)
        self.assertIn("edges", data)

    def test_t16_audio_status(self):
        """T16: /audio/status funktioniert."""
        status, data = http_get("/audio/status")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "online")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
