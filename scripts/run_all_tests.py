#!/usr/bin/env python3
"""GUIALITA — einheitlicher Testlauf über alle Suiten.

Warum es dieses Skript gibt
---------------------------
Die Suiten riefen sich gegenseitig als Subprozesse auf. Beim Lauf aller neun
Suiten wurde `test_memory.py` achtmal und `test_api.py` sechsmal ausgeführt —
35 Suite-Läufe statt 9. Zwei Folgen:

1. Die Testzahlen in der Dokumentation widersprachen sich (108 / 79 / 71 / 145),
   weil dieselben Tests mehrfach gezählt wurden.
2. Ein einziges fehlendes Backend erschien als Kaskade vieler Fehler statt als
   eine klar benannte, nicht erfüllte Voraussetzung.

Dieser Runner führt jede Suite **genau einmal** aus und stuft sie ein:

    PASS          alle Tests der Suite bestanden
    FAIL          echte Fehlschläge (Zeilen aus dem Protokoll werden gezeigt)
    NOT_EXECUTED  Voraussetzung fehlt (Backend, Mikrofon, GPU, Modelle, Runtime)

NOT_EXECUTED wird niemals zu PASS gerechnet.

Nutzung
-------
    python3 scripts/run_all_tests.py              # alles, was hier laufen kann
    python3 scripts/run_all_tests.py --only memory tts
    python3 scripts/run_all_tests.py --list       # Inventar ohne Ausführung
    python3 scripts/run_all_tests.py --yaml       # Report nach docs/measurements/
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(BASE_DIR, "tests")


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


PASS = "PASS"
FAIL = "FAIL"
NOT_EXECUTED = "NOT_EXECUTED"

# Voraussetzungen je Suite — vor dem Lauf geprüft, damit NOT_EXECUTED
# begründet ist und nicht als Fehlschlag erscheint.
SUITES = [
    ("test_voice_activation.py",    "Voice-Zustandsautomat",   [],                          300),
    ("test_memory.py",              "Session + Memory-Store",  ["backend", "llm"],          300),
    ("test_memory_retrieval.py",    "Embedding + Retrieval",   ["backend", "llm"],          600),
    ("test_memory_graph.py",        "Entities + Relationen",   ["backend", "llm"],          600),
    ("test_graph_visualization.py", "Graph-API + Frontend",    ["backend"],                 600),
    ("test_api.py",                 "HTTP-Endpunkte",          ["backend", "llm"],          600),
    ("test_tts.py",                 "TTS-Erzeugung",           ["backend", "tts"],          900),
    ("test_capture.py",             "Mikrofonaufnahme",        ["mikrofon", "espeak"],      300),
    ("test_process_audio.py",       "WAV → LFM-Audio (Batch)", ["lfm-audio-runtime", "espeak"], 900),
]

CAPABILITY_LABEL = {
    "backend": "Backend erreichbar (http://localhost:8080)",
    "llm":     "LLM-Runtime geladen (llama-cpp-python + Modell)",
    "tts":     "TTS-Runtime (llama-liquid-audio-cli + LFM-Audio-Modell)",
    "stt":     "STT-Runtime (whisper.cpp + Modell)",
    "mikrofon": "Mikrofon / PortAudio",
    "espeak":  "espeak-ng (erzeugt synthetische Testsprache)",
    "lfm-audio-runtime": "LFM-Audio-Runtime für Batch-Verarbeitung",
}


def probe_capabilities(base_url="http://localhost:8080"):
    """Prüft VOR dem Testlauf, was auf dieser Maschine überhaupt vorhanden ist."""
    import json as _json
    import shutil
    import urllib.request

    caps = {k: False for k in CAPABILITY_LABEL}

    def get(path):
        try:
            with urllib.request.urlopen(base_url + path, timeout=5) as r:
                return _json.load(r)
        except Exception:
            return None

    health = get("/health")
    if health:
        caps["backend"] = True
        caps["llm"] = (health.get("primary_runtime", {}).get("status") == "online"
                       and any(m.get("available") for m in health.get("models", [])))
    audio = get("/audio/status")
    if audio:
        caps["stt"] = audio.get("status") == "online"
    tts = get("/audio/tts/status")
    if tts:
        caps["tts"] = bool(tts.get("available"))
    caps["lfm-audio-runtime"] = caps["tts"]
    caps["espeak"] = shutil.which("espeak-ng") is not None
    try:
        import sounddevice as sd
        caps["mikrofon"] = any(d.get("max_input_channels", 0) > 0 for d in sd.query_devices())
    except Exception:
        caps["mikrofon"] = False
    return caps

# Textmuster, die eine fehlende Voraussetzung belegen (nicht einen echten Fehler).
MISSING_PREREQ = [
    (re.compile(r"Connection refused|URLError|Max retries|Failed to establish"),
     "Backend läuft nicht (http://localhost:8080)"),
    (re.compile(r"whisper\.cpp nicht verfuegbar|whisper-cli"),
     "whisper.cpp (STT) nicht verfügbar"),
    (re.compile(r"TTS Service nicht verfügbar|llama-liquid-audio-cli"),
     "LFM-Audio-Runtime (TTS) nicht verfügbar"),
    (re.compile(r"No module named 'sounddevice'|PortAudio|kein Audio-?Ger|Invalid device"),
     "kein Mikrofon / PortAudio nicht verfügbar"),
    (re.compile(r"No module named 'llama_cpp'|llama-cpp-python ist nicht installiert"),
     "llama-cpp-python nicht installiert"),
    (re.compile(r"guialita_vmic|asoundrc"),
     "virtuelles Testmikrofon nicht eingerichtet"),
    (re.compile(r"Modell fehlt|nicht gefunden.*\.gguf|\.gguf.*not found"),
     "Modelldatei fehlt"),
    (re.compile(r"No module named '(\w+)'"),
     "Python-Abhängigkeit fehlt (siehe requirements.txt)"),
    (re.compile(r"No such file or directory: 'espeak-ng'"),
     "espeak-ng fehlt (erzeugt die synthetische Testsprache)"),
    (re.compile(r"FileNotFoundError:.*No such file or directory: '([\w.-]+)'"),
     "externes Werkzeug nicht installiert"),
]

RESULT_LINE = re.compile(r"^(OK|FAILED)\b(.*)$", re.MULTILINE)
RAN_LINE = re.compile(r"^Ran (\d+) tests? in ([\d.]+)s", re.MULTILINE)
COUNT = re.compile(r"(failures|errors|skipped)=(\d+)")


def count_test_functions(path):
    try:
        with open(path, encoding="utf-8") as f:
            return sum(1 for line in f if re.match(r"\s+def test", line))
    except OSError:
        return 0


def classify(returncode, output):
    """Entscheidet zwischen FAIL und NOT_EXECUTED — im Zweifel FAIL."""
    if returncode == 0:
        return PASS, None
    for pattern, reason in MISSING_PREREQ:
        if pattern.search(output):
            return NOT_EXECUTED, reason
    return FAIL, None


def parse_counts(output):
    ran = RAN_LINE.search(output)
    stats = {"ran": int(ran.group(1)) if ran else 0,
             "seconds": float(ran.group(2)) if ran else 0.0,
             "failures": 0, "errors": 0, "skipped": 0}
    result = RESULT_LINE.search(output)
    if result:
        for key, value in COUNT.findall(result.group(2)):
            stats[key] = int(value)
    stats["passed"] = max(0, stats["ran"] - stats["failures"] - stats["errors"] - stats["skipped"])
    return stats


def first_failures(output, limit=3):
    lines = [l.strip() for l in output.splitlines()
             if l.startswith(("FAIL:", "ERROR:"))]
    return lines[:limit]


def run_suite(filename, timeout, missing=()):
    path = os.path.join(TESTS_DIR, filename)
    env = dict(os.environ)
    env["GUIALITA_TEST_NESTED"] = "0"   # keine verschachtelten Subprozesse
    t0 = time.perf_counter()
    try:
        proc = subprocess.run([sys.executable, path], capture_output=True, text=True,
                              cwd=BASE_DIR, timeout=timeout, env=env)
        output = (proc.stdout or "") + (proc.stderr or "")
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        return {"status": FAIL, "reason": f"Timeout nach {timeout}s",
                "wall_seconds": round(time.perf_counter() - t0, 1),
                "ran": 0, "passed": 0, "failures": 0, "errors": 0, "skipped": 0,
                "failed_tests": []}
    if missing:
        status = NOT_EXECUTED
        reason = "fehlt: " + ", ".join(CAPABILITY_LABEL.get(m, m) for m in missing)
    else:
        status, reason = classify(rc, output)
    stats = parse_counts(output)
    return {"status": status, "reason": reason,
            "wall_seconds": round(time.perf_counter() - t0, 1),
            "failed_tests": first_failures(output) if status == FAIL else [],
            **stats}


def main():
    ap = argparse.ArgumentParser(description="Führt alle GUIALITA-Testsuiten genau einmal aus.")
    ap.add_argument("--only", nargs="+", metavar="TEIL",
                    help="nur Suiten, deren Name diese Teilzeichenkette enthält")
    ap.add_argument("--list", action="store_true", help="nur das Inventar zeigen")
    ap.add_argument("--yaml", action="store_true", help="Report nach docs/measurements/ schreiben")
    args = ap.parse_args()

    suites = SUITES
    if args.only:
        suites = [s for s in SUITES if any(k in s[0] for k in args.only)]
        if not suites:
            print("Keine Suite passt zum Filter.")
            return 2

    inventory = [(f, label, prereq, count_test_functions(os.path.join(TESTS_DIR, f)))
                 for f, label, prereq, _ in suites]
    total_functions = sum(n for *_, n in inventory)

    print()
    print("=" * 78)
    print("  GUIALITA — Testinventar")
    print("=" * 78)
    for f, label, prereq, n in inventory:
        need = ", ".join(prereq) if prereq else "keine"
        print(f"  {f:<32}{n:>4} Tests   {label:<26} braucht: {need}")
    print(f"\n  Testfunktionen gesamt: {total_functions}   (Suiten: {len(inventory)})")
    print("  Jede Suite wird genau einmal ausgeführt — keine Mehrfachzählung.")

    if args.list:
        print()
        return 0

    capabilities = probe_capabilities()
    print("\n" + "=" * 78)
    print("  Vorhandene Fähigkeiten auf dieser Maschine")
    print("=" * 78)
    for key, label in CAPABILITY_LABEL.items():
        mark = "vorhanden" if capabilities[key] else "FEHLT"
        print(f"  {mark:<11}{label}")

    print("\n" + "=" * 78)
    print("  Ausführung")
    print("=" * 78)

    results = {}
    for filename, label, prereq, timeout in suites:
        print(f"  {filename:<32} … ", end="", flush=True)
        missing = [c for c in prereq if not capabilities.get(c, False)]
        r = run_suite(filename, timeout, missing)
        results[filename] = {**r, "label": label, "requires": prereq}
        mark = {PASS: "PASS", FAIL: "FAIL", NOT_EXECUTED: "NOT EXECUTED"}[r["status"]]
        detail = f"{r['passed']}/{r['ran']}" if r["ran"] else "—"
        print(f"{mark:<13}{detail:>8}  {r['wall_seconds']:>6.1f}s"
              + (f"   {r['reason']}" if r.get("reason") else ""))
        for line in r.get("failed_tests", []):
            print(f"      {line}")

    graded = [r for r in results.values() if r["status"] in (PASS, FAIL)]
    ungraded = [r for r in results.values() if r["status"] == NOT_EXECUTED]
    passed = sum(r["passed"] for r in graded)
    ran = sum(r["ran"] for r in graded)
    failures = sum(r["failures"] + r["errors"] for r in graded)
    ungraded_ran = sum(r["ran"] for r in ungraded)
    ungraded_passed = sum(r["passed"] for r in ungraded)
    by_status = {s: [f for f, r in results.items() if r["status"] == s]
                 for s in (PASS, FAIL, NOT_EXECUTED)}

    print("\n" + "=" * 78)
    print("  Ergebnis")
    print("=" * 78)
    print(f"  Suiten PASS         : {len(by_status[PASS])}")
    print(f"  Suiten FAIL         : {len(by_status[FAIL])}"
          + (f"  ({', '.join(by_status[FAIL])})" if by_status[FAIL] else ""))
    print(f"  Suiten NOT EXECUTED : {len(by_status[NOT_EXECUTED])}"
          + (f"  ({', '.join(by_status[NOT_EXECUTED])})" if by_status[NOT_EXECUTED] else ""))
    print()
    print(f"  Testfunktionen vorhanden      : {total_functions}")
    print(f"  bewertbar ausgeführt          : {ran}   (Suiten PASS/FAIL)")
    print(f"    davon bestanden             : {passed}")
    print(f"    davon fehlgeschlagen        : {failures}")
    if ungraded:
        print(f"  in NOT-EXECUTED-Suiten        : {ungraded_ran} gestartet, "
              f"{ungraded_passed} davon bestanden")
        print("    → nicht gewertet: die Suite konnte ihre Voraussetzung nicht erfüllen.")
        print("      Diese Zahlen NICHT als PASS in die Dokumentation übernehmen.")

    report = {
        "test_run": {
            "capabilities": capabilities,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "runner": "scripts/run_all_tests.py",
            "nested_suite_calls": "disabled (GUIALITA_TEST_NESTED=0)",
            "test_functions_total": total_functions,
            "tests_executed_graded": ran,
            "tests_passed_graded": passed,
            "tests_failed_graded": failures,
            "tests_started_in_not_executed_suites": ungraded_ran,
            "not_counted_note": "Tests aus NOT_EXECUTED-Suiten zaehlen nicht als PASS",
            "suites_pass": len(by_status[PASS]),
            "suites_fail": len(by_status[FAIL]),
            "suites_not_executed": len(by_status[NOT_EXECUTED]),
            "suites": {f: {k: v for k, v in r.items() if k != "failed_tests"}
                       for f, r in results.items()},
        }
    }

    if args.yaml:
        outdir = os.path.join(BASE_DIR, "docs", "measurements")
        os.makedirs(outdir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        outfile = os.path.join(outdir, f"test-run-{stamp}.yaml")
        with open(outfile, "w", encoding="utf-8") as fh:
            fh.write("# GUIALITA — Testlauf (automatisch erzeugt)\n")
            fh.write(_yaml(report))
        print(f"\n  Report: {os.path.relpath(outfile, BASE_DIR)}")

    print()
    return 1 if by_status[FAIL] else 0


def _yaml(node, indent=0):
    pad = "  " * indent
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, dict) and v:
                out.append(f"{pad}{k}:")
                out.append(_yaml(v, indent + 1))
            elif isinstance(v, list) and v:
                out.append(f"{pad}{k}:")
                out.extend(f"{pad}  - {_scalar(i)}" for i in v)
            elif isinstance(v, (dict, list)):
                out.append(f"{pad}{k}: " + ("{}" if isinstance(v, dict) else "[]"))
            else:
                out.append(f"{pad}{k}: {_scalar(v)}")
    return "\n".join(out) + ("\n" if indent == 0 else "")


def _scalar(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    return json.dumps(s, ensure_ascii=False) if (not s or s.strip() != s or
                                                 any(c in s for c in ":#\n\"'{}[]")) else s


if __name__ == "__main__":
    sys.exit(main())
