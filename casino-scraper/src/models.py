"""Data models for the casino bonus scraper.

Defines dataclasses representing a parsed casino bonus and the overall
scrape result, plus JSON serialization helpers.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone


@dataclass
class CasinoBonus:
    """Structured representation of a single casino welcome bonus.

    Attributes:
        name: The casino name.
        welcome_bonus: The bonus percentage and amount (e.g. "100% up to 500 EUR").
        wagering_requirement: The wagering multiplier as an integer (e.g. 35).
        minimum_deposit: The minimum deposit required (e.g. "20 EUR").
        source_url: The URL the data was pulled from.
        scraped_at: ISO 8601 UTC timestamp when the record was scraped.
    """

    name: str
    welcome_bonus: str | None
    wagering_requirement: int | None
    minimum_deposit: str | None
    source_url: str
    scraped_at: str

    def to_dict(self) -> dict[str, str | int | None]:
        """Convert the dataclass to a plain dictionary."""
        return asdict(self)


@dataclass
class ScrapeResult:
    """Container for the full scrape result.

    Attributes:
        casinos: List of parsed CasinoBonus records.
        source: The source URL that was scraped.
        count: Number of casinos scraped.
    """

    casinos: list[CasinoBonus]
    source: str
    count: int

    def to_dict(self) -> dict[str, str | int | list[dict[str, str | int | None]]]:
        """Convert the scrape result to a plain dictionary for JSON output."""
        return {
            "casinos": [c.to_dict() for c in self.casinos],
            "source": self.source,
            "count": self.count,
        }


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()