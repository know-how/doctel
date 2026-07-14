"""
provider_monitor_service.py — Background provider health monitoring

Periodically checks provider connectivity and updates status.
Runs as a background task scheduled at application startup.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.services.config_service import (
    get_all_providers,
    update_provider_status,
    add_health_record,
)
from app.services.model_management_service import test_provider_connection

logger = logging.getLogger(__name__)

# Global flag to control the monitor loop
_monitor_running = False
_monitor_task: Optional[asyncio.Task] = None


async def check_provider_health(provider_id: str, provider_dict: dict) -> dict:
    """Check health of a single provider and update its status.
    
    Args:
        provider_id: The provider's string ID
        provider_dict: Provider data including endpoints and API key info
        
    Returns:
        Dict with check results
    """
    base_url = provider_dict.get("base_url", "")
    models_endpoint = provider_dict.get("modelsEndpoint") or provider_dict.get("models_endpoint")
    chat_endpoint = provider_dict.get("chatEndpoint") or provider_dict.get("chat_endpoint")
    messages_endpoint = provider_dict.get("messagesEndpoint") or provider_dict.get("messages_endpoint")
    api_key_value = provider_dict.get("api_key_value", "")
    
    # Use API key from database
    api_key = api_key_value or None
    
    try:
        result = await test_provider_connection(
            base_url=base_url,
            api_key=api_key,
            models_endpoint=models_endpoint,
            chat_endpoint=chat_endpoint,
            messages_endpoint=messages_endpoint,
        )
        
        return {
            "providerId": provider_id,
            "success": result.get("success", False),
            "latencyMs": result.get("latencyMs", 0),
            "message": result.get("message", ""),
            "endpoints": result.get("endpoints", {}),
        }
    except Exception as e:
        logger.error(f"Health check failed for {provider_id}: {e}")
        return {
            "providerId": provider_id,
            "success": False,
            "latencyMs": 0,
            "message": str(e),
            "endpoints": {},
        }


async def run_health_checks():
    """Run health checks for all providers and update database."""
    async with AsyncSessionLocal() as db:
        try:
            providers = await get_all_providers(db)
            logger.info(f"Running health checks for {len(providers)} providers")
            
            for prov in providers:
                provider_id = prov.provider_id
                provider_dict = {
                    "base_url": prov.base_url,
                    "models_endpoint": prov.models_endpoint,
                    "chat_endpoint": prov.chat_endpoint,
                    "messages_endpoint": prov.messages_endpoint,
                    "api_key_value": prov.api_key_value,
                }
                
                # Perform health check
                result = await check_provider_health(provider_id, provider_dict)
                
                # Update provider status
                status = "CONNECTED" if result["success"] else "DISCONNECTED"
                await update_provider_status(
                    db=db,
                    provider_id=provider_id,
                    status=status,
                    is_connected=result["success"],
                )
                
                # Record health check
                await add_health_record(
                    db=db,
                    provider_id=provider_id,
                    latency_ms=result["latencyMs"],
                    success=result["success"],
                    error_message=result["message"] if not result["success"] else "",
                )
                
                logger.debug(
                    f"Provider {provider_id}: {status} ({result['latencyMs']}ms)"
                )
                
        except Exception as e:
            logger.error(f"Error in health check cycle: {e}")


async def monitor_loop(interval_minutes: int = 5):
    """Background loop that periodically checks provider health.
    
    Args:
        interval_minutes: Minutes between health check cycles (default: 5)
    """
    global _monitor_running
    
    logger.info(f"Starting provider monitor (interval: {interval_minutes} minutes)")
    
    while _monitor_running:
        try:
            await run_health_checks()
        except Exception as e:
            logger.error(f"Error in monitor loop: {e}")
        
        # Wait for next cycle
        await asyncio.sleep(interval_minutes * 60)
    
    logger.info("Provider monitor stopped")


def start_provider_monitor(interval_minutes: int = 5) -> bool:
    """Start the provider health monitor background task.
    
    Args:
        interval_minutes: Minutes between health check cycles
        
    Returns:
        True if started successfully, False if already running
    """
    global _monitor_running, _monitor_task
    
    if _monitor_running:
        logger.warning("Provider monitor already running")
        return False
    
    _monitor_running = True
    _monitor_task = asyncio.create_task(monitor_loop(interval_minutes))
    logger.info("Provider monitor started")
    return True


def stop_provider_monitor() -> bool:
    """Stop the provider health monitor.
    
    Returns:
        True if stopped successfully, False if not running
    """
    global _monitor_running, _monitor_task
    
    if not _monitor_running:
        logger.warning("Provider monitor not running")
        return False
    
    _monitor_running = False
    if _monitor_task:
        _monitor_task.cancel()
        _monitor_task = None
    
    logger.info("Provider monitor stopping...")
    return True


def is_monitor_running() -> bool:
    """Check if the provider monitor is currently running."""
    return _monitor_running


async def get_provider_health_summary():
    """Get current health summary for all providers.
    
    Returns:
        Dict mapping provider_id to health status
    """
    async with AsyncSessionLocal() as db:
        from app.services.config_service import get_health_summary
        return await get_health_summary(db)
