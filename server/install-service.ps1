# Install Claude Code Sessions Dashboard server as a Windows service using NSSM or as a scheduled task
# Run as Administrator

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$appPy = Join-Path $scriptDir "app.py"
$config = Join-Path $scriptDir "server-config.yaml"
$python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

if (-not (Test-Path $appPy)) {
    Write-Error "app.py not found at $appPy"
    exit 1
}

# Check if NSSM is available (preferred method)
$nssm = Get-Command nssm -ErrorAction SilentlyContinue

if ($nssm) {
    Write-Host "Installing Windows service via NSSM..."
    nssm install claude-dashboard $python $appPy
    nssm set claude-dashboard AppDirectory $scriptDir
    nssm set claude-dashboard AppEnvironmentExtra "CLAUDE_DASHBOARD_CONFIG=$config"
    nssm set claude-dashboard Description "Claude Code Sessions Dashboard"
    nssm set claude-dashboard Start SERVICE_AUTO_START
    nssm start claude-dashboard
    Write-Host "Done! Service installed and started."
    Write-Host "  nssm status claude-dashboard"
    Write-Host "  nssm stop claude-dashboard"
    Write-Host "  nssm restart claude-dashboard"
    Write-Host "  nssm remove claude-dashboard confirm   (to uninstall)"
} else {
    Write-Host "NSSM not found. Installing as a scheduled task (runs at logon)..."
    $action = New-ScheduledTaskAction -Execute $python -Argument $appPy -WorkingDirectory $scriptDir
    $trigger = New-ScheduledTaskTrigger -AtLogon
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0
    Register-ScheduledTask -TaskName "ClaudeDashboard" -Action $action -Trigger $trigger -Settings $settings -Description "Claude Code Sessions Dashboard"
    Start-ScheduledTask -TaskName "ClaudeDashboard"
    Write-Host "Done! Scheduled task created and started."
    Write-Host "  Get-ScheduledTask -TaskName ClaudeDashboard"
    Write-Host "  Stop-ScheduledTask -TaskName ClaudeDashboard"
    Write-Host "  Start-ScheduledTask -TaskName ClaudeDashboard"
    Write-Host "  Unregister-ScheduledTask -TaskName ClaudeDashboard   (to uninstall)"
}
