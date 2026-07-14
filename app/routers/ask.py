"""
Ask endpoints for DocTel.
"""

import json
import logging

from app.routers.deps import (
    # stdlib
    asyncio,
    datetime,
    uuid,
    Optional,
    # fastapi
    APIRouter,
    Body,
    Depends,
    # starlette
    JSONResponse,
    StreamingResponse,
    # sqlalchemy
    AsyncSession,
    select,
    # config
    settings,
    # db
    get_db,
    # models
    User,
    DbSession,
    DbMessage,
    Document,
    Document as DbDocument,
    DocAnalysis,
    # rbac
    get_current_user,
    check_project_access,
    ensure_project_membership,
    # helpers
    _parse_document_id,
    _assert_document_workspace_access,
    _searchable_project_ids,
    _derive_session_title,
    _is_generation_model,
    _ask_inflight,
    _ask_lock,
    # schemas
    AskResponse,
    Citation,
    # services
    get_rag_answer_scoped,
    generate_document_response,
    enqueue_ingest,
    select_model_with_fallback,
    # utils
    update_installed_models,
    # logger
    logger,
)

router = APIRouter(tags=["ask"])


# ── Streaming helper ──────────────────────────────────────────────────────

async def _stream_cloud_answer(
    question: str,
    chosen_model: str,
    sys_prompt: Optional[str],
    _using_zen: bool = False,
    zen_api_key: Optional[str] = None,
    zen_base_url: Optional[str] = None,
    db: Optional[AsyncSession] = None,
):
    """Stream using the provider gateway (database-driven adapter selection).
    Yields dicts with format: {"type": "content"|"reasoning", "content": str}
    """
    from app.services.provider_gateway_service import generate_stream as gateway_stream

    if _using_zen and zen_api_key:
        # Use legacy opencode_zen_service for key-based streaming (backward compat)
        from app.services.opencode_zen_service import generate_stream_with_key as zen_stream_with_key
        try:
            async for chunk in zen_stream_with_key(question, model=chosen_model, system=sys_prompt, api_key=zen_api_key, base_url=zen_base_url):
                # Normalize string chunks to dict (backward compat)
                if isinstance(chunk, str):
                    yield {"type": "content", "content": chunk}
                elif isinstance(chunk, dict):
                    yield chunk
                else:
                    yield {"type": "content", "content": str(chunk)}
            return
        except RuntimeError as e:
            if "balance depleted" in str(e).lower():
                print(f"[ZEN FALLBACK] Balance depleted, trying Gemini.", flush=True)
            else:
                yield {"type": "content", "content": f"⚠️ Cloud request failed: {e}. Check your API key in Admin > Providers."}
                return

    # All other providers: use the gateway with DB session
    if db:
        try:
            async for chunk in gateway_stream(db, question, model_id=chosen_model, system=sys_prompt):
                # Normalize string chunks to dict (backward compat)
                if isinstance(chunk, str):
                    yield {"type": "content", "content": chunk}
                else:
                    yield chunk
        except Exception as e:
            import traceback
            from app.services.openai_compatible_adapter import ProviderError
            
            error_type = type(e).__name__
            error_msg = str(e)
            
            # Check if it's a structured provider error
            if isinstance(e, ProviderError):
                provider_name = getattr(e, 'provider_name', 'unknown')
                status_code = getattr(e, 'status_code', 0)
                logger.error(f"[PROVIDER ERROR] {provider_name} returned {status_code}: {error_msg}")
                user_message = error_msg  # Already formatted by ProviderError
            else:
                # Generic error - log full stack trace
                stack_trace = traceback.format_exc()
                logger.error(f"[PROVIDER ERROR] {error_type}: {error_msg}\n{stack_trace}")
                
                # Check for common error patterns in the message
                error_lower = error_msg.lower()
                if "timeout" in error_lower or "timed out" in error_lower:
                    user_message = "Provider request timed out. Please try again."
                elif "connection" in error_lower or "unreachable" in error_lower:
                    user_message = "Provider is unavailable. Please check your network connection."
                elif "rate limit" in error_lower or "429" in error_lower:
                    user_message = "Provider rate limit exceeded. Please wait and try again."
                elif "quota" in error_lower or "credits" in error_lower or "402" in error_lower:
                    user_message = "Provider credits exhausted. Please add funds to your account."
                elif "authentication" in error_lower or "api key" in error_lower or "401" in error_lower:
                    user_message = "Invalid provider API key. Please check your API key in Admin > Providers."
                else:
                    user_message = f"Provider error: {error_msg[:200]}"
            
            yield {"type": "content", "content": f"⚠️ {user_message}"}
    else:
        yield {"type": "content", "content": "⚠️ No database session available for provider routing."}


# ── Diagnostics ───────────────────────────────────────────────────────────

@router.get("/api/ask/diagnostics")
async def ask_diagnostics(
    db: AsyncSession = Depends(get_db),
):
    """Report embedding status, ChromaDB stats, configured providers, and recent errors."""
    diag = {
        "embedding": {"available": False, "collections": 0, "error": None},
        "providers": {},
        "models": {"available": [], "default": None},
        "chroma": {"status": "not_checked", "error": None},
    }

    # 1. Provider configurations
    for provider_key, label in [
        ("gemini", "Gemini"),
        ("deepseek", "DeepSeek"),
        ("opencode_go", "OpenCode Go"),
        ("opencode_zen", "Zen"),
        ("huggingface", "HuggingFace"),
        ("llama_cpp", "LlamaCpp"),
    ]:
        base_url = getattr(settings, f"{provider_key}_base_url", None) or getattr(settings, "llm_base_url", None)
        api_key = getattr(settings, f"{provider_key}_api_key", None) or getattr(settings, "api_key", None)
        diag["providers"][label] = {
            "configured": bool(base_url),
            "has_api_key": bool(api_key),
        }

    # 2. Models
    diag["models"]["default"] = getattr(settings, "default_model", None)
    diag["models"]["available"] = list(getattr(settings, "available_models", []) or [])

    # 3. Embedding / ChromaDB
    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings
        chroma_path = settings.chroma_path
        client = chromadb.PersistentClient(path=chroma_path, settings=ChromaSettings(anonymized_telemetry=False))
        collections = client.list_collections()
        diag["embedding"]["available"] = True
        diag["embedding"]["collections"] = len(collections)
        diag["embedding"]["collection_names"] = [c.name for c in collections]
        diag["embed_model"] = getattr(settings, "embed_model", "nomic-embed-text")
    except Exception as exc:
        diag["embedding"]["available"] = False
        diag["embedding"]["error"] = str(exc)
        diag["chroma"]["status"] = "error"
        diag["chroma"]["error"] = str(exc)

    # 4. Inflight locks
    diag["inflight_locks"] = len(_ask_inflight)
    diag["active_locks"] = len(_ask_lock._locks) if hasattr(_ask_lock, "_locks") else 0

    return diag


# ── Global ask (no document) ──────────────────────────────────────────────

@router.post("/api/ask", response_model=AskResponse)
async def ask_global(
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    question = (payload.get("question") or "").strip()
    if not question:
        return JSONResponse(status_code=400, content={"error": "Missing question"})
    scope = (payload.get("scope") or "all").strip().lower()
    requested_model = (payload.get("model") or "").strip() or None
    force_policy = bool(payload.get("force_policy", False))
    force_diagram = bool(payload.get("force_diagram", False))

    project_ids: list[int] = []
    project_id = payload.get("project_id")
    if scope == "project":
        if project_id is None:
            return JSONResponse(status_code=400, content={"error": "missing_project_id"})
        try:
            pid = int(project_id)
        except Exception:
            return JSONResponse(status_code=400, content={"error": "invalid_project_id"})
        await check_project_access(pid, user, db)
        await ensure_project_membership(pid, user, db, role_in_project="analyst")
        project_ids = [pid]
    else:
        project_ids = await _searchable_project_ids(db)

    session_uuid = (payload.get("session_id") or "").strip() or None
    if not session_uuid:
        session_uuid = str(uuid.uuid4())
        s = DbSession(project_id=project_ids[0] if project_ids else None, user_id=user.id, session_uuid=session_uuid, model_name=requested_model)
        db.add(s)
        await db.commit()
    else:
        sres = await db.execute(select(DbSession).where(DbSession.session_uuid == session_uuid))
        s = sres.scalar_one_or_none()
        if not s:
            s = DbSession(project_id=project_ids[0] if project_ids else None, user_id=user.id, session_uuid=session_uuid, model_name=requested_model)
            db.add(s)
            await db.commit()
        if s.user_id != user.id:
            return JSONResponse(status_code=403, content={"error": "Access denied"})

    user_msg = DbMessage(session_id=s.id, role="user", content=question, status="pending", citations_json="")
    db.add(user_msg)
    await db.commit()
    if not (s.title or "").strip():
        s.title = _derive_session_title(question)
        db.add(s)
        await db.commit()

    from app.utils.ollama_client import ollama
    from app.services.model_resolver_service import resolve_model, resolve_provider_credentials
    from app.services.provider_gateway_service import generate as gateway_generate, generate_stream as gateway_generate_stream

    # Use centralized model resolver instead of direct settings access
    logger.info("[ASK] Resolving model for requested_model=%s", requested_model)
    resolved = await resolve_model(
        db,
        requested_model=requested_model,
        task_type="chat",
        session_model=(s.model_name or "").strip() or None,
    )
    chosen_model = resolved["model_id"]
    provider_type = resolved.get("provider_type", "ollama")
    provider_id = resolved.get("provider_id", "unknown")
    logger.info("[ASK] Model resolved: chosen_model=%s, provider_type=%s, provider_id=%s, source=%s", 
                chosen_model, provider_type, provider_id, resolved.get("source"))
    
    # Use provider_type from resolver as the single source of truth
    _using_gemini = provider_type == "gemini"
    _using_deepseek = provider_type == "deepseek"
    _using_zen = provider_type == "opencode"
    _using_hf = provider_type == "huggingface"
    _using_cloud = (chosen_model == "cloud")
    _using_ollama = provider_type == "ollama"

    # Resolve credentials from DB using the already-resolved provider_id
    # This ensures we use the correct provider even if model_id exists in multiple providers
    logger.info("[ASK] Resolving provider credentials for chosen_model=%s, provider_id=%s", chosen_model, provider_id)
    creds = await resolve_provider_credentials(db, chosen_model, provider_id_hint=provider_id)
    logger.info("[ASK] Provider credentials resolved: api_key_present=%s, base_url=%s, creds_provider_id=%s", 
                bool(creds.get("api_key")), creds.get("base_url"), creds.get("provider_id"))

    # Validate: DB is the source of truth for API keys
    is_cloud_provider = _using_gemini or _using_deepseek or _using_zen or _using_hf or _using_cloud
    logger.info("[ASK] Provider classification: is_cloud_provider=%s, _using_ollama=%s", 
                is_cloud_provider, _using_ollama)
    if is_cloud_provider and not creds["api_key"]:
        user_msg.status = "failed"
        db.add(user_msg)
        await db.commit()
        return JSONResponse(
            status_code=503,
            content={
                "error": "provider_not_configured",
                "message": f"No API key found for provider of model '{chosen_model}'. Configure an API key in Admin > Providers.",
            },
        )

    ollama_models: list[str] = []
    if not _using_gemini and not _using_deepseek and not _using_zen and not _using_hf and not _using_cloud:
        try:
            ollama_models = await ollama.list_models()
            update_installed_models(ollama_models)
        except Exception:
            ollama_models = []
    else:
        try:
            ollama_models = await asyncio.wait_for(ollama.list_models(), timeout=5.0)
            update_installed_models(ollama_models)
        except Exception:
            ollama_models = []
    present = set(ollama_models or [])
    embed_available = settings.embed_model in present

    allowed = set(settings.available_models or []) | present
    if _using_gemini:
        allowed.add(chosen_model)
        present.add(chosen_model)
    if _using_deepseek:
        allowed.add(chosen_model)
        present.add(chosen_model)
    if _using_zen:
        allowed.add(chosen_model)
        present.add(chosen_model)
    if _using_hf:
        allowed.add(chosen_model)
        present.add(chosen_model)
    if _using_cloud:
        allowed.add(chosen_model)
        present.add(chosen_model)

    session_model = (s.model_name or "").strip() or None
    if not _is_generation_model(chosen_model):
        user_msg.status = "failed"
        db.add(user_msg)
        await db.commit()
        return JSONResponse(status_code=400, content={"error": "invalid_generation_model", "model": chosen_model})
    if chosen_model not in allowed:
        user_msg.status = "failed"
        db.add(user_msg)
        await db.commit()
        return JSONResponse(status_code=400, content={"error": "model_not_allowed", "model": chosen_model})
    if chosen_model not in present:
        logger.info("Global chat model %s is not locally present; falling back to alternate tiers if needed", chosen_model)
    if not session_model and chosen_model in present:
        s.model_name = chosen_model
        db.add(s)
        await db.commit()

    rag = None
    # ── RAG TRACE: entry point diagnostics ────────────────────────────────
    logger.info(
        "[RAG_TRACE] START — question=%r | session=%s | user=%s | scope=%s | "
        "project_ids=%s | document_id=%s | model=%s",
        question[:120] if question else "",
        session_uuid,
        user.id if user else "?",
        scope,
        project_ids,
        None,  # document_id for global ask is always None
        chosen_model,
    )
    # ── RAG gate: check ChromaDB has vectors + embedding model is reachable ──
    # Replaces the fragile "settings.embed_model in present" check which
    # depends on Ollama listing models quickly enough.  Instead we try
    # the RAG call and let get_rag_answer_scoped() handle failures gracefully.
    # If ChromaDB is empty or the embedding model is unavailable, it returns
    # citations=[] which triggers the fallback below.
    rag_collections_exist = False
    try:
        from app.utils.chroma_client import chroma as _gate_chroma
        _gate_cols = _gate_chroma.list_collections()
        rag_collections_exist = any(c.count() > 0 for c in (_gate_cols or []))
    except Exception:
        rag_collections_exist = True  # assume yes if we can't check
    logger.info("[RAG] Gate check: embed_available=%s, projects=%s, chroma_collections_exist=%s",
                embed_available, bool(project_ids), rag_collections_exist)
    if embed_available and project_ids and rag_collections_exist:
        try:
            rag = await get_rag_answer_scoped(
                project_ids,
                question,
                db,
                document_id=None,
                model_name=chosen_model,
                force_policy=force_policy,
                force_diagram=force_diagram,
            )
        except Exception as rag_exc:
            logger.warning("[RAG] get_rag_answer_scoped threw exception: %s", rag_exc, exc_info=True)
            rag = None
    if not rag or not rag.get("citations"):
        # ── Cross-project fallback ──────────────────────────────────────────
        # When scope="project" and the current project has no indexed chunks,
        # try searching ALL projects before giving up.  This prevents "please
        # upload the document" responses when the same document exists (with
        # embeddings) in a different project.
        if scope == "project" and project_ids:
            try:
                all_project_ids = await _searchable_project_ids(db)
                if len(all_project_ids) > len(project_ids):
                    logger.info(
                        "[RAG] Project-scoped search returned no results; "
                        "trying cross-project search across %d projects",
                        len(all_project_ids),
                    )
                    rag = await get_rag_answer_scoped(
                        all_project_ids,
                        question,
                        db,
                        document_id=None,
                        model_name=chosen_model,
                        force_policy=force_policy,
                        force_diagram=force_diagram,
                    )
                    logger.info(
                        "[RAG] Cross-project search returned %d citations",
                        len(rag.get("citations", [])) if rag else 0,
                    )
            except Exception as cross_exc:
                logger.warning("[RAG] Cross-project search failed: %s", cross_exc)

    if not rag or not rag.get("citations"):
        if rag is None:
            logger.warning("[RAG] rag result is None — falling back to direct answer")
            logger.warning("[RAG_FALLBACK] reason=rag_none | embed_available=%s | project_ids=%s | chroma_collections=%s",
                           embed_available, project_ids, rag_collections_exist)
        elif not rag.get("citations"):
            logger.warning("[RAG] rag result has NO citations — citations=%d, context_length=%d chars",
                           len(rag.get("citations", [])), len(rag.get("answer_text", "") or ""))
            logger.warning("[RAG_FALLBACK] reason=no_citations | chunks_retrieved=%d | answer_length=%d",
                           len(rag.get("citations", [])), len(rag.get("answer_text", "") or ""))
        sys_prompt = (settings.zetdc.system_prompt or "").strip() or None
        answer_text = None
        fallback_source = None
        cloud_error = None
        try:
            if is_cloud_provider:
                answer_text = await asyncio.wait_for(
                    gateway_generate(db, question, model_id=chosen_model, system=sys_prompt),
                    timeout=120.0,
                )
                if answer_text:
                    fallback_source = "gateway"
            elif chosen_model in present:
                answer_text = await ollama.generate(chosen_model, question, system=sys_prompt)
                if answer_text:
                    fallback_source = "ollama_direct"
        except asyncio.TimeoutError:
            logger.warning("Direct global answer timed out for %s", chosen_model)
            answer_text = None
        except Exception as _direct_err:
            logger.warning("Direct global answer failed for %s (%s)", chosen_model, _direct_err)
            cloud_error = str(_direct_err)
            answer_text = None

        # Fallback: if primary failed and we have a DB key, don't retry — just report the error
        if not answer_text and is_cloud_provider and creds["api_key"]:
            pass

        if not answer_text:
            try:
                routed = await asyncio.wait_for(
                    select_model_with_fallback(question, task_type="rag"),
                    timeout=120.0,
                )
                answer_text = routed.get("answer") or ""
                fallback_source = routed.get("tier") or "fallback"
                chosen_model = routed.get("model") or chosen_model
            except asyncio.TimeoutError:
                logger.warning("Global fallback routing timed out")
                answer_text = "I could not complete the fallback answer in time. Please try again."
                fallback_source = "timeout"

        if not answer_text:
            error_detail = cloud_error or "All model tiers failed to generate a response"
            if _using_deepseek and cloud_error:
                answer_text = f"I could not get a response from the DeepSeek API. Error: {cloud_error}. Please check your DEEPSEEK_API_KEY and network connection, then try again."
            elif _using_gemini and cloud_error:
                answer_text = f"I could not get a response from the Gemini API. Error: {cloud_error}. Please check your GEMINI_API_KEY and network connection, then try again."
            elif _using_hf and cloud_error:
                answer_text = f"I could not get a response from the HuggingFace API. Error: {cloud_error}. Please check your HF_API_KEY and network connection, then try again."
            else:
                answer_text = "I was unable to find an answer using any available intelligence tier. Please ensure Ollama is running or a cloud API key is configured."

        rag = {
            "answer_text": answer_text,
            "citations": rag.get("citations", []) if rag else [],
            "cross_references": (
                rag.get("cross_references", []) if rag else []
            ) + ([{"filename": str(fallback_source), "reason": "Fallback intelligence tier used"}] if fallback_source else []),
            "used_model": chosen_model,
        }
    # ── RAG RESPONSE summary log ─────────────────────────────────────────
    logger.info(
        "[RAG_RESPONSE] answer_length=%d | citation_count=%d | model=%s | "
        "reasoning=%s",
        len(rag.get("answer_text", "") or ""),
        len(rag.get("citations", [])),
        rag.get("used_model", "?"),
        "present" if rag.get("answer_text") else "missing",
    )
    user_msg.status = "done"
    db.add(user_msg)
    # Get reasoning if available from RAG response
    reasoning_text = rag.get("reasoning_text", "") if rag else ""
    assistant = DbMessage(
        session_id=s.id,
        role="assistant",
        content=rag.get("answer_text", ""),
        reasoning=reasoning_text or None,
        status="done",
        citations_json=json.dumps(rag.get("citations", [])),
    )
    db.add(assistant)
    try:
        s.updated_at = datetime.datetime.now(datetime.timezone.utc)
        db.add(s)
    except Exception:
        pass
    await db.commit()
    # Convert cross_references to proper format
    cross_refs = rag.get("cross_references", [])
    if cross_refs and isinstance(cross_refs[0], dict):
        # Already in dict format from RAG service
        cross_refs_list = cross_refs
    else:
        # Empty or already processed
        cross_refs_list = cross_refs
    # Map citations to response format with all new fields
    citation_objects = []
    for c in rag.get("citations", []):
        if isinstance(c, dict):
            citation_objects.append(Citation(
                document_id=str(c.get("document_id")) if c.get("document_id") is not None else None,
                filename=c.get("filename"),
                chunk_index=c.get("chunk_index"),
                text=c.get("text"),
                snippet=c.get("text", ""),  # Backward compatibility
                full_text_available=c.get("full_text_available"),
                distance=c.get("distance"),
            ))
    
    return AskResponse(
        answer=rag.get("answer_text", ""),
        citations=citation_objects,
        cross_references=cross_refs_list,
        used_model=rag.get("used_model", ""),
        session_id=session_uuid,
    )


# ── Global streaming ask ──────────────────────────────────────────────────

@router.post("/api/ask/stream")
async def ask_global_stream(
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    print("\n=== ask_global_stream CALLED ===", flush=True)
    print(f"payload type: {type(payload)}", flush=True)
    print(f"payload: {json.dumps(payload, default=str)}", flush=True)
    print(f"user: {user}", flush=True)
    import traceback
    try:
        question = (payload.get("question") or "").strip()
        print(f"question: '{question}'", flush=True)
        if not question:
            print("RETURNING 400: Missing question", flush=True)
            return JSONResponse(status_code=400, content={"error": "Missing question"})
        requested_model = (payload.get("model") or "").strip() or None
        session_uuid = (payload.get("session_id") or "").strip()
        print(f"requested_model: {requested_model}", flush=True)
        print(f"session_uuid: {session_uuid}", flush=True)

        from app.services.model_resolver_service import resolve_model

        # Use centralized model resolver
        resolved = await resolve_model(
            db,
            requested_model=requested_model,
            task_type="chat",
        )
        chosen_model = resolved["model_id"]
        provider_type = resolved.get("provider_type", "ollama")
        print(f"chosen_model: '{chosen_model}' (source: {resolved['source']}, provider: {provider_type})", flush=True)
        
        # Determine streaming support from provider metadata
        from app.services.provider_gateway_service import provider_supports_streaming

        _using_zen = provider_type == "opencode"
        streaming_supported = provider_supports_streaming(provider_type)
        print(f"provider_type: {provider_type}, _using_zen: {_using_zen}, streaming_supported: {streaming_supported}", flush=True)

        if not streaming_supported:
            print("RETURNING 400: streaming not supported", flush=True)
            return JSONResponse(status_code=400, content={"error": "streaming_not_supported", "message": "The selected provider does not support streaming. Use the non-streaming endpoint or select a different model."})

        # Create/reuse session
        s = None
        if session_uuid:
            sres = await db.execute(select(DbSession).where(DbSession.session_uuid == session_uuid))
            s = sres.scalar_one_or_none()
        if not s:
            s = DbSession(project_id=None, user_id=user.id, session_uuid=session_uuid or str(uuid.uuid4()), model_name=chosen_model)
            db.add(s)
            await db.commit()
        print(f"Session created: {s.session_uuid if s else 'None'}", flush=True)

        user_msg = DbMessage(session_id=s.id, role="user", content=question, status="done", citations_json="")
        db.add(user_msg)
        if not (s.title or "").strip():
            s.title = _derive_session_title(question)
            db.add(s)
        await db.commit()
        print("User message saved", flush=True)

        sys_prompt = (settings.zetdc.system_prompt or "").strip() or None
        final_session_uuid = s.session_uuid

        # ── RAG retrieval for global context ────────────────────────────────
        scope = (payload.get("scope") or "all").strip().lower()
        raw_project_id = payload.get("project_id")
        project_ids: list[int] = []
        if scope == "project" and raw_project_id is not None:
            pid = int(raw_project_id)
            await check_project_access(pid, user, db)
            await ensure_project_membership(pid, user, db, role_in_project="analyst")
            project_ids = [pid]
        else:
            project_ids = await _searchable_project_ids(db)
        print(f"[RAG] scope={scope}, project_ids={project_ids}", flush=True)

        rag_context: str | None = None
        citations_list: list[dict] = []
        try:
            # ── Unified RAG retrieval via get_rag_answer_scoped ──────────────
            # This uses the same code path as ask_global(), ensuring
            # consistent citation formatting, embedding model resolution,
            # and context building across all endpoints.
            from app.services.rag_service import get_rag_answer_scoped as rag_scoped

            rag_result = await rag_scoped(
                project_ids,
                question,
                db,
                document_id=None,
                model_name=chosen_model,
            )

            # ── Cross-project fallback (mirrors ask_global) ──────────────
            if scope == "project" and not rag_result.get("citations"):
                all_ids = await _searchable_project_ids(db)
                if len(all_ids) > len(project_ids):
                    print(f"[RAG] Project-scoped search empty; cross-project fallback across {len(all_ids)} projects", flush=True)
                    rag_result = await rag_scoped(
                        all_ids,
                        question,
                        db,
                        document_id=None,
                        model_name=chosen_model,
                    )

            citations_list = rag_result.get("citations", [])
            rag_context = "\n\n".join(
                f"Source: {c.get('filename', 'Unknown')}, Chunk {c.get('chunk_index', 0)}\nContent: {(c.get('text', '') or '')[:1500]}"
                for c in citations_list
            ) if citations_list else None

            if rag_context:
                doc_ids = list(dict.fromkeys([c.get("document_id") for c in citations_list if c.get("document_id")]))
                print(f"[RAG] Retrieved {len(citations_list)} chunks, context={len(rag_context)} chars, doc_ids={doc_ids}", flush=True)
            else:
                print(f"[RAG] No chunks retrieved — context is EMPTY", flush=True)

        except Exception as e:
            print(f"[RAG] Error during retrieval: {e}", flush=True)
            import traceback as _tb
            _tb.print_exc()

        # Build augmented question with context
        augmented_question = question
        if rag_context:
            augmented_question = f"Answer the question using ONLY the provided context. Always cite sources.\n\nQuestion: {question}\n\nContext:\n{rag_context}"
            logger.info(
                "[RAG_PROMPT] stream — context=%d chars | total_prompt=%d chars | "
                "chunks=%d | doc_ids=%s",
                len(rag_context),
                len(augmented_question),
                len(citations_list),
                list(dict.fromkeys([c.get("document_id") for c in citations_list if c.get("document_id")])),
            )
            print(f"[RAG] Augmented question built — context={len(rag_context)} chars, total_question_length={len(augmented_question)} chars", flush=True)
        else:
            logger.warning("[RAG_FALLBACK] reason=no_context_stream | scope=%s | project_ids=%s", scope, project_ids)
            print(f"[RAG] No context — sending question without RAG context", flush=True)

        # Resolve API key: model → provider → key (database is SOURCE OF TRUTH)
        zen_api_key = None
        zen_base_url = None
        if _using_zen:
            try:
                from app.db.config_models import AIModel, AIProvider
                from sqlalchemy import select as sa_sel

                # Step 1: Find model in ai_models
                model = (await db.execute(sa_sel(AIModel).where(AIModel.model_id == chosen_model))).scalar_one_or_none()
                if not model:
                    bare = chosen_model.split("/")[-1] if "/" in chosen_model else chosen_model
                    model = (await db.execute(sa_sel(AIModel).where(AIModel.model_id.ilike(f"%{bare}%")))).scalars().first()
                print(f"[ZEN DB] model={chosen_model} found={model is not None}", flush=True)

                # Step 2: Get provider by model.provider_id
                if model:
                    provider = (await db.execute(sa_sel(AIProvider).where(AIProvider.id == model.provider_id))).scalar_one_or_none()
                    if provider and provider.api_key_value:
                        zen_api_key = provider.api_key_value.strip()
                        zen_base_url = (provider.base_url or "").strip() or None
                        print(f"[ZEN DB] ✅ KEY via model→provider: {provider.name}, len={len(zen_api_key)}", flush=True)

                # Step 3: Fallback — any provider with a non-empty api_key_value
                if not zen_api_key:
                    provider = (await db.execute(
                        sa_sel(AIProvider).where(AIProvider.api_key_value.isnot(None), AIProvider.api_key_value != "").limit(1)
                    )).scalars().first()
                    if provider:
                        zen_api_key = provider.api_key_value.strip()
                        zen_base_url = (provider.base_url or "").strip() or None
                        print(f"[ZEN DB] ⚠️ Fallback key: {provider.name} len={len(zen_api_key)}", flush=True)
                    else:
                        print(f"[ZEN DB] ❌ No provider in ai_providers has api_key_value set", flush=True)
            except Exception as e:
                import traceback
                print(f"[ZEN DB] Error: {e}\n{traceback.format_exc()}", flush=True)

        async def event_gen():
            full_text = ""
            reasoning_text = ""
            try:
                print("=== EVENT_GEN: starting stream ===", flush=True)
                async with asyncio.timeout(120.0):
                    async for event in _stream_cloud_answer(augmented_question, chosen_model, sys_prompt, _using_zen=_using_zen, zen_api_key=zen_api_key, zen_base_url=zen_base_url, db=db):
                        event_type = event.get("type", "content") if isinstance(event, dict) else "content"
                        event_content = event.get("content", "") if isinstance(event, dict) else event
                        if event_type == "content":
                            full_text += event_content
                        elif event_type == "reasoning":
                            reasoning_text += event_content
                            # Log reasoning tokens as they arrive
                            if len(reasoning_text) < 200 or len(reasoning_text) % 500 == 0:
                                logger.info("[REASONING] stream — received %d chars so far", len(reasoning_text))
                        data = json.dumps({
                            "type": event_type,
                            "content": event_content,
                            "model": chosen_model,
                            "session_id": final_session_uuid,
                        })
                        yield f"data: {data}\n\n"
                logger.info(
                    "[RAG_RESPONSE] stream_complete — answer_length=%d | reasoning_length=%d | "
                    "citation_count=%d | model=%s",
                    len(full_text), len(reasoning_text), len(citations_list), chosen_model,
                )
            except asyncio.TimeoutError:
                err = "The AI model did not respond within 2 minutes. Please try again."
                yield f"data: {json.dumps({'type': 'content', 'content': err, 'model': chosen_model, 'session_id': final_session_uuid})}\n\n"
                full_text = f"Error: {err}"
            except Exception as exc:
                import traceback as tb
                err_msg = f"{exc}\n{tb.format_exc()}"
                print(f"=== EVENT_GEN: error: {err_msg} ===", flush=True)
                yield f"data: {json.dumps({'type': 'content', 'content': str(exc), 'model': chosen_model, 'session_id': final_session_uuid})}\n\n"
                full_text = f"Error: {exc}"

            try:
                assistant = DbMessage(
                    session_id=s.id,
                    role="assistant",
                    content=full_text,
                    reasoning=reasoning_text or None,
                    status="done",
                    citations_json=json.dumps(citations_list),
                )
                db.add(assistant)
                s.updated_at = datetime.datetime.now(datetime.timezone.utc)
                db.add(s)
                await db.commit()
            except Exception:
                pass

            yield "data: [DONE]\n\n"

        print("=== RETURNING StreamingResponse ===", flush=True)
        return StreamingResponse(event_gen(), media_type="text/event-stream")
    except Exception as e:
        print(f"=== EXCEPTION in ask_global_stream: {e} ===", flush=True)
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": f"Internal error: {e}"})


# ── Document‑scoped ask ───────────────────────────────────────────────────

@router.post("/api/ask/{document_id}", response_model=AskResponse)
async def ask_document(
    document_id: str,
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc_int = _parse_document_id(document_id)
    result = await db.execute(select(DbDocument).where(DbDocument.id == doc_int))
    doc = result.scalar_one_or_none()
    if not doc:
        return JSONResponse(status_code=404, content={"error": "document_not_found", "detail": "Document not found"})
    await _assert_document_workspace_access(doc, user, db)

    question = (payload.get("question") or "").strip()
    if not question:
        return JSONResponse(status_code=400, content={"error": "Missing question"})

    session_uuid = (payload.get("session_id") or "").strip() or None
    requested_model = (payload.get("model") or "").strip() or None
    scope = (payload.get("scope") or "project").strip().lower()
    force_policy = bool(payload.get("force_policy", False))
    force_diagram = bool(payload.get("force_diagram", False))
    if not session_uuid:
        session_uuid = str(uuid.uuid4())
        s = DbSession(project_id=int(doc.project_id), user_id=user.id, session_uuid=session_uuid, model_name=requested_model)
        db.add(s)
        await db.commit()
    else:
        sres = await db.execute(select(DbSession).where(DbSession.session_uuid == session_uuid))
        s = sres.scalar_one_or_none()
        if not s:
            s = DbSession(project_id=int(doc.project_id), user_id=user.id, session_uuid=session_uuid, model_name=requested_model)
            db.add(s)
            await db.commit()
        await check_project_access(s.project_id, user, db)

    inflight_key = f"{session_uuid}:{doc_int}"
    async with _ask_lock:
        if inflight_key in _ask_inflight:
            return JSONResponse(
                status_code=409,
                content={"error": "ask_in_progress", "session_id": session_uuid, "expected_ms": 3000},
            )
        _ask_inflight[inflight_key] = asyncio.get_event_loop().time()

    try:
        pending_message_id = payload.get("pending_message_id")
        user_msg = None
        if pending_message_id is not None:
            try:
                mid = int(pending_message_id)
            except Exception:
                mid = None
            if mid is not None:
                mres = await db.execute(select(DbMessage).where(DbMessage.id == mid))
                existing = mres.scalar_one_or_none()
                if existing and existing.session_id == s.id and existing.role == "user":
                    user_msg = existing

        if not user_msg:
            user_msg = DbMessage(session_id=s.id, role="user", content=question, status="pending", citations_json="")
            db.add(user_msg)
            await db.commit()
        if not (s.title or "").strip() or (doc.filename and (s.title or "").strip() == (doc.filename or "").strip()):
            s.title = _derive_session_title(question, fallback=(doc.filename or "Conversation"))
            db.add(s)
            await db.commit()

        from app.utils.ollama_client import ollama

        ares = await db.execute(select(DocAnalysis.id).where(DocAnalysis.document_id == doc_int))
        if ares.first():
            if doc.status != "completed":
                doc.status = "completed"
                doc.ingest_step = "done"
                doc.ingest_percent = 100
                doc.ingest_message = "Completed"
                doc.error_message = ""
            doc.analysis_ready = True
            doc.ingestion_started = True
            doc.ingestion_completed = True
            doc.ingestion_failed = False
            db.add(doc)
            await db.commit()

        if doc.status == "uploaded":
            age_s = 0.0
            try:
                if getattr(doc, "created_at", None):
                    dt = doc.created_at
                    if getattr(dt, "tzinfo", None) is None:
                        dt = dt.replace(tzinfo=datetime.timezone.utc)
                    age_s = (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds()
            except Exception:
                age_s = 0.0
            if age_s > 5 and not bool(getattr(doc, "ingestion_started", False)):
                doc.status = "ingesting"
                doc.ingest_step = "extract"
                doc.ingest_percent = 0
                doc.ingest_message = "Queued for ingestion"
                doc.ingestion_started = True
                db.add(doc)
                await db.commit()
                await enqueue_ingest(int(doc.id))

        allow_while = bool(getattr(settings, "ui", None) and getattr(settings.ui, "allow_chat_while_ingesting", True))

        if doc.status not in ("completed", "summarized", "embedded") and not allow_while and doc.status != "failed":
            wait_msg = DbMessage(
                session_id=s.id,
                role="system",
                content=f"Analysis is still running (step: {doc.ingest_step}, {doc.ingest_percent}%). I will answer when ready.",
                status="done",
                citations_json="",
            )
            db.add(user_msg)
            db.add(wait_msg)
            await db.commit()
            return JSONResponse(
                status_code=202,
                content={
                    "status": "pending_analysis",
                    "reason": "analysis_not_ready",
                    "document_status": doc.status,
                    "retry_after_ms": 4000,
                    "poll_url": f"/api/ingest/{document_id}/status",
                    "session_id": session_uuid,
                    "pending_message_id": user_msg.id,
                },
            )

        # Pre-compute chosen model
        from app.services.model_resolver_service import resolve_model, resolve_provider_credentials
        _session_model_pre = (s.model_name or "").strip() or None
        resolved = await resolve_model(db, requested_model=requested_model or _session_model_pre, task_type="chat", session_model=_session_model_pre)
        chosen_model = resolved["model_id"]
        provider_type = resolved.get("provider_type", "ollama")
        provider_id = resolved.get("provider_id", "unknown")
        _using_gemini = provider_type == "gemini"
        _using_deepseek = provider_type == "deepseek"
        _using_zen = provider_type == "opencode"
        _using_hf = provider_type == "huggingface"
        _using_cloud = (chosen_model == "cloud")

        # Validate via DB instead of env vars
        is_cloud_provider = _using_gemini or _using_deepseek or _using_zen or _using_hf or _using_cloud
        creds = await resolve_provider_credentials(db, chosen_model, provider_id_hint=provider_id)
        if is_cloud_provider and not creds["api_key"]:
            user_msg.status = "failed"
            db.add(user_msg)
            await db.commit()
            return JSONResponse(status_code=503, content={
                "error": "provider_not_configured",
                "message": f"No API key found for provider of model '{chosen_model}'. Configure in Admin > Providers.",
            })

        models: list[str] = []
        if not _using_gemini and not _using_deepseek and not _using_zen and not _using_hf and not _using_cloud:
            try:
                models = await ollama.list_models()
                update_installed_models(models)
            except Exception:
                user_msg.status = "failed"
                db.add(user_msg)
                await db.commit()
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "ollama_unreachable",
                        "message": "Ollama is not reachable. Start Ollama (ollama serve) and retry.",
                        "retry_after_ms": 4000,
                        "session_id": session_uuid,
                    },
                )
            if not models:
                user_msg.status = "failed"
                db.add(user_msg)
                await db.commit()
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "ollama_unreachable",
                        "message": "Ollama returned no installed models. Pull a model and retry.",
                        "retry_after_ms": 4000,
                        "session_id": session_uuid,
                    },
                )
        else:
            try:
                models = await asyncio.wait_for(ollama.list_models(), timeout=5.0)
                update_installed_models(models)
            except Exception:
                pass
        present = set(models)
        embed_available = settings.embed_model in present

        allowed = set(settings.available_models or []) | present
        # Cloud models are always allowed and virtually present
        if is_cloud_provider:
            allowed.add(chosen_model)
            present.add(chosen_model)

        session_model = (s.model_name or "").strip() or None
        if not _is_generation_model(chosen_model):
            user_msg.status = "failed"
            db.add(user_msg)
            await db.commit()
            return JSONResponse(status_code=400, content={"error": "invalid_generation_model", "model": chosen_model})
        if chosen_model not in allowed:
            user_msg.status = "failed"
            db.add(user_msg)
            await db.commit()
            return JSONResponse(status_code=400, content={"error": "model_not_allowed", "model": chosen_model})
        if chosen_model not in present:
            user_msg.status = "failed"
            db.add(user_msg)
            await db.commit()
            return JSONResponse(
                status_code=400,
                content={
                    "error": "model_not_available",
                    "message": f"Model {chosen_model} is not installed. Please pull it via Ollama.",
                    "pull_command": f"ollama pull {chosen_model}",
                },
            )
        if not session_model and chosen_model:
            s.model_name = chosen_model
            db.add(s)
            await db.commit()
        if requested_model and requested_model != session_model:
            prev = session_model
            s.model_name = requested_model
            db.add(s)
            if prev and prev != requested_model:
                db.add(
                    DbMessage(
                        session_id=s.id,
                        role="system",
                        content=f"Model switched to {requested_model}",
                        status="done",
                        citations_json="",
                    )
                )
            await db.commit()

        # Delegate LLM generation to the unified document response service
        result = await generate_document_response(
            document_id=doc_int,
            prompt=question,
            selected_model=chosen_model,
            db=db,
        )
        rag = {
            "answer_text": result.get("answer_text", ""),
            "citations": result.get("citations", []),
            "cross_references": [],
            "used_model": result.get("used_model", chosen_model),
        }
        user_msg.status = "done"
        db.add(user_msg)
        assistant = DbMessage(
            session_id=s.id,
            role="assistant",
            content=rag.get("answer_text", ""),
            status="done",
            citations_json=json.dumps(rag.get("citations", [])),
        )
        db.add(assistant)
        try:
            s.updated_at = datetime.datetime.now(datetime.timezone.utc)
            db.add(s)
        except Exception:
            pass
        await db.commit()
        # Convert cross_references to proper format
        cross_refs = rag.get("cross_references", [])
        if cross_refs and isinstance(cross_refs[0], dict):
            # Already in dict format from RAG service
            cross_refs_list = cross_refs
        else:
            # Empty or already processed
            cross_refs_list = cross_refs
        # Map citations to response format with all new fields
        citation_objects = []
        for c in rag.get("citations", []):
            if isinstance(c, dict):
                citation_objects.append(Citation(
                    document_id=str(c.get("document_id")) if c.get("document_id") is not None else None,
                    filename=c.get("filename"),
                    chunk_index=c.get("chunk_index"),
                    text=c.get("text"),
                    snippet=c.get("text", ""),  # Backward compatibility
                    full_text_available=c.get("full_text_available"),
                    distance=c.get("distance"),
                ))
        
        return AskResponse(
            answer=rag.get("answer_text", ""),
            citations=citation_objects,
            cross_references=cross_refs_list,
            used_model=rag.get("used_model", ""),
            session_id=session_uuid,
        )
    except HTTPException:
        raise
    except Exception as e:
        try:
            logging.getLogger().exception("ask_document error")
        except Exception:
            pass
        error_msg = str(e) or "Unknown error"
        if "connection" in error_msg.lower() or "connect" in error_msg.lower():
            error_msg = "Unable to connect to AI model. Check that Ollama is running."
        elif "model" in error_msg.lower():
            error_msg = f"Model error: {error_msg}"
        elif "chroma" in error_msg.lower() or "embed" in error_msg.lower():
            error_msg = "Document indexing is not ready. Please wait for processing to complete."
        else:
            error_msg = f"AI service error: {error_msg}"
        return JSONResponse(status_code=500, content={"error": "internal_error", "detail": error_msg})
    finally:
        async with _ask_lock:
            _ask_inflight.pop(inflight_key, None)


# ── Document‑scoped streaming ask ─────────────────────────────────────────

@router.post("/api/ask/{document_id}/stream")
async def ask_document_stream(
    document_id: str,
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    question = (payload.get("question") or "").strip()
    if not question:
        return JSONResponse(status_code=400, content={"error": "Missing question"})
    requested_model = (payload.get("model") or "").strip() or None
    session_uuid = (payload.get("session_id") or "").strip()

    try:
        doc_int = _parse_document_id(document_id)
    except HTTPException:
        return JSONResponse(status_code=404, content={"error": "document_not_found"})
    doc = await db.get(Document, doc_int)
    if not doc:
        return JSONResponse(status_code=404, content={"error": "document_not_found"})

    from app.services.model_resolver_service import _resolve_provider_type

    chosen_model = requested_model or (settings.default_model or settings.text_model).strip()
    provider_type = await _resolve_provider_type(db, chosen_model)
    
    # Determine streaming support from provider metadata
    from app.services.provider_gateway_service import provider_supports_streaming

    _using_zen = provider_type == "opencode"
    streaming_supported = provider_supports_streaming(provider_type)

    if not streaming_supported:
        return JSONResponse(status_code=400, content={"error": "streaming_not_supported", "message": "The selected provider does not support streaming. Use the non-streaming endpoint or select a different model."})

    # Configuration checks: warn but don't block — let the streamer handle routing

    # Create/reuse session
    s = None
    if session_uuid:
        sres = await db.execute(select(DbSession).where(DbSession.session_uuid == session_uuid))
        s = sres.scalar_one_or_none()
    if not s:
        s = DbSession(project_id=doc.project_id, user_id=user.id, session_uuid=session_uuid or str(uuid.uuid4()), model_name=chosen_model)
        db.add(s)
        await db.commit()

    user_msg = DbMessage(session_id=s.id, role="user", content=question, status="done", citations_json="")
    db.add(user_msg)
    if not (s.title or "").strip():
        s.title = _derive_session_title(question)
        db.add(s)
    await db.commit()

    sys_prompt = (settings.zetdc.system_prompt or "").strip() or None
    final_session_uuid = s.session_uuid

    # Retrieve document chunks via unified RAG service
    # Uses get_rag_answer_scoped() — same code path as ask_global()
    rag_context = None
    citations_list: list[dict] = []
    try:
        from app.services.rag_service import get_rag_answer_scoped as rag_scoped

        rag_result = await rag_scoped(
            [int(doc.project_id)],
            question,
            db,
            document_id=doc_int,
            model_name=chosen_model,
        )

        citations_list = rag_result.get("citations", [])
        rag_context = "\n\n".join(
            f"Source: {c.get('filename', 'Unknown')}, Chunk {c.get('chunk_index', 0)}\nContent: {(c.get('text', '') or '')[:1500]}"
            for c in citations_list
        ) if citations_list else None

        if citations_list:
            doc_ids = list(dict.fromkeys([c.get("document_id") for c in citations_list if c.get("document_id")]))
            print(f"\n=== RAG: Found {len(citations_list)} chunks for doc #{doc_int}, doc_ids={doc_ids} ===", flush=True)
        else:
            print(f"\n=== RAG: No chunks found for doc #{doc_int} ===", flush=True)
    except Exception as e:
        print(f"\n=== RAG: Error: {e} ===", flush=True)

    # Fallback: read chunks directly from database if RAG failed
    if not rag_context:
        try:
            from app.db.models import Chunk
            chunk_res = await db.execute(
                select(Chunk).where(Chunk.document_id == doc_int).order_by(Chunk.chunk_index).limit(10)
            )
            db_chunks = list(chunk_res.scalars().all())
            if db_chunks:
                context_parts = []
                for c in db_chunks:
                    context_parts.append(f"Source: {doc.filename or 'Unknown'}\nContent: {(c.text or '')[:1500]}")
                rag_context = "\n\n".join(context_parts)
                print(f"\n=== DB FALLBACK: Found {len(db_chunks)} chunks for doc #{doc_int} ===", flush=True)
            else:
                print(f"\n=== DB FALLBACK: No chunks found for doc #{doc_int} ===", flush=True)
        except Exception as e2:
            print(f"\n=== DB FALLBACK: Error: {e2} ===", flush=True)

    async def event_gen():
        full_text = ""
        reasoning_text = ""
        try:
            if rag_context:
                doc_prompt = f"Answer the question using ONLY the provided context. Always cite sources.\n\nQuestion: {question}\n\nContext:\n{rag_context}"
                logger.info(
                    "[RAG_PROMPT] doc_stream — context=%d chars | total_prompt=%d chars | "
                    "chunks=%d | citations=%d",
                    len(rag_context), len(doc_prompt),
                    len(citations_list), len(citations_list),
                )
            else:
                doc_title = doc.filename or doc.title or f"Document #{doc_int}"
                doc_prompt = f"Answer the following question about the document titled '{doc_title}'. The document has been selected but its full content could not be retrieved. Provide your best answer based on the document title and any available context.\n\nQuestion: {question}"
                logger.warning("[RAG_FALLBACK] reason=no_context_doc_stream | doc_id=%s | doc_title=%s", doc_int, doc_title)
            try:
                async with asyncio.timeout(120.0):
                    async for event in _stream_cloud_answer(doc_prompt, chosen_model, sys_prompt, _using_zen=_using_zen, db=db):
                        event_type = event.get("type", "content") if isinstance(event, dict) else "content"
                        event_content = event.get("content", "") if isinstance(event, dict) else event
                        if event_type == "content":
                            full_text += event_content
                        elif event_type == "reasoning":
                            reasoning_text += event_content
                        data = json.dumps({
                            "type": event_type,
                            "content": event_content,
                            "model": chosen_model,
                            "session_id": final_session_uuid,
                        })
                        yield f"data: {data}\n\n"
                logger.info(
                    "[RAG_RESPONSE] doc_stream_complete — answer_length=%d | reasoning_length=%d | "
                    "citation_count=%d | model=%s",
                    len(full_text), len(reasoning_text), len(citations_list), chosen_model,
                )
            except asyncio.TimeoutError:
                err = "The AI model did not respond within 2 minutes. Please try again."
                yield f"data: {json.dumps({'type': 'content', 'content': err, 'model': chosen_model, 'session_id': final_session_uuid})}\n\n"
                full_text = f"Error: {err}"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'content', 'content': str(exc), 'model': chosen_model, 'session_id': final_session_uuid})}\n\n"
            full_text = f"Error: {exc}"

        # Save assistant message after streaming completes
        try:
            assistant = DbMessage(
                session_id=s.id,
                role="assistant",
                content=full_text,
                reasoning=reasoning_text or None,
                status="done",
                citations_json=json.dumps(citations_list),
            )
            db.add(assistant)
            s.updated_at = datetime.datetime.now(datetime.timezone.utc)
            db.add(s)
            await db.commit()
            logger.info(
                "[REASONING] doc_stream_saved — assistant_msg reasoning=%d chars | citations=%d",
                len(reasoning_text), len(citations_list),
            )
        except Exception:
            pass

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
