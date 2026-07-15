#!/usr/bin/env bash
# Start/stop/status the admin + public servers locally, outside Docker.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
RUN_DIR="$ROOT_DIR/.dev-run"

export DATA_DIR="$ROOT_DIR/data"
export MEDIA_INBOX_DIR="$ROOT_DIR/inbox"
export MEDIA_LIBRARY_ROOT="$ROOT_DIR/library"
export MEDIA_MANUAL_REVIEW_DIR="$ROOT_DIR/manual_review"
export PYTHONPATH="$ROOT_DIR"
ADMIN_PORT="${ADMIN_PORT:-8001}"
PUBLIC_PORT="${PUBLIC_PORT:-8000}"

ADMIN_PID_FILE="$RUN_DIR/admin.pid"
PUBLIC_PID_FILE="$RUN_DIR/public.pid"
ADMIN_LOG="$RUN_DIR/admin.log"
PUBLIC_LOG="$RUN_DIR/public.log"

ensure_venv() {
  if [ ! -x "$VENV_DIR/bin/uvicorn" ]; then
    echo "Setting up venv in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --quiet -r "$ROOT_DIR/requirements.txt"
  fi
}

is_running() {
  local pid_file="$1"
  [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null
}

start_one() {
  local name="$1" app="$2" port="$3" pid_file="$4" log="$5"
  if is_running "$pid_file"; then
    echo "$name already running (pid $(cat "$pid_file"))"
    return
  fi
  nohup "$VENV_DIR/bin/uvicorn" "$app" --host 127.0.0.1 --port "$port" \
    > "$log" 2>&1 &
  echo $! > "$pid_file"
  disown
  echo "$name started (pid $(cat "$pid_file")) on http://127.0.0.1:$port"
}

stop_one() {
  local name="$1" pid_file="$2"
  if is_running "$pid_file"; then
    kill "$(cat "$pid_file")"
    echo "$name stopped"
  else
    echo "$name not running"
  fi
  rm -f "$pid_file"
}

status_one() {
  local name="$1" pid_file="$2" port="$3"
  if is_running "$pid_file"; then
    echo "$name: running (pid $(cat "$pid_file"), http://127.0.0.1:$port)"
  else
    echo "$name: stopped"
  fi
}

start() {
  mkdir -p "$RUN_DIR" "$DATA_DIR" "$MEDIA_INBOX_DIR" "$MEDIA_LIBRARY_ROOT" "$MEDIA_MANUAL_REVIEW_DIR"
  ensure_venv
  start_one "admin" app.admin.main:app "$ADMIN_PORT" "$ADMIN_PID_FILE" "$ADMIN_LOG"
  start_one "public" app.public.main:app "$PUBLIC_PORT" "$PUBLIC_PID_FILE" "$PUBLIC_LOG"
}

stop() {
  stop_one "admin" "$ADMIN_PID_FILE"
  stop_one "public" "$PUBLIC_PID_FILE"
}

status() {
  status_one "admin" "$ADMIN_PID_FILE" "$ADMIN_PORT"
  status_one "public" "$PUBLIC_PID_FILE" "$PUBLIC_PORT"
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  status) status ;;
  restart) stop; start ;;
  *)
    echo "Usage: $0 {start|stop|status|restart}" >&2
    exit 1
    ;;
esac
