from __future__ import annotations

import json
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DEFAULT_LEVEL = "access_denied"  # default: log only failed/denied attempts
VALID_LEVELS = {"access_denied", "access", "disabled"}


class AccessLogger:
    def __init__(self, cfg_dir: Path) -> None:
        self.cfg_dir = Path(cfg_dir)
        self.cfg_dir.mkdir(parents=True, exist_ok=True)
        # store access level inside webui_auth.json per request
        self.user_file = self.cfg_dir / "webui_auth.json"
        self.log_file = self.cfg_dir / "access_log.log"

    def get_level(self) -> str:
        try:
            if self.user_file.exists():
                try:
                    doc = json.loads(self.user_file.read_text(encoding="utf-8"))
                except Exception:
                    doc = None
                if isinstance(doc, dict):
                    txt = doc.get("access_log_level")
                    if isinstance(txt, str) and txt in VALID_LEVELS:
                        return txt
        except Exception:
            pass
        return DEFAULT_LEVEL

    def set_level(self, level: str) -> bool:
        if level not in VALID_LEVELS:
            return False
        try:
            # load existing user file (if any), update the access_log_level key
            data: dict[str, object] = {}
            if self.user_file.exists():
                try:
                    data = json.loads(self.user_file.read_text(encoding="utf-8")) or {}
                except Exception:
                    data = {}
            if not isinstance(data, dict):
                data = {}
            data["access_log_level"] = level
            # write back safely
            self.user_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception:
            return False

    def should_log(self, success: bool) -> bool:
        """Determine if this access attempt should be logged.

        Args:
            success: Whether the request was successful (200-299 status)

        Returns:
            True if the attempt should be logged, False otherwise

        Levels:
        - access: log all attempts
        - access_denied: log only failed attempts (default)
        - disabled: no logging at all
        """
        lvl = self.get_level()
        if lvl == "access":
            return True
        if lvl == "disabled":
            return False
        # access_denied: only log non-success (failed) attempts
        return not bool(success)

    def log(self, *, endpoint: str, method: str, remote_addr: Optional[str], username: Optional[str], success: bool, status: int, headers: Optional[dict[str, Any]] = None, details: Optional[str] = None) -> None:
        try:
            record: dict[str, Any] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "endpoint": endpoint,
                "method": method,
                "remote_addr": remote_addr,
                "user": username,
                "success": bool(success),
                "status": int(status),
            }
            if headers:
                # Store a small subset of headers for context
                record["headers"] = {k: headers.get(k) for k in ("User-Agent", "Authorization", "Referer") if headers.get(k) is not None}
            if details:
                record["details"] = str(details)

            # Append as JSON line
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            # Best-effort logging: swallow errors
            pass

    def tail(self, n: int = 200) -> list[dict[str, Any]]:
        try:
            if not self.log_file.exists():
                return []
            # Read last n lines (simple approach)
            with open(self.log_file, encoding="utf-8") as f:
                lines = f.read().splitlines()
            lines = lines[-n:]
            out = []
            for ln in lines:
                with suppress(Exception):
                    out.append(json.loads(ln))
            return out
        except Exception:
            return []
