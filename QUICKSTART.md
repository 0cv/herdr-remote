# Herdr Mobile Relay Quick Start

This connects one Linux or macOS computer to your phone through a temporary TryCloudflare tunnel. It does not require a Cloudflare account or domain.

> [!IMPORTANT]
> Native Windows is not supported. You need Herdr 0.7.0 or newer, Git, and `curl`.

## 1. Install the Plugin

```bash
herdr plugin install 0cv/herdr-mobile-relay
```

When the setup menu opens, choose **Quick Start**. If no menu opens, run:

```bash
herdr plugin action invoke setup --plugin herdr-mobile-relay.events
```

Approve installation of missing user-level tools if prompted. Quick Start creates private relay configuration, starts the relay and bundled phone app, and opens a temporary Cloudflare tunnel.

You do not need Python, Node.js, npm, a separately hosted web app, or `sudo` for this path.

## 2. Open the Phone Link

Wait for **Relay ready**, then scan the printed QR code or open the complete HTTPS setup link on your phone.

The app imports the relay URL, label, and token automatically. Do not share the link or QR code: either can grant control of agents on this relay.

Keep the Quick Start pane open while testing. Ctrl-C stops the relay and tunnel. The next run creates a different hostname, so scan its new QR code.

## 3. Try It

Run an agent in Herdr, or tap **＋** in the phone app to start a detected Codex, Claude Code, or OpenCode agent. You can inspect output, send prompts, answer approvals and structured questions, upload an image, and manage the agent lifecycle.

## Make It Permanent

For everyday use, add a domain to Cloudflare and run the guided stable setup:

```bash
herdr plugin action invoke install-service --plugin herdr-mobile-relay.events
```

The wizard confirms the tunnel and hostname, creates or resumes the DNS route, installs the background service, and prints a QR code only after the public relay identity is verified.

If it stops, rerun the exact command it prints. Setup resumes its recorded state rather than creating a duplicate tunnel.

Repeat stable setup on each computer with a different hostname. Add each QR link to the same phone app.

Useful actions:

```bash
herdr plugin action invoke status --plugin herdr-mobile-relay.events
herdr plugin action invoke stable-teardown --plugin herdr-mobile-relay.events
```

Teardown removes only stable resources recorded as wizard-owned. Run it before uninstalling the plugin if those Cloudflare resources should also be removed.

## Local Checkout

For development or a non-marketplace installation:

```bash
git clone https://github.com/0cv/herdr-mobile-relay.git
cd herdr-mobile-relay
make quick-start
```

Use `make stable-setup` for the checkout's permanent setup. Checkout commands use `relay/.env`; plugin commands use the plugin's persistent configuration. Do not use a checkout's `make setup-link` for a running marketplace installation—the mismatch is intentionally rejected.

## Troubleshooting

- **No setup menu:** run the `setup` plugin action above.
- **Port 8375 is already in use:** stop the previous Quick Start or installed relay service.
- **The temporary URL times out:** keep the setup pane open and check its `cloudflared` error. Rerun Quick Start for a fresh hostname.
- **The app opens but remains disconnected:** reopen the complete link, including `#setup=...`.
- **Stable setup fails or times out:** keep its state file and rerun the exact command shown.
- **Stable DNS name already exists:** choose another hostname; the wizard never overwrites an existing record.
- **macOS cannot browse a project folder:** grant the relay process access under Files and Folders, or choose an unprotected directory.

For more detail, see the [README](README.md).
