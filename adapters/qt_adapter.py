from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from win_gui_core.errors import AdapterError


@dataclass
class QtLocator:
    object_name: str | None = None
    accessible_name: str | None = None
    role: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "object_name": self.object_name,
            "accessible_name": self.accessible_name,
            "role": self.role,
        }


class QtAdapter:
    def __init__(self, *, app_exe: str, app_workdir: str, dump_arg: str, automation_env_var: str) -> None:
        self.app_exe = app_exe
        self.app_workdir = app_workdir
        self.dump_arg = dump_arg
        self.automation_env_var = automation_env_var

    def dump_qt_state(self) -> dict[str, Any]:
        if not self.app_exe:
            raise AdapterError("APP_EXE is not configured for Qt state dumps.")
        with tempfile.NamedTemporaryFile(prefix="qt-state-", suffix=".json", delete=False) as handle:
            path = Path(handle.name)
        env = os.environ.copy()
        if self.automation_env_var:
            env[self.automation_env_var] = "1"
        cmd = [self.app_exe, self.dump_arg, str(path)]
        result = self._run_subprocess(cmd=cmd, env=env)
        if result.returncode != 0:
            raise AdapterError(f"Qt state dump command failed: {result.stderr.strip() or result.stdout.strip()}")
        if not path.exists():
            raise AdapterError(f"Qt state dump file was not created: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def run_app_command(self, args: list[str]) -> dict[str, Any]:
        if not self.app_exe:
            raise AdapterError("APP_EXE is not configured for app command execution.")
        env = os.environ.copy()
        if self.automation_env_var:
            env[self.automation_env_var] = "1"
        cmd = [self.app_exe, *args]
        result = self._run_subprocess(cmd=cmd, env=env)
        if result.returncode != 0:
            raise AdapterError(f"Qt app command failed: {result.stderr.strip() or result.stdout.strip()}")
        stdout = (result.stdout or "").strip()
        if not stdout:
            return {}
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise AdapterError(f"Qt app command returned invalid JSON: {stdout}") from exc
        if not isinstance(payload, dict):
            raise AdapterError("Qt app command returned a non-object JSON payload.")
        return payload

    def find_qt_object(
        self,
        *,
        object_name: str | None = None,
        accessible_name: str | None = None,
        role: str | None = None,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        dump = state or self.dump_qt_state()
        queue = [dump]
        while queue:
            node = queue.pop(0)
            if self._matches(node, object_name=object_name, accessible_name=accessible_name, role=role):
                return {"ok": True, "object": node, "locator": QtLocator(object_name, accessible_name, role).as_dict()}
            queue.extend(node.get("children", []))
        raise AdapterError("No Qt object matched the requested locator.")

    def invoke_qt_action(self, action_name: str, *, state: dict[str, Any] | None = None) -> dict[str, Any]:
        dump = state or self.dump_qt_state()
        for action in dump.get("actions", []):
            if action.get("objectName") == action_name or action.get("text") == action_name:
                command_result = self.run_app_command(
                    ["command", "--action", "invoke_action", "--object-name", action["objectName"]]
                )
                return {"ok": True, "action": action, "state": command_result}
        raise AdapterError(f"Qt action {action_name!r} was not present in the state dump.")

    def click_qt_object(self, **kwargs: Any) -> dict[str, Any]:
        return self.find_qt_object(**kwargs)

    def set_qt_value(self, *, object_name: str | None = None, accessible_name: str | None = None, value: str) -> dict[str, Any]:
        match = self.find_qt_object(object_name=object_name, accessible_name=accessible_name)
        return {"ok": True, "object": match["object"], "value": value}

    def toggle_qt_control(self, *, object_name: str | None = None, accessible_name: str | None = None) -> dict[str, Any]:
        match = self.find_qt_object(object_name=object_name, accessible_name=accessible_name)
        current = bool(match["object"].get("checked", False))
        return {"ok": True, "object": match["object"], "checked": not current}

    def _run_subprocess(self, *, cmd: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            cmd,
            cwd=self.app_workdir or None,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    @staticmethod
    def _matches(
        node: dict[str, Any],
        *,
        object_name: str | None,
        accessible_name: str | None,
        role: str | None,
    ) -> bool:
        if object_name and node.get("objectName") != object_name:
            return False
        if accessible_name and node.get("accessibleName") != accessible_name:
            return False
        if role and node.get("role") != role:
            return False
        return any([object_name, accessible_name, role])
