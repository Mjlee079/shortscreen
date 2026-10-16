# Casino Bonus Scraper

## Project Overview
A Python scraper that pulls casino bonus data from public sources and a web page that displays the data in a table.

## Features

### Scraper Script (`src/scraper.py`)
- Pulls bonus data for 3 casinos from a public source
- Uses OpenAI LLM to turn free-text bonus terms into structured fields
- Extracts 4 fields per casino:
  1. Welcome bonus (e.g., "100% up to 500 EUR")
  2. Wagering requirement (e.g., 35)
  3. Minimum deposit (e.g., 20 EUR)
  4. Source URL (link to the page it was pulled from)
- Respects robots.txt
- Runs with a single command: `python src/scraper.py`
- Falls back to regex parsing if no LLM API key is available

### Web Page (`public/casino-bonuses/index.html`)
- Displays the 3 casinos in a responsive table
- Readable on mobile phones
- Automatically fetches data from `casinos.json`
- Uses simple HTML/JS (no build step required)

### Production Planning Documents
- `specs/requirements.md` - Full requirements specification
- `specs/architecture.md` - System architecture design
- `specs/secure-coding.md` - Secure coding guidelines
- `specs/testing-strategy.md` - Testing strategy

## Requirements
- Python 3.8+
- `requests`, `beautifulsoup4`, `openai` packages
- LLM API key (optional - regex parsing fallback available):
  - OpenRouter (NVIDIA Nemotron): set `OPENROUTER_API_KEY`
  - OpenAI: set `OPENAI_API_KEY`

## Installation

1. Clone the repository
2. Install dependencies: `pip install requests beautifulsoup4 openai`
3. Set up LLM API key (optional):
   - OpenRouter (NVIDIA Nemotron): `$env:OPENROUTER_API_KEY="sk-or-..."` (PowerShell) or `export OPENROUTER_API_KEY="sk-or-..."` (bash)
   - OpenAI: `export OPENAI_API_KEY="sk-..."`
4. Run the scraper: `python src/scraper.py`
5. Open the web page: open `public/casino-bonuses/index.html` in a browser

## Running the Scraper
```bash
cd casino-scraper
python src/scraper.py
```

The output will be saved to `casinos.json`.

## Output Example
```json
[
  {
    "name": "Casino A",
    "welcome_bonus": "100% up to 500 EUR",
    "wagering_requirement": 35,
    "minimum_deposit": 20.0,
    "source_url": "https://example-casino.com/promotions"
  }
]
```

## Notes
- The scraper respects robots.txt and does not bypass logins, CAPTCHAs or blocks
- If no LLM API key is set, the script uses regex parsing as a fallback
- The web page can be hosted on any static hosting service (GitHub Pages, Netlify, Vercel)