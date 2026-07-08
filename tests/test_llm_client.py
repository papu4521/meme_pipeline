import pytest
from unittest.mock import patch, MagicMock
from pydantic_models import BouncerOutput, VisionOutput
from llm_client import _call_groq, get_completion, get_vision_validation, LLMRateLimitError, LLMAuthError
from llm_client import map_exception, LLMFatalError
from tenacity import RetryError

def test_call_groq_success():
    """Test that _call_groq succeeds and returns parsed Pydantic model."""
    with patch('llm_client.groq_client.chat.completions.create') as mock_create:
        mock_msg = MagicMock()
        mock_msg.message.content = '{"is_relevant": true, "reasoning": "test"}'
        mock_create.return_value = MagicMock(choices=[mock_msg])
        result = _call_groq("system", "user", BouncerOutput)
        assert result.is_relevant is True

def test_call_groq_retry_on_429():
    """Test _call_groq gets 429 -> retries -> succeeds on second attempt."""
    with patch('llm_client.groq_client.chat.completions.create') as mock_create:
        mock_msg = MagicMock()
        mock_msg.message.content = '{"is_relevant": true, "reasoning": "test"}'
        mock_create.side_effect = [Exception("429 Too Many Requests"), MagicMock(choices=[mock_msg])]
        result = _call_groq("system", "user", BouncerOutput)
        assert result.is_relevant is True
        assert mock_create.call_count == 2

def test_get_completion_fallback_openai_auth_error():
    """Test get_completion falls back to OpenAI when Groq raises LLMAuthError."""
    with patch('llm_client._call_groq') as mock_groq, patch('llm_client._call_openai') as mock_openai:
        mock_groq.side_effect = LLMAuthError("Auth failed")
        mock_openai.return_value = BouncerOutput(is_relevant=True)
        result = get_completion("system", "user", BouncerOutput)
        assert result.is_relevant is True
        mock_openai.assert_called_once()

def test_get_completion_fallback_openai_rate_limit():
    """Test get_completion falls back to OpenAI when Groq raises LLMRateLimitError."""
    with patch('llm_client._call_groq') as mock_groq, patch('llm_client._call_openai') as mock_openai:
        mock_groq.side_effect = LLMRateLimitError("Rate limit")
        mock_openai.return_value = BouncerOutput(is_relevant=False)
        result = get_completion("system", "user", BouncerOutput)
        assert result.is_relevant is False
        mock_openai.assert_called_once()

def test_get_vision_validation_success():
    """Test get_vision_validation returns VisionOutput with is_clean=True."""
    with patch('llm_client.openai_client.chat.completions.create') as mock_create:
        mock_msg = MagicMock()
        mock_msg.message.content = '{"is_clean": true}'
        mock_create.return_value = MagicMock(choices=[mock_msg])
        result = get_vision_validation("base64data")
        assert result.is_clean is True

def test_map_exception_401():
    with pytest.raises(LLMAuthError, match="Authentication failed"):
        map_exception(Exception("Http error 401"))

def test_map_exception_unauthorized():
    with pytest.raises(LLMAuthError, match="Authentication failed"):
        map_exception(Exception("UNAUTHORIZED error"))

def test_map_exception_429():
    with pytest.raises(LLMRateLimitError, match="Rate limited"):
        map_exception(Exception("Error 429 Too many requests"))

def test_map_exception_other():
    with pytest.raises(LLMFatalError, match="Fatal LLM error"):
        map_exception(Exception("Unknown error"))

def test_get_completion_fallback_openai_fatal_error():
    """Test get_completion falls back to OpenAI when Groq raises LLMFatalError."""
    with patch('llm_client._call_groq') as mock_groq, patch('llm_client._call_openai') as mock_openai:
        mock_groq.side_effect = LLMFatalError("Fatal error")
        mock_openai.return_value = BouncerOutput(is_relevant=True)
        result = get_completion("system", "user", BouncerOutput)
        assert result.is_relevant is True
        mock_openai.assert_called_once()

def test_call_groq_retry_exhausted():
    """Test _call_groq raises LLMRateLimitError and retries up to 2 times before failing."""
    with patch('llm_client.groq_client.chat.completions.create') as mock_create:
        mock_create.side_effect = Exception("429")
        with pytest.raises(RetryError):
            _call_groq("system", "user", BouncerOutput)
        assert mock_create.call_count == 2

def test_get_vision_validation_failure():
    """Test get_vision_validation raises appropriate exception."""
    with patch('llm_client.openai_client.chat.completions.create') as mock_create, \
         patch('llm_client.settings.OPENAI_API_KEY', "valid_key"):
        mock_create.side_effect = Exception("401 Unauthorized")
        with pytest.raises(LLMAuthError):
            get_vision_validation("base64data")

def test_call_openai_success():
    """Test _call_openai success."""
    from llm_client import _call_openai
    with patch('llm_client.openai_client.chat.completions.create') as mock_create:
        mock_msg = MagicMock()
        mock_msg.message.content = '{"is_relevant": true}'
        mock_create.return_value = MagicMock(choices=[mock_msg])
        result = _call_openai("sys", "user", BouncerOutput)
        assert result.is_relevant is True

def test_get_completion_no_response_model():
    """Test get_completion without response_model."""
    with patch('llm_client._call_groq') as mock_groq:
        mock_groq.return_value = BouncerOutput(is_relevant=True)
        result = get_completion("sys", "user", response_model=None)
        assert isinstance(result, dict)
        assert result["is_relevant"] is True

def test_call_openai_exception():
    """Test _call_openai exception mapping."""
    from llm_client import _call_openai, LLMRateLimitError
    with patch('llm_client.openai_client.chat.completions.create') as mock_create:
        mock_create.side_effect = Exception("429")
        with pytest.raises(RetryError):
            _call_openai("sys", "user", BouncerOutput)
