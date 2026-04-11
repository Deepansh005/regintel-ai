import os
from pathlib import Path

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    GROQ_API_KEY = (
        os.getenv("GROQ_API_KEY_1")
        or os.getenv("GROQ_API_KEY_2")
        or os.getenv("GROQ_API_KEY_3")
    )


def _collect_groq_api_keys() -> list[str]:
    worker_mode = os.getenv("AI_WORKER_MODE", "0").strip().lower() in {"1", "true", "yes", "on"}
    if worker_mode:
        return [value for value in [os.getenv("GROQ_API_KEY") or GROQ_API_KEY] if value]

    keys = []
    ordered_env_keys = [
        "GROQ_API_KEY_1",
        "GROQ_API_KEY_2",
        "GROQ_API_KEY_3",
        "GROQ_API_KEY_4",
        "GROQ_API_KEY_5",
    ]

    if GROQ_API_KEY:
        keys.append(GROQ_API_KEY)

    for env_name in ordered_env_keys:
        value = os.getenv(env_name)
        if value and value not in keys:
            keys.append(value)

    return keys


GROQ_API_KEYS = _collect_groq_api_keys()

if not GROQ_API_KEY:
    raise ValueError(
        "Groq API key not configured. Set GROQ_API_KEY or one of GROQ_API_KEY_1/2/3 in .env"
    )