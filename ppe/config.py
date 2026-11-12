"""Environment configuration; credentials are never included in representations."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    pdf_dir: Path
    azure_endpoint: str
    azure_deployment: str
    api_version: str
    api_key: str = field(repr=False)
    reasoning_effort: str | None = "medium"
    tracing_enabled: bool = True
    trace_content: bool = False
    tracking_uri: str = "http://127.0.0.1:5001"
    experiment: str = "ppe-comparison"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(ROOT / ".env", override=False)
        return cls(
            pdf_dir=Path(os.getenv("PPE_PDF_DIR", str(ROOT / "info/KID"))).resolve(),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/"),
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "").strip(),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "").strip(),
            api_key=os.getenv("AZURE_OPENAI_API_KEY", "").strip(),
            reasoning_effort=os.getenv(
                "AZURE_OPENAI_REASONING_EFFORT", "medium"
            ).strip()
            or None,
            tracing_enabled=os.getenv("PPE_TRACING_ENABLED", "true").strip().lower()
            in {"1", "true", "yes"},
            trace_content=os.getenv("PPE_TRACE_CONTENT", "false").strip().lower()
            in {"1", "true", "yes"},
            tracking_uri=os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5001"),
            experiment=os.getenv("MLFLOW_EXPERIMENT_NAME", "ppe-comparison"),
        )

    @property
    def model_ready(self) -> bool:
        return bool(
            self.azure_endpoint
            and self.azure_deployment
            and self.api_version
            and self.api_key
        )
