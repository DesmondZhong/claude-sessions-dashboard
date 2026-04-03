# Claude Sessions Dashboard

A client-server tool to centrally view Claude Code conversations across multiple machines.

## Project Structure

```
server/
  app.py               # Flask server — API + web dashboard + SQLite
  server-config.yaml   # Server config (api_key, host, port, db_path, backup_dir)
  install-service.sh   # Service installer (Linux systemd / macOS launchd)
  install-service.ps1  # Service installer (Windows NSSM / scheduled task)
  uninstall-service.sh
agent/
  agent.py             # Sync agent — discovers local sessions, pushes to server
  agent-config.yaml    # Agent config (server_url, api_key, vm_name, sync_interval)
  install-service.sh   # Service installer (Linux / macOS)
  install-service.ps1  # Service installer (Windows)
  uninstall-service.sh
```

## Key Design Decisions

- **Single-file server**: Dashboard HTML/CSS/JS is inlined in `app.py` as `DASHBOARD_HTML`. No frontend build step.
- **SQLite + raw backups**: Parsed sessions go into SQLite for querying. Raw JSONL files are also saved to `backups/<vm-name>/` for full-fidelity archival.
- **Agent push model**: Agents POST to the server (not SSH pull), so it works across networks and firewalls.
- **Incremental sync**: Agent tracks last-synced timestamps in `~/.claude-dashboard-agent/state.json` to avoid re-uploading unchanged sessions.
- **SIGUSR1 trigger**: Running daemon can be signalled for immediate sync via `agent.py --trigger` (Unix only).

## Claude Code Session Format

Sessions are stored locally at `~/.claude/`:
- `history.jsonl` — one line per user prompt: `{sessionId, project, timestamp, display}`
- `projects/<path>/<uuid>.jsonl` — full conversation JSONL, each line has `{type, message, timestamp, uuid, parentUuid}`
- Message content can be a string or array of blocks (`text`, `tool_use`, `tool_result`, `thinking`)

## Development

Dependencies: `flask`, `pyyaml` (server); `requests`, `pyyaml` (agent). No virtual env is set up — install with `pip install -r requirements.txt` in each directory.

To test locally:
```bash
cd server && python app.py                    # starts on :5000
cd agent && python agent.py --once            # sync once to localhost
```

## Conventions

- Keep the server as a single `app.py` file. Don't split into multiple modules unless it exceeds ~800 lines.
- Dashboard UI changes go in the `DASHBOARD_HTML` string in `app.py`.
- Agent must work on Linux, macOS, and Windows. Avoid Unix-only APIs in core logic (signal handling is gated behind `hasattr(signal, "SIGUSR1")`).
