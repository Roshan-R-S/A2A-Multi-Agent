"""Planner configuration kept separate so the existing Settings API stays stable."""

import os

from dotenv import load_dotenv

from core.config import ROOT_DIR

load_dotenv(ROOT_DIR / ".env")

planner_agent_host = os.getenv("PLANNER_AGENT_HOST", "127.0.0.1")
planner_agent_port = int(os.getenv("PLANNER_AGENT_PORT", "8004"))
planner_agent_url = f"http://{planner_agent_host}:{planner_agent_port}"
