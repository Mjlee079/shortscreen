## Secure Coding Guidelines for Casino Bonus Scraper

- All input from web pages is untrusted
- LLM output is validated against schema
- API keys from environment variables, never hardcoded
- No SQL injection risk (JSON-based data flow)
- XSS prevention: React automatically escapes content
- Rate limiting between scraper requests
- Generic error messages to users (no detailed stack traces)
