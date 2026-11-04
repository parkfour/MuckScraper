"""
Unpaywall extraction and archive fallbacks for MuckScraper.
Fetches readable article content for paywalled, blocked, or 401/402/403 articles
via public web archives (Archive.today mirrors, Wayback Machine) and embedded
JSON-LD structured metadata.
"""

import logging
import json
import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
from aggregator.html_safety import sanitize_html

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

ARCHIVE_TODAY_MIRRORS = [
    "archive.ph",
    "archive.is",
    "archive.today",
    "archive.li",
    "archive.vn",
]

WAYBACK_AVAILABILITY_API = "https://archive.org/wayback/available?url="
MIN_ARTICLE_LENGTH = 250


def extract_json_ld_article_body(html_or_soup):
    """
    Extract articleBody directly from JSON-LD schema metadata.
    Many publishers (NYT, WaPo, Boston Globe, Gannett) include full articleBody
    in JSON-LD for search engine indexing even when paywalls gate the page.
    """
    if not html_or_soup:
        return None
    try:
        soup = html_or_soup if isinstance(html_or_soup, BeautifulSoup) else BeautifulSoup(html_or_soup, "html.parser")
        for script in soup.find_all("script", type="application/ld+json"):
            if not script.string:
                continue
            try:
                payload = json.loads(script.string)
            except Exception:
                continue
            stack = payload if isinstance(payload, list) else [payload]
            for item in stack:
                if not isinstance(item, dict):
                    continue
                sub_items = item.get("@graph") if isinstance(item.get("@graph"), list) else [item]
                for sub in sub_items:
                    if not isinstance(sub, dict):
                        continue
                    body = sub.get("articleBody")
                    if body and len(body.strip()) >= MIN_ARTICLE_LENGTH:
                        paragraphs = [f"<p>{p.strip()}</p>" for p in body.split("\n") if p.strip()]
                        html_content = sanitize_html("<div>" + "".join(paragraphs) + "</div>")
                        if len(html_content) >= MIN_ARTICLE_LENGTH:
                            return html_content
    except Exception as e:
        logger.debug(f"[Unpaywall] JSON-LD extraction error: {e}")
    return None


def fetch_archive_today(url, timeout=10):
    """
    Query Archive.today mirrors for the newest snapshot of a URL.
    Returns (sanitized_html, method_name) or (None, None).
    """
    from news_fetcher.scraper import extract_with_readability

    for mirror in ARCHIVE_TODAY_MIRRORS[:2]:
        try:
            lookup_url = f"https://{mirror}/newest/{url}"
            r = requests.get(lookup_url, headers=HEADERS, timeout=timeout, allow_redirects=False)
            if r.status_code in (301, 302, 303, 307):
                snap_url = r.headers.get("Location")
                if snap_url and "/wip/" not in snap_url:
                    if snap_url.startswith("/"):
                        snap_url = f"https://{mirror}{snap_url}"
                    logger.info(f"  [Unpaywall] Found {mirror} snapshot: {snap_url[:80]}")
                    snap_resp = requests.get(snap_url, headers=HEADERS, timeout=timeout + 4)
                    if snap_resp.status_code == 200:
                        content = extract_with_readability(snap_resp.text, snap_url)
                        if content and len(content) >= MIN_ARTICLE_LENGTH:
                            return content, f"{mirror}_snapshot"
        except Exception as e:
            logger.debug(f"[Unpaywall] Error probing {mirror}: {e}")
            continue
    return None, None


def fetch_wayback(url, timeout=8):
    """
    Query the Internet Archive Wayback Machine API for an existing snapshot.
    Returns (sanitized_html, method_name) or (None, None).
    """
    from news_fetcher.scraper import extract_with_readability

    try:
        api_url = WAYBACK_AVAILABILITY_API + quote(url, safe=":/?=&%_-")
        r = requests.get(api_url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            snap = data.get("archived_snapshots", {}).get("closest", {}).get("url")
            if snap:
                logger.info(f"  [Unpaywall] Found Wayback snapshot: {snap[:80]}")
                snap_resp = requests.get(snap, headers=HEADERS, timeout=timeout + 6)
                if snap_resp.status_code == 200:
                    content = extract_with_readability(snap_resp.text, snap)
                    if content and len(content) >= MIN_ARTICLE_LENGTH:
                        return content, "wayback_snapshot"
    except Exception as e:
        logger.debug(f"[Unpaywall] Wayback Machine lookup error: {e}")
    return None, None


def unpaywall_article(url, initial_html=None):
    """
    Multi-stage unpaywall pipeline for paywalled, gated, or failed articles:
    1. Direct JSON-LD articleBody check if initial_html is available
    2. Archive.today newest snapshot
    3. Internet Archive Wayback Machine snapshot
    Returns (content, method) or (None, None).
    """
    if initial_html:
        json_ld_body = extract_json_ld_article_body(initial_html)
        if json_ld_body:
            logger.info(f"  [Unpaywall] Extracted JSON-LD articleBody ({len(json_ld_body)} chars) from original HTML")
            return json_ld_body, "json_ld_articlebody"

    # Try Archive.today first (freshest snapshots for breaking news)
    content, method = fetch_archive_today(url)
    if content:
        return content, method

    # Try Wayback Machine
    content, method = fetch_wayback(url)
    if content:
        return content, method

    return None, None
