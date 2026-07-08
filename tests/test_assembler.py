import pytest
from nodes.node5_assembler import assemble_payload

def test_assemble_payload_success():
    """Test assemble_payload correctly structures output when all data is present."""
    payload = assemble_payload(
        tweet_text="Funny meme",
        image_url="http://image.com/1.png",
        trend={"title": "News Article"}
    )
    assert payload["tweet_text"] == "Funny meme"
    assert payload["image_url"] == "http://image.com/1.png"
    assert payload["source_title"] == "News Article"
    assert payload["generation_failed"] is False
    assert "timestamp" in payload

def test_assemble_payload_missing_image():
    """Test assemble_payload falls back to a placeholder and sets generation_failed."""
    payload = assemble_payload(
        tweet_text="Funny meme",
        image_url=None,
        trend={"title": "News Article"}
    )
    assert payload["generation_failed"] is True
    assert "dummyimage.com" in payload["image_url"]

def test_assemble_payload_empty_tweet():
    """Test that assemble_payload raises ValueError on empty tweet_text."""
    with pytest.raises(ValueError, match="tweet_text cannot be empty"):
        assemble_payload("", "http://image.com/1.png", "Title")
