"""Wrappers around the installed AI Office executable.

The shell source is not on this PC. These helpers use the command line the
installed CloudComputerAI.exe already accepts. They do not patch app.asar.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

OFFICE_EXE_NAME = "CloudComputerAI.exe"
PROCESS_NAME = "CloudComputerAI"
WINDOW_TITLE = "AI Office by Cloud Computer AI"

# Same extensions the packaged boot script will open.
_DOCUMENT_SUFFIXES = {
    ".pdf",
    ".docx",
    ".docm",
    ".dotx",
    ".xlsx",
    ".xls",
    ".xlsm",
    ".xlsb",
    ".csv",
    ".tsv",
    ".pptx",
    ".pptm",
    ".ppsx",
    ".potx",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
    ".ico",
    ".doc",
    ".dot",
    ".rtf",
    ".odt",
    ".pages",
    ".ods",
    ".numbers",
    ".ppt",
    ".pps",
    ".odp",
    ".key",
}

SESSION_FLAGS = ("--desktops", "--session-status")
OVERLAY_FLAGS = ("--screenshot", "--record")


@dataclass(frozen=True)
class OfficePaths:
    exe: Path
    recent: Path

    @property
    def directory(self) -> Path:
        return self.exe.parent


def default_paths() -> OfficePaths:
    local = os.environ.get("LOCALAPPDATA", "")
    roaming = os.environ.get("APPDATA", "")
    return OfficePaths(
        exe=Path(local) / "Programs" / "CloudComputerAI" / OFFICE_EXE_NAME,
        recent=Path(roaming) / "CloudComputerAI" / "recent.json",
    )


def quote_arg(value: str) -> str:
    if value == "" or any(char in value for char in ' \t"'):
        return '"' + value.replace('"', '\\"') + '"'
    return value


def document_error(path: Path) -> str | None:
    if not path.is_file():
        return f"File not found: {path}"
    if path.suffix.lower() not in _DOCUMENT_SUFFIXES:
        return f"AI Office does not open this file type: {path.suffix or path.name}"
    return None


def parse_recent(raw: str) -> list[str]:
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("recent.json is not a list")
    return [item for item in data if isinstance(item, str)][:100]


def office_windows() -> list[tuple[int, str]]:
    script = (
        "Get-Process -Name $env:CCAI_PROC -ErrorAction SilentlyContinue | "
        "Where-Object { $_.MainWindowTitle } | "
        "ForEach-Object { Write-Output ($_.Id.ToString() + [char]9 + $_.MainWindowTitle) }"
    )
    completed = _powershell(script, {"CCAI_PROC": PROCESS_NAME}, timeout=20)
    windows: list[tuple[int, str]] = []
    for line in completed.stdout.splitlines():
        pid_text, sep, title = line.partition("\t")
        if sep and pid_text.isdigit() and title.strip():
            windows.append((int(pid_text), title.strip()))
    return windows


def wmi_create(command_line: str, cwd: str) -> int:
    script = (
        "$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create "
        "-Arguments @{ CommandLine = $env:CCAI_CMDLINE; CurrentDirectory = $env:CCAI_CWD }; "
        "if ($null -eq $r) { exit 2 }; "
        'Write-Output ("{0} {1}" -f [int]$r.ReturnValue, [int]$r.ProcessId)'
    )
    completed = _powershell(
        script,
        {"CCAI_CMDLINE": command_line, "CCAI_CWD": cwd},
        timeout=30,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(detail or "Win32_Process.Create failed")
    line = next((item.strip() for item in completed.stdout.splitlines() if item.strip()), "")
    parts = line.split()
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise RuntimeError(f"Unexpected Win32_Process.Create result: {line!r}")
    status, pid = int(parts[0]), int(parts[1])
    if status != 0:
        raise RuntimeError(f"Win32_Process.Create returned {status}")
    return pid


def launch(paths: OfficePaths | None = None, wait_seconds: float = 25) -> str:
    paths = paths or default_paths()
    _require_exe(paths)
    existing = office_windows()
    if existing:
        pid, title = existing[0]
        return f"Already running. pid={pid} title={title}"
    command = quote_arg(str(paths.exe))
    pid = wmi_create(command, str(paths.directory))
    found = _wait_for_window(wait_seconds)
    if found is None:
        return f"Started pid={pid}. The window title was not visible yet."
    return f"pid={found[0]} title={found[1]}"


def open_document(path: str, paths: OfficePaths | None = None, wait_seconds: float = 25) -> str:
    paths = paths or default_paths()
    _require_exe(paths)
    target = Path(path).expanduser().resolve()
    error = document_error(target)
    if error:
        raise ValueError(error)
    already = office_windows()
    command = f"{quote_arg(str(paths.exe))} {quote_arg(str(target))}"
    pid = wmi_create(command, str(paths.directory))
    if already:
        time.sleep(2)
        summary = _format_windows(office_windows())
        return f"Handed {target} to AI Office (spawn pid={pid}). {summary}"
    found = _wait_for_window(wait_seconds)
    if found is None:
        return f"Started pid={pid} with {target}. The window title was not visible yet."
    return f"pid={found[0]} title={found[1]} file={target}"


def recent_files(paths: OfficePaths | None = None) -> str:
    paths = paths or default_paths()
    if not paths.recent.is_file():
        return "No recent files."
    entries = parse_recent(paths.recent.read_text(encoding="utf-8-sig"))
    if not entries:
        return "No recent files."
    return "\n".join(entries)


def session_command(flag: str, paths: OfficePaths | None = None, timeout: float = 60) -> str:
    if flag not in SESSION_FLAGS:
        raise ValueError(f"Unsupported session flag: {flag}")
    paths = paths or default_paths()
    _require_exe(paths)
    return _run_exe(paths, [flag], timeout)


def overlay_command(flag: str, paths: OfficePaths | None = None, timeout: float = 30) -> str:
    if flag not in OVERLAY_FLAGS:
        raise ValueError(f"Unsupported overlay flag: {flag}")
    paths = paths or default_paths()
    _require_exe(paths)
    before = {pid for pid, _title in office_windows()}
    result = _run_exe(paths, [flag], timeout)
    after = {pid for pid, _title in office_windows()}
    if before and not before.issubset(after):
        missing = ", ".join(str(pid) for pid in sorted(before - after))
        raise RuntimeError(f"AI Office window is no longer running ({missing}). {result}")
    if not before:
        return f"{result}\nAI Office had no titled window before this call."
    alive = ", ".join(str(pid) for pid in sorted(before))
    return f"{result}\nAI Office window still running: {alive}"


def _require_exe(paths: OfficePaths) -> None:
    if not paths.exe.is_file():
        raise FileNotFoundError(f"AI Office is not installed at {paths.exe}")


def _wait_for_window(wait_seconds: float) -> tuple[int, str] | None:
    deadline = time.monotonic() + wait_seconds
    while True:
        windows = office_windows()
        preferred = [item for item in windows if item[1] == WINDOW_TITLE]
        if preferred:
            return preferred[0]
        if windows:
            return windows[0]
        if time.monotonic() >= deadline:
            return None
        time.sleep(0.4)


def _format_windows(windows: list[tuple[int, str]]) -> str:
    if not windows:
        return "No titled AI Office window yet."
    return "; ".join(f"pid={pid} title={title}" for pid, title in windows)


def _run_exe(paths: OfficePaths, args: list[str], timeout: float) -> str:
    proc = subprocess.Popen(
        [str(paths.exe), *args],
        cwd=str(paths.directory),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        output, _err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
        raise TimeoutError(f"{args[0]} did not exit within {timeout:.0f}s") from None
    body = (output or "").strip()
    if body:
        return f"exit {proc.returncode}\n{body}"
    return f"exit {proc.returncode}"


def _powershell(script: str, env_extra: dict[str, str], timeout: float) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(env_extra)
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
        check=False,
    )
