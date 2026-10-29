"""Republish Windows-MCP under this server.

PowerShell and Registry stay excluded. This process does not run
`windows-mcp install` and does not listen on the network.

The desktop tools come from the windows-mcp package installed with this
project. A customer does not need a checkout on a fixed drive path. Set
WINDOWS_MCP_DIR to run a local checkout instead. uv is taken from UV_EXE,
PATH, or %USERPROFILE%\\.local\\bin.
"""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import mcp.types as types
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

WINDOWS_MCP_COMMIT = "277db1bed9612fdfd242a50581f83ae981b07ff7"
WINDOWS_MCP_FROM = (
    "git+https://github.com/CursorTouch/Windows-MCP.git@" + WINDOWS_MCP_COMMIT
)
SERVE_ARGS = ["serve", "--exclude-tools", "PowerShell,Registry"]

EXCLUDED_TOOLS = frozenset({"PowerShell", "Registry"})
REQUIRED_TOOLS = frozenset(
    {
        "Snapshot",
        "Screenshot",
        "Click",
        "Type",
        "Scroll",
        "Move",
        "Shortcut",
        "App",
        "Wait",
        "Clipboard",
        "DisplayInventory",
        "Process",
        "FileSystem",
        "Notification",
        "Scrape",
        "MultiSelect",
        "MultiEdit",
    }
)


def select_forwarded(tools: list[types.Tool], office_names: frozenset[str]) -> list[types.Tool]:
    names = {tool.name for tool in tools}
    leaked = EXCLUDED_TOOLS.intersection(names)
    if leaked:
        raise RuntimeError("Refusing excluded tools: " + ", ".join(sorted(leaked)))
    collisions = office_names.intersection(names)
    if collisions:
        raise RuntimeError("Forwarded tools collide with office tools: " + ", ".join(sorted(collisions)))
    missing = REQUIRED_TOOLS - names
    if missing:
        raise RuntimeError("Windows-MCP is missing tools: " + ", ".join(sorted(missing)))
    return list(tools)


def user_home() -> Path:
    return Path(os.environ.get("USERPROFILE") or Path.home())


def bundled_windows_mcp() -> Path | None:
    scripts = Path(sys.executable).resolve().parent
    for name in ("windows-mcp.exe", "windows-mcp"):
        candidate = scripts / name
        if candidate.is_file():
            return candidate
    return None


def resolve_uv() -> Path | None:
    override = os.environ.get("UV_EXE", "").strip()
    if override and Path(override).is_file():
        return Path(override)
    found = shutil.which("uv")
    if found:
        return Path(found)
    home = user_home()
    for name in ("uv.exe", "uv"):
        candidate = home / ".local" / "bin" / name
        if candidate.is_file():
            return candidate
    return None


def windows_mcp_launch() -> tuple[str, list[str], str | None]:
    bundled = bundled_windows_mcp()
    if bundled is not None:
        return str(bundled), list(SERVE_ARGS), None

    uv = resolve_uv()
    if uv is None:
        raise FileNotFoundError(
            "windows-mcp is not installed in this Python environment, and uv was not found. "
            "Install uv, then run uv sync in the ai-office-mcp folder."
        )

    checkout = os.environ.get("WINDOWS_MCP_DIR", "").strip()
    if checkout:
        root = Path(checkout)
        if not (root / "pyproject.toml").is_file():
            raise FileNotFoundError(f"WINDOWS_MCP_DIR is not a Windows-MCP checkout: {root}")
        return (
            str(uv),
            ["--directory", str(root), "run", "windows-mcp", *SERVE_ARGS],
            str(root),
        )

    return (
        str(uv),
        ["tool", "run", "--from", WINDOWS_MCP_FROM, "windows-mcp", *SERVE_ARGS],
        None,
    )


def windows_mcp_parameters() -> StdioServerParameters:
    command, args, cwd = windows_mcp_launch()
    return StdioServerParameters(
        command=command,
        args=args,
        env={"ANONYMIZED_TELEMETRY": "false"},
        cwd=cwd,
    )


class WindowsMcpForwarder:
    def __init__(self, session: ClientSession, tools: list[types.Tool]) -> None:
        self._session = session
        self.tools = tools

    async def call(self, name: str, arguments: dict[str, object]) -> types.CallToolResult:
        if name in EXCLUDED_TOOLS:
            raise RuntimeError(f"{name} is excluded")
        return await self._session.call_tool(name, arguments)


@asynccontextmanager
async def forward_windows_mcp(office_names: frozenset[str]) -> AsyncIterator[WindowsMcpForwarder]:
    params = windows_mcp_parameters()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            tools = select_forwarded(list(listed.tools), office_names)
            yield WindowsMcpForwarder(session, tools)
