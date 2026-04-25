"""Flight search tool — queries Google Flights via SerpAPI."""

from typing import List, Optional

from langchain_core.tools import tool
from pydantic import BaseModel

from tools import serpapi_request


# ---------------------------------------------------------------------------
# Pydantic structured output models
# ---------------------------------------------------------------------------


class FlightOption(BaseModel):
    """Structured representation of a single flight option."""

    airline: str
    price_usd: Optional[float] = None
    duration_minutes: Optional[int] = None
    stops: int = 0
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    departure_airport_id: Optional[str] = None
    arrival_airport_id: Optional[str] = None
    carbon_kg: Optional[int] = None

    def to_string(self) -> str:
        """Produce the same formatted string as _format_flight_option()."""
        hours, minutes = divmod(self.duration_minutes or 0, 60)
        stop_label = "nonstop" if self.stops == 0 else f"{self.stops} stop(s)"

        price_display = self.price_usd if self.price_usd is not None else "N/A"
        parts = [
            f"- {self.airline}: ${price_display}",
            f"{hours}h{minutes:02d}m",
            stop_label,
        ]
        if self.departure_time and self.arrival_time:
            parts.append(f"departs {self.departure_time} → arrives {self.arrival_time}")
        if self.carbon_kg:
            parts.append(f"{self.carbon_kg}kg CO₂")

        return ", ".join(parts)


class FlightSearchResult(BaseModel):
    """Structured representation of a full flight search response."""

    departure_id: str
    arrival_id: str
    outbound_date: str
    return_date: str
    best_flights: List[FlightOption] = []
    other_flights: List[FlightOption] = []
    price_level: Optional[str] = None
    typical_price_range: Optional[List[float]] = None

    def to_agent_string(self) -> str:
        """Produce the same output as the original search_flights() string logic."""
        lines = [
            f"Flight results: {self.departure_id} → {self.arrival_id}",
            f"Dates: {self.outbound_date} to {self.return_date}",
            "",
        ]

        if self.best_flights:
            lines.append("Best flights:")
            for f in self.best_flights[:3]:
                lines.append(f.to_string())

        if self.other_flights:
            lines.append("\nOther options:")
            for f in self.other_flights[:3]:
                lines.append(f.to_string())

        if self.price_level and self.typical_price_range:
            lines.append(
                f"\nPrice insight: current prices are {self.price_level} "
                f"(typical range: ${self.typical_price_range[0]}–${self.typical_price_range[1]})"
            )

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_flight_option(flight: dict) -> str:
    """Format a single flight option into a readable string."""
    legs = flight.get("flights", [])
    if not legs:
        return "- Unknown flight"

    first_leg = legs[0]
    airline = first_leg.get("airline", "Unknown airline")
    price = flight.get("price", "N/A")
    total_duration = flight.get("total_duration", 0)
    hours, minutes = divmod(total_duration, 60)
    stops = len(legs) - 1
    stop_label = "nonstop" if stops == 0 else f"{stops} stop(s)"

    departure = first_leg.get("departure_airport", {})
    arrival = legs[-1].get("arrival_airport", {})
    dep_time = departure.get("time", "")
    arr_time = arrival.get("time", "")

    carbon = flight.get("carbon_emissions", {})
    carbon_kg = carbon.get("this_flight", 0) // 1000 if carbon else 0

    parts = [
        f"- {airline}: ${price}",
        f"{hours}h{minutes:02d}m",
        stop_label,
    ]
    if dep_time and arr_time:
        parts.append(f"departs {dep_time} → arrives {arr_time}")
    if carbon_kg:
        parts.append(f"{carbon_kg}kg CO₂")

    return ", ".join(parts)


def _parse_flight_option(flight: dict) -> FlightOption:
    """Parse a SerpAPI flight dict into a FlightOption model."""
    legs = flight.get("flights", [])
    if not legs:
        return FlightOption(airline="Unknown flight")

    first_leg = legs[0]
    carbon = flight.get("carbon_emissions", {})
    carbon_kg = carbon.get("this_flight", 0) // 1000 if carbon else 0

    return FlightOption(
        airline=first_leg.get("airline", "Unknown airline"),
        price_usd=flight.get("price"),
        duration_minutes=flight.get("total_duration", 0),
        stops=len(legs) - 1,
        departure_time=first_leg.get("departure_airport", {}).get("time", ""),
        arrival_time=legs[-1].get("arrival_airport", {}).get("time", ""),
        departure_airport_id=first_leg.get("departure_airport", {}).get("id", ""),
        arrival_airport_id=legs[-1].get("arrival_airport", {}).get("id", ""),
        carbon_kg=carbon_kg if carbon_kg else None,
    )


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


@tool
def search_flights(
    departure_id: str,
    arrival_id: str,
    outbound_date: str,
    return_date: str,
) -> str:
    """Search for flights between two airports on specific dates.

    Use this tool when the user wants to find flights for their trip.
    departure_id and arrival_id must be IATA airport codes (e.g. SFO, NRT, CDG, LHR, JFK).
    Dates must be in YYYY-MM-DD format.
    Returns a summary of the best available flights with prices, duration, and stops.
    """
    try:
        data = serpapi_request(
            {
                "engine": "google_flights",
                "departure_id": departure_id.upper(),
                "arrival_id": arrival_id.upper(),
                "outbound_date": outbound_date,
                "return_date": return_date,
                "currency": "USD",
                "hl": "en",
                "gl": "us",
                "type": "1",  # round trip
            }
        )
    except Exception as e:
        from tools import _mark_span_error
        _mark_span_error(str(e))
        return f"Flight search failed: {e}"

    best = data.get("best_flights", [])
    other = data.get("other_flights", [])
    all_flights = best + other

    if not all_flights:
        return (
            f"No flights found from {departure_id} to {arrival_id} "
            f"on {outbound_date} returning {return_date}."
        )

    # Price insights if available
    insights = data.get("price_insights", {})

    result = FlightSearchResult(
        departure_id=departure_id.upper(),
        arrival_id=arrival_id.upper(),
        outbound_date=outbound_date,
        return_date=return_date,
        best_flights=[_parse_flight_option(f) for f in best[:3]],
        other_flights=[_parse_flight_option(f) for f in other[:3]],
        price_level=insights.get("price_level", "") or None,
        typical_price_range=insights.get("typical_price_range") or None,
    )

    return result.to_agent_string()
