#!/bin/bash
set -euo pipefail

LABEL="com.herdr-remote.service"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs/herdr-remote"
CLOUDFLARED_CONFIG="${CLOUDFLARED_CONFIG:-$HOME/.cloudflared/config-herdr-remote.yml}"

generate_token() {
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex 16
    else
        uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-'
    fi
}

ensure_env() {
    if [ ! -f "$ENV_FILE" ]; then
        umask 077
        cat > "$ENV_FILE" <<EOF
HERDR_RELAY_PORT=8375
HERDR_RELAY_TOKEN=$(generate_token)
CLOUDFLARED_CONFIG=$CLOUDFLARED_CONFIG
EOF
        echo "Created $ENV_FILE"
        return
    fi

    chmod 600 "$ENV_FILE"
    if ! grep -q '^HERDR_RELAY_PORT=' "$ENV_FILE"; then
        printf '\nHERDR_RELAY_PORT=8375\n' >> "$ENV_FILE"
    fi
    if ! grep -q '^HERDR_RELAY_TOKEN=' "$ENV_FILE"; then
        printf '\nHERDR_RELAY_TOKEN=%s\n' "$(generate_token)" >> "$ENV_FILE"
    fi
    if ! grep -q '^CLOUDFLARED_CONFIG=' "$ENV_FILE"; then
        printf '\nCLOUDFLARED_CONFIG=%s\n' "$CLOUDFLARED_CONFIG" >> "$ENV_FILE"
    fi
}

if [ ! -r "$CLOUDFLARED_CONFIG" ]; then
    echo "Missing Cloudflare tunnel config: $CLOUDFLARED_CONFIG"
    echo "Create it first, or set CLOUDFLARED_CONFIG before running this installer."
    exit 1
fi

ensure_env
chmod +x "$SCRIPT_DIR/herdr-remote-service.sh"
mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$SCRIPT_DIR/herdr-remote-service.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
        <key>NetworkState</key>
        <true/>
    </dict>
    <key>ThrottleInterval</key>
    <integer>10</integer>
    <key>WorkingDirectory</key>
    <string>$(cd "$SCRIPT_DIR/.." && pwd)</string>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/service.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/service.err</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$UID" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID" "$PLIST"
launchctl enable "gui/$UID/$LABEL"
launchctl kickstart -k "gui/$UID/$LABEL"

echo "Installed and started $LABEL"
echo "Plist: $PLIST"
echo "Env:   $ENV_FILE"
echo "Logs:  $LOG_DIR/service.log and $LOG_DIR/service.err"
