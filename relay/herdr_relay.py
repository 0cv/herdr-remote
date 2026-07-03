#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["websockets>=14.0"]
# ///
"""herdr-remote relay — polls herdr, accepts push events (HTTP GET + WebSocket + UDP), broadcasts to clients."""
import asyncio, json, os, re, shutil, signal, socket, subprocess

try:
    from websockets.asyncio.server import serve
except ImportError:
    from websockets.server import serve

def default_herdr_bin():
    for candidate in (
        shutil.which("herdr"),
        os.path.expanduser("~/.local/bin/herdr"),
        "/opt/homebrew/bin/herdr",
        "/usr/local/bin/herdr",
    ):
        if candidate and os.path.exists(candidate):
            return candidate
    return "herdr"


HERDR = os.environ.get("HERDR_BIN") or default_herdr_bin()
WS_PORT = int(os.environ.get("HERDR_RELAY_PORT", "8375"))
POLL_INTERVAL = 2
AUTH_TOKEN = os.environ.get("HERDR_RELAY_TOKEN", "")  # Optional: shared secret for relay auth

# Remote hosts: comma-separated SSH targets
REMOTES = [r.strip() for r in os.environ.get("HERDR_REMOTES", "").split(",") if r.strip()]

TOOL_OPTIONS = ["yes, single permission", "trust, always allow", "no (tab to edit)"]
SUBAGENT_OPTIONS = ["approve all pending", "configure individually", "exit (cancel subagents)"]
CHROME_RE = re.compile(
    r"^[\s─━═_—│|◔◑◕●\s]+$"
    r"|Kiro\s[·•]"
    r"|esc to cancel"
    r"|type to queue"
    r"|^\s*[◔◑◕●]\s+(Shell|Bash)"
)

clients = set()
last_statuses = {}
event_queue = asyncio.Queue()
pane_remote_map = {}


def run_herdr(*args, remote=None):
    try:
        if remote:
            cmd = ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", remote, HERDR, *args]
        else:
            cmd = [HERDR, *args]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return r.stdout.strip()
    except Exception:
        return ""


def get_agents_from_host(remote=None):
    raw = run_herdr("pane", "list", remote=remote)
    host_label = remote or "local"
    try:
        data = json.loads(raw)
        panes = data.get("result", {}).get("panes", [])
        return [
            {
                "pane_id": p["pane_id"],
                "agent": p.get("agent", ""),
                "status": p.get("agent_status", "unknown"),
                "cwd": p.get("cwd", ""),
                "project": os.path.basename(p.get("cwd", "")),
                "host": host_label,
                "remote": remote,
            }
            for p in panes if p.get("agent")
        ]
    except (json.JSONDecodeError, KeyError):
        return []


def get_all_agents():
    agents = get_agents_from_host(remote=None)
    for remote in REMOTES:
        agents.extend(get_agents_from_host(remote=remote))
    return agents


def read_pane(pane_id, remote=None):
    raw = run_herdr("pane", "read", pane_id, "--lines", "20", "--source", "recent", remote=remote)
    lines = [l for l in raw.splitlines() if l.strip() and not CHROME_RE.search(l)]
    return "\n".join(lines[-6:])


def detect_options(text):
    lower = text.lower()
    if "yes, single permission" in lower:
        return TOOL_OPTIONS
    if "approve all pending" in lower:
        return SUBAGENT_OPTIONS
    return None


async def broadcast(msg):
    data = json.dumps(msg)
    dead = set()
    for ws in clients:
        try:
            await ws.send(data)
        except Exception:
            dead.add(ws)
    clients.difference_update(dead)


async def poll_loop():
    while True:
        agents = get_all_agents()
        if agents:
            for a in agents:
                pane_remote_map[a["pane_id"]] = a.get("remote")
            await broadcast({"type": "agents", "agents": agents})
            for a in agents:
                pid, status = a["pane_id"], a["status"]
                if status == "blocked" and last_statuses.get(pid) != "blocked":
                    content = read_pane(pid, remote=a.get("remote"))
                    options = detect_options(content)
                    await broadcast({
                        "type": "blocked", "pane_id": pid,
                        "agent": a["agent"], "project": a["project"],
                        "host": a.get("host", "local"),
                        "prompt": content[:500],
                        "options": options or TOOL_OPTIONS
                    })
                last_statuses[pid] = status
        await asyncio.sleep(POLL_INTERVAL)


async def event_push():
    while True:
        event = await event_queue.get()
        pane_id = event.get("pane_id", "")
        status = event.get("status", "")
        host = event.get("host", "local")

        if status == "blocked" and pane_id:
            remote = pane_remote_map.get(pane_id)
            if remote or host == "local":
                content = read_pane(pane_id, remote=remote)
            else:
                content = event.get("prompt", "Agent is blocked")
            options = detect_options(content)
            await broadcast({
                "type": "blocked", "pane_id": pane_id,
                "agent": event.get("agent", ""),
                "project": event.get("project", ""),
                "host": host,
                "prompt": content[:500],
                "options": options or TOOL_OPTIONS
            })

        if pane_id and event.get("type") == "agent_event":
            await broadcast({
                "type": "agents", "agents": [{
                    "pane_id": pane_id,
                    "agent": event.get("agent", ""),
                    "status": status,
                    "cwd": event.get("cwd", ""),
                    "project": event.get("project", ""),
                    "host": host,
                }]
            })


async def process_request(connection, request):
    """Handle WebSocket upgrades and HTTP GET /push?d=... on the same port."""
    from websockets.http11 import Response
    from websockets.datastructures import Headers

    # Token auth (if configured)
    if AUTH_TOKEN:
        token = None
        for key, value in request.headers.raw_items():
            if key.lower() == "authorization":
                token = value.replace("Bearer ", "")
        # Also check query param ?token=
        if not token and "token=" in (request.path or ""):
            import urllib.parse
            _, qs = request.path.split("?", 1) if "?" in request.path else (request.path, "")
            params = urllib.parse.parse_qs(qs)
            token = params.get("token", [None])[0]
        if token != AUTH_TOKEN:
            headers = Headers([("Content-Type", "text/plain")])
            return Response(401, "Unauthorized", headers, b"Invalid token\n")

    # Check if this is a WebSocket upgrade
    upgrade = None
    for key, value in request.headers.raw_items():
        if key.lower() == "upgrade":
            upgrade = value.lower()
    if upgrade == "websocket":
        return None  # proceed with WebSocket handshake

    # For CORS preflight
    if request.path and "OPTIONS" in str(request.headers):
        headers = Headers([
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, OPTIONS"),
            ("Access-Control-Allow-Headers", "Content-Type"),
        ])
        return Response(204, "No Content", headers, b"")

    # HTTP GET — parse event from URL query params.
    # (since we can't read request body in websockets 16)
    # Plugins should encode payload in the URL path: /push?d=...
    import urllib.parse
    if "?" in (request.path or ""):
        _, qs = request.path.split("?", 1)
        params = urllib.parse.parse_qs(qs)
        if "d" in params:
            try:
                event = json.loads(urllib.parse.unquote(params["d"][0]))
                event_queue.put_nowait(event)
            except Exception:
                pass

    headers = Headers([("Access-Control-Allow-Origin", "*")])
    return Response(200, "OK", headers, b"ok\n")


async def handle_client(ws):
    clients.add(ws)
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            msg_type = msg.get("type")
            if msg_type == "respond":
                pane_id = msg["pane_id"]
                remote = pane_remote_map.get(pane_id)
                run_herdr("pane", "send-text", pane_id, msg["text"] + "\n", remote=remote)
            elif msg_type == "agent_event":
                event_queue.put_nowait(msg)
            elif msg_type == "read_pane":
                pane_id = msg["pane_id"]
                lines = msg.get("lines", "30")
                fmt = "ansi" if msg.get("format") == "ansi" else "text"
                remote = pane_remote_map.get(pane_id)
                content = run_herdr(
                    "pane", "read", pane_id,
                    "--lines", str(lines),
                    "--source", "recent",
                    "--format", fmt,
                    remote=remote,
                )
                await ws.send(json.dumps({"type": "pane_content", "pane_id": pane_id, "content": content, "format": fmt}))
            elif msg_type == "send_keys":
                pane_id = msg["pane_id"]
                keys = msg.get("keys", [])
                remote = pane_remote_map.get(pane_id)
                run_herdr("pane", "send-keys", pane_id, *keys, remote=remote)
            elif msg_type == "send_text":
                pane_id = msg["pane_id"]
                text = msg.get("text", "")
                remote = pane_remote_map.get(pane_id)
                run_herdr("pane", "send-text", pane_id, text, remote=remote)
    finally:
        clients.discard(ws)


class UDPPlugin(asyncio.DatagramProtocol):
    def datagram_received(self, data, addr):
        try:
            event_queue.put_nowait(json.loads(data.decode()))
        except Exception:
            pass


async def main():
    loop = asyncio.get_running_loop()
    try:
        await loop.create_datagram_endpoint(UDPPlugin, local_addr=("127.0.0.1", 8376))
    except OSError:
        print("UDP 8376 in use, plugin push disabled")
    asyncio.create_task(poll_loop())
    asyncio.create_task(event_push())
    server = await serve(handle_client, "0.0.0.0", WS_PORT, process_request=process_request)
    hosts = ["local"] + REMOTES
    print(f"herdr-remote relay on :{WS_PORT} (WebSocket + HTTP GET push)")
    print(f"  polling: {', '.join(hosts)}")
    stop = loop.create_future()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set_result, None)
    await stop
    server.close()


if __name__ == "__main__":
    asyncio.run(main())
