"""
Configuration Management for SaaS RAG Chatbot Application

This module handles all application configuration including:
- Environment variables
- Database configuration
- Qdrant vector store configuration
- Security settings (JWT, CORS)
- File upload constraints
- Multi-tenancy settings
- Rate limiting
"""

from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator
import os
from pathlib import Path


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Uses Pydantic BaseSettings for automatic validation and type conversion.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # ============================================================================
    # APPLICATION SETTINGS
    # ============================================================================
    APP_NAME: str = "RAG Chatbot SaaS Platform"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    
    # ============================================================================
    # SERVER SETTINGS
    # ============================================================================
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = True
    
    # ============================================================================
    # DATABASE SETTINGS (PostgreSQL)
    # ============================================================================
    POSTGRES_USER: str = Field(..., env="POSTGRES_USER")
    POSTGRES_PASSWORD: str = Field(..., env="POSTGRES_PASSWORD")
    POSTGRES_HOST: str = Field(default="localhost", env="POSTGRES_HOST")
    POSTGRES_PORT: int = Field(default=5432, env="POSTGRES_PORT")
    POSTGRES_DB: str = Field(..., env="POSTGRES_DB")
    
    # SQLAlchemy configuration
    DATABASE_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 3600
    
    @property
    def DATABASE_URL(self) -> str:
        """Construct PostgreSQL connection URL"""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
    
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Construct async PostgreSQL connection URL"""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
    
    # ============================================================================
    # QDRANT VECTOR STORE SETTINGS
    # ============================================================================
    QDRANT_HOST: str = Field(default="localhost", env="QDRANT_HOST")
    QDRANT_PORT: int = Field(default=6333, env="QDRANT_PORT")
    QDRANT_GRPC_PORT: int = Field(default=6334, env="QDRANT_GRPC_PORT")
    QDRANT_API_KEY: Optional[str] = Field(default=None, env="QDRANT_API_KEY")
    QDRANT_PREFER_GRPC: bool = Field(default=False, env="QDRANT_PREFER_GRPC")
    QDRANT_USE_HTTPS: bool = Field(default=False, env="QDRANT_USE_HTTPS")
    QDRANT_DEFAULT_COLLECTION_NAME: str = Field(default='default_collection', env="QDRANT_DEFAULT_COLLECTION_NAME")
    
    # Vector settings
    EMBEDDING_DIMENSION: int = 384  # all-MiniLM-L6-v2 dimension
    VECTOR_DISTANCE_METRIC: str = "Cosine"
    

    # ============================================================================
    # SECURITY SETTINGS
    # ============================================================================
    # JWT Configuration
    JWT_SECRET_KEY: str = Field(..., env="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 180  # 3 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Password hashing
    PASSWORD_MIN_LENGTH: int = 6
    PASSWORD_REQUIRE_UPPERCASE: bool = False
    PASSWORD_REQUIRE_LOWERCASE: bool = False
    PASSWORD_REQUIRE_DIGIT: bool = False
    PASSWORD_REQUIRE_SPECIAL: bool = False
    
    # CORS Configuration
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        env="CORS_ORIGINS"
    )
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    # ============================================================================
    # RATE LIMITING SETTINGS
    # ============================================================================
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    WIDGET_RATE_LIMIT_PER_MINUTE: int = 20
    
    # ============================================================================
    # FILE UPLOAD CONSTRAINTS
    # ============================================================================
    MAX_FILE_SIZE_MB: int = 30
    MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024
    ALLOWED_DOCUMENT_TYPES: List[str] = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown"
    ]
    ALLOWED_FILE_EXTENSIONS: List[str] = [".pdf", ".docx", ".txt", ".md"]
    
    # Upload directories
    UPLOAD_DIR: str = "uploaded_documents"
    EMBEDDING_MODELS_DIR: str = "embedding_models"
    QDRANT_DATA_DIR: str = "qdrant_embeddings_data"
    
    # ============================================================================
    # KNOWLEDGE BASE SETTINGS
    # ============================================================================
    MAX_PAGES_TO_SCRAPE: int = 100
    MAX_DOCUMENTS_PER_BOT: int = 50
    MAX_KNOWLEDGE_SOURCES_PER_BOT: int = 100
    
    # Text chunking
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    EMBEDDING_BATCH_SIZE: int = 32
    
    # Web scraping
    SCRAPER_TIMEOUT_SECONDS: int = 30
    SCRAPER_MAX_RETRIES: int = 3
    SCRAPER_USER_AGENT: str = "RAGChatbotSaaS/1.0 (Web Crawler)"
    RESPECT_ROBOTS_TXT: bool = True  # Respect robots.txt by default
    
    # ============================================================================
    # MULTI-TENANCY SETTINGS
    # ============================================================================
    ENABLE_MULTI_TENANCY: bool = True
    DEFAULT_PLAN: str = "free"
    
    # Plan limits
    FREE_PLAN_LIMITS: dict = {
        "max_bots": 1,
        "max_messages_per_month": 100,
        "max_storage_mb": 50,
        "max_knowledge_sources": 5
    }
    
    PRO_PLAN_LIMITS: dict = {
        "max_bots": 5,
        "max_messages_per_month": 1000,
        "max_storage_mb": 500,
        "max_knowledge_sources": 50
    }
    
    ENTERPRISE_PLAN_LIMITS: dict = {
        "max_bots": -1,  # Unlimited
        "max_messages_per_month": -1,
        "max_storage_mb": -1,
        "max_knowledge_sources": -1
    }
    
    # ============================================================================
    # LLM SETTINGS (OpenAI)
    # ============================================================================
    OPENAI_API_KEY: str = Field(..., env="OPENAI_API_KEY")
    OPENAI_BASE_URL: str = Field(default="https://api.openai.com/v1", env="OPENAI_BASE_URL")
    OPENAI_ORGANIZATION: Optional[str] = Field(default=None, env="OPENAI_ORGANIZATION")
    DEFAULT_LLM_MODEL: str = Field(default="mistralai/mistral-small-3.1-24b-instruct:free", env="DEFAULT_LLM_MODEL")
    DEFAULT_LLM_TEMPERATURE: float = Field(default=0.7, env="DEFAULT_LLM_TEMPERATURE")
    DEFAULT_MAX_TOKENS: int = Field(default=500, env="DEFAULT_MAX_TOKENS")
    LLM_TIMEOUT_SECONDS: int = Field(default=60, env="LLM_TIMEOUT_SECONDS")
    
    # Available models for different use cases
    AVAILABLE_MODELS: List[str] = Field(
        default=[
            "mistralai/mistral-small-3.1-24b-instruct:free",
            "meta-llama/llama-3.3-8b-instruct:free",
            "deepseek/deepseek-chat-v3.1:free",
            "qwen/qwen3-235b-a22b:free",
            "openai/gpt-oss-20b:free",
            "gpt-4-turbo",
            "gpt-3.5-turbo"
        ],
        env="AVAILABLE_MODELS"
    )
    
    # ============================================================================
    # EMBEDDING MODEL SETTINGS
    # ============================================================================
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DEVICE: str = "cpu"  # or "cuda" for GPU
    EMBEDDING_NORMALIZE: bool = True
    
    # ============================================================================
    # RETRIEVAL SETTINGS
    # ============================================================================
    DEFAULT_TOP_K: int = 5
    SIMILARITY_THRESHOLD: float = 0.7
    HYBRID_SEARCH_ALPHA: float = 0.5  # 0.5 = equal weight to vector and BM25
    
    # ============================================================================
    # EMAIL SETTINGS (for notifications and verification)
    # ============================================================================
    SMTP_HOST: str = Field(default="smtp.gmail.com", env="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, env="SMTP_PORT")
    SMTP_USER: str = Field(default="", env="SMTP_USER")
    SMTP_PASSWORD: str = Field(default="", env="SMTP_PASSWORD")
    SMTP_TLS: bool = True
    EMAIL_FROM: str = Field(default="noreply@ragchatbot.com", env="EMAIL_FROM")
    EMAIL_FROM_NAME: str = "RAG Chatbot SaaS"
    
    # Email verification
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = 1
    
    # ============================================================================
    # FRONTEND SETTINGS
    # ============================================================================
    FRONTEND_URL: str = Field(default="http://localhost:3000", env="FRONTEND_URL")
    
    # ============================================================================
    # MONITORING & LOGGING
    # ============================================================================
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    ENABLE_REQUEST_LOGGING: bool = True
    
    # Sentry (optional)
    SENTRY_DSN: Optional[str] = Field(default=None, env="SENTRY_DSN")
    
    # ============================================================================
    # FEATURE FLAGS
    # ============================================================================
    ENABLE_EMAIL_VERIFICATION: bool = False # For production, set to True
    ENABLE_ANALYTICS: bool = False # For production, set to True
    ENABLE_WEBSOCKET: bool = False # For production, set to True
    ENABLE_STREAMING_RESPONSES: bool = False # For production, set to True
    
    # ============================================================================
    # LEMON SQUEEZY SETTINGS (Billing)
    # ============================================================================
    LEMONSQUEEZY_API_KEY: Optional[str] = Field(default=None, env="LEMONSQUEEZY_API_KEY")
    LEMONSQUEEZY_STORE_ID: Optional[str] = Field(default=None, env="LEMONSQUEEZY_STORE_ID")
    LEMONSQUEEZY_WEBHOOK_SECRET: Optional[str] = Field(default=None, env="LEMONSQUEEZY_WEBHOOK_SECRET")
    LEMONSQUEEZY_BASE_URL: str = Field(default="https://api.lemonsqueezy.com/v1", env="LEMONSQUEEZY_BASE_URL")
    
    # Product and variant IDs for different plans
    LEMONSQUEEZY_FREE_VARIANT_ID: Optional[str] = Field(default=None, env="LEMONSQUEEZY_FREE_VARIANT_ID")
    LEMONSQUEEZY_PRO_VARIANT_ID: Optional[str] = Field(default=None, env="LEMONSQUEEZY_PRO_VARIANT_ID")
    LEMONSQUEEZY_ENTERPRISE_VARIANT_ID: Optional[str] = Field(default=None, env="LEMONSQUEEZY_ENTERPRISE_VARIANT_ID")
    
    # Checkout configuration
    LEMONSQUEEZY_CHECKOUT_SUCCESS_URL: Optional[str] = Field(default=None, env="LEMONSQUEEZY_CHECKOUT_SUCCESS_URL")
    LEMONSQUEEZY_CHECKOUT_CANCEL_URL: Optional[str] = Field(default=None, env="LEMONSQUEEZY_CHECKOUT_CANCEL_URL")
    
    # ============================================================================
    # PATHS
    # ============================================================================
    @property
    def BASE_DIR(self) -> Path:
        """Get the base directory of the project"""
        return Path(__file__).resolve().parent.parent
    
    @property
    def UPLOAD_PATH(self) -> Path:
        """Get the upload directory path"""
        path = self.BASE_DIR / self.UPLOAD_DIR
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def EMBEDDING_MODELS_PATH(self) -> Path:
        """Get the embedding models directory path"""
        path = self.BASE_DIR / self.EMBEDDING_MODELS_DIR
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def QDRANT_DATA_PATH(self) -> Path:
        """Get the Qdrant data directory path"""
        path = self.BASE_DIR / self.QDRANT_DATA_DIR
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    # ============================================================================
    # VALIDATION
    # ============================================================================
    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}")
        return v
    
    @validator("CHUNK_SIZE")
    def validate_chunk_size(cls, v):
        if v < 100 or v > 2000:
            raise ValueError("CHUNK_SIZE must be between 100 and 2000")
        return v
    
    @validator("CHUNK_OVERLAP")
    def validate_chunk_overlap(cls, v, values):
        if "CHUNK_SIZE" in values and v >= values["CHUNK_SIZE"]:
            raise ValueError("CHUNK_OVERLAP must be less than CHUNK_SIZE")
        return v


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================
settings = Settings()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def get_settings() -> Settings:
    """
    Dependency injection helper for FastAPI routes.
    Returns the global settings instance.
    """
    return settings


def is_production() -> bool:
    """Check if running in production environment"""
    return settings.ENVIRONMENT == "production"


def is_development() -> bool:
    """Check if running in development environment"""
    return settings.ENVIRONMENT == "development"


# ============================================================================
# EXPORT
# ============================================================================
__all__ = [
    "Settings",
    "settings",
    "get_settings",
    "is_production",
    "is_development"
]

