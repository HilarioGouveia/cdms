from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo
import os

@dataclass(frozen=True)
class Settings:
    RULES_VERSION: str = "2.3.1"
    TIMEZONE_NAME: str = os.getenv("CDMS_TIMEZONE", "America/Sao_Paulo")
    
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    DB_PATH: Path = DATA_DIR / os.getenv("CDMS_DB_NAME", "cdms_dev.db")
    
    DEFAULT_CHANNEL: str = "primary_channel"
    DEFAULT_CONVERSION_GOAL: str = "leads_or_sales"

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.TIMEZONE_NAME)

    def ensure_directories(self) -> None:
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()