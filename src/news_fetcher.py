"""
News fetching from NewsAPI.org and NYTimes Article Search API.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class NewsFetcher:
    def __init__(self, newsapi_key: str, nytimes_key: str, sources: list[str], proxy: str = ""):
        self.newsapi_key = newsapi_key
        self.nytimes_key = nytimes_key
        self.sources = sources
        self.proxy = proxy  # e.g. "http://127.0.0.1:7890"

    def fetch_all(self, max_articles: int = 25) -> list[dict]:
        """Fetch from all sources, deduplicate, and return top articles."""
        articles: list[dict] = []

        if self.newsapi_key:
            articles += self._fetch_newsapi(max_articles)
            articles += self._fetch_newsapi_keywords(max_articles)

        if self.nytimes_key:
            articles += self._fetch_nytimes(max_articles)

        articles = self._deduplicate(articles)
        articles.sort(key=lambda a: a.get("published_at", ""), reverse=True)
        return articles[:max_articles]

    def _fetch_newsapi(self, max_articles: int) -> list[dict]:
        """Fetch top headlines from NewsAPI.org (free-tier compatible)."""
        try:
            sources_param = ",".join(self.sources)
            url = "https://newsapi.org/v2/top-headlines"
            params = {
                "sources": sources_param,
                "pageSize": min(max_articles, 100),
                "apiKey": self.newsapi_key,
            }
            proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
            resp = requests.get(url, params=params, timeout=15, proxies=proxies)
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") != "ok":
                logger.error("NewsAPI error: %s", data.get("message", "unknown"))
                return []

            articles = []
            for item in data.get("articles", []):
                articles.append({
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                    "content": item.get("content", ""),
                    "source": item.get("source", {}).get("name", ""),
                    "url": item.get("url", ""),
                    "published_at": item.get("publishedAt", ""),
                })
            logger.info("NewsAPI: fetched %d articles", len(articles))
            return articles
        except requests.RequestException as e:
            logger.error("NewsAPI fetch failed: %s", e)
            return []

    def _fetch_newsapi_keywords(self, max_articles: int) -> list[dict]:
        """Supplementary keyword search for major political/economic stories."""
        try:
            keywords = "Trump OR Xi OR tariff OR trade OR Fed OR rate OR oil OR GDP OR election"
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": keywords,
                "from": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"),
                "sortBy": "popularity",
                "pageSize": min(max_articles, 100),
                "language": "en",
                "apiKey": self.newsapi_key,
            }
            proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
            resp = requests.get(url, params=params, timeout=15, proxies=proxies)
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") != "ok":
                logger.error("NewsAPI keyword search error: %s", data.get("message", "unknown"))
                return []

            articles = []
            for item in data.get("articles", []):
                articles.append({
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                    "content": item.get("content", ""),
                    "source": item.get("source", {}).get("name", ""),
                    "url": item.get("url", ""),
                    "published_at": item.get("publishedAt", ""),
                })
            logger.info("NewsAPI keywords: fetched %d articles", len(articles))
            return articles
        except requests.RequestException as e:
            logger.error("NewsAPI keyword search failed: %s", e)
            return []

    def _fetch_nytimes(self, max_articles: int) -> list[dict]:
        """Fetch from NYTimes Article Search API with political/economic focus."""
        try:
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
            url = "https://api.nytimes.com/svc/search/v2/articlesearch.json"
            params = {
                "begin_date": yesterday,
                "sort": "newest",
                "api-key": self.nytimes_key,
                "fq": 'section_name:("Politics","Business","Economy","World","U.S.")',
            }
            proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
            resp = requests.get(url, params=params, timeout=15, proxies=proxies)
            resp.raise_for_status()
            data = resp.json()

            articles = []
            for doc in data.get("response", {}).get("docs", [])[:max_articles]:
                headline = doc.get("headline", {}).get("main", "")
                abstract = doc.get("abstract", "")
                lead = doc.get("lead_paragraph", "")
                articles.append({
                    "title": headline,
                    "description": abstract or lead,
                    "content": abstract + " " + lead if abstract and lead else (abstract or lead),
                    "source": "The New York Times",
                    "url": doc.get("web_url", ""),
                    "published_at": doc.get("pub_date", ""),
                })
            logger.info("NYTimes: fetched %d articles", len(articles))
            return articles
        except requests.RequestException as e:
            logger.error("NYTimes fetch failed: %s", e)
            return []

    def _deduplicate(self, articles: list[dict]) -> list[dict]:
        """Remove duplicate articles by similar title."""
        seen: set[str] = set()
        unique = []
        for a in articles:
            # Normalize title for dedup: lowercase, strip, first 60 chars
            key = a["title"].lower().strip()[:60]
            if key and key not in seen:
                seen.add(key)
                unique.append(a)
        return unique
