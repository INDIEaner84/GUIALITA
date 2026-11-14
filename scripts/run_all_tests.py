#!/usr/bin/env python3
"""GUIALITA — einheitlicher Testlauf über alle Suiten.

Warum es dieses Skript gibt
---------------------------
Die Suiten riefen sich gegenseitig als Subprozesse auf. Beim historischen Lauf
aller neun Suiten wurde `test_memory.py` achtmal und `test_api.py` sechsmal ausgeführt —
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
import ast
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
    ("test_voice_activation.py",    "Voice-Zustandsautomat",   ["deps"],                    300),
    ("test_memory.py",              "Session + Memory-Store",  ["backend", "llm"],          300),
    ("test_memory_retrieval.py",    "Embedding + Retrieval",   ["backend", "llm"],          600),
    ("test_memory_graph.py",        "Entities + Relationen",   ["backend", "llm"],          600),
    ("test_graph_visualization.py", "Graph-API + Frontend",    ["backend"],                 600),
    ("test_api.py",                 "HTTP-Endpunkte",          ["backend", "llm"],          600),
    ("test_tts.py",                 "TTS-Erzeugung",           ["backend", "tts"],          900),
    ("test_capture.py",             "Mikrofonaufnahme",        ["mikrofon", "espeak"],      300),
    ("test_process_audio.py",       "WAV → LFM-Audio (Batch)", ["lfm-audio-runtime", "espeak"], 900),
    # Hauptzweig (M5): Diese drei Suiten existierten und waren in der SSOT
    # dokumentiert, standen aber nicht in dieser Liste — sie liefen damit nie
    # über den kanonischen Lauf. Seit 2026-11-13 enthalten. Alle drei arbeiten
    # in-process (kein Server, kein Modell) und brauchen nur die
    # Python-Abhängigkeiten.
    ("test_audit.py",               "Audit/Export",             ["deps"],                   600),
    ("test_chat_service.py",        "ChatService (Fake-LLM)",   ["deps"],                   600),
    ("test_audio_contract.py",      "Audio-Contract",           ["deps"],                   300),
    # Neu 2026-11-13 (ADR-002, P2): Statistik des Benchmarks. Reine
    # Standardbibliothek — läuft überall, auch ohne installierte Pakete.
    ("test_benchmark.py",           "Benchmark-Statistik",      [],                         120),
    # Neu 2026-11-13 (ADR-002, P3–P6): Eval-Harness, Lifecycle-Budget,
    # Rollen-Registry, MUSCAL CLI/HTTP und Dokumenten-Konsistenz. Alle sechs
    # Suiten sind reine Standardbibliothek — belastbar in CI ohne Backend.
    ("test_eval.py",                "Eval-Harness / Golden Set", [],                      120),
    ("test_modelsctl.py",           "VRAM-Budget + Lifecycle",  [],                      120),
    ("test_roles.py",               "Rollen-Registry",          [],                      120),
    ("test_muscal.py",              "MUSCAL-Kette / Guard",     [],                      120),
    ("test_muscal_http.py",         "MUSCAL-HTTP",              [],                      120),
    ("test_doc_consistency.py",     "Dokumenten-Konsistenz",    [],                      120),
]

CAPABILITY_LABEL = {
    "deps":    "Python-Abhängigkeiten importierbar (pydantic, fastapi)",
    "backend": "Backend erreichbar (http://localhost:8080)",
    "llm":     "LLM-Runtime geladen (llama-cpp-python + Modell)",
    "mock":    "Mock-LLM aktiv (GUIALITA_MOCK_LLM=1) — Test-Adapter, kein Modell/GPU",
    "tts":     "TTS-Runtime (llama-liquid-audio-cli + LFM-Audio-Modell)",
    "stt":     "STT-Runtime (whisper.cpp + Modell)",
    "mikrofon": "Mikrofon / PortAudio",
    "espeak":  "espeak-ng (erzeugt synthetische Testsprache)",
    "lfm-audio-runtime": "LFM-Audio-Runtime für Batch-Verarbeitung",
}

# Welche Voraussetzung durch den Mock-Adapter als erfüllt gilt.
# Bewusst eng: nur "llm" (Chat-Pfad). STT/TTS/Mikrofon bleiben echte
# Hardware-/Runtime-Voraussetzungen — der Mock täuscht sie nicht vor.
MOCK_SATISFIES = {"llm"}


def satisfied(prereq: str, capabilities: dict) -> bool:
    """Erfüllt diese Maschine die Voraussetzung (echt oder per Mock)?"""
    if capabilities.get(prereq, False):
        return True
    return prereq in MOCK_SATISFIES and capabilities.get("mock", False)


def probe_capabilities(base_url="http://localhost:8080"):
    """Prüft VOR dem Testlauf, was auf dieser Maschine überhaupt vorhanden ist."""
    import importlib.util
    import json as _json
    import shutil
    import urllib.request

    caps = {k: False for k in CAPABILITY_LABEL}

    # In-process-Suiten brauchen keinen Server, aber die Python-Pakete. Ohne
    # diese Prüfung erschienen sie in einer nackten Umgebung als FAIL
    # (ImportError) statt als NOT_EXECUTED mit benannter Ursache.
    caps["deps"] = all(importlib.util.find_spec(mod) is not None
                       for mod in ("pydantic", "fastapi"))

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
        caps["mock"] = bool(health.get("mock_runtime", {}).get("enabled", False))
    else:
        # Backend läuft nicht: der Mock-Modus kann trotzdem lokal gesetzt sein.
        caps["mock"] = os.environ.get("GUIALITA_MOCK_LLM", "").strip().lower() in (
            "1", "true", "yes", "on")
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
    """Zählt Testfunktionen statisch per AST.

    Die frühere Fassung nutzte die Regex ``\\s+def test`` — also nur
    **eingerückte** Definitionen. Damit zählte sie ausschließlich Methoden in
    ``unittest.TestCase``-Klassen und übersah jeden modulweiten Test. Folge:

    - ``tests/test_process_audio.py`` meldete 5 statt 14 (9 modulweite Tests
      fehlten), die Gesamtzahl 141 war entsprechend zu niedrig.
    - ``tests/test_capture.py`` meldete 0, obwohl dort 6 Testfunktionen stehen
      (``test3_…`` bis ``test10_…``, aufgerufen aus ``main()``).

    Der AST zählt jede Funktion, deren Name mit ``test`` beginnt — unabhängig
    von Einrückung und Klasse.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
    except (OSError, SyntaxError):
        return 0
    return sum(1 for node in ast.walk(tree)
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               and node.name.startswith("test"))


STATE_FILE = os.path.join(BASE_DIR, "docs", "GUIALITA_STATE.yaml")
STATE_ROW = re.compile(r"^ {4}(test_[A-Za-z0-9_]+\.py):\s*\{tests:\s*(\d+)")
STATE_TOTAL = re.compile(r"^  test_functions_total:\s*(\d+)")


def read_state_inventory(path=STATE_FILE):
    """Liest Testzahlen aus der SSOT — bewusst ohne PyYAML.

    Nur ``test_functions_total`` und der Block ``suite_inventory`` werden
    gelesen. Das Skript bleibt damit auch dort lauffähig, wo PyYAML fehlt
    (z. B. im System-Python einer frischen Maschine).
    """
    total = None
    rows = {}
    in_block = False
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            match_total = STATE_TOTAL.match(line)
            if match_total:
                total = int(match_total.group(1))
                in_block = False
                continue
            if re.match(r"^  suite_inventory:\s*$", line):
                in_block = True
                continue
            if in_block:
                row = STATE_ROW.match(line)
                if row:
                    rows[row.group(1)] = int(row.group(2))
                elif line.strip() and not line.startswith("    "):
                    in_block = False
    return total, rows


def check_state(inventory):
    """Gleicht das Runner-Inventar gegen die SSOT ab (ADR-002, D7).

    Gibt 0 bei Übereinstimmung, 1 bei Abweichung, 2 wenn die SSOT fehlt.
    """
    try:
        total, rows = read_state_inventory()
    except OSError as exc:
        print(f"\n  SSOT nicht lesbar: {exc}")
        return 2

    problems = []
    names = {f for f, *_ in inventory}
    for f, _label, _prereq, n in inventory:
        if f not in rows:
            problems.append(f"{f}: fehlt in suite_inventory")
        elif rows[f] != n:
            problems.append(f"{f}: SSOT nennt {rows[f]}, tatsächlich {n}")
    for f in rows:
        if f not in names:
            problems.append(f"{f}: in suite_inventory, aber nicht im Runner")
    computed = sum(n for *_, n in inventory)
    if total != computed:
        problems.append(f"test_functions_total: SSOT nennt {total}, tatsächlich {computed}")

    print()
    print("=" * 78)
    print("  Abgleich Runner ↔ docs/GUIALITA_STATE.yaml")
    print("=" * 78)
    print(f"  Suiten im Runner: {len(inventory)}   in der SSOT: {len(rows)}")
    print(f"  Testfunktionen im Runner: {computed}   in der SSOT: {total}")
    if problems:
        print("\n  ABWEICHUNGEN:")
        for problem in problems:
            print(f"    - {problem}")
        return 1
    print("\n  Keine Abweichung.")
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
    ap.add_argument("--check-state", action="store_true",
                    help="Inventar gegen docs/GUIALITA_STATE.yaml prüfen")
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

    if args.check_state:
        return check_state(inventory)

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
        missing = [c for c in prereq if not satisfied(c, capabilities)]
        r = run_suite(filename, timeout, missing)
        # Kennzeichnung, wenn die Suite nur dank Mock-Adapter laufen konnte.
        # Das ist kein Ersatz für die echte Runtime und wird nicht als
        # voller Nachweis gewertet (siehe Hinweis im Ergebnisblock).
        # Bedingung bewusst eng: Mock muss tatsächlich aktiv sein UND die
        # Suite muss gewertet laufen (NOT_EXECUTED zählt nicht) UND die echte
        # Voraussetzung muss fehlen.
        via_mock = (capabilities.get("mock", False)
                    and r["status"] in (PASS, FAIL)
                    and any(c in MOCK_SATISFIES and not capabilities.get(c, False)
                            for c in prereq))
        results[filename] = {**r, "label": label, "requires": prereq,
                             "via_mock_adapter": via_mock}
        mark = {PASS: "PASS", FAIL: "FAIL", NOT_EXECUTED: "NOT EXECUTED"}[r["status"]]
        if r["status"] == PASS and via_mock:
            mark = "PASS (mock)"
        detail = f"{r['passed']}/{r['ran']}" if r["ran"] else "—"
        if r.get("skipped"):
            detail += f" ({r['skipped']} skip)"
        print(f"{mark:<13}{detail:>12}  {r['wall_seconds']:>6.1f}s"
              + (f"   {r['reason']}" if r.get("reason") else ""))
        for line in r.get("failed_tests", []):
            print(f"      {line}")

    graded = [r for r in results.values() if r["status"] in (PASS, FAIL)]
    ungraded = [r for r in results.values() if r["status"] == NOT_EXECUTED]
    passed = sum(r["passed"] for r in graded)
    ran = sum(r["ran"] for r in graded)
    failures = sum(r["failures"] + r["errors"] for r in graded)
    skipped_graded = sum(r["skipped"] for r in graded)
    mock_suites = [f for f, r in results.items() if r.get("via_mock_adapter")]
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
    print(f"    davon übersprungen (skip)   : {skipped_graded}"
          "   ← Voraussetzung fehlt, KEIN Fehler")
    if mock_suites:
        print()
        print(f"  über Mock-Adapter gelaufen    : {', '.join(mock_suites)}")
        print("    → GUIALITA_MOCK_LLM=1: Chat-/Memory-/API-Pfad sind geprüft,")
        print("      die ECHTE LLM-Runtime ist damit aber NICHT nachgewiesen.")
        print("      Runtime-Tests (Modell, STT, TTS) bleiben übersprungen.")
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
            "tests_skipped_graded": skipped_graded,
            "suites_via_mock_adapter": mock_suites,
            "mock_adapter_note": ("Mock-LLM ersetzt keine echte Runtime: "
                                  "Chat-/Memory-/API-Pfad geprüft, LLM/STT/TTS "
                                  "bleiben unbestätigt"),
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
