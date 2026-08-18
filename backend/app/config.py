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

    # Testing aid for live mode: the synthetic dataset's SME emails aren't
    # real inboxes, so real invites would go nowhere. When set, every real
    # Calendar invite's attendee is redirected to this address instead of
    # the SME's own email, so you can actually receive and RSVP to invites
    # while trying the app. Leave blank to use each SME's real email once
    # you're using real SME accounts.
    google_test_attendee_email: str = os.getenv("GOOGLE_TEST_ATTENDEE_EMAIL", "")

    demo_ops_id: str = os.getenv("DEMO_OPS_ID", "ops")
    demo_ops_password: str = os.getenv("DEMO_OPS_PASSWORD", "sessionops")

    @property
    def is_live(self) -> bool:
        return self.integration_mode == "live"


@lru_cache
def get_settings() -> Settings:
    return Settings()
