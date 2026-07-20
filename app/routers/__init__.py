"""
DocTel API Routers.

Each sub-module defines an APIRouter that is imported lazily inside
``include_routers()`` so that importing ``app.routers.deps`` does not
trigger a circular-import chain via the router sub-modules.
"""


def include_routers(app) -> None:
    """Register all API sub‑routers onto the FastAPI application.

    Imports are deferred to avoid circular imports: ``main.py`` imports
    ``_sse_broadcast`` from ``app.routers.deps`` before router modules
    have been fully loaded.
    """
    from .health import router as health_router
    from .auth import router as auth_router
    from .models import router as models_router
    from .settings import router as settings_router
    from .projects import router as projects_router
    from .documents import router as documents_router
    from .ingest import router as ingest_router
    from .chat import router as chat_router
    from .ask import router as ask_router
    from .vision import router as vision_router
    from .audio import router as audio_router
    from .charts import router as charts_router
    from .admin import router as admin_router
    from .admin_config import router as admin_config_router
    from .training import router as training_router
    from .sync import router as sync_router
    from .team import router as team_router
    from .analyze import router as analyze_router
    from .outputs import router as outputs_router
    from .compat import router as compat_router
    from .model_management import router as model_mgmt_router
    from .system_diagnostics import router as system_diag_router
    from .config_lookup import router as config_lookup_router
    from .prompt_suggestions import router as prompt_suggestions_router
    from .enterprise_admin import router as enterprise_admin_router
    from .admin_embeddings import router as admin_embeddings_router
    from .agent_gateway import router as agent_gateway_router
    from .processing_control import router as processing_control_router
    from .admin_jobs import router as admin_jobs_router

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(models_router)
    app.include_router(settings_router)
    app.include_router(projects_router)
    app.include_router(documents_router)
    app.include_router(ingest_router)
    app.include_router(chat_router)
    app.include_router(ask_router)
    app.include_router(vision_router)
    app.include_router(audio_router)
    app.include_router(charts_router)
    app.include_router(admin_router)
    app.include_router(admin_config_router)
    app.include_router(training_router)
    app.include_router(sync_router)
    app.include_router(team_router)
    app.include_router(analyze_router)
    app.include_router(outputs_router)
    app.include_router(compat_router)
    app.include_router(model_mgmt_router)
    app.include_router(system_diag_router)
    app.include_router(config_lookup_router)
    app.include_router(prompt_suggestions_router)
    app.include_router(enterprise_admin_router)
    app.include_router(admin_embeddings_router)
    app.include_router(agent_gateway_router)
    app.include_router(processing_control_router)
    app.include_router(admin_jobs_router)


__all__ = [
    "include_routers",
    "ingest_router",
    "processing_control_router",
    "admin_jobs_router",
    "chat_router",
    "ask_router",
    "vision_router",
    "audio_router",
    "charts_router",
    "admin_router",
    "training_router",
    "sync_router",
    "team_router",
    "analyze_router",
    "outputs_router",
    "compat_router",
]
