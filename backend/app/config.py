from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    aws_region: str = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "ap-south-1"))
    database_path: Path = Path(os.getenv("DATABASE_PATH", BASE_DIR / "data" / "platform.sqlite3"))
    report_dir: Path = Path(os.getenv("REPORT_DIR", BASE_DIR / "reports" / "out"))
    analyzer_name: str = os.getenv("ACCESS_ANALYZER_NAME", "dprp-external-analyzer")
    enable_scheduler: bool = os.getenv("ENABLE_SCHEDULER", "false").lower() == "true"
    local_timezone: str = os.getenv("LOCAL_TIMEZONE", "Asia/Kolkata")


settings = Settings()

