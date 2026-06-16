import threading
from typing import Dict

_lock = threading.Lock()
_counters: Dict[str, int] = {}


def incr(name: str, amount: int = 1) -> None:
    with _lock:
        _counters[name] = _counters.get(name, 0) + amount


def get_metrics() -> Dict[str, int]:
    with _lock:
        return dict(_counters)


def render_prometheus() -> str:
    """Return metrics in Prometheus exposition text format."""
    lines: list[str] = []
    with _lock:
        for key, val in _counters.items():
            # sanitize key to prometheus metric name
            name = key.replace(".", "_").replace("-", "_")
            lines.append(f"{name}_total {int(val)}")
    return "\n".join(lines) + "\n"
