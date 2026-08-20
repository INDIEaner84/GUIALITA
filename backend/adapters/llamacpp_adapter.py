import os
import threading
import time
import logging
from typing import Optional, Dict

from .base import ModelAdapter

log = logging.getLogger("guialita.llamacpp")


class LlamaCppAdapter(ModelAdapter):
    """Primaerer Adapter: llama-cpp-python (dediziert fuer GUIALITA)."""

    name = "llamacpp"

    def __init__(self):
        self._llm_cache: Dict[str, object] = {}
        self._lock = threading.Lock()
        self._gpu_available: Optional[bool] = None

    def _has_cuda(self) -> bool:
        if self._gpu_available is not None:
            return self._gpu_available
        try:
            import llama_cpp
            lib_dir = os.path.join(os.path.dirname(llama_cpp.__file__), "lib")
            has_gpu = any(
                "cuda" in name.lower()
                for name in os.listdir(lib_dir)
            )
            self._gpu_available = has_gpu
        except Exception as e:
            log.warning("CUDA-Pruefung fehlgeschlagen: %s", e)
            self._gpu_available = False
        return self._gpu_available

    def is_available(self) -> bool:
        try:
            from llama_cpp import Llama
            return True
        except Exception:
            return False

    def health(self) -> dict:
        cuda = self._has_cuda()
        return {
            "status": "online",
            "runtime": "llama-cpp-python",
            "gpu": cuda,
            "loaded_models": list(self._llm_cache.keys()),
        }

    def _resolve_path(self, path: str) -> str:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if not os.path.isabs(path):
            path = os.path.join(base, path)
        return os.path.abspath(path)

    def _load_model(self, model_cfg: dict):
        path = self._resolve_path(model_cfg["path"])
        if path in self._llm_cache:
            return self._llm_cache[path]

        from llama_cpp import Llama

        kwargs = dict(
            model_path=path,
            n_ctx=int(model_cfg.get("n_ctx", 4096)),
            n_gpu_layers=int(model_cfg.get("n_gpu_layers", 0)),
            verbose=False,
        )
        mmproj = model_cfg.get("mmproj")
        if mmproj:
            kwargs["mmproj"] = self._resolve_path(mmproj)
        tokenizer = model_cfg.get("tokenizer")
        if tokenizer:
            kwargs["tokenizer_path"] = self._resolve_path(tokenizer)
        vocoder = model_cfg.get("vocoder")
        if vocoder:
            kwargs["vocoder_path"] = self._resolve_path(vocoder)

        log.info("Lade Modell: %s", path)
        with self._lock:
            try:
                llm = Llama(**kwargs)
            except Exception as e:
                if kwargs.get("n_gpu_layers", 0) > 0:
                    log.warning("GPU-Load fehlgeschlagen (%s) - Fallback auf CPU", e)
                    kwargs["n_gpu_layers"] = 0
                    self._gpu_available = False
                    llm = Llama(**kwargs)
                else:
                    raise
            self._llm_cache[path] = llm
        log.info("Modell geladen: %s", path)
        return llm

    def chat(self, message: str, model_cfg: dict, messages: list = None, **kwargs) -> dict:
        t0 = time.perf_counter()
        llm = self._load_model(model_cfg)
        t1 = time.perf_counter()

        chat_template = model_cfg.get("chat_template", "llama3")
        if messages is None:
            messages = [
                {"role": "user", "content": message},
            ]

        out = llm.create_chat_completion(
            messages=messages,
            max_tokens=int(model_cfg.get("max_tokens", 512)),
            temperature=float(kwargs.get("temperature", 0.7)),
        )
        t2 = time.perf_counter()

        try:
            response = out["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError):
            response = str(out).strip()

        return {
            "response": response,
            "model": model_cfg.get("name", model_cfg["path"]),
            "latency_ms": (t2 - t0) * 1000.0,
            "load_ms": (t1 - t0) * 1000.0,
            "inference_ms": (t2 - t1) * 1000.0,
        }

    def close(self) -> None:
        with self._lock:
            for llm in self._llm_cache.values():
                try:
                    llm.close()
                except Exception:
                    pass
            self._llm_cache.clear()
