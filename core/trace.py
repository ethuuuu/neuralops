"""Structured tracing of every intermediate stage.

The single most important file in the project for debugging.
Never debug by staring at final output; read the trace forward and find
the first stage whose intermediate looks wrong.
"""
import json, time, threading
from pathlib import Path

_LOCK = threading.Lock()
_PATH = Path(__file__).resolve().parent.parent / "trace.jsonl"
_SUBSCRIBERS = []


def subscribe(fn):
    """UI layer registers here to stream events live."""
    _SUBSCRIBERS.append(fn)


def emit(stage: str, **fields):
    """Record one intermediate. stage is e.g. 'route', 'retrieve', 'tool_call'."""
    ev = {"ts": round(time.time(), 3), "stage": stage, **fields}
    with _LOCK:
        with _PATH.open("a") as f:
            f.write(json.dumps(ev, default=str) + "\n")
    for fn in _SUBSCRIBERS:
        try:
            fn(ev)
        except Exception:
            pass
    return ev


def read_all():
    if not _PATH.exists():
        return []
    return [json.loads(l) for l in _PATH.read_text().splitlines() if l.strip()]
