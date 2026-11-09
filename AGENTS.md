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
* **PR #43** (`feat/json-ld-article-body`): Extracts article body from JSON-LD schema with fallback.

### Submitted / Active PRs
* **PR #42** (`fix/gemini-429-backoff` - commit `e913748`):
  * Handles Gemini 429 quota exhaustion and transient errors with exponential backoff and container rate passing.
* **`fix/font-stack-quote-spacing`** (commit `7560260`):
  * Fixes huge gaps after smart quotes / apostrophes across templates by prioritizing Western system fonts (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto...`) and setting `font-kerning: normal`.
* **`fix/openai-compatible-transient-retries`** (commit `c7e47c4`):
  * Adds transient error retries (502, 503, 504) for OpenAI-compatible LLM endpoints.

### Rules for New Pull Requests
1. **Always Branch from Upstream**: When creating PR branches for `grregis/MuckScraper`, branch directly from `upstream/main` (`git checkout -b fix/feature-name upstream/main`).
2. **Zero Deployment Leakage**: Never include `lakefour-deployment` specific custom features (e.g. Jetson local fallback, custom tragedy scrapers) in upstream PR branches.
3. **Clean Commit History**: Keep PR branches rebased cleanly on `upstream/main`.

---

## 4. Lakefour Production Deployment (`lakefour-deployment` branch)

The production server `lakefour` runs the dedicated `lakefour-deployment` branch, which combines upstream `main` with site-specific enhancements:

* **Branch**: `lakefour-deployment`
* **Local Features in `lakefour-deployment`**:
  1. **Unpaywall Article Scraping Fallback**: `news_fetcher/unpaywall.py` for paywalled source resolution.
  2. **Tragedy Topic Deep Reports**: Custom classification and headline preservation for tragedy/breaking events.
  3. **Midday Edition Support**: Scheduled publishing for midday digest.
  4. **Jetson Local LLM Tier**: Fast-tier LLM inference on Jetson host with thinking tokens suppressed and output token limits configured.
  5. **Font Kerning & Typography**: Smart-quote display fix across all web templates.
  6. **OpenAI Endpoint Transient Retries**: Resiliency against Gateway 502/503 timeouts.

### Deployment & Sync Workflow
1. Commit or cherry-pick changes onto `lakefour-deployment` locally.
2. Push to `origin`:
   ```bash
   git push origin lakefour-deployment
   ```
3. Deploy to `lakefour`:
   ```bash
   ssh -i ~/.ssh/ztfs_deploy_key paul@lakefour "cd /zjunk/services/muckscraper && git pull origin lakefour-deployment && docker compose restart app scheduler"
   ```

---

## 5. Development & Testing
* **Virtualenv**: Activate with `source .venv/bin/activate`.
* **Running Tests**:
  ```bash
  pytest tests/
  ```
