"""stdio MCP server for AI Office plus the forwarded Windows desktop tools."""

from __future__ import annotations

import sys

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from ai_office_mcp.forward import forward_windows_mcp
from ai_office_mcp.office import launch, open_document, overlay_command, recent_files, session_command

OFFICE_TOOL_NAMES = frozenset(
    {
        "Launch",
        "Open",
        "Recent",
        "OfficeScreenshot",
        "Record",
        "Desktops",
        "SessionStatus",
    }
)

INSTRUCTIONS = """
Run AI Office by CloudComputerAI on this Windows PC.
Launch, Open, and Recent operate the installed CloudComputerAI.exe.
OfficeScreenshot and Record open the AI Office screenshot overlay and the Cap recorder. They do not return image bytes.
Screenshot is the computer-use picture tool. Snapshot and DisplayInventory describe the monitors before a click.
PowerShell and Registry are not available.
Do not use these tools on mail, browser profiles, or ad accounts unless the user asks for that exact task.
""".strip()


def office_tools() -> list[types.Tool]:
    empty = {"type": "object", "properties": {}, "additionalProperties": False}
    return [
        types.Tool(
            name="Launch",
            description=(
                "Open AI Office by CloudComputerAI if it is not already running. "
                "Returns the window title. Does not click the desktop."
            ),
            inputSchema=empty,
        ),
        types.Tool(
            name="Open",
            description=(
                "Open one existing document in AI Office. Pass an absolute path whose extension "
                "AI Office already accepts, such as docx, xlsx, pptx, pdf, or csv."
            ),
            inputSchema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        ),
        types.Tool(
            name="Recent",
            description="List file paths from AI Office recent.json. Returns paths only.",
            inputSchema=empty,
        ),
        types.Tool(
            name="OfficeScreenshot",
            description=(
                "Start the AI Office screenshot overlay (--screenshot). Print Screen and "
                "Win+Shift+X stay on that tool. This does not return image bytes. "
                "Use Screenshot for a picture in the chat."
            ),
            inputSchema=empty,
        ),
        types.Tool(
            name="Record",
            description="Start the AI Office Cap recorder (--record). This opens the recorder window.",
            inputSchema=empty,
        ),
        types.Tool(
            name="Desktops",
            description="Run CloudComputerAI.exe --desktops and return its text.",
            inputSchema=empty,
        ),
        types.Tool(
            name="SessionStatus",
            description="Run CloudComputerAI.exe --session-status and return its text.",
            inputSchema=empty,
        ),
    ]


def _text(text: str, error: bool = False) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=text)],
        isError=error,
    )


def _call_office(name: str, arguments: dict[str, object]) -> types.CallToolResult:
    try:
        if name == "Launch":
            return _text(launch())
        if name == "Open":
            path = arguments.get("path")
            if not isinstance(path, str) or not path.strip():
                return _text("path is required", error=True)
            return _text(open_document(path))
        if name == "Recent":
            return _text(recent_files())
        if name == "OfficeScreenshot":
            return _text(overlay_command("--screenshot"))
        if name == "Record":
            return _text(overlay_command("--record"))
        if name == "Desktops":
            return _text(session_command("--desktops"))
        if name == "SessionStatus":
            return _text(session_command("--session-status"))
    except Exception as exc:
        return _text(str(exc), error=True)
    return _text(f"Unknown office tool: {name}", error=True)


async def serve() -> None:
    server = Server("ai-office", instructions=INSTRUCTIONS)
    local_tools = office_tools()
    async with forward_windows_mcp(OFFICE_TOOL_NAMES) as forwarder:
        catalog = local_tools + forwarder.tools

        @server.list_tools()
        async def list_tools() -> list[types.Tool]:
            return catalog

        @server.call_tool()
        async def call_tool(name: str, arguments: dict[str, object]) -> types.CallToolResult:
            if name in OFFICE_TOOL_NAMES:
                return _call_office(name, arguments or {})
            try:
                return await forwarder.call(name, arguments or {})
            except Exception as exc:
                return _text(str(exc), error=True)

        print(
            f"ai-office-mcp ready with {len(catalog)} tools",
            file=sys.stderr,
        )
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
