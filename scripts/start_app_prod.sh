#!/bin/bash
set -euo pipefail

mkdir -p /data /tmp/rss-gen-cache

cleanup() {
	echo "Shutting down app processes..."
	jobs -p | xargs -r kill 2>/dev/null || true
	wait || true
	exit 0
}

trap cleanup SIGTERM SIGINT

redis-server --bind 127.0.0.1 --appendonly no --save "" &
REDIS_PID=$!

uvicorn main:app --host 0.0.0.0 --port 8765 &
BACKEND_PID=$!

uvicorn app:app --app-dir /app/rss-gen --host 0.0.0.0 --port 3460 &
DISCOVERY_PID=$!

(
	cd /app/frontend
	node build
) &
FRONTEND_PID=$!

wait -n "$REDIS_PID" "$BACKEND_PID" "$DISCOVERY_PID" "$FRONTEND_PID"
STATUS=$?
echo "One of the app processes exited with status $STATUS"
jobs -p | xargs -r kill 2>/dev/null || true
wait || true
exit "$STATUS"
