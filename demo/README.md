# Demo

Synthetic dataset and deployment configs for a public demo of the dashboard.

There are two deployment shapes:

1. **Static export (recommended for a public demo)** — `build_static.py` produces a single self-contained HTML file at `static/index.html`. Drop it on GitHub Pages, Cloudflare Pages, Netlify, or any static host. Zero cold start, zero cost, no server.
2. **Live Flask server on Render** — `Dockerfile` + `render.yaml`. Real backend, but the free tier sleeps after 15 min of idle (~30s cold-start on the next request).

## What's in here

- `conversations.py` — 12 synthetic sessions across 3 VMs (`macbook-pro`, `dev-server`, `sandbox`). Covers diverse Claude Code scenarios: tool use (Read/Edit/Bash/Grep/WebSearch/WebFetch), subagent delegation, short Q&A, one long multi-step build (~20 user messages) to showcase the navigation sidebar, and one session with a custom title.
- `seed_demo.py` — wipes and re-creates `demo-sessions.db` from the conversation data.
- `build_static.py` — bundles the demo data + a `fetch` shim into `static/index.html` so the dashboard runs entirely client-side.
- `static/index.html` — the generated static demo (committed so GitHub Pages can serve it directly).
- `server-config.yaml` — minimal demo config (secrets come from env vars).
- `Dockerfile` — containerizes the server and runs the seed on every startup.
- `render.yaml` — one-click deploy blueprint for [Render](https://render.com).

## Run locally (live server)

From the repo root:

```bash
python demo/seed_demo.py
CLAUDE_DASHBOARD_CONFIG=$(pwd)/demo/server-config.yaml \
CLAUDE_DASHBOARD_DB_PATH=$(pwd)/demo/demo-sessions.db \
CLAUDE_DASHBOARD_PORT=5099 \
python server/app.py
```

Open <http://localhost:5099>.

## Build the static demo

```bash
python demo/build_static.py
```

This (re-)seeds the demo DB if needed, fetches every session through the real Flask routes, embeds the JSON in the page, and shims `window.fetch` so the dashboard runs entirely client-side. Output: `demo/static/index.html` (~100 KB, single file, no external assets except the marked.js CDN).

Preview locally:

```bash
python -m http.server -d demo/static 5097
```

Then open <http://localhost:5097>.

## Deploy the static demo

The output is a plain HTML file; any static host works.

### Netlify (recommended)

A `netlify.toml` at the repo root configures the build automatically. In Netlify: **Add new site** → **Import an existing project** → connect GitHub → pick this repo. Done — every push to `main` redeploys.

If you'd rather configure manually:
- **Build command**: `pip install -r server/requirements.txt && python demo/build_static.py`
- **Publish directory**: `demo/static`

### Cloudflare Pages

Same settings as Netlify (build command + publish directory). Cloudflare Pages doesn't read `netlify.toml`, so set them via the dashboard.

### GitHub Pages

GitHub Pages' "Deploy from a branch" mode only accepts `/` or `/docs/` as the publish folder, not `/demo/static`. Two ways around it:
- Move the build output to `/docs/` (small change to `build_static.py`), or
- Use a GitHub Actions workflow with the modern Pages source (any folder).

### Anywhere else

Just upload `demo/static/index.html`. No backend required.

## Deploy to Render (live server)

1. Push the repo to GitHub (you've already done this).
2. In Render: **New +** → **Blueprint** → select your repo.
3. Render detects `demo/render.yaml` and proposes the service.
4. In the **Environment** section of the service, set:
   - `CLAUDE_DASHBOARD_API_KEY` — pick any random string. This protects the admin endpoints (Rename / Move / Delete). Without this set, visitors could modify the demo data.
   
   Generate one:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
5. Click **Create Blueprint**. Render builds the Docker image, seeds the DB, and starts the server. Takes ~3 minutes first time.
6. Your demo is live at `https://claude-sessions-demo.onrender.com` (or whatever name you chose).

**Note**: Render's free tier spins the container down after 15 minutes of inactivity. The first request after idle will take ~30s to cold-start, after which the DB re-seeds and everything is fresh.

## Data freshness

The DB re-seeds on every container restart, so:
- Visitors can click around freely — their Rename/Move/Delete attempts fail without the API key.
- If you do log in with the admin key and change things, the changes persist until the next restart.
- To force a refresh, trigger a redeploy in Render.

## Editing the demo content

Edit `conversations.py`. The format is a list of `SESSIONS`, each a dict with
`id`, `vm_name`, `project`, `custom_title`, `summary`, and `messages`. Helper
functions `user()`, `assistant()`, `tool_call()`, `tool_result()`, `system()`
keep the content readable.

Then:
- For the static demo: `python demo/build_static.py` and commit `demo/static/index.html`. GitHub Pages picks it up on the next push.
- For the Render server: `python demo/seed_demo.py` locally, or just redeploy — the container re-seeds on every restart.
