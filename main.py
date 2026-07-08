import asyncio
import logging
import os
import uuid
import base64
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles


from config import settings
import database
from nodes import node1_ingestor
from nodes.node2_bouncer import BounceFilter
from nodes.node3_brain import BrainNode
from nodes.node4_image import ImageNode
from nodes.node5_assembler import assemble_payload
from nodes.node6_slack import SlackHITL, router as slack_router
from nodes.compositor import MemeCompositor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Instantiate nodes
bouncer = BounceFilter()
brain = BrainNode()
image_gen = ImageNode()
slack = SlackHITL()
compositor = MemeCompositor()

last_demo_time = 0.0

def _composite_and_notify(image_prompt: str, tweet_text: str, trend: dict):
    image_url = None
    local_path = None
    data_url = None
    try:
        img_result = image_gen.generate_image(image_prompt)
        image_url = img_result.get("image_url")
        local_path = img_result.get("local_path")
        data_url = img_result.get("data_url")
    except Exception as img_err:
        logging.error(f"Image generation error: {img_err}")

    if local_path and tweet_text:
        try:
            composited_img = compositor.add_text_to_image(local_path, tweet_text)
            if composited_img.mode in ("RGBA", "P"):
                composited_img = composited_img.convert("RGB")
            new_local_path = local_path.rsplit(".", 1)[0] + ".jpg"
            composited_img.save(new_local_path, format="JPEG", quality=90)
            if os.path.exists(local_path):
                os.remove(local_path)
            local_path = new_local_path
            if image_url:
                image_url = image_url.rsplit(".", 1)[0] + ".jpg"
            with open(local_path, "rb") as f:
                updated_b64 = base64.b64encode(f.read()).decode("utf-8")
                data_url = f"data:image/jpeg;base64,{updated_b64}"
        except Exception as comp_err:
            logging.error(f"Compositor failed, using raw image: {comp_err}")

    payload = assemble_payload(tweet_text=tweet_text, image_url=image_url, trend=trend)
    payload["id"] = str(uuid.uuid4())
    if local_path:
        payload["local_path"] = local_path
    if data_url:
        payload["data_url"] = data_url
    if not image_url:
        logging.warning(f"Skipping Slack notification — no image for: {trend.get('title')}")
        return
    slack.send_for_approval(payload)

def run_pipeline(trend: dict):
    """
    Synchronous function processing a trend through Nodes 2-6.
    Runs inside a thread.
    """
    try:
        # Pipeline Sequence:
        # 1. bouncer.check_relevance(trend)
        # 2. brain.generate(trend) -> {tweet_text, image_prompt}
        # 3. image_gen.generate_image(image_prompt) -> {image_url, local_path, data_url}
        # 4. compositor.add_text_to_image(local_path, tweet_text)
        # 5. assemble_payload(...)
        # 6. slack.send_for_approval(payload)

        is_relevant = bouncer.check_relevance(trend)
        if not is_relevant:
            return

        brain_result = brain.generate(trend)
        
        _composite_and_notify(
            image_prompt=brain_result.get("image_prompt"),
            tweet_text=brain_result.get("tweet_text"),
            trend=trend
        )
        
    except Exception as e:
        logging.error(f"Error processing trend '{trend.get('title')}': {e}")

async def polling_loop():
    while True:
        logging.info("Polling RSS feeds...")
        try:
            async for trend in node1_ingestor.fetch_trends():
                await asyncio.to_thread(run_pipeline, trend)
        except Exception as e:
            logging.error(f"Polling loop error: {e}")
            
        logging.info(f"Sleeping for {settings.POLL_INTERVAL} seconds...")
        await asyncio.sleep(settings.POLL_INTERVAL)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    task = asyncio.create_task(polling_loop())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)
app.include_router(slack_router)

os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_images"), exist_ok=True)
app.mount("/images", StaticFiles(directory=os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_images")), name="images")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/api/v1/run-demo")
async def run_demo():
    global last_demo_time
    if not settings.DEMO_MODE:
        raise HTTPException(status_code=403, detail="DEMO_MODE is not enabled")
        
    current_time = time.time()
    elapsed = current_time - last_demo_time
    if elapsed < 60:
        raise HTTPException(status_code=429, detail=f"Demo cooldown active. Try again in {int(60 - elapsed)} seconds.")
        
    last_demo_time = current_time
        
    fake_trend = {
        "title": "Developers invent AI that writes commit messages for them",
        "link": "https://example.com/ai-commit-messages"
    }
    
    mock_brain = {
        "tweet_text": "Me when the AI perfectly summarizes my 50 file spaghetti code refactor in one sentence. 🍝🤖",
        "image_prompt": "A digital art illustration of a happy programmer looking at a glowing computer screen, with a robot assistant giving a thumbs up. Bright, vibrant colors, vector art style."
    }
    
    async def run_mock_pipeline():
        try:
            _composite_and_notify(
                image_prompt=mock_brain["image_prompt"],
                tweet_text=mock_brain["tweet_text"],
                trend=fake_trend
            )
        except Exception as e:
            logging.error(f"Demo mock error: {e}")

    asyncio.create_task(run_mock_pipeline())
    return {"status": "Mock pipeline triggered without hitting Groq limits! Check Slack."}
