from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    groq_api_key: str = ""
    demo_mode: bool = False
    cv_directory: str = "./data/cvs"
    claude_model: str = "claude-sonnet-4-6"
    haiku_model: str = "claude-haiku-4-5-20251001"
    groq_model: str = "llama-3.1-8b-instant"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    qdrant_url: str = "http://localhost:6333"

    model_config = {"env_file": ".env"}

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def llm_backend(self) -> str:
        if self.demo_mode:
            return "demo"
        if self.groq_api_key:
            return "groq"
        if self.anthropic_api_key:
            return "anthropic"
        return "demo"


settings = Settings()
