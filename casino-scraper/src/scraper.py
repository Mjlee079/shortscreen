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
# casinodaddy.com is first: fully server-rendered casino bonus cards.
SOURCE_CANDIDATES: list[str] = [
    "https://casinodaddy.com/casino-bonuses/",
    "https://www.gamblingsites.org/online-casinos/bonuses/",
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
# Bonus percentage: "100% up to 500 EUR" or "100% up to 500" (currency optional)
_BONUS_PCT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*%\s*(?:up\s*to|up to|max\s*of)?\s*([\d,]+(?:\.\d+)?)\s*([A-Z]{3})?",
    re.IGNORECASE,
)
# Wagering requirement: requires either a wagering word ("wagering 35", "turnover 40")
# or an "x" suffix ("35x", "40×"). Bare numbers are not matched.
_WAGERING_RE = re.compile(
    r"(?:wager(?:ing)?|turnover|playthrough)\s*(\d+)\s*[x×]?|(\d+)\s*[x×]",
    re.IGNORECASE,
)
# Minimum deposit: "min deposit 20 EUR", "minimum deposit: 20", "deposit 20 EUR"
_DEPOSIT_RE = re.compile(
    r"(?:min(?:imum)?\s*)?deposit\s*(?:of)?\s*[:]?\s*([\d,]+(?:\.\d+)?)\s*([A-Z]{3})?",
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
# LLM configuration
# ---------------------------------------------------------------------------

# OpenRouter provides OpenAI-compatible access to NVIDIA's free models
# (e.g., nemotron-4-340b-instruct, llama-3.1-nemotron-70b-instruct).
# Set OPENROUTER_API_KEY to use OpenRouter instead of OpenAI.
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
NVIDIA_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
OPENAI_MODEL = "gpt-4o-mini"

def parse_bonus_with_llm(bonus_text: str) -> dict[str, str | int | None]:
    """Use an LLM to convert free-text bonus terms into structured fields.

    Args:
        bonus_text: Raw free-text bonus description from the page.

    Returns:
        A dictionary with keys welcome_bonus, wagering_requirement,
        minimum_deposit. Values may be None if not determinable.
    """
    # Determine LLM backend from environment (read at call time so tests
    # can patch os.environ after module import).
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if openrouter_key:
        api_key = openrouter_key
        base_url = OPENROUTER_BASE_URL
        model = NVIDIA_MODEL
        backend_name = "OpenRouter (NVIDIA Nemotron)"
    elif openai_key:
        api_key = openai_key
        base_url = None
        model = OPENAI_MODEL
        backend_name = "OpenAI (gpt-4o-mini)"
    else:
        print("Warning: No LLM API key set (OPENROUTER_API_KEY or OPENAI_API_KEY). Using regex fallback.")
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

        if base_url is not None:
            client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            client = OpenAI(api_key=api_key)

        # OpenRouter requires additional headers for attribution.
        extra_headers: dict[str, str] | None = None
        if openrouter_key:
            extra_headers = {
                "HTTP-Referer": "https://github.com/casino-bonus-scraper",
                "X-Title": "Casino Bonus Scraper",
            }

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=500,
            extra_headers=extra_headers,
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
        print(f"LLM parsing error ({backend_name}): {exc}. Falling back to regex.")
        return _parse_bonus_regex(bonus_text)


def _parse_bonus_regex(bonus_text: str) -> dict[str, str | int | None]:
    """Regex-based fallback parser for bonus text.

    Args:
        bonus_text: Raw free-text bonus description.

    Returns:
        A dictionary with keys welcome_bonus, wagering_requirement,
        minimum_deposit. Values may be None.
    """
    # Replace replacement characters, strip currency symbols, normalize whitespace.
    cleaned = bonus_text.replace("\ufffd", " ")
    cleaned = re.sub(r"[€$£¥]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    welcome_bonus: str | None = None
    wagering_requirement: int | None = None
    minimum_deposit: str | None = None

    m = _BONUS_PCT_RE.search(cleaned)
    if m:
        currency = f" {m.group(3)}" if m.group(3) else ""
        welcome_bonus = f"{m.group(1)}% up to {m.group(2)}{currency}"
    else:
        # "Up to 300 + 170 FS" style (no percentage prefix).
        m_up_to = re.search(
            r"up\s*to\s*([\d,]+(?:\.\d+)?)(?:\s*\+\s*(\d+)\s*FS)?",
            cleaned,
            re.IGNORECASE,
        )
        if m_up_to:
            fs = f" + {m_up_to.group(2)} FS" if m_up_to.group(2) else ""
            welcome_bonus = f"Up to {m_up_to.group(1)}{fs}"

    m = _WAGERING_RE.search(cleaned)
    if m:
        wagering_str = m.group(1) or m.group(2)
        try:
            wagering_requirement = int(wagering_str)
        except (ValueError, TypeError):
            wagering_requirement = None

    m = _DEPOSIT_RE.search(cleaned)
    if m:
        currency = f" {m.group(2)}" if m.group(2) else ""
        minimum_deposit = f"{m.group(1)}{currency}"

    return {
        "welcome_bonus": welcome_bonus,
        "wagering_requirement": wagering_requirement,
        "minimum_deposit": minimum_deposit,
    }


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------

def _parse_casino_name_from_url(href: str | None) -> str:
    """Parse a human-readable casino name from a bonus detail URL.

    AskGamblers URLs look like:
    /casino-bonuses/latest/jackpotter-casino-bonus-50-free-spins-2026-02-24

    We extract the casino name portion (before the first bonus-related word).

    Args:
        href: The bonus detail page URL path.

    Returns:
        A title-cased casino name, or "Unknown Casino" if unparseable.
    """
    if not href:
        return "Unknown Casino"

    # Extract the last path segment
    segment = href.rstrip("/").split("/")[-1]

    # Bonus-related words that mark the end of the casino name
    stop_words = [
        "bonus", "free", "spins", "deposit", "welcome", "match", "reload",
        "cashback", "no", "percent", "up", "to", "eur", "usd", "gbp",
    ]

    parts = segment.split("-")
    name_parts: list[str] = []
    for part in parts:
        lower = part.lower()
        # Skip pure numbers and dates
        if lower.isdigit() or (len(lower) == 8 and lower.isdigit()):
            break
        if lower in stop_words:
            break
        name_parts.append(part)

    if not name_parts:
        return "Unknown Casino"

    return " ".join(p.capitalize() for p in name_parts)


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


def _extract_attribute(element: Any, selector: str, attribute: str) -> str | None:
    """Extract an attribute value from the first element matching a selector.

    Args:
        element: BeautifulSoup element to search within.
        selector: CSS selector string.
        attribute: HTML attribute name to extract.

    Returns:
        The attribute value, or None if not found.
    """
    found = element.select_one(selector)
    if found:
        return cast(str | None, found.get(attribute))
    return None


def extract_casino_data(element: Any, base_url: str) -> CasinoBonus:
    """Extract structured bonus data from a single casino HTML element.

    Args:
        element: BeautifulSoup element representing one casino offer.
        base_url: The base URL of the listing page (for resolving relative links).

    Returns:
        A populated CasinoBonus dataclass.
    """
    # Extract the bonus detail page URL: casinodaddy review link first
    # (a.fs-12... linking to /<casino>/), then askgamblers card header,
    # then any link containing "/visit/".
    detail_href = _extract_attribute(element, "a.ag-card-header", "href")
    if not detail_href:
        # casinodaddy: the "X Casino Review" link is preferred over the
        # affiliate "Play Now" (/visit/) link.
        for link in element.select("a"):
            href = link.get("href") or ""
            text = (link.get_text(strip=True) or "").lower()
            if href and "review" in text:
                detail_href = href
                break
        if not detail_href:
            for link in element.select("a"):
                href = link.get("href") or ""
                if href and "/visit/" in href:
                    detail_href = href
                    break

    # Extract casino name: try parsing from the bonus detail URL first,
    # then the review link text (strip trailing "review"), then headings.
    name = "Unknown Casino"
    if detail_href:
        name = _parse_casino_name_from_url(detail_href)
    if name == "Unknown Casino":
        for link in element.select("a"):
            text = link.get_text(strip=True)
            if text and text.lower().endswith(" review"):
                name = text[: -len(" Review")].strip()
                break
    if name == "Unknown Casino":
        heading_name = _extract_text(element, ["h3", "h2", ".casino-name", ".name", ".title"])
        if heading_name:
            name = heading_name

    # Extract bonus title text: casinodaddy bonus line (p.h5 tt-u) first,
    # then askgamblers-specific selector, then generic bonus selectors.
    bonus_text = _extract_text(
        element,
        ["p.h5.ta-c", "p.tt-u.h5", "div.mb-10.px-10 p.h5",
         "a.ag-card-body-title", ".ag-card-body-title",
         ".bonus", ".welcome-bonus", ".promo", ".offer",
         ".bonus-text", ".offer-text"],
    )

    # Build the full source URL from the detail link.
    source_url: str
    if detail_href:
        if detail_href.startswith("http"):
            source_url = detail_href
        elif detail_href.startswith("/"):
            from urllib.parse import urlparse

            parsed = urlparse(base_url)
            source_url = parsed.scheme + "://" + parsed.netloc + detail_href
        else:
            source_url = base_url.rstrip("/") + "/" + detail_href
    else:
        source_url = base_url

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

    # casinodaddy fallback: min deposit lives in a deferred "cc__back__item"
    # block ("Min deposit€10"). Fill it in if the LLM/regex could not.
    if not structured.get("minimum_deposit"):
        for item in element.select("div.cc__back__item"):
            text = item.get_text(" ", strip=True)
            if "min deposit" in text.lower():
                value = re.sub(r"(?i)min\s*deposit\s*", "", text).strip()
                # Repair mojibake: "\ufffd10" -> "EUR 10" style value.
                value = re.sub(r"[\ufffd€$£¥]+", " EUR ", value)
                value = re.sub(r"\s+", " ", value).strip()
                if value:
                    structured["minimum_deposit"] = value
                break

    # Wagering requirement is rarely on the listing card. If still unknown
    # and we have a review page, fetch it once and parse the wagering text.
    if structured.get("wagering_requirement") is None:
        review_rp = load_robots_txt(source_url)
        review_html = fetch_page(source_url, review_rp)
        if review_html:
            review_soup = BeautifulSoup(review_html, "html.parser")
            page_text = review_soup.get_text(" ", strip=True)
            page_text = page_text.replace("\ufffd", " ")
            wm = re.search(
                r"(?:wager(?:ing)?|playthrough|turnover)[^\d]{0,20}(\d{1,3})\s*[x×]?",
                page_text,
                re.IGNORECASE,
            )
            if wm:
                structured["wagering_requirement"] = int(wm.group(1))

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
        # casinodaddy.com casino bonus cards
        "div.cc",
        # askgamblers.com bonus cards
        "div.ag-card.bonus-card",
        # generic comparison-site cards
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

    # Determine LLM backend for display (read at call time).
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if openrouter_key:
        llm_backend = "OpenRouter (NVIDIA Nemotron)"
    elif openai_key:
        llm_backend = "OpenAI (gpt-4o-mini)"
    else:
        llm_backend = "None (regex fallback only)"
    print(f"LLM backend: {llm_backend}")
    print()

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