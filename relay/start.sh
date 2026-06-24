#!/bin/bash
set -e
echo "🐑 herdr-remote relay setup"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 1. Install deps
echo "▸ Installing dependencies..."
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    python3 -m venv "$SCRIPT_DIR/.venv"
fi
"$SCRIPT_DIR/.venv/bin/pip" install -q websockets

# 2. Start relay
echo "▸ Starting relay on :8375..."
"$SCRIPT_DIR/.venv/bin/python3" -u "$SCRIPT_DIR/herdr_relay.py" &
RELAY_PID=$!
sleep 2

if ! kill -0 $RELAY_PID 2>/dev/null; then
    echo "✗ Relay failed to start. Check if port 8375 is in use."
    exit 1
fi

# 3. Start tunnel
if command -v cloudflared >/dev/null 2>&1; then
    echo "▸ Starting Cloudflare tunnel..."
    cloudflared tunnel --url http://localhost:8375 2>&1 | grep --line-buffered "trycloudflare.com" | head -1 | while read line; do
        URL=$(echo "$line" | grep -o 'https://[^ ]*\.trycloudflare.com')
        echo ""
        echo "✓ Relay ready!"
        echo ""
        echo "  Tunnel URL: $URL"
        echo "  WebSocket:  wss://$(echo $URL | sed 's|https://||')"
        echo ""
        echo "  → Open https://herdr-remote.pages.dev on your phone"
        echo "  → Paste the WebSocket URL in Settings"
        echo ""
        echo "  To install the push plugin on remote machines:"
        echo "    herdr plugin install dcolinmorgan/herdr-push"
        echo "    echo 'HERDR_RELAY=$URL' > \"\$(herdr plugin config-dir herdr.push)/.env\""
        echo ""
    done
    wait
else
    echo ""
    echo "✓ Relay running on ws://localhost:8375"
    echo ""
    echo "  Install cloudflared for remote access:"
    echo "    brew install cloudflared"
    echo "    cloudflared tunnel --url http://localhost:8375"
    echo ""
    echo "  Or use on LAN: ws://$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}'):8375"
    echo ""
    wait $RELAY_PID
fi
