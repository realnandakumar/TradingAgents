# Register nw-envelope-daily at 9:30, 11:45, and 14:30 Mon-Fri.
# Requires Windows timezone set to IST.
#
# Run once from elevated PowerShell in the repo root:
#   powershell -ExecutionPolicy Bypass -File scripts/schedule_nw_envelope_daily.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = (Get-Command python).Source
$Action = New-ScheduledTaskAction -Execute $Python -Argument "-m cli.main nw-envelope-daily" -WorkingDirectory $RepoRoot
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -AllowStartIfOnBatteries

$Times = @(
    @{ Name = "TradingAgents-NWE-0930"; At = "9:30AM";  Label = "9:30 AM" },
    @{ Name = "TradingAgents-NWE-1145"; At = "11:45AM"; Label = "11:45 AM" },
    @{ Name = "TradingAgents-NWE-1430"; At = "2:30PM"; Label = "2:30 PM" }
)

foreach ($Slot in $Times) {
    Unregister-ScheduledTask -TaskName $Slot.Name -Confirm:$false -ErrorAction SilentlyContinue
    $Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $Slot.At
    Register-ScheduledTask -TaskName $Slot.Name -Action $Action -Trigger $Trigger -Settings $Settings `
        -Description "NW Envelope screener + paper portfolio at $($Slot.Label) IST weekdays"
    Write-Host "Scheduled $($Slot.Name) at $($Slot.Label) (Mon-Fri)"
}

Write-Host ""
Write-Host "Done. Logs: ~/.tradingagents/nw_envelope/daily/"
