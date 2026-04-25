#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# ── 1. Welcome banner ─────────────────────────────────────────────────────────
echo ""
echo "TravelShaper — Setup"
echo ""

# ── 2. Check prerequisites ────────────────────────────────────────────────────
missing=0

if ! command -v docker &>/dev/null; then
  echo "✗ docker not found"
  echo "  Install Docker: https://docs.docker.com/get-docker/"
  missing=1
fi

has_compose=0
if docker compose version &>/dev/null 2>&1; then
  has_compose=1
  compose_cmd="docker compose"
elif command -v docker-compose &>/dev/null; then
  has_compose=1
  compose_cmd="docker-compose"
fi

if [ "$has_compose" -eq 0 ]; then
  echo "✗ docker compose not found"
  echo "  Install Docker Compose: https://docs.docker.com/compose/install/"
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

echo "✓ Prerequisites found"

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
echo "  App:     http://localhost:8000"
echo "  Phoenix: http://localhost:6006"
echo ""
echo "  Run tests (no API keys needed):"
echo "    cd src && pip install poetry==1.8.2 && poetry install -E dev && pytest tests/ -v"
echo ""
echo "  Generate Phoenix traces:"
echo "    ./run_traces.sh"
echo ""
echo "  Run evaluations:"
echo "    python -m evaluations.run_evals"
echo ""
echo "  Stop everything:"
echo "    $compose_cmd down"
