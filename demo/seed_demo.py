#!/usr/bin/env python3
"""Populate a fresh SQLite database with synthetic demo sessions.

Deletes and recreates the demo DB on every run, so restarting the
container always boots with a clean demo dataset.
"""
import os
import sys
import sqlite3
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conversations import SESSIONS, CLIENTS


def seed(db_path):
    if os.path.exists(db_path):
        os.remove(db_path)

    db = sqlite3.connect(db_path)
    db.executescript("""
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            vm_name TEXT NOT NULL,
            project TEXT,
            custom_title TEXT DEFAULT '',
            summary TEXT,
            message_count INTEGER DEFAULT 0,
            first_timestamp TEXT,
            last_timestamp TEXT,
            updated_at TEXT
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            timestamp TEXT,
            message_type TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );
        CREATE TABLE clients (
            vm_name TEXT PRIMARY KEY,
            ip_address TEXT,
            last_sync TEXT,
            session_count INTEGER DEFAULT 0
        );
        CREATE INDEX idx_messages_session ON messages(session_id);
        CREATE INDEX idx_sessions_vm ON sessions(vm_name);
        CREATE INDEX idx_sessions_last_ts ON sessions(last_timestamp DESC);
    """)

    now = datetime.now(timezone.utc).isoformat()

    for c in CLIENTS:
        db.execute(
            "INSERT INTO clients (vm_name, ip_address, last_sync, session_count) VALUES (?, ?, ?, ?)",
            (c["vm_name"], c["ip_address"], c["last_sync"], c["session_count"]),
        )

    for s in SESSIONS:
        msgs = s["messages"]
        user_count = sum(1 for m in msgs if m.get("type") == "user")
        first_ts = msgs[0]["timestamp"] if msgs else ""
        last_ts = msgs[-1]["timestamp"] if msgs else ""

        db.execute("""
            INSERT INTO sessions (id, vm_name, project, custom_title, summary,
                                   message_count, first_timestamp, last_timestamp, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            s["id"], s["vm_name"], s["project"], s.get("custom_title", ""),
            s["summary"], user_count, first_ts, last_ts, now,
        ))
        for m in msgs:
            db.execute("""
                INSERT INTO messages (session_id, role, content, timestamp, message_type)
                VALUES (?, ?, ?, ?, ?)
            """, (s["id"], m.get("role", ""), m.get("content", ""),
                  m.get("timestamp", ""), m.get("type", "")))

    db.commit()
    db.close()

    total_msgs = sum(len(s["messages"]) for s in SESSIONS)
    print(f"Seeded {len(SESSIONS)} sessions ({total_msgs} messages) "
          f"across {len(CLIENTS)} clients into {db_path}")


if __name__ == "__main__":
    default_path = os.path.join(os.path.dirname(__file__), "demo-sessions.db")
    db_path = os.environ.get("CLAUDE_DASHBOARD_DB_PATH", default_path)
    seed(db_path)
