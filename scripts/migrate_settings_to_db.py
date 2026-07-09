"""
migrate_settings_to_db.py — Migrate current settings to database

Migrates configuration from environment variables and config.yaml
to the SystemConfig table for centralized management.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal, init_db
from app.services import app_config_service as app_cfg
from app.config import settings


async def migrate_settings():
    """Migrate current settings to database."""
    print("=== DocTel Settings Migration to Database ===")
    print()
    
    # Initialize database
    await init_db()
    
    async with AsyncSessionLocal() as db:
        migrated = []
        skipped = []
        
        # Define settings to migrate (key, current_value, should_migrate_if_blank)
        settings_to_migrate = [
            # Core
            ("app.base_dir", settings.base_dir, False),
            ("app.environment", settings.environment, False),
            ("app.offline_only", settings.offline_only, False),
            ("app.bind_host", settings.bind_host, False),
            ("app.port", settings.port, False),
            
            # Ollama
            ("ollama.text_model", settings.text_model, False),
            ("ollama.fallback_text_model", settings.fallback_text_model, False),
            ("ollama.vision_model", settings.vision_model, False),
            ("ollama.embed_model", settings.embed_model, False),
            ("ollama.base_url", settings.ollama_base_url, False),
            
            # External APIs
            ("api.gemini_api_key", settings.gemini_api_key, True),
            ("api.gemini_model", settings.gemini_model, False),
            ("api.deepseek_api_key", settings.deepseek_api_key, True),
            ("api.deepseek_model", settings.deepseek_model, False),
            ("api.deepseek_base_url", settings.deepseek_base_url, False),
            ("api.opencode_go_api_key", settings.opencode_go_api_key, True),
            ("api.opencode_zen_api_key", settings.opencode_zen_api_key, True),
            
            # Routing
            ("routing.default_model", settings.default_model, True),
            ("routing.automatic_switching", settings.automatic_switching, False),
            ("routing.enable_qwen_9b", settings.enable_qwen_9b, False),
            ("routing.qwen_9b_model", settings.qwen_9b_model, False),
            
            # RAG
            ("rag.max_context_tokens", settings.max_context_tokens, False),
            ("rag.chunk_size", settings.chunk_size, False),
            ("rag.chunk_overlap", settings.chunk_overlap, False),
            ("rag.top_k", settings.top_k, False),
            
            # Auth
            ("auth.allowed_email_domain", settings.allowed_email_domain, False),
            ("auth.ad_url", settings.ad_url, True),
            ("auth.ad_domain", settings.ad_domain, True),
            ("auth.ad_base_dn", settings.ad_base_dn, True),
            ("auth.ad_use_tls", settings.ad_use_tls, False),
            
            # Email
            ("email.server_url", settings.email_server_url, True),
            ("email.server_endpoint", settings.email_server_endpoint, False),
            ("email.sender_email", settings.email_sender_email, True),
            ("email.sender_password", settings.email_sender_password, True),
            ("email.smtp_host", settings.smtp_host, True),
            ("email.smtp_port", settings.smtp_port, False),
            ("email.smtp_user", settings.smtp_user, True),
            ("email.smtp_pass", settings.smtp_pass, True),
            ("email.smtp_use_tls", settings.smtp_use_tls, False),
        ]
        
        for key, value, allow_blank in settings_to_migrate:
            # Skip empty values unless explicitly allowed
            if not allow_blank and (value is None or value == "" or value == []):
                skipped.append(key)
                continue
            
            # Skip empty strings even if allowed (they can be set later)
            if value is None or value == "":
                skipped.append(key)
                continue
            
            try:
                # Check if already exists in DB
                existing = await app_cfg.get_setting(db, key, None)
                if existing is not None:
                    print(f"[SKIP] {key}: already in database")
                    skipped.append(key)
                    continue
                
                # Set in DB
                schema = app_cfg.get_setting_schema()
                meta = schema.get(key, {})
                description = meta.get("description", "")
                
                await app_cfg.set_setting(db, key, value, description)
                print(f"[OK] {key} = {value if 'secret' not in key else '***'}")
                migrated.append(key)
                
            except Exception as e:
                print(f"[ERROR] {key}: {e}")
                skipped.append(key)
        
        await db.commit()
        
        print()
        print("=" * 50)
        print(f"Migration complete: {len(migrated)} migrated, {len(skipped)} skipped")
        print()
        
        if migrated:
            print("Migrated settings:")
            for key in migrated:
                print(f"  - {key}")
        
        if skipped:
            print()
            print("Skipped settings (already exist or empty):")
            for key in skipped:
                print(f"  - {key}")
        
        print()
        print("These settings can now be managed via:")
        print("  - Admin UI: /admin/settings")
        print("  - API: GET/POST /api/admin/config/settings")


if __name__ == "__main__":
    asyncio.run(migrate_settings())
