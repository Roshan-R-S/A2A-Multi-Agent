import os


os.environ.setdefault(
    "GROQ_API_KEY",
    "test-api-key",
)

os.environ.setdefault(
    "GROQ_MODEL",
    "openai/gpt-oss-120b",
)

os.environ.setdefault(
    "RESEARCH_AGENT_HOST",
    "127.0.0.1",
)

os.environ.setdefault(
    "RESEARCH_AGENT_PORT",
    "8001",
)

os.environ.setdefault(
    "WRITER_AGENT_HOST",
    "127.0.0.1",
)

os.environ.setdefault(
    "WRITER_AGENT_PORT",
    "8002",
)
os.environ.setdefault(
    "VERIFIER_AGENT_HOST",
    "127.0.0.1",
)

os.environ.setdefault(
    "VERIFIER_AGENT_PORT",
    "8003",
)