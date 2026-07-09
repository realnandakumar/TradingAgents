# Register swing-daily at 9:30, 11:45, and 14:30 (2:30 PM) Mon-Fri.
# Requires Windows timezone set to IST (India Standard Time).
#
# Run once from elevated PowerShell in the repo root:
#   powershell -ExecutionPolicy Bypass -File scripts/schedule_swing_daily.ps1
#
# To remove old single-task schedule:
#   Unregister-ScheduledTask -TaskName "TradingAgents-SwingDaily" -Confirm:$false

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = (Get-Command python).Source
$Action = New-ScheduledTaskAction -Execute $Python -Argument "-m cli.main swing-daily" -WorkingDirectory $RepoRoot
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -AllowStartIfOnBatteries

$Times = @(
    @{ Name = "TradingAgents-Swing-0930"; At = "9:30AM";  Label = "9:30 AM" },
    @{ Name = "TradingAgents-Swing-1145"; At = "11:45AM"; Label = "11:45 AM" },
    @{ Name = "TradingAgents-Swing-1430"; At = "2:30PM"; Label = "2:30 PM" }
)

# Remove legacy single task if present
$Legacy = Get-ScheduledTask -TaskName "TradingAgents-SwingDaily" -ErrorAction SilentlyContinue
if ($Legacy) {
    Unregister-ScheduledTask -TaskName "TradingAgents-SwingDaily" -Confirm:$false
    Write-Host "Removed legacy task TradingAgents-SwingDaily"
}

foreach ($Slot in $Times) {
    Unregister-ScheduledTask -TaskName $Slot.Name -Confirm:$false -ErrorAction SilentlyContinue
    $Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $Slot.At
    Register-ScheduledTask -TaskName $Slot.Name -Action $Action -Trigger $Trigger -Settings $Settings `
        -Description "Swing screener + paper portfolio at $($Slot.Label) IST weekdays"
    Write-Host "Scheduled $($Slot.Name) at $($Slot.Label) (Mon-Fri)"
}

Write-Host ""
Write-Host "Done. Ensure Windows timezone is IST. Logs: ~/.tradingagents/swing/daily/"
