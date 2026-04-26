#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# ── 1. Welcome banner ─────────────────────────────────────────────────────────
echo ""
echo "TravelShaper — Setup"
echo ""

# ── 2. Check prerequisites ────────────────────────────────────────────────────
missing=0

# Pick a container runtime. Prefer Docker; fall back to Podman.
runtime_cmd=""
if command -v docker &>/dev/null; then
  runtime_cmd="docker"
elif command -v podman &>/dev/null; then
  runtime_cmd="podman"
else
  echo "✗ no container runtime found"
  echo "  Install Docker: https://docs.docker.com/get-docker/"
  echo "  or Podman:      https://podman.io/docs/installation"
  missing=1
fi

# Pick a compose CLI for the chosen runtime. Try the v2 plugin first
# ("docker compose" / "podman compose"), then the standalone tool
# ("docker-compose" / "podman-compose").
has_compose=0
compose_cmd=""
if [ -n "$runtime_cmd" ]; then
  if $runtime_cmd compose version &>/dev/null 2>&1; then
    has_compose=1
    compose_cmd="$runtime_cmd compose"
  elif command -v "${runtime_cmd}-compose" &>/dev/null; then
    has_compose=1
    compose_cmd="${runtime_cmd}-compose"
  fi
fi

if [ "$has_compose" -eq 0 ] && [ "$missing" -eq 0 ]; then
  echo "✗ ${runtime_cmd} compose not found"
  if [ "$runtime_cmd" = "docker" ]; then
    echo "  Install Docker Compose: https://docs.docker.com/compose/install/"
  else
    echo "  Install podman-compose: pip install podman-compose"
    echo "  or upgrade Podman to 4.0+ for the built-in 'podman compose' plugin"
  fi
  missing=1
fi

if ! command -v python3 &>/dev/null; then
  echo "✗ python3 not found"
  echo "  Install Python 3.11+: https://python.org"
  missing=1
fi

if [ "$missing" -eq 1 ]; then
  echo ""
  echo "Please install the missing prerequisites and re-run this script."
  exit 1
fi

echo "✓ Prerequisites found (using ${runtime_cmd})"

# Pre-create the host-side logs dir so the ./logs:/app/logs bind mount
# has somewhere to land (rootless Podman does not auto-create it), and
# chown it to UID/GID 1000 so the non-root container user (created in
# the Dockerfile) can write travelshaper.log into it.
LOGS_DIR="$(pwd)/logs"
mkdir -p "$LOGS_DIR"
if ! chown 1000:1000 "$LOGS_DIR" 2>/dev/null; then
  echo "⚠ Could not chown ${LOGS_DIR} to uid 1000 (need root or rootless namespace)."
  echo "  If logs do not appear, run:  sudo chown 1000:1000 ${LOGS_DIR}"
  echo "  or, on rootless Podman:      podman unshare chown 1000:1000 ${LOGS_DIR}"
fi

# ── 3. Create .env file ───────────────────────────────────────────────────────
if [ -f .env ]; then
  echo "✓ .env already exists — skipping"
else
  cp .env.example .env

  echo ""
  echo "─── API Keys ───────────────────────────────────────────"
  echo ""
  echo "OpenAI API key (required)"
  echo "  Get one at: https://platform.openai.com/api-keys"
  read -p "  Enter key: " openai_key
  echo ""

  echo "SerpAPI key (optional — flights/hotels won't work without it, but the app will run)"
  echo "  Get one at: https://serpapi.com/manage-api-key (free tier: 250 searches/month)"
  read -p "  Enter key (or press Enter to skip): " serpapi_key
  echo ""

  if [ -n "$openai_key" ]; then
    sed -i "s|your_openai_key_here|${openai_key}|" .env
  else
    echo "⚠ No OpenAI key provided. The agent won't work, but tests will still pass."
  fi

  if [ -n "$serpapi_key" ]; then
    sed -i "s|your_serpapi_key_here|${serpapi_key}|" .env
  fi

  echo "✓ .env created"
fi

# ── 4. Build and start containers ─────────────────────────────────────────────
echo ""
echo "Building and starting containers..."
$compose_cmd build --no-cache
$compose_cmd up -d

# ── 5. Wait for health check ──────────────────────────────────────────────────
echo ""
echo "Waiting for the app to start..."
elapsed=0
while [ "$elapsed" -lt 60 ]; do
  if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null | grep -q "200"; then
    break
  fi
  printf "."
  sleep 2
  elapsed=$((elapsed + 2))
done
echo ""

if [ "$elapsed" -ge 60 ]; then
  echo "⚠ Health check timed out after 60 seconds. Containers may still be starting."
else
  echo "✓ App is healthy"
fi

# ── 6. Final summary ──────────────────────────────────────────────────────────
echo ""
echo "✓ TravelShaper is running"
echo ""
echo "  App: http://localhost:8000"
echo ""
echo "  Tracing: spans are exported via OTLP to TRACELOOP_BASE_URL"
echo "           (default: host's Observe Agent at port 4318). Logs are"
echo "           written to ./logs/travelshaper.log for the Observe Agent's"
echo "           filelog receiver."
echo ""
echo "  Run tests (no API keys needed):"
echo "    cd src && pip install poetry==1.8.2 && poetry install -E dev && pytest tests/ -v"
echo ""
echo "  Generate traces (lands in Observe via the Observe Agent):"
echo "    ./run_traces.sh"
echo ""
echo "  Stop everything:"
echo "    $compose_cmd down"
