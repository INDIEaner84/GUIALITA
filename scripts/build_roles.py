#!/usr/bin/env python3
"""Erzeugt die YAML-Spiegelung der Rollen-Registry (ADR-002, D2 / P5).

ADR-002 verlangt eine versionierte YAML-Datei. Die Werkzeuge selbst lesen
``config/roles.json``, weil dieses Repo auch ohne PyYAML prüfbar bleiben soll.
Das ist kein Widerspruch, sondern eine bewusst zweigeteilte Darstellung:

* ``config/roles.json`` — maschinelle Quelle, ohne externe Abhängigkeit lesbar.
* ``config/roles.yaml`` — generierte, menschenlesbare ADR-konforme Ansicht.
* ``--check`` — verhindert, dass beide auseinanderlaufen.

Die YAML-Ausgabe nutzt ausschließlich eine kleine, eindeutige Teilmenge:
Skalare, doppelt quotierte Strings, Flow-Listen und ``true``/``false``.
Damit ist sie ohne YAML-Parser erzeugbar und mit jedem YAML-Parser lesbar.

Nutzung
-------
    python3 scripts/build_roles.py --check
    python3 scripts/build_roles.py --write
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "config" / "roles.json"
MIRROR = ROOT / "config" / "roles.yaml"

HEADER = (
    "# GUIALITA — Rollen-Registry, lesbare Spiegelung von config/roles.json\n"
    "#\n"
    "# GENERIERT. Nicht von Hand editieren.\n"
    "# Quelle: config/roles.json\n"
    "# Prüfung: python3 scripts/build_roles.py --check\n"
    "# ADR: docs/adr/ADR-002-agent-orchestration.md, Entscheidung D2\n"
    "#\n"
)


def load_config(path: Path = SOURCE) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def quote(value) -> str:
    """YAML-doppeltquotiert, über json.dumps — auch für Umlaute und Zeilenumbrüche."""
    return json.dumps(str(value), ensure_ascii=False)


def flow(values) -> str:
    return "[" + ", ".join(quote(v) for v in values) + "]"


def render(config: dict) -> str:
    lines = [HEADER.rstrip("\n")]
    lines.append(f"generated_by: {quote('scripts/build_roles.py')}")
    lines.append(f"source: {quote('config/roles.json')}")
    lines.append(f"schema: {int(config.get('schema', 1))}")
    lines.append(f"yaml_mirror: {quote('config/roles.yaml')}")
    lines.append("do_not_edit:")
    for line in [
        "Diese Datei ist generiert. config/roles.json aendern und",
        "python3 scripts/build_roles.py --write ausfuehren.",
    ]:
        lines.append(f"  - {quote(line)}")
    lines.append("note:")
    for line in config.get("note", []):
        lines.append(f"  - {quote(line)}")

    lines.append("tools:")
    for name, meta in (config.get("tools") or {}).items():
        lines.append(f"  {name}:")
        lines.append(f"    mutating: {'true' if meta.get('mutating') else 'false'}")
        lines.append(f"    description: {quote(meta.get('description', ''))}")

    lines.append("roles:")
    for name, role in (config.get("roles") or {}).items():
        lines.append(f"  {name}:")
        for key in ("description", "model", "prompt", "output_schema", "eval"):
            lines.append(f"    {key}: {quote(role.get(key, ''))}")
        lines.append(f"    tools: {flow(role.get('tools', []))}")
        lines.append(f"    timeout_ms: {int(role.get('timeout_ms', 0))}")
        if "max_tokens" in role:
            lines.append(f"    max_tokens: {int(role['max_tokens'])}")
        lines.append("    requires_approval: "
                     f"{'true' if role.get('requires_approval') else 'false'}")
        lines.append(f"    eval_roles: {flow(role.get('eval_roles', [name]))}")
    return "\n".join(lines) + "\n"


def check(root: Path = ROOT) -> list[str]:
    try:
        expected = render(load_config(root / "config" / "roles.json"))
        actual = (root / "config" / "roles.yaml").read_text(encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"Rollen-Mirror nicht prüfbar: {exc}"]
    if actual != expected:
        return ["config/roles.yaml weicht von config/roles.json ab"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="YAML-Mirror der Rollen-Registry prüfen.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="nur prüfen (Standard)")
    mode.add_argument("--write", action="store_true", help="config/roles.yaml neu schreiben")
    args = parser.parse_args()

    config = load_config()
    if args.write:
        MIRROR.write_text(render(config), encoding="utf-8")
        print(f"  Geschrieben: {MIRROR.relative_to(ROOT)} "
              f"({len(config.get('roles', {}))} Rollen)")
        return 0

    problems = check()
    if problems:
        for problem in problems:
            print(f"  FEHLER  {problem}")
        print("  Abhilfe: python3 scripts/build_roles.py --write")
        return 1
    print(f"  OK — config/roles.yaml entspricht config/roles.json "
          f"({len(config.get('roles', {}))} Rollen)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
