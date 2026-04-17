#!/usr/bin/env python3
"""Claude Code Conversation Dashboard — Server."""

import json
import os
import sqlite3
import html
from datetime import datetime, timezone
from pathlib import Path

import yaml
from flask import Flask, g, jsonify, request, Response

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

app = Flask(__name__)

BACKUP_DIR = None  # set during init

CONFIG_PATH = os.environ.get(
    "CLAUDE_DASHBOARD_CONFIG",
    os.path.join(os.path.dirname(__file__), "server-config.yaml"),
)


def load_config():
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f) or {}
    # Environment variables override yaml values
    env_map = {
        "CLAUDE_DASHBOARD_API_KEY": "api_key",
        "CLAUDE_DASHBOARD_HOST": "host",
        "CLAUDE_DASHBOARD_PORT": "port",
        "CLAUDE_DASHBOARD_DB_PATH": "db_path",
    }
    for env_key, cfg_key in env_map.items():
        val = os.environ.get(env_key)
        if val is not None:
            cfg[cfg_key] = int(val) if cfg_key == "port" else val
    return cfg


def get_db():
    if "db" not in g:
        cfg = load_config()
        db_path = cfg.get("db_path", os.path.join(os.path.dirname(__file__), "sessions.db"))
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    global BACKUP_DIR
    cfg = load_config()
    db_path = cfg.get("db_path", os.path.join(os.path.dirname(__file__), "sessions.db"))
    BACKUP_DIR = cfg.get("backup_dir", os.path.join(os.path.dirname(__file__), "backups"))
    os.makedirs(BACKUP_DIR, exist_ok=True)
    db = sqlite3.connect(db_path)
    db.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            vm_name TEXT NOT NULL,
            project TEXT,
            custom_title TEXT DEFAULT '',
            summary TEXT,
            message_count INTEGER DEFAULT 0,
            first_timestamp TEXT,
            last_timestamp TEXT,
            updated_at TEXT
        )
    """)
    # Migration: add custom_title column if missing (existing DBs)
    try:
        db.execute("ALTER TABLE sessions ADD COLUMN custom_title TEXT DEFAULT ''")
    except Exception:
        pass  # column already exists
    db.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            timestamp TEXT,
            message_type TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            vm_name TEXT PRIMARY KEY,
            ip_address TEXT,
            last_sync TEXT,
            session_count INTEGER DEFAULT 0
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_vm ON sessions(vm_name)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_last_ts ON sessions(last_timestamp DESC)")
    db.commit()
    db.close()


# --- Auth ---

def check_api_key():
    cfg = load_config()
    expected = cfg.get("api_key", "")
    if not expected:
        return True
    provided = request.headers.get("X-API-Key", "")
    return provided == expected


# --- API ---

@app.route("/api/sync", methods=["POST"])
def sync():
    if not check_api_key():
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "no data"}), 400

    vm_name = data.get("vm_name", "unknown")
    sessions = data.get("sessions", [])
    raw_sessions = data.get("raw_sessions", {})
    db = get_db()

    # Record agent heartbeat
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if client_ip and "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    db.execute("""
        INSERT INTO agents (vm_name, ip_address, last_sync, session_count)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(vm_name) DO UPDATE SET
            ip_address = excluded.ip_address,
            last_sync = excluded.last_sync,
            session_count = excluded.session_count
    """, (vm_name, client_ip, datetime.now(timezone.utc).isoformat(), len(sessions)))

    # Save raw JSONL backups
    if BACKUP_DIR and raw_sessions:
        vm_backup_dir = os.path.join(BACKUP_DIR, vm_name)
        os.makedirs(vm_backup_dir, exist_ok=True)
        for session_id, raw_lines in raw_sessions.items():
            backup_path = os.path.join(vm_backup_dir, f"{session_id}.jsonl")
            with open(backup_path, "w") as f:
                f.write(raw_lines)

    synced = 0
    for sess in sessions:
        session_id = sess.get("id")
        if not session_id:
            continue

        db.execute("""
            INSERT INTO sessions (id, vm_name, project, custom_title, summary, message_count, first_timestamp, last_timestamp, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                message_count = excluded.message_count,
                last_timestamp = excluded.last_timestamp,
                custom_title = excluded.custom_title,
                summary = excluded.summary,
                updated_at = excluded.updated_at
        """, (
            session_id,
            vm_name,
            sess.get("project", ""),
            sess.get("custom_title", ""),
            sess.get("summary", ""),
            sess.get("message_count", 0),
            sess.get("first_timestamp", ""),
            sess.get("last_timestamp", ""),
            datetime.now(timezone.utc).isoformat(),
        ))

        # Replace messages for this session
        messages = sess.get("messages", [])
        if messages:
            db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            for msg in messages:
                db.execute("""
                    INSERT INTO messages (session_id, role, content, timestamp, message_type)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    session_id,
                    msg.get("role", ""),
                    msg.get("content", ""),
                    msg.get("timestamp", ""),
                    msg.get("type", ""),
                ))
        synced += 1

    db.commit()
    return jsonify({"synced": synced})


@app.route("/api/sessions")
def list_sessions():
    db = get_db()
    vm = request.args.get("vm")
    project = request.args.get("project")
    search = request.args.get("q")
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)

    query = "SELECT * FROM sessions WHERE 1=1"
    params = []

    if vm:
        query += " AND vm_name = ?"
        params.append(vm)
    if project:
        query += " AND project LIKE ?"
        params.append(f"%{project}%")
    if search:
        like = f"%{search}%"
        query += """ AND (
            summary LIKE ? OR project LIKE ? OR custom_title LIKE ?
            OR id IN (SELECT DISTINCT session_id FROM messages WHERE content LIKE ?)
        )"""
        params.extend([like, like, like, like])

    query += " ORDER BY last_timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = db.execute(query, params).fetchall()

    # Build session list with optional content match snippets
    sessions_out = []
    for r in rows:
        sess = dict(r)
        if search:
            snippet_row = db.execute(
                "SELECT content FROM messages WHERE session_id = ? AND content LIKE ? LIMIT 1",
                (sess["id"], f"%{search}%"),
            ).fetchone()
            if snippet_row:
                content = snippet_row[0] or ""
                idx = content.lower().find(search.lower())
                if idx >= 0:
                    start = max(0, idx - 40)
                    end = min(len(content), idx + len(search) + 80)
                    snippet = content[start:end].replace("\n", " ")
                    if start > 0:
                        snippet = "…" + snippet
                    if end < len(content):
                        snippet = snippet + "…"
                    sess["match_snippet"] = snippet
        sessions_out.append(sess)

    # Get distinct VM names and projects for filters
    vms = [r[0] for r in db.execute("SELECT DISTINCT vm_name FROM sessions ORDER BY vm_name").fetchall()]
    projects = [r[0] for r in db.execute("SELECT DISTINCT project FROM sessions ORDER BY project").fetchall()]

    return jsonify({
        "sessions": sessions_out,
        "filters": {"vms": vms, "projects": projects},
    })


@app.route("/api/sessions/<session_id>")
def get_session(session_id):
    db = get_db()
    session = db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not session:
        return jsonify({"error": "not found"}), 404

    messages = db.execute(
        "SELECT role, content, timestamp, message_type FROM messages WHERE session_id = ? ORDER BY id",
        (session_id,),
    ).fetchall()

    return jsonify({
        "session": dict(session),
        "messages": [dict(m) for m in messages],
    })


@app.route("/api/agents")
def list_agents():
    db = get_db()
    rows = db.execute("SELECT * FROM agents ORDER BY last_sync DESC").fetchall()
    total_sessions = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    return jsonify({
        "agents": [dict(r) for r in rows],
        "total_sessions": total_sessions,
    })


# --- Dashboard ---

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude Sessions Dashboard</title>
<style>
  :root, [data-theme="dark"] {
    --bg: #0d1117; --surface: #161b22; --border: #30363d;
    --text: #e6edf3; --text-muted: #8b949e; --accent: #58a6ff;
    --accent-hover: #79c0ff; --user-bg: #1c2333; --assistant-bg: #121820;
    --system-bg: #1a1412; --tool-bg: #12191a;
    --code-bg: rgba(110,118,129,0.2); --pre-bg: rgba(110,118,129,0.15);
    --hover-overlay: rgba(255,255,255,0.03);
  }
  [data-theme="light"] {
    --bg: #f6f8fa; --surface: #ffffff; --border: #d0d7de;
    --text: #1f2328; --text-muted: #656d76; --accent: #0969da;
    --accent-hover: #0550ae; --user-bg: #ddf4ff; --assistant-bg: #dafbe1;
    --system-bg: #fff8c5; --tool-bg: #f0e8ff;
    --code-bg: rgba(175,184,193,0.2); --pre-bg: rgba(175,184,193,0.15);
    --hover-overlay: rgba(0,0,0,0.03);
  }
  @media (prefers-color-scheme: light) {
    :root:not([data-theme="dark"]) {
      --bg: #f6f8fa; --surface: #ffffff; --border: #d0d7de;
      --text: #1f2328; --text-muted: #656d76; --accent: #0969da;
      --accent-hover: #0550ae; --user-bg: #ddf4ff; --assistant-bg: #dafbe1;
      --system-bg: #fff8c5; --tool-bg: #f0e8ff;
      --code-bg: rgba(175,184,193,0.2); --pre-bg: rgba(175,184,193,0.15);
      --hover-overlay: rgba(0,0,0,0.03);
    }
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
         background: var(--bg); color: var(--text); line-height: 1.5; }
  a { color: var(--accent); text-decoration: none; }
  a:hover { color: var(--accent-hover); }

  .header { background: var(--surface); border-bottom: 1px solid var(--border);
             padding: 12px 24px; display: flex; align-items: center; gap: 16px;
             position: sticky; top: 0; z-index: 100; }
  .header h1 { font-size: 18px; font-weight: 600; white-space: nowrap; }
  .header .controls { display: flex; gap: 8px; flex: 1; align-items: center; }

  input, select, button {
    background: var(--bg); border: 1px solid var(--border); color: var(--text);
    padding: 6px 12px; border-radius: 6px; font-size: 14px;
  }
  input:focus, select:focus { outline: none; border-color: var(--accent); }
  button { cursor: pointer; background: var(--surface); }
  button:hover { border-color: var(--accent); }
  .btn-primary { background: #238636; border-color: #2ea043; color: #fff; }
  .btn-primary:hover { background: #2ea043; }
  .btn-theme { font-size: 16px; padding: 4px 10px; line-height: 1; }

  .search-input { flex: 1; min-width: 200px; }

  .container { max-width: 1400px; margin: 0 auto; padding: 16px 24px; }

  /* Session List */
  .session-list { display: flex; flex-direction: column; gap: 12px; }
  .vm-group { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
  .vm-group-header { padding: 10px 16px; cursor: pointer; user-select: none;
                      display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 500; }
  .vm-group-header:hover { background: var(--hover-overlay); }
  .vm-group-header .arrow { font-size: 10px; transition: transform 0.15s; }
  .vm-group-header .arrow.open { transform: rotate(90deg); }
  .vm-group-header .vm-name { color: var(--accent); font-weight: 600; }
  .vm-group-header .vm-count { color: var(--text-muted); font-size: 12px; }
  .vm-group-body { display: none; border-top: 1px solid var(--border); }
  .vm-group-body.open { display: block; }
  .session-row {
    display: grid; grid-template-columns: 200px 1fr 80px 160px;
    gap: 12px; padding: 10px 16px;
    cursor: pointer; align-items: center;
    border-bottom: 1px solid var(--border); transition: background 0.1s;
  }
  .session-row:last-child { border-bottom: none; }
  .session-row:hover { background: var(--hover-overlay); }
  .session-row .project { color: var(--text-muted); font-size: 13px;
                           overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .session-row .summary { font-size: 14px; overflow: hidden;
                           text-overflow: ellipsis; white-space: nowrap; }
  .session-row .count { color: var(--text-muted); font-size: 13px; text-align: center; }
  .session-row .time { color: var(--text-muted); font-size: 13px; text-align: right; }
  .session-row .snippet { grid-column: 1 / -1; font-size: 12px; color: var(--text-muted);
                           padding-top: 6px; border-top: 1px dashed var(--border); margin-top: 4px;
                           white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .session-row .snippet mark { background: rgba(255,215,0,0.35); color: inherit;
                                padding: 1px 2px; border-radius: 2px; }
  .message mark { background: rgba(255,215,0,0.35); color: inherit;
                   padding: 1px 2px; border-radius: 2px; }
  .message.search-hit { box-shadow: 0 0 0 2px var(--accent); }

  .list-header { display: grid; grid-template-columns: 200px 1fr 80px 160px;
                  gap: 12px; padding: 8px 16px; font-size: 12px;
                  color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }

  /* Session Detail */
  .detail-view { display: none; }
  .detail-view.active { display: flex; gap: 16px; }
  .list-view.hidden { display: none; }

  .back-btn { margin-bottom: 16px; }

  .detail-main { flex: 1; min-width: 0; }
  .session-meta { background: var(--surface); padding: 16px; border-radius: 8px;
                   margin-bottom: 16px; border: 1px solid var(--border); }
  .session-meta h2 { font-size: 16px; margin-bottom: 8px; }
  .session-meta .meta-row { display: flex; gap: 24px; font-size: 13px; color: var(--text-muted); }

  .msg-nav { width: 260px; flex-shrink: 0; position: sticky; top: 60px;
             align-self: flex-start; max-height: calc(100vh - 80px); overflow-y: auto; }
  .msg-nav-inner { background: var(--surface); border: 1px solid var(--border);
                    border-radius: 8px; padding: 8px 0; }
  .msg-nav-title { font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;
                    color: var(--text-muted); padding: 4px 12px 8px; font-weight: 600; }
  .msg-nav-item { display: block; padding: 6px 12px; font-size: 13px; cursor: pointer;
                   overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
                   color: var(--text); border-left: 2px solid transparent;
                   transition: background 0.1s, border-color 0.1s; }
  .msg-nav-item:hover { background: var(--hover-overlay); }
  .msg-nav-item.active { border-left-color: var(--accent); background: var(--hover-overlay);
                          color: var(--accent); }
  .msg-nav-item .nav-index { color: var(--text-muted); font-size: 11px; margin-right: 4px; }

  .messages { display: flex; flex-direction: column; gap: 8px; }
  .message { padding: 12px 16px; border-radius: 8px; border: 1px solid var(--border); }
  .message.user { background: var(--user-bg); border-left: 3px solid var(--accent); }
  .message.assistant { background: var(--assistant-bg); border-left: 3px solid #3fb950; }
  .message.system { background: var(--system-bg); border-left: 3px solid #d29922;
                     font-size: 13px; color: var(--text-muted); }
  .message.tool { background: var(--tool-bg); border-left: 3px solid #8b5cf6; }
  .message .role { font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;
                    color: var(--text-muted); margin-bottom: 4px; font-weight: 600; }
  .message .content { white-space: pre-wrap; word-break: break-word; font-size: 14px; }
  .message .content code { background: var(--code-bg); padding: 2px 6px;
                            border-radius: 3px; font-size: 13px; }
  .message .content pre { background: var(--pre-bg); padding: 12px;
                           border-radius: 6px; overflow-x: auto; margin: 8px 0; }
  .message .content pre code { background: none; padding: 0; }
  .message .timestamp { font-size: 11px; color: var(--text-muted); margin-top: 6px; }

  .collapsible { cursor: pointer; user-select: none; }
  .collapsible::before { content: '\\25B6 '; font-size: 10px; }
  .collapsible.open::before { content: '\\25BC '; }
  .collapsible-content { display: none; margin-top: 8px; }
  .collapsible.open + .collapsible-content { display: block; }

  /* Agents Panel */
  .agents-panel { background: var(--surface); border: 1px solid var(--border);
                   border-radius: 8px; margin-bottom: 16px; overflow: hidden; }
  .agents-header { padding: 10px 16px; cursor: pointer; user-select: none;
                    display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 500; }
  .agents-header:hover { background: var(--hover-overlay); }
  .agents-header .arrow { font-size: 10px; transition: transform 0.15s; }
  .agents-header .arrow.open { transform: rotate(90deg); }
  .agents-header .badge { background: var(--accent); color: #fff; font-size: 11px;
                           padding: 1px 8px; border-radius: 10px; font-weight: 600; }
  .agents-body { display: none; border-top: 1px solid var(--border); }
  .agents-body.open { display: block; }
  .agents-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .agents-table th { text-align: left; padding: 8px 16px; color: var(--text-muted);
                      font-weight: 500; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; }
  .agents-table td { padding: 8px 16px; border-top: 1px solid var(--border); }
  .status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
  .status-dot.online { background: #3fb950; }
  .status-dot.stale { background: #d29922; }
  .status-dot.offline { background: #f85149; }

  .empty { text-align: center; padding: 48px; color: var(--text-muted); }
  .loading { text-align: center; padding: 48px; color: var(--text-muted); }

  @media (max-width: 768px) {
    .session-row { grid-template-columns: 1fr; gap: 4px; }
    .list-header { display: none; }
    .session-row .time, .session-row .count { text-align: left; }
    .header { flex-wrap: wrap; }
    .header .controls { flex-wrap: wrap; }
    .msg-nav { display: none; }
    .detail-view.active { display: block; }
  }
</style>
</head>
<body>
<div class="header">
  <h1>Claude Sessions</h1>
  <div class="controls">
    <input class="search-input" type="text" id="search" placeholder="Search sessions...">
    <select id="vm-filter"><option value="">All VMs</option></select>
    <select id="project-filter"><option value="">All Projects</option></select>
    <button class="btn-primary" onclick="refresh()">Refresh</button>
    <button class="btn-theme" id="theme-toggle" onclick="toggleTheme()" title="Toggle light/dark mode"></button>
  </div>
</div>
<div class="container">
  <div class="agents-panel" id="agents-panel">
    <div class="agents-header" onclick="toggleAgents()">
      <span class="arrow" id="agents-arrow">&#9654;</span>
      <span>Connected Agents</span>
      <span class="badge" id="agents-count">0</span>
    </div>
    <div class="agents-body" id="agents-body">
      <table class="agents-table">
        <thead><tr><th>Status</th><th>Agent</th><th>IP Address</th><th>Sessions</th><th>Last Sync</th></tr></thead>
        <tbody id="agents-tbody"></tbody>
      </table>
    </div>
  </div>
  <div class="list-view" id="list-view">
    <div class="list-header">
      <span>Project</span><span>Summary</span><span>Messages</span><span>Last Active</span>
    </div>
    <div class="session-list" id="session-list"></div>
  </div>
  <div class="detail-view" id="detail-view">
    <div class="detail-main">
      <button class="back-btn" onclick="showList()">&larr; Back to list</button>
      <div class="session-meta" id="session-meta"></div>
      <div class="messages" id="messages"></div>
    </div>
    <nav class="msg-nav" id="msg-nav">
      <div class="msg-nav-inner">
        <div class="msg-nav-title">User Messages</div>
        <div id="msg-nav-list"></div>
      </div>
    </nav>
  </div>
</div>
<script>
let allSessions = [];
let debounceTimer;

function toggleAgents() {
  const body = document.getElementById('agents-body');
  const arrow = document.getElementById('agents-arrow');
  body.classList.toggle('open');
  arrow.classList.toggle('open');
}

function agentStatus(lastSync) {
  if (!lastSync) return 'offline';
  const diff = Date.now() - new Date(lastSync).getTime();
  if (diff < 2 * 3600000) return 'online';   // synced within 2h (interval is 1h)
  if (diff < 6 * 3600000) return 'stale';     // within 6h
  return 'offline';
}

async function loadAgents() {
  try {
    const res = await fetch('/api/agents');
    const data = await res.json();
    document.getElementById('agents-count').textContent = data.agents.length;
    const tbody = document.getElementById('agents-tbody');
    if (!data.agents.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:16px">No agents connected yet</td></tr>';
      return;
    }
    tbody.innerHTML = data.agents.map(a => {
      const st = agentStatus(a.last_sync);
      const label = st === 'online' ? 'Online' : st === 'stale' ? 'Stale' : 'Offline';
      return `<tr>
        <td><span class="status-dot ${st}"></span>${label}</td>
        <td><strong>${esc(a.vm_name)}</strong></td>
        <td><code>${esc(a.ip_address || 'unknown')}</code></td>
        <td>${a.session_count}</td>
        <td>${formatTime(a.last_sync)}</td>
      </tr>`;
    }).join('');
  } catch (e) { /* ignore */ }
}

async function loadSessions() {
  const el = document.getElementById('session-list');
  el.innerHTML = '<div class="loading">Loading...</div>';
  try {
    const params = new URLSearchParams();
    const q = document.getElementById('search').value;
    const vm = document.getElementById('vm-filter').value;
    const proj = document.getElementById('project-filter').value;
    if (q) params.set('q', q);
    if (vm) params.set('vm', vm);
    if (proj) params.set('project', proj);
    const res = await fetch('/api/sessions?' + params);
    const data = await res.json();
    allSessions = data.sessions;
    renderFilters(data.filters);
    renderList(data.sessions);
  } catch (e) {
    el.innerHTML = '<div class="empty">Failed to load sessions</div>';
  }
}

function renderFilters(filters) {
  const vmSel = document.getElementById('vm-filter');
  const projSel = document.getElementById('project-filter');
  const curVm = vmSel.value, curProj = projSel.value;
  vmSel.innerHTML = '<option value="">All VMs</option>' +
    filters.vms.map(v => `<option value="${esc(v)}" ${v===curVm?'selected':''}>${esc(v)}</option>`).join('');
  projSel.innerHTML = '<option value="">All Projects</option>' +
    filters.projects.map(p => {
      const short = p.split('/').filter(Boolean).slice(-2).join('/');
      return `<option value="${esc(p)}" ${p===curProj?'selected':''}>${esc(short)}</option>`;
    }).join('');
}

let vmGroupState = {};  // track open/closed state across refreshes

function renderList(sessions) {
  const el = document.getElementById('session-list');
  if (!sessions.length) { el.innerHTML = '<div class="empty">No sessions found</div>'; return; }

  // Group by vm_name, preserving sort order within each group
  const groups = {};
  const groupOrder = [];
  sessions.forEach(s => {
    if (!groups[s.vm_name]) {
      groups[s.vm_name] = [];
      groupOrder.push(s.vm_name);
    }
    groups[s.vm_name].push(s);
  });

  // Sort groups by most recent session
  groupOrder.sort((a, b) => {
    const aTime = groups[a][0]?.last_timestamp || '';
    const bTime = groups[b][0]?.last_timestamp || '';
    return bTime.localeCompare(aTime);
  });

  // Default: first group open, rest closed (unless user has toggled)
  if (Object.keys(vmGroupState).length === 0) {
    groupOrder.forEach((vm, i) => { vmGroupState[vm] = i === 0; });
  }

  const activeSearch = document.getElementById('search').value.trim();

  // Expand all groups when a search is active so results are visible
  if (activeSearch) {
    groupOrder.forEach(vm => { vmGroupState[vm] = true; });
  }

  el.innerHTML = groupOrder.map(vm => {
    const list = groups[vm];
    const isOpen = vmGroupState[vm] ?? false;
    return `<div class="vm-group">
      <div class="vm-group-header" onclick="toggleVmGroup('${esc(vm)}')">
        <span class="arrow ${isOpen ? 'open' : ''}" id="vm-arrow-${esc(vm)}">&#9654;</span>
        <span class="vm-name">${esc(vm)}</span>
        <span class="vm-count">${list.length} sessions</span>
      </div>
      <div class="vm-group-body ${isOpen ? 'open' : ''}" id="vm-body-${esc(vm)}">
        ${list.map(s => `
          <div class="session-row" onclick="showDetail('${esc(s.id)}', ${activeSearch ? `'${esc(activeSearch)}'` : 'null'})">
            <span class="project" title="${esc(s.project)}">${esc(shortProject(s.project))}</span>
            <span class="summary">${s.custom_title ? '<strong>' + esc(s.custom_title) + '</strong> — ' : ''}${esc(s.summary || '(no summary)')}</span>
            <span class="count">${s.message_count} msgs</span>
            <span class="time">${formatTime(s.last_timestamp)}</span>
            ${s.match_snippet ? `<span class="snippet">${highlightMatch(s.match_snippet, activeSearch)}</span>` : ''}
          </div>`).join('')}
      </div>
    </div>`;
  }).join('');
}

function highlightMatch(text, term) {
  if (!text || !term) return esc(text || '');
  const escaped = esc(text);
  const termEsc = esc(term).replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
  const re = new RegExp('(' + termEsc + ')', 'gi');
  return escaped.replace(re, '<mark>$1</mark>');
}

function toggleVmGroup(vm) {
  vmGroupState[vm] = !vmGroupState[vm];
  const body = document.getElementById('vm-body-' + vm);
  const arrow = document.getElementById('vm-arrow-' + vm);
  if (body) body.classList.toggle('open');
  if (arrow) arrow.classList.toggle('open');
}

function shortProject(p) {
  if (!p) return '';
  return p.split('/').filter(Boolean).slice(-2).join('/');
}

function formatTime(ts) {
  if (!ts) return '';
  try {
    const d = new Date(typeof ts === 'number' ? ts : ts);
    const now = new Date();
    const diff = now - d;
    if (diff < 3600000) return Math.floor(diff/60000) + 'm ago';
    if (diff < 86400000) return Math.floor(diff/3600000) + 'h ago';
    if (diff < 604800000) return Math.floor(diff/86400000) + 'd ago';
    return d.toLocaleDateString();
  } catch { return ts; }
}

async function showDetail(id, searchTerm) {
  document.getElementById('list-view').classList.add('hidden');
  const dv = document.getElementById('detail-view');
  dv.classList.add('active');
  document.getElementById('messages').innerHTML = '<div class="loading">Loading...</div>';

  const res = await fetch(`/api/sessions/${id}`);
  const data = await res.json();
  const s = data.session;

  document.getElementById('session-meta').innerHTML = `
    <h2>${esc(s.custom_title || s.summary || s.id)}</h2>
    <div class="meta-row">
      <span>VM: <strong>${esc(s.vm_name)}</strong></span>
      <span>Project: <strong>${esc(s.project)}</strong></span>
      <span>Messages: <strong>${s.message_count}</strong></span>
      <span>Last active: <strong>${formatTime(s.last_timestamp)}</strong></span>
    </div>`;

  const msgs = data.messages;
  const termLower = (searchTerm || '').toLowerCase();
  let userMsgIndex = 0;
  let firstHitId = null;
  document.getElementById('messages').innerHTML = msgs.map((m, i) => {
    const role = m.role || m.message_type || 'system';
    const cls = ['user','assistant','system','tool'].includes(role) ? role : 'system';
    const isHit = termLower && (m.content || '').toLowerCase().includes(termLower);
    const domId = role === 'user' ? `user-msg-${userMsgIndex++}` : (isHit ? `hit-msg-${i}` : '');
    if (isHit && !firstHitId) firstHitId = domId || `hit-msg-${i}`;
    const idAttr = domId ? `id="${domId}"` : '';
    const hitClass = isHit ? ' search-hit' : '';
    if (m.message_type === 'tool_call' || m.message_type === 'tool_result') {
      return `<div ${idAttr} class="message tool${hitClass}">
        <div class="role collapsible" onclick="this.classList.toggle('open')">${esc(m.message_type)}</div>
        <div class="collapsible-content"><div class="content"><pre><code>${searchTerm ? highlightMatch(m.content, searchTerm) : esc(m.content)}</code></pre></div></div>
        ${m.timestamp ? `<div class="timestamp">${formatTime(m.timestamp)}</div>` : ''}
      </div>`;
    }
    return `<div ${idAttr} class="message ${cls}${hitClass}">
      <div class="role">${esc(role)}</div>
      <div class="content">${searchTerm ? highlightMatch(m.content || '', searchTerm) : renderContent(m.content)}</div>
      ${m.timestamp ? `<div class="timestamp">${formatTime(m.timestamp)}</div>` : ''}
    </div>`;
  }).join('');

  // Build nav sidebar with user messages
  const userMsgs = msgs.filter(m => (m.role || m.message_type) === 'user');
  document.getElementById('msg-nav-list').innerHTML = userMsgs.map((m, i) => {
    const preview = (m.content || '').replace(/\\s+/g, ' ').slice(0, 60) || '(empty)';
    return `<div class="msg-nav-item" data-target="user-msg-${i}" onclick="scrollToMsg(this, ${i})" title="${esc(m.content || '')}">
      <span class="nav-index">${i + 1}.</span>${esc(preview)}
    </div>`;
  }).join('');

  // Set up intersection observer for active state
  setupNavObserver();

  // Scroll to first search hit if any
  if (firstHitId) {
    requestAnimationFrame(() => {
      const target = document.getElementById(firstHitId);
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  }
}

function renderContent(text) {
  if (!text) return '';
  let s = esc(text);
  // Basic code block rendering
  s = s.replace(/```(\\w*)\\n([\\s\\S]*?)```/g, '<pre><code>$2</code></pre>');
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  return s;
}

function scrollToMsg(navItem, index) {
  const target = document.getElementById('user-msg-' + index);
  if (!target) return;
  target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  // Update active state immediately
  document.querySelectorAll('.msg-nav-item').forEach(el => el.classList.remove('active'));
  navItem.classList.add('active');
}

let navObserver = null;
function setupNavObserver() {
  if (navObserver) navObserver.disconnect();
  const targets = document.querySelectorAll('[id^="user-msg-"]');
  if (!targets.length) return;
  navObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const id = entry.target.id;
        document.querySelectorAll('.msg-nav-item').forEach(el => {
          el.classList.toggle('active', el.dataset.target === id);
        });
      }
    });
  }, { rootMargin: '-60px 0px -60% 0px', threshold: 0 });
  targets.forEach(t => navObserver.observe(t));
}

function showList() {
  if (navObserver) { navObserver.disconnect(); navObserver = null; }
  document.getElementById('list-view').classList.remove('hidden');
  document.getElementById('detail-view').classList.remove('active');
}

function esc(s) { if (!s) return ''; const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

function refresh() { loadSessions(); loadAgents(); }

document.getElementById('search').addEventListener('input', () => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(loadSessions, 300);
});
document.getElementById('vm-filter').addEventListener('change', loadSessions);
document.getElementById('project-filter').addEventListener('change', loadSessions);

function getTheme() {
  const saved = localStorage.getItem('theme');
  if (saved) return saved;
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

function applyTheme(theme) {
  if (theme === 'light' || theme === 'dark') {
    document.documentElement.setAttribute('data-theme', theme);
  } else {
    document.documentElement.removeAttribute('data-theme');
  }
  document.getElementById('theme-toggle').textContent = theme === 'light' ? '\\u263E' : '\\u2600';
}

function toggleTheme() {
  const current = getTheme();
  const next = current === 'light' ? 'dark' : 'light';
  localStorage.setItem('theme', next);
  applyTheme(next);
}

applyTheme(getTheme());
loadSessions();
loadAgents();
</script>
</body>
</html>"""


@app.route("/")
def dashboard():
    return Response(DASHBOARD_HTML, content_type="text/html")


if __name__ == "__main__":
    init_db()
    cfg = load_config()
    host = cfg.get("host", "0.0.0.0")
    port = cfg.get("port", 5000)
    debug = cfg.get("debug", False)
    print(f"Starting Claude Sessions Dashboard on {host}:{port}")
    app.run(host=host, port=port, debug=debug)
