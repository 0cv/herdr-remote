#!/bin/bash
set -euo pipefail

LABEL="com.herdr-remote.service"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$UID" "$PLIST" >/dev/null 2>&1 || true
rm -f "$PLIST"

echo "Stopped and removed $LABEL"
