import os
from pathlib import Path

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_ENV_PATH)


def _sanitize_env_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().strip('"').strip("'")
    return cleaned or None


GROQ_API_KEY: str | None = None
GROQ_API_KEYS: list[str] = []


def _collect_groq_api_keys() -> list[str]:
    worker_mode = os.getenv("AI_WORKER_MODE", "0").strip().lower() in {"1", "true", "yes", "on"}
    primary_key = _sanitize_env_value(os.getenv("GROQ_API_KEY")) or GROQ_API_KEY

    if worker_mode:
        return [value for value in [primary_key] if value]

    keys = []
    ordered_env_keys = [
        "GROQ_API_KEY_1",
        "GROQ_API_KEY_2",
        "GROQ_API_KEY_3",
        "GROQ_API_KEY_4",
        "GROQ_API_KEY_5",
    ]

    if primary_key:
        keys.append(primary_key)

    for env_name in ordered_env_keys:
        value = _sanitize_env_value(os.getenv(env_name))
        if value and value not in keys:
            keys.append(value)

    return keys


def refresh_groq_settings() -> tuple[str | None, list[str]]:
    global GROQ_API_KEY, GROQ_API_KEYS

    # Ensure updated .env values are picked up after reload/restart.
    load_dotenv(dotenv_path=_ENV_PATH, override=True)

    primary_key = _sanitize_env_value(os.getenv("GROQ_API_KEY"))
    if not primary_key:
        primary_key = (
            _sanitize_env_value(os.getenv("GROQ_API_KEY_1"))
            or _sanitize_env_value(os.getenv("GROQ_API_KEY_2"))
            or _sanitize_env_value(os.getenv("GROQ_API_KEY_3"))
            or _sanitize_env_value(os.getenv("GROQ_API_KEY_4"))
            or _sanitize_env_value(os.getenv("GROQ_API_KEY_5"))
        )

    GROQ_API_KEY = primary_key

    collected = _collect_groq_api_keys()
    GROQ_API_KEYS = [key.strip() for key in collected if key and key.strip()]

    return GROQ_API_KEY, GROQ_API_KEYS


refresh_groq_settings()

if not GROQ_API_KEY:
    raise ValueError(
        "Groq API key not configured. Set GROQ_API_KEY or one of GROQ_API_KEY_1..5 in .env"
    )