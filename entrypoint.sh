#!/usr/bin/env bash
set -euo pipefail

uvicorn app.admin.main:app --host 0.0.0.0 --port "${ADMIN_PORT:-8001}" &
ADMIN_PID=$!

uvicorn app.public.main:app --host 0.0.0.0 --port "${PUBLIC_PORT:-8000}" &
PUBLIC_PID=$!

trap 'kill -TERM $ADMIN_PID $PUBLIC_PID 2>/dev/null' TERM INT

wait -n "$ADMIN_PID" "$PUBLIC_PID"
exit_code=$?
kill -TERM $ADMIN_PID $PUBLIC_PID 2>/dev/null || true
exit $exit_code
