"""Liveness of the collector loop, readable by a Docker healthcheck.

The loop writes a small JSON file each time it starts a cycle or goes to sleep,
including a *deadline*: the time by which it promises to write again. A hung
loop (deadlock, stuck await) misses its deadline; a loop that is alive but
failing (TSETMC unreachable) does not — that is reported by ``/health`` and the
logs instead, because restarting the container would not fix it.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


class Heartbeat:
    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, data: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), "utf-8")
        os.replace(tmp, self.path)  # atomic: a reader never sees half a file

    def check(self, now: datetime) -> tuple[bool, str]:
        """(healthy, reason) — healthy while the last promised deadline has not passed."""
        try:
            data = json.loads(self.path.read_text("utf-8"))
            deadline = datetime.fromisoformat(data["deadline"])
        except FileNotFoundError:
            return False, "no heartbeat yet"
        except (ValueError, KeyError) as exc:
            return False, f"unreadable heartbeat: {exc}"
        if now > deadline:
            return False, f"missed deadline {deadline.isoformat()} (state {data.get('state')})"
        return True, f"{data.get('state')} (failed streak {data.get('failed_streak', 0)})"
