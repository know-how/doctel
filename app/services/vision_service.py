import base64
import httpx
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

async def analyze_image(image_path: str, user_question: str) -> str:
    # 1. Try Ollama with vision model
    try:
        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        logger.error(f"Error encoding image to base64: {e}")
        return f"Error: {e}"

    # Try Ollama
    if settings.vision_model:
        url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
        payload = {
            "model": settings.vision_model,
            "prompt": user_question,
            "images": [image_base64],
            "stream": False
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                text = response.json().get("response", "").strip()
                if text:
                    return text
        except Exception as e:
            logger.warning("Ollama vision failed (%s); trying Gemini", e)

    # 2. Fallback to Gemini API (supports vision natively)
    try:
        from app.services.gemini_service import analyze_image as gemini_analyze, is_configured
        if is_configured():
            result = await gemini_analyze(image_path, user_question)
            return result
    except Exception as e:
        logger.warning("Gemini vision fallback failed (%s)", e)

    # 3. Fallback to DeepSeek/Zen API text-only (describe the image)
    fallback_prompt = (
        f"The user uploaded an image and asked: {user_question}\n"
        "Since I cannot directly view images, answer based on general knowledge."
    )
    try:
        from app.services.opencode_zen_service import is_configured as zen_cfg, generate as zen_gen
        if zen_cfg():
            return await zen_gen(fallback_prompt)
    except Exception as e:
        logger.warning("Zen vision fallback failed (%s)", e)

    try:
        from app.services.deepseek_service import is_configured as ds_cfg, generate as ds_gen
        if ds_cfg():
            return await ds_gen(fallback_prompt)
    except Exception as e:
        logger.warning("DeepSeek vision fallback failed (%s)", e)

    return "I could not analyze the image. Please check that a vision model (e.g. llava:7b) is installed in Ollama or a cloud API key (Gemini) is configured."
