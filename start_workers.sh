#!/bin/bash
# Start multiple RQ workers in a single container

WORKER_COUNT=${WORKER_COUNT:-4}
REDIS_URL="redis://${REDIS_HOST}:${REDIS_PORT}/${REDIS_DB}"

echo "Starting ${WORKER_COUNT} RQ workers..."

# Generate unique worker names using timestamp and random suffix
TIMESTAMP=$(date +%s)
RANDOM_SUFFIX=$RANDOM

# Cleanup function to handle graceful shutdown
cleanup() {
    echo "Shutting down workers..."
    kill $(jobs -p) 2>/dev/null
    wait
    exit 0
}

trap cleanup SIGTERM SIGINT

# Start workers in background with unique names
for i in $(seq 1 $WORKER_COUNT); do
    WORKER_NAME="worker-${TIMESTAMP}-${RANDOM_SUFFIX}-${i}"
    rq worker --url "$REDIS_URL" feed-queue --name "$WORKER_NAME" --with-scheduler &
    echo "Started $WORKER_NAME (PID: $!)"
done

# Wait for all background processes
wait
