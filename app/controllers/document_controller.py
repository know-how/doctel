import logging

from fastapi import APIRouter, UploadFile, File, Form, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models import (
    ChatSource,
    DocumentCreateResponse,
    DocumentAnalysisResponse,
    PromptListResponse,
    ChatRequest,
    ChatResponse,
    ProjectCreateRequest,
    ProjectResponse,
    ProjectListResponse,
    ProjectDocumentListResponse,
)
from app.services.auth_service import get_current_user
from app.services.document_service import (
    upload_document,
    get_document_analysis,
    get_document_prompts,
    chat_with_document,
    create_project,
    get_projects,
    get_project_documents,
    get_project_detail,
    get_project_analysis,
    get_document_file,
)
from app.services.document_response_service import generate_document_response
from app.db.database import get_db


logger = logging.getLogger(__name__)

router = APIRouter(tags=["Documents"])


@router.post("/documents", response_model=DocumentCreateResponse)
async def upload_document_endpoint(
    file: UploadFile = File(...),
    project_id: str | None = Form(None),
    project_name: str | None = Form(None),
    document_type: str | None = Form(None),
    document_date: str | None = Form(None),
) -> DocumentCreateResponse:
    return await upload_document(
        file,
        project_id=project_id,
        project_name=project_name,
        document_type=document_type,
        document_date=document_date,
    )

@router.get("/documents/{document_id}/file")
async def get_document_file_endpoint(
    document_id: str,
    user: dict = Depends(get_current_user),
) -> FileResponse:
    file_path, media_type, filename = await get_document_file(document_id)
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename,
    )


@router.get(
    "/documents/{document_id}/analysis",
    response_model=DocumentAnalysisResponse,
)
async def get_document_analysis_endpoint(
    document_id: str,
    user: dict = Depends(get_current_user),
) -> DocumentAnalysisResponse:
    return await get_document_analysis(document_id, user["ec_number"])


@router.get("/documents/{document_id}/prompts", response_model=PromptListResponse)
async def get_document_prompts_endpoint(
    document_id: str,
    user: dict = Depends(get_current_user),
) -> PromptListResponse:
    return await get_document_prompts(document_id)


@router.post(
    "/documents/{document_id}/chat",
    response_model=ChatResponse,
)
async def chat_with_document_endpoint(
    document_id: str,
    request: ChatRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    request.ec_number = user["ec_number"]
    # Delegate to the unified document response service which uses
    # embedding‑based RAG (primary) + DB fallback + multi‑provider routing.
    selected_model = request.selected_model or settings.default_model
    try:
        result = await generate_document_response(
            document_id=int(document_id),
            prompt=request.question,
            selected_model=selected_model,
            db=db,
        )
        answer_text = result.get("answer_text", "")
        citations = result.get("citations", [])
    except Exception as exc:
        logger.exception("generate_document_response failed for doc %s", document_id)
        answer_text = f"Error generating response: {exc}"
        citations = []
    return ChatResponse(
        document_id=document_id,
        question=request.question,
        answer=answer_text,
        sources=[
            ChatSource(chunk_id=str(c.get("chunk_index", "")), snippet=c.get("text", ""))
            for c in citations
        ],
    )


@router.post("/projects", response_model=ProjectResponse)
async def create_project_endpoint(
    request: ProjectCreateRequest,
    user: dict = Depends(get_current_user),
) -> ProjectResponse:
    return await create_project(request)


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects_endpoint(
    user: dict = Depends(get_current_user),
) -> ProjectListResponse:
    return await get_projects()


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project_detail_endpoint(
    project_id: str,
    user: dict = Depends(get_current_user),
) -> ProjectResponse:
    return await get_project_detail(project_id)


@router.get(
    "/projects/{project_id}/analysis",
    response_model=DocumentAnalysisResponse,
)
async def get_project_analysis_endpoint(
    project_id: str,
    user: dict = Depends(get_current_user),
) -> DocumentAnalysisResponse:
    return await get_project_analysis(project_id, user["ec_number"])


@router.get(
    "/projects/{project_id}/documents",
    response_model=ProjectDocumentListResponse,
)
async def get_project_documents_endpoint(
    project_id: str,
    user: dict = Depends(get_current_user),
) -> ProjectDocumentListResponse:
    return await get_project_documents(project_id)
