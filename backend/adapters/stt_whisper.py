import os
import re
import shutil
import subprocess
import tempfile
import time
import logging
from typing import Optional

log = logging.getLogger("guialita.stt")


class WhisperSTTAdapter:
    """Lokale Speech-to-Text-Runtime: whisper.cpp (whisper-cli).

    Grund: llama_cpp_python hat keinen Audio-Support - das LFM2.5-Audio-Modell
    ist daher nicht direkt als STT nutzbar. whisper.cpp ist bereits gebaut
    und lokal vorhanden.
    """

    name = "whisper.cpp"

    def __init__(self, cli_path: str, model_path: str, tmp_dir: Optional[str] = None):
        self.cli_path = cli_path
        self.model_path = model_path
        self.tmp_dir = tmp_dir or tempfile.gettempdir()

    def is_available(self) -> bool:
        return os.path.isfile(self.cli_path) and os.path.isfile(self.model_path)

    def health(self) -> dict:
        if not os.path.isfile(self.cli_path):
            return {"status": "offline", "runtime": "whisper.cpp", "error": f"CLI fehlt: {self.cli_path}"}
        if not os.path.isfile(self.model_path):
            return {"status": "offline", "runtime": "whisper.cpp", "error": f"Modell fehlt: {self.model_path}"}
        size_gb = round(os.path.getsize(self.model_path) / 1e9, 2)
        return {
            "status": "online",
            "runtime": "whisper.cpp",
            "cli": self.cli_path,
            "model": os.path.basename(self.model_path),
            "model_size_gb": size_gb,
            "gpu": False,
        }

    def transcribe(self, wav_bytes: bytes, language: str = "auto", sample_rate: int = 16000) -> dict:
        """Transkribiert WAV-Daten. Liefert transcript, latency_ms, segments."""
        if not self.is_available():
            raise RuntimeError("whisper.cpp nicht verfuegbar (CLI oder Modell fehlt)")

        t0 = time.perf_counter()
        with tempfile.NamedTemporaryFile(suffix=".wav", dir=self.tmp_dir, delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(wav_bytes)

        cmd = [
            self.cli_path,
            "-m", self.model_path,
            "-f", tmp_path,
            "--no-prints",  # keine Fortschrittsausgabe
            "-np",          # no prints segments
            "-oj",          # JSON-Output
        ]
        if language and language != "auto":
            cmd += ["-l", language]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("whisper.cpp Timeout (>120s)")
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        t1 = time.perf_counter()

        if proc.returncode != 0:
            raise RuntimeError(f"whisper.cpp Fehler (exit {proc.returncode}): {proc.stderr[-300:]}")

        transcript = proc.stdout.strip()
        if not transcript:
            raise RuntimeError("Kein Text erkannt (leere oder zu kurze Aufnahme?)")

        # Timestamps der Segment-Ausgabe entfernen: "[00:00:00.000 --> 00:00:01.000]"
        transcript = re.sub(r"\[\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}\]\s*", "", transcript)
        transcript = transcript.strip()
        if not transcript:
            raise RuntimeError("Kein Text erkannt (leere oder zu kurze Aufnahme?)")

        return {
            "transcript": transcript,
            "latency_ms": round((t1 - t0) * 1000.0, 2),
            "runtime": self.name,
            "model": os.path.basename(self.model_path),
            "sample_rate": sample_rate,
        }