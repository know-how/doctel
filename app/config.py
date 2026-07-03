import os
import yaml
from typing import List, Optional, Any
from pydantic import BaseModel, Field
from pathlib import Path


def _strip_inline_env_comment(value: str) -> str:
    in_single = False
    in_double = False
    previous = ""

    for index, char in enumerate(value):
        if char == '"' and not in_single:
            in_double = not in_double
        elif char == "'" and not in_double:
            in_single = not in_single
        elif char == "#" and not in_single and not in_double:
            if index == 0 or previous.isspace():
                return value[:index].rstrip()
        previous = char

    return value.strip()

def _load_dotenv() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    try:
        raw = env_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return
    for line in raw:
        s = (line or "").strip()
        if not s or s.startswith("#"):
            continue
        if s.lower().startswith("export "):
            s = s[7:].strip()
        if "=" not in s:
            continue
        key, val = s.split("=", 1)
        key = key.strip()
        val = _strip_inline_env_comment(val)
        if not key or key in os.environ:
            continue
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        os.environ[key] = val

_load_dotenv()

def _load_yaml_config(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

class SecuritySettings(BaseModel):
    use_local_https: bool = False
    encrypt_sqlite: bool = True
    use_windows_efs: bool = True

class RbacSettings(BaseModel):
    roles: List[str] = ["admin", "analyst", "viewer"]
    auto_assign_uploader: bool = True

class PerformanceTargets(BaseModel):
    ten_page_pdf_seconds: int = 15

class PullSettings(BaseModel):
    max_retries: int = 3
    backoff_seconds: List[float] = [2, 4, 8]
    resume: bool = True

class BootstrapSettings(BaseModel):
    scan_paths: List[str] = []
    schedule_seconds: int = 90
    ocr: bool = True
    overwrite_existing_analysis: bool = False

class AuthSettings(BaseModel):
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    auto_signin_modal: bool = True

class UiPollSettings(BaseModel):
    ingest_ms: int = 1500
    pull_ms: int = 800

class UiSettings(BaseModel):
    enable_model_selector: bool = True
    enable_scope_switch: bool = True
    pull_modal: bool = True
    clear_input_on_send: bool = True
    allow_chat_while_ingesting: bool = True
    show_intro_animation: bool = True
    show_greeting_message: bool = True
    intro_duration_ms: int = 2400
    greeting_messages: List[str] = [
        "Powered up and ready!",
        "How can I support your workflow today?",
        "Let's get things done ⚡",
        "What would you like me to analyze for you?",
    ]
    poll: UiPollSettings = Field(default_factory=UiPollSettings)

class StorageSettings(BaseModel):
    upload_root: str = "C:\\LocalAI\\data\\uploads"
    processed_root: str = "C:\\LocalAI\\data\\processed"
    vector_root: str = "C:\\LocalAI\\data\\chroma"
    backup_days: int = 30
    organize_by_project: bool = True

class ZetdcSettings(BaseModel):
    system_prompt: str = ""
    tags: List[str] = []
    policy_template: str = ""
    allow_web_search: bool = False

class DiagnosticsSettings(BaseModel):
    log_level: str = "INFO"
    show_health: bool = True

class Settings(BaseModel):
    # Core
    base_dir: str = os.getenv("DOCINTEL_BASE_DIR", "C:\\LocalAI")
    environment: str = os.getenv("DOCINTEL_ENV", "development")
    offline_only: bool = os.getenv("DOCINTEL_OFFLINE_ONLY", "true").lower() == "true"
    bind_host: str = os.getenv("DOCINTEL_BIND_HOST", "127.0.0.1")
    port: int = int(os.getenv("DOCINTEL_PORT", "8000"))

    # LLM (Ollama based)
    text_model: str = os.getenv("DOCINTEL_TEXT_MODEL", "qwen3:4b")
    fallback_text_model: str = os.getenv("DOCINTEL_FALLBACK_TEXT_MODEL", "qwen3:4b")
    vision_model: str = os.getenv("DOCINTEL_VISION_MODEL", "llava:7b")
    embed_model: str = os.getenv("DOCINTEL_EMBED_MODEL", "nomic-embed-text")
    ollama_base_url: str = os.getenv("DOCINTEL_OLLAMA_BASE_URL", "http://localhost:11434")

    # Gemini API (external, free tier – add GEMINI_API_KEY to your .env)
    # Get a free key at: https://aistudio.google.com/apikey
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # DeepSeek API (using OpenCode Go proxy)
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash-free")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://opencode.ai/go/v1")

    # Model routing
    enable_qwen_9b: bool = os.getenv("DOCINTEL_ENABLE_QWEN_9B", "false").lower() == "true"
    qwen_9b_model: str = os.getenv("DOCINTEL_QWEN_9B_MODEL", "qwen3:8b")
    automatic_switching: bool = os.getenv("DOCINTEL_AUTOMATIC_SWITCHING", "true").lower() == "true"
    min_free_ram_for_8b_mb: int = int(os.getenv("DOCINTEL_MIN_FREE_RAM_FOR_8B_MB", "6000"))
    min_free_ram_for_qwen9b_mb: int = int(os.getenv("DOCINTEL_MIN_FREE_RAM_FOR_QWEN9B_MB", "7000"))

    available_models: List[str] = []
    default_model: str = os.getenv("DOCINTEL_DEFAULT_MODEL", "")
    pull: PullSettings = Field(default_factory=PullSettings)
    bootstrap: BootstrapSettings = Field(default_factory=BootstrapSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    ui: UiSettings = Field(default_factory=UiSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    zetdc: ZetdcSettings = Field(default_factory=ZetdcSettings)
    diagnostics: DiagnosticsSettings = Field(default_factory=DiagnosticsSettings)

    # Auth / AD (EC number + password)
    ad_url: str = os.getenv("DOCINTEL_AD_URL", "")
    ad_domain: str = os.getenv("DOCINTEL_AD_DOMAIN", "")
    ad_base_dn: str = os.getenv("DOCINTEL_AD_BASE_DN", "")
    ad_use_tls: bool = os.getenv("DOCINTEL_AD_USE_TLS", "false").lower() == "true"

    # Auth / Email OTP
    allowed_email_domain: str = os.getenv("DOCINTEL_ALLOWED_EMAIL_DOMAIN", "zetdc.co.zw")
    email_server_url: str = os.getenv("DOCINTEL_EMAIL_SERVER_URL", "")
    email_server_endpoint: str = os.getenv("DOCINTEL_EMAIL_SERVER_ENDPOINT", "/send")
    email_sender_email: str = os.getenv("DOCINTEL_EMAIL_SENDER_EMAIL", "")
    email_sender_password: str = os.getenv("DOCINTEL_EMAIL_SENDER_PASSWORD", "")
    email_sender_ews_url: str = os.getenv("DOCINTEL_EMAIL_SENDER_EWS_URL", "")
    # Optional direct SMTP
    smtp_host: str = os.getenv("DOCINTEL_SMTP_HOST", "")
    smtp_port: int = int(os.getenv("DOCINTEL_SMTP_PORT", "587"))
    smtp_user: str = os.getenv("DOCINTEL_SMTP_USER", "")
    smtp_pass: str = os.getenv("DOCINTEL_SMTP_PASS", "")
    smtp_use_tls: bool = os.getenv("DOCINTEL_SMTP_USE_TLS", "true").lower() == "true"

    # RAG parameters
    max_context_tokens: int = int(os.getenv("DOCINTEL_MAX_CONTEXT_TOKENS", "3000"))
    # chunk_size is in CHARACTERS (not tokens). At ~4 chars/token, the default
    # of 1000 chars ≈ 250 tokens – well within nomic-embed-text's 8192-token limit.
    # Raise to 2000–4000 for larger documents; lower to 500 for high-precision retrieval.
    chunk_size: int = int(os.getenv("DOCINTEL_CHUNK_SIZE", "1000"))
    chunk_overlap: int = int(os.getenv("DOCINTEL_CHUNK_OVERLAP", "150"))  # also chars
    top_k: int = int(os.getenv("DOCINTEL_TOP_K", "6"))
    use_mmr: bool = os.getenv("DOCINTEL_USE_MMR", "true").lower() == "true"

    # Security & RBAC
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    rbac: RbacSettings = Field(default_factory=RbacSettings)
    
    # Performance
    performance_targets: PerformanceTargets = Field(default_factory=PerformanceTargets)

    # Database
    database_url: str = os.getenv("DOCINTEL_DATABASE_URL", "")
    
    @property
    def db_url(self) -> str:
        # If MySQL is configured via environment variable, use it
        if self.database_url:
            return self.database_url
        # Otherwise fallback to SQLite
        db_path = Path(self.base_dir) / "db" / "app.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{db_path}"

    @property
    def chroma_path(self) -> str:
        path = Path(self.base_dir) / "data" / "chroma"
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    @property
    def uploads_dir(self) -> Path:
        path = Path(self.base_dir) / "data" / "uploads"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def ocr_dir(self) -> Path:
        path = Path(self.base_dir) / "data" / "ocr"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def projects_dir(self) -> Path:
        path = Path(self.base_dir) / "data" / "projects"
        path.mkdir(parents=True, exist_ok=True)
        return path

    # Legacy (for compatibility if needed during migration)
    cors_allow_origins: List[str] = ["*"]

def get_settings() -> Settings:
    root_dir = Path(__file__).resolve().parent
    yaml_path = root_dir / "config.yaml"
    yaml_data = _load_yaml_config(str(yaml_path))
    
    # Allow YAML to override environment variables
    return Settings(**yaml_data)

settings = get_settings()
