#!/bin/bash
set -e
echo "🐑 herdr-remote relay setup"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${HERDR_RELAY_PORT:-8375}"
RELAY_PID=""
TUNNEL_PID=""
LOG_FILE=""

cleanup() {
    if [ -n "$TUNNEL_PID" ] && kill -0 "$TUNNEL_PID" 2>/dev/null; then
        kill "$TUNNEL_PID" 2>/dev/null || true
    fi
    if [ -n "$RELAY_PID" ] && kill -0 "$RELAY_PID" 2>/dev/null; then
        kill "$RELAY_PID" 2>/dev/null || true
    fi
    if [ -n "$LOG_FILE" ]; then
        rm -f "$LOG_FILE"
    fi
}
trap cleanup EXIT
trap 'cleanup; exit 130' INT TERM

# 1. Start relay (uv auto-installs deps)
echo "▸ Starting relay on :$PORT..."
uv run "$SCRIPT_DIR/herdr_relay.py" &
RELAY_PID=$!
sleep 2

if ! kill -0 $RELAY_PID 2>/dev/null; then
    echo "✗ Relay failed to start. Check if port 8375 is in use."
    exit 1
fi

# 2. Start tunnel
if command -v cloudflared >/dev/null 2>&1; then
    echo "▸ Starting Cloudflare tunnel..."
    LOG_FILE="$(mktemp "${TMPDIR:-/tmp}/herdr-cloudflared.XXXXXX")"
    cloudflared tunnel --url "http://localhost:$PORT" >"$LOG_FILE" 2>&1 &
    TUNNEL_PID=$!

    URL=""
    for _ in $(seq 1 30); do
        if ! kill -0 "$TUNNEL_PID" 2>/dev/null; then
            echo "✗ Cloudflare tunnel failed:"
            sed -n '1,120p' "$LOG_FILE"
            exit 1
        fi
        URL="$(sed -nE 's/.*(https:\/\/[^ ]*\.trycloudflare\.com).*/\1/p' "$LOG_FILE" | head -1)"
        if [ -n "$URL" ]; then
            break
        fi
        sleep 1
    done

    if [ -z "$URL" ]; then
        echo "✗ Timed out waiting for Cloudflare tunnel URL. Recent cloudflared output:"
        tail -40 "$LOG_FILE"
        exit 1
    fi

    echo ""
    echo "✓ Relay ready!"
    echo ""
    echo "  Tunnel URL: $URL"
    echo "  WebSocket:  wss://$(echo $URL | sed 's|https://||')"
    echo ""
    echo "  → Open your deployed web app on your phone"
    echo "  → Paste the WebSocket URL in Settings"
    echo ""

    if ! wait "$TUNNEL_PID"; then
        echo "✗ Cloudflare tunnel stopped. Recent cloudflared output:"
        if [ -f "$LOG_FILE" ]; then
            tail -40 "$LOG_FILE"
        fi
        exit 1
    fi
else
    echo ""
    echo "✓ Relay running on ws://localhost:$PORT"
    echo ""
    echo "  Install cloudflared for remote access:"
    echo "    brew install cloudflared"
    echo ""
    wait $RELAY_PID
fi
