"""
Backfill and recover readable content for paywalled, blocked, or failed articles.
Runs through articles with missing or minimal content and unpaywalls them via
Archive.today, Wayback Machine, and JSON-LD schema metadata.
"""

import logging
import sys
import time
from sqlalchemy import func
from aggregator import create_app
from aggregator.models import Article, db
from news_fetcher.unpaywall import unpaywall_article

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def backfill_unpaywalled_articles(limit=50, min_len=400):
    app = create_app()
    with app.app_context():
        # Find candidates: blocked, failed, or short content
        candidates = Article.query.filter(
            (Article.scrape_status.in_(["blocked", "failed", "pending"])) |
            (func.length(Article.content) < min_len) |
            (Article.content.is_(None))
        ).order_by(Article.id.desc()).all()

        total = len(candidates)
        logger.info(f"Found {total} candidate articles for unpaywall recovery (limit={limit})")
        recovered = 0

        for i, article in enumerate(candidates[:limit]):
            url = article.url
            if not url or any(skip in url for skip in ["youtube.com", "twitter.com", "x.com"]):
                continue

            cur_len = len(article.content or "")
            logger.info(f"[{i+1}/{min(total, limit)}] Probing [{article.id}] {article.title[:50]} (cur len={cur_len}, status={article.scrape_status})")
            
            try:
                content, method = unpaywall_article(url)
                if content and len(content) >= min_len:
                    old_status = article.scrape_status
                    article.content = content
                    article.scrape_status = "unpaywalled"
                    article.scrape_method = f"unpaywall_{method}"
                    article.scrape_failure_reason = None
                    db.session.commit()
                    recovered += 1
                    logger.info(f"  ==> RECOVERED via {method}! New length: {len(content)} chars (was {old_status})")
                else:
                    logger.info(f"  ==> No unpaywall snapshot available yet for: {url[:60]}")
            except Exception as e:
                logger.warning(f"  ==> Error unpaywalling [{article.id}]: {e}")
                db.session.rollback()

            time.sleep(1)

        logger.info(f"Finished unpaywall run. Recovered {recovered} / {min(total, limit)} articles!")
        return recovered


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    backfill_unpaywalled_articles(limit=limit)
