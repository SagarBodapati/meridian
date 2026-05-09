"""Financial news searcher — queries public RSS feeds and returns recent headlines."""
import asyncio
from dataclasses import dataclass
from datetime import datetime

import httpx
import structlog

log = structlog.get_logger()

RSS_FEEDS: dict[str, str] = {
    "reuters_business": "https://feeds.reuters.com/reuters/businessNews",
    "reuters_finance": "https://feeds.reuters.com/reuters/companyNews",
    "ft_markets": "https://www.ft.com/rss/home/uk",
    "sec_press": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=40&output=atom",
}


@dataclass
class NewsItem:
    title: str
    summary: str
    url: str
    published: datetime
    source: str


class NewsSearcher:
    """Fetches and filters recent news by keyword/ticker."""

    async def search(self, query: str, ticker: str | None = None, max_results: int = 10) -> list[NewsItem]:
        items: list[NewsItem] = []
        keywords = [q.lower() for q in query.split()[:5]]
        if ticker:
            keywords.append(ticker.lower())

        async with httpx.AsyncClient(timeout=15) as client:
            tasks = [self._fetch_feed(client, name, url) for name, url in RSS_FEEDS.items()]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for feed_items in results:
            if isinstance(feed_items, Exception):
                continue
            for item in feed_items:
                text = (item.title + " " + item.summary).lower()
                if any(kw in text for kw in keywords):
                    items.append(item)

        # Sort by recency, deduplicate by title
        seen_titles: set[str] = set()
        unique_items = []
        for item in sorted(items, key=lambda x: x.published, reverse=True):
            if item.title not in seen_titles:
                seen_titles.add(item.title)
                unique_items.append(item)

        return unique_items[:max_results]

    async def _fetch_feed(self, client: httpx.AsyncClient, name: str, url: str) -> list[NewsItem]:
        try:
            resp = await client.get(url, headers={"User-Agent": "Meridian/1.0"})
            resp.raise_for_status()
            return _parse_rss(resp.text, name)
        except Exception as exc:
            log.debug("news.feed_failed", feed=name, error=str(exc))
            return []


def _parse_rss(xml: str, source: str) -> list[NewsItem]:
    """Minimal RSS/Atom parser — no lxml needed."""
    import re
    items = []
    # Handle both <item> (RSS) and <entry> (Atom)
    entry_re = re.compile(r"<(?:item|entry)>([\s\S]*?)</(?:item|entry)>", re.I)
    title_re = re.compile(r"<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", re.I | re.S)
    link_re = re.compile(r"<link[^>]*>([^<]+)</link>|<link[^>]+href=['\"]([^'\"]+)['\"]", re.I)
    summary_re = re.compile(
        r"<(?:description|summary|content)[^>]*>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?</(?:description|summary|content)>",
        re.I,
    )
    date_re = re.compile(r"<(?:pubDate|updated|published)[^>]*>(.*?)</(?:pubDate|updated|published)>", re.I)

    for match in entry_re.finditer(xml):
        body = match.group(1)
        title_m = title_re.search(body)
        link_m = link_re.search(body)
        summary_m = summary_re.search(body)
        date_m = date_re.search(body)

        title = _clean(title_m.group(1) if title_m else "")
        url = link_m.group(1) or link_m.group(2) if link_m else ""
        summary = _clean(summary_m.group(1) if summary_m else "")[:300]
        pub_str = date_m.group(1).strip() if date_m else ""
        pub_dt = _parse_rss_date(pub_str)

        if title:
            items.append(NewsItem(title=title, summary=summary, url=url.strip(), published=pub_dt, source=source))

    return items


def _clean(text: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def _parse_rss_date(s: str) -> datetime:
    from email.utils import parsedate_to_datetime
    if not s:
        return datetime.utcnow()
    try:
        return parsedate_to_datetime(s).replace(tzinfo=None)
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            pass
    return datetime.utcnow()
