import asyncio
import concurrent.futures
import logging
import os

from app.services.ai_service import analyze_impact as _local_analyze_impact
from app.services.ai_service import detect_changes as _local_detect_changes
from app.services.ai_service import detect_compliance_gaps as _local_detect_compliance_gaps
from app.services.ai_service import generate_actions as _local_generate_actions
from app.services.router import route_request

logger = logging.getLogger(__name__)

AI_ROUTER_ENABLED = os.getenv("AI_ROUTER_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}


def _raise_pipeline_error(endpoint: str, exc: Exception | None = None) -> None:
    detail = f"Pipeline failed before LLM response (endpoint={endpoint})"
    if exc is not None:
        detail = f"{detail}: {exc}"
    raise RuntimeError(detail)


def _run_async(coro):
    try:
        asyncio.get_running_loop()
        # If a loop is already running in this thread, execute in a helper thread.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)


def _route_or_fallback(endpoint: str, payload: dict, fallback_fn, *fallback_args):
    if not AI_ROUTER_ENABLED:
        logger.warning("AI router disabled, using local fallback for endpoint=%s", endpoint)
        try:
            return fallback_fn(*fallback_args)
        except Exception as exc:
            logger.error("Local fallback failed endpoint=%s error=%s", endpoint, exc)
            _raise_pipeline_error(endpoint, exc)

    try:
        logger.info("Routing AI request endpoint=%s", endpoint)
        return _run_async(route_request(endpoint=endpoint, payload=payload))
    except Exception as exc:
        logger.error("Router request failed for %s. Falling back local. error=%s", endpoint, exc)
        try:
            return fallback_fn(*fallback_args)
        except Exception as fallback_exc:
            logger.error("Router fallback failed endpoint=%s error=%s", endpoint, fallback_exc)
            _raise_pipeline_error(endpoint, fallback_exc)


def detect_changes(old_text: str, new_text: str) -> dict:
    payload = {"old_text": old_text, "new_text": new_text}
    return _route_or_fallback("/worker/detect-changes", payload, _local_detect_changes, old_text, new_text)


def detect_compliance_gaps(new_text: str, policy_text: str) -> dict:
    payload = {"new_text": new_text, "policy_text": policy_text}
    return _route_or_fallback(
        "/worker/detect-compliance-gaps",
        payload,
        _local_detect_compliance_gaps,
        new_text,
        policy_text,
    )


def analyze_impact(impact_input) -> dict:
    payload = {"impact_input": impact_input if isinstance(impact_input, dict) else {}}
    return _route_or_fallback("/worker/generate-impacts", payload, _local_analyze_impact, impact_input)


def generate_impacts(impact_input) -> dict:
    return analyze_impact(impact_input)


def generate_actions(actions_input) -> dict:
    payload = {"actions_input": actions_input}
    return _route_or_fallback("/worker/generate-actions", payload, _local_generate_actions, actions_input)
