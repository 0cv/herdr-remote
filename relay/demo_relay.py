#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["websockets>=14.0"]
# ///
"""Demo relay — broadcasts fake agent data for showcasing the web app. No real herdr needed."""
import asyncio, json, random

try:
    from websockets.asyncio.server import serve
except ImportError:
    from websockets.server import serve

AGENTS = [
    {"pane_id": "demo:1", "agent": "kiro", "status": "working", "project": "graphrag_api", "cwd": "/home/dev/graphrag_api", "host": "local"},
    {"pane_id": "demo:2", "agent": "codex", "status": "idle", "project": "bioingest", "cwd": "/home/dev/bioingest", "host": "local"},
    {"pane_id": "demo:3", "agent": "claude", "status": "blocked", "project": "graffold-frontend", "cwd": "/home/dev/graffold-frontend", "host": "local"},
    {"pane_id": "demo:4", "agent": "kiro", "status": "working", "project": "herdr-remote", "cwd": "/home/dev/herdr-remote", "host": "remote-1"},
    {"pane_id": "demo:5", "agent": "grok", "status": "idle", "project": "pyGS", "cwd": "/home/dev/pyGS", "host": "local"},
]

BLOCKED_PROMPT = """Do you want to allow this tool call?

Tool: write_file
Path: src/components/Graph.tsx

> yes, single permission
> trust, always allow
> no (tab to edit)"""

clients = set()

async def broadcast():
    while True:
        # Randomly change statuses for demo effect
        for a in AGENTS:
            if random.random() < 0.1:
                a["status"] = random.choice(["working", "idle", "blocked"])

        msg = json.dumps({"type": "agents", "agents": AGENTS})
        dead = set()
        for ws in clients:
            try:
                await ws.send(msg)
            except Exception:
                dead.add(ws)
        clients.difference_update(dead)

        # Send blocked events
        for a in AGENTS:
            if a["status"] == "blocked":
                blocked_msg = json.dumps({
                    "type": "blocked", "pane_id": a["pane_id"],
                    "agent": a["agent"], "project": a["project"],
                    "prompt": BLOCKED_PROMPT, "host": a["host"],
                    "options": ["yes, single permission", "trust, always allow", "no (tab to edit)"]
                })
                for ws in clients:
                    try:
                        await ws.send(blocked_msg)
                    except Exception:
                        pass

        await asyncio.sleep(3)

async def handle(ws):
    clients.add(ws)
    # Send initial state
    await ws.send(json.dumps({"type": "agents", "agents": AGENTS}))
    try:
        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("type") == "read_pane":
                await ws.send(json.dumps({
                    "type": "pane_content", "pane_id": msg["pane_id"],
                    "content": f"$ herdr agent working...\n\n[demo mode — this is a read-only preview]\n\nAgent: {msg['pane_id']}\nStatus: active\nLast output: Building project...\n\n✓ Compiled successfully\n→ Running tests..."
                }))
            elif msg.get("type") == "respond":
                # Accept but do nothing (demo)
                a = next((x for x in AGENTS if x["pane_id"] == msg["pane_id"]), None)
                if a:
                    a["status"] = "working"
    finally:
        clients.discard(ws)

async def main():
    asyncio.create_task(broadcast())
    server = await serve(handle, "0.0.0.0", 8375)
    print("🐑 herdr-remote DEMO relay on :8375 (read-only, fake data)")
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
