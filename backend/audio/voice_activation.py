"""GUIALITA Voice Activation — Backend-gesteuerte Auto-Trigger-Stimmerkennung.

Flow:
    Mikrofon (sounddevice)
      ↓ Energy-Monitoring (IDLE)
      ↓ Threshold überschritten
      ↓ CALIBRATING → READY
      ↓ Sprache erkannt → RECORDING
      ↓ Stille → SILENCE
      ↓ Silence-Timeout → PROCESSING
      ↓ Whisper STT → Transcript
      ↓ ChatService → Text Response
      ↓ LFM2.5-Audio TTS → Audio
      ↓ READY (Post-TTS-Cooldown)
"""

import logging
import math
import os
import struct
import tempfile
import threading
import time
import wave
from collections import deque
from enum import Enum
from typing import Optional

import numpy as np

logger = logging.getLogger("guialita.voice_activation")


class VoiceState(str, Enum):
    IDLE = "IDLE"
    CALIBRATING = "CALIBRATING"
    READY = "READY"
    RECORDING = "RECORDING"
    SILENCE = "SILENCE"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    ERROR = "ERROR"


def db_from_amplitude(value: float, full_scale: float = 1.0) -> float:
    if value <= 0.0:
        return -120.0
    return 20.0 * math.log10(value / full_scale)


class VoiceActivationService:
    """Voice Activation mit Energy-basiertem Trigger.

    Wiederverwendet:
      - Manager.transcribe() für STT (whisper.cpp)
      - ChatService.chat() für LLM + Session + Memory
      - TTSService.synthesize() für Audio-Ausgabe
    """

    def __init__(self, manager=None, chat_service=None, tts_service=None, config_path: str = None):
        self._manager = manager
        self._chat_service = chat_service
        self._tts_service = tts_service

        self._config = self._load_config(config_path)
        self._state = VoiceState.IDLE
        self._lock = threading.Lock()
        self._audio_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Kalibrierung
        self._noise_floor_db = -60.0
        self._calibrated = False

        # Pre-Roll Buffer
        self._pre_roll_samples = int(
            self._config["pre_roll_ms"] / 1000.0 * self._config["sample_rate"]
        )
        self._pre_roll = deque(maxlen=self._pre_roll_samples)

        # Recording
        self._chunks: list = []
        self._speech_since: Optional[float] = None
        self._silence_since: Optional[float] = None
        self._rec_started_at: Optional[float] = None
        self._current_wav_path: Optional[str] = None

        # Self-TTS Feedback
        self._tts_end_time: Optional[float] = None

        # Statistiken
        self._turns_processed = 0
        self._last_transcript: Optional[str] = None
        self._last_response: Optional[str] = None
        self._last_latency_ms: float = 0.0

        # Callback für Frontend-Updates
        self._state_change_callback = None

    def _load_config(self, config_path: str = None) -> dict:
        defaults = {
            "sample_rate": 16000,
            "channels": 1,
            "block_ms": 20,
            "start_threshold_db": -35.0,
            "end_threshold_db": -45.0,
            "minimum_speech_ms": 400,
            "silence_timeout_ms": 1000,
            "maximum_recording_ms": 30000,
            "pre_roll_ms": 200,
            "calibration_ms": 500,
            "noise_margin_db": 10.0,
            "post_tts_cooldown_ms": 1500,
            "device": None,
            "stt_engine": "whisper",
            "chat_model": None,
            "tts_enabled": True,
            "tts_voice": "us_female",
            "debug": False,
        }

        if config_path is None:
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_path = os.path.join(base, "config", "voice.yaml")

        if os.path.isfile(config_path):
            try:
                import yaml
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                va = cfg.get("voice_activation", {})
                for k, v in defaults.items():
                    if k in va:
                        defaults[k] = va[k]
                logger.info("Voice-Konfiguration geladen: %s", config_path)
            except Exception as e:
                logger.warning("voice.yaml nicht lesbar (%s) - nutze Defaults", e)

        return defaults

    @property
    def state(self) -> str:
        return self._state.value

    @property
    def calibrated(self) -> bool:
        return self._calibrated

    def set_state_change_callback(self, callback):
        self._state_change_callback = callback

    def _set_state(self, new_state: VoiceState):
        with self._lock:
            old = self._state
            self._state = new_state
            if old != new_state:
                logger.info("State: %s -> %s", old.value, new_state.value)
                if self._state_change_callback:
                    try:
                        self._state_change_callback(old.value, new_state.value)
                    except Exception:
                        pass

    def status(self) -> dict:
        with self._lock:
            return {
                "enabled": self._audio_thread is not None and self._audio_thread.is_alive(),
                "state": self._state.value,
                "calibrated": self._calibrated,
                "noise_floor_db": round(self._noise_floor_db, 1),
                "turns_processed": self._turns_processed,
                "last_transcript": self._last_transcript,
                "last_response": self._last_response,
                "last_latency_ms": round(self._last_latency_ms, 1),
                "start_threshold_db": round(self._effective_start_threshold(), 1),
                "end_threshold_db": round(self._effective_end_threshold(), 1),
                "sample_rate": self._config["sample_rate"],
                "pre_roll_ms": self._config["pre_roll_ms"],
                "silence_timeout_ms": self._config["silence_timeout_ms"],
                "post_tts_cooldown_ms": self._config["post_tts_cooldown_ms"],
            }

    def _effective_start_threshold(self) -> float:
        if self._calibrated:
            return self._noise_floor_db + self._config["noise_margin_db"]
        return self._config["start_threshold_db"]

    def _effective_end_threshold(self) -> float:
        return self._config["end_threshold_db"]

    def start(self):
        if self._audio_thread and self._audio_thread.is_alive():
            logger.warning("Voice Activation bereits aktiv")
            return
        self._stop_event.clear()
        self._audio_thread = threading.Thread(target=self._run_loop, daemon=True, name="voice-activation")
        self._audio_thread.start()
        logger.info("Voice Activation gestartet")

    def stop(self):
        self._stop_event.set()
        if self._audio_thread:
            self._audio_thread.join(timeout=5.0)
            self._audio_thread = None
        self._set_state(VoiceState.IDLE)
        logger.info("Voice Activation gestoppt")

    def _run_loop(self):
        try:
            import sounddevice as sd
        except ImportError:
            logger.error("sounddevice nicht installiert")
            self._set_state(VoiceState.ERROR)
            return

        cfg = self._config
        try:
            self._calibrate(sd)
            self._set_state(VoiceState.READY)

            with sd.InputStream(
                device=cfg["device"],
                samplerate=cfg["sample_rate"],
                channels=cfg["channels"],
                dtype="float32",
                blocksize=int(cfg["sample_rate"] * cfg["block_ms"] / 1000.0),
                callback=self._audio_callback,
            ):
                while not self._stop_event.is_set():
                    sd.sleep(50)

        except Exception as e:
            logger.error("Voice Activation Fehler: %s", e)
            self._set_state(VoiceState.ERROR)

    def _calibrate(self, sd):
        cfg = self._config
        self._set_state(VoiceState.CALIBRATING)
        logger.info("Kalibrierung: messe Umgebungsgeräusch (%d ms)...", cfg["calibration_ms"])

        levels = []
        duration_s = cfg["calibration_ms"] / 1000.0
        block_size = int(cfg["sample_rate"] * cfg["block_ms"] / 1000.0)
        n_blocks = max(1, int(duration_s / (cfg["block_ms"] / 1000.0)))

        def collect_callback(indata, frames, time_info, status):
            samples = indata[:, 0]
            rms = float(np.sqrt(np.mean(np.square(samples))))
            levels.append(db_from_amplitude(rms))

        try:
            with sd.InputStream(
                device=cfg["device"],
                samplerate=cfg["sample_rate"],
                channels=cfg["channels"],
                dtype="float32",
                blocksize=block_size,
                callback=collect_callback,
            ):
                sd.sleep(cfg["calibration_ms"] + 100)
        except Exception as e:
            logger.warning("Kalibrierung fehlgeschlagen: %s", e)

        if levels:
            self._noise_floor_db = float(np.median(levels))
            start_threshold = self._noise_floor_db + cfg["noise_margin_db"]
            logger.info(
                "Kalibrierung: noise_floor=%.1f dBFS, start_threshold=%.1f dBFS",
                self._noise_floor_db, start_threshold,
            )
        else:
            logger.warning("Kalibrierung: keine Daten, nutze manuelle Schwelle")

        self._calibrated = True

    def _audio_callback(self, indata, frames, time_info, status):
        if self._stop_event.is_set():
            return

        samples = indata[:, 0]
        rms = float(np.sqrt(np.mean(np.square(samples))))
        rms_db = db_from_amplitude(rms)

        self._pre_roll.extend(samples)

        current_state = self._state

        if current_state == VoiceState.READY:
            self._handle_ready(samples, rms_db, time.time())
        elif current_state == VoiceState.RECORDING:
            self._handle_recording(samples, rms_db, time.time())
        elif current_state == VoiceState.SILENCE:
            self._handle_silence(samples, rms_db, time.time())

    def _handle_ready(self, samples, rms_db, now):
        start_threshold = self._effective_start_threshold()

        if rms_db > start_threshold:
            if self._speech_since is None:
                self._speech_since = now
                if self._config["debug"]:
                    logger.debug("[VAD] SPEECH START (pending) RMS=%.1f dB", rms_db)

            min_speech_s = self._config["minimum_speech_ms"] / 1000.0
            if now - self._speech_since >= min_speech_s:
                self._start_recording(now)
        else:
            self._speech_since = None

    def _handle_recording(self, samples, rms_db, now):
        self._chunks.append(samples.copy())

        start_threshold = self._effective_start_threshold()

        if rms_db > start_threshold:
            self._silence_since = None
        else:
            if self._silence_since is None:
                self._silence_since = now

            silence_s = self._config["silence_timeout_ms"] / 1000.0
            duration_s = now - self._rec_started_at
            max_s = self._config["maximum_recording_ms"] / 1000.0

            if now - self._silence_since >= silence_s or duration_s >= max_s:
                self._set_state(VoiceState.SILENCE)
                if self._config["debug"]:
                    reason = "silence" if now - self._silence_since >= silence_s else "max_duration"
                    logger.debug("[VAD] RECORDING END (reason=%s, dur=%.2fs)", reason, duration_s)

    def _handle_silence(self, samples, rms_db, now):
        start_threshold = self._effective_start_threshold()

        if rms_db > start_threshold:
            self._silence_since = None
            self._set_state(VoiceState.RECORDING)
            if self._config["debug"]:
                logger.debug("[VAD] SILENCE -> RECORDING (speech resumed)")
        else:
            if self._silence_since is None:
                self._silence_since = now

            silence_s = self._config["silence_timeout_ms"] / 1000.0
            if now - self._silence_since >= silence_s:
                self._finalize_recording()

    def _start_recording(self, now):
        self._set_state(VoiceState.RECORDING)
        self._rec_started_at = now
        self._silence_since = None
        self._chunks = [np.array(list(self._pre_roll), dtype=np.float32)]
        if self._config["debug"]:
            logger.debug("[REC] recording started (mit Pre-Roll)")

    def _finalize_recording(self):
        if not self._chunks:
            self._set_state(VoiceState.READY)
            return

        audio = np.concatenate(self._chunks)
        self._chunks = []
        self._pre_roll.clear()

        duration_ms = int(len(audio) / self._config["sample_rate"] * 1000.0)
        if duration_ms < 100:
            logger.info("Aufnahme zu kurz (%d ms) - ignoriere", duration_ms)
            self._set_state(VoiceState.READY)
            return

        wav_path = self._save_wav(audio)
        if wav_path is None:
            self._set_state(VoiceState.READY)
            return

        self._current_wav_path = wav_path
        self._set_state(VoiceState.PROCESSING)

        thread = threading.Thread(
            target=self._process_turn, args=(wav_path,), daemon=True, name="voice-process"
        )
        thread.start()

    def _save_wav(self, audio: np.ndarray) -> Optional[str]:
        try:
            pcm = np.clip(audio * 32768.0, -32768.0, 32767.0).astype(np.int16)
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            with wave.open(tmp.name, "wb") as wf:
                wf.setnchannels(self._config["channels"])
                wf.setsampwidth(2)
                wf.setframerate(self._config["sample_rate"])
                wf.writeframes(pcm.tobytes())
            return tmp.name
        except Exception as e:
            logger.error("WAV-Erzeugung fehlgeschlagen: %s", e)
            return None

    def _process_turn(self, wav_path: str):
        try:
            self._process_turn_inner(wav_path)
        except Exception as e:
            logger.error("Turn-Verarbeitung fehlgeschlagen: %s", e)
            self._set_state(VoiceState.ERROR)
            time.sleep(2.0)
            self._set_state(VoiceState.READY)
        finally:
            try:
                os.unlink(wav_path)
            except OSError:
                pass

    def _process_turn_inner(self, wav_path: str):
        t0 = time.time()

        # STT
        transcript = self._transcribe(wav_path)
        if not transcript:
            logger.info("Kein Transcript erkannt -> READY")
            self._set_state(VoiceState.READY)
            return

        self._last_transcript = transcript
        logger.info("Transcript: %s", transcript)

        # Chat
        chat_result = self._chat(transcript)
        if chat_result is None:
            self._set_state(VoiceState.READY)
            return

        response = chat_result["response"]
        self._last_response = response
        logger.info("Response: %s", response[:80])

        # TTS
        if self._config["tts_enabled"] and self._tts_service:
            self._set_state(VoiceState.SPEAKING)
            try:
                tts_result = self._tts_service.synthesize(
                    response, self._config["tts_voice"]
                )
                self._tts_end_time = time.time()
                self._play_audio(tts_result["wav_bytes"])
            except Exception as e:
                logger.warning("TTS fehlgeschlagen: %s", e)
                self._tts_end_time = time.time()

        self._turns_processed += 1
        self._last_latency_ms = (time.time() - t0) * 1000.0

        # Post-TTS Cooldown
        cooldown_s = self._config["post_tts_cooldown_ms"] / 1000.0
        if self._tts_end_time:
            elapsed = time.time() - self._tts_end_time
            if elapsed < cooldown_s:
                time.sleep(cooldown_s - elapsed)

        self._pre_roll.clear()
        self._set_state(VoiceState.READY)

    def _transcribe(self, wav_path: str) -> Optional[str]:
        try:
            with open(wav_path, "rb") as f:
                wav_bytes = f.read()

            if self._manager and hasattr(self._manager, "transcribe"):
                result = self._manager.transcribe(wav_bytes)
                return result.get("transcript", "").strip()
        except Exception as e:
            logger.error("STT fehlgeschlagen: %s", e)
        return None

    def _chat(self, transcript: str) -> Optional[dict]:
        try:
            if self._chat_service:
                return self._chat_service.chat(
                    transcript,
                    model_id=self._config.get("chat_model"),
                )
        except Exception as e:
            logger.error("Chat fehlgeschlagen: %s", e)
        return None

    def _play_audio(self, wav_bytes: bytes):
        try:
            import sounddevice as sd
            with wave.open(tempfile.NamedTemporaryFile(suffix=".wav", delete=False), "rb") as wf:
                pass

            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.write(wav_bytes)
            tmp.close()

            with wave.open(tmp.name, "rb") as wf:
                sr = wf.getframerate()
                nchannels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                nframes = wf.getnframes()
                raw = wf.readframes(nframes)

            if sampwidth == 2:
                audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                audio = np.frombuffer(raw, dtype=np.float32)

            if nchannels > 1:
                audio = audio[::nchannels]

            sd.play(audio, sr)
            sd.wait()

            try:
                os.unlink(tmp.name)
            except OSError:
                pass

        except Exception as e:
            logger.warning("Audio-Wiedergabe fehlgeschlagen: %s", e)
