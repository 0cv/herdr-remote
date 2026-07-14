#!/usr/bin/env python3
"""Small stdlib-only helper for the stable-tunnel setup state and JSON checks."""

import json
import os
import re
import sys
import tempfile
from pathlib import Path


OWNER = "herdr-mobile-relay-stable-setup-v1"
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
DEFAULT_STATE = {
    "owner": OWNER,
    "schema": 1,
    "stage": "initialized",
    "env_file": "",
    "tunnel_uuid": "",
    "tunnel_name": "",
    "hostname": "",
    "credentials_path": "",
    "config_path": "",
    "created_tunnel": False,
    "created_dns": False,
    "dns_route_attempted": False,
    "created_credentials": False,
    "created_config": False,
    "service_installed_by_wizard": False,
    "service_preexisting": None,
    "env_created_by_wizard": False,
    "env_config_added_by_wizard": False,
    "tunnel_deleted": False,
    "dns_cleanup_required": False,
}


def fail(message):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def read_json(path):
    try:
        with Path(path).open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Cannot read valid JSON from {path}: {exc}")


def read_state(path):
    state = read_json(path)
    if not isinstance(state, dict) or state.get("owner") != OWNER:
        fail(f"State file is not owned by Herdr Mobile Relay: {path}")
    return state


def write_state(path, state):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def parsed_value(value):
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "null":
        return None
    return value


def uuid_from_mapping(value):
    if not isinstance(value, dict):
        return ""
    for key in ("TunnelID", "tunnel_id", "id", "ID"):
        candidate = value.get(key)
        if isinstance(candidate, str) and UUID_RE.fullmatch(candidate):
            return candidate.lower()
    return ""


def require_uuid(value, source):
    candidate = uuid_from_mapping(value)
    if not candidate:
        fail(f"No tunnel UUID found in {source}")
    print(candidate)


def tunnel_id_by_name(value, name):
    if not isinstance(value, list):
        fail("Cloudflare tunnel list output was not a JSON list")
    matches = [
        item
        for item in value
        if isinstance(item, dict)
        and item.get("name") == name
        and not item.get("deletedAt")
    ]
    if not matches:
        return
    if len(matches) != 1:
        fail(f"Cloudflare returned multiple active tunnels named {name}")
    require_uuid(matches[0], f"Cloudflare tunnel named {name}")


def tunnel_list_has(value, tunnel_uuid):
    if not isinstance(value, list):
        fail("Cloudflare tunnel list output was not a JSON list")
    expected = tunnel_uuid.lower()
    for item in value:
        if uuid_from_mapping(item) == expected and not item.get("deletedAt"):
            return
    fail(f"Cloudflare tunnel {tunnel_uuid} was not found")


def tunnel_name_by_id(value, tunnel_uuid):
    if not isinstance(value, list):
        fail("Cloudflare tunnel list output was not a JSON list")
    expected = tunnel_uuid.lower()
    for item in value:
        if uuid_from_mapping(item) != expected or item.get("deletedAt"):
            continue
        name = item.get("name")
        if isinstance(name, str) and name:
            print(name)
            return
    fail(f"Cloudflare tunnel {tunnel_uuid} was not found")


def valid_health(value, label):
    if not isinstance(value, dict):
        fail(f"{label} health response was not a JSON object")
    if value.get("status") != "ok":
        fail(f"{label} health status is not ok")
    instance = value.get("instance")
    if not isinstance(instance, str) or not instance:
        fail(f"{label} health response has no relay instance ID")
    version = value.get("version")
    if not isinstance(version, str) or not version:
        fail(f"{label} health response has no relay version")
    protocol = value.get("protocol")
    if isinstance(protocol, bool) or not isinstance(protocol, int):
        fail(f"{label} health response has no numeric relay protocol")
    return value


def health_match(local, public):
    local = valid_health(local, "Local")
    public = valid_health(public, "Public")
    for key in ("instance", "version", "protocol"):
        if public[key] != local[key]:
            fail(
                f"Public health {key} does not match the local relay "
                f"({public[key]!r} != {local[key]!r})"
            )


def usage():
    fail(
        "Usage: stable_state.py {init|get|update|show|credential-id|create-id|"
        "tunnel-id-by-name|tunnel-list-has|tunnel-name-by-id|health-valid|"
        "health-match} ..."
    )


def main():
    if len(sys.argv) < 2:
        usage()
    command = sys.argv[1]
    args = sys.argv[2:]

    if command == "init" and len(args) in (1, 2):
        path = args[0]
        if Path(path).exists():
            read_state(path)
            return
        state = DEFAULT_STATE.copy()
        if len(args) == 2:
            state["env_file"] = args[1]
        write_state(path, state)
        return
    if command == "get" and len(args) == 2:
        value = read_state(args[0]).get(args[1], "")
        if value is True:
            print("true")
        elif value is False:
            print("false")
        elif value is not None:
            print(value)
        return
    if command == "update" and len(args) >= 2:
        state = read_state(args[0])
        for assignment in args[1:]:
            if "=" not in assignment:
                fail(f"Invalid state assignment: {assignment}")
            key, value = assignment.split("=", 1)
            if key in {"owner", "schema"}:
                fail(f"State field cannot be changed: {key}")
            state[key] = parsed_value(value)
        write_state(args[0], state)
        return
    if command == "show" and len(args) == 1:
        print(json.dumps(read_state(args[0]), indent=2, sort_keys=True))
        return
    if command == "credential-id" and len(args) == 1:
        require_uuid(read_json(args[0]), args[0])
        return
    if command == "create-id" and len(args) == 1:
        require_uuid(read_json(args[0]), args[0])
        return
    if command == "tunnel-id-by-name" and len(args) == 2:
        tunnel_id_by_name(read_json(args[0]), args[1])
        return
    if command == "tunnel-list-has" and len(args) == 2:
        tunnel_list_has(read_json(args[0]), args[1])
        return
    if command == "tunnel-name-by-id" and len(args) == 2:
        tunnel_name_by_id(read_json(args[0]), args[1])
        return
    if command == "health-valid" and len(args) == 1:
        valid_health(read_json(args[0]), "Relay")
        return
    if command == "health-match" and len(args) == 2:
        health_match(read_json(args[0]), read_json(args[1]))
        return
    usage()


if __name__ == "__main__":
    main()
