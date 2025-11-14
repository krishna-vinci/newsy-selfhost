web: uvicorn main:app --host 0.0.0.0 --port 8321
worker: rq worker --url redis://$REDIS_HOST:$REDIS_PORT/$REDIS_DB feed-queue --with-scheduler
