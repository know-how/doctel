"""
web_search_service.py – Internet fallback using DuckDuckGo search.

When local model + Ollama + cloud teacher all fail or are unavailable,
Doctel routes the query here. Results are fetched, summarised with the
local Ollama model, and saved to training_room/web_samples/ for later
fine-tuning.

No API key required (uses DuckDuckGo HTML search via httpx).
Falls back gracefully if duckduckgo-search package is not installed.
"""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_WEB_SEARCH_ENABLED = os.getenv("DOCTEL_WEB_SEARCH_ENABLED", "true").lower() == "true"
_MAX_RESULTS = int(os.getenv("DOCTEL_WEB_SEARCH_MAX_RESULTS", "3"))
_SUMMARY_MAX_CHARS = 3000


def is_enabled() -> bool:
    return _WEB_SEARCH_ENABLED


async def _ddg_search(query: str, max_results: int = 3) -> list[dict]:
    """
    Fetch DuckDuckGo results. Tries the duckduckgo-search package first,
    then falls back to a simple HTML scrape.
    """
    results = []
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({"title": r.get("title", ""), "snippet": r.get("body", ""), "url": r.get("href", "")})
        return results
    except ImportError:
        pass
    except Exception as e:
        logger.warning("DDGS library search failed: %s", e)

    # Fallback: simple DuckDuckGo instant answer API
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
                headers={"User-Agent": "Doctel/1.0"},
            )
            if resp.status_code == 200:
                data = resp.json()
                abstract = data.get("AbstractText", "")
                url = data.get("AbstractURL", "")
                if abstract:
                    results.append({"title": data.get("Heading", query), "snippet": abstract, "url": url})
    except Exception as e:
        logger.warning("DuckDuckGo instant API failed: %s", e)

    return results


async def _summarise_with_ollama(query: str, context: str, ollama_base_url: str, model: str) -> str:
    """Ask the local Ollama model to summarise web findings."""
    prompt = (
        f"Based on the following web search results for the query: '{query}'\n\n"
        f"{context}\n\n"
        "Please provide a concise, accurate summary of the most relevant information."
    )
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{ollama_base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
    except Exception as e:
        logger.warning("Ollama summarisation failed: %s", e)
        return context[:_SUMMARY_MAX_CHARS]


async def _save_web_sample(query: str, answer: str, results: list[dict], web_samples_dir: Path) -> None:
    """Persist web search results as training data."""
    web_samples_dir.mkdir(parents=True, exist_ok=True)
    ts_date = datetime.now(timezone.utc).strftime("%Y%m%d")
    sample_file = web_samples_dir / f"web_{ts_date}.jsonl"
    record = {
        "prompt": query,
        "completion": answer,
        "source": "web_search",
        "web_results": results,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with open(sample_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning("Failed to save web sample: %s", e)


async def search_and_summarise(
    query: str,
    ollama_base_url: str,
    model: str,
    web_samples_dir: Optional[Path] = None,
) -> Optional[str]:
    """
    Public entry point: search DuckDuckGo, summarise with local Ollama,
    save to training data, return summary or None on failure.
    """
    if not _WEB_SEARCH_ENABLED:
        logger.debug("Web search disabled")
        return None

    logger.info("Web search fallback triggered for query: %s", query[:80])
    results = await _ddg_search(query, max_results=_MAX_RESULTS)
    if not results:
        logger.warning("No web results found for: %s", query[:80])
        return None

    context = "\n\n".join(
        f"[{i+1}] {r['title']}\n{r['snippet']}\n{r['url']}"
        for i, r in enumerate(results)
    )[:_SUMMARY_MAX_CHARS]

    summary = await _summarise_with_ollama(query, context, ollama_base_url, model)
    if not summary:
        return None

    if web_samples_dir:
        await _save_web_sample(query, summary, results, web_samples_dir)

    return summary
