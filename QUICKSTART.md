# Herdr Mobile Relay Quick Start

Get mobile approval for local Herdr agents with a temporary Cloudflare quick tunnel.

> [!IMPORTANT]
> Herdr Mobile Relay currently supports only Linux and macOS. Windows is not supported.

## 1. Prepare the repository

```bash
git clone https://github.com/0cv/herdr-mobile-relay.git
cd herdr-mobile-relay
make setup
```

`make setup` creates the local web and relay config files, generates the relay token, and reports any missing prerequisites. See the [README requirements](README.md#requirements) for details.

## 2. Deploy the phone app

Host `web/` on any HTTPS static host, or deploy it to Cloudflare Pages:

```bash
# edit WEB_PROJECT in .env first if needed
make web-deploy
```

## 3. Start the relay and tunnel

```bash
make quick-start
```

The command prints:

```text
Tunnel URL: https://example.trycloudflare.com
WebSocket:  wss://example.trycloudflare.com
Token:      0123456789abcdef0123456789abcdef
```

Quick tunnel hostnames are temporary and change when the tunnel restarts. The token is stored in `relay/.env` and reused on later quick-start runs.

## 4. Connect the phone app

Open the deployed web app on your phone. In Settings, add the printed `wss://...trycloudflare.com` URL and token. Install the app from Safari's Share menu on iPhone/iPad or Chrome's install menu on Android.

For permanent hostnames and background startup, follow [Stable Hostnames](README.md#stable-hostnames) and then run the platform-detecting service installer:

```bash
make service-install
```

Repeat the relay setup on each Linux or macOS computer and add every relay URL in Settings; the browser merges their agents client-side.
