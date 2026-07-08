import logging
import feedparser
from bs4 import BeautifulSoup
import html
import asyncio
import re
from embedder import embedder
import database

class RSSIngestor:
    """
    Polls RSS feeds for news, cleans HTML/XML, and yields non-duplicate items.
    """
    def __init__(self):
        from config import settings
        self.feeds = settings.RSS_FEEDS

    def _clean_text(self, text):
        if not text:
            return ""
        # Strip HTML tags
        soup = BeautifulSoup(text, "html.parser")
        text = soup.get_text(separator=" ")
        # Unescape XML entities
        text = html.unescape(text)
        # Remove bracketed content like [Reuters]
        text = re.sub(r'\[.*?\]', '', text)
        return text.strip()

    async def fetch_trends(self):
        """
        Fetches feeds, calculates semantic embeddings, checks db for duplicates,
        and yields non-duplicate items.
        """
        for feed_url in self.feeds:
            try:
                feed = await asyncio.to_thread(feedparser.parse, feed_url, agent="MemePipelineBot/1.0 (+http://localhost)")
                
                status = getattr(feed, "status", 200)
                if status == 429:
                    logging.warning(f"Rate limited (429) on feed {feed_url}")
                    continue
                if status >= 400:
                    logging.error(f"HTTP {status} fetching feed {feed_url}")
                    continue
                if getattr(feed, "bozo", 0) and not feed.entries:
                    logging.error(f"Bozo error on feed {feed_url}: {getattr(feed, 'bozo_exception', 'Unknown')}")
                    continue
                    
                for entry in feed.entries:
                    title = self._clean_text(entry.get("title", ""))
                    summary = self._clean_text(entry.get("summary", "") or entry.get("description", ""))
                    
                    if len(summary) > 500:
                        summary = summary[:497] + "..."

                    if not title:
                        continue

                    embedding = embedder.encode(title)
                    is_dup = await database.is_duplicate(title, embedding)
                    
                    if not is_dup:
                        logging.info(f"New trend found: {title}")
                        yield {"title": title, "summary": summary, "link": entry.get("link", "")}
            except Exception as e:
                logging.error(f"Error fetching feed {feed_url}: {e}")

# Provide a module-level helper as requested by main.py spec
ingestor = RSSIngestor()

async def fetch_trends():
    async for item in ingestor.fetch_trends():
        yield item
