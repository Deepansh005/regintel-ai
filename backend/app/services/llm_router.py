import logging
import os
import threading
import time
import random
from dataclasses import dataclass
from typing import Optional

from groq import Groq

from app.core.config import GROQ_API_KEYS, refresh_groq_settings

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.1-8b-instant"
KEY_COOLDOWN_SECONDS = int(os.getenv("GROQ_KEY_COOLDOWN_SECONDS", "30"))
KEY_FAILURE_THRESHOLD = int(os.getenv("GROQ_KEY_FAILURE_THRESHOLD", "2"))
MAX_INPUT_CHARS = int(os.getenv("GROQ_MAX_INPUT_CHARS", "2500"))
MAX_OUTPUT_TOKENS = 800
STRICT_JSON_PROMPT = "Return ONLY valid JSON. No explanation. No markdown. No text outside JSON."


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
    invalid: bool = False
    invalid_reason: str = ""


_key_lock = threading.Lock()
_key_states: list[KeyState] = []


def _rebuild_key_pool(keys: list[str]) -> None:
    normalized = []
    for key in keys or []:
        value = str(key or "").strip().strip('"').strip("'")
        if value and value not in normalized:
            normalized.append(value)

    global _key_states
    _key_states = [KeyState(api_key=key, index=index) for index, key in enumerate(normalized)]

    logger.info(
        "Groq key pool loaded: count=%s keys=%s",
        len(_key_states),
        [_mask_key(state.api_key) for state in _key_states],
    )


def reload_key_pool(force_reload_env: bool = True) -> list[dict]:
    if force_reload_env:
        _, refreshed_keys = refresh_groq_settings()
    else:
        refreshed_keys = GROQ_API_KEYS

    with _key_lock:
        _rebuild_key_pool(refreshed_keys)

    return key_health_snapshot()


_rebuild_key_pool(GROQ_API_KEYS)


def _now() -> float:
    return time.time()


def _is_available(state: KeyState, now: float) -> bool:
    return (not state.invalid) and now >= state.cooldown_until


def _state_label(state: KeyState, now: float | None = None) -> str:
    ts = now if now is not None else _now()
    if state.invalid:
        return "INVALID"
    if ts < state.cooldown_until:
        return "COOLDOWN"
    return "ACTIVE"


def _select_state(
    prefer_least_used: bool = True,
    preferred_key_index: Optional[int] = None,
    excluded_indices: Optional[set[int]] = None,
) -> Optional[KeyState]:
    now = _now()
    excluded_indices = excluded_indices or set()
    available = [state for state in _key_states if _is_available(state, now) and state.index not in excluded_indices]

    if not available and excluded_indices:
        # If all available keys were excluded for this request, allow any available key.
        available = [state for state in _key_states if _is_available(state, now)]

    if not available:
        return None

    if preferred_key_index is not None:
        preferred = [state for state in available if state.index == preferred_key_index]
        if preferred:
            preferred.sort(key=lambda state: (state.active_calls, state.total_uses, state.last_used_at, state.index))
            return preferred[0]

    if prefer_least_used:
        available.sort(key=lambda state: (state.active_calls, state.total_uses, state.last_used_at, state.index))
        return available[0]

    # Randomly rotate across currently available keys to reduce synchronized cooldowns.
    least_active = min(state.active_calls for state in available)
    candidate_pool = [state for state in available if state.active_calls == least_active]
    return random.choice(candidate_pool)


def _min_cooldown_wait_seconds() -> float:
    if not _key_states:
        return 0.0
    now = _now()
    waits = [max(0.0, state.cooldown_until - now) for state in _key_states if not state.invalid]
    return min(waits) if waits else 0.0


def _has_active_or_cooldown_keys() -> bool:
    return any(not state.invalid for state in _key_states)


def get_next_api_key(
    prefer_least_used: bool = True,
    preferred_key_index: Optional[int] = None,
    excluded_indices: Optional[set[int]] = None,
    wait_for_key: bool = True,
) -> tuple[str, int]:
    while True:
        with _key_lock:
            state = _select_state(
                prefer_least_used=prefer_least_used,
                preferred_key_index=preferred_key_index,
                excluded_indices=excluded_indices,
            )

            if state is not None:
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

            if not _has_active_or_cooldown_keys():
                raise RuntimeError("No valid Groq API keys available (all keys invalid)")

        if not wait_for_key:
            raise RuntimeError("No Groq API key currently available")

        sleep_for = min(2.0, max(0.25, _min_cooldown_wait_seconds()))
        logger.info("All keys cooling briefly; waiting %.2fs for next available key", sleep_for)
        time.sleep(sleep_for)


def _truncate_message_content(content: str) -> str:
    value = str(content or "")
    if len(value) <= MAX_INPUT_CHARS:
        return value
    return value[:MAX_INPUT_CHARS]


def _prepare_messages_for_llm(messages: list[dict], enforce_json: bool = True) -> list[dict]:
    prepared = []
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "user")
        content = _truncate_message_content(str(message.get("content") or ""))
        prepared.append({"role": role, "content": content})

    if enforce_json:
        has_system = any(str(item.get("role") or "") == "system" for item in prepared)
        if has_system:
            for item in prepared:
                if str(item.get("role") or "") == "system":
                    item["content"] = f"{STRICT_JSON_PROMPT}\n\n{item.get('content') or ''}".strip()
                    break
        else:
            prepared.insert(0, {"role": "system", "content": STRICT_JSON_PROMPT})

    return prepared


def _release_api_key(api_key: str, success: bool = True, cooldown_seconds: int | None = None) -> None:
    with _key_lock:
        for state in _key_states:
            if state.api_key == api_key:
                state.active_calls = max(0, state.active_calls - 1)
                if state.invalid:
                    return
                if success:
                    state.failures = 0
                else:
                    state.failures += 1
                    if state.failures >= KEY_FAILURE_THRESHOLD:
                        state.cooldown_until = _now() + (cooldown_seconds or KEY_COOLDOWN_SECONDS)
                return


def _mark_key_cooldown(
    api_key: str,
    reason: str,
    cooldown_seconds: int | None = None,
    force: bool = False,
) -> None:
    with _key_lock:
        for state in _key_states:
            if state.api_key == api_key:
                state.active_calls = max(0, state.active_calls - 1)
                if state.invalid:
                    return
                state.failures += 1
                if force:
                    state.failures = max(state.failures, KEY_FAILURE_THRESHOLD)
                if state.failures >= KEY_FAILURE_THRESHOLD:
                    state.cooldown_until = _now() + (cooldown_seconds or KEY_COOLDOWN_SECONDS)
                logger.warning(
                    "Groq key index=%s cooled down reason=%s failures=%s cooldown_until=%s",
                    state.index,
                    reason,
                    state.failures,
                    state.cooldown_until,
                )
                return


def _mark_key_invalid(api_key: str, reason: str) -> None:
    with _key_lock:
        for state in _key_states:
            if state.api_key == api_key:
                state.active_calls = max(0, state.active_calls - 1)
                state.invalid = True
                state.invalid_reason = reason
                state.cooldown_until = 0.0
                state.failures = max(state.failures + 1, KEY_FAILURE_THRESHOLD)
                logger.error(
                    "Groq key index=%s marked INVALID reason=%s key=%s",
                    state.index,
                    reason,
                    _mask_key(state.api_key),
                )
                return


def _should_retry_with_next_key(exc: Exception) -> bool:
    message = str(exc).lower()
    return "429" in message or "rate_limit_exceeded" in message or "quota" in message or "tokens per minute" in message


def _is_auth_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "401" in message
        or "invalid api key" in message
        or "authentication" in message
        or "unauthorized" in message
    )


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
    retries: int = 2,
    initial_backoff: float = 1.5,
    model: str = GROQ_MODEL,
    preferred_key_index: Optional[int] = None,
    response_format: Optional[dict] = None,
) -> str:
    """Retry across available keys before giving up."""
    if not _key_states:
        logger.error("No Groq API keys configured")
        raise RuntimeError("No Groq API keys configured")

    last_error: Exception | None = None
    timeout_retry_used = False
    # Ensure we can try every available key at least once before failing.
    retries = max(1, retries, len(_key_states))
    max_tokens = min(max_tokens, MAX_OUTPUT_TOKENS)
    prepared_messages = _prepare_messages_for_llm(messages, enforce_json=True)
    attempted_key_indices: set[int] = set()

    for attempt in range(1, retries + 1):
        api_key = None
        key_index = None
        try:
            # Rotate key on each attempt; avoid retrying the same key immediately.
            exclude_for_attempt = set(attempted_key_indices)
            if len(exclude_for_attempt) >= len(_key_states):
                exclude_for_attempt = set()

            api_key, key_index = get_next_api_key(
                prefer_least_used=False,
                preferred_key_index=preferred_key_index,
                excluded_indices=exclude_for_attempt,
                wait_for_key=True,
            )

            attempted_key_indices.add(key_index)
            print("LLM CALLED")
            print(f"[LLM] Using key index: {key_index}")
            print(f"[LLM] Retry attempt: {attempt}")
            logger.info(
                "Groq request attempt=%s/%s key_index=%s preferred_key_index=%s model=%s",
                attempt,
                retries,
                key_index,
                preferred_key_index,
                model,
            )
            result = call_groq(
                prepared_messages,
                model=model,
                api_key=api_key,
                max_tokens=max_tokens,
                temperature=temperature,
            ) if response_format is None else _call_groq_with_format(
                messages=prepared_messages,
                model=model,
                api_key=api_key,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format=response_format,
            )

            _release_api_key(api_key, success=True)
            print("LLM RESPONSE:", result)
            return result
        except Exception as exc:
            last_error = exc
            logger.warning("Groq call failed attempt=%s/%s error=%s", attempt, retries, exc)

            if api_key:
                if _is_auth_error(exc):
                    _mark_key_invalid(api_key, reason=f"auth_error:{exc}")
                elif _should_retry_with_next_key(exc):
                    _mark_key_cooldown(api_key, reason=str(exc))
                elif _is_timeout_error(exc) and not timeout_retry_used:
                    timeout_retry_used = True
                    _release_api_key(api_key, success=False)
                else:
                    _release_api_key(api_key, success=False)

            if _is_auth_error(exc) or _should_retry_with_next_key(exc) or (_is_timeout_error(exc) and timeout_retry_used):
                continue

            if attempt < retries:
                time.sleep(initial_backoff * attempt)
                continue

    if last_error:
        logger.error("Groq failed after retries=%s error=%s", retries, last_error)
        raise RuntimeError(f"LLM failed after retries: {last_error}")
    raise RuntimeError("LLM failed after retries")


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
        raise RuntimeError(f"Pipeline failed before LLM response: {exc}") from exc


def key_health_snapshot() -> list[dict]:
    now = _now()
    with _key_lock:
        return [
            {
                "index": state.index,
                "masked_key": _mask_key(state.api_key),
                "available": (not state.invalid) and now >= state.cooldown_until,
                "state": _state_label(state, now),
                "cooldown_remaining": max(0.0, round(state.cooldown_until - now, 2)) if not state.invalid else 0.0,
                "failures": state.failures,
                "total_uses": state.total_uses,
                "active_calls": state.active_calls,
                "invalid_reason": state.invalid_reason,
            }
            for state in _key_states
        ]


def validate_keys_on_startup(model: str = GROQ_MODEL) -> dict:
    """Perform a lightweight probe for each key and mark unusable keys immediately."""
    startup_summary = {"total": 0, "usable": 0, "invalid": 0, "cooldown": 0}
    snapshot = key_health_snapshot()
    startup_summary["total"] = len(snapshot)

    for state in list(_key_states):
        masked = _mask_key(state.api_key)
        try:
            _ = call_groq(
                messages=[
                    {"role": "system", "content": "Return only valid JSON."},
                    {"role": "user", "content": '{"ok":true}'},
                ],
                model=model,
                api_key=state.api_key,
                max_tokens=16,
                temperature=0.0,
            )
            startup_summary["usable"] += 1
            logger.info("Startup validation success for key index=%s key=%s", state.index, masked)
        except Exception as exc:
            if _is_auth_error(exc):
                _mark_key_invalid(state.api_key, reason=f"startup_auth_error:{exc}")
                startup_summary["invalid"] += 1
            elif _should_retry_with_next_key(exc):
                _mark_key_cooldown(state.api_key, reason=f"startup_rate_limit:{exc}", force=True)
                startup_summary["cooldown"] += 1
            else:
                _mark_key_cooldown(state.api_key, reason=f"startup_other_error:{exc}", force=True)
                startup_summary["cooldown"] += 1

            logger.warning("Startup validation failed for key index=%s key=%s error=%s", state.index, masked, exc)

    logger.info("Groq startup key validation summary=%s", startup_summary)
    return startup_summary


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
