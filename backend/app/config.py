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

    # Demo mode: the synthetic dataset's SME emails aren't real inboxes, so
    # real Calendar invites would go nowhere. When DEMO_MODE=true, every
    # real invite's attendee is redirected to DEMO_CALENDAR_EMAIL instead of
    # the SME's own email, so a real person can receive and RSVP to invites
    # while testing. Set DEMO_MODE=false (and give SMEs real emails) for an
    # actual production SME pool. Never hardcoded -- always read from env.
    demo_mode: bool = os.getenv("DEMO_MODE", "true").lower() in ("1", "true", "yes")
    demo_calendar_email: str = os.getenv("DEMO_CALENDAR_EMAIL", os.getenv("GOOGLE_TEST_ATTENDEE_EMAIL", ""))

    demo_ops_id: str = os.getenv("DEMO_OPS_ID", "ops")
    demo_ops_password: str = os.getenv("DEMO_OPS_PASSWORD", "sessionops")

    # Comma-separated list of allowed frontend origins for CORS. Always
    # includes local dev; add the deployed frontend's origin via this env
    # var rather than hardcoding it, so the same backend works whether it's
    # being hit from localhost or a deployed Vercel URL.
    _extra_origins: str = os.getenv("CORS_ORIGINS", "")

    @property
    def cors_origins(self) -> list[str]:
        defaults = ["http://localhost:3000"]
        extra = [o.strip() for o in self._extra_origins.split(",") if o.strip()]
        return defaults + extra

    @property
    def is_live(self) -> bool:
        return self.integration_mode == "live"


@lru_cache
def get_settings() -> Settings:
    return Settings()
