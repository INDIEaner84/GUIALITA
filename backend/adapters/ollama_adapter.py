import time
import logging
from typing import Optional

import httpx

from .base import ModelAdapter

log = logging.getLogger("guialita.ollama")


class OllamaAdapter(ModelAdapter):
    """Sekundaerer Adapter: Ollama (SHARED SERVICE).

    Ollama wird NIE beendet, NIE konfiguriert und NIE exklusiv beansprucht.
    Nur Erkennung und Nutzung der API auf Port 11434.
    """

    name = "ollama"

    def __init__(self, base_url: str = "http://127.0.0.1:11434"):
        self.base_url = base_url
        self._client = httpx.Client(timeout=5.0)

    def is_available(self) -> bool:
        try:
            r = self._client.get(f"{self.base_url}/api/tags")
            return r.status_code == 200
        except Exception:
            return False

    def health(self) -> dict:
        try:
            r = self._client.get(f"{self.base_url}/api/tags")
            if r.status_code != 200:
                return {"status": "error", "runtime": "ollama", "error": f"HTTP {r.status_code}"}
            tags = r.json().get("models", [])
            models = [m["name"] for m in tags]
            return {"status": "online", "runtime": "ollama", "models": models}
        except Exception as e:
            return {"status": "offline", "runtime": "ollama", "error": str(e)}

    def chat(self, message: str, model_cfg: dict, messages: list = None, **kwargs) -> dict:
        model_name = model_cfg.get("ollama_name") or model_cfg.get("name")
        if not model_name:
            raise RuntimeError("Ollama-Modellname fehlt in Konfiguration")
        if messages is None:
            messages = [{"role": "user", "content": message}]
        t0 = time.perf_counter()
        r = self._client.post(
            f"{self.base_url}/api/chat",
            json={"model": model_name, "messages": messages, "stream": False},
        )
        t1 = time.perf_counter()
        if r.status_code != 200:
            raise RuntimeError(f"Ollama HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        response = data.get("message", {}).get("content", "").strip()
        return {
            "response": response,
            "model": model_name,
            "latency_ms": (t1 - t0) * 1000.0,
            "runtime": "ollama",
        }

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass
