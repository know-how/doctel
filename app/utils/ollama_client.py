import httpx
import json
import logging
import asyncio
from app.config import settings

logger = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self):
        self.base_url = settings.ollama_base_url.rstrip("/")
        self._retry_delays = (0.0, 0.5, 1.0, 2.0, 4.0)

    def _timeout(self, read_seconds: float) -> httpx.Timeout:
        return httpx.Timeout(timeout=read_seconds + 5.0, connect=2.0, read=read_seconds)

    async def _post_with_retries(self, url: str, payload: dict, timeout: httpx.Timeout) -> httpx.Response:
        last_exc = None
        for delay in self._retry_delays:
            if delay:
                await asyncio.sleep(delay)
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url, json=payload)
                    if response.status_code >= 400:
                        # HTTP errors are definitive — don't retry, surface immediately
                        response.raise_for_status()
                    return response
            except httpx.HTTPStatusError:
                raise  # surface 4xx/5xx immediately, no retry
            except Exception as e:
                last_exc = e
        raise last_exc  # type: ignore[misc]

    async def _get_with_retries(self, url: str, timeout: httpx.Timeout) -> httpx.Response:
        last_exc = None
        for delay in self._retry_delays:
            if delay:
                await asyncio.sleep(delay)
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    return response
            except Exception as e:
                last_exc = e
        raise last_exc  # type: ignore[misc]

    async def generate(self, model: str, prompt: str, system: str = None, options: dict = None) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        if system:
            payload["system"] = system
        # Merge caller options; always set num_ctx to prevent OOM on large prompts
        merged_options = {"num_ctx": 4096}
        if options:
            merged_options.update(options)
        payload["options"] = merged_options

        timeout = self._timeout(read_seconds=180.0)  # analysis can take up to 3 min on CPU
        try:
            response = await self._post_with_retries(url, payload, timeout)
            return response.json().get("response", "")
        except Exception as e:
            logger.error(f"Ollama generate error: {e}")
            raise

    @staticmethod
    def _extract_embedding(body: dict) -> list[float]:
        embedding = []
        if "embedding" in body:
            embedding = body.get("embedding", [])
        elif "embeddings" in body and isinstance(body["embeddings"], list) and body["embeddings"]:
            embedding = body["embeddings"][0] or []
        elif "data" in body and isinstance(body["data"], list) and body["data"]:
            embedding = body["data"][0].get("embedding", [])
        return embedding if isinstance(embedding, list) else []

    async def embed(self, model: str, input: str) -> list[float]:
        payload = {
            "model": model,
            "input": input
        }
        timeout = self._timeout(read_seconds=30.0)
        try:
            for endpoint in ("/api/embeddings", "/api/embed"):
                response = await self._post_with_retries(f"{self.base_url}{endpoint}", payload, timeout)
                embedding = self._extract_embedding(response.json())
                if embedding:
                    return embedding
            raise RuntimeError(
                f"Ollama returned empty embedding for model {model} on /api/embeddings and /api/embed"
            )
        except Exception as e:
            logger.error(f"Ollama embedding error: {e}")
            raise

    async def list_models(self) -> list[str]:
        url = f"{self.base_url}/api/tags"
        timeout = self._timeout(read_seconds=3.0)
        response = await self._get_with_retries(url, timeout)
        models = response.json().get("models", [])
        return [m["name"] for m in models]

    async def show(self, model: str) -> dict:
        url = f"{self.base_url}/api/show"
        timeout = self._timeout(read_seconds=10.0)
        response = await self._post_with_retries(url, {"name": model}, timeout)
        return response.json()

    async def pull_stream(self, model: str, resume: bool = True):
        url = f"{self.base_url}/api/pull"
        payload = {"name": model, "stream": True}
        if resume:
            payload["resume"] = True
        timeout = self._timeout(read_seconds=90.0)
        last_exc = None
        for delay in self._retry_delays:
            if delay:
                await asyncio.sleep(delay)
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream("POST", url, json=payload) as r:
                        r.raise_for_status()
                        async for line in r.aiter_lines():
                            if line is None:
                                continue
                            txt = str(line).strip()
                            if not txt:
                                continue
                            yield txt
                return
            except Exception as e:
                last_exc = e
        raise last_exc  # type: ignore[misc]

ollama = OllamaClient()
