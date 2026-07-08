import logging
from fastapi import APIRouter, Request, Response, HTTPException, BackgroundTasks
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.signature import SignatureVerifier
import json
from config import settings

from nodes.node7_instagram import InstagramPublisher, InstagramPublishError

router = APIRouter()
slack_client = WebClient(token=settings.SLACK_BOT_TOKEN)
signature_verifier = SignatureVerifier(settings.SLACK_SIGNING_SECRET) if settings.SLACK_SIGNING_SECRET else None

instagram = InstagramPublisher()

def process_approval(action_id, blocks, channel_id, message_ts, meme_id, image_url, tweet_text, link, title, local_path=None):
    if action_id == "approve_post":
        logging.info(f"APPROVED {meme_id} — ready to post to Instagram")
        caption = f"{tweet_text}\n\n🗞️ {title}\n🔗 {link}\n\n#meme #tech #AI #developer"
        try:
            instagram.publish_image(image_url=image_url, caption=caption, local_path=local_path)
            blocks[-1] = {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "✅ *Posted to Instagram*"}
            }
        except InstagramPublishError as e:
            logging.error(f"Failed to post to Instagram: {e}")
            blocks[-1] = {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"❌ *Instagram Error: {e}*"}
            }
        except Exception as e:
            logging.error(f"Unexpected error posting to Instagram: {e}")
            blocks[-1] = {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "❌ *Instagram Error*"}
            }
    elif action_id == "reject_post":
        logging.info(f"REJECTED {meme_id} — meme discarded")
        blocks[-1] = {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "❌ *Rejected*"}
        }
        
    try:
        slack_client.chat_update(
            channel=channel_id,
            ts=message_ts,
            text="Meme reviewed",
            blocks=blocks
        )
    except SlackApiError as e:
        logging.error(f"Error updating Slack message: {e}")

@router.post("/slack/actions")
async def slack_actions(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.body()
        if signature_verifier and not signature_verifier.is_valid_request(body, request.headers):
            raise HTTPException(status_code=403, detail="invalid signature")
            
        form_data = await request.form()
        payload_str = form_data.get("payload")
        if not payload_str:
            raise HTTPException(status_code=400, detail="No payload")
            
        payload = json.loads(payload_str)
        
        if payload.get("type") == "block_actions":
            action = payload["actions"][0]
            action_id = action.get("action_id")
            channel_id = payload["channel"]["id"]
            message_ts = payload["message"]["ts"]
            blocks = payload["message"]["blocks"]
            
            if action_id in ("approve_post", "reject_post"):
                val_str = action.get("value", "{}")
                try:
                    val_data = json.loads(val_str)
                    meme_id = val_data.get("id", "unknown")
                    image_url = val_data.get("url", "")
                    link = val_data.get("link", "")
                    title = val_data.get("title", "")
                    local_path = val_data.get("path", "")
                except Exception:
                    meme_id = val_str
                    image_url = ""
                    link = ""
                    title = ""
                    local_path = ""
                    
                tweet_text = ""
                for block in blocks:
                    if block["type"] == "section" and "text" in block and block["text"].get("text", "").startswith("```"):
                        tweet_text = block["text"]["text"].replace("```", "").strip()
                        
                background_tasks.add_task(
                    process_approval,
                    action_id,
                    blocks,
                    channel_id,
                    message_ts,
                    meme_id,
                    image_url,
                    tweet_text,
                    link,
                    title,
                    local_path
                )
                
        return Response(status_code=200)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logging.error(f"slack_actions error: {traceback.format_exc()}")
        return Response(content=str(e), status_code=500)

class SlackHITL:
    def __init__(self):
        self.client = slack_client
        self.channel_id = settings.SLACK_CHANNEL_ID

    def send_for_approval(self, payload):
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🔥 New Meme Ready for Review", "emoji": True}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"```{payload['tweet_text']}```"}
            }
        ]
        
        image_url = payload.get("image_url", "")
        # ALWAYS bypass Slack's image URL block. Slack is too strict about downloading from tunnels.
        # We will upload the file natively and pass the URL to Instagram via the button value!
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "🖼️ Image generated — see attached file below."
            }
        })
            
        import json
        btn_value = json.dumps({
            "id": payload.get("id", "unknown"), 
            "url": image_url,
            "path": payload.get("local_path", ""),
            "link": payload.get("source_link", ""),
            "title": payload.get("source_title", "")
        })
            
        blocks.extend([
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"*Source:* {payload['source_title']}"}]
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Approve", "emoji": True},
                        "style": "primary",
                        "value": btn_value,
                        "action_id": "approve_post"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ Reject", "emoji": True},
                        "style": "danger",
                        "value": btn_value,
                        "action_id": "reject_post"
                    }
                ]
            }
        ])
        
        try:
            self.client.chat_postMessage(
                channel=self.channel_id,
                text="New meme for review",
                blocks=blocks
            )
            
            if payload.get("local_path"):
                self.client.files_upload_v2(
                    channel=self.channel_id,
                    file=payload["local_path"],
                    title="Generated Meme Image"
                )
        except SlackApiError as e:
            logging.error(f"Error sending to Slack: {e}")
