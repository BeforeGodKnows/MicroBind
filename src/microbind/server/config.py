import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    data: Path
    demo: Path
    token: str
    verify_enabled: bool = False
    max_upload: int = 50 * 1024 * 1024
    job_timeout: int = 1800
    samples: Path | None = None
    auth_required: bool = True

    @classmethod
    def env(cls):
        auth_required = os.getenv("MICROBIND_AUTH_REQUIRED", "1") != "0"
        secret = os.getenv("MICROBIND_TOKEN_FILE")
        token = ""
        if auth_required:
            token = Path(secret).read_text().strip() if secret else os.getenv("MICROBIND_TOKEN", "")
        if auth_required and len(token) < 24:
            raise ValueError("Set MICROBIND_TOKEN (24+ characters) or MICROBIND_TOKEN_FILE")
        return cls(
            Path(os.getenv("MICROBIND_DATA", "out/server")).resolve(),
            Path(os.getenv("MICROBIND_DEMO", "demo")).resolve(),
            token,
            os.getenv("MICROBIND_VERIFY_ENABLED", "0") == "1",
            job_timeout=int(os.getenv("MICROBIND_JOB_TIMEOUT", "1800")),
            samples=Path(os.getenv("MICROBIND_SAMPLES", "samples")).resolve(),
            auth_required=auth_required,
        )
