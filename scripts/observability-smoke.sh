#!/usr/bin/env bash
set -euo pipefail

wait_for_http() {
  local name="$1"
  local url="$2"

  for attempt in $(seq 1 60); do
    if curl --fail --silent "${url}" >/dev/null 2>&1; then
      echo "${name}: ready"
      return 0
    fi

    sleep 2
  done

  echo "${name}: not ready" >&2
  return 1
}

wait_for_prometheus_query() {
  local query="$1"
  local description="$2"

  for attempt in $(seq 1 60); do
    if curl \
      --fail \
      --silent \
      --get \
      --data-urlencode "query=${query}" \
      http://127.0.0.1:9090/api/v1/query \
      | python3 -c '
import json
import sys

data = json.load(sys.stdin)
results = data.get("data", {}).get("result", [])

valid = any(
    float(result["value"][1]) > 0
    for result in results
    if "value" in result
)

raise SystemExit(0 if valid else 1)
'; then
      echo "${description}: verified"
      return 0
    fi

    sleep 2
  done

  echo "${description}: verification failed" >&2
  return 1
}

wait_for_loki_log() {
  for attempt in $(seq 1 60); do
    if curl \
      --fail \
      --silent \
      --get \
      --data-urlencode 'query={service_name="demo-api"} |= "work completed"' \
      --data-urlencode 'limit=5' \
      http://127.0.0.1:3100/loki/api/v1/query_range \
      | python3 -c '
import json
import sys

data = json.load(sys.stdin)
results = data.get("data", {}).get("result", [])

found = any(
    stream.get("values")
    for stream in results
)

raise SystemExit(0 if found else 1)
'; then
      echo "Loki application logs: verified"
      return 0
    fi

    sleep 2
  done

  echo "Loki application logs: verification failed" >&2
  return 1
}

wait_for_tempo_trace() {
  for attempt in $(seq 1 60); do
    if curl \
      --fail \
      --silent \
      --get \
      --data-urlencode 'q={ resource.service.name = "demo-api" }' \
      --data-urlencode 'limit=5' \
      http://127.0.0.1:3200/api/search \
      | python3 -c '
import json
import sys

data = json.load(sys.stdin)
traces = data.get("traces", [])

raise SystemExit(0 if traces else 1)
'; then
      echo "Tempo application traces: verified"
      return 0
    fi

    sleep 2
  done

  echo "Tempo application traces: verification failed" >&2
  return 1
}

echo "Waiting for observability services..."

wait_for_http \
  "Demo API" \
  "http://127.0.0.1:8000/health"

wait_for_http \
  "Prometheus" \
  "http://127.0.0.1:9090/-/ready"

wait_for_http \
  "Loki" \
  "http://127.0.0.1:3100/ready"

wait_for_http \
  "Tempo" \
  "http://127.0.0.1:3200/ready"

wait_for_http \
  "Grafana" \
  "http://127.0.0.1:3000/api/health"

wait_for_http \
  "Alertmanager" \
  "http://127.0.0.1:9093/-/ready"

echo "Generating application telemetry..."

for request in $(seq 1 12); do
  curl \
    --fail \
    --silent \
    http://127.0.0.1:8000/work \
    >/dev/null
done

echo "Application telemetry generated."

wait_for_prometheus_query \
  'up{job="demo-api"}' \
  "Prometheus demo-api target"

wait_for_prometheus_query \
  'sum(http_requests_total{job="demo-api",handler="/work"})' \
  "Prometheus application metrics"

wait_for_loki_log

wait_for_tempo_trace

echo
echo "End-to-end observability smoke test passed."
