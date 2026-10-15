"""Casino Bonus Scraper.

Pulls welcome bonus data for up to 3 online casinos from one public source,
uses an LLM to convert free-text bonus terms into structured fields, and
writes the result to casinos.json.

Respects robots.txt and never bypasses logins, CAPTCHAs, or blocks. If a
source blocks the scraper, it falls back to an alternative source.

Usage:
    python src/scraper.py

Environment variables:
    OPENAI_API_KEY: API key for the OpenAI LLM used to parse bonus text.
        If not set, the scraper falls back to regex-only parsing with null
        fields for any value the LLM would have extracted.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, cast

import requests
from bs4 import BeautifulSoup
from urllib.robotparser import RobotFileParser

from models import CasinoBonus, ScrapeResult, utc_now_iso
from schema import validate_casinos_data

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CASINOS_TO_SCRAPE = 3
REQUEST_TIMEOUT = 15
REQUEST_DELAY = 2  # seconds between requests (rate limiting)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Ordered list of candidate sources. The scraper tries each in turn until
# one succeeds. All are public comparison/promotion pages.
SOURCE_CANDIDATES: list[str] = [
    "https://www.casinobonus.com/bonuses",
    "https://www.bonusfinder.com/casino-bonuses",
    "https://www.askgamblers.com/casino-bonuses",
]

HEADERS: dict[str, str] = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Regex fallback patterns (used when LLM is unavailable or fails).
_BONUS_PCT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*%\s*(?:up\s*to|up to|max\s*of)?\s*([\d,]+(?:\.\d+)?)\s*([A-Z]{3})",
    re.IGNORECASE,
)
_WAGERING_RE = re.compile(
    r"(\d+)\s*[x×]\s*(?:wager|turnover|playthrough)?", re.IGNORECASE
)
_DEPOSIT_RE = re.compile(
    r"(?:min(?:imum)?\s*)?deposit\s*(?:of)?\s*([\d,]+(?:\.\d+)?)\s*([A-Z]{3})",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Robots.txt helpers
# ---------------------------------------------------------------------------

def load_robots_txt(base_url: str) -> RobotFileParser | None:
    """Fetch and parse the robots.txt file for a given base URL.

    Args:
        base_url: The root URL of the site (e.g. https://example.com/).

    Returns:
        A populated RobotFileParser, or None if it could not be fetched.
    """
    robots_url = base_url.rstrip("/") + "/robots.txt"
    try:
        resp = requests.get(robots_url, timeout=REQUEST_TIMEOUT, headers=HEADERS)
        resp.raise_for_status()
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.parse(resp.text.splitlines())
        return rp
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Warning: could not fetch robots.txt from {robots_url}: {exc}")
        return None


def is_allowed(rp: RobotFileParser | None, url: str) -> bool:
    """Check whether the given URL may be fetched per robots.txt.

    Args:
        rp: RobotFileParser instance, or None (treated as allowed).
        url: The URL to check.

    Returns:
        True if fetching is permitted, False otherwise.
    """
    if rp is None:
        return True
    return rp.can_fetch("*", url)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def fetch_page(url: str, rp: RobotFileParser | None) -> str | None:
    """Fetch a web page, respecting robots.txt.

    Args:
        url: The URL to fetch.
        rp: RobotFileParser for the site's robots.txt.

    Returns:
        The HTML text if successful and allowed, None otherwise.
    """
    if not is_allowed(rp, url):
        print(f"robots.txt disallows fetching: {url}")
        return None
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers=HEADERS)
        resp.raise_for_status()
        return resp.text
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Error fetching {url}: {exc}")
        return None


# ---------------------------------------------------------------------------
# LLM parsing
# ---------------------------------------------------------------------------

def parse_bonus_with_llm(bonus_text: str) -> dict[str, str | int | None]:
    """Use an LLM to convert free-text bonus terms into structured fields.

    Args:
        bonus_text: Raw free-text bonus description from the page.

    Returns:
        A dictionary with keys welcome_bonus, wagering_requirement,
        minimum_deposit. Values may be None if not determinable.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Warning: OPENAI_API_KEY not set. Using regex fallback.")
        return _parse_bonus_regex(bonus_text)

    prompt = f"""Extract the following fields from this casino welcome bonus text:
- welcome_bonus: The bonus percentage and amount (e.g., "100% up to 500 EUR")
- wagering_requirement: The wagering multiplier as a number (e.g., 35)
- minimum_deposit: The minimum deposit required (e.g., "20 EUR")

Bonus text: "{bonus_text}"

Return a JSON object with exactly these three fields. If any field cannot
be determined, set it to null. Be precise and only extract what is
explicitly stated."""

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=500,
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("Empty response from LLM")
        result = json.loads(content.strip())
        return {
            "welcome_bonus": result.get("welcome_bonus"),
            "wagering_requirement": (
                int(result["wagering_requirement"])
                if result.get("wagering_requirement") is not None
                else None
            ),
            "minimum_deposit": result.get("minimum_deposit"),
        }
    except Exception as exc:  # pylint: disable=broad-except
        print(f"LLM parsing error: {exc}. Falling back to regex.")
        return _parse_bonus_regex(bonus_text)


def _parse_bonus_regex(bonus_text: str) -> dict[str, str | int | None]:
    """Regex-based fallback parser for bonus text.

    Args:
        bonus_text: Raw free-text bonus description.

    Returns:
        A dictionary with keys welcome_bonus, wagering_requirement,
        minimum_deposit. Values may be None.
    """
    welcome_bonus: str | None = None
    wagering_requirement: int | None = None
    minimum_deposit: str | None = None

    m = _BONUS_PCT_RE.search(bonus_text)
    if m:
        welcome_bonus = f"{m.group(1)}% up to {m.group(2)} {m.group(3)}"

    m = _WAGERING_RE.search(bonus_text)
    if m:
        try:
            wagering_requirement = int(m.group(1))
        except ValueError:
            wagering_requirement = None

    m = _DEPOSIT_RE.search(bonus_text)
    if m:
        minimum_deposit = f"{m.group(1)} {m.group(2)}"

    return {
        "welcome_bonus": welcome_bonus,
        "wagering_requirement": wagering_requirement,
        "minimum_deposit": minimum_deposit,
    }


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------

def _extract_text(element: Any, selectors: list[str]) -> str | None:
    """Try a list of CSS selectors on an element and return the first match.

    Args:
        element: BeautifulSoup element to search within.
        selectors: List of CSS selector strings to try.

    Returns:
        Stripped text of the first matching element, or None.
    """
    for selector in selectors:
        found = element.select_one(selector)
        if found and found.get_text(strip=True):
            return cast(str, found.get_text(strip=True))
    return None


def extract_casino_data(element: Any, source_url: str) -> CasinoBonus:
    """Extract structured bonus data from a single casino HTML element.

    Args:
        element: BeautifulSoup element representing one casino offer.
        source_url: The URL the page was fetched from.

    Returns:
        A populated CasinoBonus dataclass.
    """
    name = _extract_text(element, ["h3", "h2", ".casino-name", ".name", ".title"]) or "Unknown Casino"

    bonus_text = _extract_text(
        element,
        [".bonus", ".welcome-bonus", ".promo", ".offer", ".bonus-text", ".offer-text"],
    )

    structured: dict[str, str | int | None] = {
        "welcome_bonus": None,
        "wagering_requirement": None,
        "minimum_deposit": None,
    }

    if bonus_text:
        structured = parse_bonus_with_llm(bonus_text)
    else:
        # Last resort: scan the element's full text for bonus-like content.
        full_text = element.get_text(strip=True) if element else ""
        if "%" in full_text and ("up to" in full_text.lower() or "maximum" in full_text.lower()):
            structured = parse_bonus_with_llm(full_text)

    return CasinoBonus(
        name=name,
        welcome_bonus=cast(str | None, structured.get("welcome_bonus")),
        wagering_requirement=cast(int | None, structured.get("wagering_requirement")),
        minimum_deposit=cast(str | None, structured.get("minimum_deposit")),
        source_url=source_url,
        scraped_at=utc_now_iso(),
    )


def find_casino_elements(soup: BeautifulSoup) -> list[Any]:
    """Find candidate casino offer elements in a BeautifulSoup document.

    Tries several common selectors in order, falling back to a text-based
    heuristic if none match.

    Args:
        soup: Parsed BeautifulSoup document.

    Returns:
        A list of BeautifulSoup elements, each representing a casino offer.
    """
    candidate_selectors: list[str] = [
        "article.offer",
        "div.offer-list__item",
        "div.bonus-offer",
        "div.casino-offer",
        "li.casino",
    ]

    for selector in candidate_selectors:
        elements = soup.select(selector)
        if elements:
            return elements

    # Heuristic fallback: divs containing bonus-like text.
    all_divs = soup.find_all("div")
    return [
        d
        for d in all_divs
        if d.get_text(strip=True)
        and ("%" in d.get_text(strip=True) or "bonus" in d.get_text(strip=True).lower())
    ]


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_output(result: ScrapeResult, output_path: Path) -> None:
    """Write the scrape result to a JSON file after schema validation.

    Args:
        result: The ScrapeResult to serialize.
        output_path: Path to the output JSON file.

    Raises:
        ValueError: If the data fails schema validation.
    """
    data = result.to_dict()
    errors = validate_casinos_data(data)
    if errors:
        error_msg = "; ".join(errors)
        raise ValueError(f"Schema validation failed: {error_msg}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Success! {result.count} casino(s) written to: {output_path}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def scrape(source_url: str) -> ScrapeResult | None:
    """Run the full scrape pipeline for a single source URL.

    Args:
        source_url: The URL of the casino bonuses page to scrape.

    Returns:
        A ScrapeResult if successful, None if the source could not be used.
    """
    print(f"Scraping from: {source_url}")

    rp = load_robots_txt(source_url)
    allowed = is_allowed(rp, source_url)
    print(f"robots.txt check: {'Allowed' if allowed else 'Blocked'}")

    if not allowed:
        print(f"Source blocked by robots.txt: {source_url}")
        return None

    html = fetch_page(source_url, rp)
    if html is None:
        print(f"Failed to fetch page: {source_url}")
        return None

    soup = BeautifulSoup(html, "html.parser")
    casino_elements = find_casino_elements(soup)
    print(f"Found {len(casino_elements)} potential casino offers")

    results: list[CasinoBonus] = []
    for idx, element in enumerate(casino_elements):
        if idx >= CASINOS_TO_SCRAPE:
            break
        print(f"Processing casino {idx + 1}...")
        data = extract_casino_data(element, source_url)
        results.append(data)
        if idx < min(len(casino_elements), CASINOS_TO_SCRAPE) - 1:
            print(f"Waiting {REQUEST_DELAY}s before next request...")
            time.sleep(REQUEST_DELAY)

    if not results:
        print("No casino data extracted.")
        return None

    return ScrapeResult(casinos=results, source=source_url, count=len(results))


def main() -> None:
    """Entry point: try each source candidate until one succeeds."""
    output_path = Path(__file__).resolve().parent.parent / "casinos.json"

    last_error: str | None = None
    for source_url in SOURCE_CANDIDATES:
        try:
            result = scrape(source_url)
            if result is not None:
                write_output(result, output_path)
                print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
                return
        except Exception as exc:  # pylint: disable=broad-except
            print(f"Error with source {source_url}: {exc}")
            last_error = str(exc)
            continue

    print("All sources failed.")
    if last_error:
        print(f"Last error: {last_error}")
    sys.exit(1)


if __name__ == "__main__":
    main()