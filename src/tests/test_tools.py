"""Unit tests for TravelShaper tool modules.

All external network calls are mocked — no live API keys required.
Mock paths follow the rule: patch where the name is *used*, not where
it is *defined*.  Each tool imports serpapi_request via
``from tools import serpapi_request``, so mocks target:
- ``tools.flights.serpapi_request``
- ``tools.hotels.serpapi_request``
- ``tools.cultural_guide.serpapi_request``
"""

from unittest.mock import patch

import pytest

from tools.flights import search_flights
from tools.hotels import search_hotels
from tools.cultural_guide import get_cultural_guide


# ---------------------------------------------------------------------------
# Fixtures / shared mock data
# ---------------------------------------------------------------------------

FLIGHTS_MOCK_DATA = {
    "best_flights": [
        {
            "flights": [
                {
                    "airline": "ANA",
                    "departure_airport": {
                        "name": "San Francisco International",
                        "id": "SFO",
                        "time": "2026-10-15 11:30",
                    },
                    "arrival_airport": {
                        "name": "Narita International",
                        "id": "NRT",
                        "time": "2026-10-16 15:45",
                    },
                    "duration": 660,
                    "travel_class": "Economy",
                    "flight_number": "NH 7",
                }
            ],
            "total_duration": 660,
            "price": 687,
            "carbon_emissions": {
                "this_flight": 807000,
                "typical_for_this_route": 615000,
            },
        }
    ],
    "other_flights": [
        {
            "flights": [
                {
                    "airline": "United",
                    "departure_airport": {
                        "name": "San Francisco International",
                        "id": "SFO",
                        "time": "2026-10-15 14:00",
                    },
                    "arrival_airport": {
                        "name": "Narita International",
                        "id": "NRT",
                        "time": "2026-10-16 18:00",
                    },
                    "duration": 680,
                    "travel_class": "Economy",
                    "flight_number": "UA 837",
                }
            ],
            "total_duration": 680,
            "price": 845,
            "carbon_emissions": {"this_flight": 750000},
        }
    ],
    "price_insights": {
        "lowest_price": 650,
        "price_level": "typical",
        "typical_price_range": [600, 1200],
    },
}

HOTELS_MOCK_DATA = {
    "properties": [
        {
            "name": "Hotel Gracery Shinjuku",
            "hotel_class": "4-star hotel",
            "overall_rating": 4.3,
            "reviews": 2150,
            "rate_per_night": {"lowest": "$89", "extracted_lowest": 89},
            "amenities": ["Free Wi-Fi", "Restaurant", "Fitness center", "Laundry"],
            "check_in_time": "2:00 PM",
            "check_out_time": "11:00 AM",
        },
        {
            "name": "Khaosan Tokyo Kabuki",
            "hotel_class": "2-star hotel",
            "overall_rating": 3.8,
            "reviews": 890,
            "rate_per_night": {"lowest": "$35", "extracted_lowest": 35},
            "amenities": ["Free Wi-Fi", "Shared kitchen"],
            "check_in_time": "3:00 PM",
            "check_out_time": "10:00 AM",
        },
    ]
}

CULTURAL_GUIDE_MOCK_DATA = {
    "organic_results": [
        {
            "title": "Japan Etiquette Guide",
            "snippet": "Bowing is the standard greeting. Tipping is not customary.",
            "displayed_link": "www.japan-guide.com",
        },
        {
            "title": "Essential Japanese Phrases",
            "snippet": "Sumimasen means excuse me. Arigatou gozaimasu means thank you.",
            "displayed_link": "www.tofugu.com",
        },
    ]
}


# ---------------------------------------------------------------------------
# Test 1: search_flights formats results correctly
# ---------------------------------------------------------------------------

@patch("tools.flights.serpapi_request")
def test_search_flights_formats_results(mock_serpapi: object) -> None:
    """Verify the flights tool correctly formats a SerpAPI response."""
    mock_serpapi.return_value = FLIGHTS_MOCK_DATA

    result = search_flights.invoke(
        {
            "departure_id": "SFO",
            "arrival_id": "NRT",
            "outbound_date": "2026-10-15",
            "return_date": "2026-10-22",
        }
    )

    assert isinstance(result, str), "Result must be a string"
    assert result, "Result must not be empty"
    assert "ANA" in result
    assert "687" in result
    assert "United" in result
    assert "845" in result
    assert "SFO" in result
    assert "NRT" in result
    assert "Best flights" in result


# ---------------------------------------------------------------------------
# Test 2: search_flights handles empty results
# ---------------------------------------------------------------------------

@patch("tools.flights.serpapi_request")
def test_search_flights_handles_empty_results(mock_serpapi: object) -> None:
    """Verify the flights tool returns a helpful message when no flights found."""
    mock_serpapi.return_value = {"best_flights": [], "other_flights": []}

    result = search_flights.invoke(
        {
            "departure_id": "SFO",
            "arrival_id": "NRT",
            "outbound_date": "2026-10-15",
            "return_date": "2026-10-22",
        }
    )

    assert "No flights found" in result


# ---------------------------------------------------------------------------
# Test 3: search_hotels formats results correctly
# ---------------------------------------------------------------------------

@patch("tools.hotels.serpapi_request")
def test_search_hotels_formats_results(mock_serpapi: object) -> None:
    """Verify the hotels tool correctly formats a SerpAPI response."""
    mock_serpapi.return_value = HOTELS_MOCK_DATA

    result = search_hotels.invoke(
        {
            "query": "Tokyo hotels",
            "check_in_date": "2026-10-15",
            "check_out_date": "2026-10-22",
        }
    )

    assert isinstance(result, str), "Result must be a string"
    assert result, "Result must not be empty"
    assert "Hotel Gracery Shinjuku" in result
    assert "$89" in result
    assert "Khaosan Tokyo Kabuki" in result
    assert "$35" in result
    assert "4.3" in result


# ---------------------------------------------------------------------------
# Test 4: get_cultural_guide returns guidance compiled from search results
# ---------------------------------------------------------------------------

@patch("tools.cultural_guide.serpapi_request")
def test_cultural_guide_returns_guidance(mock_serpapi: object) -> None:
    """Verify the cultural guide tool compiles organic search results correctly."""
    mock_serpapi.return_value = CULTURAL_GUIDE_MOCK_DATA

    result = get_cultural_guide.invoke({"destination": "Tokyo, Japan"})

    assert "Bowing" in result or "bowing" in result
    assert "Sumimasen" in result or "sumimasen" in result
    assert "Japan Etiquette Guide" in result
