#!/usr/bin/env python3
"""Small repeatable latency benchmark for the local GUIALITA stack.

By default this only measures deterministic local operations. ``--live`` measures
an already running backend and never starts or stops services.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.request
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def measure(label, fn, repetitions=5):
    values = []
    for _ in range(repetitions):
        started = time.perf_counter()
        fn()
        values.append((time.perf_counter() - started) * 1000)
    print(f"{label}: median={statistics.median(values):.2f} ms, "
          f"min={min(values):.2f} ms, max={max(values):.2f} ms")


def live_request(url, method="GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    if data:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="measure running backend health")
    parser.add_argument("--url", default="http://localhost:8080", help="backend base URL")
    args = parser.parse_args()

    from backend.memory.embed import embed

    print("GUIALITA benchmark")
    measure("memory.embed", lambda: embed("Wie heißt mein Projekt?"))
    if args.live:
        measure("GET /health", lambda: live_request(args.url + "/health"))
        print("Live chat is intentionally not run automatically because it loads a model and costs inference time.")


if __name__ == "__main__":
    main()
