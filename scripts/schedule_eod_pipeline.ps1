# Register unified EOD pipeline after NSE market close (4:10 PM IST weekdays).
# Also runs catch-up at user logon if today's EOD was missed (PC was off).
#
# Requires Windows timezone set to IST (India Standard Time).
#
# Run once from elevated PowerShell in the repo root:
#   powershell -ExecutionPolicy Bypass -File scripts/schedule_eod_pipeline.ps1
#
# To remove:
#   Unregister-ScheduledTask -TaskName "TradingAgents-EODPipeline" -Confirm:$false
#   Unregister-ScheduledTask -TaskName "TradingAgents-EODCatchup" -Confirm:$false

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = (Get-Command python).Source

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3)

# --- 4:10 PM weekday EOD (runs when available if PC was off at trigger time) ---
$EodAction = New-ScheduledTaskAction `
    -Execute $Python `
    -Argument "scripts/run_eod_pipeline.py" `
    -WorkingDirectory $RepoRoot
$EodTrigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday `
    -At "4:10PM"

Unregister-ScheduledTask -TaskName "TradingAgents-EODPipeline" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "TradingAgents-PriceSync" -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName "TradingAgents-EODPipeline" -Action $EodAction -Trigger $EodTrigger -Settings $Settings `
    -Description "Unified EOD price sync + screeners + dailies (4:10 PM IST; runs when available if missed)"

# --- Logon catch-up: run only if today's EOD has not completed ---
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

Unregister-ScheduledTask -TaskName "TradingAgents-EODCatchup" -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName "TradingAgents-EODCatchup" -Action $CatchupAction -Trigger $CatchupTrigger -Settings $CatchupSettings `
    -Description "Run EOD pipeline at logon if today's sync was missed (PC was off at 4:10 PM)"

Write-Host "Scheduled TradingAgents-EODPipeline at 4:10 PM (Mon-Fri, StartWhenAvailable)"
Write-Host "Scheduled TradingAgents-EODCatchup at user logon (if today's EOD not done)"
Write-Host "Removed legacy TradingAgents-PriceSync if present."
Write-Host ""
Write-Host "Done. Ensure Windows timezone is IST."
