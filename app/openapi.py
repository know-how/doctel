"""
openapi.py — DOCTEL Enterprise OpenAPI 3.1 Configuration

Centralises all OpenAPI metadata, tags, security schemes, error models,
and schema customisation for the FastAPI application.

SDK Readiness
-------------
- Every operation has a unique operationId derived from tag + endpoint name.
- All schemas are named, reusable Pydantic models (no anonymous objects).
- No duplicated schema definitions — each model is defined once in
  ``app/models/schemas.py`` and referenced by $ref.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.openapi.utils import get_openapi

from app.config import settings

# ═══════════════════════════════════════════════════════════════════════════════
# APP METADATA
# ═══════════════════════════════════════════════════════════════════════════════

APP_TITLE = "DOCTEL Enterprise AI Platform"
APP_VERSION = "2.0.0"
APP_DESCRIPTION = """
DOCTEL is ZETDC's **enterprise-grade mobile AI platform**, providing secure,
scalable, and offline-aware intelligence for the power utility industry.

## Capabilities

### Knowledge Management
- **Knowledge Assets** — Unified registry for documents, audio, video, CSV,
  databases, and API connectors
- **Knowledge Spaces** — Cross-department information workspaces with
  intelligent discovery
- **Knowledge Graph** — Enterprise knowledge graph with entity resolution,
  dependency analysis, and path discovery

### AI Agents & Workflows
- **Agent Runtime** — Multi-agent coordination with 12 specialised agent types
  (Retrieval, Graph, Meeting, Risk, Workflow, Reporting, etc.)
- **Agent Memory** — Persistent working/episodic/semantic memory with
  pgvector-backed semantic recall
- **Workflow Engine** — Objective-driven autonomous workflows
  (Policy Review, Risk Assessment, Executive Briefing, etc.)

### Audio & Video Intelligence
- **Audio Intelligence** — Meeting transcription, speaker diarisation,
  action/decision extraction, risk identification
- **Video Intelligence** — Frame-level analysis, slide extraction,
  timeline generation, visual event detection

### AI Provider Gateway
- **Multi-Provider Routing** — Unified gateway to Ollama, OpenAI-compatible,
  Gemini, Anthropic, and custom providers
- **Cost Governance** — Per-request cost tracking, budget alerts,
  department-level provider restrictions
- **Confidence Scoring** — Per-response trust scoring with citation coverage
  and retrieval relevance

### Streaming & Real-Time
- **Server-Sent Events** — Streaming chat, reasoning, agent execution,
  and RAG evidence delivery
- **Sync Events** — Real-time cross-device synchronisation

## Authentication

DOCTEL supports multiple authentication methods through a unified JWT system:

1. **EC Number + Password** — Active Directory authentication for ZETDC staff
2. **Email OTP** — One-time password via email for external partners
3. **Bearer Token** — JWT-based session tokens for all API access
4. **X-User-ID Header** — Direct user ID for internal service-to-service calls

> **Production note:** In production environments, Swagger UI and ReDoc are
> restricted to authenticated admin users only.

## Versioning

The current API version is **v2** (implicit). All endpoints are prefixed with
`/api/`. Future versions will use explicit `/api/v1/`, `/api/v2/` prefixes.

## SDK Generation

The OpenAPI specification is fully compatible with:

- Python (openapi-generator / datamodel-code-generator)
- TypeScript (openapi-typescript / orval)
- Java (OpenAPI Generator)
- C# (.NET OpenAPI CLI)

Requirements for SDK readiness are met:
- ✅ All operationId values are unique
- ✅ All schemas are reusable named models
- ✅ No anonymous objects in responses
- ✅ No duplicated schema definitions
"""

CONTACT = {
    "name": "DOCTEL Engineering Team",
    "email": "engineering@zetdc.co.zw",
    "url": "https://doctel.zetdc.co.zw",
}

LICENSE = {
    "name": "ZETDC Company License",
    "identifier": "ZETDC-EULA-1.0",
}

TERMS_OF_SERVICE = "https://doctel.zetdc.co.zw/terms"


# ═══════════════════════════════════════════════════════════════════════════════
# API TAGS — Defined once, used by both FastAPI constructor and doc generation
# ═══════════════════════════════════════════════════════════════════════════════

API_TAGS = [
    # ── Core System ──────────────────────────────────────────────────────────
    {
        "name": "System Health",
        "description": "Health checks, readiness probes, and diagnostics endpoints. "
                       "Used by load balancers, Kubernetes, and monitoring systems.",
    },
    {
        "name": "Authentication",
        "description": "User authentication, session management, and token refresh. "
                       "Supports EC Number + AD, Email OTP, and Bearer JWT flows.",
    },
    {
        "name": "Users",
        "description": "User profile management, preferences, and account administration.",
    },

    # ── Projects & Documents ─────────────────────────────────────────────────
    {
        "name": "Projects",
        "description": "Project CRUD, membership management, and scope-based access control.",
    },
    {
        "name": "Documents",
        "description": "Document upload, ingestion, analysis, and file retrieval. "
                       "Supports PDF, DOCX, TXT, images, and more.",
    },

    # ── Knowledge Platform ───────────────────────────────────────────────────
    {
        "name": "Knowledge Assets",
        "description": "Unified knowledge asset registry. Documents, audio, video, CSV, "
                       "database connections, and API connectors as first-class assets "
                       "with cross-type search and relationship discovery.",
    },
    {
        "name": "Knowledge Spaces",
        "description": "Cross-department knowledge workspaces with intelligent "
                       "content discovery, asset counts, and space-to-space relationships.",
    },
    {
        "name": "Knowledge Graph",
        "description": "Enterprise knowledge graph for entity relationship discovery, "
                       "dependency path analysis, impact assessment, and graph exploration.",
    },

    # ── Chat & Streaming ─────────────────────────────────────────────────────
    {
        "name": "Chat",
        "description": "Conversational chat with document context, session management, "
                       "and multi-turn conversations.",
    },
    {
        "name": "Streaming",
        "description": "Server-Sent Events (SSE) streaming endpoints for real-time "
                       "chat, reasoning, agent execution, and RAG evidence delivery. "
                       "See the Streaming Guide below for event format details.",
    },
    {
        "name": "RAG",
        "description": "Retrieval-Augmented Generation endpoints. Ask questions "
                       "against your knowledge base with citation-backed answers.",
    },

    # ── AI Agents ────────────────────────────────────────────────────────────
    {
        "name": "Agent Runtime",
        "description": "Multi-agent orchestration platform. Execute agent plans, "
                       "coordinate 12+ specialised agent types, and retrieve "
                       "structured evidence bundles. Agents include Retrieval, "
                       "Graph, Meeting, Risk, Workflow, Policy, and Reporting.",
    },
    {
        "name": "Agent Memory",
        "description": "Persistent agent memory across execution boundaries. "
                       "Working (per-session), Episodic (per-execution), and "
                       "Semantic (long-term) memory tiers with pgvector semantic recall.",
    },
    {
        "name": "Workflow Engine",
        "description": "Autonomous workflow execution. Define objectives and "
                       "let the platform determine required agents, tools, assets, "
                       "and outputs. Supports Policy Review, Risk Assessment, "
                       "Executive Briefing, Compliance Review, and more.",
    },

    # ── Audio & Video Intelligence ───────────────────────────────────────────
    {
        "name": "Audio Intelligence",
        "description": "Audio recording analysis, meeting transcription, speaker "
                       "diarisation, and structured insight extraction (actions, "
                       "decisions, risks, owners, follow-ups).",
    },
    {
        "name": "Video Intelligence",
        "description": "Video analysis with frame-level scene detection, slide "
                       "extraction, timeline generation, and visual event analysis.",
    },

    # ── Provider Management ──────────────────────────────────────────────────
    {
        "name": "Provider Management",
        "description": "AI provider configuration, health monitoring, and "
                       "connection management. Supports Ollama, OpenAI-compatible, "
                       "Gemini, Anthropic, and custom endpoints.",
    },
    {
        "name": "AI Models",
        "description": "Model catalogue, capability management, task mapping, "
                       "and intelligent model selection with RBAC filtering.",
    },

    # ── Administration ───────────────────────────────────────────────────────
    {
        "name": "Administration",
        "description": "System administration, user management, role-based access "
                       "control, audit logs, and enterprise configuration.",
    },
    {
        "name": "Settings",
        "description": "Application settings, UI preferences, feature flags, "
                       "and system-wide configuration.",
    },
    {
        "name": "Analytics",
        "description": "Analytics, metrics, charts, and reporting endpoints "
                       "for usage monitoring and business intelligence.",
    },
    {
        "name": "Jobs",
        "description": "Background job management for document ingestion, "
                       "embedding, transcription, and AI processing pipelines.",
    },

    # ── Mobile & Sync ────────────────────────────────────────────────────────
    {
        "name": "Sync",
        "description": "Cross-device synchronisation for mobile and web clients. "
                       "SSE-based real-time events for logout, training completion, "
                       "and state changes.",
    },
    {
        "name": "Mobile API",
        "description": "Mobile-optimised endpoints with reduced payload sizes, "
                       "offline-aware error handling, and bandwidth-efficient responses.",
    },

    # ── Training ─────────────────────────────────────────────────────────────
    {
        "name": "Training",
        "description": "AI model training pipeline. LoRA adapter training, "
                       "checkpoint management, and training job orchestration.",
    },

    # ── Legacy / Compatibility ───────────────────────────────────────────────
    {
        "name": "Compatibility",
        "description": "Legacy compatibility endpoints for backward compatibility "
                       "with older API consumers.",
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY SCHEMES
# ═══════════════════════════════════════════════════════════════════════════════

SECURITY_SCHEMES = {
    "BearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": (
            "JWT Bearer token obtained from `/api/auth/login` "
            "(EC Number + Password) or `/api/auth/email/verify` (Email OTP).\n\n"
            "Tokens expire after **30 minutes** by default. "
            "Use the `refresh_token` endpoint to obtain a new token.\n\n"
            "**Example:**\n"
            "```\n"
            "Authorization: Bearer eyJhbGciOiJIUzI1NiIs...\n"
            "```"
        ),
    },
    "OAuth2Password": {
        "type": "oauth2",
        "description": (
            "OAuth2 Password Flow (Resource Owner Password Credentials Grant).\n\n"
            "Enter your ZETDC **EC Number** as username and **password** "
            "to obtain an access token directly from Swagger UI.\n\n"
            "**Token URL:** `/api/auth/login`\n"
            "**Refresh URL:** `/api/auth/refresh`"
        ),
        "flows": {
            "password": {
                "tokenUrl": "/api/auth/login",
                "refreshUrl": "/api/auth/refresh",
                "scopes": {
                    "read": "Read access",
                    "write": "Write access",
                    "admin": "Administrator access",
                },
            },
        },
    },
    "UserIdHeader": {
        "type": "apiKey",
        "in": "header",
        "name": "X-User-ID",
        "description": (
            "Direct user ID for internal service-to-service calls. "
            "Not intended for external API consumers."
        ),
    },
}

SECURITY_REQUIREMENTS = [
    {"BearerAuth": []},
    {"OAuth2Password": ["read", "write"]},
]


# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD ERROR MODELS
# ═══════════════════════════════════════════════════════════════════════════════

# Schema fragments for openapi.json — these complement the Pydantic models
# defined in app/models/schemas.py.

ERROR_RESPONSES: dict[int, dict[str, Any]] = {
    400: {
        "description": "Bad Request — The request was malformed or contains invalid parameters.",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                "example": {
                    "success": False,
                    "error_code": "VALIDATION_ERROR",
                    "message": "Invalid request parameters",
                    "details": {
                        "field_errors": [
                            {"field": "question", "message": "This field is required"},
                        ],
                    },
                    "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                },
            },
        },
    },
    401: {
        "description": "Unauthorized — Authentication is required or the provided token has expired.",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                "example": {
                    "success": False,
                    "error_code": "TOKEN_EXPIRED",
                    "message": "Authentication token has expired. Please log in again.",
                    "details": {},
                    "request_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                },
            },
        },
    },
    403: {
        "description": "Forbidden — The authenticated user does not have permission to access this resource.",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                "example": {
                    "success": False,
                    "error_code": "ACCESS_DENIED",
                    "message": "You do not have permission to access this resource",
                    "details": {
                        "required_role": "admin",
                        "user_role": "analyst",
                    },
                    "request_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
                },
            },
        },
    },
    404: {
        "description": "Not Found — The requested resource does not exist.",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                "example": {
                    "success": False,
                    "error_code": "RESOURCE_NOT_FOUND",
                    "message": "Knowledge asset not found",
                    "details": {
                        "resource_type": "knowledge_asset",
                        "resource_id": "550e8400-e29b-41d4-a716-446655440000",
                    },
                    "request_id": "d4e5f6a7-b8c9-0123-defa-123456789012",
                },
            },
        },
    },
    409: {
        "description": "Conflict — The request conflicts with the current state of the resource.",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                "example": {
                    "success": False,
                    "error_code": "RESOURCE_CONFLICT",
                    "message": "A knowledge asset with this source already exists",
                    "details": {
                        "source_table": "documents",
                        "source_id": "550e8400-e29b-41d4-a716-446655440000",
                    },
                    "request_id": "e5f6a7b8-c9d0-1234-efab-123456789012",
                },
            },
        },
    },
    422: {
        "description": "Unprocessable Entity — Request validation failed. Check field constraints.",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/ValidationError"},
                "example": {
                    "success": False,
                    "error_code": "VALIDATION_ERROR",
                    "message": "Validation failed",
                    "details": {
                        "field_errors": [
                            {"field": "email", "message": "value is not a valid email address"},
                            {"field": "password", "message": "String should have at least 8 characters"},
                        ],
                    },
                    "request_id": "f6a7b8c9-d0e1-2345-fabc-123456789012",
                },
            },
        },
    },
    429: {
        "description": "Too Many Requests — Rate limit exceeded. Wait and retry.",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                "example": {
                    "success": False,
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "message": "Rate limit exceeded. Please wait 30 seconds before retrying.",
                    "details": {
                        "retry_after_seconds": 30,
                        "limit": 60,
                        "window_seconds": 60,
                    },
                    "request_id": "a7b8c9d0-e1f2-3456-abcd-123456789012",
                },
            },
        },
    },
    500: {
        "description": "Internal Server Error — An unexpected error occurred on the server.",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                "example": {
                    "success": False,
                    "error_code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred. Our team has been notified.",
                    "details": {},
                    "request_id": "b8c9d0e1-f2a3-4567-bcde-123456789012",
                },
            },
        },
    },
    503: {
        "description": "Service Unavailable — The service is temporarily unavailable. Retry later.",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                "example": {
                    "success": False,
                    "error_code": "SERVICE_UNAVAILABLE",
                    "message": "Provider is temporarily unavailable. Please try again later.",
                    "details": {
                        "provider": "ollama",
                        "retry_after_seconds": 30,
                    },
                    "request_id": "c9d0e1f2-a3b4-5678-cdef-123456789012",
                },
            },
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# STREAMING EVENT DOCUMENTATION
# ═══════════════════════════════════════════════════════════════════════════════

STREAMING_DOCS = """
## Streaming (Server-Sent Events) Guide

DOCTEL uses **Server-Sent Events (SSE)** for real-time streaming of AI
responses, reasoning, and agent execution. All streaming endpoints return
`Content-Type: text/event-stream`.

### Event Format

Each SSE message is a JSON object prefixed with `data:` and terminated by
`\\n\\n`:

```
data: {"type": "content", "content": "Hello, how can I help you?"}

data: {"type": "reasoning", "content": "Thinking about the question..."}

data: {"type": "done", "citations": [...], "usage": {...}}
```

### Event Types

| Type | Description |
|------|-------------|
| `content` | Text content chunk (streamed incrementally) |
| `reasoning` | Model reasoning / chain-of-thought |
| `citations` | Citation metadata for the response |
| `done` | Stream complete — final metadata (usage, citations, model) |
| `error` | An error occurred during streaming |
| `connected` | Initial connection confirmation |

### Connection Handling

```python
import httpx
import json

async with httpx.AsyncClient() as client:
    async with client.stream(
        "POST",
        "https://api.doctel.zetdc.co.zw/api/ask/stream",
        json={"question": "Summarise the policy"},
        headers={"Authorization": "Bearer <token>"},
        timeout=120.0,
    ) as response:
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                event = json.loads(line[6:])
                if event["type"] == "content":
                    print(event["content"], end="")
                elif event["type"] == "done":
                    break
```

### Reconnection Guidance

- Set a **120-second timeout** for streaming requests
- On disconnect, re-send the last user message
- The server sends `: keepalive\\n\\n` every 25 seconds to prevent
  proxy timeouts
- Client-side exponential backoff: start at 1s, max 30s
"""


# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOM OPENAPI SCHEMA GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

def doctel_openapi_schema(app: FastAPI) -> dict[str, Any]:
    """
    Generate the complete OpenAPI 3.1 schema for the DOCTEL platform.

    Extends FastAPI's default ``get_openapi()`` with:
    - Production metadata (contact, license, ToS)
    - Security scheme definitions
    - Standard error response models
    - Streaming documentation
    - Consistent operation IDs
    - DOCTEL-specific customisation
    """
    # Generate base schema from FastAPI's auto-detected routes
    openapi_schema = get_openapi(
        title=APP_TITLE,
        version=APP_VERSION,
        description=APP_DESCRIPTION,
        routes=app.routes,
        tags=API_TAGS,
        contact=CONTACT,
        license_info=LICENSE,
        terms_of_service=TERMS_OF_SERVICE,
    )

    # Set OpenAPI version to 3.1
    if "openapi" in openapi_schema:
        openapi_schema["openapi"] = "3.1.0"

    # ── Security ─────────────────────────────────────────────────────────────
    openapi_schema["components"]["securitySchemes"] = SECURITY_SCHEMES
    openapi_schema["security"] = SECURITY_REQUIREMENTS

    # ── Servers ──────────────────────────────────────────────────────────────
    openapi_schema["servers"] = [
        {
            "url": "https://api.doctel.zetdc.co.zw",
            "description": "Production server",
        },
        {
            "url": "http://localhost:8000",
            "description": "Local development server",
        },
    ]

    # ── Standard Error Schema (added to components.schemas) ─────────────────
    # These are referenced by $ref in the ERROR_RESPONSES above.
    if "schemas" not in openapi_schema["components"]:
        openapi_schema["components"]["schemas"] = {}

    openapi_schema["components"]["schemas"]["ErrorResponse"] = {
        "type": "object",
        "description": "Standard error response for all API errors.",
        "properties": {
            "success": {
                "type": "boolean",
                "description": "Always false for error responses.",
                "example": False,
            },
            "error_code": {
                "type": "string",
                "description": "Machine-readable error code for programmatic handling.\n\n"
                               "Common codes: `VALIDATION_ERROR`, `TOKEN_EXPIRED`, "
                               "`ACCESS_DENIED`, `RESOURCE_NOT_FOUND`, "
                               "`RESOURCE_CONFLICT`, `RATE_LIMIT_EXCEEDED`, "
                               "`INTERNAL_ERROR`, `SERVICE_UNAVAILABLE`.",
                "example": "RESOURCE_NOT_FOUND",
            },
            "message": {
                "type": "string",
                "description": "Human-readable error message.",
                "example": "Knowledge asset not found",
            },
            "details": {
                "type": "object",
                "description": "Additional error details, may include field-level errors, "
                               "resource identifiers, or retry guidance.",
                "example": {
                    "resource_type": "knowledge_asset",
                    "resource_id": "550e8400-e29b-41d4-a716-446655440000",
                },
            },
            "request_id": {
                "type": "string",
                "format": "uuid",
                "description": "Unique request identifier for tracing. Include this "
                               "when reporting issues to support.",
                "example": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            },
        },
        "required": ["success", "error_code", "message"],
    }

    openapi_schema["components"]["schemas"]["ValidationError"] = {
        "type": "object",
        "description": "Validation error response with per-field error details.",
        "allOf": [
            {"$ref": "#/components/schemas/ErrorResponse"},
        ],
        "properties": {
            "success": {"type": "boolean", "example": False},
            "error_code": {"type": "string", "example": "VALIDATION_ERROR"},
            "details": {
                "type": "object",
                "properties": {
                    "field_errors": {
                        "type": "array",
                        "description": "Per-field validation error details.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {
                                    "type": "string",
                                    "description": "The field that failed validation.",
                                },
                                "message": {
                                    "type": "string",
                                    "description": "Validation error message.",
                                },
                            },
                        },
                    },
                },
            },
        },
    }

    # ── Streaming documentation ────────────────────────────────────────────
    openapi_schema["info"]["x-streaming"] = STREAMING_DOCS

    # ── Rate limiting metadata ──────────────────────────────────────────────
    openapi_schema["info"]["x-ratelimit"] = {
        "description": "Rate limits apply per authenticated user. "
                       "Standard limits: 60 requests/minute for chat, "
                       "10 requests/minute for streaming, 100 requests/minute "
                       "for read operations.",
        "headers": {
            "X-RateLimit-Limit": "Maximum requests per window",
            "X-RateLimit-Remaining": "Remaining requests in current window",
            "X-RateLimit-Reset": "Unix timestamp when the window resets",
        },
    }

    # ── Audit metadata ──────────────────────────────────────────────────────
    openapi_schema["info"]["x-audit"] = {
        "description": "All AI provider interactions are automatically "
                       "recorded in the InteractionAudit table for compliance "
                       "and governance. Each request generates audit entries "
                       "for: prompt text, response text, model used, provider, "
                       "token counts, latency, and cost.",
    }

    return openapi_schema


# ═══════════════════════════════════════════════════════════════════════════════
# DOCS ENDPOINT SECURITY
# ═══════════════════════════════════════════════════════════════════════════════

async def verify_docs_access(request: Request) -> None:
    """
    Verify that the requesting user is allowed to view API documentation.

    Access policy:
    - **development**: Open (no authentication required)
    - **test**: Authenticated users only
    - **production**: Admin users only

    This function is called from middleware in ``main.py``.  It raises
    HTTPException(401) or HTTPException(403) when access is denied.
    """
    env = (settings.environment or "development").lower()

    if env == "development":
        return  # Open access

    from app.db.database import AsyncSessionLocal
    from app.security.rbac import get_current_user, require_role

    async with AsyncSessionLocal() as session:
        user = await get_current_user(request, db=session)

        if env == "test":
            return  # Any authenticated user is allowed

        # Production — admin only
        role_checker = require_role(["admin"])
        await role_checker(user)
        return


# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOM SWAGGER UI TEMPLATE PATH
# ═══════════════════════════════════════════════════════════════════════════════

CUSTOM_SWAGGER_UI_PATH = "/static/swagger.html"
CUSTOM_SWAGGER_UI_TITLE = "DOCTEL Enterprise AI Platform — API Reference"
