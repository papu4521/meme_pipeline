import logging
from datetime import datetime, timezone

def assemble_payload(tweet_text: str, image_url: str, trend: dict) -> dict:
    """
    Assembles the final payload, handling missing images.
    Args:
        tweet_text (str): The winning generated tweet text from the Judge.
        image_url (str): The generated image URL from the Vision Loop.
        trend (dict): The original trend data.
    Returns:
        dict: The assembled payload.
    """
    if not tweet_text:
        raise ValueError("tweet_text cannot be empty")

    generation_failed = False
    if not image_url:
        generation_failed = True
        image_url = "https://dummyimage.com/800x600/000/fff.png&text=Image+Failed"
        logging.warning("Image generation failed flag set, using placeholder image.")

    payload = {
        "tweet_text": tweet_text,
        "image_url": image_url,
        "source_title": trend.get("title", ""),
        "source_link": trend.get("link", ""),
        "generation_failed": generation_failed,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    return payload
