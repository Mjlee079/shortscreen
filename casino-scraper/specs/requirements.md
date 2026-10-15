# Casino Bonus Scraper - Requirements

## Overview
Build a casino bonus scraper that pulls bonus data from 3 online casinos from a public source and displays it on a single web page.

## Core Features

### 1. Scraper Script
- **Language**: Python (recommended for LLM integration and web scraping)
- **Source**: One public source (casino promotions page or comparison site)
- **Casinos**: Exactly 3 casinos
- **Fields per casino** (4 fields):
  1. Welcome bonus (free-text, e.g.,  100% up to 500 EUR)
  2. Wagering requirement (multiplier, e.g., 35)
  3. Minimum deposit (e.g., 20 EUR)
  4. Source URL (link to the page it was pulled from)
- **LLM usage**: Use a language model to turn free-text bonus terms into structured fields
- **Execution**: Runs with a single command
- **Robots.txt**: Respects robots.txt
- **No bypass**: Does not bypass logins, CAPTCHAs or blocks; if blocked, switches source

### 2. Web Page
- **A table of the 3 casinos** generated from the JSON file
- **Published**: On any free host (GitHub Pages, Netlify, Vercel)
- **Design**: Readable on a phone (does not need to be fancy)
- **Technology**: React (per the @react-expert skill)

### 3. Written Part (Production Planning)
- How to scale to 200 casinos, updated daily
- Where it runs: which server or cloud, and why
- Which database, and how it is backed up
- Domain, DNS and HTTPS
- How the daily scraper run is scheduled, and how to know it failed
- Rough monthly cost

## Deliverables

1. **Live link** to the web page
2. **Git repo** with:
   - The scraper script
   - The JSON output
   - A short README: how to install and run
3. **Written part**: Production plan for 200 casinos
4. **AI usage**: Which tool was used, one place where it was wrong and how it was caught
5. **Time tracked**: How long the task took
