# AI Office MCP

This server lets the Grok TUI run AI Office by CloudComputerAI on this Windows PC. It launches the installed `CloudComputerAI.exe`, opens a document the exe already accepts, and republishes the local [Windows-MCP](https://github.com/CursorTouch/Windows-MCP) checkout for clicks and typing.

The installed app is not modified. `app.asar` is not patched. `windows-mcp install` is not run. PowerShell and Registry are not published.

Windows-MCP checkout pin: `277db1bed9612fdfd242a50581f83ae981b07ff7` on `main` at `C:\Users\Admin\projects\Windows-MCP`. This repo does not vendor that checkout.

## Tools

Office tools talk to the installed exe:

- `Launch` starts AI Office when it is not running and returns the window title.
- `Open` hands one existing document path to the exe.
- `Recent` reads `%APPDATA%\CloudComputerAI\recent.json`.
- `OfficeScreenshot` runs `--screenshot`. That opens the screenshot overlay. It does not return image bytes. Print Screen and Win+Shift+X stay on that overlay.
- `Record` runs `--record` and opens Cap.
- `Desktops` and `SessionStatus` run `--desktops` and `--session-status`.

`Screenshot` is the forwarded computer-use tool that returns a picture. The office overlay tool is named `OfficeScreenshot` so the two do not share a name.

## Rollback

Grok's `config.toml` is not in this repo. It holds other servers' credentials.

Before pointing Grok at this server, copy the live config to `C:\Users\Admin\.grok\config.toml.bak-2026-10-29-ai-office`. Restore that file over `config.toml` and reload MCP to remove this server and turn the standalone `windows-mcp` entry back on.

Code rollback is `git checkout` or `git revert` of a commit on `main`, then the config restore if Grok was already pointed here.

## Run

```powershell
C:\Users\Admin\.local\bin\uv.exe --directory C:\Users\Admin\projects\ai-office-mcp run ai-office-mcp
```

The process speaks MCP on stdin and stdout. It starts Windows-MCP with `ANONYMIZED_TELEMETRY=false` and `--exclude-tools PowerShell,Registry`.
