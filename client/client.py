#!/usr/bin/env python3
"""Claude Code Session Sync Client — runs on each VM to push sessions to the dashboard server."""

import argparse
import json
import os
import platform
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "client-config.yaml")
STATE_DIR = os.path.expanduser("~/.claude-dashboard-client")
STATE_FILE = os.path.join(STATE_DIR, "state.json")
PID_FILE = os.path.join(STATE_DIR, "client.pid")
CLAUDE_DIR = os.path.expanduser("~/.claude")

# Event used to wake up the daemon for an immediate sync
_sync_now = threading.Event()


def load_config(config_path):
    with open(config_path) as f:
        cfg = yaml.safe_load(f) or {}
    # Environment variables override yaml values
    env_map = {
        "CLAUDE_DASHBOARD_API_KEY": "api_key",
        "CLAUDE_DASHBOARD_SERVER_URL": "server_url",
        "CLAUDE_DASHBOARD_VM_NAME": "vm_name",
        "CF_ACCESS_CLIENT_ID": "cf_access_client_id",
        "CF_ACCESS_CLIENT_SECRET": "cf_access_client_secret",
    }
    for env_key, cfg_key in env_map.items():
        val = os.environ.get(env_key)
        if val is not None:
            cfg[cfg_key] = val
    return cfg


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"synced_sessions": {}}


def save_state(state):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def discover_sessions():
    """Find all session JSONL files and extract metadata + messages."""
    projects_dir = os.path.join(CLAUDE_DIR, "projects")
    if not os.path.isdir(projects_dir):
        return []

    # Build history index: sessionId -> {project, first_display}
    history_index = {}
    history_path = os.path.join(CLAUDE_DIR, "history.jsonl")
    if os.path.exists(history_path):
        with open(history_path) as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    sid = entry.get("sessionId", "")
                    if sid and sid not in history_index:
                        history_index[sid] = {
                            "project": entry.get("project", ""),
                            "display": entry.get("display", ""),
                        }
                except (json.JSONDecodeError, KeyError):
                    continue

    sessions = []
    raw_sessions = {}
    for project_dir in Path(projects_dir).iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_file in project_dir.glob("*.jsonl"):
            # Skip subagent files
            if "subagents" in str(jsonl_file):
                continue
            session_id = jsonl_file.stem
            try:
                session_data = parse_session_file(jsonl_file, session_id, history_index)
                if session_data:
                    sessions.append(session_data)
                    # Read raw file for backup
                    raw_sessions[session_id] = jsonl_file.read_text()
            except Exception as e:
                print(f"  Warning: failed to parse {jsonl_file}: {e}", file=sys.stderr)

    return sessions, raw_sessions


def parse_session_file(jsonl_path, session_id, history_index):
    """Parse a session JSONL file into structured data."""
    messages = []
    first_ts = None
    last_ts = None
    custom_title = None
    summary = None
    user_msg_count = 0

    with open(jsonl_path) as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            entry_type = entry.get("type", "")
            timestamp = entry.get("timestamp", "")
            msg = entry.get("message", {})

            if entry_type == "custom-title":
                custom_title = entry.get("customTitle", "")
                continue

            if not timestamp:
                continue

            if first_ts is None:
                first_ts = timestamp
            last_ts = timestamp

            role = msg.get("role", "") if isinstance(msg, dict) else ""
            content_raw = msg.get("content", "") if isinstance(msg, dict) else ""

            # Extract text content
            if isinstance(content_raw, list):
                text_parts = []
                for block in content_raw:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_use":
                            messages.append({
                                "role": "assistant",
                                "content": f"Tool: {block.get('name', '')}({json.dumps(block.get('input', {}))[:500]})",
                                "timestamp": timestamp,
                                "type": "tool_call",
                            })
                        elif block.get("type") == "tool_result":
                            content = block.get("content", "")
                            if isinstance(content, list):
                                content = " ".join(
                                    b.get("text", "") for b in content if isinstance(b, dict)
                                )
                            messages.append({
                                "role": "tool",
                                "content": str(content)[:2000],
                                "timestamp": timestamp,
                                "type": "tool_result",
                            })
                content = "\n".join(text_parts) if isinstance(content_raw, list) else str(content_raw)
            else:
                content = str(content_raw)

            if entry_type == "user" and role == "user":
                # Skip entries that are purely tool_result blocks (already captured above)
                if isinstance(content_raw, list) and not content.strip():
                    continue
                user_msg_count += 1
                if summary is None and content.strip():
                    summary = content.strip()[:200]
                messages.append({
                    "role": "user",
                    "content": content,
                    "timestamp": timestamp,
                    "type": "user",
                })
            elif role == "assistant" and content.strip():
                messages.append({
                    "role": "assistant",
                    "content": content,
                    "timestamp": timestamp,
                    "type": "assistant",
                })
            elif entry_type == "system":
                # Include system messages but keep them brief
                if content.strip():
                    messages.append({
                        "role": "system",
                        "content": content[:500],
                        "timestamp": timestamp,
                        "type": "system",
                    })

    if not messages:
        return None

    # Use history index for project/summary if available
    hist = history_index.get(session_id, {})
    project = hist.get("project", "")
    if not summary:
        summary = hist.get("display", "")

    return {
        "id": session_id,
        "project": project,
        "custom_title": custom_title or "",
        "summary": summary or "(no summary)",
        "message_count": user_msg_count,
        "first_timestamp": first_ts,
        "last_timestamp": last_ts,
        "messages": messages,
    }


def get_file_mtime(path):
    """Get file modification time as ISO string."""
    try:
        mtime = os.path.getmtime(path)
        return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    except OSError:
        return ""


def default_vm_name():
    """Pick the most descriptive hostname available.

    On macOS, platform.node() can return a generic "Mac" when launched from
    launchd. Prefer LocalHostName (the Bonjour name shown in Finder/AirDrop),
    fall back to platform.node(), strip trailing .local.
    """
    if sys.platform == "darwin":
        try:
            import subprocess
            result = subprocess.run(
                ["scutil", "--get", "LocalHostName"],
                capture_output=True, text=True, timeout=2,
            )
            name = result.stdout.strip()
            if name:
                return name
        except Exception:
            pass
    name = platform.node() or "unknown"
    if name.endswith(".local"):
        name = name[:-6]
    return name


def sync_to_server(config, sessions, raw_sessions=None):
    """Push sessions to the dashboard server."""
    server_url = config["server_url"].rstrip("/")
    api_key = config.get("api_key", "")
    vm_name = config.get("vm_name") or default_vm_name()

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    cf_client_id = config.get("cf_access_client_id", "")
    cf_client_secret = config.get("cf_access_client_secret", "")
    if cf_client_id and cf_client_secret:
        headers["CF-Access-Client-Id"] = cf_client_id
        headers["CF-Access-Client-Secret"] = cf_client_secret

    payload = {
        "vm_name": vm_name,
        "sessions": sessions,
    }
    if raw_sessions:
        payload["raw_sessions"] = raw_sessions

    resp = requests.post(
        f"{server_url}/api/sync",
        json=payload,
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def run_once(config):
    """Discover sessions and sync to server, only sending new/updated ones."""
    state = load_state()
    synced = state.get("synced_sessions", {})

    print(f"Discovering sessions in {CLAUDE_DIR}...", flush=True)
    all_sessions, all_raw = discover_sessions()
    print(f"  Found {len(all_sessions)} sessions", flush=True)

    # Filter to only new/updated sessions
    to_sync = []
    raw_to_sync = {}
    for sess in all_sessions:
        sid = sess["id"]
        last_ts = sess.get("last_timestamp", "")
        if sid not in synced or synced[sid] != last_ts:
            to_sync.append(sess)
            if sid in all_raw:
                raw_to_sync[sid] = all_raw[sid]

    if not to_sync:
        print("  All sessions up to date, nothing to sync.", flush=True)
        return

    print(f"  Syncing {len(to_sync)} new/updated sessions...", flush=True)
    result = sync_to_server(config, to_sync, raw_to_sync)
    print(f"  Server accepted {result.get('synced', 0)} sessions", flush=True)

    # Update state
    for sess in to_sync:
        synced[sess["id"]] = sess.get("last_timestamp", "")
    state["synced_sessions"] = synced
    state["last_sync"] = datetime.now(timezone.utc).isoformat()
    save_state(state)


def write_pid():
    """Write PID file so --trigger can find the daemon."""
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def remove_pid():
    try:
        os.remove(PID_FILE)
    except OSError:
        pass


def read_pid():
    """Read the daemon's PID from the PID file."""
    try:
        with open(PID_FILE) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def trigger_daemon():
    """Send SIGUSR1 to the running daemon to trigger an immediate sync."""
    pid = read_pid()
    if pid is None:
        print("No running client daemon found (no PID file).", file=sys.stderr)
        sys.exit(1)
    try:
        os.kill(pid, signal.SIGUSR1)
        print(f"Triggered sync on daemon (PID {pid}).")
    except ProcessLookupError:
        print(f"Daemon PID {pid} is not running. Stale PID file.", file=sys.stderr)
        remove_pid()
        sys.exit(1)
    except PermissionError:
        print(f"Permission denied sending signal to PID {pid}.", file=sys.stderr)
        sys.exit(1)


def run_daemon(config):
    """Run continuously, syncing on an interval."""
    interval = config.get("sync_interval", 3600)
    print(f"Running in daemon mode, syncing every {interval}s", flush=True)

    # Set up SIGUSR1 handler to trigger immediate sync
    if hasattr(signal, "SIGUSR1"):
        def _handle_trigger(signum, frame):
            print("Received SIGUSR1 — triggering immediate sync.", flush=True)
            _sync_now.set()
        signal.signal(signal.SIGUSR1, _handle_trigger)

    write_pid()
    try:
        while True:
            try:
                run_once(config)
            except Exception as e:
                print(f"Sync error: {e}", file=sys.stderr)
            # Wait for interval or until signalled
            _sync_now.wait(timeout=interval)
            _sync_now.clear()
    finally:
        remove_pid()


def main():
    parser = argparse.ArgumentParser(description="Claude Code Session Sync Client")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Path to config file")
    parser.add_argument("--once", action="store_true", help="Sync once and exit")
    parser.add_argument("--daemon", action="store_true", help="Run continuously")
    parser.add_argument("--trigger", action="store_true",
                        help="Signal a running daemon to sync immediately")
    parser.add_argument("--resync", action="store_true",
                        help="Clear incremental sync state and push all sessions again")
    args = parser.parse_args()

    if args.trigger:
        trigger_daemon()
        return

    if args.resync:
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
            print(f"Cleared sync state at {STATE_FILE}")
        else:
            print("No sync state to clear.")

    config = load_config(args.config)

    if args.once:
        run_once(config)
    elif args.daemon:
        run_daemon(config)
    else:
        # Default: run once
        run_once(config)


if __name__ == "__main__":
    main()
