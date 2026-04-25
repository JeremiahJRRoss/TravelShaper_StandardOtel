#!/bin/bash
# ============================================================
# TravelShaper — Phoenix trace generator
# Fires all 10 queries against the running server and generates
# traces viewable in Phoenix at http://localhost:6006
#
# Usage:
#   ./run_traces.sh              # default: http://localhost:8000
#   ./run_traces.sh http://...   # custom base URL
# ============================================================
set -e

BASE_URL="${1:-http://localhost:8000}"
SLEEP_BETWEEN=3

# ── dynamic date generation ──────────────────────────────────
# All dates are computed relative to today so queries never go stale.
Q1_DEP=$(date -d "+30 days" +%Y-%m-%d)
Q1_RET=$(date -d "+40 days" +%Y-%m-%d)
Q2_DEP=$(date -d "+45 days" +%Y-%m-%d)
Q2_RET=$(date -d "+54 days" +%Y-%m-%d)
Q3_DEP=$(date -d "+60 days" +%Y-%m-%d)
Q3_RET=$(date -d "+67 days" +%Y-%m-%d)
Q6_DEP=$(date -d "+90 days" +%Y-%m-%d)
Q6_RET=$(date -d "+103 days" +%Y-%m-%d)
Q7_CHECKIN=$(date -d "+120 days" +%Y-%m-%d)
Q7_CHECKOUT=$(date -d "+127 days" +%Y-%m-%d)
Q8_DEP=$(date -d "+150 days" +%Y-%m-%d)
Q8_RET=$(date -d "+164 days" +%Y-%m-%d)
Q10_DEP=$(date -d "+180 days" +%Y-%m-%d)
Q10_RET=$(date -d "+185 days" +%Y-%m-%d)
Q11_DEP=$(date -d "-30 days" +%Y-%m-%d)   # past — error handling test
Q11_RET=$(date -d "-23 days" +%Y-%m-%d)

echo ""
echo "  TravelShaper — Phoenix Trace Generator"
echo "  Target:  ${BASE_URL}"
echo "  Phoenix: http://localhost:6006"
echo "  Queries: 11"
echo "  Dates generated relative to: $(date +%Y-%m-%d)"
echo ""
echo "  Starting in 2 seconds..."
sleep 2
echo ""

# ── helper ───────────────────────────────────────────────────
fire() {
  local n="$1"
  local label="$2"
  local body="$3"
  echo "┌─ Query ${n} ─ ${label}"
  curl -s -X POST "${BASE_URL}/chat" \
    -H "Content-Type: application/json" \
    -d "${body}" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    text = d.get('response','') or str(d)
    preview = text[:120].replace('\n',' ')
    print('│  ✓ ' + preview + ('...' if len(text) > 120 else ''))
except:
    print('│  ✗ (parse error or server error)')
"
  echo "└─────────────────────────────────────────────────────"
  echo ""
  sleep "$SLEEP_BETWEEN"
}

# ============================================================
# Query 1 — Full trip, save money, food + photography
# Expected tools: search_flights, search_hotels, get_cultural_guide, duckduckgo_search
# ============================================================
fire 1 "SFO → Tokyo · Save money · Food + Photo" \
'{
  "message": "I am planning a trip departing from San Francisco, CA (please identify the nearest major international airport). Destination: Tokyo, Japan. Departure: '"${Q1_DEP}"'. Return: '"${Q1_RET}"' (10 days). Budget preference: save money. Interests: food and dining, photography. Please provide a complete travel briefing with hyperlinks for every named place, restaurant, hotel, and attraction.",
  "departure": "San Francisco, CA",
  "destination": "Tokyo, Japan",
  "preferences": "I want to eat where the locals eat — not a restaurant with an English menu out front. I am happy to point at things and hope for the best."
}'

# ============================================================
# Query 2 — Full trip, full experience, arts + nightlife
# Expected tools: search_flights, search_hotels, get_cultural_guide, duckduckgo_search
# ============================================================
fire 2 "NYC → Barcelona · Full experience · Arts + Nightlife" \
'{
  "message": "I am planning a trip departing from New York City, NY (please identify the nearest major international airport). Destination: Barcelona, Spain. Departure: '"${Q2_DEP}"'. Return: '"${Q2_RET}"' (9 days). Budget preference: full experience. Interests: arts and culture, food and dining, nightlife and events. Please provide a complete travel briefing with hyperlinks for every named place, restaurant, hotel, and attraction.",
  "departure": "New York City, NY",
  "destination": "Barcelona, Spain",
  "preferences": "This is a 30th birthday trip. I want at least one dinner that I will still be talking about in ten years. Surprise me."
}'

# ============================================================
# Query 3 — Budget trip, auto-correction test ("Roam" → Rome)
# Expected tools: search_flights, search_hotels, get_cultural_guide
# ============================================================
fire 3 "Chicago → Roam [sic] · Save money · Auto-correction test" \
'{
  "message": "I am planning a trip departing from Chicago, IL (please identify the nearest major international airport). Destination: Roam, Italy. Departure: '"${Q3_DEP}"'. Return: '"${Q3_RET}"' (1 week). Budget preference: save money. Please provide a complete travel briefing with hyperlinks for every named place, restaurant, hotel, and attraction.",
  "departure": "Chicago, IL",
  "destination": "Roam, Italy",
  "preferences": "I am a broke grad student. Every dollar counts. I will eat standing up if I have to."
}'

# ============================================================
# Query 4 — Cultural guide only, no origin or dates
# Expected tools: get_cultural_guide, duckduckgo_search
# ============================================================
fire 4 "Japan etiquette · No origin/dates · Tattoo edge case" \
'{
  "message": "I am visiting Japan for the first time next month. What should I know about etiquette, language, what to wear, and what not to do?",
  "destination": "Japan",
  "preferences": "I have read that bowing is important but I have no idea when or how much. Also I have a sleeve tattoo — will that be a problem?"
}'

# ============================================================
# Query 5 — Interest-heavy, already at destination
# Expected tools: duckduckgo_search, get_cultural_guide
# ============================================================
fire 5 "Lisbon · Already there · Photo + Food · No transport" \
'{
  "message": "I am already in Lisbon, Portugal. I do not need flights or hotels. I want to know the best photography spots — golden hour, street life, the stuff that does not show up on Instagram. Also where should I eat that is not a tourist trap?",
  "destination": "Lisbon, Portugal",
  "preferences": "I shoot film, not digital. I am looking for texture — peeling tiles, old men playing cards, laundry across alleys. That kind of thing."
}'

# ============================================================
# Query 6 — Flights only, single tool test
# Expected tools: search_flights only
# ============================================================
fire 6 "LAX → London · Flights only · Single tool" \
'{
  "message": "I am planning a trip departing from Los Angeles, CA (please identify the nearest major international airport). Destination: London, United Kingdom. Departure: '"${Q6_DEP}"'. Return: '"${Q6_RET}"'. Budget preference: save money. Please focus only on flight options — I have accommodation sorted.",
  "departure": "Los Angeles, CA",
  "destination": "London, United Kingdom"
}'

# ============================================================
# Query 7 — Hotels only, single tool test
# Expected tools: search_hotels only
# ============================================================
fire 7 "Bangkok · Hotels only · Single tool" \
'{
  "message": "I am already booked on a flight to Bangkok, Thailand. I need budget hotel options only — check-in '"${Q7_CHECKIN}"', check-out '"${Q7_CHECKOUT}"'. Save money mode. No flights, no cultural guide, just hotels.",
  "destination": "Bangkok, Thailand",
  "preferences": "I would like a safe, clean, trip that focuses on learning about the religious history in the region"
}'

# ============================================================
# Query 8 — Nature + fitness, full experience, long-haul
# Expected tools: search_flights, search_hotels, get_cultural_guide, duckduckgo_search
# ============================================================
fire 8 "Miami → Queenstown · Full experience · Nature + Fitness" \
'{
  "message": "I am planning a trip departing from Miami, FL (please identify the nearest major international airport). Destination: Queenstown, New Zealand. Departure: '"${Q8_DEP}"'. Return: '"${Q8_RET}"' (2 weeks). Budget preference: full experience. Interests: nature and outdoors, fitness and sports. Please provide a complete travel briefing with hyperlinks for every named place.",
  "departure": "Miami, FL",
  "destination": "Queenstown, New Zealand",
  "preferences": "I want to jump off something tall, run up something steep, and kayak something cold. Southern hemisphere summer is the whole reason for the timing."
}'

# ============================================================
# Query 9 — Vague / open-ended, agent chooses destination
# Expected tools: duckduckgo_search
# ============================================================
fire 9 "Somewhere warm · Vague input · Agent chooses" \
'{
  "message": "I need a break. I want somewhere warm in February, not too far from the East Coast, cheap to get to, good food, and where I can actually switch off. I do not want to go to Cancun. Surprise me.",
  "preferences": "I have been staring at a laptop for six months. I want to feel like a human being again."
}'

# ============================================================
# Query 10 — Domestic US, full experience, SXSW
# Expected tools: search_flights, search_hotels, duckduckgo_search (no cultural guide)
# ============================================================
fire 10 "Seattle → Austin · SXSW · Full experience · Domestic" \
'{
  "message": "I am planning a trip departing from Seattle, WA (please identify the nearest major international airport). Destination: Austin, Texas. Departure: '"${Q10_DEP}"'. Return: '"${Q10_RET}"' (SXSW week). Budget preference: full experience. Interests: nightlife and events, food and dining. Please provide a complete travel briefing with hyperlinks for every named place, venue, hotel, and restaurant.",
  "departure": "Seattle, WA",
  "destination": "Austin, Texas",
  "preferences": "I go to SXSW every year but I always end up at the same venues. I want someone to tell me what I have been missing. Specifically: where are the locals actually going that week?"
}'

# ============================================================
# Query 11 — Past dates · Error handling test
# Expected: agent should reject or warn about past departure dates
# ============================================================
fire 11 "Boston → Paris · PAST DATES · Error handling test" \
'{
  "message": "I am planning a trip departing from Boston, MA (please identify the nearest major international airport). Destination: Paris, France. Departure: '"${Q11_DEP}"'. Return: '"${Q11_RET}"' (7 days). Budget preference: save money. Please provide flight and hotel options.",
  "departure": "Boston, MA",
  "destination": "Paris, France",
  "preferences": "This is a test with past dates — the system should handle this gracefully."
}'

# ============================================================
echo ""
echo "  Exporting spans to CSV..."
python3 -m scripts.export_spans || echo "  (Span export skipped — Phoenix may not be reachable)"
echo ""
echo "  All 11 queries complete."
echo "  View traces → http://localhost:6006"
echo "  Run evals  → python3 -m evaluations.run_evals"
echo "  Sync feedback → python3 -m scripts.sync_feedback"
echo ""
