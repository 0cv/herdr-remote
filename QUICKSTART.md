# Quick Start

Get mobile approval for local herdr agents with a temporary Cloudflare quick tunnel.

## 1. Start the relay and tunnel

```bash
./relay/start.sh
```

The script prints:

```text
Tunnel URL: https://example.trycloudflare.com
WebSocket:  wss://example.trycloudflare.com
```

Quick tunnel hostnames are temporary and change when the tunnel restarts.

## 2. Open the web app

Open your deployed copy of `web/` on your phone. In Settings, add the printed `wss://...trycloudflare.com` URL.

To deploy the web app:

```bash
cp .env.example .env
# edit WEB_PROJECT in .env
make web-deploy
```

## 3. Use a stable relay hostname

For a fixed `wss://` URL, create a named Cloudflare tunnel and install the macOS service:

```bash
cloudflared tunnel login
cloudflared tunnel create herdr-remote
cloudflared tunnel route dns herdr-remote relay.yourdomain.com
make service-install
```

Then use `wss://relay.yourdomain.com` in the web app.

## 4. Show two computers on one page

Run one relay and one Cloudflare tunnel per computer. Give each computer a distinct hostname:

```text
wss://relay-mac.150283.xyz
wss://relay-fedora.150283.xyz
```

In the web app Settings, add both relay URLs. The browser connects to both relays directly and merges the agents on one page.

On Fedora/Linux, install `cloudflared`, create `~/.cloudflared/config-herdr-remote.yml`, then run:

```bash
make linux-service-install
```
