#!/bin/bash
# Launch herdr-remote TUI in a herdr split pane (right side, 30% width)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found in PATH"
    exit 1
fi

TUI_CMD="uv run \"$SCRIPT_DIR/herdr_tui.py\""

if command -v herdr &>/dev/null; then
    PANE=$(herdr pane current 2>/dev/null | jq -r '.result.pane_id' 2>/dev/null)
    if [ -n "$PANE" ] && [ "$PANE" != "null" ]; then
        herdr pane split "$PANE" --direction right --ratio 0.3 --focus
        sleep 0.3
        NEW_PANE=$(herdr pane current 2>/dev/null | jq -r '.result.pane_id' 2>/dev/null)
        herdr pane send-text "$NEW_PANE" "$TUI_CMD"
        exit 0
    fi
fi

# Fallback: just run directly
uv run "$SCRIPT_DIR/herdr_tui.py"
