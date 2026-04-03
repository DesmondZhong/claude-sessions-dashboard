#!/usr/bin/env python3
"""Claude Code Session Sync Agent — runs on each VM to push sessions to the dashboard server."""

import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "agent-config.yaml")
STATE_DIR = os.path.expanduser("~/.claude-dashboard-agent")
STATE_FILE = os.path.join(STATE_DIR, "state.json")
CLAUDE_DIR = os.path.expanduser("~/.claude")


def load_config(config_path):
    with open(config_path) as f:
        return yaml.safe_load(f)


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


def sync_to_server(config, sessions, raw_sessions=None):
    """Push sessions to the dashboard server."""
    server_url = config["server_url"].rstrip("/")
    api_key = config.get("api_key", "")
    vm_name = config.get("vm_name", platform.node())

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

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

    print(f"Discovering sessions in {CLAUDE_DIR}...")
    all_sessions, all_raw = discover_sessions()
    print(f"  Found {len(all_sessions)} sessions")

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
        print("  All sessions up to date, nothing to sync.")
        return

    print(f"  Syncing {len(to_sync)} new/updated sessions...")
    result = sync_to_server(config, to_sync, raw_to_sync)
    print(f"  Server accepted {result.get('synced', 0)} sessions")

    # Update state
    for sess in to_sync:
        synced[sess["id"]] = sess.get("last_timestamp", "")
    state["synced_sessions"] = synced
    state["last_sync"] = datetime.now(timezone.utc).isoformat()
    save_state(state)


def run_daemon(config):
    """Run continuously, syncing on an interval."""
    interval = config.get("sync_interval", 300)
    print(f"Running in daemon mode, syncing every {interval}s")
    while True:
        try:
            run_once(config)
        except Exception as e:
            print(f"Sync error: {e}", file=sys.stderr)
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Claude Code Session Sync Agent")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Path to config file")
    parser.add_argument("--once", action="store_true", help="Sync once and exit")
    parser.add_argument("--daemon", action="store_true", help="Run continuously")
    args = parser.parse_args()

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
