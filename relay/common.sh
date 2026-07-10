#!/bin/bash

generate_token() {
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex 16
        return
    fi
    if command -v uuidgen >/dev/null 2>&1; then
        uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-'
        return
    fi
    echo "Cannot generate a relay token: install openssl or uuidgen." >&2
    return 1
}

append_env_default() {
    local env_file="$1"
    local key="$2"
    local value="$3"

    if grep -q "^${key}=" "$env_file"; then
        return
    fi
    printf '%s=%s\n' "$key" "$value" >> "$env_file"
}

ensure_relay_env() {
    local env_file="$1"
    local cloudflared_config="${2:-}"

    if [ ! -f "$env_file" ]; then
        umask 077
        touch "$env_file"
        echo "Created $env_file"
    fi

    chmod 600 "$env_file"
    if ! grep -q '^HERDR_RELAY_TOKEN=' "$env_file" || [ -z "$(sed -n 's/^HERDR_RELAY_TOKEN=//p' "$env_file" | tail -1)" ]; then
        printf 'HERDR_RELAY_TOKEN=%s\n' "$(generate_token)" >> "$env_file"
    fi
    if [ -n "$cloudflared_config" ]; then
        append_env_default "$env_file" CLOUDFLARED_CONFIG "$cloudflared_config"
    fi
}

load_relay_env() {
    local env_file="$1"
    if [ ! -f "$env_file" ]; then
        return
    fi
    set -a
    # shellcheck source=/dev/null
    . "$env_file"
    set +a
}

require_supported_platform() {
    case "$(uname -s)" in
        Darwin|Linux)
            return
            ;;
        *)
            echo "Unsupported platform: Herdr Mobile Relay currently supports only Linux and macOS."
            exit 1
            ;;
    esac
}
