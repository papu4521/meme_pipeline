from unittest.mock import patch, MagicMock
from database import _cosine_similarity

def test_cosine_similarity_identical():
    v = [1.0, 0.0, 0.0]
    assert _cosine_similarity(v, v) == 1.0

def test_cosine_similarity_zero_vector():
    assert _cosine_similarity([0, 0, 0], [1, 2, 3]) == 0.0

@patch("llm_client.groq_client")
def test_bouncer_marks_irrelevant(mock_groq):
    mock_groq.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content='{"is_relevant": false}'))]
    )
    from nodes.node2_bouncer import BounceFilter
    bouncer = BounceFilter()
    
    # Run a test trend through the bouncer
    trend = {
        "title": "Random generic article about bananas",
        "summary": "This has nothing to do with software engineering.",
        "link": "http://example.com"
    }
    
    result = bouncer.check_relevance(trend)
    assert result is False
