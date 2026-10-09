"""Local configuration for the dataset milestone."""
from pathlib import Path
from pydantic import BaseModel, ConfigDict


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    database: Path = Path("data/asvs.sqlite3")


MAX_DATASET_BYTES = 10 * 1024 * 1024
SUPPORTED_VERSION = "5.0.0"
