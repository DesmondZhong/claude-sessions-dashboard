# Claude Sessions Dashboard

Centrally view and manage Claude Code conversations across multiple VMs.

## Architecture

- **Server** (`server/app.py`) — Flask + SQLite dashboard, runs on your central machine
- **Agent** (`agent/agent.py`) — lightweight sync script, runs on each VM

Agents periodically push session data to the server. The server stores everything in SQLite and serves a web dashboard.

## Quick Start

### 1. Server Setup (your Mac Mini)

```bash
cd server
pip install -r requirements.txt

# Edit config — set your API key
vim server-config.yaml

python app.py
```

Dashboard available at `http://localhost:5000`.

### 2. Agent Setup (each VM)

```bash
cd agent
pip install -r requirements.txt

# Edit config — set server URL, API key, and VM name
vim agent-config.yaml

# Sync once
python agent.py --once

# Or run as daemon
python agent.py --daemon
```

### 3. Cron Setup (optional)

Sync every 5 minutes:

```bash
crontab -e
# Add:
*/5 * * * * cd /path/to/claude-sessions/agent && python agent.py --once >> /tmp/claude-sync.log 2>&1
```

## Exposing with Cloudflare Tunnel

To access the dashboard from anywhere with authentication:

```bash
# Install cloudflared
# https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

# Login
cloudflared tunnel login

# Create tunnel
cloudflared tunnel create claude-dashboard

# Route to your domain
cloudflared tunnel route dns claude-dashboard claude-sessions.yourdomain.com

# Run tunnel
cloudflared tunnel --url http://localhost:5000 run claude-dashboard
```

Then set up **Cloudflare Access** in the Cloudflare Zero Trust dashboard to add authentication (Google, GitHub, email OTP, etc.) in front of your tunnel.

## Configuration

### Server (`server/server-config.yaml`)

| Key | Description | Default |
|-----|-------------|---------|
| `api_key` | Shared secret for agent auth | (required) |
| `host` | Bind address | `0.0.0.0` |
| `port` | Port | `5000` |
| `db_path` | SQLite database path | `./sessions.db` |
| `debug` | Flask debug mode | `false` |

### Agent (`agent/agent-config.yaml`)

| Key | Description | Default |
|-----|-------------|---------|
| `server_url` | Dashboard server URL | (required) |
| `api_key` | Shared secret | (required) |
| `vm_name` | Label for this machine | hostname |
| `sync_interval` | Seconds between syncs (daemon mode) | `300` |
