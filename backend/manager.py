import logging
import os
from typing import Dict, Optional

import yaml

from . import paths
from .adapters.llamacpp_adapter import LlamaCppAdapter
from .adapters.ollama_adapter import OllamaAdapter
from .adapters.stt_whisper import WhisperSTTAdapter

log = logging.getLogger("guialita.manager")

BASE_DIR = paths.root()

# Konfigurationsschlüssel, deren Werte als Dateipfade behandelt werden
# (Platzhalter-Expansion + Absolutmachung beim Laden der Konfiguration).
PATH_KEYS = ("path", "mmproj", "tokenizer", "vocoder", "cli_path", "model_path")


class ModelManager:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.join(BASE_DIR, "config", "models.yaml")
        self._config = self._load_config()
        self.llamacpp = LlamaCppAdapter()
        self.ollama = OllamaAdapter(base_url=self._config.get("server", {}).get("ollama_url", "http://127.0.0.1:11434"))
        self.default_model = self._config.get("default_model", "granite-3b")
        stt_cfg = self._config.get("stt", {})
        self.stt = WhisperSTTAdapter(
            cli_path=stt_cfg.get("cli_path") or paths.whisper_cli(),
            model_path=stt_cfg.get("model_path")
            or os.path.join(paths.model_root(), "whisper", "ggml-base.bin"),
        )
        self.stt_config = stt_cfg

    def _resolve_path(self, path: str) -> str:
        return paths.resolve(path)

    def _load_config(self) -> dict:
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        return self._expand_paths(config)

    @classmethod
    def _expand_paths(cls, node, key: Optional[str] = None):
        """Löst ${GUIALITA_*}-Platzhalter auf und macht Pfadwerte absolut."""
        if isinstance(node, dict):
            return {k: cls._expand_paths(v, k) for k, v in node.items()}
        if isinstance(node, list):
            return [cls._expand_paths(v, key) for v in node]
        if isinstance(node, str) and key in PATH_KEYS:
            return paths.resolve(node)
        return node

    def get_models(self) -> dict:
        return self._config.get("models", {})

    def get_model_cfg(self, model_id: Optional[str] = None) -> dict:
        models = self.get_models()
        model_id = model_id or self.default_model
        if model_id not in models:
            raise KeyError(f"Unbekanntes Modell: {model_id}")
        cfg = dict(models[model_id])
        cfg["_id"] = model_id
        return cfg

    def list_models(self) -> list:
        result = []
        for mid, cfg in self.get_models().items():
            path = cfg.get("path", "")
            if not os.path.isabs(path):
                path = os.path.join(BASE_DIR, path)
            exists = os.path.exists(path)
            result.append({
                "id": mid,
                "name": cfg.get("name", mid),
                "adapter": cfg.get("adapter", "llamacpp"),
                "path": path,
                "available": exists,
                "size_gb": round(os.path.getsize(path) / 1e9, 2) if exists else None,
            })
        return result

    def health(self) -> dict:
        llm_ok = self.llamacpp.is_available()
        llm_health = self.llamacpp.health() if llm_ok else {"status": "offline", "runtime": "llama-cpp-python"}
        ollama_health = self.ollama.health()
        return {
            "api": "online",
            "default_model": self.default_model,
            "primary_runtime": {
                "runtime": "llama-cpp-python",
                "status": "online" if llm_ok else "offline",
                "gpu": llm_health.get("gpu", False) if llm_ok else False,
            },
            "secondary_runtime": ollama_health,
            "models": self.list_models(),
        }

    def chat(self, message: str, model_id: Optional[str] = None, messages: Optional[list] = None,
             **kwargs) -> dict:
        cfg = self.get_model_cfg(model_id)
        adapter_name = cfg.get("adapter", "llamacpp")

        if adapter_name == "llamacpp":
            if not self.llamacpp.is_available():
                raise RuntimeError("llama-cpp-python ist nicht installiert")
            result = self.llamacpp.chat(message, cfg, messages=messages, **kwargs)
        elif adapter_name == "ollama":
            if not self.ollama.is_available():
                raise RuntimeError(
                    "Ollama ist nicht erreichbar. Ollama ist ein SHARED SERVICE - "
                    "starte ihn separat: `ollama serve`"
                )
            result = self.ollama.chat(message, cfg, messages=messages, **kwargs)
        else:
            raise RuntimeError(f"Unbekannter Adapter: {adapter_name}")

        result["model_id"] = cfg["_id"]
        result.setdefault("runtime", adapter_name)
        return result

    def close(self) -> None:
        self.llamacpp.close()
        self.ollama.close()

    def stt_health(self) -> dict:
        h = self.stt.health()
        h["engine"] = self.stt_config.get("engine", "whisper.cpp")
        h["language"] = self.stt_config.get("language", "auto")
        h["sample_rate"] = self.stt_config.get("sample_rate", 16000)
        return h

    def transcribe(self, wav_bytes: bytes) -> dict:
        lang = self.stt_config.get("language", "auto")
        sample_rate = int(self.stt_config.get("sample_rate", 16000))
        result = self.stt.transcribe(wav_bytes, language=lang, sample_rate=sample_rate)
        result["engine"] = self.stt_config.get("engine", "whisper.cpp")
        return result
