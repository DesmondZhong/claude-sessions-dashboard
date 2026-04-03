#!/usr/bin/env bash
set -euo pipefail

# Uninstall claude-sessions-dashboard service

case "$(uname -s)" in
    Linux)
        echo "Removing systemd service..."
        sudo systemctl stop claude-dashboard 2>/dev/null || true
        sudo systemctl disable claude-dashboard 2>/dev/null || true
        sudo rm -f /etc/systemd/system/claude-dashboard.service
        sudo systemctl daemon-reload
        echo "Done."
        ;;

    Darwin)
        echo "Removing launchd service..."
        PLIST_FILE="$HOME/Library/LaunchAgents/com.claude-dashboard.plist"
        launchctl unload "$PLIST_FILE" 2>/dev/null || true
        rm -f "$PLIST_FILE"
        echo "Done."
        ;;

    *)
        echo "Unsupported OS: $(uname -s). Use uninstall-service.ps1 for Windows."
        exit 1
        ;;
esac
