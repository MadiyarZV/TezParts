from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Telegram
    telegram_bot_token: str
    admin_chat_id: int

    # Anthropic
    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-5"

    # Brand voice
    business_name: str = "TezParts"
    niche_description: str = "автозапчасти"
    brand_voice_notes: str = ""

    # Scheduling
    daily_post_hour: int = 9
    daily_post_minute: int = 0

    # Storage
    database_url: str = "sqlite+aiosqlite:///./data/bot.db"


settings = Settings()
