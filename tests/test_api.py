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


_CAPABILITIES = None


def capabilities() -> dict:
    """Fähigkeiten des laufenden Backends (einmalig pro Testlauf ermittelt).

    Quelle ist /diagnostics, damit die Suite selbst entscheidet, was auf
    dieser Maschine wirklich vorhanden ist — statt pauschal abzubrechen.
    """
    global _CAPABILITIES
    if _CAPABILITIES is None:
        try:
            _, data = http_get("/diagnostics")
            _CAPABILITIES = data.get("capabilities", {}) or {}
        except Exception:
            _CAPABILITIES = {}
    return _CAPABILITIES


def require_real(capability: str, what: str):
    """Überspringt einen Test sauber, wenn die echte Runtime fehlt.

    Grund: Ohne Modelldatei/whisper.cpp lief früher die GESAMTE Suite als
    NOT_EXECUTED — auch die Tests, die nur den API-Vertrag prüfen. Jetzt
    wird der Vertrag geprüft und nur der runtime-abhängige Teil mit
    Begründung übersprungen (skip != fail).
    """
    if not capabilities().get(capability, False):
        raise unittest.SkipTest(f"{what} — Fähigkeit '{capability}' fehlt auf dieser Maschine")


def require_chat(what: str):
    """Überspringt Tests, die einen funktionierenden Chat-Pfad brauchen.

    Der Pfad ist entweder echt (llama-cpp-python + Modell) oder über den
    Test-Adapter (GUIALITA_MOCK_LLM=1) verfügbar. Ohne beides kann kein
    Erfolg geprüft werden — dann ist es eine fehlende Voraussetzung, kein
    Codefehler.
    """
    caps = capabilities()
    if not (caps.get("llm", False) or caps.get("llm_mock", False)):
        raise unittest.SkipTest(
            f"{what} — weder echte LLM-Runtime noch Mock-Adapter verfügbar")


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


class TestDiagnostics(unittest.TestCase):
    """Diagnose-Endpunkt: aufgelöste Pfade und fehlende Fähigkeiten."""

    def test_diagnostics_returns_200(self):
        status, data = http_get("/diagnostics")
        self.assertEqual(status, 200)
        self.assertIn("environment", data)
        self.assertIn("capabilities", data)

    def test_diagnostics_lists_env_variables(self):
        _, data = http_get("/diagnostics")
        for key in ("GUIALITA_ROOT", "GUIALITA_MODEL_ROOT",
                    "GUIALITA_EXTERNAL_MODEL_ROOT", "GUIALITA_WHISPER_CLI"):
            self.assertIn(key, data["environment"], f"{key} fehlt in /diagnostics")

    def test_diagnostics_model_paths_are_absolute_and_checked(self):
        _, data = http_get("/diagnostics")
        self.assertGreater(len(data["models"]), 0)
        real = 0
        for mid, m in data["models"].items():
            # Der Mock-Adapter hat konstruktionsbedingt keine Modelldatei —
            # er wird geprüft, aber nicht an Dateipfaden gemessen.
            if m.get("adapter") == "mock":
                self.assertEqual(m["path"], "", f"{mid}: Mock darf keinen Pfad haben")
                continue
            real += 1
            self.assertTrue(m["path"].startswith("/"), f"{mid}: Pfad nicht absolut")
            self.assertNotIn("${", m["path"], f"{mid}: Platzhalter nicht aufgelöst")
            self.assertIn("exists", m)
        self.assertGreater(real, 0, "Mindestens ein echtes Modell muss konfiguriert sein")

    def test_diagnostics_reports_missing_capabilities(self):
        _, data = http_get("/diagnostics")
        caps = data["capabilities"]
        missing = data["missing_capabilities"]
        self.assertEqual(sorted(missing), sorted(k for k, v in caps.items() if not v))
        self.assertEqual(data["ready_for_voice_turn"], not missing)

    def test_diagnostics_stt_engine_is_supported(self):
        _, data = http_get("/diagnostics")
        self.assertIn(data["stt"]["engine"], data["stt"]["supported_engines"])


class TestModelConnectivity(unittest.TestCase):
    def test_models_listed(self):
        _, data = http_get("/models")
        self.assertGreater(len(data["models"]), 0)
        available = [m for m in data["models"] if m["available"]]
        self.assertGreater(len(available), 0, "Mindestens ein Modell muss verfuegbar sein")

    def test_granite_model_available(self):
        require_real("llm", "granite-3b (GGUF + llama-cpp-python) nicht vorhanden")
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
        require_chat("Chat-Erfolgsformat nicht prüfbar")
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
        require_real("llm", "echte LLM-Runtime fehlt — Mock zählt hier nicht als LFM-Antwort")
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
        require_real("stt", "whisper.cpp (CLI oder ggml-base.bin) nicht vorhanden")
        _, data = http_get("/audio/status")
        self.assertEqual(data["status"], "online")
        self.assertEqual(data["engine"], "whisper.cpp")


class TestAudioTranscribe(unittest.TestCase):
    def test_valid_wav_transcribes(self):
        require_real("stt", "whisper.cpp (CLI oder ggml-base.bin) nicht vorhanden")
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
        require_real("stt", "whisper.cpp (CLI oder ggml-base.bin) nicht vorhanden")
        require_real("llm", "echte LLM-Runtime fehlt (chat_runtime muss 'llamacpp' sein)")
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


class TestMockRuntime(unittest.TestCase):
    """Vollständiger API-Pfad ohne Modelle/GPU — über den Test-Adapter.

    Diese Tests sind nur aussagekräftig, wenn GUIALITA_MOCK_LLM=1 gesetzt ist.
    Sie beweisen, dass Session → Memory → Retrieval → ChatService → Adapter →
    Persistenz → Audit lokal laufen, ohne dass eine echte Runtime nötig ist.
    Sie ersetzen KEINE Prüfung der echten LLM-/STT-Runtime.
    """

    def setUp(self):
        if not capabilities().get("llm_mock", False):
            self.skipTest("GUIALITA_MOCK_LLM ist nicht aktiv (kein Test-Adapter)")

    def test_mock_flag_is_reported(self):
        _, data = http_get("/diagnostics")
        self.assertTrue(data["mock_llm_enabled"])
        self.assertTrue(data["capabilities"]["llm_mock"])
        # Mock darf die echte Fähigkeit nicht vortäuschen:
        self.assertFalse(data["ready_for_voice_turn"],
                         "Mock-Modus darf nicht als voice-ready gemeldet werden")

    def test_mock_chat_full_loop_persists(self):
        status, data = http_post("/chat", {"message": "Mock-Loop-Test", "model": "mock-1b"})
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["runtime"], "mock")
        self.assertIn("MOCK-LLM-OK", data["response"])
        self.assertTrue(data["session_id"].startswith("SES-"))
        self.assertTrue(data["message_id"].startswith("MSG-"))

        # Persistenz prüfen: beide Nachrichten müssen in der Session liegen.
        _, msgs = http_get(f"/sessions/{data['session_id']}/messages")
        self.assertEqual(msgs["count"], 2)
        self.assertEqual(msgs["messages"][0]["role"], "user")
        self.assertEqual(msgs["messages"][1]["role"], "assistant")

    def test_mock_chat_is_deterministic(self):
        _, first = http_post("/chat", {"message": "deterministisch", "model": "mock-1b"})
        _, second = http_post("/chat", {"message": "deterministisch", "model": "mock-1b"})
        self.assertEqual(first["response"], second["response"])

    def test_mock_session_export_contains_no_secrets(self):
        _, data = http_post("/chat", {"message": "Export-Test", "model": "mock-1b"})
        sid = data["session_id"]
        req = urllib.request.Request(f"{BASE_URL}/sessions/{sid}/export")
        with urllib.request.urlopen(req, timeout=30) as r:
            export = json.loads(r.read().decode())
        self.assertEqual(export["status"], "success")
        self.assertEqual(export["message_count"], 2)
        # Audit schreibt nur Metadaten — niemals Antwortinhalte.
        for event in export["audit_events"]:
            self.assertNotIn("response", event)
            self.assertNotIn("transcript", event)
            self.assertNotIn("content", event)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
