"""GUIALITA TTS Service — LFM2.5-Audio Text-to-Speech."""

import os
import subprocess
import tempfile
import struct
import logging
import time

from .. import paths

logger = logging.getLogger("guialita.tts")

PROJECT_DIR = paths.root()
RUNTIME_DIR = os.path.join(paths.runtime_root(), "liquid-audio")
CLI_BINARY = os.path.join(RUNTIME_DIR, "llama-liquid-audio-cli")

_AUDIO_MODEL_DIR = os.path.join(paths.model_root(), "lfm-audio-1.5b")
DEFAULT_MODEL = os.path.join(_AUDIO_MODEL_DIR, "LFM2.5-Audio-1.5B-Q4_0.gguf")
DEFAULT_MMPROJ = os.path.join(_AUDIO_MODEL_DIR, "mmproj-LFM2.5-Audio-1.5B-Q4_0.gguf")
DEFAULT_VOCODER = os.path.join(_AUDIO_MODEL_DIR, "vocoder-LFM2.5-Audio-1.5B-Q4_0.gguf")
DEFAULT_TOKENIZER = os.path.join(_AUDIO_MODEL_DIR, "tokenizer-LFM2.5-Audio-1.5B-Q4_0.gguf")

VOICES = {
    "us_female": "Perform TTS. Use the US female voice.",
    "us_male": "Perform TTS. Use the US male voice.",
    "uk_female": "Perform TTS. Use the UK female voice.",
    "uk_male": "Perform TTS. Use the UK male voice.",
}

DEFAULT_VOICE = "us_female"
TIMEOUT_SECONDS = 120


class TTSService:
    """LFM2.5-Audio TTS via llama-liquid-audio-cli."""

    def __init__(self):
        self._available = None

    def is_available(self) -> bool:
        # A failed startup check must not stay stale: model files may be mounted
        # or downloaded after the API process has started. Recheck while absent,
        # cache only the successful result.
        if self._available is not True:
            available = (
                os.path.isfile(CLI_BINARY)
                and os.access(CLI_BINARY, os.X_OK)
                and os.path.isfile(DEFAULT_MODEL)
                and os.path.isfile(DEFAULT_MMPROJ)
                and os.path.isfile(DEFAULT_VOCODER)
                and os.path.isfile(DEFAULT_TOKENIZER)
            )
            if available and self._available is not True:
                logger.info("TTS Service bereit: LFM2.5-Audio via %s", CLI_BINARY)
            self._available = available
        return bool(self._available)

    def health(self) -> dict:
        return {
            "available": self.is_available(),
            "model": "LFM2.5-Audio-1.5B",
            "runtime": "llama-liquid-audio-cli",
            "voices": list(VOICES.keys()),
            "default_voice": DEFAULT_VOICE,
        }

    def synthesize(self, text: str, voice: str = None) -> dict:
        # Validate caller input before checking optional local model assets. This
        # keeps API semantics deterministic even on machines without TTS files.
        if not text or not text.strip():
            raise ValueError("Text darf nicht leer sein")

        voice = voice or DEFAULT_VOICE
        if voice not in VOICES:
            raise ValueError(f"Ungültige Voice: {voice}. Verfügbar: {list(VOICES.keys())}")

        if not self.is_available():
            raise RuntimeError("TTS Service nicht verfügbar")

        text = text.strip()
        system_prompt = VOICES[voice]

        t_start = time.time()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            output_path = tmp.name

        try:
            env = os.environ.copy()
            env["LD_LIBRARY_PATH"] = RUNTIME_DIR + ":" + env.get("LD_LIBRARY_PATH", "")

            cmd = [
                CLI_BINARY,
                "-m", DEFAULT_MODEL,
                "-mm", DEFAULT_MMPROJ,
                "-mv", DEFAULT_VOCODER,
                "--tts-speaker-file", DEFAULT_TOKENIZER,
                "-sys", system_prompt,
                "-p", text,
                "--output", output_path,
            ]

            result = subprocess.run(
                cmd, capture_output=True,
                timeout=TIMEOUT_SECONDS, env=env,
            )

            if result.returncode != 0:
                stderr = result.stderr[-500:].decode("utf-8", errors="replace") if result.stderr else ""
                raise RuntimeError(f"TTS CLI Fehler (rc={result.returncode}): {stderr}")

            if not os.path.isfile(output_path) or os.path.getsize(output_path) < 44:
                raise RuntimeError("TTS: Keine gültige WAV-Datei erzeugt")

            wav_bytes = open(output_path, "rb").read()
            wav_info = self._parse_wav(wav_bytes)

            t_total = time.time() - t_start

            return {
                "wav_bytes": wav_bytes,
                "sample_rate": wav_info["sample_rate"],
                "channels": wav_info["channels"],
                "duration_s": wav_info["duration"],
                "size_bytes": len(wav_bytes),
                "latency_ms": round(t_total * 1000),
                "voice": voice,
                "text": text,
            }

        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def _parse_wav(self, data: bytes) -> dict:
        if len(data) < 44 or data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
            return {"sample_rate": 24000, "channels": 1, "duration": 0.0}

        fmt_code = struct.unpack_from("<H", data, 20)[0]
        channels = struct.unpack_from("<H", data, 22)[0]
        sample_rate = struct.unpack_from("<I", data, 24)[0]
        bits_per_sample = struct.unpack_from("<H", data, 34)[0]

        data_offset = 20 + struct.unpack_from("<I", data, 16)[0]
        if data_offset + 8 > len(data):
            return {"sample_rate": sample_rate, "channels": channels, "duration": 0.0}

        data_size = struct.unpack_from("<I", data, data_offset + 4)[0]
        bytes_per_sample = channels * bits_per_sample // 8
        duration = data_size / (sample_rate * bytes_per_sample) if bytes_per_sample > 0 else 0.0

        return {"sample_rate": sample_rate, "channels": channels, "duration": duration}


tts_service = TTSService()
