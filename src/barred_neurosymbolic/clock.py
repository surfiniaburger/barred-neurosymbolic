"""
RunClock utility for deterministic and frozen timestamps in autonomous swarms.
"""

import os
import re
from datetime import datetime, timezone
from typing import Optional


class RunClock:
    def __init__(self, fixed_now: Optional[str] = None):
        self.fixed_now = fixed_now.strip() if isinstance(fixed_now, str) and fixed_now.strip() else None

    @classmethod
    def from_env(cls) -> "RunClock":
        return cls(os.getenv("RUN_CLOCK_NOW", ""))

    @classmethod
    def from_value(cls, value: Optional[str]) -> "RunClock":
        return cls(value)

    def now_iso(self) -> str:
        if self.fixed_now:
            return self.fixed_now
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    def compact_timestamp(self) -> str:
        value = self.now_iso().replace("T", "-").replace("Z", "")
        return re.sub(r"[^0-9A-Za-z_-]+", "-", value).strip("-")
