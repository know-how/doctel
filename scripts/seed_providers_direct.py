"""
Seed AI providers directly into the database.
This bypasses the HTTP API and writes directly to SQLite/Postgres.
"""

import sys, os, json, uuid
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text

PROVIDERS = [
    {
        "provider_id": "ollama",
        "name": "Ollama",
        "vendor": "ollama",
        "base_url": "http://localhost:11434/v1",
        "description": "Locally hosted models via Ollama",
        "status": "active",
        "visible_to_users": True,
        "icon": "cpu",
        "sort_order": 1,
        "provider_type": "openai",
        "models_endpoint": "http://localhost:11434/api/tags",
        "chat_endpoint": "",
        "health_endpoint": "http://localhost:11434/api/tags",
    },
    {
        "provider_id": "deepseek",
        "name": "DeepSeek",
        "vendor": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "description": "DeepSeek cloud API",
        "status": "active",
        "visible_to_users": True,
        "icon": "deepseek",
        "sort_order": 2,
        "provider_type": "openai",
    },
    {
        "provider_id": "opencode-zen",
        "name": "OpenCode Zen",
        "vendor": "opencode",
        "base_url": "https://opencode.ai/zen/v1",
        "description": "OpenCode Zen API",
        "status": "active",
        "visible_to_users": True,
        "icon": "opencode",
        "sort_order": 3,
        "provider_type": "openai",
    },
    {
        "provider_id": "opencode-go",
        "name": "OpenCode Go",
        "vendor": "opencode",
        "base_url": "https://opencode.ai/zen/go/v1",
        "description": "OpenCode Go API",
        "status": "active",
        "visible_to_users": True,
        "icon": "opencode",
        "sort_order": 4,
        "provider_type": "openai",
    },
    {
        "provider_id": "google-gemini",
        "name": "Google Gemini",
        "vendor": "google",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "description": "Google Gemini models",
        "status": "active",
        "visible_to_users": True,
        "icon": "gemini",
        "sort_order": 5,
        "provider_type": "gemini",
    },
    {
        "provider_id": "openai",
        "name": "OpenAI",
        "vendor": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "description": "OpenAI cloud API",
        "status": "active",
        "visible_to_users": True,
        "icon": "openai",
        "sort_order": 6,
        "provider_type": "openai",
    },
]

# Cloud model definitions (these are well-known models that should always be available)
CLOUD_MODELS = {
    "deepseek": [
        {"model_id": "deepseek-chat", "display_name": "DeepSeek Chat", "state": "active", "supports_chat": True, "supports_reasoning": True, "context_window": 65536},
        {"model_id": "deepseek-reasoner", "display_name": "DeepSeek Reasoner", "state": "active", "supports_chat": True, "supports_reasoning": True, "context_window": 65536},
        {"model_id": "deepseek-v4-flash:cloud", "display_name": "DeepSeek V4 Flash", "state": "active", "supports_chat": True, "supports_reasoning": True, "context_window": 131072},
    ],
    "opencode-zen": [
        {"model_id": "zen/deepseek-v4-flash", "display_name": "DeepSeek V4 Flash (Zen)", "state": "active", "supports_chat": True, "supports_reasoning": True, "context_window": 131072},
    ],
    "opencode-go": [
        {"model_id": "go/deepseek-v4-flash", "display_name": "DeepSeek V4 Flash (Go)", "state": "active", "supports_chat": True, "supports_reasoning": True, "context_window": 131072},
    ],
    "google-gemini": [
        {"model_id": "gemini-2.5-pro", "display_name": "Gemini 2.5 Pro", "state": "active", "supports_chat": True, "supports_reasoning": True, "supports_vision": True, "context_window": 1048576},
        {"model_id": "gemini-2.0-flash", "display_name": "Gemini 2.0 Flash", "state": "active", "supports_chat": True, "supports_vision": True, "context_window": 1048576},
        {"model_id": "gemini-1.5-pro", "display_name": "Gemini 1.5 Pro", "state": "active", "supports_chat": True, "supports_reasoning": True, "supports_vision": True, "context_window": 1048576},
        {"model_id": "gemini-1.5-flash", "display_name": "Gemini 1.5 Flash", "state": "active", "supports_chat": True, "supports_vision": True, "context_window": 1048576},
        {"model_id": "text-embedding-004", "display_name": "Text Embedding", "state": "active", "supports_embedding": True, "context_window": 2048},
    ],
    "openai": [
        {"model_id": "gpt-4o", "display_name": "GPT-4o", "state": "active", "supports_chat": True, "supports_vision": True, "supports_reasoning": True, "context_window": 128000},
        {"model_id": "gpt-4o-mini", "display_name": "GPT-4o Mini", "state": "active", "supports_chat": True, "supports_vision": True, "context_window": 128000},
        {"model_id": "gpt-4-turbo", "display_name": "GPT-4 Turbo", "state": "active", "supports_chat": True, "supports_vision": True, "context_window": 128000},
        {"model_id": "text-embedding-3-large", "display_name": "Text Embedding 3 Large", "state": "active", "supports_embedding": True, "context_window": 8191},
        {"model_id": "text-embedding-3-small", "display_name": "Text Embedding 3 Small", "state": "active", "supports_embedding": True, "context_window": 8191},
    ],
}


async def main():
    # Read database URL from config
    from app.config import settings
    db_url = settings.database_url or ""

    if not db_url:
        print("No database_url found in config!")
        return

    print(f"Database URL: {db_url[:50]}...")

    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        # Check existing providers
        result = await session.execute(text("SELECT provider_id FROM ai_providers"))
        existing = {row[0] for row in result.fetchall()}
        print(f"Existing providers: {len(existing)}")

        # Add providers
        for prov in PROVIDERS:
            if prov["provider_id"] in existing:
                print(f"SKIP {prov['name']} (exists)")
                continue

            cols = ", ".join(prov.keys())
            placeholders = ", ".join([f":{k}" for k in prov.keys()])
            await session.execute(
                text(f"INSERT INTO ai_providers ({cols}) VALUES ({placeholders})"),
                prov
            )
            print(f"ADDED {prov['name']}")
            existing.add(prov["provider_id"])

        # Get provider internal IDs
        for prov in PROVIDERS:
            result = await session.execute(
                text("SELECT id FROM ai_providers WHERE provider_id = :pid"),
                {"pid": prov["provider_id"]}
            )
            row = result.fetchone()
            if row:
                prov["_pk"] = row[0]

        # Add cloud models
        for pid, models in CLOUD_MODELS.items():
            pk = None
            for p in PROVIDERS:
                if p["provider_id"] == pid:
                    pk = p.get("_pk")
                    break
            if not pk:
                print(f"SKIP models for {pid} (provider not found)")
                continue

            result = await session.execute(
                text("SELECT model_id FROM ai_models WHERE provider_id = :pk"),
                {"pk": pk}
            )
            existing_models = {row[0] for row in result.fetchall()}

            for model in models:
                if model["model_id"] in existing_models:
                    continue

                model_data = {
                    "provider_id": pk,
                    "model_id": model["model_id"],
                    "display_name": model["display_name"],
                    "state": model.get("state", "active"),
                    "context_window": model.get("context_window", 4096),
                    "supports_chat": model.get("supports_chat", False),
                    "supports_vision": model.get("supports_vision", False),
                    "supports_code": model.get("supports_code", False),
                    "supports_embedding": model.get("supports_embedding", False),
                    "supports_reasoning": model.get("supports_reasoning", False),
                    "supports_tools": model.get("supports_tools", False),
                    "supports_rag": model.get("supports_rag", False),
                    "visible_to_users": True,
                    "pricing_tier": "cloud",
                    "allowed_roles": "[]",
                    "department_restrictions": "[]",
                    "for_tasks": "[]",
                }
                cols = ", ".join(model_data.keys())
                placeholders = ", ".join([f":{k}" for k in model_data.keys()])
                await session.execute(
                    text(f"INSERT INTO ai_models ({cols}) VALUES ({placeholders})"),
                    model_data
                )
                print(f"  MODEL {model['model_id']} added")

        await session.commit()

    # Show final state
    async with session_factory() as session:
        result = await session.execute(text("""
            SELECT p.name, p.provider_id, COUNT(m.id) as model_count
            FROM ai_providers p
            LEFT JOIN ai_models m ON m.provider_id = p.id
            GROUP BY p.id, p.name
            ORDER BY p.sort_order
        """))
        rows = result.fetchall()
        total = 0
        for name, pid, cnt in rows:
            total += cnt
            print(f"  {name} ({pid}): {cnt} models")
        print(f"\nTotal: {total} models")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
