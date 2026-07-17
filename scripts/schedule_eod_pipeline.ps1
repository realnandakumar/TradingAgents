# EOD pipeline scheduling helper.
#
# Default: REMOVE automated EOD tasks (manual Sync now from Command Center).
#   powershell -ExecutionPolicy Bypass -File scripts/schedule_eod_pipeline.ps1
#
# Optional: re-enable 4:10 PM weekday + logon catch-up (IST timezone).
#   powershell -ExecutionPolicy Bypass -File scripts/schedule_eod_pipeline.ps1 -Enable
#
# Manual sync (preferred):
#   Dashboard Command Center → Sync now
#   python scripts/run_eod_pipeline.py --force

param(
    [switch]$Enable
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = (Get-Command python).Source

# Always clear legacy + current EOD automation first.
Unregister-ScheduledTask -TaskName "TradingAgents-EODPipeline" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "TradingAgents-EODCatchup" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "TradingAgents-PriceSync" -Confirm:$false -ErrorAction SilentlyContinue

if (-not $Enable) {
    Write-Host "Removed TradingAgents-EODPipeline / EODCatchup / PriceSync (if present)."
    Write-Host "EOD is manual: Command Center Sync now, or:"
    Write-Host "  python scripts/run_eod_pipeline.py --force"
    exit 0
}

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3)

$EodAction = New-ScheduledTaskAction `
    -Execute $Python `
    -Argument "scripts/run_eod_pipeline.py" `
    -WorkingDirectory $RepoRoot
$EodTrigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday `
    -At "4:10PM"

Register-ScheduledTask -TaskName "TradingAgents-EODPipeline" -Action $EodAction -Trigger $EodTrigger -Settings $Settings `
    -Description "Unified EOD price sync + screeners + dailies (4:10 PM IST; optional automation)"

$CatchupAction = New-ScheduledTaskAction `
    -Execute $Python `
    -Argument "scripts/run_eod_if_missed.py" `
    -WorkingDirectory $RepoRoot
$CatchupTrigger = New-ScheduledTaskTrigger -AtLogOn
$CatchupSettings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3)

Register-ScheduledTask -TaskName "TradingAgents-EODCatchup" -Action $CatchupAction -Trigger $CatchupTrigger -Settings $CatchupSettings `
    -Description "Run EOD pipeline at logon if today's sync was missed"

Write-Host "Scheduled TradingAgents-EODPipeline at 4:10 PM (Mon-Fri)."
Write-Host "Scheduled TradingAgents-EODCatchup at user logon."
Write-Host "Ensure Windows timezone is IST."
