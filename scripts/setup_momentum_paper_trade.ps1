# Bootstrap momentum paper trading (book + first daily run + scheduler).
#
# Run from repo root:
#   powershell -ExecutionPolicy Bypass -File scripts/setup_momentum_paper_trade.ps1
#
# Optional: skip scheduler registration
#   powershell -ExecutionPolicy Bypass -File scripts/setup_momentum_paper_trade.ps1 -NoSchedule

param([switch]$NoSchedule)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Home = Join-Path $env:USERPROFILE ".tradingagents\momentum"

New-Item -ItemType Directory -Force -Path $Home | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Home "daily") | Out-Null
Write-Host "Momentum book directory: $Home"

$env:PYTHONPATH = $RepoRoot
Push-Location $RepoRoot
try {
    Write-Host "`nRunning momentum daily (force)..."
    python scripts/run_momentum_daily_now.py
    Write-Host "`nPortfolio snapshot:"
    python scripts/momentum_dashboard_snapshot.py
} finally {
    Pop-Location
}

if (-not $NoSchedule) {
    Write-Host "`nRegistering scheduled tasks (9:30, 11:45, 14:30)..."
    & (Join-Path $RepoRoot "scripts\schedule_momentum_daily.ps1")
}

Write-Host ""
Write-Host "Momentum paper trade ready."
Write-Host "  Book:     ~/.tradingagents/momentum/positions.json"
Write-Host "  CLI:      tradingagents momentum-positions"
Write-Host "  Desk:     http://localhost:3000/momentum  (npm run dev in dashboard/)"
Write-Host "  Daily:    tradingagents momentum-daily"
