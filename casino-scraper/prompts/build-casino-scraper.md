# Prompt: Build Casino Bonus Scraper

## Role
You are a full-stack AI coding agent building a casino bonus scraper screening task. You write type-safe Python 3.11+ (@python-pro) and React 19 + TypeScript (@react-expert) code. You respect robots.txt, never bypass logins/CAPTCHAs/blocks, and use an LLM for at least one parsing step.

## Task
Build a casino bonus scraper that:
1. Pulls bonus data for exactly 3 online casinos from ONE public source (a casino promotions page or comparison site).
2. Extracts 4 fields per casino: welcome bonus, wagering requirement (multiplier), minimum deposit, source URL.
3. Uses an LLM to convert free-text bonus terms into the 4 structured fields.
4. Writes output to casinos.json.
5. Runs with a single command: `python src/scraper.py`
6. Respects robots.txt; if the source blocks you, switch to an alternative source.
7. Includes a React web page (table of the 3 casinos, generated from casinos.json, mobile-readable).
8. Deploys to a free static host (GitHub Pages / Netlify / Vercel).

## Constraints (hard requirements from @phase)
- Typing data by hand does NOT meet the requirement.
- Do not bypass logins, CAPTCHAs, or blocks. Check robots.txt first.
- Cap: 3 casinos, one source.
- Single command to run the scraper.
- Web page must be readable on a phone.
- Include a written part: production scaling to 200 casinos daily (where it runs, database, backups, domain/DNS/HTTPS, daily scheduling + failure alerting, rough monthly cost).

## Stack (from @casino-scraper/specs/architecture.md)
- Scraper: Python 3.11+, requests + BeautifulSoup, OpenAI API for LLM parsing.
- Frontend: React 19 + Vite + TypeScript, Tailwind CSS.
- Data: casinos.json.
- Hosting: GitHub Pages.
- Scheduling: GitHub Actions cron (daily).
- Python typing: mypy --strict, dataclasses, pytest >90% coverage.
- React: TypeScript strict mode, error boundaries, semantic HTML + ARIA, no array-index keys, effect cleanup.

## Chain-of-Thought (for the LLM parsing step)
Before calling the LLM, think through:
1. Which public source allows scraping per robots.txt?
2. What CSS selectors target each casino's bonus block?
3. What free-text needs LLM parsing (e.g., "100% up to 500 EUR with 35x wagering, min deposit 20 EUR")?
4. How to validate the LLM output against the 4-field schema?
5. What fallback if LLM parsing fails or source is blocked?

## Structured Output Schema (JSON)
casinos.json must match:
{
  "casinos": [
    {
      "name": string,
      "welcome_bonus": string,        // e.g. "100% up to 500 EUR"
      "wagering_requirement": number,  // e.g. 35
      "minimum_deposit": string,       // e.g. "20 EUR"
      "source_url": string,            // URL it was pulled from
      "scraped_at": string             // ISO 8601 timestamp
    }
  ],
  "source": string,
  "count": number
}

## Few-Shot Example (LLM parsing)
Input text: "Welcome bonus 100% up to 500 EUR. Wagering 35x. Min deposit 20 EUR."
Expected output:
{"welcome_bonus": "100% up to 500 EUR", "wagering_requirement": 35, "minimum_deposit": "20 EUR"}

## Validation / Test Criteria
- scraper.py runs with `python src/scraper.py` (single command).
- casinos.json contains exactly 3 casinos with all 4 fields.
- wagering_requirement is a number, not a string.
- React page renders a table from casinos.json and is mobile-responsive.
- TypeScript: `tsc --noEmit` passes with strict mode.
- Python: `mypy --strict` passes; pytest suite green with >90% coverage.
- robots.txt checked before scraping; no login/CAPTCHA bypass.
- API key from environment variable only (never hardcoded).

## Usage Instructions
- Model: GPT-4o-mini (or equivalent), temperature 0.2, JSON mode / function calling.
- Max tokens: ~1000 per LLM parse call.
- Run: `python src/scraper.py` then `cd frontend && npm run dev` (or build for GitHub Pages).
- Required env var: OPENAI_API_KEY

## Known Limitations / Edge Cases
- Bonus terms vary by site; LLM may misparse unusual phrasing → add regex fallback.
- Source may change HTML structure → update selectors.
- Rate limits on OpenAI API → add retry with backoff.
- Free hosting may have build-time limits → commit casinos.json to repo.
- If no LLM key is set, scraper falls back to regex-only parsing with null fields.

## Deliverables
1. src/scraper.py (Python, type-hinted, mypy --strict clean).
2. src/models.py (dataclasses for CasinoBonus, ScrapeResult).
3. src/schema.py (JSON schema validation).
4. casinos.json (generated output).
5. frontend/ (React 19 + Vite + TypeScript, table view).
6. README.md (install + run instructions).
7. WRITTEN.md (production scaling to 200 casinos daily).
8. .github/workflows/daily-scraper.yml (daily scheduler + GitHub Pages deploy).
9. 5 lines on AI usage (tool used, one place it was wrong, how caught).
10. Time spent log.