#!/usr/bin/env bash
set -euo pipefail

# Install claude-sessions client as a system service (Linux systemd or macOS launchd)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CLIENT_PY="$SCRIPT_DIR/client.py"
CONFIG="$SCRIPT_DIR/client-config.yaml"
VENV_DIR="$PROJECT_DIR/.venv"

if [ ! -f "$CLIENT_PY" ]; then
    echo "Error: client.py not found at $CLIENT_PY"
    exit 1
fi

if [ ! -f "$CONFIG" ]; then
    echo "Error: client-config.yaml not found. Copy client-config.yaml and edit it first."
    exit 1
fi

# Install uv if not present
if ! command -v uv &>/dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Create venv and install deps (uv manages its own Python if needed)
echo "Setting up Python environment with uv..."
uv venv "$VENV_DIR" 2>/dev/null || true
uv pip install -r "$SCRIPT_DIR/requirements.txt" --python "$VENV_DIR/bin/python" --quiet

PYTHON="$VENV_DIR/bin/python"

case "$(uname -s)" in
    Linux)
        echo "Installing systemd service..."
        SERVICE_FILE="/etc/systemd/system/claude-dashboard-client.service"
        sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Claude Code Sessions Dashboard Client
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$SCRIPT_DIR
ExecStart=$PYTHON $CLIENT_PY --daemon --config $CONFIG
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        sudo systemctl daemon-reload
        sudo systemctl enable claude-dashboard-client
        sudo systemctl start claude-dashboard-client
        echo "Done! Client service installed and started."
        echo ""
        echo "Manage with:"
        echo "  sudo systemctl status claude-dashboard-client"
        echo "  sudo systemctl stop claude-dashboard-client"
        echo "  sudo systemctl restart claude-dashboard-client"
        echo "  sudo journalctl -u claude-dashboard-client -f"
        ;;

    Darwin)
        echo "Installing launchd service..."
        PLIST_FILE="$HOME/Library/LaunchAgents/com.claude-dashboard-client.plist"
        mkdir -p "$HOME/Library/LaunchAgents"
        cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.claude-dashboard-client</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$CLIENT_PY</string>
        <string>--daemon</string>
        <string>--config</string>
        <string>$CONFIG</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/claude-dashboard-client.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/claude-dashboard-client.err</string>
</dict>
</plist>
EOF
        launchctl unload "$PLIST_FILE" 2>/dev/null || true
        launchctl load "$PLIST_FILE"
        echo "Done! Client service installed and started."
        echo ""
        echo "Manage with:"
        echo "  launchctl list | grep claude-dashboard-client"
        echo "  launchctl stop com.claude-dashboard-client"
        echo "  launchctl start com.claude-dashboard-client"
        echo "  tail -f /tmp/claude-dashboard-client.log"
        ;;

    *)
        echo "Unsupported OS: $(uname -s). Use install-service.ps1 for Windows."
        exit 1
        ;;
esac
