import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import settings
from groq import Groq
import openai
from pydantic import BaseModel
from pydantic_models import BouncerOutput, VisionOutput
from typing import NoReturn

class LLMAuthError(Exception): pass
class LLMRateLimitError(Exception): pass
class LLMFatalError(Exception): pass

def map_exception(e: Exception) -> NoReturn:
    error_msg = str(e).lower()
    if "401" in error_msg or "unauthorized" in error_msg or "authentication" in error_msg:
        raise LLMAuthError(f"Authentication failed: {e}")
    elif "429" in error_msg or "rate limit" in error_msg or "too many requests" in error_msg:
        raise LLMRateLimitError(f"Rate limited: {e}")
    else:
        raise LLMFatalError(f"Fatal LLM error: {e}")

groq_client = Groq(api_key=settings.GROQ_API_KEY)
if not settings.OPENAI_API_KEY:
    logging.warning("OPENAI_API_KEY not set — Groq fallback to OpenAI is disabled.")
openai_client = openai.Client(api_key=settings.OPENAI_API_KEY or "dummy_key_to_prevent_startup_crash")

@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(LLMRateLimitError)
)
def _call_groq(system_prompt: str, user_prompt: str, model_cls: type[BaseModel], model: str = "llama-3.1-8b-instant"):
    try:
        response = groq_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=500
        )
        content = response.choices[0].message.content.strip()
        return model_cls.model_validate_json(content)
    except Exception as e:
        map_exception(e)

@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(LLMRateLimitError)
)
def _call_openai(system_prompt: str, user_prompt: str, model_cls: type[BaseModel]):
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=500
        )
        content = response.choices[0].message.content.strip()
        return model_cls.model_validate_json(content)
    except Exception as e:
        map_exception(e)

def get_completion(system_prompt: str, user_prompt: str, response_model: type[BaseModel] = None, model: str = "llama-3.1-8b-instant"):
    model_cls = response_model if response_model is not None else BouncerOutput
    try:
        parsed = _call_groq(system_prompt, user_prompt, model_cls, model=model)
    except (LLMAuthError, LLMRateLimitError, LLMFatalError) as e:
        logging.warning(f"Groq failed ({e}), falling back to OpenAI.")
        parsed = _call_openai(system_prompt, user_prompt, model_cls)
        
    if response_model is None:
        return parsed.model_dump()
    return parsed


def get_vision_validation(image_base64: str) -> VisionOutput:
    if not settings.OPENAI_API_KEY or "dummy" in settings.OPENAI_API_KEY or "your_" in settings.OPENAI_API_KEY:
        return VisionOutput(is_clean=True, reason="Skipped: No OpenAI API key provided.")
        
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                    {"type": "text", "text": "Is this image safe for social media? Reply JSON: {\"is_clean\": true/false, \"reason\": \"\"}"}
                ]
            }],
            response_format={"type": "json_object"},
            max_tokens=50
        )
        return VisionOutput.model_validate_json(response.choices[0].message.content)
    except Exception as e:
        map_exception(e)
