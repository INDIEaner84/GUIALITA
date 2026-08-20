from abc import ABC, abstractmethod
from typing import Any


class ModelAdapter(ABC):
    """Abstrakte Schnittstelle fuer Model-Backends (LFM Runtime)."""

    name: str = "abstract"

    @abstractmethod
    def is_available(self) -> bool:
        """True, wenn die Runtime erreichbar ist."""

    @abstractmethod
    def health(self) -> dict:
        """Status der Runtime."""

    @abstractmethod
    def chat(self, message: str, model_cfg: dict, messages: list = None, **kwargs) -> dict:
        """Sendet eine Chat-Nachricht an das Modell. Liefert response, model, latency_ms.

        messages: optionale vollständige Chat-History
        ([{"role": ..., "content": ...}, ...]). Ist messages None, wird das
        bisherige Single-Message-Verhalten beibehalten.
        """

    def close(self) -> None:
        pass
