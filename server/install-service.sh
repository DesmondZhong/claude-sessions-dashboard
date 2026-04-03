#!/usr/bin/env bash
set -euo pipefail

# Install claude-sessions-dashboard as a system service (Linux systemd or macOS launchd)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_PY="$SCRIPT_DIR/app.py"
CONFIG="$SCRIPT_DIR/server-config.yaml"
PYTHON="${PYTHON:-python3}"

if [ ! -f "$APP_PY" ]; then
    echo "Error: app.py not found at $APP_PY"
    exit 1
fi

case "$(uname -s)" in
    Linux)
        echo "Installing systemd service..."
        SERVICE_FILE="/etc/systemd/system/claude-dashboard.service"
        sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Claude Sessions Dashboard
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$SCRIPT_DIR
Environment=CLAUDE_DASHBOARD_CONFIG=$CONFIG
ExecStart=$PYTHON $APP_PY
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
        sudo systemctl daemon-reload
        sudo systemctl enable claude-dashboard
        sudo systemctl start claude-dashboard
        echo "Done! Service installed and started."
        echo "  sudo systemctl status claude-dashboard"
        echo "  sudo systemctl stop claude-dashboard"
        echo "  sudo systemctl restart claude-dashboard"
        echo "  sudo journalctl -u claude-dashboard -f"
        ;;

    Darwin)
        echo "Installing launchd service..."
        PLIST_FILE="$HOME/Library/LaunchAgents/com.claude-dashboard.plist"
        mkdir -p "$HOME/Library/LaunchAgents"
        cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.claude-dashboard</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$APP_PY</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>CLAUDE_DASHBOARD_CONFIG</key>
        <string>$CONFIG</string>
    </dict>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/claude-dashboard.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/claude-dashboard.err</string>
</dict>
</plist>
EOF
        launchctl unload "$PLIST_FILE" 2>/dev/null || true
        launchctl load "$PLIST_FILE"
        echo "Done! Service installed and started."
        echo "  launchctl list | grep claude-dashboard"
        echo "  launchctl stop com.claude-dashboard"
        echo "  launchctl start com.claude-dashboard"
        echo "  tail -f /tmp/claude-dashboard.log"
        ;;

    *)
        echo "Unsupported OS: $(uname -s). Use install-service.ps1 for Windows."
        exit 1
        ;;
esac
