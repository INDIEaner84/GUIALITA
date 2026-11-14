#!/usr/bin/env python3
"""Prüft die kanonischen Zahlen und Grenzen über die aktuellen Dokumente hinweg.

Warum es dieses Skript gibt
---------------------------
``run_all_tests.py --check-state`` gleicht nur Runner und SSOT ab. Die
Erfahrung in diesem Repo war aber, dass dieselbe Zahl anschließend in einem
Bootstrap, einem Regression Contract, einem ADR und einem Session-Log
weiterlebte — halb korrigiert, halb historisch. Dieses Skript prüft die
**aktuellen** Formulierungen und lässt historische Korrekturabschnitte
ausdrücklich stehen, sofern sie als überholt markiert sind.

Zusätzlich werden die generierten Artefakte geprüft:
``evals/golden.json`` ↔ Rollen-Suiten, ``config/roles.yaml`` ↔ JSON-Quelle.

Nutzung
-------
    python3 scripts/check_docs.py
    python3 scripts/check_docs.py --root /pfad/zu/GUIALITA
"""

from __future__ import annotations

import argparse
import importlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CURRENT_FILES = (
    "docs/GUIALITA_STATE.yaml",
    "docs/BASELINES/REGRESSION_CONTRACT.md",
    "docs/GUIALITA_SESSION_BOOTSTRAP.md",
    "docs/adr/ADR-002-agent-orchestration.md",
    "docs/SESSION_LOG.md",
    "docs/HEARTBEAT.md",
    "docs/SINGLE_SOURCE_OF_TRUTH.md",
    "docs/GUIALITA_PHASE_STATUS.md",
    "docs/LFM25_AUDIO_AUDIT.md",
    "docs/LFM25_AUDIO_AUDIT_V2.md",
    "PROTOTYPEN/README.md",
    "README.md",
    ".github/workflows/state-consistency.yml",
)

# Historische Zahlen bleiben in Korrekturabschnitten erlaubt. Verboten sind
# nur Formulierungen, die sich als *aktuell* lesen.
FORBIDDEN_CURRENT = (
    "136 Testfunktionen in 9 Suiten",
    "136 Tests, 9 Suiten",
    "141 -> 167 Funktionen",
    "9 -> 12 Suiten",
    "Maßgeblich sind jetzt **177 Testfunktionen in 13 Suiten**",
    "8 von 13 Testsuiten benötigen",
    "Acht von dreizehn Suiten benötigen",
    "fünf Suiten — test_benchmark.py",
    "**Status**: PROPOSED — **nicht autorisiert, nicht implementiert**",
    "Nichts davon ist implementiert; es ist ausschließlich Zielbild, kein Zustand.",
    "P3–P6 offen und weiterhin freigabepflichtig",
    "Bleiben freigabepflichtig; `prohibitions` unverändert.",
    "keine MUSCAL-Schichten",
    "141 Tests über neun Suiten",
    "Acht der neun Testsuiten",
    "Aktueller Status — 2026-08-22",
    "PASS — 39 Tests über scripts/test.py",
    "## Nächste Milestones",
    "Freigabe für P3–P6 (neue Schichten) steht aus.",
    "MUSCAL ist `future_target: PLANNED`",
    "Aktueller Stand: Voice Activation V1",
    "Voraussetzung: Backend läuft.",
    "## Phasenplan",
)

REQUIRED_INVARIANTS = (
    "hard_stop: true",
    "next_authorized_phase: NONE",
    '"MUSCAL-Adapter, Vision, Desktop-/Browser-Control, WebSocket, Multi-Agent"',
    '"Cloud-STT/TTS oder Cloud-Inferenz"',
)


def normalize(text: str) -> str:
    """Whitespace normalisieren, damit Zeilenumbrüche keine Prüfung umgehen."""
    return re.sub(r"\s+", " ", text).strip()


def forbidden_in(text: str) -> list[str]:
    haystack = normalize(text)
    return [phrase for phrase in FORBIDDEN_CURRENT
            if normalize(phrase) in haystack]


def read_numbers(root: Path = ROOT) -> tuple[int, int]:
    state = (root / "docs" / "GUIALITA_STATE.yaml").read_text(encoding="utf-8")
    total = re.search(r"^  test_functions_total:\s*(\d+)", state, re.MULTILINE)
    suites = re.search(r"^  suites:\s*(\d+)", state, re.MULTILINE)
    if not total or not suites:
        raise ValueError("test_functions_total oder suites fehlt in der SSOT")
    return int(total.group(1)), int(suites.group(1))


def required_phrases(total: int, suites: int, root: Path = ROOT) -> dict[str, list[str]]:
    number_phrase = f"**{total} Testfunktionen in {suites} Suiten**"
    return {
        "docs/GUIALITA_STATE.yaml": [
            f"test_functions_total: {total}",
            f"suites: {suites}",
            f"8 von {suites} Testsuiten benötigen",
            f"**{total} Testfunktionen in {suites} Suiten**",
        ],
        "docs/BASELINES/REGRESSION_CONTRACT.md": [
            f"| **Summe** | **{total}** |",
            f"Maßgeblich sind jetzt {number_phrase}",
        ],
        "docs/GUIALITA_SESSION_BOOTSTRAP.md": [
            number_phrase,
            "8 davon brauchen Backend",
        ],
        "docs/adr/ADR-002-agent-orchestration.md": [
            number_phrase,
            "P3–P6 als CLI/HTTP-Werkzeuge umgesetzt",
        ],
        "docs/SESSION_LOG.md": [
            number_phrase,
            "P3–P6 umgesetzt",
            "Live-Abnahme",
        ],
        "docs/HEARTBEAT.md": [
            number_phrase,
            "Aktueller Stand — 2026-11-13",
            "7 PASS, 12 NOT EXECUTED, 0 FAIL",
        ],
        "docs/SINGLE_SOURCE_OF_TRUTH.md": [
            "ADR-002-Werkzeuge",
            "docs/GUIALITA_STATE.yaml",
        ],
        "docs/GUIALITA_PHASE_STATUS.md": [
            "ADR-002: Agenten-Orchestrierung",
        ],
        "docs/LFM25_AUDIO_AUDIT.md": [
            "Historischer Beleg",
            "docs/GUIALITA_STATE.yaml",
        ],
        "docs/LFM25_AUDIO_AUDIT_V2.md": [
            "Historischer Beleg",
            "docs/GUIALITA_STATE.yaml",
        ],
        "PROTOTYPEN/README.md": [
            "NICHT ANGEBUNDEN",
            "maßgebliche Zustand",
        ],
        "README.md": [
            number_phrase,
            "Maßgeblicher",
            "Historischer Phasenplan (kein Status)",
        ],
        ".github/workflows/state-consistency.yml": [
            "python3 scripts/check_docs.py",
            "python3 scripts/contract_check.py",
        ],
    }


def check_required_phrases(root: Path = ROOT) -> list[str]:
    try:
        total, suites = read_numbers(root)
    except (OSError, ValueError) as exc:
        return [f"SSOT nicht lesbar: {exc}"]
    problems = []
    for relative, needles in required_phrases(total, suites, root).items():
        path = root / relative
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            problems.append(f"{relative}: nicht lesbar ({exc})")
            continue
        for needle in needles:
            if needle not in text:
                problems.append(f"{relative}: aktuelle Formulierung fehlt: {needle}")
    return problems


def check_invariants(root: Path = ROOT) -> list[str]:
    try:
        state = (root / "docs" / "GUIALITA_STATE.yaml").read_text(encoding="utf-8")
    except OSError as exc:
        return [f"SSOT nicht lesbar: {exc}"]
    return [f"SSOT-Invariante fehlt: {needle}"
            for needle in REQUIRED_INVARIANTS if needle not in state]


def check_generated(root: Path = ROOT) -> list[str]:
    problems = []
    for module_name in ("build_golden", "build_roles"):
        try:
            module = importlib.import_module(module_name)
            problems.extend(module.check(root))
        except (ImportError, AttributeError) as exc:
            problems.append(f"{module_name} nicht prüfbar: {exc}")
    return problems


def run_checks(root: Path = ROOT) -> list[str]:
    problems = check_required_phrases(root)
    problems.extend(check_invariants(root))
    for relative in CURRENT_FILES:
        path = root / relative
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue  # fehlende Datei meldet check_required_phrases bereits
        for phrase in forbidden_in(text):
            problems.append(f"{relative}: veraltete Aktualitätsbehauptung: {phrase}")
    problems.extend(check_generated(root))
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Dokumenten-Konsistenz prüfen.")
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()
    root = Path(args.root)
    problems = run_checks(root)
    print()
    print("=" * 78)
    print("  Dokumenten-Konsistenz")
    print("=" * 78)
    if problems:
        for problem in problems:
            print(f"  FEHLER  {problem}")
        print(f"\n  {len(problems)} Problem(e).")
        return 1
    try:
        total, suites = read_numbers(root)
        print(f"  OK — {total} Testfunktionen in {suites} Suiten, "
              f"Grenzen und generierte Artefakte konsistent")
    except (OSError, ValueError):
        print("  OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
