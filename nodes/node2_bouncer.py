import logging
import json
import time
import llm_client

class BounceFilter:
    """
    Relevance filter using a small LLM to determine if a news item is suitable.
    """
    def __init__(self):
        self.system_prompt = """You are a strict content filter for a tech-humor Twitter brand. 
Your only job is to output valid JSON. No explanation. No preamble.
Output format: {"is_relevant": true} or {"is_relevant": false}

Rules for is_relevant = true:
- Topic is about AI, software, startups, tech products, developer culture, or Silicon Valley
- The story is mildly amusing, ironic, surprising, or culturally relevant to tech workers
- No deaths, tragedies, natural disasters, wars, or human suffering

Rules for is_relevant = false:
- Politics, elections, government policy
- Crime, violence, accidents
- Health, medical, pandemics
- Finance, stock markets, cryptocurrency prices
- Sports, entertainment, celebrity gossip
- Anything tragic or emotionally heavy

Output ONLY valid JSON. No explanation."""

    def check_relevance(self, item):
        """
        Checks if a news item is relevant.
        Args:
            item (dict): {"title": str, "summary": str}
        Returns:
            bool: True if relevant, False otherwise.
        """
        user_message = f"Title: {item.get('title')}\nSummary: {item.get('summary')}"
        
        try:
            data = llm_client.get_completion(self.system_prompt, user_message)
            is_relevant = data.get("is_relevant", False)
            logging.info(f"Bouncer: '{item.get('title')}' -> {is_relevant}")
            return is_relevant
            
        except Exception as e:
            logging.error(f"Bouncer failed completely: {e}")
            return False
