#!/usr/bin/env python3
"""GUIALITA PHASE 1A — Automatisierte Capture-Tests (via virtuellem Mikrofon).

Nutzt das PulseAudio Null-Sink "guialita_vmic" und spielt espeak-Audio
ein, um Sprachszenarien zu simulieren.

Voraussetzung:
    pactl load-module module-null-sink sink_name=guialita_vmic ...
    ~/.asoundrc mit pcm.guialita_vmic (type pulse, device guialita_vmic.monitor)

Usage:
    /home/hz/.guialita-venv/bin/python tests/test_capture.py
"""

import os
import shutil
import subprocess
import sys
import time
import wave

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(PROJECT_DIR, "scripts", "audio_capture.py")
INBOX = os.path.join(PROJECT_DIR, "audio", "inbox")
VENV_PY = "/home/hz/.guialita-venv/bin/python"
DEVICE_ID = 15

RESULTS = []


def reset_inbox():
    for f in os.listdir(INBOX):
        os.remove(os.path.join(INBOX, f))


def wav_files():
    return sorted(f for f in os.listdir(INBOX) if f.endswith(".wav"))


def make_speech(out_path, text, speed=150):
    subprocess.run(
        ["espeak-ng", "-v", "de", "-s", str(speed), "-w", out_path, text],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def play(path):
    subprocess.run(["paplay", "--device=guialita_vmic", path], check=True)


def run_capture(args, duration_s, during=None):
    """Startet Capture, wartet, führt `during` aus, beendet Capture."""
    reset_inbox()
    proc = subprocess.Popen(
        [VENV_PY, "-u", SCRIPT, "--device", str(DEVICE_ID)] + args,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    time.sleep(2.5)
    if during:
        during()
    time.sleep(duration_s)
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    log = proc.stdout.read() if proc.stdout else ""
    return wav_files(), log


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")


def validate_wav(path):
    try:
        with wave.open(path, "rb") as wf:
            return {
                "channels": wf.getnchannels(),
                "sampwidth": wf.getsampwidth(),
                "framerate": wf.getframerate(),
                "frames": wf.getnframes(),
            }
    except Exception as exc:
        return {"error": str(exc)}


def test3_silence_no_wav():
    wavs, log = run_capture([], duration_s=10)
    check("TEST 3 Stille -> keine WAV", len(wavs) == 0, f"({len(wavs)} WAV)")


def test4_short_speech():
    make_speech("/tmp/opencode/t4.wav", "Hallo GUIALITA.", 160)
    wavs, log = run_capture(["--max-recordings", "1"], duration_s=5, during=lambda: play("/tmp/opencode/t4.wav"))
    ok = len(wavs) == 1
    check("TEST 4 kurze Sprache -> 1 WAV", ok, f"({len(wavs)} WAV)")
    if ok:
        v = validate_wav(os.path.join(INBOX, wavs[0]))
        check("  TEST 4 WAV-Format", v.get("channels") == 1 and v.get("sampwidth") == 2
              and v.get("framerate") == 16000 and v.get("frames", 0) > 0, str(v))


def test5_long_sentence():
    make_speech("/tmp/opencode/t5.wav", "Das ist ein Test für die automatische Audioaufnahme von GUIALITA.", 140)
    wavs, log = run_capture(["--max-recordings", "1"], duration_s=8, during=lambda: play("/tmp/opencode/t5.wav"))
    check("TEST 5 längerer Satz -> 1 WAV", len(wavs) == 1, f"({len(wavs)} WAV)")


def test6_pause_inside():
    make_speech("/tmp/opencode/t6a.wav", "Hallo GUIALITA.", 150)
    make_speech("/tmp/opencode/t6b.wav", "Das ist ein Test.", 150)
    def during():
        play("/tmp/opencode/t6a.wav")
        time.sleep(1.2)
        play("/tmp/opencode/t6b.wav")
    wavs, log = run_capture(["--max-recordings", "1"], duration_s=8, during=during)
    check("TEST 6 Pause im Satz -> 1 WAV", len(wavs) == 1, f"({len(wavs)} WAV)")


def test8_max_duration():
    make_speech("/tmp/opencode/t8.wav", "Dies ist eine sehr lange Audioaufnahme für den Test der maximalen Dauer.", 130)
    def during():
        play("/tmp/opencode/t8.wav")
        time.sleep(1.0)
        play("/tmp/opencode/t8.wav")
    wavs, log = run_capture(["--max-recordings", "1", "--max-duration", "2500"], duration_s=8, during=during)
    ok = len(wavs) == 1
    dur_ms = 0
    if ok:
        v = validate_wav(os.path.join(INBOX, wavs[0]))
        dur_ms = int(v.get("frames", 0) / v.get("framerate", 1) * 1000)
        ok = dur_ms <= 3500
    check("TEST 8 max-Dauer greift", ok, f"({len(wavs)} WAV, dur={dur_ms}ms <= 3500ms)")


def test10_multiple_recordings():
    make_speech("/tmp/opencode/t10.wav", "Aufnahme Nummer eins.", 150)
    def during():
        for _ in range(5):
            play("/tmp/opencode/t10.wav")
            time.sleep(1.5)
    wavs, log = run_capture(["--max-recordings", "5"], duration_s=14, during=during)
    names = set(wavs)
    check("TEST 10 fünf Aufnahmen", len(wavs) == 5, f"({len(wavs)} WAV, eindeutig={len(names) == 5})")


def main():
    reset_inbox()
    test3_silence_no_wav()
    test4_short_speech()
    test5_long_sentence()
    test6_pause_inside()
    test8_max_duration()
    test10_multiple_recordings()
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n=== PHASE 1A CAPTURE TESTS: {passed}/{len(RESULTS)} PASS ===")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())