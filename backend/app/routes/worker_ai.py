import asyncio
import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.ai_service import analyze_impact
from app.services.ai_service import detect_changes
from app.services.ai_service import detect_compliance_gaps
from app.services.ai_service import detect_regulatory_changes_new
from app.services.ai_service import generate_actions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/worker", tags=["worker-ai"])

MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "2"))
_worker_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)


class DetectChangesPayload(BaseModel):
    old_text: str
    new_text: str


class DetectGapsPayload(BaseModel):
    new_text: str
    policy_text: str
    changes: list[dict] | None = None


class ImpactPayload(BaseModel):
    impact_input: dict


class ActionsPayload(BaseModel):
    actions_input: dict | list


async def _run_limited(func, *args):
    async with _worker_semaphore:
        return await asyncio.to_thread(func, *args)


@router.get("/health")
async def worker_health():
    return {
        "status": "healthy",
        "max_concurrent_requests": MAX_CONCURRENT_REQUESTS,
        "available_slots": _worker_semaphore._value,
    }


@router.post("/detect-changes")
async def worker_detect_changes(payload: DetectChangesPayload):
    try:
        return await _run_limited(detect_changes, payload.old_text, payload.new_text)
    except Exception as exc:
        logger.error("worker detect_changes failed: %s", exc)
        raise HTTPException(status_code=500, detail="LLM pipeline failed") from exc


@router.post("/detect-changes-new")
async def worker_detect_changes_new(payload: DetectChangesPayload):
    """NEW SYSTEM: Semantic block-based change detection."""
    try:
        return await _run_limited(detect_regulatory_changes_new, payload.old_text, payload.new_text)
    except Exception as exc:
        logger.error("worker detect_changes_new failed: %s", exc)
        raise HTTPException(status_code=500, detail="LLM pipeline failed") from exc


@router.post("/detect-compliance-gaps")
async def worker_detect_compliance_gaps(payload: DetectGapsPayload):
    try:
        return await _run_limited(detect_compliance_gaps, payload.new_text, payload.policy_text, payload.changes)
    except Exception as exc:
        logger.error("worker detect_compliance_gaps failed: %s", exc)
        raise HTTPException(status_code=500, detail="LLM pipeline failed") from exc


@router.post("/generate-impacts")
async def worker_generate_impacts(payload: ImpactPayload):
    try:
        return await _run_limited(analyze_impact, payload.impact_input)
    except Exception as exc:
        logger.error("worker generate_impacts failed: %s", exc)
        raise HTTPException(status_code=500, detail="LLM pipeline failed") from exc


@router.post("/generate-actions")
async def worker_generate_actions(payload: ActionsPayload):
    try:
        return await _run_limited(generate_actions, payload.actions_input)
    except Exception as exc:
        logger.error("worker generate_actions failed: %s", exc)
        raise HTTPException(status_code=500, detail="LLM pipeline failed") from exc
