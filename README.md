# Claude Sessions Dashboard

Centrally view and manage Claude Code conversations across multiple machines.

See [`demo/`](./demo/) for a live showcase with synthetic data, including a one-click Render deploy.

## Architecture

```
  Machine A (client)    Machine B (client)    Machine C (client)
  ┌──────────┐         ┌──────────┐         ┌──────────┐
  │ client.py│         │ client.py│         │ client.py│
  └────┬─────┘         └────┬─────┘         └────┬─────┘
       │                    │                    │
       │    POST /api/sync  │                    │
       └────────────────────┼────────────────────┘
                            │
                            ▼
               ┌────────────────────┐
               │  Server (app.py)   │
               │  Flask + SQLite    │
               │  + JSONL backups   │
               └────────────────────┘
                            │
                   Cloudflare Tunnel
                 + Cloudflare Access
                            │
                    Browser (anywhere)
```

- **Server** (`server/app.py`) — Flask + SQLite dashboard. Stores parsed sessions in SQLite and raw JSONL backups on disk.
- **Client** (`client/client.py`) — lightweight sync script on each machine. Reads local `~/.claude/` session files and pushes to the server.

## Quick Start

### 1. Server Setup

```bash
# Set up secrets (optional — or set in server-config.yaml)
cp .env.example .env && vim .env

# Install as a service (installs uv + deps automatically)
cd server
chmod +x install-service.sh
./install-service.sh

# Or run directly for development
uv venv && uv pip install -r requirements.txt
python app.py
```

Dashboard available at `http://localhost:5050`.

### 2. Client Setup (each machine)

```bash
cd client

# Edit config — set server URL and machine name
vim client-config.yaml

# Install as a service (installs uv + deps automatically)
chmod +x install-service.sh
./install-service.sh

# Or test manually
python client.py --once
```

The client runs in daemon mode as a background service, syncing every hour by default (configurable via `sync_interval` in `client-config.yaml`). It starts automatically on boot.

To trigger an immediate sync without waiting for the next interval:

```bash
python client.py --trigger
```

This sends a signal to the running daemon, which syncs right away and then resumes its normal schedule.

## Service Management

Both the server and client can be installed as persistent services that start on boot. No tmux, screen, or cron needed.

### Linux (systemd)

**Server:**
```bash
cd server && chmod +x install-service.sh && ./install-service.sh
```

```bash
sudo systemctl status claude-dashboard
sudo systemctl stop claude-dashboard
sudo systemctl restart claude-dashboard
sudo journalctl -u claude-dashboard -f   # view logs
```

**Client (on each machine):**
```bash
cd client && chmod +x install-service.sh && ./install-service.sh
```

```bash
sudo systemctl status claude-dashboard-client
sudo systemctl stop claude-dashboard-client
sudo systemctl restart claude-dashboard-client
sudo journalctl -u claude-dashboard-client -f
```

Uninstall either with `./uninstall-service.sh` in the respective directory.

### macOS (launchd)

**Server:**
```bash
cd server && chmod +x install-service.sh && ./install-service.sh
```

```bash
launchctl list | grep claude-dashboard
launchctl stop com.claude-dashboard
launchctl start com.claude-dashboard
tail -f /tmp/claude-dashboard.log
```

**Client:**
```bash
cd client && chmod +x install-service.sh && ./install-service.sh
```

```bash
launchctl list | grep claude-dashboard-client
launchctl stop com.claude-dashboard-client
launchctl start com.claude-dashboard-client
tail -f /tmp/claude-dashboard-client.log
```

Uninstall either with `./uninstall-service.sh` in the respective directory.

### Windows (NSSM or Scheduled Task)

Run PowerShell as Administrator:

**Server:**
```powershell
cd server
.\install-service.ps1
```

**Client:**
```powershell
cd client
.\install-service.ps1
```

If [NSSM](https://nssm.cc/) is installed, these create proper Windows services. Otherwise, they fall back to scheduled tasks that run at logon.

## Making the Server Reachable Across Machines

Your clients need to reach the server over the network. Options:

### Option A: Cloudflare Tunnel (recommended for internet access)

Exposes your server securely without opening ports or configuring firewalls.

```bash
# Install cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
cloudflared tunnel login
cloudflared tunnel create claude-dashboard
cloudflared tunnel route dns claude-dashboard sessions.yourdomain.com
cloudflared tunnel --url http://localhost:5050 run claude-dashboard
```

Then configure **Cloudflare Access** to protect the dashboard:

1. **Add an Access application** — in [Zero Trust dashboard](https://one.dash.cloudflare.com/) → Access → Applications → Add an application → Self-hosted. Set the domain to your tunnel hostname (e.g. `sessions.yourdomain.com`).

2. **Add an Access policy for browser users** — create a policy with an identity provider (Google, GitHub, email OTP, etc.) so you can log in via the browser.

3. **Create a Service Token for clients** — go to Access → Service Auth → Service Tokens → Create Service Token. Copy the **Client ID** and **Client Secret** (the secret is only shown once).

4. **Add a Service Token policy** — in your Access application, add a second policy:
   - Action: **Service Auth**
   - Include: **Service Token** → select the token you created
   
   This lets the client bypass identity login and authenticate with the token headers instead.

5. **Configure the client** — add the service token credentials to `client-config.yaml`:

   ```yaml
   # client-config.yaml
   server_url: "https://sessions.yourdomain.com"
   api_key: "your-shared-secret"
   cf_access_client_id: "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.access"
   cf_access_client_secret: "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
   ```

   The client sends these as `CF-Access-Client-Id` and `CF-Access-Client-Secret` headers on every request.

### Option B: Tailscale / ZeroTier (private mesh VPN)

If all machines are on Tailscale, the server is reachable via its Tailscale IP (e.g., `http://100.x.y.z:5050`). No public exposure needed.

### Option C: Direct IP / LAN

If machines are on the same network, use the server's LAN IP directly. For machines on different networks, you'll need port forwarding on your router (port 5050).

Set the client config accordingly:

```yaml
# client-config.yaml
server_url: "https://sessions.yourdomain.com"  # Cloudflare Tunnel
# server_url: "http://100.64.0.1:5050"         # Tailscale
# server_url: "http://192.168.1.50:5050"        # LAN
```

## Raw JSONL Backups

In addition to the SQLite database, the server stores raw JSONL session files in `server/backups/<vm-name>/`. This preserves the original Claude Code session format including all metadata, tool calls, and thinking blocks.

## Configuration

All config values can be overridden with environment variables, so you don't need to put secrets in the yaml files. Environment variables take precedence over yaml values. You can set them in a `.env` file (already gitignored) or export them in your shell.

### Server (`server/server-config.yaml`)

| Key | Env var | Description | Default |
|-----|---------|-------------|---------|
| `api_key` | `CLAUDE_DASHBOARD_API_KEY` | Shared secret for client auth | (required) |
| `host` | `CLAUDE_DASHBOARD_HOST` | Bind address | `0.0.0.0` |
| `port` | `CLAUDE_DASHBOARD_PORT` | Port | `5050` |
| `db_path` | `CLAUDE_DASHBOARD_DB_PATH` | SQLite database path | `./sessions.db` |
| `backup_dir` | — | Raw JSONL backup directory | `./backups` |
| `debug` | — | Flask debug mode | `false` |

### Client (`client/client-config.yaml`)

| Key | Env var | Description | Default |
|-----|---------|-------------|---------|
| `server_url` | `CLAUDE_DASHBOARD_SERVER_URL` | Dashboard server URL | (required) |
| `api_key` | `CLAUDE_DASHBOARD_API_KEY` | Shared secret | (required) |
| `vm_name` | `CLAUDE_DASHBOARD_VM_NAME` | Label for this machine | hostname |
| `sync_interval` | — | Seconds between syncs (daemon mode) | `3600` |
| `cf_access_client_id` | `CF_ACCESS_CLIENT_ID` | Cloudflare Access service token Client ID | (optional) |
| `cf_access_client_secret` | `CF_ACCESS_CLIENT_SECRET` | Cloudflare Access service token Client Secret | (optional) |

## Client Commands

| Command | Description |
|---------|-------------|
| `python client.py --once` | Sync once and exit |
| `python client.py --daemon` | Run continuously (used by the service) |
| `python client.py --trigger` | Signal running daemon to sync immediately |

## Local Development / Debug Mode

To run the server with Flask's debug mode (auto-reload on code changes, detailed error pages, interactive debugger):

```bash
cd server

# Option 1: Set debug: true in server-config.yaml
# debug: true

# Option 2: Use Flask's environment variable (overrides config)
FLASK_DEBUG=1 python app.py
```

Debug mode enables:
- **Auto-reload** — the server restarts automatically when you edit `app.py`
- **Interactive debugger** — in-browser debugger on unhandled exceptions
- **Detailed tracebacks** — full stack traces instead of generic 500 errors

> **Warning:** Never run debug mode in production. The interactive debugger allows arbitrary code execution.

## Dashboard Features

The web dashboard includes:

- **Clients panel** — expandable section at the top showing all connected clients with their name, IP address, session count, last sync time, and online/stale/offline status
- **Session list** — all sessions across all machines, searchable and filterable by VM or project
- **Session detail** — click any session to view the full conversation with collapsible tool calls
- **Message navigation** — sticky sidebar listing all user messages for quick jump-to navigation within a session
