"""
prompt_suggestions.py — Dynamic Prompt Suggestions API

Provides CRUD operations for managing prompt suggestions displayed on the New Chat page.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.routers.deps import get_db, require_role, User, JSONResponse
from app.db.config_models import PromptSuggestion

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prompt-suggestions", tags=["prompt-suggestions"])


@router.get("")
async def list_prompt_suggestions(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max records to return"),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_enabled: Optional[bool] = Query(None, description="Filter by enabled status (None = no filter)"),
    search: Optional[str] = Query(None, description="Search in title and prompt_text"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin", "user"])),
):
    """List prompt suggestions with optional filtering.

    Supports pagination (skip/limit), category filtering, enabled-status filtering,
    and full-text search across title and prompt_text.
    """
    # Base count query (for total)
    count_query = select(func.count(PromptSuggestion.id))
    
    # Base data query
    query = select(PromptSuggestion)
    
    # Apply filters
    if is_enabled is not None:
        query = query.where(PromptSuggestion.enabled == is_enabled)
        count_query = count_query.where(PromptSuggestion.enabled == is_enabled)
    if category:
        query = query.where(PromptSuggestion.category == category)
        count_query = count_query.where(PromptSuggestion.category == category)
    if search:
        search_filter = (
            PromptSuggestion.title.ilike(f"%{search}%") |
            PromptSuggestion.prompt_text.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply ordering, pagination
    query = query.order_by(PromptSuggestion.display_order, PromptSuggestion.id)
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    suggestions = result.scalars().all()
    
    return {
        "items": [s.to_dict() for s in suggestions],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/random")
async def get_random_prompt_suggestions(
    count: int = Query(4, ge=1, le=12),
    model_capabilities: Optional[List[str]] = Query(None, description="Filter by model capabilities"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin", "user"])),
):
    """Get random prompt suggestions for display on New Chat page.
    
    Returns a random selection of enabled suggestions, optionally filtered
    by model capabilities (e.g., vision, audio, code).
    """
    query = select(PromptSuggestion).where(PromptSuggestion.enabled == True)
    
    # Filter by capabilities if provided
    if model_capabilities:
        # Include suggestions that don't require any capability OR
        # suggestions that require a capability the model has
        capability_filter = (
            (PromptSuggestion.requires_capability.is_(None)) |
            (PromptSuggestion.requires_capability.in_(model_capabilities))
        )
        query = query.where(capability_filter)
    
    # Random ordering
    query = query.order_by(func.random()).limit(count)
    
    result = await db.execute(query)
    suggestions = result.scalars().all()
    
    return {
        "suggestions": [s.to_dict() for s in suggestions],
        "count": len(suggestions),
    }


@router.get("/categories")
async def get_prompt_categories(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin", "user"])),
):
    """Get all unique categories used for prompt suggestions."""
    result = await db.execute(
        select(PromptSuggestion.category)
        .where(PromptSuggestion.enabled == True)
        .distinct()
        .order_by(PromptSuggestion.category)
    )
    categories = [row[0] for row in result.all()]
    
    return {"categories": categories}


@router.post("")
async def create_prompt_suggestion(
    title: str = Body(..., min_length=1, max_length=255),
    prompt_text: str = Body(..., min_length=1),
    category: str = Body("general", max_length=64),
    icon: str = Body("💬", max_length=64),
    requires_capability: Optional[str] = Body(None, max_length=64),
    display_order: int = Body(0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Create a new prompt suggestion (admin only)."""
    suggestion = PromptSuggestion(
        title=title,
        prompt_text=prompt_text,
        category=category,
        icon=icon,
        requires_capability=requires_capability,
        display_order=display_order,
        enabled=True,
    )
    
    db.add(suggestion)
    await db.commit()
    await db.refresh(suggestion)
    
    logger.info(f"Created prompt suggestion: {title} (id={suggestion.id})")
    
    return {"suggestion": suggestion.to_dict(), "message": "Prompt suggestion created"}


@router.put("/{suggestion_id}")
async def update_prompt_suggestion(
    suggestion_id: int,
    title: Optional[str] = Body(None, max_length=255),
    prompt_text: Optional[str] = Body(None),
    category: Optional[str] = Body(None, max_length=64),
    icon: Optional[str] = Body(None, max_length=64),
    requires_capability: Optional[str] = Body(None),
    display_order: Optional[int] = Body(None),
    enabled: Optional[bool] = Body(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Update a prompt suggestion (admin only)."""
    result = await db.execute(
        select(PromptSuggestion).where(PromptSuggestion.id == suggestion_id)
    )
    suggestion = result.scalar_one_or_none()
    
    if not suggestion:
        return JSONResponse(
            status_code=404,
            content={"error": "Prompt suggestion not found"}
        )
    
    # Update fields
    if title is not None:
        suggestion.title = title
    if prompt_text is not None:
        suggestion.prompt_text = prompt_text
    if category is not None:
        suggestion.category = category
    if icon is not None:
        suggestion.icon = icon
    if requires_capability is not None:
        suggestion.requires_capability = requires_capability
    if display_order is not None:
        suggestion.display_order = display_order
    if enabled is not None:
        suggestion.enabled = enabled
    
    await db.commit()
    await db.refresh(suggestion)
    
    logger.info(f"Updated prompt suggestion: {suggestion.title} (id={suggestion.id})")
    
    return {"suggestion": suggestion.to_dict(), "message": "Prompt suggestion updated"}


@router.delete("/{suggestion_id}")
async def delete_prompt_suggestion(
    suggestion_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Delete a prompt suggestion (admin only)."""
    result = await db.execute(
        select(PromptSuggestion).where(PromptSuggestion.id == suggestion_id)
    )
    suggestion = result.scalar_one_or_none()
    
    if not suggestion:
        return JSONResponse(
            status_code=404,
            content={"error": "Prompt suggestion not found"}
        )
    
    await db.delete(suggestion)
    await db.commit()
    
    logger.info(f"Deleted prompt suggestion: {suggestion.title} (id={suggestion_id})")
    
    return {"message": "Prompt suggestion deleted"}


@router.post("/seed")
async def seed_default_prompt_suggestions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Seed default prompt suggestions if none exist (admin only)."""
    # Check if any suggestions exist
    result = await db.execute(select(func.count(PromptSuggestion.id)))
    count = result.scalar()
    
    if count > 0:
        return {"message": "Prompt suggestions already exist", "count": count}
    
    # Default suggestions
    defaults = [
        # Policy category
        {"title": "Explain ZETDC net metering policy", "prompt_text": "Explain the ZETDC net metering policy in detail. What are the requirements, benefits, and process for customers who want to install solar panels?", "category": "policy", "icon": "📋"},
        {"title": "What are customer connection requirements?", "prompt_text": "What are the requirements for a new customer to get electricity connection from ZETDC? List all necessary documents, fees, and steps.", "category": "policy", "icon": "📋"},
        {"title": "Explain billing categories", "prompt_text": "Explain the different ZETDC billing categories (domestic, commercial, industrial). What are the tariff rates and how is consumption calculated?", "category": "policy", "icon": "📋"},
        
        # Safety category
        {"title": "Summarize ZETDC safety procedures", "prompt_text": "Summarize the key ZETDC safety procedures for electrical work. Include lockout/tagout, PPE requirements, and working near live equipment.", "category": "safety", "icon": "🏗️"},
        {"title": "Explain lockout tagout process", "prompt_text": "Explain the ZETDC lockout/tagout (LOTO) process in detail. What are the steps, who is authorized, and what documentation is required?", "category": "safety", "icon": "🔒"},
        {"title": "Explain PPE requirements", "prompt_text": "What are the PPE requirements for ZETDC field staff? List required equipment for different types of electrical work.", "category": "safety", "icon": "🦺"},
        
        # Reports category
        {"title": "Create a monthly outage report", "prompt_text": "Create a template for a monthly power outage report. Include sections for: outage duration, affected areas, cause analysis, and restoration time.", "category": "reports", "icon": "📊"},
        {"title": "Summarize incident reports", "prompt_text": "Summarize how to write effective incident reports for ZETDC. What information must be included and what is the reporting timeline?", "category": "reports", "icon": "📊"},
        {"title": "Generate maintenance report", "prompt_text": "Create a maintenance report template for ZETDC equipment. Include inspection checklist, findings, recommendations, and follow-up actions.", "category": "reports", "icon": "📊"},
        
        # Languages category
        {"title": "Summarize in Shona", "prompt_text": "Summarize the following document in Shona language. Use clear and simple language that non-technical customers can understand.", "category": "languages", "icon": "🇿🇼"},
        {"title": "Translate to Ndebele", "prompt_text": "Translate the following text to Ndebele. Maintain technical accuracy while using accessible language.", "category": "languages", "icon": "🇿🇼"},
        {"title": "Convert to business English", "prompt_text": "Convert the following technical document to professional business English suitable for corporate communication.", "category": "languages", "icon": "📝"},
        
        # Vision category (requires vision capability)
        {"title": "🖼️ Analyze an image", "prompt_text": "Analyze this image and describe what you see. If it contains technical equipment, identify components and explain their function.", "category": "vision", "icon": "🖼️", "requires_capability": "vision"},
        {"title": "🖼️ Extract text from image", "prompt_text": "Extract all text visible in this image. Format it clearly and indicate if any text is unclear or ambiguous.", "category": "vision", "icon": "🖼️", "requires_capability": "vision"},
        
        # General category
        {"title": "⚡ ZETDC outage reporting process", "prompt_text": "Explain the ZETDC outage reporting process. How do customers report outages and what information should they provide?", "category": "general", "icon": "⚡"},
        {"title": "🔧 Troubleshoot common issues", "prompt_text": "List common electrical issues customers face and provide troubleshooting steps before calling ZETDC.", "category": "general", "icon": "🔧"},
        {"title": "💡 Energy saving tips", "prompt_text": "Provide practical energy saving tips for ZETDC customers to reduce their electricity bills.", "category": "general", "icon": "💡"},
    ]
    
    created_count = 0
    for i, data in enumerate(defaults):
        suggestion = PromptSuggestion(
            title=data["title"],
            prompt_text=data["prompt_text"],
            category=data["category"],
            icon=data["icon"],
            requires_capability=data.get("requires_capability"),
            display_order=i,
            enabled=True,
        )
        db.add(suggestion)
        created_count += 1
    
    await db.commit()
    
    logger.info(f"Seeded {created_count} default prompt suggestions")
    
    return {"message": f"Created {created_count} default prompt suggestions", "count": created_count}


@router.post("/{suggestion_id}/toggle")
async def toggle_prompt_suggestion(
    suggestion_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Toggle the enabled status of a prompt suggestion (admin only)."""
    result = await db.execute(
        select(PromptSuggestion).where(PromptSuggestion.id == suggestion_id)
    )
    suggestion = result.scalar_one_or_none()
    
    if not suggestion:
        return JSONResponse(
            status_code=404,
            content={"error": "Prompt suggestion not found"}
        )
    
    suggestion.enabled = not suggestion.enabled
    await db.commit()
    await db.refresh(suggestion)
    
    status = "enabled" if suggestion.enabled else "disabled"
    logger.info(f"Toggled prompt suggestion: {suggestion.title} (id={suggestion.id}) → {status}")
    
    return suggestion.to_dict()
