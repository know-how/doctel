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
    _using_gemini: bool,
    _using_deepseek: bool,
    _using_zen: bool,
    _using_hf: bool = False,
    _using_cloud: bool = False,
):
    from app.services.gemini_service import generate_stream as gemini_stream, is_configured as gemini_configured
    from app.services.deepseek_service import generate_stream as deepseek_stream
    from app.services.opencode_zen_service import generate_stream as zen_stream, is_configured as zen_configured
    from app.services.huggingface_service import generate_stream as hf_stream, is_configured as hf_configured

    if _using_zen:
        try:
            async for chunk in zen_stream(question, model=chosen_model, system=sys_prompt):
                yield chunk
            return
        except RuntimeError as e:
            if "balance depleted" in str(e).lower() and gemini_configured():
                print(f"[ZEN FALLBACK] Zen balance depleted, falling back to Gemini. Error: {e}", flush=True)
                async for chunk in gemini_stream(question, system=sys_prompt):
                    yield chunk
                return
            raise
    if _using_hf:
        async for chunk in hf_stream(question, model=chosen_model, system=sys_prompt):
            yield chunk
    elif _using_deepseek:
        async for chunk in deepseek_stream(question, system=sys_prompt):
            yield chunk
    elif _using_gemini:
        async for chunk in gemini_stream(question, system=sys_prompt):
            yield chunk
    elif _using_cloud:
        # 'cloud' alias: try cloud providers in priority order until one works
        printed_provider = False
        if zen_configured():
            printed_provider = True
            async for chunk in zen_stream(question, system=sys_prompt):
                yield chunk
            return
        if hf_configured():
            printed_provider = True
            async for chunk in hf_stream(question, system=sys_prompt):
                yield chunk
            return
        if gemini_configured():
            printed_provider = True
            async for chunk in gemini_stream(question, system=sys_prompt):
                yield chunk
            return
        if not printed_provider:
            yield "⚠️ No cloud AI provider is configured. Set up Zen (OPENCODE_GO_API_KEY), HuggingFace (HF_API_KEY), or Gemini (GEMINI_API_KEY) in your .env file."
    else:
        yield ""


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
        chroma_path = getattr(settings, "chroma_db_path", "data/chroma")
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
    from app.services.gemini_service import (
        GEMINI_MODEL_ID,
        is_configured as gemini_configured,
        generate as gemini_generate,
    )
    from app.services.deepseek_service import (
        DEEPSEEK_MODEL_ID,
        is_configured as deepseek_configured,
        generate as deepseek_generate,
    )
    from app.services.opencode_zen_service import (
        is_configured as zen_configured,
        generate as zen_generate,
    )
    from app.services.huggingface_service import (
        is_configured as hf_configured,
        generate as hf_generate,
    )

    # Use centralized model resolver instead of direct settings access
    from app.services.model_resolver_service import resolve_model
    
    resolved = await resolve_model(
        db,
        requested_model=requested_model,
        task_type="chat",
        session_model=(s.model_name or "").strip() or None,
    )
    chosen_model = resolved["model_id"]
    provider_type = resolved.get("provider_type", "ollama")
    
    # Use provider_type from resolver as the single source of truth
    _using_gemini = provider_type == "gemini"
    _using_deepseek = provider_type == "deepseek"
    _using_zen = provider_type == "opencode"
    _using_hf = provider_type == "huggingface"
    _using_cloud = (chosen_model == "cloud")

    if _using_gemini and not gemini_configured():
        user_msg.status = "failed"
        db.add(user_msg)
        await db.commit()
        return JSONResponse(
            status_code=503,
            content={
                "error": "gemini_not_configured",
                "message": "GEMINI_API_KEY is not set. Add it to your .env file and restart.",
            },
        )

    if _using_deepseek and not deepseek_configured():
        user_msg.status = "failed"
        db.add(user_msg)
        await db.commit()
        return JSONResponse(
            status_code=503,
            content={
                "error": "deepseek_not_configured",
                "message": "DEEPSEEK_API_KEY is not set. Add it to your .env file and restart.",
            },
        )

    if _using_zen and not zen_configured():
        user_msg.status = "failed"
        db.add(user_msg)
        await db.commit()
        return JSONResponse(
            status_code=503,
            content={
                "error": "zen_not_configured",
                "message": "OPENCODE_GO_API_KEY is not set. Get one at https://opencode.ai/go and add it to your .env file.",
            },
        )

    if _using_hf and not hf_configured():
        user_msg.status = "failed"
        db.add(user_msg)
        await db.commit()
        return JSONResponse(
            status_code=503,
            content={
                "error": "hf_not_configured",
                "message": "HF_API_KEY is not set. Get one at https://huggingface.co/settings/tokens and add it to your .env file.",
            },
        )

    if _using_cloud and not zen_configured() and not hf_configured() and not gemini_configured():
        user_msg.status = "failed"
        db.add(user_msg)
        await db.commit()
        return JSONResponse(
            status_code=503,
            content={
                "error": "cloud_not_configured",
                "message": "No cloud AI provider is configured. Set up Zen (OPENCODE_GO_API_KEY), HuggingFace (HF_API_KEY), or Gemini (GEMINI_API_KEY) in your .env file.",
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
        allowed.add(GEMINI_MODEL_ID)
        present.add(GEMINI_MODEL_ID)
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
    if embed_available and project_ids:
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
        except Exception:
            rag = None
    if not rag or not rag.get("citations"):
        sys_prompt = (settings.zetdc.system_prompt or "").strip() or None
        answer_text = None
        fallback_source = None
        cloud_error = None
        try:
            if _using_deepseek:
                answer_text = await asyncio.wait_for(deepseek_generate(question, system=sys_prompt), timeout=120.0)
                if answer_text:
                    fallback_source = "deepseek_direct"
            elif _using_gemini:
                answer_text = await asyncio.wait_for(gemini_generate(question, system=sys_prompt), timeout=120.0)
                if answer_text:
                    fallback_source = "gemini_direct"
            elif _using_zen:
                answer_text = await asyncio.wait_for(zen_generate(question, model=chosen_model, system=sys_prompt), timeout=120.0)
                if answer_text:
                    fallback_source = "zen_direct"
            elif _using_hf:
                answer_text = await asyncio.wait_for(hf_generate(question, model=chosen_model, system=sys_prompt), timeout=120.0)
                if answer_text:
                    fallback_source = "hf_direct"
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

        if not answer_text and zen_configured() and not _using_zen:
            try:
                answer_text = await asyncio.wait_for(zen_generate(question, system=sys_prompt), timeout=120.0)
                chosen_model = "zen/deepseek-v4-flash-free"
                fallback_source = "zen_api"
            except (asyncio.TimeoutError, Exception) as _zen_err:
                logger.warning("Zen global fallback failed (%s)", _zen_err)
                answer_text = None

        if not answer_text and deepseek_configured() and not _using_deepseek:
            try:
                answer_text = await asyncio.wait_for(deepseek_generate(question, system=sys_prompt), timeout=120.0)
                chosen_model = DEEPSEEK_MODEL_ID
                fallback_source = "deepseek_api"
            except (asyncio.TimeoutError, Exception) as _deepseek_err:
                logger.warning("DeepSeek global fallback failed (%s)", _deepseek_err)
                answer_text = None

        if not answer_text and gemini_configured() and not _using_gemini:
            try:
                answer_text = await asyncio.wait_for(gemini_generate(question, system=sys_prompt), timeout=120.0)
                chosen_model = GEMINI_MODEL_ID
                fallback_source = "gemini_api"
            except (asyncio.TimeoutError, Exception) as _gemini_err:
                logger.warning("Gemini global fallback failed (%s)", _gemini_err)
                answer_text = None

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
    return AskResponse(
        answer=rag.get("answer_text", ""),
        citations=[Citation(**{**c, "document_id": str(c["document_id"])}) if isinstance(c, dict) and c.get("document_id") is not None else c for c in rag.get("citations", [])],
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

        from app.services.gemini_service import GEMINI_MODEL_ID, is_configured as gemini_configured
        from app.services.deepseek_service import DEEPSEEK_MODEL_ID, is_configured as deepseek_configured
        from app.services.opencode_zen_service import is_configured as zen_configured
        from app.services.huggingface_service import is_configured as hf_configured
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
        
        # Use provider_type from resolver as the single source of truth
        _using_gemini = provider_type == "gemini"
        _using_deepseek = provider_type == "deepseek"
        _using_zen = provider_type == "opencode"
        _using_hf = provider_type == "huggingface"
        _using_cloud = (chosen_model == "cloud")
        is_cloud = _using_gemini or _using_deepseek or _using_zen or _using_hf or _using_cloud
        print(f"_using_gemini: {_using_gemini}, _using_deepseek: {_using_deepseek}, _using_zen: {_using_zen}, _using_hf: {_using_hf}, is_cloud: {is_cloud}", flush=True)

        if not is_cloud:
            print("RETURNING 400: not cloud", flush=True)
            return JSONResponse(status_code=400, content={"error": "streaming_only_for_cloud", "message": "Streaming is only supported for cloud models. Use the non-streaming endpoint for local models."})

        if _using_gemini and not gemini_configured():
            print("RETURNING 503: gemini not configured", flush=True)
            return JSONResponse(status_code=503, content={"error": "gemini_not_configured"})
        if _using_deepseek and not deepseek_configured():
            print("RETURNING 503: deepseek not configured", flush=True)
            return JSONResponse(status_code=503, content={"error": "deepseek_not_configured"})
        if _using_zen and not zen_configured():
            print("RETURNING 503: zen not configured", flush=True)
            return JSONResponse(status_code=503, content={"error": "zen_not_configured"})
        if _using_hf and not hf_configured():
            print("RETURNING 503: hf not configured", flush=True)
            return JSONResponse(status_code=503, content={"error": "hf_not_configured"})
        if _using_cloud:
            # 'cloud' is an alias that uses the fallback chain — no mandatory API key needed
            pass

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

        async def event_gen():
            full_text = ""
            try:
                print("=== EVENT_GEN: starting stream ===", flush=True)
                async with asyncio.timeout(120.0):
                    async for chunk in _stream_cloud_answer(question, chosen_model, sys_prompt, _using_gemini, _using_deepseek, _using_zen, _using_hf, _using_cloud=_using_cloud):
                        full_text += chunk
                        data = json.dumps({"chunk": chunk, "model": chosen_model, "session_id": final_session_uuid})
                        yield f"data: {data}\n\n"
            except asyncio.TimeoutError:
                err = "The AI model did not respond within 2 minutes. Please try again."
                yield f"data: {json.dumps({'error': err})}\n\n"
                full_text = f"Error: {err}"
            except Exception as exc:
                import traceback as tb
                err_msg = f"{exc}\n{tb.format_exc()}"
                print(f"=== EVENT_GEN: error: {err_msg} ===", flush=True)
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"
                full_text = f"Error: {exc}"

            try:
                assistant = DbMessage(
                    session_id=s.id,
                    role="assistant",
                    content=full_text,
                    status="done",
                    citations_json="[]",
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

        # Pre-compute chosen model so we can skip Ollama checks for Gemini/DeepSeek/Zen
        from app.services.gemini_service import (
            GEMINI_MODEL_ID,
            is_configured as gemini_configured,
        )
        from app.services.deepseek_service import (
            DEEPSEEK_MODEL_ID,
            is_configured as deepseek_configured,
        )
        from app.services.opencode_zen_service import (
            is_configured as zen_configured,
        )
        from app.services.huggingface_service import (
            is_configured as hf_configured,
        )
        _session_model_pre = (s.model_name or "").strip() or None
        _default_model_pre = (settings.default_model or settings.text_model).strip()
        chosen_model = requested_model or _session_model_pre or _default_model_pre
        _using_gemini = (chosen_model == GEMINI_MODEL_ID)
        _using_deepseek = (chosen_model == DEEPSEEK_MODEL_ID)
        _using_zen = chosen_model.startswith("zen/") or chosen_model.startswith("go/")
        _using_hf = chosen_model.startswith("huggingface/")
        _using_cloud = (chosen_model == "cloud")

        if _using_gemini and not gemini_configured():
            user_msg.status = "failed"
            db.add(user_msg)
            await db.commit()
            return JSONResponse(
                status_code=503,
                content={
                    "error": "gemini_not_configured",
                    "message": "GEMINI_API_KEY is not set. Add it to your .env file and restart.",
                    "session_id": session_uuid,
                },
            )

        if _using_deepseek and not deepseek_configured():
            user_msg.status = "failed"
            db.add(user_msg)
            await db.commit()
            return JSONResponse(
                status_code=503,
                content={
                    "error": "deepseek_not_configured",
                    "message": "DEEPSEEK_API_KEY is not set. Add it to your .env file and restart.",
                    "session_id": session_uuid,
                },
            )

        if _using_zen and not zen_configured():
            user_msg.status = "failed"
            db.add(user_msg)
            await db.commit()
            return JSONResponse(
                status_code=503,
                content={
                    "error": "zen_not_configured",
                    "message": "OPENCODE_GO_API_KEY is not set. Get one at https://opencode.ai/go and add it to your .env file.",
                    "session_id": session_uuid,
                },
            )

        if _using_hf and not hf_configured():
            user_msg.status = "failed"
            db.add(user_msg)
            await db.commit()
            return JSONResponse(
                status_code=503,
                content={
                    "error": "hf_not_configured",
                    "message": "HF_API_KEY is not set. Get one at https://huggingface.co/settings/tokens and add it to your .env file.",
                    "session_id": session_uuid,
                },
            )

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
        # Cloud models are always allowed and virtually present when configured
        if _using_gemini:
            allowed.add(GEMINI_MODEL_ID)
            present.add(GEMINI_MODEL_ID)
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
        return AskResponse(
            answer=rag.get("answer_text", ""),
            citations=[Citation(**{**c, "document_id": str(c["document_id"])}) if isinstance(c, dict) and c.get("document_id") is not None else c for c in rag.get("citations", [])],
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

    from app.services.gemini_service import GEMINI_MODEL_ID, is_configured as gemini_configured
    from app.services.deepseek_service import DEEPSEEK_MODEL_ID, is_configured as deepseek_configured
    from app.services.opencode_zen_service import is_configured as zen_configured
    from app.services.huggingface_service import is_configured as hf_configured
    from app.services.model_resolver_service import _get_provider_type

    chosen_model = requested_model or (settings.default_model or settings.text_model).strip()
    provider_type = _get_provider_type(chosen_model)
    
    # Use provider_type as the single source of truth
    _using_gemini = provider_type == "gemini"
    _using_deepseek = provider_type == "deepseek"
    _using_zen = provider_type == "opencode"
    _using_hf = provider_type == "huggingface"
    _using_cloud = (chosen_model == "cloud")
    is_cloud = _using_gemini or _using_deepseek or _using_zen or _using_hf or _using_cloud

    if not is_cloud:
        return JSONResponse(status_code=400, content={"error": "streaming_only_for_cloud", "message": "Streaming is only supported for cloud models (Gemini, DeepSeek, Zen, HuggingFace). Use the non-streaming endpoint for local models."})

    if _using_gemini and not gemini_configured():
        return JSONResponse(status_code=503, content={"error": "gemini_not_configured"})
    if _using_deepseek and not deepseek_configured():
        return JSONResponse(status_code=503, content={"error": "deepseek_not_configured"})
    if _using_zen and not zen_configured():
        return JSONResponse(status_code=503, content={"error": "zen_not_configured"})
    if _using_hf and not hf_configured():
        return JSONResponse(status_code=503, content={"error": "hf_not_configured"})
    if _using_cloud:
        # 'cloud' is an alias that uses the fallback chain — no mandatory API key needed
        pass

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

    # Retrieve document chunks via RAG for context
    rag_context = None
    try:
        from app.utils.ollama_client import ollama as rag_ollama
        from app.utils.chroma_client import chroma
        installed_models = await asyncio.wait_for(rag_ollama.list_models(), timeout=5.0)
        embed_ok = settings.embed_model in (installed_models or [])
        if embed_ok:
            query_embedding = await rag_ollama.embed(settings.embed_model, question)
            res = chroma.query(str(doc.project_id), query_embedding, top_k=6, where={"document_id": doc_int})
            docs = (res.get("documents") or [[]])[0] if isinstance(res, dict) else []
            metas = (res.get("metadatas") or [[]])[0] if isinstance(res, dict) else []
            if docs:
                context_parts = []
                for i, txt in enumerate(docs or []):
                    meta = metas[i] if i < len(metas) else {}
                    fname = meta.get("filename", doc.filename or "Unknown")
                    context_parts.append(f"Source: {fname}\nContent: {txt[:1500]}")
                rag_context = "\n\n".join(context_parts)
                print(f"\n=== RAG: Found {len(docs)} chunks for doc #{doc_int} ===", flush=True)
            else:
                print(f"\n=== RAG: No chunks found for doc #{doc_int} ===", flush=True)
        else:
            print(f"\n=== RAG: Embed model '{settings.embed_model}' not installed ===", flush=True)
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
        try:
            if rag_context:
                doc_prompt = f"Answer the question using ONLY the provided context. Always cite sources.\n\nQuestion: {question}\n\nContext:\n{rag_context}"
            else:
                doc_title = doc.filename or doc.title or f"Document #{doc_int}"
                doc_prompt = f"Answer the following question about the document titled '{doc_title}'. The document has been selected but its full content could not be retrieved. Provide your best answer based on the document title and any available context.\n\nQuestion: {question}"
            try:
                async with asyncio.timeout(120.0):
                    async for chunk in _stream_cloud_answer(doc_prompt, chosen_model, sys_prompt, _using_gemini, _using_deepseek, _using_zen, _using_hf, _using_cloud=_using_cloud):
                        full_text += chunk
                        data = json.dumps({"chunk": chunk, "model": chosen_model, "session_id": final_session_uuid})
                        yield f"data: {data}\n\n"
            except asyncio.TimeoutError:
                err = "The AI model did not respond within 2 minutes. Please try again."
                yield f"data: {json.dumps({'error': err})}\n\n"
                full_text = f"Error: {err}"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            full_text = f"Error: {exc}"

        # Save assistant message after streaming completes
        try:
            assistant = DbMessage(
                session_id=s.id,
                role="assistant",
                content=full_text,
                status="done",
                citations_json="[]",
            )
            db.add(assistant)
            s.updated_at = datetime.datetime.now(datetime.timezone.utc)
            db.add(s)
            await db.commit()
        except Exception:
            pass

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
