#!/usr/bin/env python3
"""GUIALITA — Eval-Harness mit Golden Set (ADR-002, D1 / P3).

Warum das vor jeder Orchestrierung kommt
----------------------------------------
Ohne dieses Skript ist jede Aussage der Form "Modell X ist besser" oder "Rolle
Y funktioniert" eine Meinung. Das Harness macht daraus eine Zahl, die man vor
und nach einer Änderung vergleichen kann.

Zwei Betriebsarten
------------------
``--dry-run``  prüft **das Harness selbst**. Jede Aufgabe bringt eine
               aufgezeichnete Stub-Antwort und das erwartete Urteil mit.
               Stimmen alle Urteile, arbeiten die Grader korrekt — auch die
               negativen Kontrollen, die absichtlich falsch sind.
               Das braucht kein Backend, kein Modell, keine GPU.

``--live``     bewertet ein echtes Modell über ``POST /chat``. Der Rollen-Prompt
               wird der Aufgabe vorangestellt, weil ``/chat`` keinen
               System-Parameter kennt. ``--model`` überschreibt das Modell aus
               ``config/roles.json`` und macht so zwei Konfigurationen direkt
               vergleichbar.

``--compare A B`` vergleicht zwei Live-Reports: Score, p50, p95 und maximale
               Latenz. Das ist der Nachweis aus ADR-002 D1 — allerdings erst
               belastbar, wenn beide Reports auf der Referenzmaschine entstanden
               sind. Ein Sandbox-Dry-Run ist kein Modellvergleich.

Aufbau der Aufgabensätze
------------------------
``evals/roles/<rolle>.json`` ist die Quelle. ``evals/golden.json`` wird daraus
von ``scripts/build_golden.py`` generiert und enthält das Gesamtset. Die
Grader sind bewusst klein und explizit: ``equals``, ``one_of``, ``contains``,
``must_not_contain``, ``regex``, ``json_keys``, ``one_of_field``,
``min_list_len``, ``non_empty``, ``max_latency_ms``.

Ressourcen
----------
Ein Live-Report enthält einen ``resource_snapshot``. Wo ``nvidia-smi`` fehlt,
steht dort ausdrücklich „nicht gemessen" — die deklarierte VRAM-Größe aus
``config/model_budget.json`` ist eine Planungsgröße, keine Messung.

Nutzung
-------
    python3 scripts/eval.py --dry-run
    python3 scripts/eval.py --dry-run --all-suites
    python3 scripts/eval.py --dry-run --suite auditor
    python3 scripts/eval.py --live --model granite-3b --json /tmp/a.json
    python3 scripts/eval.py --live --model granite-8b --json /tmp/b.json
    python3 scripts/eval.py --compare /tmp/a.json /tmp/b.json
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLDEN = ROOT / "evals" / "golden.json"
ROLE_DIR = ROOT / "evals" / "roles"
ROLES_FILE = ROOT / "config" / "roles.json"
BUDGET_FILE = ROOT / "config" / "model_budget.json"
ROLE_SUITES = ("router", "planner", "coder", "auditor")


def display_path(path: Path) -> str:
    """Pfad relativ zum Repo, falls möglich — sonst absolut."""
    try:
        return str(Path(path).relative_to(ROOT))
    except ValueError:
        return str(path)


# ----------------------------------------------------------------------------
# Golden Set und Rollen
# ----------------------------------------------------------------------------
def load_golden(path: Path = DEFAULT_GOLDEN) -> dict:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    tasks = data.get("tasks") or []
    if not tasks:
        raise ValueError(f"Golden Set ohne Aufgaben: {path}")
    seen = set()
    for task in tasks:
        for key in ("id", "role", "prompt", "expect", "stub"):
            if key not in task:
                raise ValueError(f"Aufgabe ohne '{key}': {task.get('id', '?')}")
        if task["id"] in seen:
            raise ValueError(f"Doppelte Aufgaben-ID: {task['id']}")
        seen.add(task["id"])
        if not isinstance(task["stub"], dict):
            raise ValueError(f"stub muss ein Objekt sein: {task['id']}")
        if task["stub"].get("outcome") not in ("pass", "fail"):
            raise ValueError(f"stub.outcome muss pass|fail sein: {task['id']}")
    return data


def load_roles(path: Path = ROLES_FILE) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle).get("roles", {})
    except OSError:
        return {}


# ----------------------------------------------------------------------------
# Grader
# ----------------------------------------------------------------------------
def extract_json(text: str):
    """Holt ein JSON-Objekt aus einer Antwort — auch aus einem Code-Block.

    Modelle liefern JSON häufig in ```json ... ``` oder mit Vorrede. Das ist
    kein Grund, die Aufgabe als gescheitert zu werten; fehlende Schlüssel sind
    es.
    """
    candidates = [text]
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fence:
        candidates.insert(0, fence.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate.strip())
        except (json.JSONDecodeError, ValueError):
            continue
    return None


def grade(task: dict, response: str, latency_ms: float) -> tuple[bool, list[str]]:
    """Bewertet eine Antwort gegen ``task['expect']``.

    Gibt (bestanden, Gründe) zurück. Die Gründe werden auch bei Erfolg gefüllt,
    damit ein Lauf nachvollziehbar bleibt.
    """
    expect = task.get("expect") or {}
    text = response or ""
    lowered = text.lower().strip()
    reasons: list[str] = []
    ok = True

    if "non_empty" in expect and expect["non_empty"]:
        if not lowered:
            ok = False
            reasons.append("Antwort ist leer")

    if "equals" in expect:
        wanted = str(expect["equals"]).lower().strip()
        if lowered != wanted:
            ok = False
            reasons.append(f"erwartet genau '{wanted}', erhalten '{lowered[:60]}'")
        else:
            reasons.append(f"Label korrekt: {wanted}")

    if "one_of" in expect:
        allowed = [str(v).lower().strip() for v in expect["one_of"]]
        if lowered not in allowed:
            ok = False
            reasons.append(f"keiner der erlaubten Werte {allowed}: '{lowered[:60]}'")

    if "contains" in expect:
        for needle in expect["contains"]:
            if str(needle).lower() not in lowered:
                ok = False
                reasons.append(f"fehlt: '{needle}'")

    if "must_not_contain" in expect:
        for needle in expect["must_not_contain"]:
            if str(needle).lower() in lowered:
                ok = False
                reasons.append(f"verbotenes Muster gefunden: '{needle}'")

    if "regex" in expect:
        for pattern in expect["regex"]:
            if not re.search(pattern, text):
                ok = False
                reasons.append(f"Regex ohne Treffer: {pattern}")

    parsed = None
    if any(key in expect for key in ("json_keys", "one_of_field", "min_list_len")):
        parsed = extract_json(text)
        if parsed is None:
            ok = False
            reasons.append("Antwort ist kein JSON")
        elif not isinstance(parsed, dict):
            ok = False
            reasons.append("JSON ist kein Objekt")
            parsed = None
        else:
            for key in expect.get("json_keys", []):
                if key not in parsed:
                    ok = False
                    reasons.append(f"JSON-Schlüssel fehlt: {key}")

    if "one_of_field" in expect and parsed:
        spec = expect["one_of_field"]
        field = spec.get("field")
        allowed = [str(v).lower() for v in spec.get("values", [])]
        value = str(parsed.get(field, "")).lower()
        if value not in allowed:
            ok = False
            reasons.append(f"{field}={value or '—'} nicht in {allowed}")

    if "min_list_len" in expect and parsed:
        spec = expect["min_list_len"]
        field = spec.get("field")
        minimum = int(spec.get("min", 1))
        value = parsed.get(field)
        if not isinstance(value, list):
            ok = False
            reasons.append(f"{field} ist keine Liste")
        elif len(value) < minimum:
            ok = False
            reasons.append(f"{field} hat {len(value)} Einträge, mindestens {minimum} nötig")
        else:
            reasons.append(f"{field}: {len(value)} Einträge")

    limit = expect.get("max_latency_ms")
    if limit is not None and latency_ms > float(limit):
        ok = False
        reasons.append(f"zu langsam: {latency_ms:.0f} ms > {limit} ms")

    return ok, reasons


def percentile(values: list[float], pct: float) -> float | None:
    """Lineares Perzentil ohne numpy — für p50/p95 aus kleinen Stichproben."""
    if not values:
        return None
    ordered = sorted(float(v) for v in values)
    if len(ordered) == 1:
        return round(ordered[0], 1)
    position = (len(ordered) - 1) * pct / 100.0
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    value = ordered[lower] * (1 - fraction) + ordered[upper] * fraction
    return round(value, 1)


# ----------------------------------------------------------------------------
# Backends
# ----------------------------------------------------------------------------
class StubBackend:
    """Liefert die aufgezeichnete Antwort einer Aufgabe. Prüft das Harness."""

    name = "stub"

    def __init__(self, roles: dict | None = None):
        self.roles = roles or {}

    def ask(self, task: dict) -> tuple[str, float]:
        return task["stub"]["response"], 0.0


class LiveBackend:
    """Fragt ein laufendes Backend über POST /chat."""

    name = "live"

    def __init__(self, base_url: str, roles: dict | None = None,
                 timeout: float = 300.0, model_override: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.roles = roles or {}
        self.timeout = timeout
        self.model_override = model_override

    def _message(self, task: dict) -> str:
        role = self.roles.get(task["role"], {})
        prompt = role.get("prompt", "").strip()
        if not prompt:
            return task["prompt"]
        return f"{prompt}\n\nAufgabe: {task['prompt']}"

    def ask(self, task: dict) -> tuple[str, float]:
        role = self.roles.get(task["role"], {})
        payload = {"message": self._message(task)}
        model = self.model_override or role.get("model")
        if model:
            payload["model"] = model
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(self.base_url + "/chat", data=data,
                                         method="POST")
        request.add_header("Content-Type", "application/json")
        started = time.perf_counter()
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read())
        latency_ms = (time.perf_counter() - started) * 1000
        if isinstance(body, dict) and body.get("status") == "error":
            raise RuntimeError(f"Backend-Fehler: {body.get('error', '?')} — "
                               f"{body.get('details', '')}")
        return str(body.get("response", "")), latency_ms


# ----------------------------------------------------------------------------
# Lauf
# ----------------------------------------------------------------------------
def select_tasks(golden: dict, role: str | None, task_id: str | None) -> list[dict]:
    tasks = golden["tasks"]
    if role:
        tasks = [t for t in tasks if t["role"] == role]
    if task_id:
        tasks = [t for t in tasks if t["id"] == task_id]
    return tasks


def run_dry(tasks: list[dict], backend: StubBackend) -> dict:
    """Selbsttest: stimmt jedes Urteil mit dem erwarteten Urteil überein?"""
    results = []
    for task in tasks:
        response, latency = backend.ask(task)
        passed, reasons = grade(task, response, latency)
        expected = task["stub"]["outcome"] == "pass"
        agrees = passed == expected
        results.append({
            "id": task["id"],
            "role": task["role"],
            "kind": task.get("kind", "positive"),
            "graded": "pass" if passed else "fail",
            "expected": "pass" if expected else "fail",
            "harness": "ok" if agrees else "FEHLER",
            "reasons": reasons,
        })
    return {"mode": "dry-run", "results": results}


def run_live(tasks: list[dict], backend: LiveBackend) -> dict:
    results = []
    for task in tasks:
        try:
            response, latency = backend.ask(task)
        except urllib.error.HTTPError as exc:
            results.append({"id": task["id"], "role": task["role"],
                            "graded": "fail", "latency_ms": None,
                            "reasons": [f"HTTP {exc.code}"]})
            continue
        except Exception as exc:  # noqa: BLE001 — Diagnose
            results.append({"id": task["id"], "role": task["role"],
                            "graded": "fail", "latency_ms": None,
                            "reasons": [f"{type(exc).__name__}: {exc}"]})
            continue
        passed, reasons = grade(task, response, latency)
        results.append({
            "id": task["id"],
            "role": task["role"],
            "kind": task.get("kind", "positive"),
            "graded": "pass" if passed else "fail",
            "latency_ms": round(latency, 1),
            "reasons": reasons,
            "response_head": (response or "")[:160].replace("\n", " "),
        })
    return {"mode": "live", "results": results}


def resource_snapshot(root: Path = ROOT) -> dict:
    """VRAM: messen, wo möglich — sonst ausdrücklich als nicht gemessen markieren."""
    snapshot: dict = {
        "measured": False,
        "source": "nicht geprüft",
        "declared_total_gb": None,
        "gpu_used_gb": None,
        "gpu_total_gb": None,
        "gpu_free_gb": None,
    }
    try:
        with (root / "config" / "model_budget.json").open(encoding="utf-8") as handle:
            budget = json.load(handle)
        snapshot["declared_total_gb"] = budget.get("gpu", {}).get("total_gb")
    except (OSError, ValueError, json.JSONDecodeError):
        pass

    if not shutil.which("nvidia-smi"):
        snapshot["source"] = "nvidia-smi nicht vorhanden — nicht gemessen"
        return snapshot
    try:
        output = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
        used, total = (int(part.strip()) for part in output[0].split(","))
        snapshot.update({
            "measured": True,
            "source": "nvidia-smi",
            "gpu_used_gb": round(used / 1024, 2),
            "gpu_total_gb": round(total / 1024, 2),
            "gpu_free_gb": round((total - used) / 1024, 2),
        })
    except (ValueError, OSError, IndexError, subprocess.SubprocessError):
        snapshot["source"] = "nvidia-smi vorhanden, aber nicht auswertbar — nicht gemessen"
    return snapshot


def summarize(report: dict) -> dict:
    results = report["results"]
    if report["mode"] == "dry-run":
        broken = [r for r in results if r["harness"] != "ok"]
        return {"tasks": len(results), "harness_errors": len(broken),
                "ok": not broken}
    passed = [r for r in results if r["graded"] == "pass"]
    latencies = [r["latency_ms"] for r in results if r.get("latency_ms") is not None]
    p50 = percentile(latencies, 50)
    p95 = percentile(latencies, 95)
    return {
        "tasks": len(results),
        "passed": len(passed),
        "failed": len(results) - len(passed),
        "score_pct": round(100 * len(passed) / len(results), 1) if results else 0.0,
        "p50_latency_ms": p50,
        "median_latency_ms": p50,   # Alias, damit alte Reports lesbar bleiben
        "p95_latency_ms": p95,
        "max_latency_ms": round(max(latencies), 1) if latencies else None,
    }


def compare_reports(left: dict, right: dict) -> dict:
    """Vergleicht zwei Live-Reports nach Score und Latenz (ADR-002 D1)."""
    if left.get("mode") != "live" or right.get("mode") != "live":
        raise ValueError("Nur Live-Reports sind vergleichbar")

    def summary(report: dict) -> dict:
        # Neu berechnen, nicht dem gespeicherten Summary blind vertrauen:
        # aeltere Reports kennen p95 noch nicht.
        return summarize(report)

    def label(report: dict) -> str:
        config = report.get("configuration") or {}
        return str(config.get("model") or config.get("golden")
                   or report.get("revision") or "unbekannt")

    a, b = summary(left), summary(right)
    warnings = []
    if a["tasks"] != b["tasks"]:
        warnings.append(f"Unterschiedliche Aufgabenzahl: {a['tasks']} vs {b['tasks']}")
    if left.get("golden") != right.get("golden"):
        warnings.append("Unterschiedliche Golden Sets — Vergleich nur eingeschränkt belastbar")

    def delta(key: str):
        first, second = a.get(key), b.get(key)
        if first is None or second is None:
            return None
        return round(second - first, 1)

    return {
        "left": {"label": label(left), **a},
        "right": {"label": label(right), **b},
        "delta": {
            "score_pct": delta("score_pct"),
            "passed": delta("passed"),
            "p50_latency_ms": delta("p50_latency_ms"),
            "p95_latency_ms": delta("p95_latency_ms"),
            "max_latency_ms": delta("max_latency_ms"),
        },
        "warnings": warnings,
    }


# ----------------------------------------------------------------------------
# Ausgabe
# ----------------------------------------------------------------------------
def print_report(report: dict) -> None:
    summary = summarize(report)
    print()
    print("=" * 78)
    print(f"  Eval — {report['mode']}")
    print("=" * 78)
    if report.get("configuration"):
        config = report["configuration"]
        if config.get("model"):
            print(f"  Modell-Override: {config['model']}")
        if config.get("golden"):
            print(f"  Golden Set     : {config['golden']}")
    if report["mode"] == "dry-run":
        for row in report["results"]:
            mark = "ok  " if row["harness"] == "ok" else "FEHL"
            print(f"  {mark:<5}{row['id']:<28} {row['role']:<10} "
                  f"erwartet={row['expected']:<5} geurteilt={row['graded']}")
        print()
        if summary["ok"]:
            print(f"  Harness-Selbsttest: OK — {summary['tasks']} Aufgaben, "
                  f"alle Urteile wie erwartet")
        else:
            print(f"  Harness-Selbsttest: FEHLER in {summary['harness_errors']} "
                  f"von {summary['tasks']} Aufgaben")
        return

    for row in report["results"]:
        mark = "PASS" if row["graded"] == "pass" else "FAIL"
        latency = f"{row['latency_ms']:.0f} ms" if row.get("latency_ms") is not None else "—"
        print(f"  {mark:<5}{row['id']:<28} {row['role']:<10} {latency:>10}")
        if row["graded"] == "fail":
            for reason in row["reasons"][:3]:
                print(f"        · {reason}")
    print()
    print(f"  Score: {summary['passed']}/{summary['tasks']} "
          f"({summary['score_pct']} %)   p50: "
          f"{summary['p50_latency_ms'] or '—'} ms   p95: "
          f"{summary['p95_latency_ms'] or '—'} ms   max: "
          f"{summary['max_latency_ms'] or '—'} ms")
    resource = report.get("resource_snapshot")
    if resource:
        if resource.get("measured"):
            print(f"  VRAM (nvidia-smi): {resource['gpu_used_gb']} GB belegt, "
                  f"{resource['gpu_free_gb']} GB frei von {resource['gpu_total_gb']} GB")
        else:
            print(f"  VRAM: NICHT GEMESSEN ({resource['source']}); "
                  f"deklariertes Budget: {resource['declared_total_gb'] or '—'} GB")


def print_comparison(comparison: dict) -> None:
    left, right, delta = comparison["left"], comparison["right"], comparison["delta"]

    def signed(value) -> str:
        return "—" if value is None else f"{value:+}"

    print()
    print("=" * 78)
    print("  Eval — Modellvergleich (ADR-002 D1)")
    print("=" * 78)
    print(f"  A: {left['label']:<28} Score {left['score_pct']:>5} %   "
          f"p50 {left['p50_latency_ms'] or '—':>7} ms   p95 {left['p95_latency_ms'] or '—':>7} ms")
    print(f"  B: {right['label']:<28} Score {right['score_pct']:>5} %   "
          f"p50 {right['p50_latency_ms'] or '—':>7} ms   p95 {right['p95_latency_ms'] or '—':>7} ms")
    print()
    print(f"  Δ Score : {signed(delta['score_pct'])} %-Punkte")
    print(f"  Δ p50   : {signed(delta['p50_latency_ms'])} ms")
    print(f"  Δ p95   : {signed(delta['p95_latency_ms'])} ms")
    print(f"  Δ max   : {signed(delta['max_latency_ms'])} ms")
    for warning in comparison["warnings"]:
        print(f"  WARNUNG: {warning}")


def git_revision() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True,
                              timeout=5).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def run_all_suites(roles: dict, json_path: str | None) -> int:
    """Trockenlauf über jede Rollen-Suite einzeln — beweist die vier Quellen."""
    reports = []
    all_ok = True
    print()
    print("=" * 78)
    print("  Eval — Selbsttest aller Rollen-Suiten")
    print("=" * 78)
    for role in ROLE_SUITES:
        path = ROLE_DIR / f"{role}.json"
        golden = load_golden(path)
        report = run_dry(golden["tasks"], StubBackend(roles))
        report["generated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        report["revision"] = git_revision()
        report["golden"] = display_path(path)
        report["configuration"] = {"golden": display_path(path), "role": role}
        report["summary"] = summarize(report)
        reports.append(report)
        status = "OK" if report["summary"]["ok"] else "FEHLER"
        print(f"  {role:<10}{len(golden['tasks']):>3} Aufgaben   {status}")
        all_ok &= report["summary"]["ok"]
    if json_path:
        path = Path(json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"mode": "all-suites", "reports": reports},
                                   ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        print(f"\n  Report geschrieben: {path}")
    print(f"\n  Gesamt: {'OK' if all_ok else 'FEHLER'}")
    return 0 if all_ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Eval-Harness: Golden Set gegen Stub (Selbsttest) oder "
                    "gegen ein laufendes Backend.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true",
                      help="Harness selbst prüfen (kein Backend nötig)")
    mode.add_argument("--live", action="store_true",
                      help="echtes Modell über POST /chat bewerten")
    mode.add_argument("--compare", nargs=2, metavar=("A", "B"),
                      help="zwei Live-JSON-Reports vergleichen")

    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--role", help="nur Aufgaben dieser Rolle")
    parser.add_argument("--suite", choices=ROLE_SUITES,
                        help="Golden Set einer Rolle statt Gesamtset")
    parser.add_argument("--all-suites", action="store_true",
                        help="alle Rollen-Suiten einzeln im Trockenlauf prüfen")
    parser.add_argument("--model", help="Live-Lauf: Modell aus roles.json überschreiben")
    parser.add_argument("--id", dest="task_id", help="nur diese Aufgabe")
    parser.add_argument("--golden", default=str(DEFAULT_GOLDEN))
    parser.add_argument("--json", metavar="PFAD", help="Report als JSON schreiben")
    args = parser.parse_args()

    if args.compare:
        if args.json:
            parser.error("--compare erzeugt keinen neuen Report; --json hier nicht verwenden")
        try:
            left = json.loads(Path(args.compare[0]).read_text(encoding="utf-8"))
            right = json.loads(Path(args.compare[1]).read_text(encoding="utf-8"))
            comparison = compare_reports(left, right)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"  Vergleich nicht möglich: {exc}")
            return 2
        print_comparison(comparison)
        return 0

    if args.all_suites and not args.dry_run:
        parser.error("--all-suites ist nur mit --dry-run sinnvoll")
    if args.suite and args.all_suites:
        parser.error("--suite und --all-suites schließen sich aus")
    if args.suite and args.golden != str(DEFAULT_GOLDEN):
        parser.error("--suite und --golden schließen sich aus")
    if args.model and not args.live:
        parser.error("--model ist nur für --live sinnvoll")

    roles = load_roles()
    if args.all_suites:
        return run_all_suites(roles, args.json)

    golden_path = Path(args.golden)
    if args.suite:
        golden_path = ROLE_DIR / f"{args.suite}.json"
    golden = load_golden(golden_path)
    tasks = select_tasks(golden, args.role, args.task_id)
    if not tasks:
        print(f"Keine Aufgabe passt zum Filter (role={args.role}, id={args.task_id}).")
        return 2

    if args.dry_run:
        report = run_dry(tasks, StubBackend(roles))
    else:
        report = run_live(tasks, LiveBackend(args.url, roles, args.timeout, args.model))
        report["resource_snapshot"] = resource_snapshot()

    report["generated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report["revision"] = git_revision()
    report["golden"] = display_path(golden_path)
    report["configuration"] = {
        "golden": display_path(golden_path),
        "role_filter": args.role,
        "task_id": args.task_id,
        "model": args.model,
        "url": args.url if args.live else None,
    }
    report["summary"] = summarize(report)

    print_report(report)

    if args.json:
        path = Path(args.json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print(f"\n  Report geschrieben: {path}")

    if args.dry_run:
        return 0 if report["summary"]["ok"] else 1
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
