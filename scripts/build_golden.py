#!/usr/bin/env python3
"""Baut das aggregierte Golden Set aus den Rollen-Suiten (ADR-002, D1/P3/P5).

Warum ein Generator
-------------------
Vier Rollen, vier Eval-Suiten und ein Gesamtset von Hand zu pflegen ist eine
Einladung zu genau der Art Widerspruch, die dieses Projekt schon bei den
Testzahlen teuer bezahlt hat. Deshalb gilt:

* `evals/roles/<rolle>.json` ist die Quelle.
* `evals/golden.json` ist **generiert** und wird nicht von Hand editiert.
* `--check` vergleicht beides und scheitert, sobald jemand nur eine Seite
  ändert. CI ruft diesen Modus auf.

Nutzung
-------
    python3 scripts/build_golden.py --check
    python3 scripts/build_golden.py --write
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLE_DIR = ROOT / "evals" / "roles"
GOLDEN = ROOT / "evals" / "golden.json"
SUITE_ORDER = ("router", "planner", "coder", "auditor")
GRADERS = ("equals", "one_of", "contains", "must_not_contain", "regex",
           "json_keys", "one_of_field", "min_list_len", "non_empty",
           "max_latency_ms")


def load_suite(role: str, root: Path = ROOT) -> dict:
    path = root / "evals" / "roles" / f"{role}.json"
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if data.get("role") != role:
        raise ValueError(f"{path.name}: role='{data.get('role')}', erwartet '{role}'")
    tasks = data.get("tasks") or []
    if not tasks:
        raise ValueError(f"{path.name}: keine Aufgaben")
    ids = set()
    for task in tasks:
        for key in ("id", "role", "prompt", "expect", "stub"):
            if key not in task:
                raise ValueError(f"{path.name}: Aufgabe ohne '{key}': {task.get('id', '?')}")
        if task["role"] != role:
            raise ValueError(f"{path.name}: Aufgabe {task['id']} hat role='{task['role']}'")
        if task["id"] in ids:
            raise ValueError(f"{path.name}: doppelte ID {task['id']}")
        ids.add(task["id"])
        if task["stub"].get("outcome") not in ("pass", "fail"):
            raise ValueError(f"{path.name}: stub.outcome muss pass|fail sein: {task['id']}")
    return data


def build_golden(root: Path = ROOT) -> dict:
    suites = {role: load_suite(role, root) for role in SUITE_ORDER}
    tasks = []
    seen = set()
    for role in SUITE_ORDER:
        for task in suites[role]["tasks"]:
            if task["id"] in seen:
                raise ValueError(f"Aufgaben-ID {task['id']} kommt in mehreren Suiten vor")
            seen.add(task["id"])
            tasks.append(task)
    negatives = [t for t in tasks if t["stub"]["outcome"] == "fail"]
    return {
        "schema": 1,
        "version": 1,
        "generated_by": "scripts/build_golden.py",
        "generated_from": [f"evals/roles/{role}.json" for role in SUITE_ORDER],
        "do_not_edit": [
            "Diese Datei ist generiert. Bitte evals/roles/<rolle>.json aendern",
            "und 'python3 scripts/build_golden.py --write' ausfuehren."
        ],
        "note": [
            "Golden Set fuer das Eval-Harness (ADR-002, D1/P3).",
            "",
            "Jede Aufgabe hat zwei Zwecke: sie bewertet ein echtes Modell",
            "(--live) und testet das Harness selbst (--dry-run). Negative",
            "Kontrollen muessen absichtlich als FAIL enden; ein Harness, das",
            "nur zustimmen kann, misst nichts.",
            "",
            "Die vier Rollen-Suiten sind die Quelle. Der Generator verhindert,",
            "dass Gesamtset und Rollensuiten auseinanderlaufen."
        ],
        "graders": list(GRADERS),
        "task_count": len(tasks),
        "negative_controls": len(negatives),
        "tasks": tasks,
    }


def check(root: Path = ROOT) -> list[str]:
    try:
        expected = build_golden(root)
        path = root / "evals" / "golden.json"
        with path.open(encoding="utf-8") as handle:
            actual = json.load(handle)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"Golden Set nicht prüfbar: {exc}"]

    problems = []
    if actual.get("tasks") != expected["tasks"]:
        problems.append("evals/golden.json weicht von den Rollen-Suiten ab")
    for key in ("generated_by", "generated_from", "graders", "task_count",
                "negative_controls", "do_not_edit"):
        if actual.get(key) != expected[key]:
            problems.append(f"evals/golden.json: Feld '{key}' ist veraltet")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Golden Set aus Rollen-Suiten erzeugen/prüfen.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="nur prüfen (Standard)")
    mode.add_argument("--write", action="store_true", help="evals/golden.json neu schreiben")
    args = parser.parse_args()

    if args.write:
        golden = build_golden()
        GOLDEN.write_text(json.dumps(golden, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
        print(f"  Geschrieben: {GOLDEN.relative_to(ROOT)} "
              f"({golden['task_count']} Aufgaben, "
              f"{golden['negative_controls']} negative Kontrollen)")
        return 0

    problems = check()
    if problems:
        for problem in problems:
            print(f"  FEHLER  {problem}")
        print("  Abhilfe: python3 scripts/build_golden.py --write")
        return 1
    golden = build_golden()
    print(f"  OK — evals/golden.json entspricht den Rollen-Suiten "
          f"({golden['task_count']} Aufgaben, "
          f"{golden['negative_controls']} negative Kontrollen)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
