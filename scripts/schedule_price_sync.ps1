# Register daily price-cache sync after NSE market close (4:00 PM IST weekdays).
# Requires Windows timezone set to IST (India Standard Time).
#
# Run once from elevated PowerShell in the repo root:
#   powershell -ExecutionPolicy Bypass -File scripts/schedule_price_sync.ps1
#
# To remove:
#   Unregister-ScheduledTask -TaskName "TradingAgents-PriceSync" -Confirm:$false

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = (Get-Command python).Source
$Action = New-ScheduledTaskAction -Execute $Python -Argument "scripts/sync_price_cache.py --mode incremental" -WorkingDirectory $RepoRoot
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -AllowStartIfOnBatteries
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At "4:00PM"

Unregister-ScheduledTask -TaskName "TradingAgents-PriceSync" -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName "TradingAgents-PriceSync" -Action $Action -Trigger $Trigger -Settings $Settings `
    -Description "Incremental OHLCV price cache sync after market close (4:00 PM IST weekdays)"
Write-Host "Scheduled TradingAgents-PriceSync at 4:00 PM (Mon-Fri)"
Write-Host ""
Write-Host "Done. Ensure Windows timezone is IST."
