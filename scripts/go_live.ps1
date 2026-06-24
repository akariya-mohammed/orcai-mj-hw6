# HW6 go-live helper — run this right before the cross-group match.
# Generates per-server tokens (if missing), starts both MCP servers with the
# reliable mock NL backend, and prints the next steps (ngrok + what to send).
#
#   powershell -ExecutionPolicy Bypass -File scripts\go_live.ps1
#
# IMPORTANT: set game.grid_size + game.origin in config.yaml to the AGREED values
# (e.g. [10,10] / 0) BEFORE running this — the servers read the board from config.

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path .env)) { New-Item -ItemType File .env | Out-Null }

function Ensure-Token($name) {
    $existing = (Get-Content .env -ErrorAction SilentlyContinue |
        Where-Object { $_ -match "^$name=(.+)$" })
    if (-not $existing) {
        $tok = & .\.venv\Scripts\python.exe -c "import secrets;print(secrets.token_urlsafe(32))"
        Add-Content .env "$name=$tok"
        Write-Host "generated $name"
    }
}

Ensure-Token "COP_MCP_TOKEN"
Ensure-Token "THIEF_MCP_TOKEN"

# Load .env into this process so the servers inherit the tokens.
Get-Content .env | ForEach-Object {
    if ($_ -match "^\s*(\w+)\s*=\s*(.*)$") { Set-Item "env:$($matches[1])" $matches[2] }
}
$env:HW6_LLM_PROVIDER = "mock"   # deterministic, reliable canonical NL

Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-m", "src.servers.cop_server"
Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-m", "src.servers.thief_server"
Start-Sleep -Seconds 5

$grid = (Select-String -Path config.yaml -Pattern "grid_size").Line.Trim()
$origin = (Select-String -Path config.yaml -Pattern "^\s*origin:").Line.Trim()
Write-Host ""
Write-Host "==================== HW6 servers up ===================="
Write-Host "  board: $grid   $origin   (must match what you agreed!)"
Write-Host "  Cop   MCP -> http://127.0.0.1:8765/mcp"
Write-Host "  Thief MCP -> http://127.0.0.1:8766/mcp"
Write-Host ""
Write-Host "  Next (two more terminals):  ngrok http 8765    and    ngrok http 8766"
Write-Host "  Send the partner PRIVATELY: the two https://....ngrok-free.app/mcp URLs"
Write-Host "  plus COP_MCP_TOKEN and THIEF_MCP_TOKEN from your .env."
Write-Host "  Keep ngrok + these servers OPEN through smoke + all 6 sub-games + compare."
Write-Host "========================================================"
