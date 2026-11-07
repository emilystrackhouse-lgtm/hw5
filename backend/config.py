"""Settings for the Campus Customs agent team, loaded once from .env in the project root (hw5/).

This is the only file that names the AI model. Homework 5 allows exactly one
model, gpt-6-luna through Portkey, so any other OPENAI_MODEL value is refused
instead of silently used.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")  # keep run output clean

# ---- AI model (Portkey) --------------------------------------------------
REQUIRED_MODEL = "gpt-6-luna"
DEFAULT_PORTKEY_BASE_URL = "https://api.portkey.ai/v1"


class ConfigError(RuntimeError):
    """A setting is missing or not allowed."""


def model_name() -> str:
    name = os.getenv("OPENAI_MODEL", REQUIRED_MODEL).strip()
    if name != REQUIRED_MODEL:
        raise ConfigError(
            f"OPENAI_MODEL is '{name}', but Homework 5 allows only '{REQUIRED_MODEL}' "
            "for every agent. Fix OPENAI_MODEL in .env."
        )
    return name


def portkey_api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise ConfigError("PORTKEY_API_KEY is missing. Add it to .env in the project root (hw5/).")
    return key


def portkey_base_url() -> str:
    return os.getenv("PORTKEY_BASE_URL", DEFAULT_PORTKEY_BASE_URL)


# ---- Files ---------------------------------------------------------------
def _project_path(value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else PROJECT_ROOT / p


ORIGINAL_DB_PATH = PROJECT_ROOT / "data" / "campus_customs.db"
WORKING_DB_PATH = _project_path(os.getenv("DB_PATH", "data/campus_customs_new.db"))
MCP_SERVER_SCRIPT = PROJECT_ROOT / "mcp_server" / "server.py"
AUDIT_PATH = _project_path(os.getenv("AUDIT_PATH", "output/audit_trail.json"))
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


# ---- Token and loop limits (one ticket run, all agents combined) ----------
def _int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


RUN_TOTAL_TOKENS_LIMIT = _int("RUN_TOTAL_TOKENS_LIMIT", 150_000)  # whole ticket, every agent
RUN_REQUEST_LIMIT = _int("RUN_REQUEST_LIMIT", 40)                 # model calls per ticket
RUN_TOOL_CALLS_LIMIT = _int("RUN_TOOL_CALLS_LIMIT", 60)           # MCP + delegation calls per ticket
MAX_OUTPUT_TOKENS = _int("MAX_OUTPUT_TOKENS", 1_500)              # per model reply
MAX_DELEGATION_DEPTH = _int("MAX_DELEGATION_DEPTH", 2)            # Boss -> A -> B, no deeper
MAX_DELEGATIONS_PER_RUN = _int("MAX_DELEGATIONS_PER_RUN", 10)
AUDIT_TEXT_LIMIT = _int("AUDIT_TEXT_LIMIT", 4_000)                # chars kept per logged field
