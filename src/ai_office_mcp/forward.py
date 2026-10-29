"""Republish the local Windows-MCP checkout under this server.

PowerShell and Registry stay excluded. This process does not run
`windows-mcp install` and does not listen on the network.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import mcp.types as types
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

WINDOWS_MCP_COMMIT = "277db1bed9612fdfd242a50581f83ae981b07ff7"
DEFAULT_UV = Path(r"C:\Users\Admin\.local\bin\uv.exe")
DEFAULT_WINDOWS_MCP = Path(r"C:\Users\Admin\projects\Windows-MCP")

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


def windows_mcp_parameters(
    uv: Path = DEFAULT_UV,
    checkout: Path = DEFAULT_WINDOWS_MCP,
) -> StdioServerParameters:
    if not uv.is_file():
        raise FileNotFoundError(f"uv is not installed at {uv}")
    if not (checkout / "pyproject.toml").is_file():
        raise FileNotFoundError(f"Windows-MCP checkout is not at {checkout}")
    return StdioServerParameters(
        command=str(uv),
        args=[
            "--directory",
            str(checkout),
            "run",
            "windows-mcp",
            "serve",
            "--exclude-tools",
            "PowerShell,Registry",
        ],
        env={"ANONYMIZED_TELEMETRY": "false"},
        cwd=str(checkout),
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
