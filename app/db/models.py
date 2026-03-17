from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    ec_number = Column(String, index=True)
    email = Column(String, index=True)
    display_name = Column(String, default="")
    role = Column(String)  # admin, analyst, viewer
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owned_projects = relationship("Project", back_populates="owner")
    memberships = relationship("ProjectMember", back_populates="user")
    identity_providers = relationship("UserIdentityProvider", back_populates="user")

class UserIdentityProvider(Base):
    __tablename__ = "user_identity_providers"
    __table_args__ = (UniqueConstraint("provider", "identity", name="uq_identity_provider_identity"),)
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    provider = Column(String, index=True)  # ec_password|email_otp
    identity = Column(String, index=True)
    verified = Column(Boolean, default=False)
    last_login_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="identity_providers")

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="owned_projects")
    members = relationship("ProjectMember", back_populates="project")
    documents = relationship("Document", back_populates="project")
    sessions = relationship("Session", back_populates="project")

class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_members_project_user"),)
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    role_in_project = Column(String)

    project = relationship("Project", back_populates="members")
    user = relationship("User", back_populates="memberships")

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id"))
    filename = Column(String)
    path = Column(String)
    mime_type = Column(String)
    sha256 = Column(String, index=True)
    pages = Column(Integer)
    doc_type = Column(String)
    doc_date = Column(String)
    auto_project_confidence = Column(Float, default=0.0)
    needs_project_review = Column(Boolean, default=False)
    tags_json = Column(Text, default="[]")
    analysis_ready = Column(Boolean, default=False)
    ingestion_started = Column(Boolean, default=False)
    ingestion_completed = Column(Boolean, default=False)
    ingestion_failed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String, default="uploaded", index=True)
    ingest_step = Column(String, default="uploaded")
    ingest_percent = Column(Integer, default=0)
    ingest_message = Column(String, default="")
    error_message = Column(Text, default="")
    detected_type = Column(String, default="")
    updated_at = Column(Text, default="", server_default=func.now())

    project = relationship("Project", back_populates="documents")
    analysis = relationship("DocAnalysis", back_populates="document", uselist=False)
    prompts = relationship("SuggestedPrompt", back_populates="document")
    chunks = relationship("Chunk", back_populates="document")

class DocAnalysis(Base):
    __tablename__ = "doc_analysis"
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    executive_summary = Column(Text)
    detailed_summary = Column(Text)
    sentiment = Column(String)
    entities_json = Column(Text)  # JSON string
    topics_json = Column(Text)    # JSON string
    action_items_json = Column(Text)  # JSON string
    decisions_json = Column(Text)     # JSON string

    document = relationship("Document", back_populates="analysis")

class SuggestedPrompt(Base):
    __tablename__ = "suggested_prompts"
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    prompt_text = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="prompts")

class Chunk(Base):
    __tablename__ = "chunks"
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    project_id = Column(Integer, ForeignKey("projects.id"))
    chunk_index = Column(Integer)
    text = Column(Text)
    citation_ref = Column(String)
    embedding_id = Column(Integer, ForeignKey("embeddings.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="chunks")

class Embedding(Base):
    __tablename__ = "embeddings"
    id = Column(Integer, primary_key=True, index=True)
    vector_ref = Column(String)  # Chroma ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    session_uuid = Column(String, unique=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    document_id = Column(Integer, ForeignKey("documents.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    model_name = Column(String)
    title = Column(String, default="")
    scope = Column(String, default="document")  # global|project|document
    archived = Column(Boolean, default=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="sessions")
    messages = relationship("Message", back_populates="session")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    role = Column(String)  # user, assistant, system
    content = Column(Text)
    status = Column(String, default="done")  # pending, done, failed
    citations_json = Column(Text)  # JSON string
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("Session", back_populates="messages")

class Setting(Base):
    __tablename__ = "settings"
    key = Column(String, primary_key=True)
    value = Column(String)

class DocumentLink(Base):
    __tablename__ = "document_links"
    id = Column(Integer, primary_key=True, index=True)
    from_document_id = Column(Integer, ForeignKey("documents.id"))
    to_document_id = Column(Integer, ForeignKey("documents.id"))
    relation = Column(String)
    confidence = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Diagram(Base):
    __tablename__ = "diagrams"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    session_id = Column(Integer, ForeignKey("sessions.id"))
    title = Column(String)
    mermaid = Column(Text)
    drawing_prompt = Column(Text)
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SystemSetting(Base):
    __tablename__ = "system_settings"
    key = Column(String, primary_key=True)
    value_json = Column(Text)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by_user_id = Column(Integer, ForeignKey("users.id"))

class SettingsAudit(Base):
    __tablename__ = "settings_audit"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, index=True)
    old_value_json = Column(Text)
    new_value_json = Column(Text)
    changed_by_user_id = Column(Integer, ForeignKey("users.id"))
    changed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
