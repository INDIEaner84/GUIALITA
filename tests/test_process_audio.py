#!/usr/bin/env python3
"""GUIALITA PHASE 1B — Testsuite (Testmatrix T1-T10).

Echte LFM2.5-Audio-Inferenz (kein Mock) für T1, T2, T4, T5, T7, T8, T10.
Unit-Tests für Dateinamen-Sicherheit (T9) und WAV-Validierung (T3, T6).

Usage:
    /home/hz/.guialita-venv/bin/python tests/test_process_audio.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import process_audio as pa

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix="guialita_1b_")

RESULTS = []


def note(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")


def make_speech(path, text, speed=150):
    subprocess.run(["espeak-ng", "-v", "de", "-s", str(speed), "-w", path, text],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def make_silent_wav(path, seconds=2.0):
    subprocess.run(["sox", "-b", "16", "-n", "-r", "16000", "-c", "1", path,
                    "synth", str(seconds), "sine", "0"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def make_tone_wav(path, seconds=0.2):
    subprocess.run(["sox", "-b", "16", "-n", "-r", "16000", "-c", "1", path,
                    "synth", str(seconds), "sine", "440"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def cfg_for(out_dir, **overrides):
    cfg = {
        "model": pa.DEFAULT_MODEL, "mmproj": pa.DEFAULT_MMPROJ,
        "vocoder": pa.DEFAULT_VOCODER, "tokenizer": pa.DEFAULT_TOKENIZER,
        "runner": pa.DEFAULT_RUNNER, "output_dir": out_dir,
        "keep_original": False, "no_rename": False,
        "threads": 12, "timeout_s": 900, "debug": False,
    }
    cfg.update(overrides)
    return cfg


def run_real(wav, out_dir, **overrides):
    cfg = cfg_for(out_dir, **overrides)
    return pa.process_wav(wav, cfg)


class TestFilenameSafety(unittest.TestCase):
    def test_sanitize_dangerous(self):
        bad = 'Hallo/\\:*?"<>| GUIALITA .. test $ ; ` ! & ( )'
        slug = pa.sanitize_filename(bad)
        self.assertNotIn("/", slug)
        self.assertNotIn("\\", slug)
        self.assertNotIn("..", slug)
        self.assertNotIn("$", slug)
        self.assertNotIn(";", slug)
        self.assertTrue(slug.isascii() and "_" not in slug and " " not in slug)

    def test_sanitize_length(self):
        slug = pa.sanitize_filename("x" * 300)
        self.assertLessEqual(len(slug), pa.MAX_SLUG_LEN)

    def test_sanitize_empty(self):
        self.assertEqual(pa.sanitize_filename(""), "")

    def test_build_final_no_collision(self):
        used = {"20260818_100000__test.wav"}
        name = pa.build_final_name("Test", "whatever.wav", used)
        self.assertNotIn(name, used)
        self.assertTrue(name.endswith(".wav"))
        self.assertNotIn("/", name)

    def test_build_final_empty_transcript(self):
        name = pa.build_final_name("", "x.wav", set())
        self.assertTrue(name.endswith("__transcript.wav"))


def test_t1_valid_speech():
    wav = os.path.join(TMP, "t1.wav")
    make_speech(wav, "Hallo GUIALITA.")
    out = os.path.join(TMP, "out1")
    os.makedirs(out)
    r = run_real(wav, out)
    ok = r["status"] == "SUCCESS" and r.get("transcript")
    note("T1 gültige Sprach-WAV -> echter Transcript", ok,
         f"transcript={r.get('transcript')!r} status={r['status']}")
    note("T1 finale Datei erzeugt", bool(r.get("final_filename")), r.get("final_filename", ""))
    return r


def test_t2_second_wav():
    wav = os.path.join(TMP, "t2.wav")
    make_speech(wav, "Das ist ein anderer Test.")
    out = os.path.join(TMP, "out2")
    os.makedirs(out)
    r = run_real(wav, out)
    note("T2 zweite WAV -> Transcript", r["status"] == "SUCCESS" and bool(r.get("transcript")),
         f"transcript={r.get('transcript')!r}")


def test_t3_silent():
    wav = os.path.join(TMP, "t3_silent.wav")
    make_silent_wav(wav)
    out = os.path.join(TMP, "out3")
    os.makedirs(out)
    r = run_real(wav, out)
    ok = r["status"] == "SILENT" and not r.get("transcript")
    note("T3 Stille -> kein falscher Transcript", ok,
         f"status={r['status']} transcript={r.get('transcript')!r}")
    note("T3 Original bleibt", os.path.exists(wav), "")


def test_t4_very_short():
    wav = os.path.join(TMP, "t4_short.wav")
    make_tone_wav(wav, 0.2)
    out = os.path.join(TMP, "out4")
    os.makedirs(out)
    r = run_real(wav, out)
    ok = r["status"] in ("SUCCESS", "NO_TRANSCRIPTION", "SILENT")
    note("T4 sehr kurze WAV -> kontrolliertes Ergebnis", ok,
         f"status={r['status']} transcript={r.get('transcript')!r}")


def test_t5_longer():
    wav = os.path.join(TMP, "t5.wav")
    make_speech(wav, "Dies ist ein längerer Satz für den LFM Audio Test.", 140)
    out = os.path.join(TMP, "out5")
    os.makedirs(out)
    r = run_real(wav, out)
    note("T5 längere WAV -> Erfolg", r["status"] == "SUCCESS" and bool(r.get("transcript")),
         f"status={r['status']} transcript={r.get('transcript')!r}")


def test_t6_invalid_wav():
    wav = os.path.join(TMP, "t6_invalid.wav")
    with open(wav, "w") as f:
        f.write("das ist kein wav")
    out = os.path.join(TMP, "out6")
    os.makedirs(out)
    r = run_real(wav, out)
    note("T6 ungültige WAV -> Validierungsfehler", r["status"] == "FAILED" and bool(r.get("error")),
         f"status={r['status']} error={r.get('error')}")
    note("T6 Original bleibt", os.path.exists(wav), "")


def test_t7_missing_model():
    wav = os.path.join(TMP, "t7.wav")
    make_speech(wav, "Hallo GUIALITA.")
    out = os.path.join(TMP, "out7")
    os.makedirs(out)
    r = run_real(wav, out, model="/nonexistent/model.gguf")
    ok = r["status"] == "MODEL_ERROR" and "fehlt" in (r.get("error") or "")
    note("T7 fehlendes Modell -> kontrollierter Modellfehler", ok,
         f"status={r['status']} error={r.get('error')}")
    note("T7 Original bleibt", os.path.exists(wav), "")


def test_t8_multiple_ids():
    out = os.path.join(TMP, "out8")
    os.makedirs(out)
    ids = []
    for i in range(3):
        wav = os.path.join(TMP, f"t8_{i}.wav")
        make_speech(wav, f"Aufnahme Nummer {i}.")
        r = run_real(wav, out)
        ids.append(r.get("audio_id"))
    ok = all(ids) and len(set(ids)) == 3
    note("T8 mehrere WAVs -> eindeutige AUDIO-IDs", ok, str(ids))


def test_t10_duplicate():
    out = os.path.join(TMP, "out10")
    os.makedirs(out)
    wav = os.path.join(TMP, "t10_src.wav")
    make_speech(wav, "Duplikat Test.")
    wav2 = os.path.join(TMP, "t10_src2.wav")
    shutil.copy2(wav, wav2)
    r1 = run_real(wav, out)
    r2 = run_real(wav2, out)
    names = sorted(f for f in os.listdir(out) if f.endswith(".wav"))
    ok = r1.get("final_filename") and r2.get("final_filename") and r1["final_filename"] != r2["final_filename"]
    note("T10 Duplikat -> keine Kollision, kein Überschreiben", ok,
         f"n={len(names)} dateien={names}")


def main():
    test_t1_valid_speech()
    test_t2_second_wav()
    test_t3_silent()
    test_t4_very_short()
    test_t5_longer()
    test_t6_invalid_wav()
    test_t7_missing_model()
    test_t8_multiple_ids()
    test_t10_duplicate()
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFilenameSafety)
    tr = unittest.TextTestRunner(verbosity=1)
    tr.run(suite)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n=== PHASE 1B TESTS: {passed}/{len(RESULTS)} PASS ===")
    shutil.rmtree(TMP, ignore_errors=True)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())