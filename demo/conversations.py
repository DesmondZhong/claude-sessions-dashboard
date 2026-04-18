"""Synthetic demo conversations for the dashboard showcase.

12 sessions across 3 VMs, covering diverse Claude Code scenarios:
tool use (Read/Edit/Bash/Grep), web search/fetch, subagents, long
multi-step builds, short Q&A, and custom-titled sessions.
"""
from datetime import datetime, timedelta, timezone


def days_ago(n, hour=10, minute=0):
    return (datetime.now(timezone.utc) - timedelta(days=n))\
        .replace(hour=hour, minute=minute, second=0, microsecond=0)\
        .isoformat()


def _msg(role, content, ts, mtype=None):
    return {"role": role, "content": content, "timestamp": ts, "type": mtype or role}


def user(c, ts):         return _msg("user", c, ts, "user")
def assistant(c, ts):    return _msg("assistant", c, ts, "assistant")
def system(c, ts):       return _msg("system", c, ts, "system")
def tool_call(name, inp, ts):
    return {"role": "assistant", "content": f"Tool: {name}({inp})",
            "timestamp": ts, "type": "tool_call"}
def tool_result(c, ts):
    return {"role": "tool", "content": c, "timestamp": ts, "type": "tool_result"}


CLIENTS = [
    {"vm_name": "macbook-pro",  "ip_address": "10.0.1.5",    "last_sync": days_ago(0, 11), "session_count": 5},
    {"vm_name": "dev-server",   "ip_address": "192.168.1.100","last_sync": days_ago(0, 10), "session_count": 4},
    {"vm_name": "sandbox",      "ip_address": "172.20.0.3",  "last_sync": days_ago(0, 9),  "session_count": 3},
]


SESSIONS = []


# ─── macbook-pro · Session 1: type hints (short Q&A) ───────────────────────
_ts = lambda h, m=0: days_ago(0, h, m)
SESSIONS.append({
    "id": "s-type-hints-0001",
    "vm_name": "macbook-pro",
    "project": "/Users/demo/projects/webapp",
    "custom_title": "",
    "summary": "Add type hints to the User API signatures",
    "messages": [
        user("Can you add type hints to the functions in api/users.py? I want to catch bugs earlier.", _ts(10, 15)),
        tool_call("Read", "api/users.py", _ts(10, 15, )),
        tool_result("def get_user(id):\n    ...\n\ndef create_user(data):\n    ...\n\ndef list_users(filters=None, limit=50):\n    ...", _ts(10, 16)),
        assistant("Here's what I found. Let me add type hints with proper return types and optional parameters.", _ts(10, 16)),
        tool_call("Edit", "api/users.py", _ts(10, 16)),
        tool_result("Updated 3 functions with type annotations.", _ts(10, 17)),
        assistant("Added:\n```python\ndef get_user(id: int) -> User | None: ...\ndef create_user(data: UserCreate) -> User: ...\ndef list_users(filters: UserFilter | None = None, limit: int = 50) -> list[User]: ...\n```\n\nThe `User | None` syntax requires Python 3.10+. Let me know if you need the older `Optional[User]` form.", _ts(10, 17)),
        user("3.10+ is fine. Does mypy pass now?", _ts(10, 18)),
        tool_call("Bash", "mypy api/users.py", _ts(10, 18)),
        tool_result("Success: no issues found in 1 source file", _ts(10, 18)),
        assistant("Clean. No mypy errors.", _ts(10, 19)),
        user("Perfect, thanks.", _ts(10, 19)),
    ],
})


# ─── macbook-pro · Session 2: CSS grid debugging ──────────────────────────
_ts = lambda h, m=0: days_ago(1, h, m)
SESSIONS.append({
    "id": "s-css-grid-0002",
    "vm_name": "macbook-pro",
    "project": "/Users/demo/projects/webapp",
    "custom_title": "",
    "summary": "The CSS grid layout is broken on mobile — columns overflow",
    "messages": [
        user("The CSS grid layout is broken on mobile. Columns overflow the viewport. Can you take a look?", _ts(14, 30)),
        tool_call("Grep", "grid-template-columns", _ts(14, 30)),
        tool_result("src/styles/layout.css:23:  grid-template-columns: 280px 1fr 200px;\nsrc/styles/cards.css:12:  grid-template-columns: repeat(3, 1fr);", _ts(14, 30)),
        tool_call("Read", "src/styles/layout.css", _ts(14, 31)),
        tool_result(".container {\n  display: grid;\n  grid-template-columns: 280px 1fr 200px;\n  gap: 16px;\n}\n\n@media (max-width: 768px) {\n  .container {\n    grid-template-columns: 1fr;\n  }\n}", _ts(14, 31)),
        assistant("The layout.css media query looks correct for the container. Let me check cards.css — that's the one with `repeat(3, 1fr)` which could overflow on narrow viewports.", _ts(14, 31)),
        user("Yes that's probably it, we have a card grid inside.", _ts(14, 32)),
        tool_call("Read", "src/styles/cards.css", _ts(14, 32)),
        tool_result(".card-grid {\n  display: grid;\n  grid-template-columns: repeat(3, 1fr);\n  gap: 12px;\n}", _ts(14, 32)),
        assistant("Found it. `repeat(3, 1fr)` forces 3 equal columns regardless of viewport. On narrow screens each column gets <100px and content overflows. The fix is `auto-fit` with a minimum:", _ts(14, 33)),
        tool_call("Edit", "src/styles/cards.css", _ts(14, 33)),
        tool_result("Changed grid-template-columns to `repeat(auto-fit, minmax(240px, 1fr))`.", _ts(14, 33)),
        assistant("Now columns collapse to 2 or 1 automatically based on available width, with a 240px minimum per card.", _ts(14, 34)),
        user("That worked. But now there's still a bit of horizontal scroll. Could be padding?", _ts(14, 45)),
        tool_call("Grep", "padding-right|padding-left", _ts(14, 45)),
        tool_result("src/styles/layout.css:15:  padding-left: 24px;\nsrc/styles/layout.css:16:  padding-right: 24px;", _ts(14, 45)),
        assistant("The container has fixed 24px left/right padding. Combined with `width: 100%` this causes overflow. Switching to `box-sizing: border-box` (or using `padding-inline`) will fix it.", _ts(14, 46)),
        user("Apply box-sizing globally please.", _ts(14, 47)),
        tool_call("Edit", "src/styles/layout.css", _ts(14, 47)),
        tool_result("Added `*, *::before, *::after { box-sizing: border-box; }` at top of file.", _ts(14, 47)),
        assistant("Done. Horizontal scroll should be gone now.", _ts(14, 48)),
        user("Confirmed, thanks!", _ts(14, 55)),
    ],
})


# ─── macbook-pro · Session 3: subagent research ──────────────────────────
_ts = lambda h, m=0: days_ago(2, h, m)
SESSIONS.append({
    "id": "s-auth-research-0003",
    "vm_name": "macbook-pro",
    "project": "/Users/demo/projects/webapp",
    "custom_title": "",
    "summary": "Research current best practices for JWT vs session auth",
    "messages": [
        user("I'm redesigning our auth system. Can you research the current best practices between JWT and session-based auth for SPAs in 2026?", _ts(16, 0)),
        assistant("This is a research-heavy question — let me delegate to a research subagent so I can keep the main context focused.", _ts(16, 0)),
        tool_call("Task", "subagent_type=Explore, prompt=Research JWT vs session auth for SPAs in 2026 — cover security, UX, and scaling trade-offs. Report in under 400 words.", _ts(16, 0)),
        tool_result("(subagent) Summary:\n• JWTs excel at stateless APIs and microservices where session stores are a bottleneck.\n• Session cookies (HTTP-only, Secure, SameSite=Lax) are recommended by OWASP for browser-facing SPAs — safer against XSS leaks of tokens and simpler to revoke.\n• Common modern pattern: session cookies for browser clients + short-lived JWTs for service-to-service.\n• Revocation: JWTs need blacklist/rotation; sessions just delete the row.\n• Refresh tokens in httpOnly cookie + access token in memory is a compromise.\nSources: OWASP ASVS 4.0.3, Auth0 engineering blog 2025, PortSwigger.", _ts(16, 2)),
        assistant("Here's the subagent's summary:\n\n**Short answer:** For a browser SPA, prefer session cookies (httpOnly, Secure, SameSite=Lax). Use JWT only for service-to-service or stateless APIs.\n\n**Key trade-offs:**\n- **Revocation**: sessions = delete a row; JWTs = need blacklist or short TTL + rotation.\n- **XSS exposure**: httpOnly cookie isn't readable by JS; localStorage-stored JWT is.\n- **Scaling**: JWTs avoid a session store, but a Redis-backed session store is fine to ~100k rps.\n\n**Modern hybrid**: Session cookie for the browser ↔ API edge; short-lived JWT between your services internally.\n\nOWASP ASVS 4.0.3 still recommends session cookies for browser-facing apps.", _ts(16, 3)),
        user("Makes sense. What about refresh token rotation specifically?", _ts(16, 5)),
        tool_call("WebSearch", "refresh token rotation best practice 2026", _ts(16, 5)),
        tool_result("Top result: \"Refresh Token Rotation\" (auth0.com/docs). Summary: issue a new refresh token on every use; invalidate the old one; detect reuse as breach signal.", _ts(16, 5)),
        assistant("The accepted pattern:\n\n1. Every refresh returns a new `refresh_token` (+ new `access_token`).\n2. The old refresh is invalidated immediately.\n3. If an invalidated token is used again → treat as stolen, revoke the entire token family.\n4. Store refresh in httpOnly cookie; access in memory (never localStorage).\n\nAuth0, Okta, and AWS Cognito all default to this.", _ts(16, 6)),
        user("Great. Can you draft a minimal implementation plan?", _ts(16, 8)),
        assistant("Sure. Here's a pragmatic plan:\n\n**Phase 1 — Sessions for the browser**\n- `POST /login` → sets `session_id` cookie (httpOnly, Secure, SameSite=Lax, 24h)\n- Redis session store, keyed by session_id → `{user_id, created_at, device}`\n- `POST /logout` → deletes the Redis row + clears cookie\n\n**Phase 2 — Internal JWTs**\n- Sign short-lived (5m) JWTs with the user_id claim for service-to-service calls.\n- Rotate signing key quarterly.\n\n**Phase 3 — Refresh tokens (only if you need long-lived sessions)**\n- `refresh_token` in a separate httpOnly cookie, 30-day TTL.\n- Rotate on every use, detect reuse, revoke family on breach.\n\nWant me to scaffold the session store module first?", _ts(16, 9)),
        user("Yes, but later. Saving this plan for now.", _ts(16, 10)),
    ],
})


# ─── macbook-pro · Session 4: async race condition (custom title) ──────────
_ts = lambda h, m=0: days_ago(3, h, m)
SESSIONS.append({
    "id": "s-async-fix-0004",
    "vm_name": "macbook-pro",
    "project": "/Users/demo/projects/data-pipeline",
    "custom_title": "async-race-condition",
    "summary": "Intermittent test failure in the ingestion pipeline",
    "messages": [
        user("The ingestion tests are flaky — they pass locally but fail on CI ~30% of the time. Always the same test: `test_parallel_ingest`.", _ts(9, 30)),
        tool_call("Read", "tests/test_ingest.py", _ts(9, 30)),
        tool_result("async def test_parallel_ingest():\n    pipeline = Pipeline()\n    tasks = [pipeline.ingest(f'batch-{i}') for i in range(10)]\n    results = await asyncio.gather(*tasks)\n    assert pipeline.total_count == 10\n    assert all(r.status == 'ok' for r in results)", _ts(9, 30)),
        tool_call("Read", "src/pipeline.py", _ts(9, 31)),
        tool_result("class Pipeline:\n    def __init__(self):\n        self.total_count = 0\n\n    async def ingest(self, batch_id):\n        result = await self._process(batch_id)\n        self.total_count += 1  # ← read-modify-write on shared state\n        return result", _ts(9, 31)),
        assistant("Found it. `self.total_count += 1` is read-modify-write on shared state with no lock. Under parallel `asyncio.gather`, two coroutines can read the same value before either writes back, so increments get lost.\n\nThe fix is either `asyncio.Lock` or atomic increment via `itertools.count`.", _ts(9, 32)),
        user("Use Lock — I want the code to stay readable.", _ts(9, 32)),
        tool_call("Edit", "src/pipeline.py", _ts(9, 33)),
        tool_result("Added `self._lock = asyncio.Lock()` and wrapped the counter in `async with self._lock`.", _ts(9, 33)),
        user("Can you run the test 50 times to make sure it's actually fixed?", _ts(9, 34)),
        tool_call("Bash", "for i in $(seq 1 50); do pytest tests/test_ingest.py::test_parallel_ingest -x -q || break; done", _ts(9, 34)),
        tool_result("50 passed, 0 failed", _ts(9, 36)),
        assistant("50/50 pass. The race is gone.", _ts(9, 36)),
        user("Wait — will the Lock serialize all ingests? That defeats the parallelism.", _ts(9, 37)),
        assistant("Good catch. The Lock only wraps the counter increment (2 nanoseconds of work) — `_process` still runs in parallel. But you're right that for very high throughput, a lock-free increment is better. Want me to switch to `itertools.count`?", _ts(9, 38)),
        user("No, this is fine for our scale. One more thing — add a comment explaining why the lock is there?", _ts(9, 39)),
        tool_call("Edit", "src/pipeline.py", _ts(9, 39)),
        tool_result("Added: `# Lock prevents lost updates when many ingests complete concurrently.`", _ts(9, 39)),
        user("Perfect, shipping.", _ts(9, 40)),
    ],
})


# ─── macbook-pro · Session 5: React patterns research ──────────────────────
_ts = lambda h, m=0: days_ago(4, h, m)
SESSIONS.append({
    "id": "s-react-patterns-0005",
    "vm_name": "macbook-pro",
    "project": "/Users/demo/projects/webapp",
    "custom_title": "",
    "summary": "Find modern React performance patterns for our dashboard",
    "messages": [
        user("Our React dashboard is slow. Can you find current best-practice patterns for performance in React 19?", _ts(11, 0)),
        tool_call("WebSearch", "React 19 performance patterns 2026", _ts(11, 0)),
        tool_result("Top results: react.dev/learn/render-and-commit, Kent C. Dodds blog on React 19 compiler, Vercel engineering blog on RSC perf.", _ts(11, 1)),
        tool_call("WebFetch", "https://react.dev/learn/you-might-not-need-an-effect", _ts(11, 1)),
        tool_result("Key patterns: derive state from props instead of useEffect; compute expensive values with useMemo; memoize callbacks passed to children with useCallback; split state so only affected components re-render; colocate state near where it's used.", _ts(11, 2)),
        assistant("Here are the current patterns most applicable to a dashboard:\n\n1. **React 19 compiler** — auto-memoizes. If you're on 19+, stop manually `useMemo`-ing. Check `react-compiler-healthcheck`.\n2. **Colocate state** — if only ChartCard uses `hoveredPoint`, don't lift it to the root. Prevents whole-tree re-renders.\n3. **Virtualize long lists** — `react-window` or TanStack Virtual for >100 rows.\n4. **Split contexts** — one giant context → every consumer re-renders. Split by update frequency.\n5. **Suspense + RSC boundaries** — shift data loading to the server where possible.\n\nWant me to profile the dashboard first and point at specific hot spots?", _ts(11, 3)),
        user("Yes — what profiler should I use?", _ts(11, 4)),
        assistant("The built-in React DevTools Profiler is still the right starting point. It shows:\n- Which components rendered\n- Why (props/state/context changed)\n- How long each took\n\nRecord a representative interaction (e.g., filter change), look for components rendering with unchanged props — those are the cheap wins.\n\nFor JS-level perf (not just render), use Chrome DevTools → Performance tab → capture.", _ts(11, 5)),
        user("Ok, I'll profile and come back with specifics. Thanks.", _ts(11, 6)),
    ],
})


# ─── dev-server · Session 1: THE LONG ONE — build task queue ──────────────
_ts = lambda h, m=0: days_ago(5, h, m)
long_msgs = [
    user("I want to build a simple distributed task queue in Python using Redis. Nothing too fancy — just workers, retries, and a CLI to submit jobs. Can you help me build this step by step?", _ts(9, 0)),
    assistant("Yes, this is a great scope for a single-session build. Let me outline the architecture before we write code:\n\n- **Broker**: Redis (list as a FIFO queue per priority)\n- **Worker**: a long-running process that BLPOP's jobs, executes registered task functions, handles retries\n- **Client/CLI**: enqueues a job by name + JSON-serialized args\n- **Results (optional)**: Redis hash keyed by job ID\n\nSound good?", _ts(9, 1)),
    user("Yes, go ahead.", _ts(9, 2)),
    tool_call("Write", "pyproject.toml", _ts(9, 2)),
    tool_result("Created pyproject.toml with deps: redis, click, pydantic.", _ts(9, 2)),
    tool_call("Bash", "uv venv && uv pip install -e .", _ts(9, 3)),
    tool_result("Installed redis 5.0, click 8.1, pydantic 2.5 into .venv.", _ts(9, 3)),
    assistant("Project scaffold is ready. Let me lay out the directory structure:\n```\ntaskq/\n  __init__.py\n  broker.py      # Redis connection + enqueue/dequeue\n  worker.py      # Worker loop\n  registry.py    # Task registration decorator\n  cli.py         # `taskq submit`, `taskq worker`\n```", _ts(9, 4)),
    user("Looks good. Let's start with the registry and broker.", _ts(9, 5)),
    tool_call("Write", "taskq/registry.py", _ts(9, 5)),
    tool_result("Wrote 18 lines: TASKS dict + @task decorator.", _ts(9, 5)),
    tool_call("Write", "taskq/broker.py", _ts(9, 6)),
    tool_result("Wrote 34 lines: enqueue() and dequeue() with Redis BLPOP.", _ts(9, 6)),
    assistant("Done. The registry is a simple dict with a decorator:\n```python\nTASKS = {}\ndef task(name):\n    def decorator(fn):\n        TASKS[name] = fn\n        return fn\n    return decorator\n```\n\nBroker enqueues by `LPUSH queue:default {json}` and dequeues with `BRPOP` (blocking, FIFO).", _ts(9, 7)),
    user("Now the worker class, please.", _ts(9, 8)),
    tool_call("Write", "taskq/worker.py", _ts(9, 8)),
    tool_result("Wrote 48 lines: Worker class with run() loop, task lookup, JSON deserialization.", _ts(9, 9)),
    assistant("The worker polls `BRPOP queue:default 1`, deserializes the payload to `{task, args, kwargs, id, attempts}`, looks up the function in the registry, calls it. On return, writes the result to a Redis hash.", _ts(9, 10)),
    user("How should we handle task failures and retries?", _ts(9, 12)),
    assistant("Standard approach: on exception, increment the `attempts` counter and re-enqueue after a delay until max_retries. Exponential backoff between retries (1s, 2s, 4s, 8s…).\n\nRedis has two options for delayed re-enqueue:\n- Sorted set scored by `time.time() + delay`, polled by the worker\n- `ZADD` with a separate \"scheduler\" process\n\nLet me add the simple version — sorted set, scanned at the start of each worker loop.", _ts(9, 13)),
    tool_call("Edit", "taskq/worker.py", _ts(9, 14)),
    tool_result("Added handle_failure() method: re-enqueues failed tasks to delayed:<queue> sorted set with exponential backoff.", _ts(9, 14)),
    tool_call("Edit", "taskq/worker.py", _ts(9, 15)),
    tool_result("Added _promote_ready_tasks(): moves due tasks from delayed: sorted set back to the main queue.", _ts(9, 15)),
    user("Let's add a priority queue feature. I want at least high/normal/low.", _ts(9, 20)),
    assistant("Cleanest implementation: one Redis list per priority. Worker does `BRPOP queue:high queue:normal queue:low 1` — Redis returns from the first non-empty list, so high-priority jobs get picked first by design.", _ts(9, 20)),
    tool_call("Edit", "taskq/broker.py", _ts(9, 21)),
    tool_result("Added priority parameter to enqueue(); dequeue() now polls high/normal/low in order.", _ts(9, 21)),
    user("How can we monitor the queue? Like, see how many jobs are pending?", _ts(9, 25)),
    tool_call("Write", "taskq/stats.py", _ts(9, 26)),
    tool_result("Wrote 22 lines: queue_depths() and recent_failures() using LLEN and the failures hash.", _ts(9, 26)),
    assistant("`queue_depths()` returns `{'high': 0, 'normal': 14, 'low': 3, 'delayed': 2}`. Should be enough for a basic status check or a `/healthz` endpoint.", _ts(9, 27)),
    user("Now a CLI to submit tasks from the shell.", _ts(9, 30)),
    tool_call("Write", "taskq/cli.py", _ts(9, 31)),
    tool_result("Wrote 35 lines: click CLI with submit/worker/stats commands.", _ts(9, 31)),
    assistant("The CLI:\n```\ntaskq submit send_email --arg to=alice@example.com --arg subject='Hi'\ntaskq worker          # start a worker\ntaskq stats           # show queue depths\n```", _ts(9, 32)),
    user("Can we support scheduled tasks? Like cron — run this task every 5 minutes.", _ts(9, 40)),
    assistant("That's worth pulling out into its own file since it's a different concern. The scheduler process:\n1. Reads a `SCHEDULES` dict (from `@scheduled('*/5 * * * *')` decorator)\n2. On each tick, checks which schedules are due\n3. Enqueues the tasks just like a regular submission\n\nUses `croniter` for cron parsing.", _ts(9, 41)),
    tool_call("Bash", "uv pip install croniter", _ts(9, 42)),
    tool_result("Installed croniter 2.0.", _ts(9, 42)),
    tool_call("Write", "taskq/scheduler.py", _ts(9, 42)),
    tool_result("Wrote 40 lines: @scheduled decorator + Scheduler class with run_forever().", _ts(9, 43)),
    user("Let's add tests for the core worker behavior.", _ts(9, 50)),
    tool_call("Write", "tests/test_worker.py", _ts(9, 51)),
    tool_result("Wrote 65 lines: tests for enqueue, successful run, retry behavior, priority ordering.", _ts(9, 51)),
    tool_call("Bash", "pytest tests/ -v", _ts(9, 52)),
    tool_result("tests/test_worker.py::test_enqueue_and_run PASSED\ntests/test_worker.py::test_retry_on_failure PASSED\ntests/test_worker.py::test_priority_ordering PASSED\ntests/test_worker.py::test_max_retries_moves_to_failures PASSED\n4 passed in 2.3s", _ts(9, 53)),
    assistant("All green. Tests use `fakeredis` so no real Redis needed during tests.", _ts(9, 53)),
    user("What about graceful shutdown? I don't want to lose in-flight jobs on SIGTERM.", _ts(10, 0)),
    tool_call("Edit", "taskq/worker.py", _ts(10, 1)),
    tool_result("Added _shutdown flag + signal handler; worker finishes current task then exits cleanly.", _ts(10, 1)),
    assistant("The worker now:\n1. Catches SIGTERM/SIGINT → sets `_shutdown = True`\n2. Finishes the task it's currently running (no kill)\n3. Exits the loop on next iteration\n4. If running under systemd, configure `TimeoutStopSec=60` so it has a minute to finish.", _ts(10, 2)),
    user("How do we scale this to multiple workers on different machines?", _ts(10, 10)),
    assistant("It already works! Each worker is independent — they all BRPOP the same Redis queues. Redis handles the atomic handoff, so no two workers ever pick the same job.\n\nFor production:\n- Run N workers per machine, M machines → you have N×M parallelism\n- Workers are stateless, so autoscaling is easy\n- Single Redis is the bottleneck at ~50k ops/sec. Past that, use Redis Cluster or split by queue.", _ts(10, 11)),
    user("Add structured logging — I want JSON logs for our log aggregator.", _ts(10, 15)),
    tool_call("Edit", "taskq/worker.py", _ts(10, 16)),
    tool_result("Replaced print() calls with structlog; added correlation_id = job_id for every log line.", _ts(10, 16)),
    assistant("Every log line now includes: `ts`, `level`, `event`, `job_id`, `task_name`, `attempts`, `duration_ms`. Works with Datadog, Elastic, and anything that speaks JSON.", _ts(10, 17)),
    user("Let's add a simple web dashboard to view stats in the browser.", _ts(10, 25)),
    tool_call("Write", "taskq/dashboard.py", _ts(10, 26)),
    tool_result("Wrote 55 lines: Flask app with / showing queue depths + recent failures, auto-refresh every 5s.", _ts(10, 26)),
    assistant("`taskq dashboard --port 8080` starts a Flask app with a single page: queue depth bars + a table of the last 20 failures. Intentionally minimal — if you need more, integrate with Grafana by exposing Prometheus metrics (which we'll add next).", _ts(10, 27)),
    user("How do we handle distributed locks? Sometimes a task should only run once across all workers.", _ts(10, 35)),
    assistant("Classic use case for Redis `SET NX`:\n\n```python\nfrom contextlib import contextmanager\n\n@contextmanager\ndef lock(redis, key, ttl=30):\n    token = secrets.token_hex(16)\n    if not redis.set(f'lock:{key}', token, nx=True, ex=ttl):\n        raise LockError(f'Already held: {key}')\n    try:\n        yield\n    finally:\n        # Only delete if we still own it\n        redis.eval(\"\"\"if redis.call('get',KEYS[1])==ARGV[1]\n                      then return redis.call('del',KEYS[1]) end\"\"\", 1, f'lock:{key}', token)\n```\n\nThe TTL + token pattern prevents stale locks if the worker dies mid-task.", _ts(10, 36)),
    user("What's a good deployment strategy?", _ts(10, 45)),
    assistant("For most teams: Docker container + systemd (or k8s Deployment with replicas). Your `taskq worker` command is the container entrypoint.\n\nExample systemd:\n```\n[Service]\nExecStart=/opt/taskq/bin/taskq worker\nRestart=always\nTimeoutStopSec=60\n```\n\nFor k8s, use a Deployment with `terminationGracePeriodSeconds: 60` and set it to not kill the pod mid-task.\n\nRedis: managed service (ElastiCache, Upstash) is fine for most workloads. Self-hosted only if you want control.", _ts(10, 46)),
    user("Add Prometheus metrics.", _ts(10, 55)),
    tool_call("Bash", "uv pip install prometheus-client", _ts(10, 56)),
    tool_result("Installed prometheus-client 0.20.", _ts(10, 56)),
    tool_call("Edit", "taskq/worker.py", _ts(10, 57)),
    tool_result("Added Counter(tasks_total{task,status}) and Histogram(task_duration_seconds{task}).", _ts(10, 57)),
    tool_call("Edit", "taskq/dashboard.py", _ts(10, 58)),
    tool_result("Added /metrics endpoint serving prometheus_client.generate_latest().", _ts(10, 58)),
    assistant("Scrape `http://worker:8080/metrics` from Prometheus. Metrics:\n- `taskq_tasks_total{task, status}` (counter)\n- `taskq_task_duration_seconds{task}` (histogram with default buckets)\n- `taskq_queue_depth{queue}` (gauge, sampled every 15s)", _ts(10, 59)),
    user("How should we document this?", _ts(11, 5)),
    tool_call("Write", "README.md", _ts(11, 6)),
    tool_result("Wrote 120-line README with install, quickstart, CLI reference, deploying, monitoring sections.", _ts(11, 6)),
    assistant("The README covers:\n1. Install\n2. Quickstart (decorator example + CLI)\n3. Priorities & retries\n4. Scheduling\n5. Deployment (systemd + k8s snippets)\n6. Monitoring (Prometheus + dashboard)\n\nFor per-function docs, docstrings are in place — you can generate HTML with `pdoc taskq`.", _ts(11, 7)),
    user("Thanks, this came together really well!", _ts(11, 10)),
    assistant("Glad it worked out. A recap of what we built:\n\n- **taskq/** Python package, ~500 lines total\n- Redis-backed, priority queues, retries with exponential backoff\n- Graceful shutdown, distributed locks\n- CLI, dashboard, Prometheus metrics\n- 4 tests, all passing\n\nNext if you want to extend: rate limiting per task, dead-letter queue, job chaining.", _ts(11, 11)),
]
SESSIONS.append({
    "id": "s-task-queue-0006",
    "vm_name": "dev-server",
    "project": "/opt/projects/taskq",
    "custom_title": "build-task-queue",
    "summary": "I want to build a simple distributed task queue in Python using Redis",
    "messages": long_msgs,
})


# ─── dev-server · Session 2: DB migration review ──────────────────────────
_ts = lambda h, m=0: days_ago(6, h, m)
SESSIONS.append({
    "id": "s-db-migration-0007",
    "vm_name": "dev-server",
    "project": "/opt/projects/api-gateway",
    "custom_title": "",
    "summary": "Review migration 0042_add_indexes.sql before applying to prod",
    "messages": [
        user("Can you review `migrations/0042_add_indexes.sql` before I apply it to prod? The table has 80M rows.", _ts(14, 0)),
        tool_call("Read", "migrations/0042_add_indexes.sql", _ts(14, 0)),
        tool_result("CREATE INDEX idx_events_user_created ON events(user_id, created_at);\nCREATE INDEX idx_events_type ON events(type);", _ts(14, 0)),
        assistant("Two issues to flag:\n\n1. **Locks writes**: plain `CREATE INDEX` locks the table for writes until it completes. On 80M rows that's 10+ minutes of write downtime.\n2. **No rollback**: if the migration fails halfway, you're stuck.\n\nFix both with `CREATE INDEX CONCURRENTLY` and separate the two indexes into individual migrations.", _ts(14, 1)),
        user("Yeah good point. Rewrite it?", _ts(14, 2)),
        tool_call("Edit", "migrations/0042_add_indexes.sql", _ts(14, 2)),
        tool_result("Split into 0042 and 0043, both using CONCURRENTLY. Added DROP INDEX IF EXISTS as down migrations.", _ts(14, 2)),
        user("How long will CONCURRENTLY take on 80M rows?", _ts(14, 4)),
        assistant("Rule of thumb: 1-2x the time of a regular CREATE INDEX. On an m5.xlarge with decent disk, expect 20-40 minutes for an 80M row b-tree index on (user_id, created_at). The second index on `type` will be faster (~5 min) since it's a single short column.\n\nCONCURRENTLY uses more I/O and CPU but doesn't block writes — so application latency will rise a bit during the build.", _ts(14, 5)),
        user("Can you check if those columns have any nulls? Nulls mess with the index sometimes.", _ts(14, 7)),
        tool_call("Bash", "psql prod -c \"SELECT count(*) FROM events WHERE user_id IS NULL OR created_at IS NULL OR type IS NULL;\"", _ts(14, 7)),
        tool_result(" count\n-------\n     0\n(1 row)", _ts(14, 8)),
        assistant("No nulls in any of the three columns, so `NOT NULL` is already enforced de facto. The indexes will work fine.", _ts(14, 8)),
        user("One last thing — how do I verify the index is actually being used after the migration?", _ts(14, 10)),
        assistant("Run `EXPLAIN ANALYZE` on a representative query:\n```sql\nEXPLAIN ANALYZE SELECT * FROM events \nWHERE user_id = 42 AND created_at > now() - interval '7 days';\n```\n\nLook for `Index Scan using idx_events_user_created` — if you see `Seq Scan` instead, the planner decided the index isn't worth it (usually means the query matches too many rows or the stats are stale; try `ANALYZE events;`).", _ts(14, 11)),
        user("Perfect, will run it post-deploy. Thanks.", _ts(14, 12)),
    ],
})


# ─── dev-server · Session 3: nginx config ──────────────────────────────────
_ts = lambda h, m=0: days_ago(7, h, m)
SESSIONS.append({
    "id": "s-nginx-config-0008",
    "vm_name": "dev-server",
    "project": "/etc/nginx",
    "custom_title": "",
    "summary": "Explain the nginx reverse-proxy config for our API",
    "messages": [
        user("I'm taking over this nginx config. Can you walk me through what `/etc/nginx/sites-available/api.conf` does?", _ts(15, 0)),
        tool_call("Read", "/etc/nginx/sites-available/api.conf", _ts(15, 0)),
        tool_result("upstream api_backend {\n    least_conn;\n    server 10.0.1.10:8080 max_fails=3 fail_timeout=30s;\n    server 10.0.1.11:8080 max_fails=3 fail_timeout=30s;\n    keepalive 32;\n}\n\nserver {\n    listen 443 ssl http2;\n    server_name api.example.com;\n\n    ssl_certificate /etc/letsencrypt/live/api.example.com/fullchain.pem;\n    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;\n\n    location / {\n        proxy_pass http://api_backend;\n        proxy_http_version 1.1;\n        proxy_set_header Connection \"\";\n        proxy_set_header Host $host;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n        proxy_set_header X-Real-IP $remote_addr;\n        proxy_read_timeout 60s;\n    }\n}", _ts(15, 0)),
        assistant("Here's what each piece does:\n\n**upstream api_backend**\n- Two backend API servers at .10 and .11, port 8080\n- `least_conn`: new requests go to whichever backend has fewer active connections\n- `max_fails=3, fail_timeout=30s`: after 3 failed requests, mark the backend down for 30s\n- `keepalive 32`: keep up to 32 idle upstream connections per worker (reduces reconnection overhead)\n\n**server block**\n- HTTPS on 443 with HTTP/2\n- Let's Encrypt cert\n\n**location /** — this is the actual proxy:\n- `proxy_http_version 1.1` + `Connection \"\"` — required for keepalive to the upstream\n- `X-Forwarded-For`/`X-Real-IP` — backend can see real client IP\n- `proxy_read_timeout 60s` — kills requests that take >60s\n\nStandard, well-tuned setup.", _ts(15, 1)),
        user("What's the failure mode if both backends go down?", _ts(15, 3)),
        assistant("Once both are marked unavailable (3 fails each), nginx returns `502 Bad Gateway` immediately without attempting upstream connections for the `fail_timeout` window. After 30s it tries one again — if that succeeds, it comes back online.\n\nIf you want a fallback page instead of a bare 502, add:\n```\nerror_page 502 503 504 /maintenance.html;\nlocation = /maintenance.html {\n    root /var/www/errors;\n    internal;\n}\n```", _ts(15, 4)),
        user("Got it, thanks.", _ts(15, 5)),
    ],
})


# ─── dev-server · Session 4: git merge conflicts ──────────────────────────
_ts = lambda h, m=0: days_ago(8, h, m)
SESSIONS.append({
    "id": "s-git-merge-0009",
    "vm_name": "dev-server",
    "project": "/opt/projects/api-gateway",
    "custom_title": "",
    "summary": "Resolve merge conflicts from the refactor branch",
    "messages": [
        user("I just merged main into my feature branch and got conflicts in 4 files. Can you help me work through them?", _ts(13, 0)),
        tool_call("Bash", "git status", _ts(13, 0)),
        tool_result("On branch feature/user-preferences\nYou have unmerged paths.\n\nUnmerged paths:\n  both modified:   src/api/users.py\n  both modified:   src/models/user.py\n  both modified:   tests/test_users.py\n  both modified:   README.md", _ts(13, 0)),
        tool_call("Bash", "git diff src/models/user.py", _ts(13, 1)),
        tool_result("<<<<<<< HEAD\nclass User(BaseModel):\n    id: int\n    email: str\n    preferences: UserPrefs = Field(default_factory=UserPrefs)\n=======\nclass User(BaseModel):\n    id: int\n    email: str\n    display_name: str | None = None\n>>>>>>> main", _ts(13, 1)),
        assistant("`src/models/user.py`: your branch added `preferences`, main added `display_name`. These don't conflict semantically — you just need to keep both fields. Let me resolve.", _ts(13, 2)),
        tool_call("Edit", "src/models/user.py", _ts(13, 2)),
        tool_result("Kept both `preferences` and `display_name` fields.", _ts(13, 2)),
        user("And the api/users.py one?", _ts(13, 3)),
        tool_call("Bash", "git diff src/api/users.py", _ts(13, 3)),
        tool_result("<<<<<<< HEAD\ndef get_user(id: int) -> User:\n    user = db.get(id)\n    user.preferences = load_prefs(id)\n    return user\n=======\ndef get_user(id: int) -> User:\n    user = db.get(id)\n    if not user:\n        raise NotFoundError(f\"user {id}\")\n    return user\n>>>>>>> main", _ts(13, 4)),
        assistant("This one needs both the null-check from main AND your preferences loading. Merge them in the correct order — null-check first, then load prefs:\n```python\ndef get_user(id: int) -> User:\n    user = db.get(id)\n    if not user:\n        raise NotFoundError(f\"user {id}\")\n    user.preferences = load_prefs(id)\n    return user\n```", _ts(13, 5)),
        tool_call("Edit", "src/api/users.py", _ts(13, 5)),
        tool_result("Applied combined fix.", _ts(13, 5)),
        user("Tests next.", _ts(13, 7)),
        tool_call("Bash", "git diff tests/test_users.py", _ts(13, 7)),
        tool_result("Both sides added a new test function at the end of the file — no actual semantic conflict, just adjacent lines.", _ts(13, 7)),
        tool_call("Edit", "tests/test_users.py", _ts(13, 8)),
        tool_result("Kept both test functions.", _ts(13, 8)),
        user("And README.md — probably just trivial?", _ts(13, 10)),
        tool_call("Edit", "README.md", _ts(13, 10)),
        tool_result("Both sides added a bullet to the Features list; kept both.", _ts(13, 10)),
        tool_call("Bash", "pytest -x && git add -A && git commit --no-edit", _ts(13, 11)),
        tool_result("42 passed in 5.1s\n[feature/user-preferences abc1234] Merge branch 'main' into feature/user-preferences", _ts(13, 12)),
        assistant("All conflicts resolved, tests pass, merge commit created. You're ready to push.", _ts(13, 12)),
        user("Thanks for walking through it.", _ts(13, 13)),
    ],
})


# ─── sandbox · Session 1: regex help (no tools) ────────────────────────────
_ts = lambda h, m=0: days_ago(9, h, m)
SESSIONS.append({
    "id": "s-regex-help-0010",
    "vm_name": "sandbox",
    "project": "/home/demo/scratch",
    "custom_title": "",
    "summary": "Regex to validate email addresses — what's reasonable?",
    "messages": [
        user("What's a reasonable regex for validating email addresses? I don't need RFC-5322 perfect, just good enough to catch typos.", _ts(18, 0)),
        assistant("Honestly — the shortest one that catches >99% of real typos is:\n\n```\n^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$\n```\n\nIt requires: something, @, something, ., something, all without spaces. Misses almost no valid emails and rejects obviously bad ones.\n\nIf you want stricter character classes:\n\n```\n^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$\n```\n\nBut: if the email is used for actual delivery, don't validate with regex — send a confirmation email. That catches 100% of bad emails including valid-looking ones at nonexistent domains.", _ts(18, 1)),
        user("Good point on the confirmation email. Is the first regex safe from ReDoS?", _ts(18, 3)),
        assistant("Yes. It has no nested quantifiers or backtracking hazards — every `[^\\s@]+` is followed by a fixed literal (`@`, `.`). Linear in input length.\n\nA dangerous pattern would look like `(a+)+$` where the engine can explore exponentially many paths. Nothing like that here.", _ts(18, 4)),
        user("Thanks.", _ts(18, 5)),
    ],
})


# ─── sandbox · Session 2: Docker networking ───────────────────────────────
_ts = lambda h, m=0: days_ago(10, h, m)
SESSIONS.append({
    "id": "s-docker-debug-0011",
    "vm_name": "sandbox",
    "project": "/home/demo/projects/docker-lab",
    "custom_title": "",
    "summary": "Container can't reach postgres on the same docker network",
    "messages": [
        user("My API container can't connect to the postgres container even though they're on the same Docker network. I've tried `postgres:5432` and it hangs.", _ts(10, 30)),
        tool_call("Bash", "docker ps", _ts(10, 30)),
        tool_result("CONTAINER ID   IMAGE                COMMAND                  PORTS\nabc123         api:latest           \"./run.sh\"               8080/tcp\ndef456         postgres:16          \"docker-entrypoint…\"    0.0.0.0:5432->5432/tcp", _ts(10, 31)),
        tool_call("Bash", "docker network inspect bridge | grep -A5 Containers", _ts(10, 31)),
        tool_result("        \"Containers\": {}", _ts(10, 31)),
        assistant("Found it. Both containers are running but `docker network inspect bridge` shows no containers attached. They're probably on the default bridge network and using different networks per `docker-compose` service.\n\nLet me check.", _ts(10, 32)),
        tool_call("Bash", "docker network ls", _ts(10, 32)),
        tool_result("NETWORK ID    NAME              DRIVER\nabc           bridge            bridge\ndef           host              host\nghi           dockerlab_default bridge", _ts(10, 32)),
        tool_call("Bash", "docker network inspect dockerlab_default", _ts(10, 33)),
        tool_result("Containers: {def456: postgres} — only the postgres container is on this network.", _ts(10, 33)),
        assistant("That's the problem. Your API container was started with `docker run` outside of `docker-compose`, so it's on the default `bridge` network. Postgres is on `dockerlab_default` (created by compose).\n\nEither:\n1. Run the API via docker-compose so it joins the same network (preferred)\n2. Or attach the API to the compose network: `docker network connect dockerlab_default <api-container-id>`", _ts(10, 34)),
        user("I'll go with option 1. Can you show me the docker-compose.yaml?", _ts(10, 36)),
        tool_call("Read", "docker-compose.yaml", _ts(10, 36)),
        tool_result("services:\n  postgres:\n    image: postgres:16\n    ports: [\"5432:5432\"]\n    environment: {POSTGRES_PASSWORD: dev}", _ts(10, 36)),
        assistant("You don't have the `api` service in compose yet. Add:\n```yaml\n  api:\n    build: .\n    depends_on: [postgres]\n    environment:\n      DATABASE_URL: postgres://postgres:dev@postgres:5432/postgres\n    ports: [\"8080:8080\"]\n```\n\nThen `docker-compose up --build`. Hostname `postgres` will resolve because compose puts both on the same network and registers service names as DNS.", _ts(10, 37)),
        user("That worked. Why does compose use the service name as hostname?", _ts(10, 42)),
        assistant("Compose creates a user-defined bridge network for the project, and Docker's embedded DNS resolver automatically registers each container's service name as a DNS A record on that network.\n\nSo `postgres:5432` works because `postgres` resolves to the container's IP. The default `bridge` network doesn't do this — you'd have to use `--link` (deprecated) or IPs.", _ts(10, 43)),
        user("Makes sense, thanks.", _ts(10, 45)),
    ],
})


# ─── sandbox · Session 3: API design review with web search ───────────────
_ts = lambda h, m=0: days_ago(11, h, m)
SESSIONS.append({
    "id": "s-api-design-0012",
    "vm_name": "sandbox",
    "project": "/home/demo/projects/api-design-doc",
    "custom_title": "",
    "summary": "Review REST vs GraphQL tradeoff for mobile app backend",
    "messages": [
        user("We're picking an API style for a new mobile app backend. 3 platforms (iOS/Android/Web), read-heavy, ~20 resource types. REST vs GraphQL — what's the current thinking?", _ts(16, 0)),
        tool_call("WebSearch", "GraphQL vs REST mobile backend 2026 tradeoffs", _ts(16, 0)),
        tool_result("Top results: apollographql.com/blog (GraphQL vendor, biased), netflixtechblog.com on Federation, stackoverflow survey 2025 showing REST still dominant.", _ts(16, 0)),
        tool_call("WebFetch", "https://netflixtechblog.com/how-netflix-scales-its-api-with-graphql", _ts(16, 1)),
        tool_result("Netflix uses GraphQL Federation for cross-team schema composition. Key value: each team owns a subgraph; clients get one endpoint. Costs: schema coordination, operational complexity, harder caching.", _ts(16, 2)),
        assistant("Honest summary for your constraints:\n\n**GraphQL wins if:**\n- Multiple clients need different subsets of the same data (mobile wants less than web — classic GraphQL strength)\n- You have the team to own a schema + tooling (Apollo/Relay)\n- Over-fetching on 20 resource types would be real\n\n**REST wins if:**\n- Endpoint-level caching matters (CDN-friendly)\n- Simple CRUD dominates (no deep nested reads)\n- You don't have a GraphQL-experienced team yet\n\nFor a read-heavy mobile app with 3 clients, GraphQL's variable-response-shape is a genuine fit. But the operational cost is non-trivial — subscriptions, N+1 query issues, query cost analysis.\n\nA middle ground worth considering: REST + `include=` query param for eager-loading (as JSON:API does).", _ts(16, 3)),
        user("What about BFF pattern?", _ts(16, 5)),
        assistant("BFF (Backend-for-Frontend) is the pragmatic compromise:\n\n- One REST-ish service per client (`mobile-bff`, `web-bff`)\n- Each BFF composes calls to internal services and returns tailored responses\n- No schema language needed, just idiomatic HTTP\n\nTradeoffs:\n- **Pro**: clients are simple; each BFF is tuned to one UI\n- **Pro**: easy to cache per endpoint at the CDN\n- **Con**: code duplication across BFFs\n- **Con**: one more service to run per client\n\nFor 3 clients this is manageable. For 10+ clients, GraphQL Federation starts to pay off.", _ts(16, 6)),
        user("Great, I think we'll start with REST + BFFs and revisit if we feel the pain. Can you write up the decision as an ADR?", _ts(16, 10)),
        tool_call("Write", "docs/adr/0007-api-style.md", _ts(16, 11)),
        tool_result("Wrote 45-line ADR with context, decision, consequences, alternatives.", _ts(16, 11)),
        assistant("ADR 0007 drafted. Structure:\n- **Context**: 3 clients, 20 resource types, read-heavy\n- **Decision**: REST with per-client BFFs\n- **Consequences**: simpler start, some duplication, revisit if client count grows\n- **Alternatives considered**: GraphQL (rejected: team velocity), BFF-less shared REST (rejected: over-fetching on mobile)", _ts(16, 12)),
        user("Thanks, that's exactly the shape I needed.", _ts(16, 13)),
    ],
})
