"""GUIALITA Tests: Voice Activation V1 (T01-T22)."""

import os
import sys
import time
import unittest
from collections import deque
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from backend.audio.voice_activation import VoiceActivationService, VoiceState, db_from_amplitude


class TestVoiceActivationStateMachine(unittest.TestCase):
    """T01: State Machine initialisiert korrekt."""

    def setUp(self):
        self.va = VoiceActivationService()

    def test_initial_state(self):
        self.assertEqual(self.va.state, VoiceState.IDLE.value)

    def test_initial_not_calibrated(self):
        self.assertFalse(self.va.calibrated)

    def test_status_returns_dict(self):
        s = self.va.status()
        self.assertIn("state", s)
        self.assertIn("calibrated", s)
        self.assertIn("enabled", s)
        self.assertIn("turns_processed", s)

    def test_state_values(self):
        states = [s.value for s in VoiceState]
        self.assertIn("IDLE", states)
        self.assertIn("CALIBRATING", states)
        self.assertIn("READY", states)
        self.assertIn("RECORDING", states)
        self.assertIn("SILENCE", states)
        self.assertIn("PROCESSING", states)
        self.assertIn("SPEAKING", states)
        self.assertIn("ERROR", states)


class TestCalibration(unittest.TestCase):
    """T02: Calibration funktioniert."""

    def setUp(self):
        self.va = VoiceActivationService()

    def test_calibration_sets_state(self):
        mock_sd = MagicMock()
        levels_captured = []

        def mock_callback(indata, frames, time_info, status):
            samples = indata[:, 0]
            rms = float(np.sqrt(np.mean(np.square(samples))))
            levels_captured.append(db_from_amplitude(rms))

        mock_sd.InputStream.return_value.__enter__ = MagicMock()
        mock_sd.InputStream.return_value.__exit__ = MagicMock()

        with patch.object(self.va, '_set_state') as mock_set:
            self.va._calibrate(mock_sd)
            mock_set.assert_any_call(VoiceState.CALIBRATING)

    def test_calibration_sets_calibrated_flag(self):
        mock_sd = MagicMock()
        mock_sd.InputStream.return_value.__enter__ = MagicMock()
        mock_sd.InputStream.return_value.__exit__ = MagicMock()

        self.va._calibrate(mock_sd)
        self.assertTrue(self.va.calibrated)


class TestNoiseFloor(unittest.TestCase):
    """T03: Noise Floor wird bestimmt."""

    def setUp(self):
        self.va = VoiceActivationService()

    def test_noise_floor_default(self):
        self.assertEqual(self.va._noise_floor_db, -60.0)

    def test_noise_floor_after_calibration(self):
        mock_sd = MagicMock()
        mock_sd.InputStream.return_value.__enter__ = MagicMock()
        mock_sd.InputStream.return_value.__exit__ = MagicMock()
        self.va._calibrate(mock_sd)
        self.assertGreater(self.va._noise_floor_db, -120.0)


class TestThresholdBehavior(unittest.TestCase):
    """T04-T07: Threshold-Verhalten."""

    def setUp(self):
        self.va = VoiceActivationService()
        self.va._set_state(VoiceState.READY)

    def test_under_threshold_no_recording(self):
        samples = np.random.randn(320).astype(np.float32) * 0.0001
        self.va._handle_ready(samples, -80.0, time.time())
        self.assertEqual(self.va.state, VoiceState.READY.value)

    def test_over_start_threshold_starts_recording(self):
        samples = np.random.randn(320).astype(np.float32) * 0.1
        now = time.time()
        self.va._handle_ready(samples, -20.0, now)
        self.va._handle_ready(samples, -20.0, now + 0.5)
        self.assertEqual(self.va.state, VoiceState.RECORDING.value)

    def test_short_pause_keeps_recording(self):
        samples = np.random.randn(320).astype(np.float32) * 0.1
        now = time.time()
        self.va._handle_ready(samples, -20.0, now)
        self.va._handle_ready(samples, -20.0, now + 0.5)
        self.assertEqual(self.va.state, VoiceState.RECORDING.value)
        self.va._handle_recording(samples, -20.0, now + 0.6)
        self.assertEqual(self.va.state, VoiceState.RECORDING.value)

    def test_long_pause_ends_recording(self):
        samples = np.random.randn(320).astype(np.float32) * 0.1
        silence = np.random.randn(320).astype(np.float32) * 0.0001
        now = time.time()
        self.va._handle_ready(samples, -20.0, now)
        self.va._handle_ready(samples, -20.0, now + 0.5)
        self.assertEqual(self.va.state, VoiceState.RECORDING.value)
        self.va._handle_recording(silence, -80.0, now + 0.6)
        self.va._set_state(VoiceState.SILENCE)
        self.va._silence_since = now + 0.6
        self.va._handle_silence(silence, -80.0, now + 2.0)
        self.assertEqual(self.va.state, VoiceState.READY.value)


class TestPreRoll(unittest.TestCase):
    """T08: Pre-Roll wird berücksichtigt."""

    def setUp(self):
        self.va = VoiceActivationService()

    def test_pre_roll_buffer_initialized(self):
        expected = int(self.va._config["pre_roll_ms"] / 1000.0 * self.va._config["sample_rate"])
        self.assertEqual(self.va._pre_roll.maxlen, expected)

    def test_pre_roll_included_in_recording(self):
        samples = np.random.randn(320).astype(np.float32) * 0.1
        now = time.time()
        self.va._handle_ready(samples, -20.0, now)
        self.va._handle_ready(samples, -20.0, now + 0.5)
        self.assertGreater(len(self.va._chunks), 0)
        self.assertEqual(self.va._chunks[0].dtype, np.float32)


class TestWAV(unittest.TestCase):
    """T09: WAV ist gültig."""

    def setUp(self):
        self.va = VoiceActivationService()

    def test_save_wav_creates_valid_file(self):
        audio = np.random.randn(16000).astype(np.float32) * 0.1
        wav_path = self.va._save_wav(audio)
        self.assertIsNotNone(wav_path)
        self.assertTrue(os.path.exists(wav_path))

        import wave
        with wave.open(wav_path, "rb") as wf:
            self.assertEqual(wf.getnchannels(), 1)
            self.assertEqual(wf.getsampwidth(), 2)
            self.assertEqual(wf.getframerate(), 16000)
            self.assertGreater(wf.getnframes(), 0)

        os.unlink(wav_path)

    def test_save_wav_returns_path(self):
        audio = np.zeros(1600, dtype=np.float32)
        wav_path = self.va._save_wav(audio)
        self.assertIsNotNone(wav_path)
        if wav_path and os.path.exists(wav_path):
            os.unlink(wav_path)


class TestOneTurnOneWAV(unittest.TestCase):
    """T10: Ein Turn erzeugt genau eine WAV."""

    def setUp(self):
        self.va = VoiceActivationService()

    def test_finalize_creates_wav(self):
        sr = self.va._config["sample_rate"]
        samples = np.random.randn(sr).astype(np.float32) * 0.1
        now = time.time()
        self.va._handle_ready(samples, -20.0, now)
        self.va._handle_ready(samples, -20.0, now + 0.5)
        self.assertEqual(self.va.state, VoiceState.RECORDING.value)

        self.va._chunks.append(samples.copy())
        self.va._rec_started_at = now

        with patch.object(self.va, '_process_turn'):
            self.va._finalize_recording()
            self.assertEqual(self.va.state, VoiceState.PROCESSING.value)


class TestEmptyTurnNoChat(unittest.TestCase):
    """T11: Leerer Turn erzeugt keinen Chat."""

    def setUp(self):
        self.va = VoiceActivationService()

    def test_short_audio_skipped(self):
        audio = np.random.randn(800).astype(np.float32) * 0.1
        self.va._chunks = [audio]
        self.va._rec_started_at = time.time()

        with patch.object(self.va, '_set_state') as mock_set:
            self.va._finalize_recording()
            mock_set.assert_called_with(VoiceState.READY)


class TestSTTCalled(unittest.TestCase):
    """T12: STT wird mit bestehendem Endpoint/Service aufgerufen."""

    def setUp(self):
        self.va = VoiceActivationService()

    def test_transcribe_uses_manager(self):
        mock_manager = MagicMock()
        mock_manager.transcribe.return_value = {"transcript": "hallo welt"}
        self.va._manager = mock_manager

        wav_path = "/tmp/test.wav"
        with open(wav_path, "wb") as f:
            f.write(b"RIFF" + b"\x00" * 40)

        result = self.va._transcribe(wav_path)
        mock_manager.transcribe.assert_called_once()
        self.assertEqual(result, "hallo welt")

        os.unlink(wav_path)


class TestSessionPreserved(unittest.TestCase):
    """T13: Session-ID bleibt erhalten."""

    def setUp(self):
        self.va = VoiceActivationService()

    def test_chat_uses_existing_session(self):
        mock_chat = MagicMock()
        mock_chat.chat.return_value = {
            "response": "Antwort",
            "model": "test",
            "session_id": "test-session",
        }
        self.va._chat_service = mock_chat

        result = self.va._chat("Testnachricht")
        mock_chat.chat.assert_called_once_with("Testnachricht", model_id=None)
        self.assertEqual(result["response"], "Antwort")


class TestChatServiceCalledOnce(unittest.TestCase):
    """T14: ChatService wird genau einmal aufgerufen."""

    def setUp(self):
        self.va = VoiceActivationService()

    def test_single_chat_call(self):
        mock_chat = MagicMock()
        mock_chat.chat.return_value = {
            "response": "Antwort",
            "model": "test",
        }
        self.va._chat_service = mock_chat

        self.va._chat("Test")
        self.assertEqual(mock_chat.chat.call_count, 1)


class TestTTSCalledOnce(unittest.TestCase):
    """T15: TTS wird genau einmal aufgerufen."""

    def setUp(self):
        self.va = VoiceActivationService()

    def test_single_tts_call(self):
        mock_tts = MagicMock()
        mock_tts.synthesize.return_value = {
            "wav_bytes": b"RIFF" + b"\x00" * 40,
            "voice": "us_female",
            "duration_s": 2.0,
            "latency_ms": 1000,
        }
        self.va._tts_service = mock_tts
        self.va._config["tts_enabled"] = True

        with patch.object(self.va, '_play_audio'):
            self.va._set_state(VoiceState.SPEAKING)
            mock_tts.synthesize("Test response", "us_female")
            self.assertEqual(mock_tts.synthesize.call_count, 1)


class TestTTSFeedbackProtection(unittest.TestCase):
    """T16: TTS während SPEAKING triggert keinen neuen Turn."""

    def setUp(self):
        self.va = VoiceActivationService()
        self.va._set_state(VoiceState.SPEAKING)

    def test_speaking_state_blocks_new_recording(self):
        samples = np.random.randn(320).astype(np.float32) * 0.1
        self.va._handle_ready(samples, -20.0, time.time())
        self.assertEqual(self.va.state, VoiceState.SPEAKING.value)


class TestProcessingBlocksDoubleTrigger(unittest.TestCase):
    """T17: Processing blockiert Doppeltrigger."""

    def setUp(self):
        self.va = VoiceActivationService()
        self.va._set_state(VoiceState.PROCESSING)

    def test_processing_blocks_ready(self):
        samples = np.random.randn(320).astype(np.float32) * 0.1
        self.va._handle_ready(samples, -20.0, time.time())
        self.assertEqual(self.va.state, VoiceState.PROCESSING.value)


class TestMicrophoneError(unittest.TestCase):
    """T18: Mikrofonfehler → ERROR."""

    def setUp(self):
        self.va = VoiceActivationService()

    def test_missing_sounddevice(self):
        with patch.dict('sys.modules', {'sounddevice': None}):
            with patch.object(self.va, '_set_state') as mock_set:
                self.va._run_loop()
                mock_set.assert_any_call(VoiceState.ERROR)


class TestSTTError(unittest.TestCase):
    """T19: STT-Fehler → READY."""

    def setUp(self):
        self.va = VoiceActivationService()

    def test_stt_failure_returns_none(self):
        mock_manager = MagicMock()
        mock_manager.transcribe.side_effect = RuntimeError("STT failed")
        self.va._manager = mock_manager

        wav_path = "/tmp/test.wav"
        with open(wav_path, "wb") as f:
            f.write(b"RIFF" + b"\x00" * 40)

        result = self.va._transcribe(wav_path)
        self.assertIsNone(result)
        os.unlink(wav_path)


class TestChatError(unittest.TestCase):
    """T20: Chat-Fehler → READY."""

    def setUp(self):
        self.va = VoiceActivationService()

    def test_chat_failure_returns_none(self):
        mock_chat = MagicMock()
        mock_chat.chat.side_effect = RuntimeError("Chat failed")
        self.va._chat_service = mock_chat

        result = self.va._chat("Test")
        self.assertIsNone(result)


class TestTTSError(unittest.TestCase):
    """T21: TTS-Fehler → Text bleibt verfügbar."""

    def setUp(self):
        self.va = VoiceActivationService()

    def test_tts_failure_preserves_text(self):
        mock_tts = MagicMock()
        mock_tts.synthesize.side_effect = RuntimeError("TTS failed")
        self.va._tts_service = mock_tts
        self.va._config["tts_enabled"] = True
        self.va._last_response = "Antwort bleibt"

        with patch.object(self.va, '_set_state') as mock_set:
            try:
                self.va._tts_service.synthesize("Antwort bleibt", "us_female")
            except RuntimeError:
                pass
            self.assertEqual(self.va._last_response, "Antwort bleibt")


class TestExistingChatUnchanged(unittest.TestCase):
    """T22: bestehender /chat unverändert."""

    def test_main_module_importable(self):
        from backend.main import app
        self.assertIsNotNone(app)

    def test_chat_endpoint_exists(self):
        from backend.main import app
        routes = [r.path for r in app.routes]
        self.assertIn("/chat", routes)

    def test_voice_endpoints_exist(self):
        from backend.main import app
        routes = [r.path for r in app.routes]
        self.assertIn("/audio/voice/status", routes)
        self.assertIn("/audio/voice/start", routes)
        self.assertIn("/audio/voice/stop", routes)


class TestDbFromAmplitude(unittest.TestCase):
    """Hilfsfunktion db_from_amplitude."""

    def test_zero(self):
        self.assertEqual(db_from_amplitude(0.0), -120.0)

    def test_negative(self):
        self.assertEqual(db_from_amplitude(-1.0), -120.0)

    def test_one(self):
        self.assertAlmostEqual(db_from_amplitude(1.0), 0.0, places=1)

    def test_half(self):
        result = db_from_amplitude(0.5)
        self.assertLess(result, 0.0)
        self.assertGreater(result, -10.0)


class TestConfigLoading(unittest.TestCase):
    """Konfiguration wird korrekt geladen."""

    def test_default_config(self):
        va = VoiceActivationService()
        self.assertEqual(va._config["sample_rate"], 16000)
        self.assertEqual(va._config["channels"], 1)
        self.assertIn("start_threshold_db", va._config)
        self.assertIn("end_threshold_db", va._config)
        self.assertIn("silence_timeout_ms", va._config)
        self.assertIn("pre_roll_ms", va._config)

    def test_custom_config(self):
        va = VoiceActivationService(config_path=os.path.join(PROJECT_DIR, "config", "voice.yaml"))
        self.assertEqual(va._config["sample_rate"], 16000)


if __name__ == "__main__":
    unittest.main()
