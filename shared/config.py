"""Shared configuration and environment variable accessors for all agents."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Always load from career-agent/.env regardless of working directory
load_dotenv(Path(__file__).parent.parent / ".env")


def get_groq_api_key() -> str:
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        raise EnvironmentError("GROQ_API_KEY is not set in career-agent/.env")
    return key
