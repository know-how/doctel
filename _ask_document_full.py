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
            # Cache session PK early — db.rollback() later will expire ORM objects
            _session_pk = s.id
            user_msg = DbMessage(session_id=_session_pk, role="user", content=question, status="pending", citations_json="")
            db.add(user_msg)
            await db.commit()
        else:
            _session_pk = s.id
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
                job_id = await enqueue_ingest("document_ingest", document_id=doc.id, owner_id=doc.owner_id)
                if job_id is None:
                    logger.warning("[ASK] Failed to enqueue ingest job for doc %s (owner=%s)", doc.id, doc.owner_id)

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

        # Detect intent for image/diagram generation routing
        _intent_info_local = detect_intent(question)
        _is_image_intent_local = _intent_info_local["primary_intent"] in ("image", "diagram")

        # Pre-compute chosen model
        from app.services.model_resolver_service import resolve_model, resolve_provider_credentials
        _session_model_pre = (s.model_name or "").strip() or None
        _resolver_task_type = "image_generation" if _is_image_intent_local else "chat"
        resolved = await resolve_model(db, requested_model=requested_model or _session_model_pre, task_type=_resolver_task_type, session_model=_session_model_pre)
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
        # Rollback any aborted transaction before saving results
        try:
            await db.rollback()
        except Exception:
            pass
        rag = {
            "answer_text": result.get("answer_text", ""),
            "citations": result.get("citations", []),
            "cross_references": [],
            "used_model": result.get("used_model", chosen_model),
        }
        # Enrich citations with permission info and action URLs (BEFORE DB save)
        if rag.get("citations"):
            rag["citations"] = await enrich_citations(rag["citations"], user, db)
        user_msg.status = "done"
        db.add(user_msg)
        # Clean answer text before saving — strip chunk IDs, AI-isms, metadata leaks
        cleaned_answer = clean_response_text(rag.get("answer_text", ""))
        assistant = DbMessage(
            session_id=_session_pk,
            role="assistant",
            content=cleaned_answer,
            status="done",
            citations_json=json.dumps(rag.get("citations", [])),
        )
        # Update rag dict so the response also uses cleaned text
        rag["answer_text"] = cleaned_answer
        db.add(assistant)
        try:
            s.updated_at = datetime.datetime.now(datetime.timezone.utc)
            db.add(s)
        except Exception:
            pass
        try:
            await db.commit()
        except Exception:
            try:
                await db.rollback()
            except Exception:
                pass
            user_msg.status = "failed"
            db.add(user_msg)
            try:
                await db.commit()
            except Exception:
                pass
            return JSONResponse(status_code=500, content={"error": "internal_error", "detail": "Failed to save response"})
        # Track conversation state for conversational continuity
        await update_session_state(db, session_uuid, question, cleaned_answer, entities=[], retrieval_question=question)

        # ── Session summarization (every 5 turns) ─────────────────────────────
        try:
            _ss_state = await get_session_state(db, session_uuid)
            _ss_turn = _ss_state.get("turn_count", 0) if _ss_state else 0
            if _ss_turn > 0 and should_summarize(_ss_turn):
                _ss_segment = conversation_history[-10:] if conversation_history else [
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": cleaned_answer},
                ]
                await summarize_and_store(db, session_uuid, _ss_segment, _ss_turn)
        except Exception as _ss_err:
            logger.warning("[SESSION_SUMMARIZER] Doc summarization failed: %s", _ss_err)

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
                # Defensive: coerce optional booleans to None (not False) so Pydantic
                # doesn't reject null values from enrich_citations.
                _cv = c.get("can_view")
                _cd = c.get("can_download")
                _ft = c.get("full_text_available")

                citation_objects.append(Citation(
                    document_id=str(c.get("document_id")) if c.get("document_id") is not None else None,
                    filename=c.get("filename"),
                    chunk_index=c.get("chunk_index"),
                    text=c.get("text"),
                    snippet=c.get("text", ""),  # Backward compatibility
                    full_text_available=_ft if isinstance(_ft, bool) else None,
                    distance=c.get("distance"),
                    can_view=_cv if isinstance(_cv, bool) else None,
                    can_download=_cd if isinstance(_cd, bool) else None,
                    open_url=c.get("open_url"),
                    download_url=c.get("download_url"),
                    preview_url=c.get("preview_url"),
                    source_type=c.get("source_type"),
                    # Defensive: Pydantic v2 validates str | None, and enrich_citations
                    # may return int for project_id when it comes directly from RAG.
                    project_id=str(c.get("project_id")) if c.get("project_id") is not None else None,
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

