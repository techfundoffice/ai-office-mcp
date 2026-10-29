import json
from pathlib import Path

import mcp.types as types
import pytest

from ai_office_mcp import forward
from ai_office_mcp.forward import EXCLUDED_TOOLS, REQUIRED_TOOLS, WINDOWS_MCP_COMMIT, select_forwarded
from ai_office_mcp.office import document_error, parse_recent, quote_arg


def test_quote_arg_wraps_spaces() -> None:
    assert quote_arg(r"C:\Program Files\CloudComputerAI.exe") == r'"C:\Program Files\CloudComputerAI.exe"'
    assert quote_arg("notepad") == "notepad"


def test_document_error_rejects_missing_and_unknown_types(tmp_path: Path) -> None:
    missing = tmp_path / "note.txt"
    assert document_error(missing) == f"File not found: {missing}"
    missing.write_text("x", encoding="utf-8")
    assert "does not open" in (document_error(missing) or "")
    csv_path = tmp_path / "sheet.csv"
    csv_path.write_text("a,b\n", encoding="utf-8")
    assert document_error(csv_path) is None


def test_parse_recent_keeps_strings_only() -> None:
    raw = json.dumps(["C:\\docs\\a.csv", 3, "C:\\docs\\b.docx"])
    assert parse_recent(raw) == ["C:\\docs\\a.csv", "C:\\docs\\b.docx"]


def test_parse_recent_rejects_a_dict() -> None:
    with pytest.raises(ValueError):
        parse_recent("{}")


def _tool(name: str) -> types.Tool:
    return types.Tool(name=name, description=name, inputSchema={"type": "object"})


def test_select_forwarded_rejects_excluded_and_collisions() -> None:
    office = frozenset({"Launch", "Open"})
    tools = [_tool(name) for name in sorted(REQUIRED_TOOLS)]
    assert [tool.name for tool in select_forwarded(tools, office)] == sorted(REQUIRED_TOOLS)

    with pytest.raises(RuntimeError, match="excluded"):
        select_forwarded(tools + [_tool("PowerShell")], office)
    with pytest.raises(RuntimeError, match="collide"):
        select_forwarded(tools + [_tool("Launch")], office)
    with pytest.raises(RuntimeError, match="missing"):
        select_forwarded([_tool("App")], office)

    assert "PowerShell" in EXCLUDED_TOOLS
    assert "Registry" in EXCLUDED_TOOLS


def test_launch_uses_the_venv_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    exe = tmp_path / "windows-mcp.exe"
    exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(forward, "bundled_windows_mcp", lambda: exe)
    command, args, cwd = forward.windows_mcp_launch()
    assert command == str(exe)
    assert args == ["serve", "--exclude-tools", "PowerShell,Registry"]
    assert cwd is None


def test_launch_uses_uv_from_the_user_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(forward, "bundled_windows_mcp", lambda: None)
    monkeypatch.delenv("WINDOWS_MCP_DIR", raising=False)
    monkeypatch.delenv("UV_EXE", raising=False)
    home = tmp_path / "home"
    uv = home / ".local" / "bin" / "uv.exe"
    uv.parent.mkdir(parents=True)
    uv.write_text("", encoding="utf-8")
    monkeypatch.setattr(forward, "user_home", lambda: home)
    monkeypatch.setattr(forward.shutil, "which", lambda _name: None)
    command, args, cwd = forward.windows_mcp_launch()
    assert command == str(uv)
    assert WINDOWS_MCP_COMMIT in " ".join(args)
    assert cwd is None
    assert "projects\\Windows-MCP" not in command
