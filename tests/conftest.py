import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import pytest

@pytest.fixture
def fake_trend():
    return {
        "title": "Developers invent AI that writes commit messages for them",
        "summary": "A new AI tool automatically generates meaningful commit messages based on git diffs.",
        "link": "https://example.com/news",
        "published": "2026-06-21T10:00:00Z"
    }

@pytest.fixture
def fake_llm_response():
    return {
        "image_prompt": "A robot sitting at a keyboard typing commit messages, cyberpunk style",
        "candidates": [
            "Candidate 1",
            "Candidate 2",
            "Candidate 3"
        ]
    }
