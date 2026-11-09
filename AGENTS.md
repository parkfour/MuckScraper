# MuckScraper Project Memory & Maintenance Guide

## 1. Project Overview & Architecture
* **Upstream Repository**: `https://github.com/grregis/MuckScraper.git`
* **Local / Fork Repository**: `git@github.com:parkfour/MuckScraper.git`
* **Public Domain**: `https://news.parkfour.com`
* **Reverse Proxy**: Apache vhost on `center` (`/etc/apache2/sites-available/news.parkfour.com-ssl.conf`) proxying to `lakefour.n.parkfour.com:5000`
* **Production Deployment**: Host `lakefour` (`/zjunk/services/muckscraper`)
* **Docker Compose Stack**:
  * `app` (FastAPI / port 5000)
  * `scheduler` (automated morning, midday, and evening editions)
  * `postgres` (PostgreSQL with pgvector for embeddings and semantic search)
  * `docker-restart-proxy`

---

## 2. Git Configuration & SSH Authentication
Always use the dedicated GitHub identity and SSH agent configuration when committing and pushing:

* **Author Identity**: `Paul J. Park <coding@parkfour.com>`
* **SSH Key & Agent**:
  ```bash
  git config core.sshCommand "ssh -o IdentityAgent=/run/user/1000/gcr/ssh -i ~/.ssh/coding@parkfour.com.pub -o IdentitiesOnly=yes"
  git config user.name "Paul J. Park"
  git config user.email "coding@parkfour.com"
  ```
* **Remotes**:
  * `origin`: `git@github.com:parkfour/MuckScraper.git` (GitHub fork)
  * `upstream`: `https://github.com/grregis/MuckScraper.git` (Original open-source repo)

---

## 3. Pull Request Status & Upstream Tracking

### Merged Upstream
* **PR #41** (`fix/rss-feed-topic-labels`): Makes feed topic assignment opt-in per feed.
* **PR #42** (`fix/gemini-429-backoff` - commit `e913748`): Handles Gemini 429 quota exhaustion and transient errors with exponential backoff and container rate pacing. Merged 2026-11-05.
* **PR #43** (`feat/json-ld-article-body`): Extracts article body from JSON-LD schema with fallback.

### Submitted / Active PRs
* **PR #44** (`fix/font-stack-quote-spacing`):
  * Eliminates large spacing gaps around smart quotes / apostrophes across templates by prioritizing Western system fonts and forcing `font-kerning: normal`.
  * Updated with review feedback: `--font-sans` single token in `theme.css` without trailing `system-ui`, and plain `var(--font-sans)` across templates. Rebased cleanly on `upstream/main`.
* **PR #45** (`fix/openai-compatible-transient-retries`):
  * Adds transient error retries (502, 503, 504) for OpenAI-compatible LLM endpoints.
  * Updated with review feedback: preserves deliberate 16s default wait on 429 rate limits, uses exponential backoff for 502/503/504, includes unit tests for both 429 and 503 retry waits. Rebased cleanly on `upstream/main`.

### Rules for New Pull Requests
1. **Always Branch from Upstream**: When creating PR branches for `grregis/MuckScraper`, branch directly from `upstream/main` (`git checkout -b fix/feature-name upstream/main`).
2. **Zero Deployment Leakage**: Never include `lakefour-deployment` specific custom features (e.g. Jetson local fallback, custom tragedy scrapers) in upstream PR branches.
3. **Clean Commit History**: Keep PR branches rebased cleanly on `upstream/main`.

---

## 4. Lakefour Production Deployment & Architecture

### Host & Environment Details
* **Host**: `lakefour` (`lakefour.n.parkfour.com`)
* **Deployment Path**: `/zjunk/services/muckscraper`
* **Access**: `ssh -i ~/.ssh/ztfs_deploy_key paul@lakefour`
* **Docker Compose Stack**:
  * `muckscraper-app-1`: FastAPI web interface and API on local port `5000`.
  * `muckscraper-scheduler-1`: Automated cron scheduler for daily editions.
  * `muckscraper-postgres-1`: PostgreSQL 16 with `pgvector` for semantic embeddings and hybrid search.
  * `muckscraper-docker-restart-proxy-1`: Helper container to trigger container reboots via Docker socket.
* **Database & Migration Memory**:
  * Earlier versions used a dedicated Meilisearch container. As of upstream v1.1.0, Meilisearch was fully retired in favor of PostgreSQL native full-text + pgvector search.
* **Public Gateway & Reverse Proxy**:
  * Apache virtual host on `center` (`/etc/apache2/sites-available/news.parkfour.com-ssl.conf`) terminates TLS (`https://news.parkfour.com`) and reverse proxies both HTTP and WebSocket traffic (for live edition generation progress) to `lakefour.n.parkfour.com:5000`.

### Scheduled Publishing Schedule
* Morning Edition: 7:00 AM
* Midday Edition: 12:00 PM (Local custom feature)
* Evening Edition: 6:00 PM

---

## 5. Development Branching Strategy & Local Customizations

### Why `lakefour-deployment` Exists
`grregis/MuckScraper` is an active upstream open-source project. To keep our production deployment stable while contributing clean PRs upstream:
* **`upstream/main`**: Pristine tracking branch of the official open-source repository.
* **`origin/main`**: Our GitHub fork's default branch, kept fast-forward aligned with `upstream/main`.
* **`lakefour-deployment`**: Our long-lived production deployment branch. It integrates `upstream/main` with site-specific production features and local bug fixes waiting for upstream review.

### Local Features Maintained on `lakefour-deployment`
1. **Jetson Local LLM Fast-Tier (`news_fetcher/llm_client.py`)**:
   * Uses local Jetson cluster (`jetson.n.parkfour.com:8080`) for rapid headline/summary classification.
   * *Critical Memory*: Reasoning models on Jetson generate `<thought>...</thought>` thinking tokens that can blow out token limits and fail headline generation. In `news_fetcher/llm_client.py`, reasoning tokens are explicitly stripped and output length is capped (`max_tokens: 300`) to guarantee fast, reliable completion.
2. **Unpaywall Article Scraping Fallback (`news_fetcher/unpaywall.py`)**:
   * Resolves paywalled or restricted news links via the Unpaywall open-access resolver when standard scraping yields sparse content.
3. **Tragedy Topic Headline Preservation (`deep_report/tragedy`)**:
   * Preserves exact breaking/tragedy headlines and prevents aggressive summarization from diluting critical details.
4. **Midday Edition Support (`edition_publish.py`)**:
   * Extra scheduled edition at 12:00 PM.
5. **Smart Quote Typography & Font Stack**:
   * Eliminates large spacing gaps around smart quotes/apostrophes by prioritizing Western system fonts and forcing `font-kerning: normal`.
6. **OpenAI Endpoint Transient Retries**:
   * Retries transient 502/503/504 errors with exponential backoff on OpenAI-compatible API providers.

### Historical Context: `lakefour/local-wip`
* `lakefour/local-wip` (commit `f262abb`) was the historical snapshot branch used to preserve uncommitted local features from `lakefour` before standardizing on git worktrees.
* In commit `182465d`, upstream v1.1.0 was merged cleanly into `lakefour-deployment` and all local features were re-integrated. `lakefour-deployment` is now the sole authoritative branch for production.

---

## 6. PR & Deployment Workflows

### Creating an Upstream Pull Request (Clean & Conflict-Free)
Never branch off `lakefour-deployment` for upstream PRs—this prevents local deployment code from leaking upstream.
```bash
# 1. Ensure upstream is fresh
git fetch upstream

# 2. Branch directly from upstream/main
git checkout -b fix/my-clean-fix upstream/main

# 3. Cherry-pick or make changes, write tests, and verify
pytest tests/

# 4. Push to fork under coding@parkfour.com
git push -u origin fix/my-clean-fix
```

### Deploying to Lakefour
```bash
# 1. Merge or cherry-pick approved changes into lakefour-deployment locally
git checkout lakefour-deployment
git merge --no-ff fix/my-clean-fix

# 2. Push to GitHub fork
git push origin lakefour-deployment

# 3. Pull on lakefour (Note: remote is named 'parkfour' on lakefour)
ssh -i ~/.ssh/ztfs_deploy_key paul@lakefour \
  "cd /zjunk/services/muckscraper && git pull parkfour lakefour-deployment && docker compose restart app scheduler"
```

---

## 5. Development & Testing
* **Virtualenv**: Activate with `source .venv/bin/activate`.
* **Running Tests**:
  ```bash
  pytest tests/
  ```
