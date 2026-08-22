"""Privacy-conscious append-only audit events for GUIALITA.

Only technical metadata is recorded by default. Message/audio content is never
written unless GUIALITA_AUDIT_INCLUDE_CONTENT=1 is explicitly configured.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_PATH = _ROOT / "data" / "audit.jsonl"
_LOCK = threading.Lock()


def read_events(session_id: str | None = None, limit: int = 200) -> list[dict]:
    """Read recent audit metadata without failing when no log exists."""
    path = Path(os.environ.get("GUIALITA_AUDIT_PATH", str(_DEFAULT_PATH))).expanduser()
    if not path.is_file():
        return []
    events = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines()[-max(1, min(limit, 1000)):]:
            try:
                event = json.loads(line)
                if session_id is None or event.get("session_id") == session_id:
                    events.append(event)
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return events


def summary(session_id: str | None = None) -> dict:
    """Summarize technical events for a session or the whole local log."""
    events = read_events(session_id, limit=1000)
    completed = [e for e in events if e.get("status") == "success"]
    def average(key: str) -> float:
        values = [float(e[key]) for e in completed if e.get(key) is not None]
        return round(sum(values) / len(values), 2) if values else 0.0
    return {
        "event_count": len(events),
        "completed_count": len(completed),
        "error_count": sum(1 for e in events if e.get("status") == "error"),
        "average_transcription_ms": average("transcription_ms"),
        "average_chat_ms": average("chat_ms"),
        "average_total_ms": average("total_ms"),
        "sessions": sorted({e.get("session_id") for e in events if e.get("session_id")}),
    }


def record(event: str, **fields) -> None:
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": event,
        **fields,
    }
    if os.environ.get("GUIALITA_AUDIT_INCLUDE_CONTENT") != "1":
        payload.pop("content", None)
        payload.pop("transcript", None)
        payload.pop("response", None)

    path = Path(os.environ.get("GUIALITA_AUDIT_PATH", str(_DEFAULT_PATH))).expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK, path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        # Auditing must never make chat unavailable.
        pass
