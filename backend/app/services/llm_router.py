import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Optional

from groq import Groq

from app.core.config import GROQ_API_KEYS

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.1-8b-instant"
KEY_COOLDOWN_SECONDS = int(os.getenv("GROQ_KEY_COOLDOWN_SECONDS", "30"))


def _mask_key(api_key: str) -> str:
    value = api_key or ""
    if len(value) <= 5:
        return value
    return f"{value[:5]}***"


@dataclass
class KeyState:
    api_key: str
    index: int
    active_calls: int = 0
    failures: int = 0
    cooldown_until: float = 0.0
    last_used_at: float = 0.0
    total_uses: int = 0


_key_lock = threading.Lock()
_key_states: list[KeyState] = [KeyState(api_key=key, index=index) for index, key in enumerate(GROQ_API_KEYS)]
_round_robin_index = 0

logger.info(
    "Groq key pool loaded: count=%s keys=%s",
    len(_key_states),
    [_mask_key(state.api_key) for state in _key_states],
)


def _now() -> float:
    return time.time()


def _is_available(state: KeyState, now: float) -> bool:
    return now >= state.cooldown_until


def _select_state(prefer_least_used: bool = True, preferred_key_index: Optional[int] = None) -> KeyState:
    now = _now()
    available = [state for state in _key_states if _is_available(state, now)]
    if not available:
        raise RuntimeError("No Groq API keys available. All keys are cooling down.")

    if preferred_key_index is not None:
        preferred = [state for state in available if state.index == preferred_key_index]
        if preferred:
            preferred.sort(key=lambda state: (state.active_calls, state.total_uses, state.last_used_at, state.index))
            return preferred[0]

    if prefer_least_used:
        available.sort(key=lambda state: (state.active_calls, state.total_uses, state.last_used_at, state.index))
        return available[0]

    global _round_robin_index
    available.sort(key=lambda state: (state.active_calls, state.total_uses, state.last_used_at, state.index))
    selected = available[_round_robin_index % len(available)]
    _round_robin_index = (_round_robin_index + 1) % max(1, len(available))
    return selected


def get_next_api_key(prefer_least_used: bool = True, preferred_key_index: Optional[int] = None) -> tuple[str, int]:
    with _key_lock:
        state = _select_state(prefer_least_used=prefer_least_used, preferred_key_index=preferred_key_index)
        state.active_calls += 1
        state.last_used_at = _now()
        state.total_uses += 1
        logger.info(
            "Using API key index: %s masked=%s active_calls=%s",
            state.index,
            _mask_key(state.api_key),
            state.active_calls,
        )
        return state.api_key, state.index


def _release_api_key(api_key: str, success: bool = True, cooldown_seconds: int | None = None) -> None:
    with _key_lock:
        for state in _key_states:
            if state.api_key == api_key:
                state.active_calls = max(0, state.active_calls - 1)
                if success:
                    state.failures = 0
                else:
                    state.failures += 1
                    state.cooldown_until = _now() + (cooldown_seconds or KEY_COOLDOWN_SECONDS)
                return


def _mark_key_cooldown(api_key: str, reason: str, cooldown_seconds: int | None = None) -> None:
    with _key_lock:
        for state in _key_states:
            if state.api_key == api_key:
                state.failures += 1
                state.cooldown_until = _now() + (cooldown_seconds or KEY_COOLDOWN_SECONDS)
                logger.warning(
                    "Groq key index=%s cooled down reason=%s failures=%s cooldown_until=%s",
                    state.index,
                    reason,
                    state.failures,
                    state.cooldown_until,
                )
                return


def _should_retry_with_next_key(exc: Exception) -> bool:
    message = str(exc).lower()
    return "429" in message or "rate_limit_exceeded" in message or "quota" in message or "tokens per minute" in message


def _is_timeout_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "timeout" in message or "timed out" in message


def call_groq(messages: list[dict], model: str, api_key: str, max_tokens: int = 1000, temperature: float = 0.0) -> str:
    """Initialize the Groq client per call so the API key is never stale."""
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = (response.choices[0].message.content or "") if response and response.choices else ""
    if not content:
        raise RuntimeError("Groq API returned empty content")
    return content


def call_groq_with_retry(
    messages: list[dict],
    max_tokens: int = 1000,
    temperature: float = 0.0,
    retries: int = 3,
    initial_backoff: float = 1.5,
    model: str = GROQ_MODEL,
    preferred_key_index: Optional[int] = None,
    response_format: Optional[dict] = None,
) -> str:
    """Retry across available keys before giving up."""
    last_error: Exception | None = None
    timeout_retry_used = False

    for attempt in range(1, retries + 1):
        api_key = None
        try:
            api_key, key_index = get_next_api_key(
                prefer_least_used=True,
                preferred_key_index=preferred_key_index,
            )
            logger.info(
                "Groq request attempt=%s/%s key_index=%s preferred_key_index=%s model=%s",
                attempt,
                retries,
                key_index,
                preferred_key_index,
                model,
            )
            result = call_groq(
                messages,
                model=model,
                api_key=api_key,
                max_tokens=max_tokens,
                temperature=temperature,
            ) if response_format is None else _call_groq_with_format(
                messages=messages,
                model=model,
                api_key=api_key,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format=response_format,
            )
            _release_api_key(api_key, success=True)
            return result
        except Exception as exc:
            last_error = exc
            logger.warning("Groq call failed attempt=%s/%s error=%s", attempt, retries, exc)

            if api_key:
                if _should_retry_with_next_key(exc):
                    _mark_key_cooldown(api_key, reason=str(exc))
                elif _is_timeout_error(exc) and not timeout_retry_used:
                    timeout_retry_used = True
                    _release_api_key(api_key, success=False, cooldown_seconds=5)
                else:
                    _release_api_key(api_key, success=False, cooldown_seconds=5)

            if _should_retry_with_next_key(exc) or (_is_timeout_error(exc) and timeout_retry_used):
                continue

            if attempt < retries:
                time.sleep(initial_backoff * attempt)
                continue

    if last_error:
        raise RuntimeError(f"Groq failed after {retries} retries: {last_error}") from last_error

    raise RuntimeError("Groq failed unexpectedly without an error")


def llm_chat_completion(
    task_type: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1000,
    temperature: float = 0.0,
    retries: int = 2,
    timeout_seconds: int = 45,
) -> Optional[str]:
    """
    Backward-compatible wrapper used by existing services.

    timeout_seconds is kept for interface compatibility; requests are handled
    by the Groq client and higher-level callers manage their own timeouts.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        return call_groq_with_retry(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            retries=max(1, retries),
            initial_backoff=0.5,
            model=GROQ_MODEL,
        )
    except Exception as exc:
        logger.error("Groq call for task '%s' failed: %s", task_type, exc)
        raise RuntimeError(f"Groq failed for task '{task_type}': {exc}") from exc


def key_health_snapshot() -> list[dict]:
    now = _now()
    with _key_lock:
        return [
            {
                "index": state.index,
                "masked_key": _mask_key(state.api_key),
                "available": now >= state.cooldown_until,
                "cooldown_remaining": max(0.0, round(state.cooldown_until - now, 2)),
                "failures": state.failures,
                "total_uses": state.total_uses,
                "active_calls": state.active_calls,
            }
            for state in _key_states
        ]


def _call_groq_with_format(
    messages: list[dict],
    model: str,
    api_key: str,
    max_tokens: int,
    temperature: float,
    response_format: dict,
) -> str:
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
    )
    content = (response.choices[0].message.content or "") if response and response.choices else ""
    if not content:
        raise RuntimeError("Groq API returned empty content")
    return content
