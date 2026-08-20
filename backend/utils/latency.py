import time
from dataclasses import dataclass, field


@dataclass
class Latency:
    t_start: float = field(default_factory=time.perf_counter)
    t_model_request: float = 0.0
    t_model_response: float = 0.0
    t_total: float = 0.0

    def mark_model_request(self):
        self.t_model_request = time.perf_counter()

    def mark_model_response(self):
        self.t_model_response = time.perf_counter()
        self.t_total = time.perf_counter() - self.t_start

    @property
    def model_time_ms(self) -> float:
        if self.t_model_response and self.t_model_request:
            return (self.t_model_response - self.t_model_request) * 1000.0
        return 0.0

    @property
    def total_ms(self) -> float:
        return self.t_total * 1000.0

    def to_dict(self) -> dict:
        return {
            "request_start": self.t_start,
            "model_request_ms": (self.t_model_request - self.t_start) * 1000.0 if self.t_model_request else None,
            "model_time_ms": self.model_time_ms,
            "total_ms": self.total_ms,
        }
