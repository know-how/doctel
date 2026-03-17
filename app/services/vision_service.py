import base64
import httpx
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

async def analyze_image(image_path: str, user_question: str) -> str:
    # 1. Encode image to base64
    try:
        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        logger.error(f"Error encoding image to base64: {e}")
        return f"Error: {e}"
        
    # 2. Call Ollama with Vision model
    url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
    payload = {
        "model": settings.vision_model,
        "prompt": user_question,
        "images": [image_base64],
        "stream": False
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json().get("response", "")
        except Exception as e:
            logger.error(f"Vision analysis error: {e}")
            return f"Error during vision analysis: {e}"
