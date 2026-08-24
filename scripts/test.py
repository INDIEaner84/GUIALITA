#!/usr/bin/env python3
"""Run GUIALITA tests in useful, explicit layers.

Default mode is safe on a fresh checkout and never needs a running backend.
Use --live only when the local backend and external runtimes are ready.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTEST = [sys.executable, "-m", "pytest", "-q", "--tb=short"]

UNIT = [
    "tests/test_chat_service.py",
    "tests/test_audit.py",
    "tests/test_audio_contract.py",
    "tests/test_memory.py::TestStoreUnit",
    "tests/test_memory_graph.py::TestGraphStore",
    "tests/test_memory_graph.py::TestExtractor",
    "tests/test_memory_graph.py::TestGraphRetrieval",
    "tests/test_memory_retrieval.py::TestEmbedding",
    "tests/test_memory_retrieval.py::TestMemoryStoreRetrieval",
    "tests/test_process_audio.py::TestFilenameSafety",
]

LIVE = [
    "tests/test_api.py",
    "tests/test_memory.py::TestMemoryAPI",
    "tests/test_memory_retrieval.py::TestRetrievalAPI",
    "tests/test_memory_graph.py::TestGraphAPI",
    "tests/test_graph_visualization.py::TestGraphVisualizationAPI",
    "tests/test_tts.py::TestTTSService",
    "tests/test_voice_activation.py",
]


def run(label: str, paths: list[str]) -> int:
    print(f"\n=== {label} ===")
    result = subprocess.run(PYTEST + paths, cwd=ROOT)
    if result.returncode == 0:
        print(f"{label}: PASS")
    else:
        print(f"{label}: BLOCKED/FAIL (exit {result.returncode})")
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="also run backend/runtime tests")
    args = parser.parse_args()

    unit_rc = run("UNIT", UNIT)
    if not args.live:
        print("\nOverall: PASS (unit layer only; use --live for runtime tests)")
        return unit_rc

    live_rc = run("LIVE", LIVE)
    return 1 if unit_rc or live_rc else 0


if __name__ == "__main__":
    raise SystemExit(main())
