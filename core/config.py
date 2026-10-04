from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]

load_dotenv(ROOT_DIR / ".env")


def require_env(name: str) -> str:
    value = os.getenv(name)

    if not value or not value.strip():
        raise RuntimeError(
            f"Missing required environment variable: {name}"
        )

    return value.strip()


@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    groq_model: str

    research_agent_host: str
    research_agent_port: int

    writer_agent_host: str
    writer_agent_port: int

    verifier_agent_host: str
    verifier_agent_port: int

    @property
    def research_agent_url(self) -> str:
        return (
            f"http://{self.research_agent_host}:"
            f"{self.research_agent_port}"
        )

    @property
    def writer_agent_url(self) -> str:
        return (
            f"http://{self.writer_agent_host}:"
            f"{self.writer_agent_port}"
        )

    @property
    def verifier_agent_url(self) -> str:
        return (
            f"http://{self.verifier_agent_host}:"
            f"{self.verifier_agent_port}"
        )


settings = Settings(
    groq_api_key=require_env("GROQ_API_KEY"),

    groq_model=os.getenv(
        "GROQ_MODEL",
        "openai/gpt-oss-120b",
    ),

    research_agent_host=os.getenv(
        "RESEARCH_AGENT_HOST",
        "127.0.0.1",
    ),
    research_agent_port=int(
        os.getenv(
            "RESEARCH_AGENT_PORT",
            "8001",
        )
    ),

    writer_agent_host=os.getenv(
        "WRITER_AGENT_HOST",
        "127.0.0.1",
    ),
    writer_agent_port=int(
        os.getenv(
            "WRITER_AGENT_PORT",
            "8002",
        )
    ),

    verifier_agent_host=os.getenv(
        "VERIFIER_AGENT_HOST",
        "127.0.0.1",
    ),
    verifier_agent_port=int(
        os.getenv(
            "VERIFIER_AGENT_PORT",
            "8003",
        )
    ),
)