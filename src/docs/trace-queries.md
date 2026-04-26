# Trace Queries — 11 Queries for Observe Tracing

**Run these after starting TravelShaper, with the Observe Agent running on the host.**  
Each query uses the full JSON schema — `departure`, `destination`, and `preferences` fields included — exactly as the browser UI submits them. This exercises place validation, voice routing, and all four tools. The queries themselves are unchanged from previous tracing backends; only the destination differs — Traceloop now exports OTLP HTTP spans to the Observe Agent, which forwards them to Observe.

Run the whole set in one shot:
```bash
chmod +x run_traces.sh && ./run_traces.sh
```
Or paste individual queries below. All dates in `run_traces.sh` are computed dynamically relative to today, so the script never goes stale. The dates shown below are illustrative examples. Traces appear in your Observe workspace within seconds.

---

## Query 1 — Full trip, save money, food + photography
**Voice:** Bourdain / Billy Dee / Gladwell  
**Expected tools:** search_flights, search_hotels, get_cultural_guide, duckduckgo_search

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am planning a trip departing from San Francisco, CA (please identify the nearest major international airport). Destination: Tokyo, Japan. Departure: 2026-10-15. Return: 2026-10-25 (10 days). Budget preference: save money. Interests: food and dining, photography. Please provide a complete travel briefing with hyperlinks for every named place, restaurant, hotel, and attraction.",
    "departure": "San Francisco, CA",
    "destination": "Tokyo, Japan",
    "preferences": "I want to eat where the locals eat — not a restaurant with an English menu out front. I am happy to point at things and hope for the best."
  }'
```

---

## Query 2 — Full trip, full experience, arts + nightlife
**Voice:** Leach / Pharrell / Rushdie  
**Expected tools:** search_flights, search_hotels, get_cultural_guide, duckduckgo_search

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am planning a trip departing from New York City, NY (please identify the nearest major international airport). Destination: Barcelona, Spain. Departure: 2026-10-01. Return: 2026-10-10 (9 days). Budget preference: full experience. Interests: arts and culture, food and dining, nightlife and events. Please provide a complete travel briefing with hyperlinks for every named place, restaurant, hotel, and attraction.",
    "departure": "New York City, NY",
    "destination": "Barcelona, Spain",
    "preferences": "This is a 30th birthday trip. I want at least one dinner that I will still be talking about in ten years. Surprise me."
  }'
```

---

## Query 3 — Budget trip, minimal interests, misspelled destination (auto-correction test)
**Voice:** Bourdain / Billy Dee / Gladwell  
**Expected tools:** search_flights, search_hotels, get_cultural_guide  
**Validation test:** "Roam" should be corrected to "Rome, Italy"

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am planning a trip departing from Chicago, IL (please identify the nearest major international airport). Destination: Roam, Italy. Departure: 2026-11-05. Return: 2026-11-12 (1 week). Budget preference: save money. Please provide a complete travel briefing with hyperlinks for every named place, restaurant, hotel, and attraction.",
    "departure": "Chicago, IL",
    "destination": "Roam, Italy",
    "preferences": "I am a broke grad student. Every dollar counts. I will eat standing up if I have to."
  }'
```

---

## Query 4 — Cultural guide only, no origin or dates
**Voice:** Leach / Pharrell / Rushdie (default — no budget keyword)  
**Expected tools:** get_cultural_guide, duckduckgo_search

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am visiting Japan for the first time next month. What should I know about etiquette, language, what to wear, and what not to do?",
    "destination": "Japan",
    "preferences": "I have read that bowing is important but I have no idea when or how much. Also I have a sleeve tattoo — will that be a problem?"
  }'
```

---

## Query 5 — Interest-heavy, no transport, photography + food
**Voice:** Bourdain / Billy Dee / Gladwell  
**Expected tools:** duckduckgo_search, get_cultural_guide

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am already in Lisbon, Portugal. I do not need flights or hotels. I want to know the best photography spots — golden hour, street life, the stuff that does not show up on Instagram. Also where should I eat that is not a tourist trap?",
    "destination": "Lisbon, Portugal",
    "preferences": "I shoot film, not digital. I am looking for texture — peeling tiles, old men playing cards, laundry across alleys. That kind of thing."
  }'
```

---

## Query 6 — Flights only, single tool test
**Expected tools:** search_flights only

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am planning a trip departing from Los Angeles, CA (please identify the nearest major international airport). Destination: London, United Kingdom. Departure: 2026-12-15. Return: 2026-12-28. Budget preference: save money. Please focus only on flight options — I have accommodation sorted.",
    "departure": "Los Angeles, CA",
    "destination": "London, United Kingdom"
  }'
```

---

## Query 7 — Hotels only, single tool test, budget
**Expected tools:** search_hotels only

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am already booked on a flight to Bangkok, Thailand. I need budget hotel options only — check-in January 5 2027, check-out January 12 2027. Save money mode. No flights, no cultural guide, just hotels.",
    "destination": "Bangkok, Thailand",
    "preferences": "I would like a safe, clean, trip that focuses on learning about the religious history in the region"
  }'
```

---

## Query 8 — Nature + fitness focus, full experience
**Voice:** Leach / Pharrell / Rushdie  
**Expected tools:** search_flights, search_hotels, get_cultural_guide, duckduckgo_search

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am planning a trip departing from Miami, FL (please identify the nearest major international airport). Destination: Queenstown, New Zealand. Departure: 2026-12-26. Return: 2027-01-09 (2 weeks). Budget preference: full experience. Interests: nature and outdoors, fitness and sports. Please provide a complete travel briefing with hyperlinks for every named place.",
    "departure": "Miami, FL",
    "destination": "Queenstown, New Zealand",
    "preferences": "I want to jump off something tall, run up something steep, and kayak something cold. Southern hemisphere summer is the whole reason for the timing."
  }'
```

---

## Query 9 — Vague input, edge case, agent chooses destination
**Expected tools:** duckduckgo_search (agent should reason through the recommendation)

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I need a break. I want somewhere warm in February, not too far from the East Coast, cheap to get to, good food, and where I can actually switch off. I do not want to go to Cancun. Surprise me.",
    "preferences": "I have been staring at a laptop for six months. I want to feel like a human being again."
  }'
```

---

## Query 10 — Domestic US trip, full experience, music + food + nightlife
**Voice:** Leach / Pharrell / Rushdie  
**Expected tools:** search_flights, search_hotels, duckduckgo_search (no cultural guide — domestic)

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am planning a trip departing from Seattle, WA (please identify the nearest major international airport). Destination: Austin, Texas. Departure: 2027-03-12. Return: 2027-03-17 (SXSW week). Budget preference: full experience. Interests: nightlife and events, food and dining. Please provide a complete travel briefing with hyperlinks for every named place, venue, hotel, and restaurant.",
    "departure": "Seattle, WA",
    "destination": "Austin, Texas",
    "preferences": "I go to SXSW every year but I always end up at the same venues. I want someone to tell me what I have been missing. Specifically: where are the locals actually going that week?"
  }'
```

---

## Query 11 — Past dates, error handling test
**Expected behaviour:** Agent should reject or warn about past departure dates. This tests graceful handling of invalid date inputs.

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am planning a trip departing from Boston, MA (please identify the nearest major international airport). Destination: Paris, France. Departure: 2026-03-01. Return: 2026-03-08 (7 days). Budget preference: save money. Please provide flight and hotel options.",
    "departure": "Boston, MA",
    "destination": "Paris, France",
    "preferences": "This is a test with past dates — the system should handle this gracefully."
  }'
```

> **Note:** In `run_traces.sh`, the dates for Query 11 are computed as 30 days in the past relative to today, so they are always past dates regardless of when the script is run.

---

## Coverage matrix

| # | Flights | Hotels | Cultural | Web | Budget | Interests | Special test |
|---|---------|--------|----------|-----|--------|-----------|--------------|
| 1 | ✓ | ✓ | ✓ | ✓ | Save | Food, Photo | Full schema |
| 2 | ✓ | ✓ | ✓ | ✓ | Full | Arts, Food, Nightlife | Full schema |
| 3 | ✓ | ✓ | ✓ | | Save | | Auto-correction ("Roam" → Rome) |
| 4 | | | ✓ | ✓ | Full | | No origin/dates; tattoo edge case |
| 5 | | | ✓ | ✓ | Save | Photo, Food | Already in destination |
| 6 | ✓ | | | | Save | | Single tool — flights only |
| 7 | | ✓ | | | Save | | Single tool — hotels only |
| 8 | ✓ | ✓ | ✓ | ✓ | Full | Nature, Fitness | Long-haul southern hemisphere |
| 9 | | | | ✓ | | | Vague/open-ended — agent chooses |
| 10 | ✓ | ✓ | | ✓ | Full | Nightlife, Food | Domestic — no cultural guide |
| 11 | ✓ | ✓ | | | Save | | Past dates — error handling |

**Covers:** all 4 tools individually and in combination · both budget voices · place auto-correction · missing origin/dates · already-at-destination · vague open-ended · domestic vs. international · past-date error handling · 5 of 6 interest categories
