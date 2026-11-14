"""GUIALITA Mock-LLM-Adapter — deterministischer Test-Adapter ohne Modell/GPU.

Zweck
-----
Lokale Entwicklung und automatisierte Tests auf Maschinen ohne
llama-cpp-python, ohne Modelldateien und ohne GPU (z. B. CI, Sandbox,
frisch geklontes Repo). Der Adapter ersetzt KEINE Produktions-Runtime:
Granite/LFM via llama-cpp-python bleiben primär. Er wird nur aktiv,
wenn er explizit angefordert wird:

    GUIALITA_MOCK_LLM=1        (Umgebungsvariable, siehe .env.example)
    oder Modell mit adapter: mock in config/models.yaml

Verhalten
---------
- Deterministisch: gleiche Eingabe → gleiche Ausgabe (kein Zufall).
- Echo + Marker: Die Antwort enthält den Marker ``MOCK-LLM-OK`` und die
  letzte User-Nachricht, damit Tests beweisen können, dass der volle
  Pfad (Session → Memory → ChatService → Adapter → Persistenz) lief.
- History-bewusst: Bei ``messages=[...]`` wird die letzte User-Nachricht
  aus der History verwendet.
- Keine Datei-, Netzwerk- oder Hardware-Zugriffe. Keine Abhängigkeiten.

Verbote (siehe docs/GUIALITA_STATE.yaml → prohibitions)
--------------------------------------------------------
Dieser Adapter ist kein Cloud-Ersatz, kein Runtime-Austausch und keine
neue Fähigkeit im Sinne der Freeze-Policy. Er ist reine Testinfrastruktur.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

from .base import ModelAdapter

log = logging.getLogger("guialita.mock")

MOCK_MARKER = "MOCK-LLM-OK"
MOCK_MODEL_NAME = "mock-1b (deterministic test adapter)"


def mock_enabled() -> bool:
    """True, wenn der Mock-Modus über die Umgebung angefordert ist."""
    return os.environ.get("GUIALITA_MOCK_LLM", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


class MockAdapter(ModelAdapter):
    """Deterministischer Fake-LLM für lokale Tests (kein Modell, keine GPU)."""

    name = "mock"

    def is_available(self) -> bool:
        return True

    def health(self) -> dict:
        return {
            "status": "online",
            "runtime": "mock",
            "gpu": False,
            "model": MOCK_MODEL_NAME,
            "note": "Test-Adapter ohne Modell/GPU — kein Produktions-Ersatz",
        }

    def chat(self, message: str, model_cfg: dict, messages: list = None, **kwargs) -> dict:
        t0 = time.perf_counter()

        # Letzte User-Nachricht aus der History bestimmen (falls vorhanden).
        last_user = (message or "").strip()
        if messages:
            for entry in reversed(messages):
                if isinstance(entry, dict) and entry.get("role") == "user":
                    content = str(entry.get("content", "")).strip()
                    if content:
                        last_user = content
                    break

        model_name = (model_cfg or {}).get("name") or MOCK_MODEL_NAME
        response = f"{MOCK_MARKER} [{model_name}] Echo: {last_user}"

        latency_ms = (time.perf_counter() - t0) * 1000.0
        log.debug("Mock-Chat: %s (%.2f ms)", last_user[:60], latency_ms)
        return {
            "response": response,
            "model": model_name,
            "latency_ms": latency_ms,
            "runtime": "mock",
        }

    def close(self) -> None:
        pass
