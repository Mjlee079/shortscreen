"""Test suite for the casino bonus scraper.

Covers data models, schema validation, robots.txt handling, LLM parsing,
HTML extraction, and the full scrape pipeline. External dependencies
(requests, openai) are mocked so no real network calls are made.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from models import CasinoBonus, ScrapeResult, utc_now_iso
from schema import CASINOS_SCHEMA, validate_casinos_data
import scraper


# ---------------------------------------------------------------------------
# utc_now_iso
# ---------------------------------------------------------------------------

def test_utc_now_iso_returns_iso_string() -> None:
    """utc_now_iso should return a valid ISO 8601 UTC string."""
    result = utc_now_iso()
    parsed = datetime.fromisoformat(result)
    assert parsed.tzinfo is not None
    assert parsed.tzinfo.utcoffset(parsed) is not None


# ---------------------------------------------------------------------------
# CasinoBonus dataclass
# ---------------------------------------------------------------------------

def test_casinobonus_to_dict() -> None:
    """CasinoBonus.to_dict should serialize all fields correctly."""
    bonus = CasinoBonus(
        name="Test Casino",
        welcome_bonus="100% up to 500 EUR",
        wagering_requirement=35,
        minimum_deposit="20 EUR",
        source_url="https://example.com/casino",
        scraped_at="2026-10-15T00:00:00+00:00",
    )
    data = bonus.to_dict()
    assert data == {
        "name": "Test Casino",
        "welcome_bonus": "100% up to 500 EUR",
        "wagering_requirement": 35,
        "minimum_deposit": "20 EUR",
        "source_url": "https://example.com/casino",
        "scraped_at": "2026-10-15T00:00:00+00:00",
    }


def test_casinobonus_null_fields() -> None:
    """CasinoBonus should allow None for optional parsed fields."""
    bonus = CasinoBonus(
        name="Test Casino",
        welcome_bonus=None,
        wagering_requirement=None,
        minimum_deposit=None,
        source_url="https://example.com/casino",
        scraped_at="2026-10-15T00:00:00+00:00",
    )
    assert bonus.welcome_bonus is None
    assert bonus.wagering_requirement is None
    assert bonus.minimum_deposit is None


# ---------------------------------------------------------------------------
# ScrapeResult dataclass
# ---------------------------------------------------------------------------

def test_scraperesult_to_dict() -> None:
    """ScrapeResult.to_dict should match the expected JSON schema shape."""
    result = ScrapeResult(
        casinos=[
            CasinoBonus(
                name="Casino A",
                welcome_bonus="100% up to 500 EUR",
                wagering_requirement=35,
                minimum_deposit="20 EUR",
                source_url="https://example.com/a",
                scraped_at="2026-10-15T00:00:00+00:00",
            )
        ],
        source="https://example.com",
        count=1,
    )
    data = result.to_dict()
    assert data["count"] == 1
    assert data["source"] == "https://example.com"
    assert len(data["casinos"]) == 1
    assert data["casinos"][0]["name"] == "Casino A"


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def test_validate_valid_data_passes() -> None:
    """Valid casinos data should return an empty error list."""
    data: dict[str, Any] = {
        "casinos": [
            {
                "name": "Casino A",
                "welcome_bonus": "100% up to 500 EUR",
                "wagering_requirement": 35,
                "minimum_deposit": "20 EUR",
                "source_url": "https://example.com/a",
                "scraped_at": "2026-10-15T00:00:00+00:00",
            }
        ],
        "source": "https://example.com",
        "count": 1,
    }
    assert validate_casinos_data(data) == []


def test_validate_missing_top_level_field() -> None:
    """Missing a required top-level field should produce an error."""
    data: dict[str, Any] = {"casinos": [], "source": "https://example.com"}
    errors = validate_casinos_data(data)
    assert any("count" in e for e in errors)


def test_validate_wagering_not_integer() -> None:
    """wagering_requirement must be an integer or null."""
    data: dict[str, Any] = {
        "casinos": [
            {
                "name": "Casino A",
                "welcome_bonus": "100% up to 500 EUR",
                "wagering_requirement": "thirty-five",
                "minimum_deposit": "20 EUR",
                "source_url": "https://example.com/a",
                "scraped_at": "2026-10-15T00:00:00+00:00",
            }
        ],
        "source": "https://example.com",
        "count": 1,
    }
    errors = validate_casinos_data(data)
    assert any("wagering_requirement" in e for e in errors)


def test_validate_too_many_casinos() -> None:
    """More than 3 casinos should be rejected."""
    casinos = [
        {
            "name": f"Casino {i}",
            "welcome_bonus": "100% up to 500 EUR",
            "wagering_requirement": 35,
            "minimum_deposit": "20 EUR",
            "source_url": f"https://example.com/{i}",
            "scraped_at": "2026-10-15T00:00:00+00:00",
        }
        for i in range(5)
    ]
    data: dict[str, Any] = {"casinos": casinos, "source": "https://example.com", "count": 5}
    errors = validate_casinos_data(data)
    assert any("casinos" in e for e in errors)


def test_validate_null_wagering_is_ok() -> None:
    """wagering_requirement of null should be accepted."""
    data: dict[str, Any] = {
        "casinos": [
            {
                "name": "Casino A",
                "welcome_bonus": None,
                "wagering_requirement": None,
                "minimum_deposit": None,
                "source_url": "https://example.com/a",
                "scraped_at": "2026-10-15T00:00:00+00:00",
            }
        ],
        "source": "https://example.com",
        "count": 1,
    }
    assert validate_casinos_data(data) == []


# ---------------------------------------------------------------------------
# Robots.txt helpers
# ---------------------------------------------------------------------------

def test_is_allowed_none_rp_returns_true() -> None:
    """When no robots.txt parser is available, fetching is allowed."""
    assert scraper.is_allowed(None, "https://example.com/page") is True


def test_load_robots_txt_failure_returns_none() -> None:
    """load_robots_txt should return None on network failure."""
    with patch("scraper.requests.get", side_effect=Exception("network down")):
        result = scraper.load_robots_txt("https://example.com")
        assert result is None


# ---------------------------------------------------------------------------
# fetch_page
# ---------------------------------------------------------------------------

def test_fetch_page_disallowed_returns_none() -> None:
    """fetch_page should return None when robots.txt disallows."""
    mock_rp = MagicMock()
    mock_rp.can_fetch.return_value = False
    result = scraper.fetch_page("https://example.com/blocked", mock_rp)
    assert result is None


def test_fetch_page_success_returns_html() -> None:
    """fetch_page should return HTML text on success."""
    mock_rp = MagicMock()
    mock_rp.can_fetch.return_value = True
    mock_response = MagicMock()
    mock_response.text = "<html><body>Hello</body></html>"
    mock_response.raise_for_status.return_value = None
    with patch("scraper.requests.get", return_value=mock_response):
        result = scraper.fetch_page("https://example.com/page", mock_rp)
        assert result == "<html><body>Hello</body></html>"


def test_fetch_page_network_error_returns_none() -> None:
    """fetch_page should return None on network error."""
    mock_rp = MagicMock()
    mock_rp.can_fetch.return_value = True
    with patch("scraper.requests.get", side_effect=Exception("timeout")):
        result = scraper.fetch_page("https://example.com/page", mock_rp)
        assert result is None


# ---------------------------------------------------------------------------
# LLM parsing
# ---------------------------------------------------------------------------

def test_parse_bonus_with_llm_no_api_key_uses_regex() -> None:
    """Without OPENAI_API_KEY, the regex fallback should be used."""
    with patch.dict("os.environ", {}, clear=True):
        result = scraper.parse_bonus_with_llm(
            "Welcome bonus 100% up to 500 EUR. Wagering 35x. Min deposit 20 EUR."
        )
        assert result["welcome_bonus"] == "100% up to 500 EUR"
        assert result["wagering_requirement"] == 35
        assert result["minimum_deposit"] == "20 EUR"


def test_parse_bonus_with_llm_success() -> None:
    """LLM parsing should return structured fields on success."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test123"}, clear=True):
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({
            "welcome_bonus": "100% up to 500 EUR",
            "wagering_requirement": 35,
            "minimum_deposit": "20 EUR",
        })
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        with patch("openai.OpenAI", return_value=mock_client):
            result = scraper.parse_bonus_with_llm(
                "Welcome bonus 100% up to 500 EUR. Wagering 35x."
            )
            assert result["welcome_bonus"] == "100% up to 500 EUR"
            assert result["wagering_requirement"] == 35
            assert result["minimum_deposit"] == "20 EUR"


def test_parse_bonus_with_llm_error_falls_back_to_regex() -> None:
    """LLM errors should fall back to regex parsing."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test123"}, clear=True):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API down")
        with patch("openai.OpenAI", return_value=mock_client):
            result = scraper.parse_bonus_with_llm(
                "Welcome bonus 100% up to 500 EUR. Wagering 35x. Min deposit 20 EUR."
            )
            assert result["welcome_bonus"] == "100% up to 500 EUR"
            assert result["wagering_requirement"] == 35


# ---------------------------------------------------------------------------
# Regex fallback parser
# ---------------------------------------------------------------------------

def test_regex_parser_bonus_percentage() -> None:
    """Regex parser should extract the welcome bonus percentage."""
    result = scraper._parse_bonus_regex("100% up to 500 EUR bonus")
    assert result["welcome_bonus"] == "100% up to 500 EUR"


def test_regex_parser_wagering() -> None:
    """Regex parser should extract the wagering multiplier."""
    result = scraper._parse_bonus_regex("Wagering requirement: 40x")
    assert result["wagering_requirement"] == 40


def test_regex_parser_min_deposit() -> None:
    """Regex parser should extract the minimum deposit."""
    result = scraper._parse_bonus_regex("Min deposit 20 EUR")
    assert result["minimum_deposit"] == "20 EUR"


def test_regex_parser_empty_text() -> None:
    """Regex parser should return all nulls for empty text."""
    result = scraper._parse_bonus_regex("")
    assert result["welcome_bonus"] is None
    assert result["wagering_requirement"] is None
    assert result["minimum_deposit"] is None


# ---------------------------------------------------------------------------
# HTML extraction helpers
# ---------------------------------------------------------------------------

def test_extract_text_first_match() -> None:
    """_extract_text should return text from the first matching selector."""
    html = '<div><h2>Casino Royale</h2><h3>Royale Casino</h3></div>'
    soup = BeautifulSoup(html, "html.parser")
    result = scraper._extract_text(soup, ["h3", "h2"])
    assert result == "Royale Casino"  # h3 is tried first


def test_extract_text_no_match_returns_none() -> None:
    """_extract_text should return None when no selector matches."""
    html = '<div><p>No header here</p></div>'
    soup = BeautifulSoup(html, "html.parser")
    result = scraper._extract_text(soup, ["h1", "h2", ".title"])
    assert result is None


def test_find_casino_elements_article_offer() -> None:
    """find_casino_elements should match article.offer elements."""
    html = """
    <html><body>
        <article class="offer"><h2>Casino A</h2></article>
        <article class="offer"><h2>Casino B</h2></article>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    elements = scraper.find_casino_elements(soup)
    assert len(elements) == 2


def test_find_casino_elements_heuristic_fallback() -> None:
    """find_casino_elements should fall back to text-based heuristic."""
    html = '<div>Welcome bonus 100% up to 500 EUR</div>'
    soup = BeautifulSoup(html, "html.parser")
    elements = scraper.find_casino_elements(soup)
    assert len(elements) >= 1


# ---------------------------------------------------------------------------
# extract_casino_data
# ---------------------------------------------------------------------------

def test_extract_casino_data_full() -> None:
    """extract_casino_data should populate all fields from HTML."""
    html = """
    <div class="offer">
        <h2>Lucky Casino</h2>
        <div class="bonus">100% up to 500 EUR. Wagering 35x. Min deposit 20 EUR.</div>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    element = soup.select_one("div.offer")
    with patch.dict("os.environ", {}, clear=True):
        result = scraper.extract_casino_data(element, "https://example.com")
        assert result.name == "Lucky Casino"
        assert result.source_url == "https://example.com"
        assert result.welcome_bonus is not None
        assert result.scraped_at is not None


# ---------------------------------------------------------------------------
# write_output
# ---------------------------------------------------------------------------

def test_write_output_creates_file(tmp_path: Path) -> None:
    """write_output should write valid JSON to the given path."""
    result = ScrapeResult(
        casinos=[
            CasinoBonus(
                name="Casino A",
                welcome_bonus="100% up to 500 EUR",
                wagering_requirement=35,
                minimum_deposit="20 EUR",
                source_url="https://example.com/a",
                scraped_at="2026-10-15T00:00:00+00:00",
            )
        ],
        source="https://example.com",
        count=1,
    )
    out_file = tmp_path / "casinos.json"
    scraper.write_output(result, out_file)
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["count"] == 1
    assert data["source"] == "https://example.com"


def test_write_output_invalid_data_raises(tmp_path: Path) -> None:
    """write_output should raise ValueError for schema-invalid data."""
    result = ScrapeResult(
        casinos=[
            CasinoBonus(
                name="Casino A",
                welcome_bonus="100% up to 500 EUR",
                wagering_requirement="not-an-int",
                minimum_deposit="20 EUR",
                source_url="https://example.com/a",
                scraped_at="2026-10-15T00:00:00+00:00",
            )
        ],
        source="https://example.com",
        count=1,
    )
    out_file = tmp_path / "casinos.json"
    with pytest.raises(ValueError, match="Schema validation failed"):
        scraper.write_output(result, out_file)


# ---------------------------------------------------------------------------
# scrape (orchestration)
# ---------------------------------------------------------------------------

def test_scrape_robots_blocked_returns_none() -> None:
    """scrape should return None when robots.txt disallows fetching."""
    mock_rp = MagicMock()
    mock_rp.can_fetch.return_value = False
    with patch("scraper.load_robots_txt", return_value=mock_rp):
        result = scraper.scrape("https://example.com/bonuses")
        assert result is None


def test_scrape_fetch_failure_returns_none() -> None:
    """scrape should return None when page fetch fails."""
    mock_rp = MagicMock()
    mock_rp.can_fetch.return_value = True
    with patch("scraper.load_robots_txt", return_value=mock_rp), patch(
        "scraper.fetch_page", return_value=None
    ):
        result = scraper.scrape("https://example.com/bonuses")
        assert result is None


def test_scrape_success_returns_result() -> None:
    """scrape should return a ScrapeResult on success."""
    mock_rp = MagicMock()
    mock_rp.can_fetch.return_value = True
    html = """
    <html><body>
        <article class="offer"><h2>Casino A</h2><div class="bonus">100% up to 500 EUR. Wagering 35x. Min deposit 20 EUR.</div></article>
    </body></html>
    """
    with patch("scraper.load_robots_txt", return_value=mock_rp), patch(
        "scraper.fetch_page", return_value=html
    ), patch.dict("os.environ", {}, clear=True):
        result = scraper.scrape("https://example.com/bonuses")
        assert result is not None
        assert result.count >= 1
        assert result.source == "https://example.com/bonuses"