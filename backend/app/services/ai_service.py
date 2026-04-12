import asyncio
from difflib import SequenceMatcher
import hashlib
import json
import logging
import math
import re
import time
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.services.clause_extractor import extract_clauses_from_text, filter_relevant_clauses
from app.services.llm_router import call_groq_with_retry

logger = logging.getLogger(__name__)

MAX_CALLS = 5
DEFAULT_BATCH_SIZE = 3
INTER_CALL_DELAY_SECONDS = 2
MAX_INPUT_TOKENS = 2000
MAX_TOTAL_TOKENS_PER_REQUEST = 5000
BATCH_OUTPUT_TOKENS = 350
SUMMARY_OUTPUT_TOKENS = 250
MERGE_OUTPUT_TOKENS = 450
SAFE_TRUNCATE_CHARS = 2000
TOP_ITEM_LIMIT = 10
STRICT_JSON_INSTRUCTION = (
    "Return ONLY valid JSON. No explanation. No markdown. No text outside JSON. "
    "Do not include summary strings or prose outside JSON."
)
STRICT_SCHEMA_INSTRUCTION = (
    "Always respond with this top-level JSON schema exactly: "
    '{"changes": [], "compliance_gaps": [], "impacts": [], "actions": []}'
)


class UnifiedResponseSchema(BaseModel):
    changes: list[dict] = Field(default_factory=list)
    compliance_gaps: list[dict] = Field(default_factory=list)
    impacts: list[dict] = Field(default_factory=list)
    actions: list[dict] = Field(default_factory=list)


def empty_schema_response() -> dict:
    return UnifiedResponseSchema().model_dump()


def _schema_response(
    changes: list[dict] | None = None,
    compliance_gaps: list[dict] | None = None,
    impacts: list[dict] | None = None,
    actions: list[dict] | None = None,
) -> dict:
    payload = UnifiedResponseSchema(
        changes=changes or [],
        compliance_gaps=compliance_gaps or [],
        impacts=impacts or [],
        actions=actions or [],
    )
    return payload.model_dump()


def deduplicate_items(items: list[dict]) -> list[dict]:
    if not isinstance(items, list):
        return []

    deduped = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue

        issue = str(
            item.get("issue")
            or item.get("description")
            or item.get("action")
            or item.get("summary")
            or item.get("title")
            or ""
        ).strip().lower()
        regulation_requirement = str(item.get("regulation_requirement") or item.get("area") or item.get("owner") or "").strip().lower()
        digest = hashlib.sha256(f"{issue}|{regulation_requirement}".encode("utf-8")).hexdigest()

        if digest in seen:
            continue
        seen.add(digest)
        deduped.append(item)

    return deduped


def _normalize_severity(value: Any) -> str:
    level = str(value or "").strip().lower()
    if level == "high":
        return "High"
    if level == "medium":
        return "Medium"
    if level == "low":
        return "Low"
    return "Medium"


def _normalize_impact_item(item: dict) -> dict:
    if not isinstance(item, dict):
        return {
            "title": "Compliance Impact",
            "description": "Impact identified from regulatory changes and policy gaps",
            "severity": "Medium",
            "impacted_departments": [],
        }

    departments = item.get("impacted_departments")
    if not isinstance(departments, list):
        departments = item.get("departments")
    if not isinstance(departments, list):
        departments = item.get("department")

    if isinstance(departments, str):
        departments = [departments]
    if not isinstance(departments, list):
        departments = []

    normalized_departments = []
    seen_departments = set()
    for department in departments:
        label = str(department or "").strip()
        if not label:
            continue
        key = label.lower()
        if key in seen_departments:
            continue
        seen_departments.add(key)
        normalized_departments.append(label)

    title = str(item.get("title") or item.get("area") or "Compliance Impact").strip()
    description = str(item.get("description") or item.get("summary") or "Impact identified from regulatory changes and policy gaps").strip()

    return {
        "title": title,
        "description": description,
        "severity": _normalize_severity(item.get("severity")),
        "impacted_departments": normalized_departments,
    }


def _normalize_impacts_list(items: list[dict]) -> list[dict]:
    if not isinstance(items, list):
        return []

    normalized = [_normalize_impact_item(item) for item in items if isinstance(item, dict)]
    if not normalized:
        return []

    # Keep severity distribution realistic: mostly Medium, some Low, limited High.
    total = len(normalized)
    max_high = max(1, math.ceil(total * 0.3))
    min_high = max(1, math.floor(total * 0.2)) if total >= 4 else 1

    high_indices = [index for index, item in enumerate(normalized) if item.get("severity") == "High"]
    medium_indices = [index for index, item in enumerate(normalized) if item.get("severity") == "Medium"]
    low_indices = [index for index, item in enumerate(normalized) if item.get("severity") == "Low"]

    if len(high_indices) > max_high:
        for index in high_indices[max_high:]:
            normalized[index]["severity"] = "Medium"

    elif len(high_indices) < min_high and medium_indices:
        needed = min_high - len(high_indices)
        for index in medium_indices[:needed]:
            normalized[index]["severity"] = "High"

    # Ensure there is at least one Low impact when we have enough entries.
    if total >= 3 and not any(item.get("severity") == "Low" for item in normalized):
        demote_index = next((idx for idx, item in enumerate(normalized) if item.get("severity") == "Medium"), None)
        if demote_index is None:
            demote_index = next((idx for idx, item in enumerate(normalized) if item.get("severity") == "High"), None)
        if demote_index is not None:
            normalized[demote_index]["severity"] = "Low"

    return normalized


def _parse_json_without_duplicate_keys(raw: str):
    def _dedupe_pairs(pairs):
        merged = {}
        for key, value in pairs:
            if key not in merged:
                merged[key] = value
        return merged

    return json.loads(raw, object_pairs_hook=_dedupe_pairs)


def _strip_trailing_commas(raw: str) -> str:
    if not isinstance(raw, str):
        return raw
    return re.sub(r",\s*([}\]])", r"\1", raw)


def clean_llm_json(raw_response: str) -> dict | None:
    if not raw_response or not isinstance(raw_response, str):
        return None

    original = raw_response.strip()
    candidate = _strip_trailing_commas(original)

    parsed = None

    # Attempt 1: direct parse.
    try:
        parsed = _parse_json_without_duplicate_keys(candidate)
    except Exception:
        parsed = None

    # Attempt 2: fenced JSON block extraction.
    if parsed is None:
        fenced_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", candidate, re.IGNORECASE)
        if fenced_match:
            extracted = _strip_trailing_commas(fenced_match.group(1).strip())
            try:
                parsed = _parse_json_without_duplicate_keys(extracted)
            except Exception:
                parsed = None

    # Attempt 3: first object-like region extraction.
    if parsed is None:
        json_match = re.search(r"\{[\s\S]*\}", candidate)
        if json_match:
            extracted = _strip_trailing_commas(json_match.group(0).strip())
            try:
                parsed = _parse_json_without_duplicate_keys(extracted)
            except Exception:
                parsed = None

    if parsed is None:
        return UnifiedResponseSchema().model_dump()

    if isinstance(parsed, list):
        parsed = {"compliance_gaps": parsed}

    if not isinstance(parsed, dict):
        return None

    normalized = {
        "changes": parsed.get("changes") if isinstance(parsed.get("changes"), list) else [],
        "compliance_gaps": parsed.get("compliance_gaps") if isinstance(parsed.get("compliance_gaps"), list) else [],
        "impacts": parsed.get("impacts") if isinstance(parsed.get("impacts"), list) else [],
        "actions": parsed.get("actions") if isinstance(parsed.get("actions"), list) else [],
    }

    if not normalized["compliance_gaps"] and isinstance(parsed.get("gaps"), list):
        normalized["compliance_gaps"] = parsed.get("gaps") or []

    legacy_impact = parsed.get("impact")
    if not normalized["impacts"]:
        if isinstance(legacy_impact, list):
            normalized["impacts"] = legacy_impact
        elif isinstance(legacy_impact, dict):
            normalized["impacts"] = [legacy_impact]

    if isinstance(parsed.get("actions"), dict):
        normalized["actions"] = [parsed.get("actions")]

    normalized["compliance_gaps"] = deduplicate_items(normalized["compliance_gaps"])
    normalized["impacts"] = deduplicate_items(_normalize_impacts_list(normalized["impacts"]))
    normalized["actions"] = deduplicate_items(normalized["actions"])

    try:
        return UnifiedResponseSchema.model_validate(normalized).model_dump()
    except ValidationError:
        return None


def estimate_tokens(text: str) -> int:
    return len(text or "") // 4


def _item_text(item) -> str:
    if isinstance(item, dict):
        if "left" in item or "right" in item:
            return f"OLD:\n{item.get('left') or ''}\n\nNEW:\n{item.get('right') or ''}"
        return str(item.get("page_content") or item.get("text") or item.get("content") or "")
    if isinstance(item, (list, tuple)):
        return "\n\n".join(str(part or "") for part in item)
    return str(getattr(item, "page_content", getattr(item, "text", item)) or "")


def _truncate_text_for_tokens(text: str, max_tokens: int = MAX_INPUT_TOKENS) -> str:
    value = (text or "").strip()
    if not value:
        return ""
    if estimate_tokens(value) <= max_tokens:
        return value
    return value[:SAFE_TRUNCATE_CHARS]


def _truncate_item_for_tokens(item):
    if isinstance(item, dict):
        truncated = dict(item)
        if "left" in truncated:
            truncated["left"] = _truncate_text_for_tokens(str(truncated.get("left") or ""))
        if "right" in truncated:
            truncated["right"] = _truncate_text_for_tokens(str(truncated.get("right") or ""))
        if "text" in truncated:
            truncated["text"] = _truncate_text_for_tokens(str(truncated.get("text") or ""))
        if "page_content" in truncated:
            truncated["page_content"] = _truncate_text_for_tokens(str(truncated.get("page_content") or ""))
        return truncated

    if isinstance(item, tuple):
        return tuple(_truncate_text_for_tokens(str(part or "")) for part in item)

    if isinstance(item, list):
        return [_truncate_text_for_tokens(str(part or "")) for part in item]

    if isinstance(item, str):
        return _truncate_text_for_tokens(item)

    return item


def _dedupe_clause_list(clauses: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for clause in clauses or []:
        if not isinstance(clause, dict):
            continue
        clause_id = str(clause.get("clause_id") or "").strip().lower()
        title = str(clause.get("title") or "").strip().lower()
        content = str(clause.get("content") or "").strip().lower()
        key = f"{clause_id}|{title}|{content}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(clause)
    return deduped


def _filter_text_for_llm(text: str, label: str) -> str:
    """Apply clause filtering right before LLM prompt construction.

    Backward compatibility: if extraction/filtering fails or yields no usable output,
    return original text unchanged.
    """
    source_text = str(text or "").strip()
    if not source_text:
        return source_text

    try:
        all_clauses = extract_clauses_from_text(source_text)
        if not all_clauses:
            return source_text

        all_clauses = _dedupe_clause_list(all_clauses)
        filtered_clauses = filter_relevant_clauses(all_clauses)
        filtered_clauses = _dedupe_clause_list(filtered_clauses)

        if not filtered_clauses:
            return source_text

        logger.info(
            "Using filtered clauses for LLM processing | stage=%s before=%s after=%s",
            label,
            len(all_clauses),
            len(filtered_clauses),
        )

        rebuilt = "\n\n".join(str(clause.get("content") or "").strip() for clause in filtered_clauses).strip()
        return rebuilt or source_text
    except Exception as exc:
        logger.warning("Clause filtering failed at stage=%s, using original clauses: %s", label, exc)
        return source_text


def _score_relevance(text: str) -> int:
    value = (text or "").lower()
    score = 0
    for keyword in (
        "must",
        "shall",
        "required",
        "prohibited",
        "compliance",
        "policy",
        "regulation",
        "report",
        "risk",
        "audit",
        "deadline",
        "penalty",
        "threshold",
        "section",
    ):
        if keyword in value:
            score += 3
    if re.search(r"\b\d+%\b", value) or re.search(r"\b\d+(?:\.\d+)?\b", value):
        score += 4
    if value.isupper() and len(value) < 120:
        score += 2
    score += min(len(value) // 500, 4)
    return score


def _score_item(item) -> int:
    return _score_relevance(_item_text(item))


def _rank_and_limit_items(items: list, limit: int = TOP_ITEM_LIMIT) -> list:
    ranked = sorted(
        items or [],
        key=lambda item: (_score_item(item), estimate_tokens(_item_text(item))),
        reverse=True,
    )
    return ranked[:limit]


def create_token_safe_batches(items, max_input_tokens: int = MAX_INPUT_TOKENS):
    batches = []
    current_batch = []
    current_tokens = 0

    for item in items or []:
        normalized_item = item
        item_text = _item_text(normalized_item)
        item_tokens = estimate_tokens(item_text)

        if item_tokens > max_input_tokens:
            normalized_item = _truncate_item_for_tokens(normalized_item)
            item_text = _item_text(normalized_item)
            item_tokens = estimate_tokens(item_text)

        if current_batch and current_tokens + item_tokens > max_input_tokens:
            batches.append(current_batch)
            current_batch = [normalized_item]
            current_tokens = item_tokens
        else:
            current_batch.append(normalized_item)
            current_tokens += item_tokens

    if current_batch:
        batches.append(current_batch)

    return batches


def _derive_batch_input_budget(item_count: int, use_summary: bool) -> int:
    batch_calls = max(1, min(MAX_CALLS - 1 - (1 if use_summary else 0), item_count))
    planned_calls = batch_calls + 1 + (1 if use_summary else 0)
    reserved_output = batch_calls * BATCH_OUTPUT_TOKENS + MERGE_OUTPUT_TOKENS + (SUMMARY_OUTPUT_TOKENS if use_summary else 0)
    available_input = max(800, MAX_TOTAL_TOKENS_PER_REQUEST - reserved_output)
    return max(500, min(MAX_INPUT_TOKENS, available_input // planned_calls))


def _ensure_prompt_token_safe(prompt: str) -> str:
    value = prompt or ""
    if estimate_tokens(value) > MAX_INPUT_TOKENS:
        return value[:MAX_INPUT_TOKENS * 4]
    return value


def split_into_chunks(text: str, chunk_size: int = 2500) -> list[str]:
    """Split text into manageable chunks for Groq (TPM safe)."""
    if not text or not isinstance(text, str):
        return []

    text = text.strip()
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    words = text.split()
    current_chunk = []
    current_length = 0

    for word in words:
        word_len = len(word) + 1
        if current_length + word_len > chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_length = word_len
        else:
            current_chunk.append(word)
            current_length += word_len

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def merge_chunk_results(results: list[dict], result_key: str) -> list[dict]:
    """Merge results from multiple analyses, removing duplicates."""
    merged = []
    seen_keys = set()

    for result in results:
        if not isinstance(result, dict):
            continue

        items = result.get(result_key, [])
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue

            key_fields = [str(item.get("issue") or item.get("summary") or "").lower().strip()[:100]]
            key = "|".join(key_fields)

            if key not in seen_keys:
                merged.append(item)
                seen_keys.add(key)

    return merged


def trim_text(text, max_len: int = 300):
    value = text if isinstance(text, str) else str(text or "")
    return value[:max_len]


def default_impact(systems=None):
    default_departments = []
    if isinstance(systems, list):
        default_departments = [str(system).strip() for system in systems if str(system or "").strip()]

    return _schema_response(
        impacts=[
            {
                "title": "Compliance Impact",
                "description": "Impact assessment based on identified compliance gaps",
                "severity": "Medium",
                "impacted_departments": default_departments,
            }
        ]
    )


def default_actions():
    return _schema_response(
        actions=[
            {
                "action": "Review regulatory gaps and update policy accordingly",
                "priority": "Medium",
                "owner": "Compliance",
                "timeline": "1-2 weeks",
            }
        ]
    )


def _default_changes_response() -> dict:
    return _schema_response()


def _default_gaps_response() -> dict:
    return _schema_response()


def _extract_changes(payload) -> list:
    if isinstance(payload, dict):
        items = payload.get("changes")
        if isinstance(items, list):
            return items
    if isinstance(payload, list):
        return payload
    return []


def _extract_gaps(payload) -> list:
    if isinstance(payload, dict):
        gaps = payload.get("compliance_gaps")
        if not isinstance(gaps, list):
            gaps = payload.get("gaps")
        if isinstance(gaps, list):
            return gaps
    if isinstance(payload, list):
        return payload
    return []


def _priority_value(risk: Any) -> int:
    level = (risk or "").strip().lower()
    if level == "high":
        return 3
    if level == "medium":
        return 2
    return 1


def _normalize_action(item: dict) -> dict:
    title = item.get("title") or item.get("step") or item.get("task") or item.get("name") or "Untitled Task"
    description = item.get("description") or item.get("details") or item.get("summary") or "No Description"
    priority = item.get("priority") or "Medium"

    return {
        "title": trim_text(title, 120),
        "description": trim_text(description, 240),
        "priority": priority,
        "status": item.get("status") or "Pending",
        "deadline": item.get("deadline") or item.get("timeline") or "TBD",
    }


def _normalize_impact_payload(payload, systems=None) -> dict:
    base = default_impact(systems=systems)
    if not isinstance(payload, dict):
        return base

    legacy_impact = payload.get("impact")
    if isinstance(legacy_impact, dict):
        return _schema_response(impacts=_normalize_impacts_list([legacy_impact]))

    impacts = payload.get("impacts")
    if isinstance(impacts, list):
        return _schema_response(impacts=_normalize_impacts_list(impacts))

    return base


def _parse_json_response(content):
    if not content or not isinstance(content, str):
        return None

    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return None

    try:
        return _parse_json_without_duplicate_keys(match.group(0))
    except Exception:
        return None


def _call_groq_safe(
    prompt: str,
    system_prompt: str = "You are a regulatory analysis AI.",
    max_tokens: int = 1000,
    retries: int = 3,
    expect_schema: bool = True,
    preferred_key_index: int | None = None,
    invalid_previous_response: bool = False,
) -> dict:
    """Safe Groq call with error handling and JSON parsing."""
    try:
        retry_message = "\nPrevious response invalid. Return only JSON." if invalid_previous_response else ""
        strict_schema_message = f"\n{STRICT_SCHEMA_INSTRUCTION}" if expect_schema else ""
        messages = [
            {
                "role": "system",
                "content": f"{system_prompt}\n{STRICT_JSON_INSTRUCTION}{strict_schema_message}{retry_message}",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            content = call_groq_with_retry(
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.0,
                retries=retries,
                initial_backoff=2.0,
                preferred_key_index=preferred_key_index,
                response_format={"type": "json_object"},
            )
        except Exception as json_mode_error:
            error_text = str(json_mode_error).lower()
            json_generation_failed = (
                "json_validate_failed" in error_text
                or "failed to generate json" in error_text
                or "invalid_request_error" in error_text
            )

            if not json_generation_failed:
                raise

            # Fallback: drop API-level response_format and rely on strict prompt + parser.
            logger.warning("json_object mode failed, falling back to prompt-only JSON parsing: %s", json_mode_error)
            content = call_groq_with_retry(
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.0,
                retries=1,
                initial_backoff=1.0,
                preferred_key_index=preferred_key_index,
            )

        if not content:
            return {"error": "Empty response from Groq"}

        logger.info("llm_raw_response=%s", content[:1200])

        if expect_schema:
            parsed = clean_llm_json(content)
        else:
            parsed = _parse_json_response(content)

        if parsed is None:
            logger.warning("Could not parse JSON response: %s", content[:200])
            return UnifiedResponseSchema().model_dump() if expect_schema else {"error": "Could not parse JSON response"}

        if expect_schema:
            parsed = UnifiedResponseSchema.model_validate(parsed).model_dump()

        logger.info("llm_cleaned_json=%s", json.dumps(parsed, ensure_ascii=True)[:1200])

        return parsed

    except Exception as exc:
        logger.error("Groq call failed: %s", exc)
        return {"error": str(exc)}


def _safe_call(
    prompt: str,
    max_tokens: int = 1300,
    retries: int = 3,
    initial_backoff: int = 5,
    expect_schema: bool = True,
    preferred_key_index: int | None = None,
) -> dict:
    prompt = _ensure_prompt_token_safe(prompt)
    backoff = initial_backoff
    last_error = "Groq failed after retries"

    for attempt in range(retries):
        # Retry never accumulates partial outputs; only the final successful payload is returned.
        result = _call_groq_safe(
            prompt=prompt,
            max_tokens=max_tokens,
            retries=2,
            expect_schema=expect_schema,
            preferred_key_index=preferred_key_index,
            invalid_previous_response=(attempt > 0),
        )
        if isinstance(result, dict) and "error" not in result:
            return result

        if isinstance(result, dict) and isinstance(result.get("error"), str):
            last_error = result.get("error")

        logger.warning("safe_call failed on attempt %s/%s. Backoff=%ss", attempt + 1, retries, backoff)
        is_last_attempt = attempt >= (retries - 1)
        if is_last_attempt:
            break

        time.sleep(backoff)
        backoff *= 2

    return {"error": f"Groq failed after retries: {last_error}"}


def _optional_summary(label: str, text: str, call_budget: int) -> str:
    """Build a compact context summary when input is large and there is call budget left."""
    value = (text or "").strip()
    if call_budget < 3 or estimate_tokens(value) < 800:
        return ""

    prompt = f"""
Summarize key regulatory points from this {label} document.
Avoid repetition. Be concise but complete.

Return ONLY valid JSON. No explanation. No markdown. No text outside JSON.\n\nJSON schema:
{{
  "summary": "Compact summary preserving key obligations, thresholds, timelines, penalties, and scope"
}}

DOCUMENT:
{_truncate_text_for_tokens(value, max_tokens=MAX_INPUT_TOKENS)}
"""

    result = _safe_call(prompt=prompt, max_tokens=450, retries=2, initial_backoff=4, expect_schema=False)
    if isinstance(result, dict) and "error" not in result:
        summary_text = result.get("summary") if isinstance(result.get("summary"), str) else None
        if summary_text and summary_text.strip():
            return summary_text.strip()

    return ""


def _final_merge_changes(partials: list[dict]) -> dict:
    if not partials:
        return {"changes": []}

    prompt = f"""
Combine the following analyses into one final JSON response.
Avoid repetition. Be concise but complete.
Keep only material, non-duplicate regulatory changes.

Return ONLY valid JSON. No explanation. No markdown. No text outside JSON.\n\nJSON schema:
{{
  "changes": [
    {{
      "type": "added | removed | modified",
      "category": "KYC | Risk | Capital | Reporting | Governance | Audit | Other",
      "summary": "Specific change in <=2 lines",
      "impact": "Brief significance note"
    }}
  ]
}}

PARTIAL_ANALYSES:
{json.dumps(partials, ensure_ascii=True)}
"""

    merged = _safe_call(prompt=prompt, max_tokens=1200, retries=2, initial_backoff=4)
    if isinstance(merged, dict) and "error" not in merged and isinstance(merged.get("changes"), list):
        return {"changes": merged.get("changes", [])[:5]}

    fallback = merge_chunk_results(partials, "changes")
    return {"changes": fallback[:5] if fallback else []}


def _final_merge_gaps(partials: list[dict]) -> dict:
    if not partials:
        return _schema_response()

    prompt = f"""
Combine the following analyses into one final JSON response.
Avoid repetition. Be concise but complete.
Keep only material, non-duplicate compliance gaps.

Return ONLY valid JSON. No explanation. No markdown. No text outside JSON.\n\nJSON schema:
{{
  "compliance_gaps": [
    {{
      "issue": "Gap description <=2 lines",
      "risk": "High | Medium | Low",
      "regulation_requirement": "What regulation requires",
      "policy_current_state": "What policy says/doesn't say"
    }}
  ]
}}

PARTIAL_ANALYSES:
{json.dumps(partials, ensure_ascii=True)}
"""

    merged = _safe_call(prompt=prompt, max_tokens=1200, retries=2, initial_backoff=4)
    if isinstance(merged, dict) and "error" not in merged and isinstance(merged.get("compliance_gaps"), list):
        gaps = merged.get("compliance_gaps", [])
        gaps = sorted(gaps, key=lambda g: _priority_value((g or {}).get("risk", "Low")), reverse=True)
        return _schema_response(compliance_gaps=gaps[:6])

    fallback = merge_chunk_results(partials, "compliance_gaps")
    fallback = sorted(fallback, key=lambda g: _priority_value((g or {}).get("risk", "Low")), reverse=True)
    return _schema_response(compliance_gaps=fallback[:6] if fallback else [])




MAX_PARALLEL_CALLS = 3


def build_batches(chunks, max_tokens_per_batch: int):
    return create_token_safe_batches(chunks, max_input_tokens=max_tokens_per_batch)


async def process_in_parallel(tasks: list[dict], label: str = "pipeline") -> list[Any]:
    semaphore = asyncio.Semaphore(MAX_PARALLEL_CALLS)

    async def run_task(position: int, task: dict):
        async with semaphore:
            callable_fn = task.get("callable")
            args = task.get("args") or []
            kwargs = dict(task.get("kwargs") or {})
            kwargs.setdefault("preferred_key_index", position % MAX_PARALLEL_CALLS)
            started = time.perf_counter()
            logger.info(
                "%s_task_start position=%s preferred_key_index=%s",
                label,
                position,
                kwargs.get("preferred_key_index"),
            )
            result = await asyncio.to_thread(callable_fn, *args, **kwargs)
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.info("%s_task_done position=%s elapsed_ms=%s", label, position, elapsed_ms)
            return position, result

    futures = [asyncio.create_task(run_task(index, task)) for index, task in enumerate(tasks)]
    results = await asyncio.gather(*futures, return_exceptions=False)
    results.sort(key=lambda item: item[0])
    return [item[1] for item in results]


async def process_batches_parallel(batch_entries: list[dict], label: str = "batch") -> list[dict]:
    semaphore = asyncio.Semaphore(MAX_PARALLEL_CALLS)

    async def run_entry(position: int, entry: dict):
        async with semaphore:
            prompt = entry.get("prompt") or ""
            max_tokens = int(entry.get("max_tokens") or BATCH_OUTPUT_TOKENS)
            retries = int(entry.get("retries") or 3)
            backoff = float(entry.get("initial_backoff") or 5)
            batch_size = entry.get("batch_size") or 0
            estimated_tokens = entry.get("estimated_tokens") or estimate_tokens(prompt)
            started = time.perf_counter()
            logger.info(
                "%s_parallel_start position=%s batch_size=%s estimated_tokens=%s max_tokens=%s",
                label,
                position,
                batch_size,
                estimated_tokens,
                max_tokens,
            )
            result = await asyncio.to_thread(
                _safe_call,
                prompt,
                max_tokens,
                retries,
                backoff,
                True,
                position % MAX_PARALLEL_CALLS,
            )
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.info(
                "%s_parallel_done position=%s batch_size=%s estimated_tokens=%s elapsed_ms=%s",
                label,
                position,
                batch_size,
                estimated_tokens,
                elapsed_ms,
            )
            return position, result

    tasks = [asyncio.create_task(run_entry(index, entry)) for index, entry in enumerate(batch_entries)]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    results.sort(key=lambda item: item[0])
    return [item[1] for item in results]


def _build_change_prompt(batch_index: int, pair_batches: list, batch: list, summary: str) -> str:
    old_batch = "\n\n".join([f"[OLD_{i + 1}]\n{item['left']}" for i, item in enumerate(batch)])
    new_batch = "\n\n".join([f"[NEW_{i + 1}]\n{item['right']}" for i, item in enumerate(batch)])
    return f"""
You are a regulatory analyst. Compare OLD and NEW context and identify ONLY material changes.
Avoid repetition. Be concise but complete.
Limit response to essential insights only. Avoid long explanations.

CRITICAL:
1. Use ONLY info from provided text
2. Focus on HIGH-IMPORTANCE changes only
3. Return empty changes array if no material changes
4. Do NOT invent details

REFERENCE SUMMARY:
{summary or "N/A"}

BATCH {batch_index}/{len(pair_batches)}

OLD:
{old_batch[:7000]}

NEW:
{new_batch[:7000]}

Return ONLY valid JSON. No explanation. No markdown. No text outside JSON.\n\nJSON schema:
{{
  "changes": [
    {{
      "type": "added | removed | modified",
      "category": "KYC | Risk | Capital | Reporting | Governance | Audit | Other",
      "summary": "Specific change in <=2 lines",
      "impact": "Brief significance note"
    }}
  ]
}}
"""


def _build_gap_prompt(batch_index: int, pair_batches: list, batch: list, summary: str) -> str:
    regulation_batch = "\n\n".join([f"[REG_{i + 1}]\n{item['left']}" for i, item in enumerate(batch)])
    policy_batch = "\n\n".join([f"[POL_{i + 1}]\n{item['right']}" for i, item in enumerate(batch)])
    return f"""
You are a compliance auditor assessing gaps ONLY from provided context.
Avoid repetition. Be concise but complete.
Limit response to essential insights only. Avoid long explanations.

TASK: Identify gaps where POLICY fails to meet REGULATION.

CRITICAL:
1. Use ONLY info from provided text
2. Focus on HIGH-IMPACT gaps only
3. Return empty compliance_gaps array if none found
4. Do NOT assume unstated requirements

REFERENCE SUMMARY:
{summary or "N/A"}

BATCH {batch_index}/{len(pair_batches)}

REGULATION:
{regulation_batch[:7000]}

POLICY:
{policy_batch[:7000]}

Return ONLY valid JSON. No explanation. No markdown. No text outside JSON.\n\nJSON schema:
{{
  "compliance_gaps": [
    {{
      "issue": "Gap description <=2 lines",
      "risk": "High | Medium | Low",
      "regulation_requirement": "What regulation requires",
      "policy_current_state": "What policy says/doesn't say"
    }}
  ]
}}
"""


def _prepare_pairs(left_text: str, right_text: str, left_label: str, right_label: str) -> list[dict]:
    left_chunks = split_into_chunks(left_text, chunk_size=2500)
    right_chunks = split_into_chunks(right_text, chunk_size=2500)

    max_len = max(len(left_chunks), len(right_chunks))
    left_chunks.extend([""] * (max_len - len(left_chunks)))
    right_chunks.extend([""] * (max_len - len(right_chunks)))

    pairs = []
    for left_chunk, right_chunk in zip(left_chunks, right_chunks):
        if not (left_chunk or "").strip() and not (right_chunk or "").strip():
            continue
        pair_item = {"left": _truncate_text_for_tokens(left_chunk), "right": _truncate_text_for_tokens(right_chunk)}
        pair_item["score"] = _score_item(pair_item)
        pairs.append(pair_item)

    if not pairs:
        return []

    pairs = _rank_and_limit_items(pairs, limit=TOP_ITEM_LIMIT)
    return pairs


def _sequential_summary(label: str, combined_text: str, call_budget: int) -> str:
    return _optional_summary(label, combined_text, call_budget)


def _extract_filtered_clauses_for_map(text: str, label: str, clause_prefix: str) -> list[dict]:
    source_text = str(text or "").strip()
    if not source_text:
        return []

    try:
        all_clauses = extract_clauses_from_text(source_text)
        if not all_clauses:
            return []

        all_clauses = _dedupe_clause_list(all_clauses)
        filtered_clauses = filter_relevant_clauses(all_clauses)
        filtered_clauses = _dedupe_clause_list(filtered_clauses)

        if not filtered_clauses:
            filtered_clauses = all_clauses

        logger.info(
            "Using filtered clauses for LLM processing | stage=%s before=%s after=%s",
            label,
            len(all_clauses),
            len(filtered_clauses),
        )

        normalized = []
        for index, clause in enumerate(filtered_clauses, start=1):
            content = str(clause.get("content") or "").strip()
            if not content:
                continue
            clause_id = str(clause.get("clause_id") or f"{clause_prefix}-{index}").strip()
            normalized.append(
                {
                    "clause_id": clause_id,
                    "title": str(clause.get("title") or "").strip(),
                    "content": _truncate_text_for_tokens(content, max_tokens=350),
                }
            )
        return normalized
    except Exception as exc:
        logger.warning("Clause extraction/filtering failed for stage=%s, using fallback: %s", label, exc)
        fallback = _truncate_text_for_tokens(source_text, max_tokens=350)
        return [{"clause_id": f"{clause_prefix}-1", "title": "", "content": fallback}] if fallback else []


def _parse_mapped_changes(raw_content: str) -> list[dict] | None:
    if not raw_content or not isinstance(raw_content, str):
        return None

    candidate = _strip_trailing_commas(raw_content.strip())
    parsed = None

    try:
        parsed = _parse_json_without_duplicate_keys(candidate)
    except Exception:
        parsed = None

    if parsed is None:
        fenced_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", candidate, re.IGNORECASE)
        if fenced_match:
            extracted = _strip_trailing_commas(fenced_match.group(1).strip())
            try:
                parsed = _parse_json_without_duplicate_keys(extracted)
            except Exception:
                parsed = None

    if parsed is None:
        object_match = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", candidate)
        if object_match:
            extracted = _strip_trailing_commas(object_match.group(0).strip())
            try:
                parsed = _parse_json_without_duplicate_keys(extracted)
            except Exception:
                parsed = None

    if parsed is None:
        return None

    if isinstance(parsed, dict):
        items = parsed.get("changes") if isinstance(parsed.get("changes"), list) else []
    elif isinstance(parsed, list):
        items = parsed
    else:
        return None

    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        change = str(item.get("change") or item.get("summary") or "").strip()
        change_type = str(item.get("type") or "modified").strip().lower()
        if change_type not in {"added", "modified", "removed"}:
            change_type = "modified"
        if not change:
            continue
        normalized.append({"change": trim_text(change, 220), "type": change_type})

    return normalized[:2]


def map_changes_per_clause(clause, stats: dict | None = None) -> list[dict]:
    """MAP phase: detect up to 2 changes for a single clause pair with a short prompt."""
    if not isinstance(clause, dict):
        return []

    clause_id = str(clause.get("clause_id") or "unknown")
    old_content = _truncate_text_for_tokens(str(clause.get("old_content") or ""), max_tokens=350)
    new_content = _truncate_text_for_tokens(str(clause.get("new_content") or ""), max_tokens=350)

    if not old_content and not new_content:
        return []

    user_prompt = (
        "Identify material differences between OLD and NEW for this clause. "
        "Return at most 2 items.\n"
        "Output JSON only with schema: "
        '{"changes":[{"change":"...","type":"added|modified|removed"}]}\n\n'
        f"CLAUSE_ID: {clause_id}\n"
        f"OLD: {old_content}\n"
        f"NEW: {new_content}"
    )

    prompt_tokens = estimate_tokens(user_prompt)
    logger.info("map_changes_per_clause clause_id=%s tokens_used=%s", clause_id, prompt_tokens)

    for attempt in range(2):
        if isinstance(stats, dict):
            stats["api_calls"] = int(stats.get("api_calls") or 0) + 1
        try:
            content = call_groq_with_retry(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a strict JSON regulatory diff assistant. Return only valid JSON.",
                    },
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=140,
                temperature=0.0,
                retries=1,
                initial_backoff=1.0,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            logger.warning("map_changes_per_clause LLM call failed clause_id=%s attempt=%s error=%s", clause_id, attempt + 1, exc)
            content = ""

        parsed = _parse_mapped_changes(content)
        if parsed is not None:
            logger.info(
                "map_changes_per_clause clause_id=%s tokens_used=%s",
                clause_id,
                prompt_tokens + estimate_tokens(content),
            )
            return parsed

        logger.warning("Invalid JSON for clause_id=%s attempt=%s. Retrying once.", clause_id, attempt + 1)

    return []


def _normalize_change_text(value: str) -> str:
    normalized = re.sub(r"\s+", " ", str(value or "").strip().lower())
    return normalized


def _is_similar_change(left: str, right: str, threshold: float = 0.9) -> bool:
    if not left or not right:
        return False
    ratio = SequenceMatcher(None, left, right).ratio()
    return ratio >= threshold


def merge_and_dedupe_clause_changes(clause_level_outputs: list[list[dict]]) -> list[dict]:
    """Combine clause MAP outputs and return clean unique changes."""
    merged_items = []
    for output in clause_level_outputs or []:
        if not isinstance(output, list):
            continue
        for item in output:
            if not isinstance(item, dict):
                continue
            change = str(item.get("change") or "").strip()
            change_type = str(item.get("type") or "modified").strip().lower()
            if change_type not in {"added", "modified", "removed"}:
                change_type = "modified"
            if not change:
                continue
            merged_items.append({"change": change, "type": change_type})

    before_count = len(merged_items)

    unique_changes = []
    seen_exact = set()

    for item in merged_items:
        normalized_change = _normalize_change_text(item.get("change") or "")
        normalized_type = str(item.get("type") or "modified").strip().lower()
        exact_key = f"{normalized_type}|{normalized_change}"

        if exact_key in seen_exact:
            continue

        is_near_duplicate = False
        for existing in unique_changes:
            if normalized_type != str(existing.get("type") or "modified").strip().lower():
                continue
            existing_text = _normalize_change_text(existing.get("change") or "")
            if _is_similar_change(normalized_change, existing_text):
                is_near_duplicate = True
                break

        if is_near_duplicate:
            continue

        seen_exact.add(exact_key)
        unique_changes.append({
            "change": re.sub(r"\s+", " ", str(item.get("change") or "").strip()),
            "type": normalized_type,
        })

    logger.info("MAP merge/dedup: before_count=%s after_dedup=%s", before_count, len(unique_changes))
    return unique_changes


def _normalize_reduce_changes(items: list[dict]) -> list[dict]:
    normalized = []
    for item in items or []:
        if not isinstance(item, dict):
            continue

        summary = str(item.get("summary") or item.get("change") or "").strip()
        if not summary:
            continue

        change_type = str(item.get("type") or "modified").strip().lower()
        if change_type not in {"added", "modified", "removed"}:
            change_type = "modified"

        normalized.append(
            {
                "type": change_type,
                "category": str(item.get("category") or "Other").strip() or "Other",
                "summary": trim_text(summary, 220),
                "impact": trim_text(str(item.get("impact") or "Regulatory update identified").strip(), 220),
            }
        )

    return deduplicate_items(normalized)[:10]


def _normalize_reduce_actions(items: list[dict]) -> list[dict]:
    normalized = []
    for item in items or []:
        if not isinstance(item, dict):
            continue

        action = str(item.get("action") or item.get("title") or "").strip()
        if not action:
            continue

        priority = str(item.get("priority") or "Medium").strip().title()
        if priority not in {"High", "Medium", "Low"}:
            priority = "Medium"

        owner = str(item.get("owner") or "Compliance").strip() or "Compliance"

        normalized.append(
            {
                "action": trim_text(action, 220),
                "priority": priority,
                "owner": trim_text(owner, 80),
            }
        )

    return deduplicate_items(normalized)[:10]


def _parse_reduce_payload(raw_content: str) -> dict | None:
    if not raw_content or not isinstance(raw_content, str):
        return None

    candidate = _strip_trailing_commas(raw_content.strip())
    parsed = None

    try:
        parsed = _parse_json_without_duplicate_keys(candidate)
    except Exception:
        parsed = None

    if parsed is None:
        fenced_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", candidate, re.IGNORECASE)
        if fenced_match:
            extracted = _strip_trailing_commas(fenced_match.group(1).strip())
            try:
                parsed = _parse_json_without_duplicate_keys(extracted)
            except Exception:
                parsed = None

    if not isinstance(parsed, dict):
        return None

    changes = parsed.get("changes") if isinstance(parsed.get("changes"), list) else []
    actions = parsed.get("actions") if isinstance(parsed.get("actions"), list) else []

    return {
        "changes": _normalize_reduce_changes(changes),
        "actions": _normalize_reduce_actions(actions),
    }


def reduce_changes_and_actions(merged_changes: list[dict]) -> dict:
    """REDUCE phase: single LLM call to consolidate changes and generate actions."""
    candidate_changes = _normalize_reduce_changes(merged_changes or [])
    print("Starting REDUCE Phase...")
    if not candidate_changes:
        print("Final changes count: 0")
        return {
            "changes": [],
            "actions": [],
        }

    prompt_payload = candidate_changes[:20]
    prompt = f"""
You are a compliance reducer.
Task:
1. Merge similar changes.
2. Return final clean list of changes (max 10).
3. Generate concrete actions from those changes (max 10).

Return ONLY strict JSON matching this schema exactly:
{{
  "changes": [
    {{
      "type": "added|modified|removed",
      "category": "Other",
      "summary": "...",
      "impact": "..."
    }}
  ],
  "actions": [
    {{
      "action": "...",
      "priority": "High|Medium|Low",
      "owner": "..."
    }}
  ]
}}

INPUT_CHANGES:
{json.dumps(prompt_payload, ensure_ascii=True)}
"""

    for attempt in range(2):
        try:
            content = call_groq_with_retry(
                messages=[
                    {
                        "role": "system",
                        "content": "Return only valid JSON matching the required schema.",
                    },
                    {"role": "user", "content": _ensure_prompt_token_safe(prompt)},
                ],
                max_tokens=700,
                temperature=0.0,
                retries=1,
                initial_backoff=1.0,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            logger.warning("reduce_changes_and_actions LLM call failed attempt=%s error=%s", attempt + 1, exc)
            content = ""

        parsed = _parse_reduce_payload(content)
        if parsed is not None:
            parsed["changes"] = _normalize_reduce_changes(parsed.get("changes") or [])[:10]
            parsed["actions"] = _normalize_reduce_actions(parsed.get("actions") or [])[:10]
            logger.info("REDUCE phase: final_changes_count=%s", len(parsed.get("changes") or []))
            print(f"Final changes count: {len(parsed.get('changes') or [])}")
            return parsed

        logger.warning("reduce_changes_and_actions invalid JSON attempt=%s", attempt + 1)

    fallback_actions = default_actions().get("actions", [])[:10]
    fallback_result = {
        "changes": candidate_changes[:10],
        "actions": _normalize_reduce_actions(fallback_actions),
    }
    logger.info("REDUCE phase: final_changes_count=%s", len(fallback_result.get("changes") or []))
    print(f"Final changes count: {len(fallback_result.get('changes') or [])}")
    return fallback_result


def detect_changes(old_text: str, new_text: str) -> dict:
    """Detect material changes using MAP phase (per-clause LLM calls)."""
    try:
        if not old_text or not new_text:
            return _default_changes_response()

        old_text = _truncate_text_for_tokens(trim_text(old_text, 5500))
        new_text = _truncate_text_for_tokens(trim_text(new_text, 5500))

        old_clauses = _extract_filtered_clauses_for_map(old_text, label="changes_old", clause_prefix="old")
        new_clauses = _extract_filtered_clauses_for_map(new_text, label="changes_new", clause_prefix="new")

        if not old_clauses and not new_clauses:
            return _default_changes_response()

        print("Starting MAP Phase...")

        max_len = max(len(old_clauses), len(new_clauses))
        print(f"Processing {max_len} filtered clauses")
        old_clauses.extend([{}] * (max_len - len(old_clauses)))
        new_clauses.extend([{}] * (max_len - len(new_clauses)))

        all_changes = []
        clause_level_outputs = []
        seen_clause_pairs = set()
        map_stats = {"api_calls": 0}
        clauses_processed = 0

        for index in range(max_len):
            old_clause = old_clauses[index] if isinstance(old_clauses[index], dict) else {}
            new_clause = new_clauses[index] if isinstance(new_clauses[index], dict) else {}

            clause_id = str(
                new_clause.get("clause_id")
                or old_clause.get("clause_id")
                or f"pair-{index + 1}"
            )
            print(f"Processing clause_id: {clause_id}")

            pair_key = f"{clause_id}|{old_clause.get('content') or ''}|{new_clause.get('content') or ''}"
            if pair_key in seen_clause_pairs:
                continue
            seen_clause_pairs.add(pair_key)

            old_content = str(old_clause.get("content") or "").strip()
            new_content = str(new_clause.get("content") or "").strip()
            if not old_content and not new_content:
                continue
            if old_content == new_content:
                continue

            clause_payload = {
                "clause_id": clause_id,
                "old_content": old_content,
                "new_content": new_content,
            }

            clause_changes = map_changes_per_clause(clause_payload, stats=map_stats)
            clauses_processed += 1
            clause_level_outputs.append(clause_changes)
            all_changes.extend(clause_changes)

        logger.info(
            "MAP phase: clauses_processed=%s total_api_calls=%s",
            clauses_processed,
            int(map_stats.get("api_calls") or 0),
        )
        print(f"MAP Phase complete. Total extracted changes: {len(all_changes)}")

        unique_clean_changes = merge_and_dedupe_clause_changes(clause_level_outputs)

        mapped_changes = [
            {
                "type": item.get("type") or "modified",
                "category": "Other",
                "summary": trim_text(item.get("change") or "", 220),
                "impact": "Detected in clause-level MAP analysis",
            }
            for item in unique_clean_changes
        ]

        deduped_changes = deduplicate_items(mapped_changes)
        return _schema_response(changes=deduped_changes[:5])

    except Exception as e:
        logger.error("detect_changes failed: %s", e)
        return _default_changes_response()


def detect_compliance_gaps(new_text: str, policy_text: str) -> dict:
    """Detect compliance gaps using token-aware batched analysis."""
    try:
        if not new_text or not policy_text:
            return _default_gaps_response()

        new_text = _truncate_text_for_tokens(trim_text(new_text, 5500))
        policy_text = _truncate_text_for_tokens(trim_text(policy_text, 5500))

        new_text = _filter_text_for_llm(new_text, label="gaps_regulation")
        policy_text = _filter_text_for_llm(policy_text, label="gaps_policy")

        pairs = _prepare_pairs(new_text, policy_text, "REGULATION", "POLICY")
        if not pairs:
            return _default_gaps_response()

        use_summary = len(pairs) <= 6
        batch_input_budget = _derive_batch_input_budget(len(pairs), use_summary=use_summary)
        max_batch_calls = max(1, MAX_CALLS - 1 - (1 if use_summary else 0))
        pair_batches = build_batches(pairs, max_tokens_per_batch=batch_input_budget)
        while len(pair_batches) > max_batch_calls and batch_input_budget < MAX_INPUT_TOKENS:
            batch_input_budget = min(MAX_INPUT_TOKENS, batch_input_budget + 250)
            pair_batches = build_batches(pairs, max_tokens_per_batch=batch_input_budget)

        logger.info("detect_compliance_gaps: items=%s batches=%s batch_budget=%s", len(pairs), len(pair_batches), batch_input_budget)

        request_tokens_used = 0

        def reserve_tokens(prompt_text: str, output_tokens: int) -> bool:
            nonlocal request_tokens_used
            estimated_tokens = estimate_tokens(prompt_text) + output_tokens
            if request_tokens_used + estimated_tokens > MAX_TOTAL_TOKENS_PER_REQUEST:
                return False
            request_tokens_used += estimated_tokens
            return True

        summary = ""
        if use_summary:
            combined_for_summary = "\n\n".join([f"REGULATION:\n{item['left']}\n\nPOLICY:\n{item['right']}" for item in pairs])
            summary_prompt = f"""
Summarize key regulatory points from this regulation-policy comparison.
Avoid repetition. Be concise but complete.
Limit response to essential insights only. Avoid long explanations.

Return ONLY valid JSON. No explanation. No markdown. No text outside JSON.\n\nJSON schema:
{{
  "summary": "Compact summary preserving key obligations, thresholds, timelines, penalties, and scope"
}}

DOCUMENT:
{_truncate_text_for_tokens(combined_for_summary)}
"""
            summary_prompt = _ensure_prompt_token_safe(summary_prompt)
            if reserve_tokens(summary_prompt, SUMMARY_OUTPUT_TOKENS):
                summary_result = _safe_call(
                    prompt=summary_prompt,
                    max_tokens=SUMMARY_OUTPUT_TOKENS,
                    retries=2,
                    initial_backoff=4,
                    expect_schema=False,
                )
                if isinstance(summary_result, dict) and "error" not in summary_result:
                    summary_text = summary_result.get("summary") if isinstance(summary_result.get("summary"), str) else None
                    if summary_text and summary_text.strip():
                        summary = summary_text.strip()

        batch_entries = []
        for batch_index, batch in enumerate(pair_batches, start=1):
            prompt = _build_gap_prompt(batch_index, pair_batches, batch, summary)
            prompt = _ensure_prompt_token_safe(prompt)
            if not reserve_tokens(prompt, BATCH_OUTPUT_TOKENS):
                logger.warning("detect_compliance_gaps token budget exhausted before batch %s", batch_index)
                break
            batch_entries.append(
                {
                    "prompt": prompt,
                    "max_tokens": BATCH_OUTPUT_TOKENS,
                    "retries": 3,
                    "initial_backoff": 5,
                    "batch_size": len(batch),
                    "estimated_tokens": estimate_tokens(prompt),
                }
            )

        partial_results = asyncio.run(process_batches_parallel(batch_entries, label="gaps")) if batch_entries else []
        partial_results = [result for result in partial_results if isinstance(result, dict) and "error" not in result]

        if not partial_results:
            return _default_gaps_response()

        merge_prompt = f"""
Combine the following analyses into one final JSON response.
Avoid repetition. Be concise but complete.
Limit response to essential insights only. Avoid long explanations.
Keep only material, non-duplicate compliance gaps.

Return ONLY valid JSON. No explanation. No markdown. No text outside JSON.\n\nJSON schema:
{{
  "compliance_gaps": [
    {{
      "issue": "Gap description <=2 lines",
      "risk": "High | Medium | Low",
      "regulation_requirement": "What regulation requires",
      "policy_current_state": "What policy says/doesn't say"
    }}
  ]
}}

PARTIAL_ANALYSES:
{json.dumps(partial_results, ensure_ascii=True)}
"""
        merge_prompt = _ensure_prompt_token_safe(merge_prompt)
        if reserve_tokens(merge_prompt, MERGE_OUTPUT_TOKENS):
            merged = _safe_call(prompt=merge_prompt, max_tokens=MERGE_OUTPUT_TOKENS, retries=2, initial_backoff=4)
            if isinstance(merged, dict) and "error" not in merged and isinstance(merged.get("compliance_gaps"), list):
                gaps = merged.get("compliance_gaps", [])
                gaps = sorted(gaps, key=lambda g: _priority_value((g or {}).get("risk", "Low")), reverse=True)
                deduped = deduplicate_items(gaps[:6])
                logger.info("deduplicated_output=%s", json.dumps({"compliance_gaps": deduped}, ensure_ascii=True)[:1200])
                return _schema_response(compliance_gaps=deduped)

        fallback = merge_chunk_results(partial_results, "compliance_gaps")
        fallback = sorted(fallback, key=lambda g: _priority_value((g or {}).get("risk", "Low")), reverse=True)
        deduped = deduplicate_items(fallback[:6] if fallback else [])
        logger.info("deduplicated_output=%s", json.dumps({"compliance_gaps": deduped}, ensure_ascii=True)[:1200])
        return _schema_response(compliance_gaps=deduped)

    except Exception as e:
        logger.error("detect_compliance_gaps failed: %s", e)
        return _default_gaps_response()


def analyze_impact(impact_input: dict) -> dict:
    """Analyze impacts based on detected changes and compliance gaps."""
    try:
        if not impact_input or not isinstance(impact_input, dict):
            return _schema_response()

        changes = impact_input.get("changes", [])
        gaps = impact_input.get("compliance_gaps", [])

        if not changes and not gaps:
            return _schema_response()

        combined_text = ""
        if changes:
            combined_text += "CHANGES DETECTED:\n" + json.dumps(changes[:3], indent=2) + "\n\n"
        if gaps:
            combined_text += "COMPLIANCE GAPS FOUND:\n" + json.dumps(gaps[:3], indent=2)

        combined_text = _filter_text_for_llm(combined_text, label="impacts")

        prompt = f"""
Analyze the business and compliance impact of these detected changes and gaps.
Provide 2-3 key impacts with severity assessment.

CONTEXT:
{_truncate_text_for_tokens(combined_text)}

Return ONLY valid JSON. No explanation. No markdown. No text outside JSON.\n\nJSON schema:
{{
  "impacts": [
    {{
            "title": "Impact title",
      "description": "Impact description",
            "severity": "High | Medium | Low",
            "impacted_departments": ["Compliance", "Risk", "Operations"]
    }}
  ]
}}
"""
        prompt = _ensure_prompt_token_safe(prompt)
        result = _safe_call(prompt=prompt, max_tokens=BATCH_OUTPUT_TOKENS, retries=2, initial_backoff=4)

        if isinstance(result, dict) and "error" not in result and isinstance(result.get("impacts"), list):
            deduped_impacts = deduplicate_items(_normalize_impacts_list(result.get("impacts", [])[:3]))
            logger.info("deduplicated_output=%s", json.dumps({"impacts": deduped_impacts}, ensure_ascii=True)[:1200])
            return _schema_response(impacts=deduped_impacts)

        return _schema_response()

    except Exception as e:
        logger.error("analyze_impact failed: %s", e)
        return _schema_response()


def generate_actions(actions_input: dict) -> dict:
    """Generate actionable remediation steps from compliance gaps and impacts."""
    try:
        if not actions_input or not isinstance(actions_input, dict):
            return _schema_response()

        changes = actions_input.get("changes", [])
        gaps = actions_input.get("compliance_gaps", [])
        impacts = actions_input.get("impacts", [])

        if not gaps and not impacts:
            fallback_actions = default_actions().get("actions", [])
            return _schema_response(actions=fallback_actions)

        combined_text = ""
        if changes:
            combined_text += "CHANGES:\n" + json.dumps(changes[:2], indent=2) + "\n\n"
        if gaps:
            combined_text += "COMPLIANCE GAPS:\n" + json.dumps(gaps[:4], indent=2) + "\n\n"
        if impacts:
            combined_text += "IMPACTS:\n" + json.dumps(impacts[:4], indent=2)

        combined_text = _filter_text_for_llm(combined_text, label="actions")

        prompt = f"""
Generate 2-6 concrete and implementable compliance actions.
Each action must map to one or more compliance gaps and the corresponding impacts.
Each action should include owner, priority, and timeline.

CONTEXT:
{_truncate_text_for_tokens(combined_text)}

Return ONLY valid JSON. No explanation. No markdown. No text outside JSON.\n\nJSON schema:
{{
  "actions": [
    {{
      "action": "Specific action description",
      "priority": "High | Medium | Low",
      "owner": "Team/Department responsible"
    }}
  ]
}}
"""
        prompt = _ensure_prompt_token_safe(prompt)
        result = _safe_call(prompt=prompt, max_tokens=BATCH_OUTPUT_TOKENS, retries=2, initial_backoff=4)

        if isinstance(result, dict) and "error" not in result and isinstance(result.get("actions"), list):
            deduped_actions = deduplicate_items(result.get("actions", [])[:6])
            if not deduped_actions:
                deduped_actions = default_actions().get("actions", [])
            logger.info("deduplicated_output=%s", json.dumps({"actions": deduped_actions}, ensure_ascii=True)[:1200])
            return _schema_response(actions=deduped_actions)

        return _schema_response(actions=default_actions().get("actions", []))

    except Exception as e:
        logger.error("generate_actions failed: %s", e)
        return _schema_response(actions=default_actions().get("actions", []))



