#!/usr/bin/env python3
"""GUIALITA PHASE 1A — Continuous Microphone -> VAD/Level -> WAV Capture.

Kontinuierliches Mikrofon-Monitoring mit Level-basierter
Spracherkennung und automatischer WAV-Aufnahme.

Kein STT, kein TTS, kein LLM. Die WAV ist das Endprodukt dieser Phase.

Usage:
    python scripts/audio_capture.py                     # Standardlauf
    python scripts/audio_capture.py --debug             # Level-Logging
    python scripts/audio_capture.py --list-devices      # Devices anzeigen
    python scripts/audio_capture.py --device 15 --max-recordings 1
"""

import argparse
import json
import math
import os
import signal
import sys
import time
from collections import deque
from datetime import datetime
import wave

import numpy as np
import sounddevice as sd

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUTPUT_DIR = os.path.join(PROJECT_DIR, "audio", "inbox")

DEFAULTS = {
    "sample_rate": 16000,
    "channels": 1,
    "speech_threshold_db": -35.0,
    "silence_threshold_db": -45.0,
    "minimum_speech_ms": 400,
    "silence_timeout_ms": 700,
    "maximum_recording_ms": 30000,
    "pre_roll_ms": 400,
    "block_ms": 20,
    "output_dir": DEFAULT_OUTPUT_DIR,
    "device": None,
    "max_recordings": 0,
    "debug": False,
}

MIN_DB = -120.0


def db_from_amplitude(value: float, full_scale: float = 1.0) -> float:
    if value <= 0.0:
        return MIN_DB
    return 20.0 * math.log10(value / full_scale)


class LevelDetector:
    """Einfacher RMS/Peak/Level-Detektor.

    Austauschbar durch ein echtes VAD (Schnittstelle bleibt gleich:
    process(samples) -> dict mit rms_db/peak_db).
    """

    def process(self, samples: np.ndarray) -> dict:
        rms = float(np.sqrt(np.mean(np.square(samples))))
        peak = float(np.max(np.abs(samples)))
        return {
            "rms": rms,
            "peak": peak,
            "rms_db": db_from_amplitude(rms),
            "peak_db": db_from_amplitude(peak),
        }


class CaptureWorker:
    """State Machine: IDLE -> MONITORING -> SPEECH_DETECTED -> RECORDING
    -> FINALIZING -> SAVED -> MONITORING"""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.state = "IDLE"
        self.detector = LevelDetector()
        self._audio_ready = False
        self._stop_requested = False

        self._pre_roll = deque(maxlen=int(cfg["pre_roll_ms"] / 1000.0 * cfg["sample_rate"]))
        self._chunks = []
        self._speech_since = None
        self._silence_since = None
        self._rec_started_at = None
        self._final_pending = False
        self._recordings = 0
        self._last_debug_ts = 0.0
        self._last_level = None

    # --- Callback (Audio-Thread) ---
    def _callback(self, indata, frames, time_info, status):
        if status:
            print(f"[WARN] audio status: {status}", file=sys.stderr)
        samples = indata[:, 0]
        level = self.detector.process(samples)
        self._last_level = level
        now = time.time()

        if self.cfg["debug"] and now - self._last_debug_ts >= 0.2:
            self._last_debug_ts = now
            print(
                f"[MONITOR] RMS={level['rms_db']:.1f} dBFS "
                f"PEAK={level['peak_db']:.1f} dBFS "
                f"state={self.state}"
            )

        self._pre_roll.extend(samples)

        if self.state == "MONITORING":
            if level["rms_db"] > self.cfg["speech_threshold_db"]:
                if self._speech_since is None:
                    self._speech_since = now
                    if self.cfg["debug"]:
                        print("[VAD] SPEECH START (pending)")
                min_speech_s = self.cfg["minimum_speech_ms"] / 1000.0
                if now - self._speech_since >= min_speech_s:
                    self._start_recording(now)
            else:
                self._speech_since = None

        elif self.state == "RECORDING":
            self._chunks.append(samples.copy())
            if level["rms_db"] > self.cfg["speech_threshold_db"]:
                self._silence_since = None
            else:
                if self._silence_since is None:
                    self._silence_since = now
                silence_s = self.cfg["silence_timeout_ms"] / 1000.0
                duration_s = now - self._rec_started_at
                max_s = self.cfg["maximum_recording_ms"] / 1000.0
                if now - self._silence_since >= silence_s or duration_s >= max_s:
                    self.state = "FINALIZING"
                    self._final_pending = True
                    if self.cfg["debug"]:
                        reason = "silence" if now - self._silence_since >= silence_s else "max_duration"
                        print(f"[VAD] SPEECH END (reason={reason}, dur={duration_s:.2f}s)")

    # --- Recording-Logik ---
    def _start_recording(self, now):
        self.state = "RECORDING"
        self._rec_started_at = now
        self._silence_since = None
        self._chunks = [np.array(self._pre_roll, dtype=np.float32)]
        if self.cfg["debug"]:
            print("[REC] recording started (mit Pre-Roll)")

    def _save_recording(self) -> dict:
        if not self._chunks:
            return {}
        audio = np.concatenate(self._chunks)
        duration_ms = int(len(audio) / self.cfg["sample_rate"] * 1000.0)

        filename = self._next_filename()
        wav_path = os.path.join(self.cfg["output_dir"], filename)
        pcm = np.clip(audio * 32768.0, -32768.0, 32767.0).astype(np.int16)
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(self.cfg["channels"])
            wf.setsampwidth(2)
            wf.setframerate(self.cfg["sample_rate"])
            wf.writeframes(pcm.tobytes())

        level = self.detector.process(audio)
        meta = {
            "filename": filename,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "duration_ms": duration_ms,
            "sample_rate": self.cfg["sample_rate"],
            "channels": self.cfg["channels"],
            "sample_width": 16,
            "peak_db": round(level["peak_db"], 1),
            "rms_db": round(level["rms_db"], 1),
            "trigger": "level",
            "device": self.cfg["device_name"],
            "thresholds": {
                "speech_threshold_db": self.cfg["speech_threshold_db"],
                "silence_threshold_db": self.cfg["silence_threshold_db"],
                "silence_timeout_ms": self.cfg["silence_timeout_ms"],
                "minimum_speech_ms": self.cfg["minimum_speech_ms"],
                "maximum_recording_ms": self.cfg["maximum_recording_ms"],
                "pre_roll_ms": self.cfg["pre_roll_ms"],
            },
        }
        meta_path = wav_path.replace(".wav", ".json")
        with open(meta_path, "w", encoding="utf-8") as mf:
            json.dump(meta, mf, indent=2, ensure_ascii=False)

        quality = self._check_wav(wav_path)
        meta["quality"] = quality
        self._recordings += 1
        self._last_saved = meta
        print(f"[SAVE] {filename} dur={duration_ms}ms rms={level['rms_db']:.1f}dBFS {quality['status']}")
        return meta

    def _next_filename(self) -> str:
        n = self._recordings + 1
        return f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{n:03d}.wav"

    def _check_wav(self, path: str) -> dict:
        result = {
            "exists": os.path.exists(path),
            "size_bytes": os.path.getsize(path) if os.path.exists(path) else 0,
            "status": "FAIL",
        }
        if not result["exists"] or result["size_bytes"] <= 44:
            return result
        try:
            with wave.open(path, "rb") as wf:
                channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                nframes = wf.getnframes()
                raw = wf.readframes(nframes)
            pcm = np.frombuffer(raw, dtype=np.int16)
            pcm64 = pcm.astype(np.float64)
            rms_db = db_from_amplitude(float(np.sqrt(np.mean(np.square(pcm64)))), full_scale=32768.0)
            peak_db = db_from_amplitude(float(np.max(np.abs(pcm64))), full_scale=32768.0)
            result.update({
                "channels": channels,
                "sample_width": sampwidth * 8,
                "framerate": framerate,
                "frames": nframes,
                "duration_ms": int(nframes / framerate * 1000.0),
                "rms_db": round(rms_db, 1),
                "peak_db": round(peak_db, 1),
            })
            if channels != self.cfg["channels"] or sampwidth != 2 or framerate != self.cfg["sample_rate"]:
                result["status"] = "FAIL"
            elif nframes == 0:
                result["status"] = "EMPTY"
            elif rms_db < -50.0:
                result["status"] = "SILENT"
            else:
                result["status"] = "PASS"
        except Exception as exc:
            result["status"] = "FAIL"
            result["error"] = str(exc)
        return result

    # --- Lifecycle ---
    def run(self):
        cfg = self.cfg
        device_name = cfg["device"] if cfg["device"] is not None else "default"
        cfg["device_name"] = device_name
        print(f"=== GUIALITA Audio Capture (PHASE 1A) ===")
        print(f"Device: {device_name}  SR={cfg['sample_rate']}  CH={cfg['channels']}")
        print(f"Thresholds: speech={cfg['speech_threshold_db']}dB "
              f"silence={cfg['silence_threshold_db']}dB  "
              f"silence_timeout={cfg['silence_timeout_ms']}ms  "
              f"max_rec={cfg['maximum_recording_ms']}ms")
        print(f"Output: {cfg['output_dir']}")
        print("Status: MONITORING (sprich, um eine Aufnahme zu starten)")
        sys.stdout.flush()

        self.state = "MONITORING"
        try:
            with sd.InputStream(
                device=cfg["device"],
                samplerate=cfg["sample_rate"],
                channels=cfg["channels"],
                dtype="float32",
                blocksize=int(cfg["sample_rate"] * cfg["block_ms"] / 1000.0),
                callback=self._callback,
            ):
                while not self._stop_requested:
                    if self._final_pending:
                        self._final_pending = False
                        meta = self._save_recording()
                        self.state = "MONITORING"
                        if meta.get("quality", {}).get("status") == "SILENT":
                            print(f"[WARN] SILENT_FILE: {meta['filename']} -> failed/")
                            self._move_to_failed(meta["filename"])
                        if cfg["max_recordings"] and self._recordings >= cfg["max_recordings"]:
                            self._stop_requested = True
                            print(f"[OK] {self._recordings} Aufnahme(n), Limit erreicht.")
                    sd.sleep(20)
        except sd.PortAudioError as exc:
            print(f"[ERROR] Audio-Stream Fehler: {exc}", file=sys.stderr)
            self.state = "ERROR"
            return 1
        except KeyboardInterrupt:
            print("\n[STOP] Abbruch durch Benutzer.")
        finally:
            if self.state in ("RECORDING", "FINALIZING"):
                print("[DISCARD] laufende Aufnahme verworfen (kein sauberes Ende).")
        print(f"[STOP] Mikrofon geschlossen. Aufnahmen: {self._recordings}")
        return 0

    def _move_to_failed(self, filename: str):
        src = os.path.join(self.cfg["output_dir"], filename)
        failed_dir = os.path.join(os.path.dirname(self.cfg["output_dir"]), "failed")
        os.makedirs(failed_dir, exist_ok=True)
        dst = os.path.join(failed_dir, filename)
        os.replace(src, dst)
        json_src = src.replace(".wav", ".json")
        if os.path.exists(json_src):
            os.replace(json_src, json_src.replace(".wav", ".json").replace(self.cfg["output_dir"], failed_dir))


def list_devices():
    print("Verfügbare Audio-Geräte:")
    for idx, dev in enumerate(sd.query_devices()):
        in_ch = dev.get("max_input_channels", 0)
        mark = " <-- Default" if idx == sd.default.device[0] else ""
        print(f"  {idx}: {dev['name']} (in={in_ch}, sr={dev['default_samplerate']:.0f}){mark}")


def parse_args():
    parser = argparse.ArgumentParser(description="GUIALITA Audio Capture (PHASE 1A)")
    parser.add_argument("--device", type=int, default=DEFAULTS["device"],
                        help="Audio-Device-ID (Standard: System-Default)")
    parser.add_argument("--output", type=str, default=DEFAULTS["output_dir"],
                        help="Ausgabeverzeichnis für WAV-Dateien")
    parser.add_argument("--threshold", type=float, default=DEFAULTS["speech_threshold_db"],
                        help=f"Speech-Schwellwert in dBFS (Default: {DEFAULTS['speech_threshold_db']})")
    parser.add_argument("--silence-threshold", type=float, default=DEFAULTS["silence_threshold_db"],
                        help=f"Silence-Schwellwert in dBFS (Default: {DEFAULTS['silence_threshold_db']})")
    parser.add_argument("--silence", type=int, default=DEFAULTS["silence_timeout_ms"],
                        help=f"Silence-Timeout in ms (Default: {DEFAULTS['silence_timeout_ms']})")
    parser.add_argument("--max-duration", type=int, default=DEFAULTS["maximum_recording_ms"],
                        help=f"Maximale Aufnahmedauer in ms (Default: {DEFAULTS['maximum_recording_ms']})")
    parser.add_argument("--sample-rate", type=int, default=DEFAULTS["sample_rate"],
                        help=f"Sample Rate (Default: {DEFAULTS['sample_rate']})")
    parser.add_argument("--max-recordings", type=int, default=DEFAULTS["max_recordings"],
                        help="Nach N Aufnahmen beenden (0 = unbegrenzt)")
    parser.add_argument("--debug", action="store_true", default=DEFAULTS["debug"],
                        help="Level-Logging im Monitor-Modus")
    parser.add_argument("--list-devices", action="store_true", help="Geräte anzeigen und beenden")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.list_devices:
        list_devices()
        return 0
    cfg = dict(DEFAULTS)
    cfg.update({
        "device": args.device,
        "output_dir": args.output,
        "speech_threshold_db": args.threshold,
        "silence_threshold_db": args.silence_threshold,
        "silence_timeout_ms": args.silence,
        "maximum_recording_ms": args.max_duration,
        "sample_rate": args.sample_rate,
        "max_recordings": args.max_recordings,
        "debug": args.debug,
    })
    os.makedirs(cfg["output_dir"], exist_ok=True)
    worker = CaptureWorker(cfg)
    return worker.run()


if __name__ == "__main__":
    sys.exit(main())