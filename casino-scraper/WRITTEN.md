# Production Scaling Plan — 200 Casinos, Updated Daily

This document describes how to take the casino bonus scraper from a
3-casino screening task to a production system tracking 200 casinos,
updated daily. The role owns the full stack, so specific technology
choices are called out.

## Where It Runs

**Primary:** AWS Lambda (or Google Cloud Functions) for the scraper, plus
Amazon S3 + CloudFront for the static web front end.

**Why:**
- Lambda scales to zero — you pay only for the few minutes of daily
  scraper runtime, not for an always-on server.
- S3 + CloudFront provides a globally distributed, low-latency static
  site at minimal cost.
- Both are fully managed, minimizing operational toil.

**Alternative:** A small EC2 / Compute Engine instance running a Docker
container with cron, if long-running scraping sessions (e.g. JavaScript-
rendered sites requiring Playwright) exceed Lambda's 15-minute timeout.

## Database

**Choice:** PostgreSQL on Amazon RDS (or Cloud SQL on GCP).

**Why:** With 200 casinos and daily updates, you need queryable history
(which bonus changed when), not just a flat JSON file. PostgreSQL gives
ACID transactions, JSONB for flexible bonus-term storage, and mature
tooling.

**Schema (simplified):**

```sql
CREATE TABLE casinos (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  source_url TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE bonus_snapshots (
  id SERIAL PRIMARY KEY,
  casino_id INTEGER REFERENCES casinos(id),
  welcome_bonus TEXT,
  wagering_requirement INTEGER,
  minimum_deposit TEXT,
  scraped_at TIMESTAMPTZ NOT NULL,
  source TEXT NOT NULL
);
```

**Backups:**
- RDS automated daily snapshots + point-in-time recovery (35-day
  retention).
- Weekly manual snapshot copied to a different region for disaster
  recovery.
- Daily `pg_dump` to S3 as an additional logical backup.

## Domain, DNS, and HTTPS

- **Domain:** Registered via Route 53 (or Cloudflare), e.g.
  `casinobonuses.example.com`.
- **DNS:** Route 53 alias records pointing to the CloudFront
  distribution.
- **HTTPS:** AWS Certificate Manager (ACM) public certificate attached
  to CloudFront — free, auto-renewed, TLS 1.3.
- **Security headers:** CloudFront response headers policy enforcing
  CSP, HSTS, X-Frame-Options, X-Content-Type-Options.

## Daily Scraper Schedule & Failure Detection

**Scheduling:** Amazon EventBridge (CloudWatch Events) cron rule
triggering the Lambda scraper once daily (e.g. 02:00 UTC).

**Failure detection:**
1. Lambda emits CloudWatch metrics (duration, error count).
2. CloudWatch alarm triggers on any failed invocation, sending an SNS
   notification (email / Slack / PagerDuty).
3. The scraper writes a run manifest to DynamoDB (success/failure,
   timestamp, error message); a separate "heartbeat" Lambda checks the
   manifest daily and alerts if no successful run appeared in the last
   26 hours.
4. Dashboards in CloudWatch show scraper success rate, latency, and
   rows inserted.

## Data Flow

1. EventBridge triggers the scraper Lambda.
2. Lambda fetches each of 200 casino pages (respecting robots.txt,
   rate-limited, with retries and exponential backoff).
3. Free-text bonus terms are parsed via an LLM (OpenAI API or a
   self-hosted model for cost control).
4. Structured bonus data is validated against a JSON schema and inserted
   into PostgreSQL as a new snapshot row.
5. A build step regenerates a public JSON feed (or queries the DB
   directly via an API) and publishes it to S3.
6. CloudFront invalidates its cache; the static React front end fetches
   the latest data.

## Rough Monthly Cost

| Component | Estimate (USD/month) |
|-----------|---------------------|
| AWS Lambda (200 casinos, daily) | $1–$3 |
| Amazon RDS PostgreSQL (db.t3.micro, single-AZ) | $15–$20 |
| S3 + CloudFront (static site, low traffic) | $2–$5 |
| Route 53 hosted zone | $0.50 |
| ACM certificate | $0 |
| CloudWatch alarms + SNS notifications | $1–$2 |
| OpenAI API (200 LLM calls/day) | $5–$15 (depends on model) |
| **Total** | **~$25–$45/month** |

Costs can be reduced by using a smaller/self-hosted LLM model, spot
instances, or consolidating the scraper onto a single small EC2
instance instead of Lambda + RDS.

## AI Usage

Tool used: OpenCode with the @python-pro, @react-expert,
@prompt-engineer, @websocket-engineer, @security-reviewer,
@secure-code-guardian, @test-master, @sre-engineer, @architecture-designer,
@code-documenter, @spec-miner, and @the-fool skills.

One place where AI was wrong: The initial scraper draft used
`openai.ChatCompletion.create` (the legacy v0.x OpenAI SDK API) and
`BeautifulSoup.find_class()` (which does not exist — BeautifulSoup uses
`find(class_=...)` or `select_one()`). It also disabled SSL verification
with `verify=False`, which violates secure-coding guidelines.

How it was caught: The code was reviewed against the @python-pro type
safety and mypy strict requirements, the @secure-code-guardian
no-hardcoded-secrets / TLS rules, and manual reading of the BeautifulSoup
docs. The OpenAI SDK was updated to the v1.x client
(`OpenAI().chat.completions.create`), `find_class` was replaced with
`select_one`, and `verify=False` was removed so certificate verification
is enforced.

## Time Spent

Approximately 3 hours (screening-task cap): architecture review, prompt
engineering, scraper implementation with type safety, React frontend,
test suite, CI/CD workflow, and documentation.