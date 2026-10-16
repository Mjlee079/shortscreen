# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

Please report security vulnerabilities by opening an issue or contacting the repository owner. Do not disclose sensitive information (API keys, credentials) in public issues.

## Security Measures Implemented

### Scraper (Python)

- **API keys from environment variables only** — `OPENROUTER_API_KEY` or `OPENAI_API_KEY` are read via `os.environ.get()`; never hardcoded
- **SSL certificate verification enabled** — all `requests.get()` calls use default verification (no `verify=False`)
- **robots.txt compliance** — the scraper checks `robots.txt` before fetching any page and skips disallowed URLs
- **No logins, CAPTCHAs, or blocks bypassed** — if a source blocks the scraper, it falls back to an alternative source
- **Rate limiting** — 2-second delay between scraper requests to avoid overwhelming target servers
- **Input validation** — all scraped data is validated against a JSON schema before being written to `casinos.json`
- **No command injection** — no `shell=True`, `eval()`, `exec()`, or `pickle` usage
- **No SQL injection risk** — JSON-based data flow, no SQL queries

### Frontend (React 19 + TypeScript)

- **XSS prevention** — React automatically escapes rendered content; user-supplied data is never inserted as raw HTML
- **Type safety** — TypeScript strict mode catches type-related bugs at compile time
- **No dangerous innerHTML usage** — all content is rendered through JSX expressions

### Dependencies

- **npm audit** — The `frontend/` directory has dev-time vulnerabilities in `braces`, `esbuild`, and `postcss-selector-parser`. These are build-time-only dependencies (via tailwindcss/vite) and do not affect the production static site served on GitHub Pages.
- **Python dependencies** — `requests`, `beautifulsoup4`, `openai` are pinned in `pyproject.toml`

## Secure Configuration

1. Never commit `.env` files or API keys to the repository
2. Set `OPENROUTER_API_KEY` or `OPENAI_API_KEY` as environment variables before running the scraper
3. For GitHub Actions, store the API key as a repository secret (`Settings → Secrets and variables → Actions`)
4. Review `casinos.json` output before deploying to ensure no sensitive data was scraped
