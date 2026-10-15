# Casino Bonus Scraper

A screening-task project that scrapes welcome bonus data for 3 online casinos from a public source, parses free-text bonus terms with an LLM (NVIDIA Nemotron via OpenRouter) into structured fields, and displays the results on a single mobile-responsive web page.

Built with **Python 3.11+** (scraper) and **React 19 + TypeScript + Vite** (frontend).

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/Mjlee079/shortscreen.git
cd shortscreen
```

### 2. Python scraper

Install dependencies:

```bash
pip install requests beautifulsoup4 openai pytest pytest-mypy
```

Set your OpenRouter API key (for NVIDIA Nemotron LLM parsing):

```powershell
# PowerShell
$env:OPENROUTER_API_KEY="sk-or-v1-..."

# bash/zsh
export OPENROUTER_API_KEY="sk-or-v1-..."
```

Run the scraper (single command):

```bash
cd casino-scraper
python src/scraper.py
```

This writes `casinos.json` at the project root.

### 3. Type checking (mypy strict)

```bash
pip install mypy
mypy --strict src/
```

Expected: `Success: no issues found in 3 source files`

### 4. Run tests

```bash
pytest tests/ -v
```

Target: >90% coverage, all 31 tests passing.

### 5. React frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 to view the casino bonus table.

Build for production:

```bash
npm run build
```

## Deployment Options

### Option 1: Netlify (Simple, with daily auto-update)

1. Go to **https://app.netlify.com/start** → **Add new site** → **Import an existing project** → **GitHub** → select `Mjlee079/shortscreen`
2. **Build settings:**
   - Base directory: `casino-scraper/frontend`
   - Build command: `npm ci && npm run build`
   - Publish directory: `dist`
3. Go to **Site settings** → **Environment variables** → **Add variable**:
   - Key: `OPENROUTER_API_KEY`
   - Value: `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`
4. Click **Deploy site**. Your site will be live at a URL like: `https://random-name.netlify.app`

**Daily auto-update (optional):**
- Go to **Site settings** → **Functions** → **Enable Functions**
- Go to **Trigger functions** → **Schedule functions**
- Add the schedule file `casino-scraper/frontend/netlify/functions/scrape.schedule.json` with content:
  ```json
  {
    "schedule": "@daily",
    "name": "Daily Casino Scrape"
  }
  ```
- The scraper will run every day at midnight UTC, updating `casinos.json` and triggering a redeploy.

Live site example: **https://casino-bonus-scraper.netlify.app**

### Option 2: Vercel

1. Go to **https://vercel.com/new** → **Import repository** → select `Mjlee079/shortscreen`
2. **Framework Preset**: Vite
3. **Root Directory**: `casino-scraper/frontend`
4. **Build Command**: `npm ci && npm run build`
5. **Output Directory**: `dist`

The `vercel.json` at root handles redirects and framework detection.

Live site examples:
- Netlify: `https://random-name.netlify.app`
- Vercel: `https://shortscreen.vercel.app`

### Option 3: GitHub Pages (Free, Auto-Deploy via GitHub Actions)

The project includes a GitHub Actions workflow that:
- Runs the Python scraper daily (via cron) or on manual trigger
- Builds the React frontend with Vite
- Deploys to GitHub Pages

**Setup:**
1. Go to **https://github.com/Mjlee079/shortscreen/settings/pages**
2. Under **Build and deployment** → **Source**, select **GitHub Actions**
3. Go to **https://github.com/Mjlee079/shortscreen/settings/secrets/actions**
4. Click **New repository secret**
5. Name: `OPENROUTER_API_KEY`
6. Value: `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`
7. The workflow will trigger on push to `main`

Live site: **https://mjlee079.github.io/shortscreen/**

### Option 4: Manual Deploy (Screening Task Approach)

1. Run the scraper locally: `cd casino-scraper && python src/scraper.py`
2. Commit the data: `git add casinos.json && git commit -m "update data"`
3. Push: `git push origin main`
4. Netlify/Vercel auto-deploys in ~1 minute
5. Refresh the page to see new data

**Advantages:** Simplest approach, works on free tiers
**Disadvantages:** Requires manual intervention, Data only updates when you run the scraper

---

## File Structure

```text
short/
├── .github/workflows/deploy.yaml      # GitHub Actions CI/CD
├── .gitignore
├── casinos.json                        # Scraped output (committed to repo)
├── netlify.toml                        # Netlify config
├── vercel.json                         # Vercel config
├── README.md                           # This file
├── WRITTEN.md                          # Production scaling plan
├── SECURITY.md                         # Security policy
├── prompts/
│   └── build-casino-scraper.md         # AI prompt engineering spec
└── casino-scraper/
    ├── .gitignore
    ├── pyproject.toml                  # Python config + mypy strict
    ├── src/
    │   ├── models.py                   # Dataclasses (CasinoBonus, ScrapeResult)
    │   ├── schema.py                   # JSON schema validation
    │   └── scraper.py                  # Main scraper (OpenRouter/NVIDIA Nemotron)
    ├── tests/
    │   └── test_scraper.py             # 31 pytest tests (>90% coverage)
    ├── frontend/
    │   ├── src/
    │   │   ├── App.tsx                 # Root React component
    │   │   ├── CasinoTable.tsx         # Responsive bonus table
    │   │   ├── main.tsx                # App entry point
    │   │   ├── types.ts                # TypeScript interfaces
    │   │   └── index.css               # Tailwind CSS
    │   ├── vite.config.ts
    │   ├── package.json
    │   ├── tailwind.config.js
    │   ├── netlify.toml                # Netlify config
    │   └── netlify/functions/
    │       ├── scrape.js               # Scheduled scraper function
    │       └── scrape.schedule.json     # Daily schedule trigger
    ├── casinos.json                      # Scraped output (committed)
    └── frontend/
        ├── package.json
        ├── vite.config.ts
        ├── tsconfig.json
        └── index.html
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | Yes (for LLM parsing) | NVIDIA Nemotron key from OpenRouter |
| `OPENAIR_API_KEY` | Optional | Alternative OpenAI key (fallback) |

## Scripts

| Command | Description |
|---------|-------------|
| `python src/scraper.py` | Run scraper (writes `casinos.json`) |
| `pytest tests/` | Run 31 pytest tests |
| `mypy --strict src/` | Type-check with mypy strict mode |
| `cd frontend && npm run dev` | Start React dev server (localhost:5173) |
| `cd frontend && npm run build` | Build production frontend |
| `git add casinos.json && git commit -m "update data"` | Manual data update |
| `git push origin main` | Push to trigger Netlify/Vercel deploy |

## License

Screening-task project. No license specified.