#!/bin/bash
set -euo pipefail

LABEL="herdr-remote.service"
UNIT_FILE="$HOME/.config/systemd/user/$LABEL"

systemctl --user disable --now "$LABEL" >/dev/null 2>&1 || true
rm -f "$UNIT_FILE"
systemctl --user daemon-reload

echo "Stopped and removed $LABEL"
