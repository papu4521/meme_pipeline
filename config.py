from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    GROQ_API_KEY: str
    OPENAI_API_KEY: str = ""
    SLACK_BOT_TOKEN: str
    SLACK_SIGNING_SECRET: str = ""
    SLACK_CHANNEL_ID: str
    DATABASE_URL: str = "sqlite+aiosqlite:///./meme_pipeline.db"
    POLL_INTERVAL: int = 60
    DEMO_MODE: bool = False
    BASE_URL: str = "http://localhost:8000"
    NVIDIA_API_KEY: str | None = None
    INSTAGRAM_ACCOUNT_ID: str = ""
    META_ACCESS_TOKEN: str = ""
    RSS_FEEDS: list[str] = [
        "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pWVXlnQVAB",
        "https://www.reddit.com/r/technology/.rss"
    ]

    @field_validator("POLL_INTERVAL")
    @classmethod
    def must_be_positive(cls, v):
        if v < 10:
            raise ValueError("POLL_INTERVAL must be at least 10 seconds")
        return v

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
