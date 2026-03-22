#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"
LOG_DIR="$ROOT_DIR/logs"
PID_FILE="$RUN_DIR/paper_runtime.pid"
LOG_FILE="$LOG_DIR/paper_runtime.log"
RUNTIME_APP_CONFIG="$RUN_DIR/paper.app.runtime.yaml"

PYTHON_BIN="${PYTHON_BIN:-/home/administrator/.venv/bin/python}"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"

load_env() {
  if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
  fi

  export CATS_MODE="paper"
  export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
  export CATS_APP_CONFIG_TEMPLATE="${CATS_APP_CONFIG_TEMPLATE:-$ROOT_DIR/configs/app.example.yaml}"
  export CATS_RISK_CONFIG="${CATS_RISK_CONFIG:-$ROOT_DIR/configs/risk.example.yaml}"
  export CATS_SYMBOLS_CONFIG="${CATS_SYMBOLS_CONFIG:-$ROOT_DIR/configs/symbols.example.yaml}"
}

prepare_runtime_app_config() {
  mkdir -p "$RUN_DIR"

  if [[ ! -f "$CATS_APP_CONFIG_TEMPLATE" ]]; then
    echo "missing app config template: $CATS_APP_CONFIG_TEMPLATE" >&2
    exit 1
  fi

  "$PYTHON_BIN" - <<'PY'
from pathlib import Path
import yaml
import os

source = Path(os.environ["CATS_APP_CONFIG_TEMPLATE"])
target = Path(os.environ["RUNTIME_APP_CONFIG"])
data = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
if not isinstance(data, dict):
    raise SystemExit(f"app config template must be a mapping: {source}")
data["mode"] = "paper"
target.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
PY

  export CATS_APP_CONFIG="$RUNTIME_APP_CONFIG"
}

validate_startup() {
  if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "python not executable: $PYTHON_BIN" >&2
    exit 1
  fi

  if [[ ! -f "$CATS_RISK_CONFIG" ]]; then
    echo "missing risk config: $CATS_RISK_CONFIG" >&2
    exit 1
  fi

  if [[ ! -f "$CATS_SYMBOLS_CONFIG" ]]; then
    echo "missing symbols config: $CATS_SYMBOLS_CONFIG" >&2
    exit 1
  fi

  if [[ -z "${NOFX_API_KEY:-}" || "${NOFX_API_KEY:-}" == "replace_me" ]]; then
    echo "NOFX_API_KEY is required before starting paper runtime" >&2
    exit 1
  fi
}

is_running() {
  if [[ ! -f "$PID_FILE" ]]; then
    return 1
  fi

  local pid
  pid="$(cat "$PID_FILE")"
  if [[ -z "$pid" ]]; then
    return 1
  fi

  if kill -0 "$pid" >/dev/null 2>&1; then
    return 0
  fi

  rm -f "$PID_FILE"
  return 1
}

start() {
  load_env
  export RUNTIME_APP_CONFIG
  prepare_runtime_app_config
  validate_startup

  mkdir -p "$RUN_DIR" "$LOG_DIR"

  if is_running; then
    echo "paper runtime is already running (pid $(cat "$PID_FILE"))"
    exit 0
  fi

  (
    cd "$ROOT_DIR"
    nohup "$PYTHON_BIN" -m cats_py.apps.run_decision_engine >>"$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
  )

  sleep 1

  if is_running; then
    echo "paper runtime started"
    echo "pid: $(cat "$PID_FILE")"
    echo "log: $LOG_FILE"
    return 0
  fi

  echo "paper runtime failed to start, check log: $LOG_FILE" >&2
  exit 1
}

stop() {
  if ! is_running; then
    echo "paper runtime is not running"
    exit 0
  fi

  local pid
  pid="$(cat "$PID_FILE")"
  kill "$pid" >/dev/null 2>&1 || true

  for _ in $(seq 1 10); do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      rm -f "$PID_FILE"
      echo "paper runtime stopped"
      return 0
    fi
    sleep 1
  done

  kill -9 "$pid" >/dev/null 2>&1 || true
  rm -f "$PID_FILE"
  echo "paper runtime force stopped"
}

status() {
  load_env
  export RUNTIME_APP_CONFIG
  if [[ -f "$CATS_APP_CONFIG_TEMPLATE" ]]; then
    prepare_runtime_app_config
  fi

  echo "root: $ROOT_DIR"
  echo "python: $PYTHON_BIN"
  echo "mode: paper"
  echo "app_config_template: ${CATS_APP_CONFIG_TEMPLATE:-$ROOT_DIR/configs/app.example.yaml}"
  echo "app_config: ${CATS_APP_CONFIG:-$RUNTIME_APP_CONFIG}"
  echo "risk_config: ${CATS_RISK_CONFIG:-$ROOT_DIR/configs/risk.example.yaml}"
  echo "symbols_config: ${CATS_SYMBOLS_CONFIG:-$ROOT_DIR/configs/symbols.example.yaml}"
  echo "log: $LOG_FILE"

  if is_running; then
    echo "status: running"
    echo "pid: $(cat "$PID_FILE")"
  else
    echo "status: stopped"
  fi
}

usage() {
  cat <<'EOF'
Usage:
  scripts/paper_runtime.sh start
  scripts/paper_runtime.sh stop
  scripts/paper_runtime.sh status

Optional environment variables:
  PYTHON_BIN
  ENV_FILE
  NOFX_API_KEY
  PYTHONPATH
  CATS_APP_CONFIG_TEMPLATE
  CATS_RISK_CONFIG
  CATS_SYMBOLS_CONFIG
EOF
}

main() {
  local command="${1:-}"
  case "$command" in
    start)
      start
      ;;
    stop)
      stop
      ;;
    status)
      status
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "${1:-}"
