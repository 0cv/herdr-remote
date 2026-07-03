# herdr-remote

Monitor and approve [herdr](https://herdr.dev) agents from a phone, menu bar, or terminal dashboard.

## Components

- **Relay**: local Python process on port `8375`; polls local herdr.
- **Web app**: static mobile UI in `web/`; connect it to one or more relay `ws://` or `wss://` URLs.
- **Cloudflare tunnel**: exposes the relay without opening inbound ports.
- **LaunchAgent service**: macOS background service that starts both the relay and a named Cloudflare tunnel.
- **macOS menu bar app** and **terminal TUI**: optional clients for the same relay.

## Quick Start

Start a temporary tunnel:

```bash
./relay/start.sh
```

The script starts the relay and prints a temporary Cloudflare quick tunnel URL:

```text
Tunnel URL: https://example.trycloudflare.com
WebSocket:  wss://example.trycloudflare.com
```

Open your deployed web app on your phone and enter the printed `wss://...trycloudflare.com` URL in Settings. Quick tunnels are temporary; the hostname changes when the tunnel restarts.

## Web App

The web app is static and lives in `web/`.

Deploy it anywhere that can host static files. With Cloudflare Pages direct upload:

```bash
cp .env.example .env
# edit WEB_PROJECT in .env
make web-deploy
```

In the app Settings:

- **Relay Name**: a display label such as `Mac` or `Fedora`
- **Relay URL**: `wss://...`
- **Token**: value of `HERDR_RELAY_TOKEN` if relay auth is enabled

Add one relay entry for each computer you want on the same page.

## Named Tunnel

For a stable relay hostname, create a named Cloudflare tunnel and route a DNS name you control:

```bash
cloudflared tunnel login
cloudflared tunnel create herdr-remote
cloudflared tunnel route dns herdr-remote relay.yourdomain.com
```

Create `~/.cloudflared/config-herdr-remote.yml`:

```yaml
tunnel: herdr-remote
credentials-file: /Users/you/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: relay.yourdomain.com
    service: http://localhost:8375
  - service: http_status:404
```

Run it manually:

```bash
make relay-run
cloudflared tunnel --config ~/.cloudflared/config-herdr-remote.yml run
```

Then use this in the web app:

```text
wss://relay.yourdomain.com
```

## Multiple Computers, One Page

Run one relay and one Cloudflare tunnel per computer. The computers do not need to SSH into each other. The web app connects to each relay URL directly and merges the agent lists in the browser.

Use distinct public hostnames, for example:

```text
wss://relay-mac.150283.xyz
wss://relay-fedora.150283.xyz
```

Each hostname should point at the tunnel for that computer. Do not run Mac and Fedora as replicas of the same Cloudflare tunnel if they serve different local relays; Cloudflare may send a WebSocket to either connector for that tunnel.

In the web app Settings, add both relay URLs. If both computers use the same `HERDR_RELAY_TOKEN`, enter the same token for both entries.

## macOS Background Service

For day-to-day use, prefer the LaunchAgent service over two manual terminals. It runs the relay and named Cloudflare tunnel together.

Prerequisite: create `~/.cloudflared/config-herdr-remote.yml` as shown above.

Install and start:

```bash
make service-install
```

The installer:

- creates `relay/.env` if it does not exist
- generates `HERDR_RELAY_TOKEN`
- writes `~/Library/LaunchAgents/com.herdr-remote.service.plist`
- starts `relay/herdr-remote-service.sh` through launchd

Useful commands:

```bash
make web-deploy
make service-status
make service-logs
make service-uninstall
```

Read the token for the web app:

```bash
sed -n 's/^HERDR_RELAY_TOKEN=//p' relay/.env
```

The service starts at login and launchd restarts it if it exits. Cloudflared handles normal sleep and network reconnects. If the laptop is powered off, the relay is unavailable until the Mac boots and the user logs in.

## Fedora/Linux Background Service

Install `cloudflared` first, then create the same named tunnel config shown above at `~/.cloudflared/config-herdr-remote.yml`. Cloudflare publishes Linux packages and RPM downloads for `cloudflared`.

Install and start a user systemd service:

```bash
make linux-service-install
```

Useful commands:

```bash
make linux-service-status
make linux-service-logs
make linux-service-uninstall
```

The Linux service runs `relay/herdr-remote-service.sh`, which starts both the relay and `cloudflared`. It uses `relay/.env` for `HERDR_RELAY_PORT`, `HERDR_RELAY_TOKEN`, and `CLOUDFLARED_CONFIG`.

## Architecture

```
        Web app
       /       \
 WebSocket   WebSocket
     │           │
 Mac tunnel  Fedora tunnel
     │           │
 Mac relay   Fedora relay
     │           │
 Mac herdr   Fedora herdr
```

## Token Auth

Enable relay auth with:

```bash
export HERDR_RELAY_TOKEN="$(openssl rand -hex 16)"
make relay-run
```

For the launchd service, set or read the token in `relay/.env`.

## Optional Clients

macOS menu bar app:

```bash
cd herdi-mac
./build.sh
cp -r dist/Herdi.app /Applications/
```

Terminal TUI:

```bash
uv run relay/herdr_tui.py
```

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- `cloudflared` for remote access
- herdr 0.7+
