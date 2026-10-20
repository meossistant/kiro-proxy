import os
import shutil
from pathlib import Path
from pydantic import BaseModel

class Settings(BaseModel):
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    KIRO_CLI_PATH: str = os.getenv(
        "KIRO_CLI_PATH",
        shutil.which("kiro-cli") or os.path.expanduser("~/.local/bin/kiro-cli")
    )
    KIRO_AGENT: str = os.getenv("KIRO_AGENT", "generic")
    API_KEY: str | None = os.getenv("API_KEY") or os.getenv("KIRO_PROXY_API_KEY")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "auto")

settings = Settings()
