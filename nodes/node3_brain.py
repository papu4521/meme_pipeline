import logging
import llm_client
from pydantic_models import BrainOutput, JudgeOutput
from pydantic import ValidationError

class BrainNode:
    """
    Creative strategist using an LLM-as-a-Judge pattern to generate meme tweets.
    """
    def __init__(self):
        self.generation_prompt = """You are a witty tech-humor Twitter strategist. You write viral meme tweets for a developer audience.
You must output ONLY valid JSON matching the exact schema. No explanation. No preamble. No markdown.

Rules for candidates (must provide exactly 3):
- Be dry, ironic, or absurdist. Speak to software engineers.
- Never use hashtags like #AI or #Tech more than twice total.
- Always end with a relevant emoji.
- Max 240 characters.

Rules for image_prompt:
- Describe only what should be SEEN. No dialogue, no captions, no text in the image.
- Instead of "a robot saying I am tired", write "an exhausted robot slumped at a computer desk, cinematic lighting"
- Style: digital art, clean, slightly exaggerated, editorial illustration style
- NEVER include any words, letters, text, signs, speech bubbles, or writing of any kind in the prompt.
- The `image_prompt` must be strictly PG-rated and brand-safe to avoid triggering NSFW filters. Do not include violence, adult themes, or edgy language in the visual description.
- DO NOT use real company names, trademarks, or specific product names (like iPhone, Apple, OpenAI, etc) as they instantly trigger copyright/safety filters in the image generator. Use generic terms instead (e.g. 'smartphone', 'tech company', 'AI lab').

Output format:
{
  "image_prompt": "<purely visual prompt>",
  "candidates": ["<tweet 1>", "<tweet 2>", "<tweet 3>"]
}
"""
        self.fallback_prompt = """You are a witty tech-humor Twitter strategist. 
Write exactly 3 funny tweet candidates about the topic, and 1 image prompt.
Output format:
{
  "image_prompt": "<purely visual prompt>",
  "candidates": ["<tweet 1>", "<tweet 2>", "<tweet 3>"]
}
"""

        self.judge_prompt = """You are a ruthless comedy editor. Given these 3 tweet options about a tech trend, pick the absolute funniest one. Consider irony and developer relatability.
You must output ONLY valid JSON matching the exact schema.

Output format:
{
  "winning_tweet": "<the exact text of the chosen tweet>",
  "reasoning": "<short explanation of why it won>"
}
"""

    def generate(self, item):
        user_message = f"Trend: {item.get('title')}\nContext: {item.get('summary')}"
        
        try:
            # Step 1: Divergence
            brain_output = llm_client.get_completion(self.generation_prompt, user_message, response_model=BrainOutput)
        except ValidationError as ve:
            logging.warning(f"Brain validation failed, falling back to 1 tweet: {ve}")
            try:
                brain_output = llm_client.get_completion(self.fallback_prompt, user_message, response_model=BrainOutput)
            except Exception as e2:
                logging.error(f"Fallback also failed: {e2}")
                return {"tweet_text": "Tech is crazy right now. 🤯", "image_prompt": "a confused robot"}
        except Exception as e:
            logging.error(f"BrainNode generation error: {e}")
            raise
            
        # Step 2: Convergence (LLM-as-a-Judge)
        if len(brain_output.candidates) > 1:
            candidates_text = "\n".join([f"Option {i+1}: {c}" for i, c in enumerate(brain_output.candidates)])
            judge_message = f"{user_message}\n\nCandidates:\n{candidates_text}"
            
            try:
                judge_output = llm_client.get_completion(self.judge_prompt, judge_message, response_model=JudgeOutput)
                winning_tweet = judge_output.winning_tweet
                logging.info(f"Judge selected tweet: {winning_tweet} (Reasoning: {judge_output.reasoning})")
            except Exception as e:
                logging.error(f"Judge failed, defaulting to first candidate: {e}")
                winning_tweet = brain_output.candidates[0]
        else:
            winning_tweet = brain_output.candidates[0]
            
        if len(winning_tweet) > 240:
            winning_tweet = winning_tweet[:240].rsplit(' ', 1)[0]
            
        return {
            "tweet_text": winning_tweet,
            "image_prompt": brain_output.image_prompt
        }
