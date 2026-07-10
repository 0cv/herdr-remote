#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
WEB_ENV_FILE="$REPO_DIR/.env"

# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

require_supported_platform

if [ ! -f "$WEB_ENV_FILE" ]; then
    cp "$REPO_DIR/.env.example" "$WEB_ENV_FILE"
    echo "Created $WEB_ENV_FILE"
fi
ensure_relay_env "$ENV_FILE"

missing=0
for command in herdr uv cloudflared; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Missing required command: $command"
        missing=1
    fi
done

if [ "$missing" -ne 0 ]; then
    echo ""
    echo "Install the missing tools, then run make setup again:"
    echo "  Herdr:       https://herdr.dev"
    echo "  uv:          https://docs.astral.sh/uv/getting-started/installation/"
    echo "  cloudflared: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/"
    exit 1
fi

if ! command -v npx >/dev/null 2>&1; then
    echo "Optional: install Node.js/npm if you want to deploy the web app with make web-deploy."
fi

echo ""
echo "Setup complete."
echo "  Relay config: $ENV_FILE"
echo "  Web config:   $WEB_ENV_FILE"
echo ""
echo "Next steps:"
echo "  1. Run make web-deploy (or host ./web on any HTTPS static host)."
echo "  2. Run make quick-start to open a temporary relay tunnel."
