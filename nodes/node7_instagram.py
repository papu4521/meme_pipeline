import logging
import httpx
import time
from config import settings

class InstagramAuthError(Exception): pass
class InstagramRateLimitError(Exception): pass
class InstagramPublishError(Exception): pass

class InstagramPublisher:
    def __init__(self):
        self.account_id = settings.INSTAGRAM_ACCOUNT_ID
        self.access_token = settings.META_ACCESS_TOKEN
        self.base_url = "https://graph.facebook.com/v19.0"

    def _handle_error(self, response: httpx.Response):
        try:
            error_data = response.json().get("error", {})
        except Exception:
            error_data = {"message": response.text}
            
        error_msg = error_data.get("message", "Unknown error").lower()
        code = error_data.get("code")
        
        if response.status_code == 401 or "invalid oauth" in error_msg:
            raise InstagramAuthError(f"Authentication failed: {error_msg}")
        elif response.status_code == 429 or code == 4:
            raise InstagramRateLimitError(f"Rate limited: {error_msg}")
        else:
            raise InstagramPublishError(f"Publish error {response.status_code}: {error_data}")

    def publish_image(self, image_url: str, caption: str, local_path: str = None) -> dict:
        if image_url.startswith("http://localhost") or image_url.startswith("data:"):
            raise ValueError("Instagram requires a publicly accessible image URL, not localhost or data URI.")

        import os
        if not local_path and "trycloudflare.com/images/" in image_url:
            filename = image_url.split("/images/")[-1]
            possible_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated_images", filename)
            if os.path.exists(possible_path):
                local_path = possible_path

        if "trycloudflare.com" in image_url and local_path:
            logging.info(f"Cloudflare URL detected. Using catbox.moe bypass for {local_path}...")
            try:
                with open(local_path, "rb") as f:
                    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                    response = httpx.post("https://catbox.moe/user/api.php", data={"reqtype": "fileupload"}, files={"fileToUpload": f}, headers=headers, timeout=60.0)
                    if response.status_code == 200 and response.text.startswith("http"):
                        image_url = response.text.strip()
                        logging.info(f"catbox.moe public URL obtained: {image_url}")
                    else:
                        raise Exception(f"Catbox API returned {response.status_code}: {response.text}")
            except Exception as e:
                logging.error(f"Failed to upload to catbox.moe: {e}")
                raise InstagramPublishError(f"Local bypass upload failed: {e}")

        if not self.account_id or not self.access_token:
            raise InstagramAuthError("Missing INSTAGRAM_ACCOUNT_ID or META_ACCESS_TOKEN in config.")

        # Step A: Create media container
        create_url = f"{self.base_url}/{self.account_id}/media"
        create_payload = {
            "image_url": image_url,
            "caption": caption,
            "access_token": self.access_token
        }
        
        create_resp = httpx.post(create_url, data=create_payload, timeout=30.0)
        if create_resp.status_code != 200:
            self._handle_error(create_resp)
            
        creation_id = create_resp.json().get("id")
        if not creation_id:
            raise InstagramPublishError("Failed to get creation_id from media endpoint.")
            
        # Step B: Wait for container to be ready
        status_url = f"{self.base_url}/{creation_id}"
        status_params = {
            "fields": "status_code",
            "access_token": self.access_token
        }
        
        ready = False
        for attempt in range(10):
            status_resp = httpx.get(status_url, params=status_params, timeout=30.0)
            if status_resp.status_code != 200:
                self._handle_error(status_resp)
                
            status_code = status_resp.json().get("status_code")
            if status_code == "FINISHED":
                ready = True
                break
            elif status_code == "ERROR":
                raise InstagramPublishError(f"Media container failed processing: {status_resp.json()}")
                
            time.sleep(3)
            
        if not ready:
            raise InstagramPublishError(f"Media container {creation_id} did not reach FINISHED status in time.")
            
        # Step C: Publish the container
        publish_url = f"{self.base_url}/{self.account_id}/media_publish"
        publish_payload = {
            "creation_id": creation_id,
            "access_token": self.access_token
        }
        
        publish_resp = httpx.post(publish_url, data=publish_payload, timeout=30.0)
        if publish_resp.status_code != 200:
            self._handle_error(publish_resp)
            
        media_id = publish_resp.json().get("id")
        if not media_id:
            raise InstagramPublishError("Failed to get published media ID.")
            
        logging.info(f"Instagram post published: https://www.instagram.com/p/{media_id}")
        return {"instagram_media_id": media_id}
