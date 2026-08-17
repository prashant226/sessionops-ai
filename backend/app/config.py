import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    integration_mode: str = os.getenv("INTEGRATION_MODE", "mock")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./sessionops.db")

    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_redirect_uri: str = os.getenv("GOOGLE_REDIRECT_URI", "")
    google_sheets_spreadsheet_id: str = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    demo_ops_id: str = os.getenv("DEMO_OPS_ID", "ops")
    demo_ops_password: str = os.getenv("DEMO_OPS_PASSWORD", "sessionops")

    @property
    def is_live(self) -> bool:
        return self.integration_mode == "live"


@lru_cache
def get_settings() -> Settings:
    return Settings()
