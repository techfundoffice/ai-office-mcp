# AI Office MCP

This server lets a Grok TUI on a Windows PC run AI Office by CloudComputerAI on that same PC. It launches the installed `CloudComputerAI.exe`, opens a document the exe already accepts, and starts Windows-MCP for clicks and typing.

It controls the PC where it is running. It does not reach another computer.

The installed AI Office app is not modified. PowerShell and Registry are not published. `windows-mcp install` is not run.

Windows-MCP is pinned to commit `277db1bed9612fdfd242a50581f83ae981b07ff7` from https://github.com/CursorTouch/Windows-MCP. `uv sync` installs that pin into this project. A separate checkout is optional.

## Install on a Windows PC

Requirements: Windows, AI Office installed for that user, [uv](https://docs.astral.sh/uv/) on PATH or at `%USERPROFILE%\.local\bin\uv.exe`, and Python 3.14 (uv can install it).

```powershell
git clone https://github.com/techfundoffice/ai-office-mcp.git
Set-Location ai-office-mcp
uv sync
```

Add this to `%USERPROFILE%\.grok\config.toml`. Replace the directory with the folder that was cloned. Use the full path to `uv.exe` when `uv` is not on PATH.

```toml
[mcp_servers.ai-office]
command = "uv"
args = ["--directory", "C:\\path\\to\\ai-office-mcp", "run", "ai-office-mcp"]
env = { ANONYMIZED_TELEMETRY = "false" }
enabled = true
startup_timeout_sec = 120
```

Reload MCP in the Grok TUI. The first start installs nothing further when `uv sync` has already run.

`Launch` looks for `%LOCALAPPDATA%\Programs\CloudComputerAI\CloudComputerAI.exe`.

## Tools

- `Launch` starts AI Office when it is not running and returns the window title.
- `Open` hands one existing document path to the exe.
- `Recent` reads `%APPDATA%\CloudComputerAI\recent.json`.
- `OfficeScreenshot` runs `--screenshot`. That opens the screenshot overlay. It does not return image bytes. Print Screen and Win+Shift+X stay on that overlay.
- `Record` runs `--record` and opens Cap.
- `Desktops` and `SessionStatus` run `--desktops` and `--session-status`.
- Desktop tools from Windows-MCP: Snapshot, Screenshot, Click, Type, and the rest of that set except PowerShell and Registry.

`Screenshot` returns a picture to the chat. `OfficeScreenshot` is the overlay.

## This PC

Rollback of the Grok config on this machine is `C:\Users\Admin\.grok\config.toml.bak-2026-10-29-ai-office`. Copy it over `config.toml` and reload MCP. That file is not in this repo.
