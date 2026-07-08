import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from nodes.node1_ingestor import ingestor

@pytest.mark.asyncio
async def test_fetch_trends_yields_unique_items():
    """Test fetch_trends yields items that are not duplicates."""
    with patch('nodes.node1_ingestor.feedparser.parse') as mock_parse, \
         patch('nodes.node1_ingestor.embedder.encode'), \
         patch('nodes.node1_ingestor.database.is_duplicate', new_callable=AsyncMock) as mock_is_dup:
        mock_feed = MagicMock()
        mock_feed.status = 200
        mock_feed.bozo = 0
        mock_feed.entries = [{"title": "New Trend", "summary": "A summary"}]
        mock_parse.return_value = mock_feed
        mock_is_dup.return_value = False
        
        # Test just the first feed for simplicity
        with patch('config.settings.RSS_FEEDS', ["http://fakefeed"]):
            ingestor.feeds = ["http://fakefeed"]
            results = [item async for item in ingestor.fetch_trends()]
            assert len(results) == 1
            assert results[0]["title"] == "New Trend"

@pytest.mark.asyncio
async def test_fetch_trends_skips_no_title():
    """Test fetch_trends skips items with no title."""
    with patch('nodes.node1_ingestor.feedparser.parse') as mock_parse:
        mock_feed = MagicMock()
        mock_feed.status = 200
        mock_feed.entries = [{"title": "", "summary": "No title item"}]
        mock_parse.return_value = mock_feed
        
        with patch('config.settings.RSS_FEEDS', ["http://fakefeed"]):
            ingestor.feeds = ["http://fakefeed"]
            results = [item async for item in ingestor.fetch_trends()]
            assert len(results) == 0

@pytest.mark.asyncio
async def test_fetch_trends_skips_duplicates():
    """Test fetch_trends skips duplicate items (database.is_duplicate returns True)."""
    with patch('nodes.node1_ingestor.feedparser.parse') as mock_parse, \
         patch('nodes.node1_ingestor.embedder.encode'), \
         patch('nodes.node1_ingestor.database.is_duplicate', new_callable=AsyncMock) as mock_is_dup:
        mock_feed = MagicMock()
        mock_feed.status = 200
        mock_feed.entries = [{"title": "Duplicate Trend", "summary": "A summary"}]
        mock_parse.return_value = mock_feed
        mock_is_dup.return_value = True
        
        with patch('config.settings.RSS_FEEDS', ["http://fakefeed"]):
            ingestor.feeds = ["http://fakefeed"]
            results = [item async for item in ingestor.fetch_trends()]
            assert len(results) == 0

@pytest.mark.asyncio
async def test_fetch_trends_handles_429():
    """Test fetch_trends handles a 429 status on a feed gracefully."""
    with patch('nodes.node1_ingestor.feedparser.parse') as mock_parse:
        mock_feed = MagicMock()
        mock_feed.status = 429
        mock_parse.return_value = mock_feed
        
        with patch('config.settings.RSS_FEEDS', ["http://fakefeed"]):
            ingestor.feeds = ["http://fakefeed"]
            results = [item async for item in ingestor.fetch_trends()]
            assert len(results) == 0

@pytest.mark.asyncio
async def test_fetch_trends_handles_bozo():
    """Test fetch_trends handles a bozo feed error gracefully."""
    with patch('nodes.node1_ingestor.feedparser.parse') as mock_parse:
        mock_feed = MagicMock()
        mock_feed.status = 200
        mock_feed.bozo = 1
        mock_feed.entries = []
        mock_feed.bozo_exception = "Bad XML"
        mock_parse.return_value = mock_feed
        
        with patch('config.settings.RSS_FEEDS', ["http://fakefeed"]):
            ingestor.feeds = ["http://fakefeed"]
            results = [item async for item in ingestor.fetch_trends()]
            assert len(results) == 0

@pytest.mark.asyncio
async def test_fetch_trends_status_400():
    """Test fetch_trends skips feeds with status >= 400."""
    with patch('nodes.node1_ingestor.feedparser.parse') as mock_parse:
        mock_feed = MagicMock()
        mock_feed.status = 500
        mock_parse.return_value = mock_feed
        with patch('config.settings.RSS_FEEDS', ["http://fakefeed"]):
            ingestor.feeds = ["http://fakefeed"]
            results = [item async for item in ingestor.fetch_trends()]
            assert len(results) == 0

@pytest.mark.asyncio
async def test_fetch_trends_long_summary():
    """Test fetch_trends truncates summaries over 500 chars."""
    with patch('nodes.node1_ingestor.feedparser.parse') as mock_parse, \
         patch('nodes.node1_ingestor.embedder.encode'), \
         patch('nodes.node1_ingestor.database.is_duplicate', new_callable=AsyncMock) as mock_is_dup:
        mock_feed = MagicMock()
        mock_feed.status = 200
        long_summary = "A" * 600
        mock_feed.entries = [{"title": "T", "summary": long_summary}]
        mock_parse.return_value = mock_feed
        mock_is_dup.return_value = False
        with patch('config.settings.RSS_FEEDS', ["http://fakefeed"]):
            ingestor.feeds = ["http://fakefeed"]
            results = [item async for item in ingestor.fetch_trends()]
            assert len(results) == 1
            assert len(results[0]["summary"]) == 500
            assert results[0]["summary"].endswith("...")

@pytest.mark.asyncio
async def test_fetch_trends_loop_exception():
    """Test fetch_trends continues if database or embedder raises an exception."""
    with patch('nodes.node1_ingestor.feedparser.parse') as mock_parse, \
         patch('nodes.node1_ingestor.embedder.encode') as mock_encode:
        mock_feed = MagicMock()
        mock_feed.status = 200
        mock_feed.entries = [{"title": "T", "summary": "S"}]
        mock_parse.return_value = mock_feed
        mock_encode.side_effect = Exception("Embedder crash")
        with patch('config.settings.RSS_FEEDS', ["http://fakefeed"]):
            ingestor.feeds = ["http://fakefeed"]
            results = [item async for item in ingestor.fetch_trends()]
            assert len(results) == 0

@pytest.mark.asyncio
async def test_module_level_fetch_trends():
    """Test the module-level fetch_trends helper function."""
    from nodes.node1_ingestor import fetch_trends
    with patch('nodes.node1_ingestor.ingestor.fetch_trends') as mock_ingestor_fetch:
        # Create an async generator mock
        async def mock_gen():
            yield {"title": "T"}
        mock_ingestor_fetch.return_value = mock_gen()
        results = [item async for item in fetch_trends()]
        assert len(results) == 1
        assert results[0]["title"] == "T"
