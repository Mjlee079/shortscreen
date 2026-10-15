
# Casino Bonus Scraper - Architecture Design

## High-Level Architecture

`mermaid
graph TD
    subgraph Local Development
        A[Scraper Script (Python)] -->|Generates| B[casinos.json]
        C[React Web App] -->|Reads from| B
        D[Git Repository] -->|Hosts| A & C
    end

    subgraph Production
        E[Cloud Server/Function] -->|Daily Runs| B[Database]
        F[CDN] -->|Serves| G[Web App]
    end
`

## Component Design

### 1. Scraper Service (Python)
- **Framework**: Custom script using equests + BeautifulSoup
- **LLM Integration**: Uses OpenAI/API function to parse free-text bonus terms
- **Schedule**: Cron job or GitHub Actions daily trigger
- **Fallback**: Switches source if blocked (robots.txt respected)

### 2. Data Store
- **Format**: JSON file (for simplicity in screening task)
- **Production**: Would use lightweight database (SQLite or JSON file on server)

### 3. Web Frontend (React)
- **Framework**: React 19 with TypeScript
- **Data Loading**: Fetches JSON from local path or API endpoint
- **Display**: Table responsive for mobile
- **Hosting**: Static site on GitHub Pages/Netlify/Vercel

### 4. Deployment Pipeline
- **CI/CD**: GitHub Actions or similar
- **Build**: 
pm run build for React, python scraper.py for data
- **Deploy**: Automatic deployment to chosen hosting service

## Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Scraper | Python 3.11 | Rich ecosystem, LLM client libraries, simple web scraping |
| LLM | OpenAI API | Free-text to structured data extraction |
| Web | React 19 + Vite | Modern, fast, phone-readable out of the box |
| Styling | Tailwind CSS or minimal CSS | Quick to set up, responsive |
| Hosting | GitHub Pages | Free, integrated with Git |
| Scheduling | GitHub Actions | Free tier, cron scheduling |

## Key Design Decisions

1. **Single Source Priority**: Start with one comparison site; if blocked, switch to another
2. **LLM for Parsing**: The free-text bonus terms (e.g.,  100% up to 500 EUR with 35x wagering) are parsed using an LLM to extract the structured fields
3. **Static Delivery**: The web page is static HTML that reads from a JSON file committed to the repo (or fetched at build time)
4. **Daily Refresh**: GitHub Actions triggers the scraper daily, updates the JSON, and redeploys the site

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Source blocks the scraper | Maintain list of 2-3 alternative sources; switch on failure |
| LLM parsing errors | Add validation; fallback manual parsing if LLM fails |
| Daily run fails | Monitor GitHub Actions logs; alert on failure |
| JSON format changes | Add schema validation on load |

## Production Scaling (200 Casinos)

If scaling to 200 casinos daily:

- **Database**: Replace JSON with PostgreSQL for better queryability
- **Scheduler**: More robust scheduling (cron on dedicated server)
- **Monitoring**: Error budget, alert on scraper failures
- **Cache**: Redis for frequent read access
- **Cost**: ~-50/month for cloud server + database

