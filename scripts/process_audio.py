#!/usr/bin/env python3
"""GUIALITA PHASE 1B — WAV -> LFM2.5-Audio -> Transcript -> Safe Renaming.

Pipeline:
    existing WAV (audio/inbox/)
        -> Validierung
        -> LFM2.5-Audio-1.5B (llama-liquid-audio-cli, ASR)
        -> echter Transcript
        -> AUDIO-ID + Metadaten
        -> sicheres Dateinamen-Design
        -> atomisches Rename/Move nach audio/processed/

Runtime: Liquid AI LFM2.5-Audio Runner (llama-liquid-audio-cli, CPU).
Modell:  models/lfm-audio-1.5b/LFM2.5-Audio-1.5B-Q4_0.gguf + mmproj + vocoder + tokenizer.
Runner:  runtime/liquid-audio/llama-liquid-audio-cli (offizieller Runner, PR #18641).

Usage:
    python scripts/process_audio.py audio/inbox/audio_....wav
    python scripts/process_audio.py <wav> --debug
    python scripts/process_audio.py <wav> --keep-original
    python scripts/process_audio.py <wav> --output audio/processed
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
import wave
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_DIR = os.path.join(PROJECT_DIR, "audio")
INBOX = os.path.join(AUDIO_DIR, "inbox")
PROCESSED = os.path.join(AUDIO_DIR, "processed")
FAILED = os.path.join(AUDIO_DIR, "failed")
COUNTER_FILE = os.path.join(AUDIO_DIR, ".audio_id_counter")

MODEL_DIR = os.path.join(PROJECT_DIR, "models", "lfm-audio-1.5b")
DEFAULT_MODEL = os.path.join(MODEL_DIR, "LFM2.5-Audio-1.5B-Q4_0.gguf")
DEFAULT_MMPROJ = os.path.join(MODEL_DIR, "mmproj-LFM2.5-Audio-1.5B-Q4_0.gguf")
DEFAULT_VOCODER = os.path.join(MODEL_DIR, "vocoder-LFM2.5-Audio-1.5B-Q4_0.gguf")
DEFAULT_TOKENIZER = os.path.join(MODEL_DIR, "tokenizer-LFM2.5-Audio-1.5B-Q4_0.gguf")
DEFAULT_RUNNER = os.path.join(PROJECT_DIR, "runtime", "liquid-audio", "llama-liquid-audio-cli")
ASR_SYSTEM_PROMPT = "Perform ASR."
MAX_SLUG_LEN = 60
SILENT_RMS_DB = -50.0

# Verarbeitungs-Zustände (Abschnitt 20 der Spec)
STATES = ["DISCOVERED", "VALIDATED", "LOADING_MODEL", "INFERENCE",
          "RESULT_RECEIVED", "METADATA_CREATED", "RENAMING", "COMPLETED", "FAILED"]


def db_from_amplitude(value: float, full_scale: float = 32768.0) -> float:
    if value <= 0.0:
        return -120.0
    return 20.0 * math.log10(value / full_scale)


def validate_wav(path: str) -> dict:
    """Prüft WAV: Existenz, Header, PCM, Dauer, Pegel."""
    result = {"path": path, "exists": os.path.exists(path),
              "size_bytes": os.path.getsize(path) if os.path.exists(path) else 0,
              "status": "FAIL"}
    if not result["exists"]:
        result["error"] = "missing"
        return result
    if result["size_bytes"] <= 44:
        result["error"] = "too_small"
        return result
    try:
        with wave.open(path, "rb") as wf:
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            raw = wf.readframes(nframes)
    except Exception as exc:
        result["error"] = f"corrupt: {exc}"
        return result
    if sampwidth != 2:
        result["error"] = f"unsupported sample width {sampwidth * 8} bit (nur 16-bit)"
        return result
    duration_ms = int(nframes / framerate * 1000.0) if framerate else 0
    pcm = None
    if len(raw) > 0:
        import numpy as np
        pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
    rms_db = db_from_amplitude(float(math.sqrt(float(np.mean(np.square(pcm))))) if pcm is not None else 0.0)
    peak_db = db_from_amplitude(float(np.max(np.abs(pcm))) if pcm is not None and len(pcm) else 0.0)
    result.update({
        "channels": channels, "sample_width": sampwidth * 8, "framerate": framerate,
        "frames": nframes, "duration_ms": duration_ms,
        "rms_db": round(rms_db, 1), "peak_db": round(peak_db, 1),
    })
    if channels != 1:
        result["error"] = f"unsupported channels {channels} (nur mono)"
    elif duration_ms <= 0:
        result["error"] = "empty_duration"
    elif rms_db < SILENT_RMS_DB:
        result["status"] = "SILENT"
    else:
        result["status"] = "VALID"
    return result


def next_audio_id() -> str:
    """Kollisionssichere AUDIO-ID via Zählerdatei."""
    counter = 0
    if os.path.exists(COUNTER_FILE):
        try:
            counter = int(open(COUNTER_FILE).read().strip())
        except Exception:
            counter = 0
    counter += 1
    with open(COUNTER_FILE, "w") as f:
        f.write(str(counter))
    return f"AUDIO-{counter:06d}"


def sanitize_filename(transcript: str) -> str:
    """Transkript -> sichere Dateinamen-Slug (keine Metazeichen, Pfad-Traversal ausgeschlossen)."""
    if not transcript:
        return ""
    s = transcript.lower()
    s = re.sub(r"[^a-z0-9\u00e4\u00f6\u00fc\u00df]+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    s = s.strip("-")
    if len(s) > MAX_SLUG_LEN:
        s = s[:MAX_SLUG_LEN].rstrip("-")
    return s


def build_final_name(transcript: str, wav_path: str, used_names: set) -> str:
    """Finaler Dateiname: YYYYMMDD_HHMMSS__<slug>.wav (kollisionssicher)."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = sanitize_filename(transcript)
    if not slug:
        slug = "transcript"
    base = f"{ts}__{slug}"
    name = f"{base}.wav"
    n = 2
    while name in used_names:
        name = f"{base}-{n}.wav"
        n += 1
    return name


def run_lfm_asr(wav_path: str, cfg: dict) -> dict:
    """Führt LFM2.5-Audio-ASR aus (llama-liquid-audio-cli als Subprozess)."""
    runner = cfg["runner"]
    if not os.path.exists(runner):
        return {"status": "MODEL_ERROR", "error": f"runner fehlt: {runner}"}
    for label, key in (("modell", "model"), ("mmproj", "mmproj"),
                       ("vocoder", "vocoder"), ("tokenizer", "tokenizer")):
        if not os.path.exists(cfg[key]):
            return {"status": "MODEL_ERROR", "error": f"{label} fehlt: {cfg[key]}"}
    runner_dir = os.path.dirname(runner)
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = runner_dir + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    cmd = [
        runner,
        "-m", cfg["model"],
        "-mm", cfg["mmproj"],
        "-mv", cfg["vocoder"],
        "--tts-speaker-file", cfg["tokenizer"],
        "-sys", ASR_SYSTEM_PROMPT,
        "--audio", wav_path,
        "-t", str(cfg["threads"]),
    ]
    if cfg["debug"]:
        print("[RUN]", " ".join(cmd))
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env, timeout=cfg["timeout_s"])
    total_ms = int((time.time() - t0) * 1000)
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")

    transcript = ""
    marker = "=== GENERATED TEXT ==="
    if marker in out:
        tail = out.split(marker, 1)[1]
        lines = [l.strip() for l in tail.splitlines() if l.strip()]
        if lines:
            transcript = lines[0]
    if not transcript and proc.returncode != 0:
        return {"status": "INFERENCE_ERROR", "error": f"cli rc={proc.returncode}",
                "returncode": proc.returncode, "total_ms": total_ms,
                "log_tail": "\n".join(out.splitlines()[-8:])}

    metrics = {"total_ms": total_ms}
    for pat, key in ((r"load time\s*=\s*([\d.]+) ms", "model_load_ms"),
                     (r"audio slice encoded in ([\d.]+) ms", "encode_ms"),
                     (r"audio decoded \(batch [\d/]+\) in ([\d.]+) ms", "decode_ms")):
        m = re.search(pat, out)
        if m:
            metrics[key] = int(float(m.group(1)))
    if cfg["debug"]:
        print(f"[LFM] rc={proc.returncode} total={total_ms}ms transcript={transcript!r}")
    return {"status": "SUCCESS" if transcript else "NO_TRANSCRIPTION",
            "transcript": transcript, "metrics": metrics, "returncode": proc.returncode}


def process_wav(path: str, cfg: dict) -> dict:
    """Komplette Phase-1B-Pipeline für eine WAV. Original bleibt bei Fehler unverändert."""
    result = {
        "state": "DISCOVERED", "audio_id": None, "source_file": path,
        "final_filename": None, "transcript": None, "status": "FAILED",
        "error": None,
    }

    # DISCOVERED -> VALIDATED
    v = validate_wav(path)
    result["wav_validation"] = v
    if v["status"] == "SILENT":
        result["status"] = "SILENT"
        result["error"] = "silent wav (kein Sprachsignal)"
        result["state"] = "FAILED"
        return result
    if v["status"] != "VALID":
        result["error"] = v.get("error", "invalid wav")
        result["state"] = "FAILED"
        return result
    result["state"] = "VALIDATED"

    # VALIDATED -> LOADING_MODEL / INFERENCE
    result["state"] = "LOADING_MODEL"
    r = run_lfm_asr(path, cfg)
    result["inference"] = r
    result["state"] = "INFERENCE"

    transcript = r.get("transcript", "")
    if r["status"] != "SUCCESS":
        result["status"] = r["status"]
        result["error"] = r.get("error")
        result["state"] = "FAILED"
        return result
    result["state"] = "RESULT_RECEIVED"
    result["transcript"] = transcript

    # RESULT_RECEIVED -> METADATA_CREATED
    audio_id = next_audio_id()
    result["audio_id"] = audio_id
    result["timestamp"] = datetime.now().isoformat(timespec="seconds")
    meta = {
        "audio_id": audio_id,
        "source_filename": os.path.basename(path),
        "final_filename": None,
        "transcript": transcript,
        "model": "LFM2.5-Audio-1.5B",
        "model_file": os.path.basename(cfg["model"]),
        "runtime": "llama-liquid-audio-cli (LiquidAI, CPU)",
        "duration_ms": v["duration_ms"],
        "sample_rate": v["framerate"],
        "channels": v["channels"],
        "sample_width": v["sample_width"],
        "timestamp": result["timestamp"],
        "status": "SUCCESS",
        "confidence": None,
        "model_load_ms": r["metrics"].get("model_load_ms"),
        "inference_ms": r["metrics"].get("decode_ms"),
        "encode_ms": r["metrics"].get("encode_ms"),
        "total_processing_ms": r["metrics"].get("total_ms"),
    }
    result["meta"] = meta
    result["state"] = "METADATA_CREATED"

    # METADATA_CREATED -> RENAMING (nur nach erfolgreicher Analyse; Original bleibt bei Fehler)
    if not cfg["no_rename"]:
        used = {f for f in os.listdir(cfg["output_dir"]) if f.endswith(".wav")}
        final_name = build_final_name(transcript, path, used)
        meta["final_filename"] = final_name
        src = os.path.abspath(path)
        dst = os.path.abspath(os.path.join(cfg["output_dir"], final_name))
        try:
            if cfg["keep_original"]:
                import shutil
                shutil.copy2(src, dst)
            else:
                os.replace(src, dst)
            result["final_filename"] = final_name
            result["state"] = "RENAMING"
        except Exception as exc:
            result["status"] = "FAILED"
            result["error"] = f"rename fehlgeschlagen (Original bleibt): {exc}"
            result["state"] = "FAILED"
            return result

    # RENAMING -> COMPLETED
    meta_path = os.path.join(cfg["output_dir"], meta["audio_id"] + ".json")
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        result["metadata_path"] = meta_path
    except Exception as exc:
        result["status"] = "FAILED"
        result["error"] = f"metadaten fehlgeschlagen: {exc}"
        result["state"] = "FAILED"
        return result
    result["status"] = "SUCCESS"
    result["state"] = "COMPLETED"
    return result


def main():
    parser = argparse.ArgumentParser(description="GUIALITA Phase 1B: WAV -> LFM2.5-Audio -> Transcript")
    parser.add_argument("wav", nargs="?", help="WAV-Datei (Standard: letzte/erste Datei in audio/inbox/)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--mmproj", default=DEFAULT_MMPROJ)
    parser.add_argument("--vocoder", default=DEFAULT_VOCODER)
    parser.add_argument("--tokenizer", default=DEFAULT_TOKENIZER)
    parser.add_argument("--runner", default=DEFAULT_RUNNER)
    parser.add_argument("--output", default=PROCESSED, help="Zielverzeichnis (processed)")
    parser.add_argument("--keep-original", action="store_true", help="Original in inbox behalten (Kopie statt Move)")
    parser.add_argument("--no-rename", action="store_true", help="Analyse ohne Umbenennen/Move (nur Transkript + Bericht)")
    parser.add_argument("--threads", type=int, default=12)
    parser.add_argument("--timeout-s", type=int, default=900)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    cfg = {
        "model": args.model, "mmproj": args.mmproj, "vocoder": args.vocoder,
        "tokenizer": args.tokenizer, "runner": args.runner, "output_dir": args.output,
        "keep_original": args.keep_original, "no_rename": args.no_rename,
        "threads": args.threads, "timeout_s": args.timeout_s, "debug": args.debug,
    }

    if not args.wav:
        wavs = sorted(f for f in os.listdir(INBOX) if f.endswith(".wav"))
        if not wavs:
            print("Keine WAV in audio/inbox/ gefunden. Datei angeben: process_audio.py <wav>")
            return 1
        args.wav = os.path.join(INBOX, wavs[0])
    if not os.path.isabs(args.wav):
        args.wav = os.path.join(PROJECT_DIR, args.wav)

    t0 = time.time()
    r = process_wav(args.wav, cfg)
    elapsed = time.time() - t0

    print(f"== GUIALITA Phase 1B: {os.path.basename(args.wav)} ==")
    print(f"State:    {r['state']}")
    print(f"Status:   {r['status']}")
    if r.get("audio_id"):
        print(f"AUDIO-ID: {r['audio_id']}")
    if r.get("transcript"):
        print(f"Transkript: {r['transcript']}")
    if r.get("final_filename"):
        print(f"Final:    {r['final_filename']}")
    if r.get("error"):
        print(f"Fehler:   {r['error']}")
    if r.get("inference") and r["inference"].get("metrics"):
        m = r["inference"]["metrics"]
        print(f"Latenz:   total={m.get('total_ms')}ms "
              f"load={m.get('model_load_ms')}ms encode={m.get('encode_ms')}ms decode={m.get('decode_ms')}ms")
    print(f"Gesamt:   {elapsed:.2f}s")
    return 0 if r["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())