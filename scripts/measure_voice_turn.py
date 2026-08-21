#!/usr/bin/env python3
"""GUIALITA — Latenzmessung eines vollständigen Sprach-Turns.

Zweck
-----
Schließt das offene Gate aus Voice Forensics V1. Dort wurden ~48 s pro
Sprach-Turn gemessen — allerdings VOR dem CUDA-VMM-Repair. Dieses Skript
misst dieselbe Kette erneut und stuft jede Stufe einzeln ein:

    WAV  →  STT (whisper.cpp)
         →  CHAT (Memory-Retrieval + Kontext + LLM + Persistenz + Indexierung)
         →  TTS (LFM2.5-Audio)

Es wird NICHTS optimiert und NICHTS an der Pipeline geändert — nur gemessen.

Ehrlichkeitsregeln
------------------
- Eine Stufe, die nicht ausgeführt werden kann, ist NOT_EXECUTED — nicht PASS.
- Eine Stufe, die fehlschlägt, ist FAIL — inklusive Fehlermeldung.
- Es werden keine Zahlen geschätzt, interpoliert oder aus Doku übernommen.

Nutzung
-------
    # Mikrofonaufnahme (Standard): 3 Turns, erster = kalt
    python3 scripts/measure_voice_turn.py --record

    # Vorhandene WAV-Datei wiederholt durchmessen (reproduzierbar)
    python3 scripts/measure_voice_turn.py --wav audio/processed/beispiel.wav

    # Ohne STT: nur LLM + TTS messen
    python3 scripts/measure_voice_turn.py --text "Wie heisst mein Projekt?"

    # Ohne die produktive Datenbank zu berühren
    python3 scripts/measure_voice_turn.py --wav … --isolated

Ergebnis
--------
Tabelle auf stdout + maschinenlesbarer Report unter
`docs/measurements/voice-turn-<zeitstempel>.yaml`.
"""

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import wave
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)


def _reexec_in_venv():
    """Startet dieses Skript im konfigurierten Venv neu, falls nötig.

    Auf der Referenzmaschine liegt sounddevice in /home/hz/.guialita-venv,
    nicht im System-Python. Wer `python3 scripts/…` aufruft, scheiterte bisher
    an ModuleNotFoundError. GUIALITA_VENV (aus .env) wird jetzt beachtet.
    """
    if os.environ.get("GUIALITA_NO_REEXEC"):
        return
    venv = os.environ.get("GUIALITA_VENV")
    if not venv:
        env_file = os.path.join(BASE_DIR, ".env")
        if os.path.isfile(env_file):
            with open(env_file, encoding="utf-8") as fh:
                for line in fh:
                    if line.strip().startswith("GUIALITA_VENV="):
                        venv = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
    if not venv:
        return
    venv = os.path.expanduser(venv)
    candidate = os.path.join(venv, "bin", "python")
    if not os.path.isfile(candidate):
        return
    # Vergleich über sys.prefix, nicht über den Interpreterpfad: das
    # Venv-Python ist meist ein Symlink auf denselben Interpreter, hat aber
    # andere site-packages.
    if os.path.realpath(sys.prefix) == os.path.realpath(venv):
        return
    env = dict(os.environ, GUIALITA_NO_REEXEC="1")
    print(f"  Wechsle in die konfigurierte Umgebung: {candidate}", flush=True)
    os.execve(candidate, [candidate, os.path.abspath(__file__)] + sys.argv[1:], env)


_reexec_in_venv()


NOT_EXECUTED = "NOT_EXECUTED"
PASS = "PASS"
FAIL = "FAIL"

STAGES = ("stt", "chat", "tts")


def skip_remaining(turn, reason):
    """Markiert noch nicht gelaufene Stufen als NOT_EXECUTED — nie als PASS."""
    for name in STAGES:
        turn["stages"].setdefault(name, {"name": name, "status": NOT_EXECUTED,
                                         "reason": reason})
    turn["total_complete"] = False
    turn["status"] = FAIL
    return turn


# ----------------------------------------------------------------------
# Hilfsmittel
# ----------------------------------------------------------------------

def ms(t0: float, t1: float) -> float:
    return round((t1 - t0) * 1000.0, 1)


class GpuSampler:
    """Tastet GPU-Auslastung und VRAM per nvidia-smi ab (falls vorhanden)."""

    def __init__(self, interval: float = 0.5):
        self.interval = interval
        self.samples = []
        self._stop = threading.Event()
        self._thread = None
        self.available = self._probe()

    @staticmethod
    def _probe() -> bool:
        try:
            subprocess.run(["nvidia-smi", "-L"], capture_output=True, timeout=5, check=True)
            return True
        except Exception:
            return False

    def _loop(self):
        while not self._stop.is_set():
            try:
                out = subprocess.run(
                    ["nvidia-smi",
                     "--query-gpu=utilization.gpu,memory.used",
                     "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=5,
                )
                util, mem = out.stdout.strip().split("\n")[0].split(",")
                self.samples.append((int(util.strip()), int(mem.strip())))
            except Exception:
                pass
            self._stop.wait(self.interval)

    def start(self):
        if not self.available:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> dict:
        if not self.available:
            return {"status": NOT_EXECUTED, "reason": "nvidia-smi nicht verfügbar"}
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        if not self.samples:
            return {"status": NOT_EXECUTED, "reason": "keine Messpunkte"}
        utils = [s[0] for s in self.samples]
        mems = [s[1] for s in self.samples]
        return {
            "status": PASS,
            "samples": len(self.samples),
            "util_percent_peak": max(utils),
            "util_percent_avg": round(statistics.mean(utils), 1),
            "vram_mib_peak": max(mems),
            "vram_mib_min": min(mems),
        }


def wav_info(path: str) -> dict:
    try:
        with wave.open(path, "rb") as w:
            frames = w.getnframes()
            rate = w.getframerate()
            return {
                "path": path,
                "duration_s": round(frames / float(rate), 2) if rate else None,
                "sample_rate": rate,
                "channels": w.getnchannels(),
                "bytes": os.path.getsize(path),
            }
    except Exception as e:
        return {"path": path, "error": str(e)}


def record_wav(seconds: float, sample_rate: int = 16000) -> str:
    """Nimmt vom Standardmikrofon auf. Bewusst simpel: feste Dauer, keine VAD.

    Die VAD-Logik hat ihre eigene Messung; hier soll nur ein sauberes
    Eingangssignal für die Kette entstehen.
    """
    import numpy as np
    import sounddevice as sd

    print(f"  Aufnahme läuft ({seconds:.0f} s) — jetzt sprechen …", flush=True)
    audio = sd.rec(int(seconds * sample_rate), samplerate=sample_rate,
                   channels=1, dtype="int16")
    sd.wait()
    fd, path = tempfile.mkstemp(suffix=".wav", prefix="guialita_measure_")
    os.close(fd)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(audio.tobytes())
    peak = float(np.max(np.abs(audio))) / 32768.0 if audio.size else 0.0
    print(f"  Aufnahme fertig (Peak {peak:.3f})")
    return path


# ----------------------------------------------------------------------
# Messung eines Turns
# ----------------------------------------------------------------------

def measure_turn(components, wav_path, text, session_id, voice, turn_index):
    """Misst einen Turn. Liefert ein Dict mit Zeiten und Status pro Stufe."""
    manager, chat_service, tts = components
    turn = {
        "turn": turn_index,
        "kind": "cold" if turn_index == 1 else "warm",
        "stages": {},
    }

    # ---------- STT ----------
    transcript = text
    if wav_path:
        stage = {"name": "stt", "runtime": "whisper.cpp"}
        try:
            with open(wav_path, "rb") as f:
                wav_bytes = f.read()
            t0 = time.perf_counter()
            result = manager.transcribe(wav_bytes)
            stage["ms"] = ms(t0, time.perf_counter())
            transcript = (result.get("transcript") or "").strip()
            stage["transcript"] = transcript
            stage["status"] = PASS if transcript else FAIL
            if not transcript:
                stage["error"] = "leeres Transkript"
        except Exception as e:
            stage["status"] = FAIL
            stage["error"] = f"{type(e).__name__}: {e}"
        turn["stages"]["stt"] = stage
        if stage.get("status") != PASS:
            return skip_remaining(turn, "vorherige Stufe (STT) fehlgeschlagen")
    else:
        turn["stages"]["stt"] = {"name": "stt", "status": NOT_EXECUTED,
                                 "reason": "--text angegeben, STT übersprungen"}

    # ---------- CHAT (Retrieval + Kontext + LLM + Persistenz + Index) ----------
    stage = {"name": "chat"}
    response = None
    try:
        t0 = time.perf_counter()
        result = chat_service.chat(transcript, session_id=session_id)
        stage["ms"] = ms(t0, time.perf_counter())
        response = result["response"]
        llm_ms = float(result.get("latency_ms") or 0.0)
        stage["llm_ms"] = round(llm_ms, 1)
        # Alles im Chat, was nicht reine LLM-Inferenz ist:
        # Memory-Retrieval, Kontextbau, SQLite-Persistenz, Indexierung, Graph.
        stage["memory_overhead_ms"] = round(stage["ms"] - llm_ms, 1)
        stage["model"] = result.get("model")
        stage["runtime"] = result.get("runtime")
        stage["history_used"] = result.get("history_used")
        stage["session_id"] = result.get("session_id")
        stage["response_chars"] = len(response or "")
        stage["status"] = PASS
        session_id = result.get("session_id") or session_id
    except Exception as e:
        stage["status"] = FAIL
        stage["error"] = f"{type(e).__name__}: {e}"
    turn["stages"]["chat"] = stage
    if stage.get("status") != PASS:
        return skip_remaining(turn, "vorherige Stufe (CHAT) fehlgeschlagen")

    # ---------- TTS ----------
    stage = {"name": "tts", "runtime": "llama-liquid-audio-cli", "voice": voice}
    if tts is None or not tts.is_available():
        stage["status"] = NOT_EXECUTED
        stage["reason"] = "TTS-Runtime oder Modell nicht verfügbar"
    else:
        try:
            t0 = time.perf_counter()
            tts_result = tts.synthesize(response, voice)
            stage["ms"] = ms(t0, time.perf_counter())
            stage["wav_bytes"] = len(tts_result.get("wav_bytes") or b"")
            stage["status"] = PASS
        except Exception as e:
            stage["status"] = FAIL
            stage["error"] = f"{type(e).__name__}: {e}"
    turn["stages"]["tts"] = stage

    measured = [s.get("ms", 0.0) for s in turn["stages"].values() if s.get("status") == PASS]
    turn["total_ms"] = round(sum(measured), 1)
    turn["total_complete"] = all(
        turn["stages"][k].get("status") == PASS for k in ("chat", "tts")
    ) and turn["stages"]["stt"].get("status") in (PASS, NOT_EXECUTED)
    turn["session_id"] = session_id
    turn["status"] = PASS
    return turn


# ----------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------

def print_report(report):
    def fmt(v):
        return f"{v/1000:6.2f} s" if isinstance(v, (int, float)) else f"{'—':>8}"

    print()
    print("=" * 74)
    print("  GUIALITA — Sprach-Turn Latenzmessung")
    print("=" * 74)
    print(f"  Zeitpunkt : {report['timestamp']}")
    print(f"  Quelle    : {report['input']['mode']}")
    print(f"  Turns     : {len(report['turns'])}")
    print()

    header = f"  {'Turn':<6}{'Art':<7}{'STT':>10}{'LLM':>10}{'Memory':>10}{'TTS':>10}{'GESAMT':>11}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for t in report["turns"]:
        s = t["stages"]
        stt = s.get("stt", {}).get("ms")
        llm = s.get("chat", {}).get("llm_ms")
        mem = s.get("chat", {}).get("memory_overhead_ms")
        tts = s.get("tts", {}).get("ms")
        print(f"  {t['turn']:<6}{t['kind']:<7}{fmt(stt):>10}{fmt(llm):>10}"
              f"{fmt(mem):>10}{fmt(tts):>10}{fmt(t.get('total_ms')):>11}")

    print()
    for key, label in (("stt", "STT   "), ("chat", "CHAT  "), ("tts", "TTS   ")):
        st = {t["stages"].get(key, {}).get("status") for t in report["turns"]}
        note = ""
        for t in report["turns"]:
            s = t["stages"].get(key, {})
            if s.get("status") in (FAIL, NOT_EXECUTED):
                note = "  ← " + (s.get("error") or s.get("reason") or "")
                break
        print(f"  {label} {'/'.join(sorted(x for x in st if x))}{note}")

    w = report["summary"].get("warm")
    if w:
        print()
        print(f"  Warm-Turn (Median über {w['turns']} Turns): {w['total_ms']/1000:.2f} s")
        if w.get("dominant_stage"):
            print(f"  Größter Posten: {w['dominant_stage'].upper()} "
                  f"({w['dominant_share_percent']} % der Zeit)")
    else:
        print("\n  Kein Warm-Median: zu wenige vollständige Turns.")

    g = report.get("gpu", {})
    if g.get("status") == PASS:
        print(f"  GPU: Peak {g['util_percent_peak']} %, "
              f"Ø {g['util_percent_avg']} %, VRAM Peak {g['vram_mib_peak']} MiB")
    else:
        print(f"  GPU: {g.get('status')} ({g.get('reason','')})")

    print()
    print("  Vergleich Voice Forensics V1 (vor CUDA-Repair): 48.00 s warm")
    if w:
        delta = 48000 - w["total_ms"]
        richtung = "schneller" if delta > 0 else "langsamer"
        print(f"  Jetzt: {w['total_ms']/1000:.2f} s  →  "
              f"{abs(delta)/1000:.2f} s {richtung} ({abs(delta)/48000*100:.0f} %)")
    print("=" * 74)


def to_yaml(report) -> str:
    """Minimaler YAML-Writer (keine Abhängigkeit von PyYAML nötig)."""
    def emit(node, indent=0):
        pad = "  " * indent
        out = []
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, (dict, list)) and v:
                    out.append(f"{pad}{k}:")
                    out.append(emit(v, indent + 1))
                elif isinstance(v, (dict, list)):
                    out.append(f"{pad}{k}: {{}}" if isinstance(v, dict) else f"{pad}{k}: []")
                else:
                    out.append(f"{pad}{k}: {scalar(v)}")
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, (dict, list)):
                    body = emit(item, indent + 1)
                    first, *rest = body.split("\n")
                    out.append(f"{pad}- {first.strip()}")
                    out.extend(rest)
                else:
                    out.append(f"{pad}- {scalar(item)}")
        return "\n".join(out)

    def scalar(v):
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return str(v)
        s = str(v)
        if s == "" or any(c in s for c in ":#\n\"'{}[]") or s.strip() != s:
            return json.dumps(s, ensure_ascii=False)
        return s

    return emit(report) + "\n"


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Misst die Latenz eines GUIALITA-Sprach-Turns.")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--wav", help="vorhandene WAV-Datei messen (reproduzierbar)")
    src.add_argument("--record", action="store_true", help="vom Mikrofon aufnehmen")
    src.add_argument("--text", help="STT überspringen, direkt diesen Text senden")
    ap.add_argument("--turns", type=int, default=3, help="Anzahl Turns (Standard: 3, erster = kalt)")
    ap.add_argument("--seconds", type=float, default=5.0, help="Aufnahmedauer bei --record")
    ap.add_argument("--voice", default="us_female", help="TTS-Stimme")
    ap.add_argument("--isolated", action="store_true",
                    help="temporäre Datenbank verwenden (produktive DB bleibt unberührt)")
    ap.add_argument("--no-write", action="store_true", help="keinen YAML-Report schreiben")
    args = ap.parse_args()

    if not (args.wav or args.record or args.text):
        args.record = True

    tmpdir = None
    if args.isolated:
        tmpdir = tempfile.mkdtemp(prefix="guialita_measure_db_")
        os.environ["GUIALITA_DB"] = os.path.join(tmpdir, "measure.db")
        print(f"  Isolierte Datenbank: {os.environ['GUIALITA_DB']}")

    # Import erst nach Setzen der Umgebung
    from backend.manager import ModelManager
    from backend.memory.store import MemoryStore
    from backend.chat_service import ChatService
    from backend.audio.tts import tts_service
    from backend import paths

    print("  Initialisiere Komponenten …")
    manager = ModelManager()
    store = MemoryStore()
    chat_service = ChatService(manager, store)

    report = {
        "measurement": "voice_turn_latency",
        "purpose": "Schliesst das offene Performance-Gate aus Voice Forensics V1",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "baseline_compared_to": "GUIALITA-VOICE-ACTIVATION-V1 (48s warm, vor CUDA-Repair)",
        "environment": {
            "python": sys.version.split()[0],
            "guialita_root": paths.root(),
            "isolated_db": bool(args.isolated),
            "stt_available": manager.stt.is_available(),
            "tts_available": tts_service.is_available(),
            "llm_available": manager.llamacpp.is_available(),
        },
        "input": {},
        "turns": [],
        "summary": {},
        "gpu": {},
    }

    # --- Eingangssignal ---
    wav_path = None
    text = None
    if args.text:
        text = args.text
        report["input"] = {"mode": "text", "text": text}
    else:
        if args.record:
            try:
                wav_path = record_wav(args.seconds)
            except Exception as e:
                print(f"  FEHLER Aufnahme: {type(e).__name__}: {e}")
                print("  Abbruch — ohne Eingangssignal ist keine Messung möglich.")
                return 2
            report["input"] = {"mode": "microphone", **wav_info(wav_path)}
        else:
            wav_path = args.wav
            if not os.path.isfile(wav_path):
                print(f"  FEHLER: WAV nicht gefunden: {wav_path}")
                return 2
            report["input"] = {"mode": "wav_file", **wav_info(wav_path)}

    # --- Vorbedingungen ehrlich melden, aber nicht abbrechen ---
    env = report["environment"]
    for label, ok in (("LLM (llama-cpp-python)", env["llm_available"]),
                      ("STT (whisper.cpp)", env["stt_available"]),
                      ("TTS (LFM2.5-Audio)", env["tts_available"])):
        print(f"  {label:<26} {'verfügbar' if ok else 'NICHT verfügbar'}")

    gpu = GpuSampler()
    gpu.start()

    session_id = None
    for i in range(1, args.turns + 1):
        print(f"\n  Turn {i}/{args.turns} ({'kalt' if i == 1 else 'warm'}) …", flush=True)
        turn = measure_turn((manager, chat_service, tts_service),
                            wav_path, text, session_id, args.voice, i)
        session_id = turn.get("session_id") or session_id
        report["turns"].append(turn)
        st = turn["stages"]
        print(f"    STT {st.get('stt',{}).get('ms','—')} ms | "
              f"CHAT {st.get('chat',{}).get('ms','—')} ms | "
              f"TTS {st.get('tts',{}).get('ms','—')} ms")

    report["gpu"] = gpu.stop()

    # --- Zusammenfassung: Median über die Warm-Turns ---
    warm = [t for t in report["turns"] if t["kind"] == "warm" and t.get("total_complete")]
    if warm:
        def med(getter):
            vals = [getter(t) for t in warm if getter(t) is not None]
            return round(statistics.median(vals), 1) if vals else None

        total = med(lambda t: t.get("total_ms"))
        stages = {
            "stt_ms": med(lambda t: t["stages"].get("stt", {}).get("ms")),
            "llm_ms": med(lambda t: t["stages"].get("chat", {}).get("llm_ms")),
            "memory_overhead_ms": med(lambda t: t["stages"].get("chat", {}).get("memory_overhead_ms")),
            "tts_ms": med(lambda t: t["stages"].get("tts", {}).get("ms")),
        }
        named = {k: v for k, v in stages.items() if v}
        dominant = max(named, key=named.get) if named else None
        report["summary"]["warm"] = {
            "turns": len(warm),
            "total_ms": total,
            **stages,
            "dominant_stage": dominant.replace("_ms", "") if dominant else None,
            "dominant_share_percent": round(named[dominant] / total * 100) if dominant and total else None,
        }
    cold = next((t for t in report["turns"] if t["kind"] == "cold"), None)
    if cold:
        report["summary"]["cold_total_ms"] = cold.get("total_ms")

    print_report(report)

    if not args.no_write:
        outdir = os.path.join(BASE_DIR, "docs", "measurements")
        os.makedirs(outdir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        outfile = os.path.join(outdir, f"voice-turn-{stamp}.yaml")
        with open(outfile, "w", encoding="utf-8") as f:
            f.write("# GUIALITA — Sprach-Turn Latenzmessung (automatisch erzeugt)\n")
            f.write("# Erzeugt von scripts/measure_voice_turn.py\n")
            f.write(to_yaml(report))
        print(f"\n  Report: {os.path.relpath(outfile, BASE_DIR)}")
        print("  Nächster Schritt: Werte nach docs/GUIALITA_STATE.yaml übertragen")
        print("  (phases.voice_forensics_v1.gate_status).\n")

    if tmpdir:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    incomplete = [t["turn"] for t in report["turns"] if not t.get("total_complete")]
    return 1 if incomplete else 0


if __name__ == "__main__":
    sys.exit(main())
