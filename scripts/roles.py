#!/usr/bin/env python3
"""GUIALITA — Rollen-Registry prüfen und anzeigen (ADR-002, D2 / P5).

Eine Rolle ist Konfiguration, kein Gewicht: Prompt, Tool-Allowlist, Modell,
Limits, Eval-Suite. Dieses Skript prüft, dass die Konfiguration in sich stimmt,
**bevor** eine Orchestrierung sie benutzt.

Die Invariante, die den Aufwand rechtfertigt
--------------------------------------------
Ein Auditor ohne Schreibrecht ist kein Auditor, sondern ein zweiter Coder. Die
Prüfung erzwingt:

* Rollen mit ``audit`` im Namen dürfen kein mutierendes Tool haben.
* Ein mutierendes Tool setzt ``requires_approval: true`` voraus.
* Jede Rolle verweist auf eine existierende Eval-Suite und ein Modell, das
  wirklich in ``config/models.yaml`` steht.
* ``config/roles.yaml`` (ADR-002 D2) bleibt mit ``config/roles.json`` synchron.
* Ein Rollenwechsel ohne Modellwechsel wird als solcher ausgewiesen — nicht als
  kostenlose Nebensächlichkeit, sondern als der Normalfall, den D3 anstrebt.

Nutzung
-------
    python3 scripts/roles.py list
    python3 scripts/roles.py show auditor
    python3 scripts/roles.py suites
    python3 scripts/roles.py switch router planner
    python3 scripts/roles.py validate        # Exitcode 1 bei Fehlern
    python3 scripts/roles.py mirror         # JSON ↔ YAML abgleichen
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLES_FILE = ROOT / "config" / "roles.json"
MODELS_FILE = ROOT / "config" / "models.yaml"

REQUIRED_FIELDS = ("description", "model", "prompt", "tools", "output_schema",
                   "timeout_ms", "eval")
MIN_TIMEOUT_MS = 1000
MAX_TIMEOUT_MS = 600_000
MIN_PROMPT_CHARS = 20


# ----------------------------------------------------------------------------
# Modelle aus models.yaml lesen
# ----------------------------------------------------------------------------
def model_ids(path: Path = MODELS_FILE) -> list[str]:
    """Liest die Modell-IDs aus ``config/models.yaml``.

    Bewusst ein toleranter Zeilenleser statt eines YAML-Parsers: dieses Skript
    soll auch dort laufen, wo PyYAML fehlt. Erkannt wird der Block ``models:``
    mit seinen direkt eingerückten Schlüsseln. Ändert sich die Struktur,
    liefert die Funktion weniger IDs — und ``validate`` schlägt fehl, statt
    still zu raten. Punkte im Schlüssel sind erlaubt: ``lfm-vision-1.6b``
    ist ein gültiger Modellname und wurde von einer früheren Fassung
    verschluckt.
    """
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    ids: list[str] = []
    in_models = False
    for line in lines:
        if re.match(r"^models:\s*$", line):
            in_models = True
            continue
        if not in_models:
            continue
        if line and not line.startswith(" "):
            break  # nächster Top-Level-Block
        entry = re.match(r"^ {2}([A-Za-z0-9][A-Za-z0-9._-]*):\s*$", line)
        if entry:
            ids.append(entry.group(1))
    return ids


def load_roles(path: Path = ROLES_FILE) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# ----------------------------------------------------------------------------
# Validierung
# ----------------------------------------------------------------------------
def check_eval_suite(name: str, role: dict, root: Path = ROOT) -> list[str]:
    """Prüft eine Rollen-Eval-Suite, ohne eval.py oder einen YAML-Parser zu brauchen."""
    problems: list[str] = []
    suite_path = Path(str(role["eval"]))
    if not suite_path.is_absolute():
        suite_path = root / suite_path
    try:
        with suite_path.open(encoding="utf-8") as handle:
            suite = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{name}: Eval-Suite nicht lesbar ({role['eval']}): {exc}"]

    tasks = suite.get("tasks") or []
    if not tasks:
        problems.append(f"{name}: Eval-Suite ohne Aufgaben: {role['eval']}")
        return problems

    allowed = set(role.get("eval_roles") or [name])
    suite_role = suite.get("role")
    if suite_role and suite_role not in allowed:
        problems.append(f"{name}: Eval-Suite nennt role='{suite_role}', "
                        f"erlaubt ist {sorted(allowed)}")
    if suite_role:
        seen = set()
        for task in tasks:
            if task.get("role") not in allowed:
                problems.append(f"{name}: Aufgabe {task.get('id', '?')} hat "
                                f"role='{task.get('role')}'")
            if task.get("id") in seen:
                problems.append(f"{name}: doppelte Aufgaben-ID {task.get('id')}")
            seen.add(task.get("id"))
        if not any(t.get("stub", {}).get("outcome") == "fail" for t in tasks):
            problems.append(f"{name}: Eval-Suite ohne negative Kontrolle")
    return problems


def validate(config: dict, known_models: list[str] | None = None,
             root: Path = ROOT) -> list[str]:
    """Prüft die Rollenkonfiguration. Gibt eine Liste von Fehlern zurück.

    Leere Liste heißt: in sich stimmig. Es heißt nicht, dass die Rollen
    funktionieren — dafür ist die Eval-Suite da.
    """
    problems: list[str] = []
    roles = config.get("roles") or {}
    tools = config.get("tools") or {}
    models = known_models if known_models is not None else model_ids()

    if not roles:
        return ["keine Rollen definiert"]
    if not tools:
        problems.append("kein Tool-Verzeichnis definiert")

    mutating = {name for name, meta in tools.items() if meta.get("mutating")}

    for name, role in roles.items():
        # Fehlende Pflichtfelder pro Rolle prüfen, nicht global. Eine frühe
        # Fassung brach hier bei der ersten beschädigten Rolle ab und
        # übersprang dadurch alle folgenden — genau die falsche Richtung.
        missing = [field for field in REQUIRED_FIELDS if field not in role]
        if missing:
            for field in missing:
                problems.append(f"{name}: Pflichtfeld fehlt: {field}")
            continue

        if role["model"] not in models:
            problems.append(f"{name}: Modell '{role['model']}' steht nicht in "
                            f"config/models.yaml ({', '.join(models) or 'keine gefunden'})")

        if not isinstance(role["tools"], list):
            problems.append(f"{name}: tools muss eine Liste sein")
            role_tools = []
        else:
            role_tools = role["tools"]
        unknown_tools = [t for t in role_tools if t not in tools]
        if unknown_tools:
            problems.append(f"{name}: unbekannte Tools {unknown_tools}")

        if not str(role["prompt"]).strip():
            problems.append(f"{name}: Prompt ist leer")
        elif len(str(role["prompt"]).strip()) < MIN_PROMPT_CHARS:
            problems.append(f"{name}: Prompt kürzer als {MIN_PROMPT_CHARS} Zeichen")

        timeout = role["timeout_ms"]
        if not isinstance(timeout, int) or not MIN_TIMEOUT_MS <= timeout <= MAX_TIMEOUT_MS:
            problems.append(f"{name}: timeout_ms außerhalb "
                            f"{MIN_TIMEOUT_MS}–{MAX_TIMEOUT_MS}: {timeout}")

        eval_path = Path(str(role["eval"]))
        if not eval_path.is_absolute():
            eval_path = root / eval_path
        if not eval_path.is_file():
            problems.append(f"{name}: Eval-Suite fehlt: {role['eval']}")
        else:
            problems.extend(check_eval_suite(name, role, root))

        for other in role.get("eval_roles", []):
            if other not in roles:
                problems.append(f"{name}: eval_roles nennt unbekannte Rolle '{other}'")

        # Invariante 1: ein Auditor schreibt nicht.
        if "audit" in name.lower():
            offenders = [t for t in role_tools if t in mutating]
            if offenders:
                problems.append(f"{name}: Rolle mit Audit-Aufgabe hat mutierende "
                                f"Tools {offenders} — ein Auditor ändert nichts")

        # Invariante 2: mutierendes Tool braucht Freigabe.
        if any(t in mutating for t in role_tools) and not role.get("requires_approval"):
            problems.append(f"{name}: mutierendes Tool ohne requires_approval")

    return problems


def check_mirror(root: Path = ROOT) -> list[str]:
    """JSON-Quelle und YAML-Mirror abgleichen (delegiert an build_roles)."""
    try:
        import build_roles  # liegt im selben scripts/-Verzeichnis
    except ImportError as exc:
        return [f"build_roles nicht importierbar: {exc}"]
    return build_roles.check(root)


# ----------------------------------------------------------------------------
# Rollenwechsel
# ----------------------------------------------------------------------------
def role_switch(from_role: str, to_role: str, config: dict) -> dict:
    """Beschreibt einen Rollenwechsel — insbesondere, ob ein Modellwechsel nötig ist.

    Diese Funktion misst nichts und lädt nichts. Sie beantwortet nur die Frage,
    die ADR-002 D3 vor jede Orchestrierung stellt: bleibt dieselbe Instanz
    liegen, oder wird ein neues Gewicht gebraucht? Die tatsächlichen Kosten
    misst ``scripts/modelsctl.py switch`` auf der Referenzmaschine.
    """
    roles = config.get("roles") or {}
    missing = [name for name in (from_role, to_role) if name not in roles]
    if missing:
        raise ValueError(f"unbekannte Rolle(n): {', '.join(missing)}")
    source, target = roles[from_role], roles[to_role]
    from_model, to_model = source.get("model"), target.get("model")
    requires_approval = bool(target.get("requires_approval"))
    return {
        "from": from_role,
        "to": to_role,
        "from_model": from_model,
        "to_model": to_model,
        "model_switch": from_model != to_model,
        "requires_approval": requires_approval,
        "shared_instance": from_model == to_model,
        "measured_switch_ms": None,
        "note": ("Beide Rollen teilen sich dieselbe Modellinstanz — kein "
                 "Modellwechsel, keine Ladezeit."
                 if from_model == to_model else
                 "Modellwechsel nötig. Wechselzeit ist eine Messgröße, keine "
                 "Konstante; siehe scripts/modelsctl.py switch."),
    }


# ----------------------------------------------------------------------------
# Ausgabe
# ----------------------------------------------------------------------------
def print_list(config: dict) -> None:
    roles = config.get("roles") or {}
    tools = config.get("tools") or {}
    print(f"\n  {'Rolle':<12}{'Modell':<14}{'Tools':<34}{'Timeout':>9}")
    print("  " + "-" * 70)
    for name, role in roles.items():
        tool_text = ", ".join(role["tools"]) or "—"
        print(f"  {name:<12}{role['model']:<14}{tool_text[:33]:<34}"
              f"{role['timeout_ms']:>7} ms")
    print(f"\n  {len(roles)} Rollen, {len(tools)} Tools "
          f"({sum(1 for t in tools.values() if t.get('mutating'))} mutierend)")


def print_role(name: str, role: dict) -> None:
    print(f"\n  {name}")
    print("  " + "-" * 70)
    for key in ("description", "model", "output_schema", "timeout_ms",
                "max_tokens", "requires_approval", "eval", "eval_roles"):
        if key in role:
            print(f"  {key:<18}{role[key]}")
    print(f"  {'tools':<18}{', '.join(role['tools']) or '—'}")
    print(f"  {'prompt':<18}")
    for line in str(role["prompt"]).splitlines():
        print(f"      {line}")


def print_suites(config: dict, root: Path = ROOT) -> int:
    roles = config.get("roles") or {}
    print(f"\n  {'Rolle':<12}{'Suite':<28}{'Aufgaben':>9}{'Negativ':>9}")
    print("  " + "-" * 60)
    ok = True
    for name, role in roles.items():
        path = Path(str(role["eval"]))
        if not path.is_absolute():
            path = root / path
        try:
            with path.open(encoding="utf-8") as handle:
                suite = json.load(handle)
            tasks = suite.get("tasks") or []
            negatives = sum(1 for t in tasks
                            if t.get("stub", {}).get("outcome") == "fail")
            print(f"  {name:<12}{role['eval']:<28}{len(tasks):>9}{negatives:>9}")
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  {name:<12}{role['eval']:<28}{'FEHLER':>18}  {exc}")
            ok = False
    return 0 if ok else 1


def print_switch(result: dict) -> None:
    print()
    print("=" * 78)
    print("  Rollenwechsel")
    print("=" * 78)
    print(f"  {result['from']} → {result['to']}")
    print(f"  Modell : {result['from_model']} → {result['to_model']}")
    print(f"  Urteil : {'MODELLWECHSEL NÖTIG' if result['model_switch'] else 'kein Modellwechsel'}")
    print(f"  Freigabe für Zielrolle: {'ja' if result['requires_approval'] else 'nein'}")
    print(f"  {result['note']}")
    print("  Gemessene Wechselzeit: — (nur auf der Referenzmaschine)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rollen-Registry prüfen.")
    parser.add_argument("--roles", default=str(ROLES_FILE))
    parser.add_argument("--models", default=str(MODELS_FILE))
    parser.add_argument("--root", default=str(ROOT))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="alle Rollen anzeigen")
    show = sub.add_parser("show", help="eine Rolle im Detail")
    show.add_argument("role")
    sub.add_parser("suites", help="Eval-Suiten je Rolle anzeigen")
    switch = sub.add_parser("switch", help="Rollenwechsel auf Modellwechsel prüfen")
    switch.add_argument("from_role")
    switch.add_argument("to_role")
    validate_parser = sub.add_parser("validate", help="Konfiguration prüfen")
    validate_parser.add_argument("--check-mirror", action="store_true",
                                 help="zusätzlich JSON ↔ YAML abgleichen")
    sub.add_parser("mirror", help="nur JSON ↔ YAML abgleichen")
    args = parser.parse_args()

    root = Path(args.root)
    try:
        config = load_roles(Path(args.roles))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  Rollen nicht lesbar: {exc}")
        return 2

    if args.command == "list":
        print_list(config)
        return 0

    if args.command == "show":
        roles = config.get("roles") or {}
        if args.role not in roles:
            print(f"  Unbekannte Rolle: {args.role}")
            return 2
        print_role(args.role, roles[args.role])
        return 0

    if args.command == "suites":
        return print_suites(config, root)

    if args.command == "switch":
        try:
            result = role_switch(args.from_role, args.to_role, config)
        except ValueError as exc:
            print(f"  {exc}")
            return 2
        print_switch(result)
        return 0

    if args.command == "mirror":
        problems = check_mirror(root)
        if problems:
            for problem in problems:
                print(f"  FEHLER  {problem}")
            return 1
        print(f"  OK — config/roles.yaml entspricht config/roles.json")
        return 0

    known = model_ids(Path(args.models))
    problems = validate(config, known, root)
    if args.check_mirror:
        problems.extend(check_mirror(root))
    print()
    print("=" * 78)
    print("  Rollen-Validierung")
    print("=" * 78)
    print(f"  Modelle in config/models.yaml: {', '.join(known) or 'KEINE GEFUNDEN'}")
    if problems:
        for problem in problems:
            print(f"  FEHLER  {problem}")
        print(f"\n  {len(problems)} Problem(e).")
        return 1
    print(f"\n  OK — {len(config.get('roles', {}))} Rollen konsistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
