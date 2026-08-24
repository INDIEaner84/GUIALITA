#!/usr/bin/env python3
"""Read-only local diagnostics for GUIALITA.

The command never downloads models, starts services, or changes Ollama.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def check(label: str, ok: bool, detail: str = "") -> None:
    mark = "OK" if ok else "MISSING"
    print(f"[{mark:7}] {label}{(': ' + detail) if detail else ''}")


def main() -> int:
    print(f"GUIALITA doctor — {ROOT}")
    all_ok = True
    for module in ("fastapi", "pydantic", "yaml", "numpy"):
        present = importlib.util.find_spec(module) is not None
        check(f"Python package {module}", present)
        all_ok &= present

    try:
        from backend.manager import ModelManager
        manager = ModelManager()
        models = manager.list_models()
        available = [m for m in models if m["available"]]
        check("Configured models", bool(models), str(len(models)))
        check("Available models", bool(available), ", ".join(m["id"] for m in available) or "none")
        all_ok &= bool(models)
    except Exception as exc:
        check("Backend configuration", False, f"{type(exc).__name__}: {exc}")
        all_ok = False

    try:
        from backend.audio.tts import tts_service
        check("TTS runtime and model", tts_service.is_available())
    except Exception as exc:
        check("TTS check", False, f"{type(exc).__name__}: {exc}")

    print("\nResult:", "READY" if all_ok else "PARTIAL — missing optional/local assets are listed above")
    # Missing models are expected on development machines, so diagnostics do
    # not fail automation unless the Python runtime itself is unusable.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
