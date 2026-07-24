import uuid

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Boolean, UniqueConstraint, UUID, text
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from .database import Base

# ── Embedding Governance Constants ──────────────────────────────────────────
EMBEDDING_VERSION = "1"  # Bump when embedding model/provider changes require re-embedding

# Document status values for embedding lifecycle
DOC_STATUS_EMBEDDED = "embedded"       # Has current embeddings (new status for completed docs)
DOC_STATUS_READY = "ready"             # Fully processed and ready (was "completed")
DOC_STATUS_RE_EMBED_REQUIRED = "re_embed_required"  # Embedding model changed; needs re-embedding
DOC_STATUS_EMBEDDING_IN_PROGRESS = "embedding_in_progress"  # Embedding currently running
DOC_STATUS_EMBEDDING_FAILED = "embedding_failed"  # Last embedding attempt failed

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    username = Column(String(255), unique=True, index=True)
    ec_number = Column(String(255), index=True)
    email = Column(String(255), index=True)
    display_name = Column(String(255), default="")
    role = Column(String(50))  # admin, analyst, viewer
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owned_projects = relationship("Project", back_populates="owner")
    memberships = relationship("ProjectMember", back_populates="user")
    identity_providers = relationship("UserIdentityProvider", back_populates="user")

class UserIdentityProvider(Base):
    __tablename__ = "user_identity_providers"
    __table_args__ = (UniqueConstraint("provider", "identity", name="uq_identity_provider_identity"),)
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    provider = Column(String(50), index=True)  # ec_password|email_otp
    identity = Column(String(255), index=True)
    verified = Column(Boolean, default=False)
    last_login_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="identity_providers")



class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token = Column(String(512), primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String(50))
    identity = Column(String(255))
    display_name = Column(String(255), default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    archived_at = Column(DateTime(timezone=True), nullable=True, default=None)

    owner = relationship("User", back_populates="owned_projects")
    members = relationship("ProjectMember", back_populates="project")
    documents = relationship("Document", back_populates="project")
    sessions = relationship("Session", back_populates="project")

class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_members_project_user"),)
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    role_in_project = Column(String(50))

    project = relationship("Project", back_populates="members")
    user = relationship("User", back_populates="memberships")

class Document(Base):
    __tablename__ = "documents"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True, server_default=text("uuid_generate_v4()"))
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(500), nullable=False, default="")
    project_id = Column(Integer, ForeignKey("projects.id"))
    uploaded_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    filename = Column(String(512))
    path = Column(String(512))
    mime_type = Column(String(255))
    sha256 = Column(String(64), index=True)
    pages = Column(Integer)
    doc_type = Column(String(255))
    doc_date = Column(String(255))
    is_public = Column(Boolean, default=False)
    auto_project_confidence = Column(Float, default=0.0)
    needs_project_review = Column(Boolean, default=False)
    tags_json = Column(Text, default="[]")
    analysis_ready = Column(Boolean, default=False)
    ingestion_started = Column(Boolean, default=False)
    ingestion_completed = Column(Boolean, default=False)
    ingestion_failed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(50), default="uploaded", index=True)
    ingest_step = Column(String(50), default="uploaded")
    ingest_percent = Column(Integer, default=0)
    ingest_message = Column(String(255), default="")
    error_message = Column(Text, default="")
    detected_type = Column(String(50), default="")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # ── Processing Control Fields v1 ───────────────────────────────────────
    processing_state = Column(String(20), default="UPLOADED", index=True)
    processing_step = Column(String(50), default="")
    pause_requested = Column(Boolean, default=False)
    cancel_requested = Column(Boolean, default=False)
    retry_count = Column(Integer, default=0)
    checkpoint = Column(Text, default=None, comment="JSON checkpoint for worker resume")

    # ── Embedding Governance Fields ────────────────────────────────────────
    embedding_provider = Column(String(128), nullable=True, default=None,
                                comment="Provider used for last embedding (e.g. ollama)")
    embedding_model = Column(String(255), nullable=True, default=None,
                             comment="Model used for last embedding (e.g. nomic-embed-text)")
    embedded_at = Column(DateTime(timezone=True), nullable=True, default=None,
                         comment="Timestamp of last successful embedding")
    embedding_version = Column(String(32), nullable=True, default=None,
                                comment="Embedding version tag; bumped when model changes")

    project = relationship("Project", back_populates="documents")
    analysis = relationship("DocAnalysis", back_populates="document", uselist=False)
    prompts = relationship("SuggestedPrompt", back_populates="document")
    chunks = relationship("Chunk", back_populates="document")

class DocAnalysis(Base):
    __tablename__ = "doc_analysis"
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))
    executive_summary = Column(Text)
    detailed_summary = Column(Text)
    sentiment = Column(String(50))
    entities_json = Column(Text)  # JSON string
    topics_json = Column(Text)    # JSON string
    action_items_json = Column(Text)  # JSON string
    decisions_json = Column(Text)     # JSON string
    summary_json = Column(Text, nullable=True, default=None,
                          comment="Enterprise summary: JSON blob with structured sections (doc_type, executive_summary, key_findings, responsibilities, risks, etc.) — generated by document_summarizer.py")
    doc_type = Column(String(50), nullable=True, default=None,
                      comment="Detected document type: policy|frs|meeting|sop|generic")

    document = relationship("Document", back_populates="analysis")

class SuggestedPrompt(Base):
    __tablename__ = "suggested_prompts"
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))
    prompt_text = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="prompts")

class Chunk(Base):
    __tablename__ = "chunks"
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))
    project_id = Column(Integer, ForeignKey("projects.id"))
    chunk_index = Column(Integer)
    text = Column(Text)
    citation_ref = Column(String(255))
    embedding_id = Column(Integer, ForeignKey("embeddings.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="chunks")

class Embedding(Base):
    __tablename__ = "embeddings"
    id = Column(Integer, primary_key=True, index=True)
    vector_ref = Column(String(255))  # Chroma ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # ── Embedding Governance Fields ────────────────────────────────────────
    model_name = Column(String(255), nullable=True, default=None,
                        comment="Embedding model used (e.g. nomic-embed-text)")
    provider = Column(String(128), nullable=True, default=None,
                      comment="Provider used for embedding (e.g. ollama)")
    dimensions = Column(Integer, nullable=True, default=None,
                        comment="Vector dimension count")

class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    session_uuid = Column(String(255), unique=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    model_name = Column(String(255))
    title = Column(String(255), default="")
    scope = Column(String(50), default="document")  # global|project|document
    archived = Column(Boolean, default=False)
    conversation_state = Column(Text, nullable=True, default=None,
                                comment="JSON blob tracking entities_seen, topic_history, last_turn_summary")
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="sessions")
    messages = relationship("Message", back_populates="session")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    role = Column(String(50))  # user, assistant, system
    content = Column(Text)
    reasoning = Column(Text, nullable=True)
    status = Column(String(50), default="done")  # pending, done, failed
    citations_json = Column(Text)  # JSON string
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("Session", back_populates="messages")

class Setting(Base):
    __tablename__ = "settings"
    key = Column(String(255), primary_key=True)
    value = Column(String(255))

class DocumentLink(Base):
    __tablename__ = "document_links"
    id = Column(Integer, primary_key=True, index=True)
    from_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))
    to_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))
    relation = Column(String(255))
    confidence = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Diagram(Base):
    __tablename__ = "diagrams"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    session_id = Column(Integer, ForeignKey("sessions.id"))
    title = Column(String(255))
    mermaid = Column(Text)
    drawing_prompt = Column(Text)
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SystemSetting(Base):
    __tablename__ = "system_settings"
    key = Column(String(255), primary_key=True)
    value_json = Column(Text)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

class SettingsAudit(Base):
    __tablename__ = "settings_audit"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), index=True)
    old_value_json = Column(Text)
    new_value_json = Column(Text)
    changed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    changed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class DocumentChunk(Base):
    """pgvector document chunk — the primary retrieval unit for RAG.

    Maps to the `document_chunks` table created by the industrial schema migration.
    Used by VectorSearchRBAC for RBAC-pre-filtered vector similarity search.
    """
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    chunk_size = Column(Integer, nullable=True)
    chunk_text = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    section_heading = Column(String(500), nullable=True)
    preceding_context = Column(Text, nullable=True)
    following_context = Column(Text, nullable=True)
    embedding_model = Column(String(100), nullable=True)
    embedding_provider = Column(String(50), nullable=True)
    embedded_at = Column(DateTime(timezone=True), nullable=True)
    token_count = Column(Integer, nullable=True)
    quality_score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class Permission(Base):
    """Granular action permission."""
    __tablename__ = "permissions"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    code = Column(String(100), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    resource_type = Column(String(50), nullable=False)
    action = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RolePermission(Base):
    """Role-Permission mapping."""
    __tablename__ = "role_permissions"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    permission_id = Column(UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False)
    conditions = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)


class UserRole(Base):
    """User-Role assignment."""
    __tablename__ = "user_roles"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    scope_type = Column(String(50), nullable=False)
    scope_id = Column(UUID(as_uuid=True), nullable=True)
    granted_at = Column(DateTime(timezone=True), server_default=func.now())
    granted_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    revoked_reason = Column(Text, default="")
    __table_args__ = (UniqueConstraint("user_id", "role_id", "scope_type", "scope_id", name="uq_user_role_scope"),)


class AccessControl(Base):
    """Explicit ACL entry for document access."""
    __tablename__ = "access_control"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    subject_type = Column(String(50), nullable=False)
    subject_id = Column(UUID(as_uuid=True), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(UUID(as_uuid=True), nullable=False)
    permission = Column(String(50), nullable=False)
    inherit_to_descendants = Column(Boolean, default=False)
    granted_at = Column(DateTime(timezone=True), server_default=func.now())
    granted_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    revoked_reason = Column(Text, default="")
    __table_args__ = (UniqueConstraint("subject_type", "subject_id", "resource_type", "resource_id", "permission",
                                        name="uq_acl_entry"),)


class Workspace(Base):
    """Cross-department workspace."""
    __tablename__ = "workspaces"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class WorkspaceMember(Base):
    """Workspace membership."""
    __tablename__ = "workspace_members"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_in_workspace = Column(String(50), default="member")
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    added_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    removed_at = Column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),)


class AuditLog(Base):
    """Comprehensive audit trail."""
    __tablename__ = "audit_log"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_ec_number = Column(String(50), nullable=True)
    impersonated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)
    action_category = Column(String(50), nullable=True)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    resource_name = Column(String(500), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    session_id = Column(String(255), nullable=True)
    request_id = Column(String(255), nullable=True)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class AudioMetadata(Base):
    """Audio-specific metadata linked to a Document record.

    Captures duration, language, speaker count, transcription model info,
    and processing metrics for audio and video documents.
    This is a complementary table — the Document row itself is the primary
    record; AudioMetadata enriches it with audio-specific attributes.
    """
    __tablename__ = "audio_metadata"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"),
                         nullable=False, unique=True, index=True)
    duration_sec = Column(Float, nullable=True,
                          comment="Audio/video duration in seconds")
    language = Column(String(10), nullable=True, default="en",
                      comment="Detected language (e.g. en, sn)")
    speaker_count = Column(Integer, nullable=True, default=None,
                           comment="Number of distinct speakers detected (requires diarization)")
    speakers_json = Column(Text, nullable=True, default=None,
                           comment="JSON array of speaker names/labels")
    transcription_model = Column(String(255), nullable=True, default=None,
                                  comment="Model used for transcription (e.g. gemini-2.5-flash, whisper-small)")
    has_diarization = Column(Boolean, default=False,
                             comment="Whether speaker diarization was applied")
    processing_time_ms = Column(Integer, nullable=True, default=None,
                                comment="Milliseconds taken for transcription")
    source_type = Column(String(20), nullable=True, default="audio",
                         comment="Source type: audio or video")
    word_count = Column(Integer, nullable=True, default=None,
                        comment="Total word count of transcript")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", backref=backref("audio_metadata", uselist=False))


class SystemPrompt(Base):
    """System prompts managed via the Admin Prompts page."""
    __tablename__ = "system_prompts"
    id = Column(Integer, primary_key=True, index=True)
    prompt_type = Column(String(50), index=True, nullable=False)  # chat, summary, extraction, classification, comparison
    content = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
