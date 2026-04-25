"""Hotel search tool — queries Google Hotels via SerpAPI."""

from typing import List, Optional

from langchain_core.tools import tool
from pydantic import BaseModel

from tools import serpapi_request


# ---------------------------------------------------------------------------
# Pydantic structured output models
# ---------------------------------------------------------------------------


class HotelProperty(BaseModel):
    """Structured representation of a single hotel property."""

    name: str
    hotel_class: Optional[str] = None
    overall_rating: Optional[float] = None
    reviews: Optional[int] = None
    price_display: Optional[str] = None
    amenities: List[str] = []
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None

    def to_string(self) -> str:
        """Produce the same formatted string as _format_property()."""
        top_amenities = ", ".join(self.amenities[:5]) if self.amenities else "not listed"

        parts = [f"- {self.name}"]
        if self.hotel_class:
            parts[0] += f" ({self.hotel_class})"
        parts.append(f"  {self.price_display or 'N/A'}/night")
        if self.overall_rating:
            parts.append(f"  Rating: {self.overall_rating}/5 ({self.reviews or 0} reviews)")
        parts.append(f"  Amenities: {top_amenities}")
        if self.check_in_time and self.check_out_time:
            parts.append(f"  Check-in: {self.check_in_time}, Check-out: {self.check_out_time}")

        return "\n".join(parts)


class HotelSearchResult(BaseModel):
    """Structured representation of a full hotel search response."""

    query: str
    check_in_date: str
    check_out_date: str
    sort_by: int
    properties: List[HotelProperty] = []

    def to_agent_string(self) -> str:
        """Produce the same output as the original search_hotels() string logic."""
        lines = [
            f"Hotel results: {self.query}",
            f"Dates: {self.check_in_date} to {self.check_out_date}",
            f"Sorted by: {'lowest price' if self.sort_by == 3 else 'highest rating'}",
            "",
        ]

        for prop in self.properties[:5]:
            lines.append(prop.to_string())
            lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_property(prop: dict) -> str:
    """Format a single hotel property into a readable string."""
    name = prop.get("name", "Unknown hotel")
    hotel_class = prop.get("hotel_class", "")
    rating = prop.get("overall_rating", 0)
    reviews = prop.get("reviews", 0)
    rate_info = prop.get("rate_per_night", {})
    price = rate_info.get("lowest", "N/A")

    amenities = prop.get("amenities", [])
    top_amenities = ", ".join(amenities[:5]) if amenities else "not listed"

    check_in = prop.get("check_in_time", "")
    check_out = prop.get("check_out_time", "")

    parts = [f"- {name}"]
    if hotel_class:
        parts[0] += f" ({hotel_class})"
    parts.append(f"  {price}/night")
    if rating:
        parts.append(f"  Rating: {rating}/5 ({reviews} reviews)")
    parts.append(f"  Amenities: {top_amenities}")
    if check_in and check_out:
        parts.append(f"  Check-in: {check_in}, Check-out: {check_out}")

    return "\n".join(parts)


def _parse_property(prop: dict) -> HotelProperty:
    """Parse a SerpAPI hotel property dict into a HotelProperty model."""
    rate_info = prop.get("rate_per_night", {})
    return HotelProperty(
        name=prop.get("name", "Unknown hotel"),
        hotel_class=prop.get("hotel_class") or None,
        overall_rating=prop.get("overall_rating") or None,
        reviews=prop.get("reviews") or None,
        price_display=rate_info.get("lowest") or None,
        amenities=prop.get("amenities", []),
        check_in_time=prop.get("check_in_time") or None,
        check_out_time=prop.get("check_out_time") or None,
    )


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


@tool
def search_hotels(
    query: str,
    check_in_date: str,
    check_out_date: str,
    adults: int = 2,
    sort_by: int = 13,
) -> str:
    """Search for hotels at a destination for specific dates.

    Use this tool when the user wants to find hotels or accommodation.
    query should be a destination like 'Tokyo hotels' or 'Barcelona hotels'.
    Dates must be in YYYY-MM-DD format.
    sort_by: 3 for lowest price, 13 for highest rating (default).
    For budget travelers, use sort_by=3. For full experience, use sort_by=13.
    Returns a summary of available hotels with prices, ratings, and amenities.
    """
    try:
        data = serpapi_request(
            {
                "engine": "google_hotels",
                "q": query,
                "check_in_date": check_in_date,
                "check_out_date": check_out_date,
                "adults": str(adults),
                "currency": "USD",
                "gl": "us",
                "hl": "en",
                "sort_by": str(sort_by),
            }
        )
    except Exception as e:
        from tools import _mark_span_error
        _mark_span_error(str(e))
        return f"Hotel search failed: {e}"

    properties = data.get("properties", [])

    if not properties:
        return f"No hotels found for '{query}' on {check_in_date} to {check_out_date}."

    result = HotelSearchResult(
        query=query,
        check_in_date=check_in_date,
        check_out_date=check_out_date,
        sort_by=sort_by,
        properties=[_parse_property(p) for p in properties[:5]],
    )

    return result.to_agent_string()
