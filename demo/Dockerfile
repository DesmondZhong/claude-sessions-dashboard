# Build context is the repo root. See demo/README.md for deployment.
FROM python:3.12-slim

WORKDIR /app

# Install server dependencies
COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt gunicorn

# Copy server code and demo artifacts
COPY server/app.py /app/server/app.py
COPY demo/ /app/demo/

# Use the demo server config
ENV CLAUDE_DASHBOARD_CONFIG=/app/demo/server-config.yaml
# Demo DB lives in /app/demo/demo-sessions.db (seeded at startup)
ENV CLAUDE_DASHBOARD_DB_PATH=/app/demo/demo-sessions.db

# Seed on start so every restart gives a clean demo dataset
CMD ["sh", "-c", "python /app/demo/seed_demo.py && gunicorn --chdir /app/server --bind 0.0.0.0:${PORT:-5050} --workers 2 --access-logfile - app:app"]
