from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import psutil

from .errors import AssertionFailedError


class LogManager:
    def __init__(self, app_log_dir: Path, app_dump_dir: Path | None = None) -> None:
        self.app_log_dir = app_log_dir
        self.app_dump_dir = app_dump_dir

    def resolve_log_path(self, filename: str | None = None) -> Path | None:
        if filename:
            path = self.app_log_dir / filename
            return path if path.exists() else None
        if not self.app_log_dir.exists():
            return None
        files = [path for path in self.app_log_dir.glob("**/*") if path.is_file()]
        if not files:
            return None
        files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return files[0]

    def tail_log(self, filename: str | None = None, lines: int = 200) -> dict[str, Any]:
        path = self.resolve_log_path(filename)
        if path is None or not path.exists():
            return {"ok": False, "error": "log file not found"}
        content = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-lines:]
        return {"ok": True, "path": str(path), "content": "\n".join(content)}

    def collect_recent_logs(self, minutes: int = 120, output_dir: str | None = None) -> dict[str, Any]:
        if not self.app_log_dir.exists():
            return {"ok": False, "error": f"log dir not found: {self.app_log_dir}"}
        cutoff = time.time() - minutes * 60
        out_dir = Path(output_dir) if output_dir else Path.cwd() / "artifacts" / f"logs-{int(time.time())}"
        out_dir.mkdir(parents=True, exist_ok=True)
        copied: list[str] = []
        for item in sorted(self.app_log_dir.glob("**/*")):
            if not item.is_file():
                continue
            if item.stat().st_mtime < cutoff:
                continue
            relative = item.relative_to(self.app_log_dir)
            destination = out_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)
            copied.append(str(destination))
        return {"ok": True, "output_dir": str(out_dir), "files": copied}

    def assert_log_contains(self, expected_text: str, filename: str | None = None, lines: int = 400) -> dict[str, Any]:
        tail = self.tail_log(filename=filename, lines=lines)
        if not tail.get("ok"):
            raise AssertionFailedError(tail["error"])
        if expected_text not in tail["content"]:
            raise AssertionFailedError(f"{expected_text!r} was not present in {tail['path']}.")
        return {"ok": True, "path": tail["path"], "match": expected_text}

    def collect_event_logs(self, minutes: int = 60, output_dir: str | None = None) -> dict[str, Any]:
        out_dir = Path(output_dir) if output_dir else Path.cwd() / "artifacts" / f"event-logs-{int(time.time())}"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "application.evtx.txt"
        seconds = minutes * 60
        query = "*[System[TimeCreated[timediff(@SystemTime)<=" f"{seconds * 1000}]]]"
        result = subprocess.run(
            ["wevtutil", "qe", "Application", f"/q:{query}", "/f:text"],
            capture_output=True,
            text=True,
            check=False,
        )
        path.write_text(result.stdout or result.stderr, encoding="utf-8", errors="ignore")
        return {"ok": result.returncode == 0, "path": str(path), "returncode": result.returncode}

    def collect_dumps(self, output_dir: str | None = None) -> dict[str, Any]:
        if self.app_dump_dir is None or not self.app_dump_dir.exists():
            return {"ok": True, "files": [], "note": "APP_DUMP_DIR is not configured"}
        out_dir = Path(output_dir) if output_dir else Path.cwd() / "artifacts" / f"dumps-{int(time.time())}"
        out_dir.mkdir(parents=True, exist_ok=True)
        copied: list[str] = []
        for item in sorted(self.app_dump_dir.glob("**/*.dmp")):
            relative = item.relative_to(self.app_dump_dir)
            destination = out_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)
            copied.append(str(destination))
        return {"ok": True, "output_dir": str(out_dir), "files": copied}

    def get_process_tree(self, pid: int | None = None) -> dict[str, Any]:
        if pid is None:
            return {"ok": False, "error": "pid is required"}
        proc = psutil.Process(pid)
        children = proc.children(recursive=True)
        return {
            "ok": True,
            "root": self._serialize_process(proc),
            "children": [self._serialize_process(child) for child in children],
        }

    def wait_process_idle(
        self,
        pid: int | None = None,
        cpu_threshold: float = 2.0,
        timeout_sec: float = 10.0,
        stable_for_sec: float = 1.0,
    ) -> dict[str, Any]:
        if pid is None:
            return {"ok": False, "error": "pid is required"}
        proc = psutil.Process(pid)
        proc.cpu_percent(interval=None)
        deadline = time.time() + timeout_sec
        stable_since: float | None = None
        while time.time() < deadline:
            cpu = proc.cpu_percent(interval=0.2)
            if cpu <= cpu_threshold:
                stable_since = stable_since or time.time()
                if time.time() - stable_since >= stable_for_sec:
                    return {"ok": True, "pid": pid, "cpu_percent": cpu}
            else:
                stable_since = None
        return {"ok": False, "pid": pid, "error": "process did not become idle"}

    @staticmethod
    def _serialize_process(proc: psutil.Process) -> dict[str, Any]:
        with proc.oneshot():
            return {
                "pid": proc.pid,
                "name": proc.name(),
                "exe": proc.exe() if os.name == "nt" else "",
                "status": proc.status(),
            }
