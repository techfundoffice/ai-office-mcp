$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$uv = $null
$cmd = Get-Command uv -ErrorAction SilentlyContinue
if ($cmd) {
    $uv = $cmd.Source
} else {
    $candidate = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
    if (Test-Path -LiteralPath $candidate) { $uv = $candidate }
}
if (-not $uv) {
    throw "Install uv from https://docs.astral.sh/uv/ and run this script again."
}

& $uv sync
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$dir = $root.Replace("\", "\\")
$uvToml = $uv.Replace("\", "\\")
Write-Output ""
Write-Output "Add this block to $env:USERPROFILE\.grok\config.toml and reload MCP:"
Write-Output ""
Write-Output "[mcp_servers.ai-office]"
Write-Output "command = `"$uvToml`""
Write-Output "args = [`"--directory`", `"$dir`", `"run`", `"ai-office-mcp`"]"
Write-Output "env = { ANONYMIZED_TELEMETRY = `"false`" }"
Write-Output "enabled = true"
Write-Output "startup_timeout_sec = 120"
