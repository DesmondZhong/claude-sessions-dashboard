# Install Claude Code Sessions Dashboard client as a Windows service using NSSM or as a scheduled task
# Run as Administrator

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$clientPy = Join-Path $scriptDir "client.py"
$config = Join-Path $scriptDir "client-config.yaml"
$python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

if (-not (Test-Path $clientPy)) {
    Write-Error "client.py not found at $clientPy"
    exit 1
}

if (-not (Test-Path $config)) {
    Write-Error "client-config.yaml not found. Copy and edit it first."
    exit 1
}

$nssm = Get-Command nssm -ErrorAction SilentlyContinue

if ($nssm) {
    Write-Host "Installing Windows service via NSSM..."
    nssm install claude-dashboard-client $python "$clientPy --daemon --config $config"
    nssm set claude-dashboard-client AppDirectory $scriptDir
    nssm set claude-dashboard-client Description "Claude Code Sessions Dashboard Client"
    nssm set claude-dashboard-client Start SERVICE_AUTO_START
    nssm start claude-dashboard-client
    Write-Host "Done! Client service installed and started."
    Write-Host "  nssm status claude-dashboard-client"
    Write-Host "  nssm stop claude-dashboard-client"
    Write-Host "  nssm restart claude-dashboard-client"
    Write-Host "  nssm remove claude-dashboard-client confirm   (to uninstall)"
} else {
    Write-Host "NSSM not found. Installing as a scheduled task (runs at logon)..."
    $action = New-ScheduledTaskAction -Execute $python -Argument "$clientPy --daemon --config $config" -WorkingDirectory $scriptDir
    $trigger = New-ScheduledTaskTrigger -AtLogon
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0
    Register-ScheduledTask -TaskName "ClaudeDashboardClient" -Action $action -Trigger $trigger -Settings $settings -Description "Claude Code Sessions Dashboard Client"
    Start-ScheduledTask -TaskName "ClaudeDashboardClient"
    Write-Host "Done! Scheduled task created and started."
    Write-Host "  Get-ScheduledTask -TaskName ClaudeDashboardClient"
    Write-Host "  Stop-ScheduledTask -TaskName ClaudeDashboardClient"
    Write-Host "  Start-ScheduledTask -TaskName ClaudeDashboardClient"
    Write-Host "  Unregister-ScheduledTask -TaskName ClaudeDashboardClient   (to uninstall)"
}
