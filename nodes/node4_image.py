from PIL import Image
import io
from io import BytesIO
import base64
import uuid
import os
import time
import logging
from config import settings
import llm_client

class ImageGenerationError(Exception):
    pass

class ImageNode:
    def __init__(self):
        self.model = "black-forest-labs/FLUX.1-schnell"
        self.output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "generated_images")
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_image(self, image_prompt: str) -> dict:
        enhanced_prompt = (
            f"{image_prompt}, "
            "digital art style, clean editorial illustration, "
            "vibrant colors, professional quality, "
            "no text, no words, no watermarks, no signatures"
        )
        negative_prompt = (
            "text, watermark, blurry, deformed, ugly, "
            "low quality, pixelated, signature, letters, "
            "numbers, words, captions, speech bubbles"
        )

        last_error = None
        last_image_data = None

        for attempt in range(3):
            try:
                logging.info(f"Generating image (attempt {attempt + 1}/3) with FLUX.1-schnell...")

                # Image Generation logic using NVIDIA NIM or Pollinations
                filename = f"{uuid.uuid4().hex}.png"
                filepath = os.path.join(self.output_dir, filename)
                import requests
                
                if settings.NVIDIA_API_KEY and attempt == 0:
                    # Try NVIDIA NIM API first (Free Tier)
                    logging.info("Using NVIDIA NIM API for image generation...")
                    headers = {
                        "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
                        "Accept": "application/json",
                    }
                    payload = {
                        "prompt": enhanced_prompt,
                        "width": 1024,
                        "height": 1024,
                        "steps": 4,
                        "seed": 0,
                        "samples": 1
                    }
                    resp = requests.post("https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-schnell", headers=headers, json=payload, timeout=60)
                    resp.raise_for_status()
                    response_data = resp.json()
                    
                    image_base64 = (
                        response_data.get("b64_json") or 
                        response_data.get("image") or 
                        (response_data.get("data") and response_data["data"][0].get("b64_json")) or
                        (response_data.get("artifacts") and response_data["artifacts"][0].get("base64"))
                    )
                    
                    if not image_base64:
                        image_base64 = response_data.get("data", [{}])[0].get("url", "")
                    
                    if image_base64 and image_base64.startswith("data:image"):
                        image_base64 = image_base64.split(",")[1]
                        
                    if not image_base64:
                        raise ValueError(f"Could not find image base64 data in response: {str(response_data)[:200]}")
                        
                    image_binary = base64.b64decode(image_base64)
                else:
                    # Fallback to Pollinations.ai if no NVIDIA key is provided OR if we are retrying
                    if attempt > 0:
                        logging.warning("Falling back to Pollinations.ai due to previous failure...")
                    else:
                        logging.info("Using Pollinations.ai for image generation...")
                        
                    import urllib.parse
                    encoded_prompt = urllib.parse.quote(enhanced_prompt)
                    image_url_api = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=800&height=600&nologo=true"
                    resp = requests.get(image_url_api, timeout=60)
                    resp.raise_for_status()
                    image_binary = resp.content
                    image_base64 = base64.b64encode(image_binary).decode("utf-8")
                
                with open(filepath, "wb") as f:
                    f.write(image_binary)
                    
                # Check if image is completely black (safety filter trigger)
                try:
                    with Image.open(filepath) as img:
                        extrema = img.convert("L").getextrema()
                        if extrema == (0, 0) or extrema == (0, 255) and img.getbbox() is None:
                            # If min and max are 0, it's pitch black
                            pass
                        if extrema == (0, 0):
                            os.remove(filepath)
                            raise ValueError("Image generator returned a completely black image (Safety/NSFW filter triggered).")
                except Exception as e:
                    if "Safety/NSFW" in str(e):
                        raise e
                        
                logging.info(f"Image saved locally to: {filepath}")

                local_server_url = f"{settings.BASE_URL}/images/{filename}"
                data_url = f"data:image/png;base64,{image_base64}"
                
                last_image_data = {
                    "image_url": local_server_url,
                    "data_url": data_url,
                    "local_path": filepath,
                    "mime_type": "image/png",
                    "model_used": self.model
                }

                logging.info("Validating image with LLM Vision Gate...")
                vision_output = llm_client.get_vision_validation(image_base64)

                if not vision_output.is_clean:
                    logging.warning(f"Vision gate caught text in attempt {attempt + 1}! Regenerating...")
                    os.remove(filepath)
                    last_image_data = None # Clear dirty data
                    continue
                else:
                    logging.info("Vision gate approved image as text-free.")
                    return last_image_data

            except Exception as e:
                last_error = str(e)
                wait_time = 2 ** attempt
                if "503" in last_error or "loading" in last_error.lower():
                    wait_time = 20
                    logging.warning(f"Model is loading (cold start). Waiting {wait_time}s before retry...")
                else:
                    logging.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)

        logging.error(f"All 3 image generation/validation attempts failed. Last error: {last_error}")
        
        # Only return last_image_data if it was generated but failed due to network/API timeout on the vision side
        # not if it failed the vision check (where we set it to None)
        if last_image_data:
            return last_image_data
            
        raise ImageGenerationError("Failed to generate a text-free image after 3 attempts.")
