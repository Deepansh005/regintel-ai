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

from app.services.llm_router import call_groq_with_retry
from app.services.semantic_block_extractor import extract_semantic_blocks
from app.services.semantic_block_matcher import match_blocks, to_matched_blocks_payload
from app.services.strict_diff_engine import compare_all_matched_blocks, compare_blocks_batch
from app.services.change_processor import hard_validate_changes, deduplicate_changes, limit_output_changes, render_final_output

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
STRICT_JSON_ARRAY_INSTRUCTION = "Return ONLY valid JSON array. No explanation. No markdown. No text outside JSON."
STRICT_SCHEMA_INSTRUCTION = (
    "Always respond with this top-level JSON schema exactly: "
    '{"changes": [], "compliance_gaps": [], "impacts": [], "actions": []}'
)
VAGUE_CHANGE_TERMS = ("improve", "enhance", "develop", "updated", "improved", "policy updated")
CONDITION_SIGNAL_TERMS = (
    "shall",
    "must",
    "required",
    "if ",
    "unless",
    "provided that",
    "at least",
    "not less than",
    "no more than",
    "threshold",
    "limit",
    "within",
)

FIELD_NORMALIZATION_RULES = [
    ("Dividend Payout Cap", [r"dividend", r"payout|cap|limit"]),
    ("STR Reporting Timeline", [r"str|suspicious transaction", r"report|reporting|timeline|deadline|day"]),
    ("CET1 Ratio Eligibility", [r"cet1|common equity tier\s*1", r"eligib|threshold|bucket|ratio"]),
    ("Regulatory Reporting Requirement", [r"report|reporting|disclosure|filing", r"shall|must|required|within"]),
    ("Eligibility Condition", [r"eligib|condition|criteria|qualif"]),
    ("Restriction or Prohibition", [r"prohibit|restriction|shall not|must not|not allowed"]),
    ("PAT-Based Payout Formula", [r"pat|profit after tax", r"formula|ratio|payout|distribution"]),
    ("Regulatory Limit Threshold", [r"threshold|limit|ceiling|cap|not exceed|max(?:imum)?"]),
    ("Capital Adequacy Requirement", [r"crar|capital adequacy|capital to risk|tier\s*1|tier\s*2"]),
    ("NPA Classification Rule", [r"npa|non-performing asset|overdue", r"classif|stage|bucket|aging"]),
    ("Provisioning Requirement", [r"provision|provisioning|expected credit loss|ecl", r"percent|%|minimum"]),
    ("Exposure Limit", [r"exposure|single borrower|group borrower|large exposure", r"limit|cap|ceiling|%"]),
    ("KYC Periodicity Requirement", [r"kyc|know your customer", r"periodic|periodicity|refresh|update|year|month"]),
    ("AML-CFT Monitoring Requirement", [r"aml|cft|anti[-\s]?money|terror", r"monitor|screen|surveillance|transaction"]),
    ("Board Approval Requirement", [r"board|committee|governance|approval", r"approve|ratify|sanction|required"]),
    ("Return Filing Timeline", [r"return|filing|submission", r"within|day|days|month|timeline|deadline"]),
]

FIELD_ALIAS_NORMALIZATION = [
    (r"\bdividend\s+(?:payout\s+)?cap\b|\bpayout\s+cap\b", "Dividend Payout Cap"),
    (r"\bstr\b.*\b(?:timeline|deadline|reporting)\b|\bsuspicious\s+transaction\s+report", "STR Reporting Timeline"),
    (r"\bcet1\b.*\b(?:eligib|threshold|bucket|ratio)\b|\bcommon\s+equity\s+tier\s*1\b", "CET1 Ratio Eligibility"),
    (r"\bpat\b.*\b(?:formula|ratio|payout)\b|\bprofit\s+after\s+tax\b", "PAT-Based Payout Formula"),
    (r"\bcrar\b|\bcapital\s+adequacy\b|\btier\s*1\b", "Capital Adequacy Requirement"),
    (r"\bnpa\b|\bnon[-\s]?performing\s+asset\b", "NPA Classification Rule"),
    (r"\bprovision(?:ing)?\b|\becl\b|\bexpected\s+credit\s+loss\b", "Provisioning Requirement"),
    (r"\bexposure\s+limit\b|\bsingle\s+borrower\b|\bgroup\s+borrower\b", "Exposure Limit"),
    (r"\bkyc\b|\bknow\s+your\s+customer\b", "KYC Periodicity Requirement"),
    (r"\baml\b|\bcft\b|\banti[-\s]?money\b", "AML-CFT Monitoring Requirement"),
    (r"\bboard\s+approval\b|\bcommittee\s+approval\b", "Board Approval Requirement"),
    (r"\breturn\s+filing\b|\bfiling\s+timeline\b|\bsubmission\s+deadline\b", "Return Filing Timeline"),
]


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


def _clean_llm_response_text(raw_response: str) -> str:
    response = str(raw_response or "").strip()

    # remove markdown fences if present, even when surrounded by plain text
    if "```" in response:
        fenced_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response, re.IGNORECASE)
        if fenced_match:
            response = fenced_match.group(1).strip()

    if response.lower().startswith("json"):
        response = response[4:].strip()

    return _strip_trailing_commas(response)


def _extract_first_valid_json(raw_response: str):
    """Extract only the first valid JSON object/array from a noisy response."""
    response = _clean_llm_response_text(raw_response)
    if not response:
        return None

    # Attempt direct parse first.
    try:
        return _parse_json_without_duplicate_keys(response)
    except Exception:
        pass

    # If multiple JSON-like blocks exist, scan and pick first valid JSON object or array.
    starters = [index for index, ch in enumerate(response) if ch in "[{"]
    for start in starters:
        opener = response[start]
        closer = "}" if opener == "{" else "]"
        depth = 0
        in_string = False
        escaped = False

        for end in range(start, len(response)):
            ch = response[end]

            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue

            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    candidate = _strip_trailing_commas(response[start:end + 1].strip())
                    try:
                        return _parse_json_without_duplicate_keys(candidate)
                    except Exception:
                        break

    return None


def clean_llm_json(raw_response: str) -> dict | None:
    if not raw_response or not isinstance(raw_response, str):
        return None

    parsed = _extract_first_valid_json(raw_response)

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


def _simple_paragraph_blocks(text: str, prefix: str) -> list[dict]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", str(text or "")) if part and part.strip()]
    return [
        {
            "block_id": f"{prefix}-{index}",
            "heading": "Paragraph Block",
            "content": _truncate_text_for_tokens(paragraph, max_tokens=350),
        }
        for index, paragraph in enumerate(paragraphs, start=1)
    ]


def _dedupe_clause_list(clauses: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for clause in clauses or []:
        if not isinstance(clause, dict):
            continue
        clause_id = str(clause.get("clause_id") or clause.get("block_id") or "").strip().lower()
        title = str(clause.get("title") or clause.get("heading") or "").strip().lower()
        content = str(clause.get("content") or "").strip().lower()
        key = f"{clause_id}|{title}|{content}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(clause)
    return deduped


def _filter_text_for_llm(text: str, label: str) -> str:
    """Apply semantic block filtering right before LLM prompt construction."""
    source_text = str(text or "").strip()
    if not source_text:
        return source_text

    try:
        all_clauses = extract_semantic_blocks(source_text)
        if not all_clauses:
            all_clauses = _simple_paragraph_blocks(source_text, prefix=f"{label}-fallback")
        if not all_clauses:
            return source_text

        all_clauses = _dedupe_clause_list(all_clauses)
        scored = sorted(
            all_clauses,
            key=lambda block: _score_relevance(str(block.get("content") or "")),
            reverse=True,
        )
        filtered_clauses = _dedupe_clause_list(scored[:TOP_ITEM_LIMIT])

        logger.info(
            "Using semantic blocks for LLM processing | stage=%s before=%s after=%s",
            label,
            len(all_clauses),
            len(filtered_clauses),
        )

        rebuilt = "\n\n".join(str(clause.get("content") or "").strip() for clause in filtered_clauses).strip()
        return rebuilt or source_text
    except Exception as exc:
        logger.warning("Semantic block filtering failed at stage=%s, using original text: %s", label, exc)
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


def _normalize_impact_department(value: str) -> str:
    label = str(value or "").strip()
    if not label:
        return "Compliance"
    return label


def _infer_impact_departments(text: str) -> list[str]:
    content = str(text or "").lower()
    departments: list[str] = []

    def add_department(name: str) -> None:
        normalized = _normalize_impact_department(name)
        if normalized not in departments:
            departments.append(normalized)

    if any(keyword in content for keyword in ["capital", "adequacy", "tier 1", "tier-1", "ccar", "provisioning", "limit", "exposure"]):
        add_department("Finance")
        add_department("Risk")

    if any(keyword in content for keyword in ["kyc", "customer due diligence", "cdd", "onboarding"]):
        add_department("Compliance")
        add_department("Operations")

    if any(keyword in content for keyword in ["aml", "anti-money", "anti money", "cft", "sanction", "suspicious transaction", "str"]):
        add_department("Risk")
        add_department("Compliance")

    if any(keyword in content for keyword in ["report", "reporting", "filing", "submission", "timeline", "deadline"]):
        add_department("Operations")
        add_department("Compliance")

    if any(keyword in content for keyword in ["audit", "evidence", "control", "traceability", "document"]):
        add_department("Audit")
        add_department("Compliance")

    if any(keyword in content for keyword in ["legal", "statutory", "regulation", "obligation", "penalty", "sanction"]):
        add_department("Legal")
        add_department("Compliance")

    if not departments:
        add_department("Compliance")

    return departments[:3]


def _infer_impact_severity(text: str) -> str:
    content = str(text or "").lower()
    if any(keyword in content for keyword in ["capital", "aml", "sanction", "penalty", "breach", "restriction", "prohibition", "exposure", "provisioning", "tier 1", "tier-1"]):
        return "High"
    if any(keyword in content for keyword in ["kyc", "report", "reporting", "filing", "deadline", "timeline", "audit"]):
        return "Medium"
    return "Medium"


def _build_impact_description(gap_text: str, department: str, severity: str) -> str:
    gap_text = _clean_text_for_llm(gap_text, label="impact") if "_clean_text_for_llm" in globals() else str(gap_text or "").strip()
    base_gap = gap_text[:180] if gap_text else "the identified compliance gap"
    department_key = str(department or "").strip().lower()

    consequence_map = {
        "finance": "can lead to regulatory penalties, capital constraints, and funding restrictions",
        "risk": "can increase control failures, supervisory scrutiny, and residual risk exposure",
        "compliance": "can result in compliance breaches, remediation escalation, and regulatory findings",
        "operations": "can disrupt operational workflows, increase exception handling, and delay execution",
        "legal": "can create legal exposure, enforcement action risk, and adverse statutory consequences",
        "audit": "can weaken audit defensibility, evidence trails, and assurance outcomes",
    }

    consequence = consequence_map.get(department_key, "can create business disruption and regulatory exposure")
    severity_label = str(severity or "Medium").upper()
    return f"Failure to address {base_gap} in {department} can {consequence}. Severity: {severity_label}."


def _infer_impacts_from_inputs(changes: list[dict], gaps: list[dict]) -> list[dict]:
    inferred: list[dict] = []

    source_items = []
    if gaps:
        source_items.extend([item for item in gaps if isinstance(item, dict)])
    if not source_items and changes:
        source_items.extend([item for item in changes if isinstance(item, dict)])

    for item in source_items:
        gap_text = " ".join(
            str(item.get(field) or "")
            for field in ("title", "issue", "gap", "description", "reason", "recommendation", "summary")
        ).strip()
        departments = _infer_impact_departments(gap_text)
        severity = _infer_impact_severity(gap_text)

        for department in departments:
            inferred.append(
                {
                    "department": department,
                    "severity": severity,
                    "description": _build_impact_description(gap_text, department, severity),
                }
            )

    deduped: list[dict] = []
    seen = set()
    for item in inferred:
        key = (
            str(item.get("department") or "").strip().lower(),
            str(item.get("severity") or "").strip().lower(),
            str(item.get("description") or "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    return deduped[:30]


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

    response = str(content).strip()
    original_response = response

    # remove markdown/backticks before parsing
    if "`" in response:
        if "```" in response:
            fenced_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response, re.IGNORECASE)
            if fenced_match:
                response = fenced_match.group(1).strip()
        else:
            parts = response.split("`")
            if len(parts) > 1:
                response = parts[1].strip()

    # extract JSON array only when available
    start = response.find("[")
    end = response.rfind("]")
    if start != -1 and end != -1 and end >= start:
        response = response[start:end + 1]

    response = _strip_trailing_commas(response)

    try:
        return _parse_json_without_duplicate_keys(response)
    except Exception:
        fallback = _extract_first_valid_json(_clean_llm_response_text(original_response))
        if fallback is not None:
            return fallback
        print("❌ JSON FAILED:", response[:200])
        return []


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
                "content": f"{system_prompt}\n{STRICT_JSON_INSTRUCTION}\n{STRICT_JSON_ARRAY_INSTRUCTION}{strict_schema_message}{retry_message}",
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
            "title": "Requirement title",
            "type": "added | removed | modified",
            "summary": "Specific factual change in <=2 lines",
            "source": "RBI | POLICY"
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
            "title": "Gap title",
            "severity": "High | Medium | Low",
            "description": "Specific mismatch between regulation and policy",
            "recommendation": "Direct remediation action"
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
        all_clauses = extract_semantic_blocks(source_text)
        if not all_clauses:
            all_clauses = _simple_paragraph_blocks(source_text, prefix=f"{clause_prefix}-fallback")
        if not all_clauses:
            return []

        all_clauses = _dedupe_clause_list(all_clauses)
        ranked_blocks = sorted(
            all_clauses,
            key=lambda block: _score_relevance(str(block.get("content") or "")),
            reverse=True,
        )
        filtered_clauses = _dedupe_clause_list(ranked_blocks[:TOP_ITEM_LIMIT])

        if not filtered_clauses:
            filtered_clauses = all_clauses

        logger.info(
            "Using semantic blocks for LLM processing | stage=%s before=%s after=%s",
            label,
            len(all_clauses),
            len(filtered_clauses),
        )

        normalized = []
        for index, clause in enumerate(filtered_clauses, start=1):
            content = str(clause.get("content") or "").strip()
            if not content:
                continue
            clause_id = str(clause.get("block_id") or clause.get("clause_id") or f"{clause_prefix}-{index}").strip()
            normalized.append(
                {
                    "clause_id": clause_id,
                    "title": str(clause.get("heading") or clause.get("title") or "").strip(),
                    "content": _truncate_text_for_tokens(content, max_tokens=350),
                }
            )
        return normalized
    except Exception as exc:
        logger.warning("Semantic block extraction/filtering failed for stage=%s, using paragraph fallback: %s", label, exc)
        fallback_blocks = _simple_paragraph_blocks(source_text, prefix=f"{clause_prefix}-fallback")
        return [
            {
                "clause_id": str(block.get("block_id") or f"{clause_prefix}-{index}"),
                "title": str(block.get("heading") or ""),
                "content": str(block.get("content") or ""),
            }
            for index, block in enumerate(fallback_blocks, start=1)
            if str(block.get("content") or "").strip()
        ]


def _log_clause_structure(label: str, clauses: list[dict]) -> None:
    clause_list = [item for item in (clauses or []) if isinstance(item, dict)]
    total = len(clause_list)
    if total == 0:
        logger.info("Semantic block analysis | document=%s total=0", label)
        return

    title_count = sum(1 for item in clause_list if str(item.get("title") or "").strip())
    content_lengths = [len(str(item.get("content") or "")) for item in clause_list]
    avg_chars = int(round(sum(content_lengths) / total)) if total else 0
    max_chars = max(content_lengths, default=0)
    sample_titles = [
        trim_text(str(item.get("title") or "").strip(), 80)
        for item in clause_list
        if str(item.get("title") or "").strip()
    ][:3]

    logger.info(
        "Semantic block analysis | document=%s total=%s titled=%s avg_chars=%s max_chars=%s sample_titles=%s",
        label,
        total,
        title_count,
        avg_chars,
        max_chars,
        sample_titles,
    )


def _normalized_similarity_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _title_for_matching(clause: dict) -> str:
    if not isinstance(clause, dict):
        return ""
    return _normalized_similarity_text(str(clause.get("title") or clause.get("heading") or ""))


def _content_preview_for_matching(clause: dict, limit: int = 200) -> str:
    if not isinstance(clause, dict):
        return ""
    content = str(clause.get("content") or "")
    return _normalized_similarity_text(content[:limit])


def _similarity_ratio(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _match_old_new_clauses(old_clauses: list[dict], new_clauses: list[dict]) -> list[dict]:
    """Match clauses with primary title similarity and secondary content-preview similarity."""
    old_items = [item for item in (old_clauses or []) if isinstance(item, dict)]
    new_items = [item for item in (new_clauses or []) if isinstance(item, dict)]

    matched_pairs: list[dict] = []
    used_old: set[int] = set()
    used_new: set[int] = set()

    title_threshold = 0.55
    content_threshold = 0.45

    # Primary pass: title/heading similarity.
    for new_index, new_clause in enumerate(new_items):
        new_title = _title_for_matching(new_clause)
        if not new_title:
            continue

        best_old_index = -1
        best_score = 0.0

        for old_index, old_clause in enumerate(old_items):
            if old_index in used_old:
                continue
            old_title = _title_for_matching(old_clause)
            if not old_title:
                continue

            score = _similarity_ratio(old_title, new_title)
            if score > best_score:
                best_score = score
                best_old_index = old_index

        if best_old_index >= 0 and best_score >= title_threshold:
            used_old.add(best_old_index)
            used_new.add(new_index)
            matched_pairs.append(
                {
                    "old_clause": old_items[best_old_index],
                    "new_clause": new_clause,
                    "match_type": "title",
                    "score": round(best_score, 4),
                }
            )

    # Secondary pass: content similarity using first 200 chars.
    for new_index, new_clause in enumerate(new_items):
        if new_index in used_new:
            continue

        new_preview = _content_preview_for_matching(new_clause, limit=200)
        if not new_preview:
            continue

        best_old_index = -1
        best_score = 0.0

        for old_index, old_clause in enumerate(old_items):
            if old_index in used_old:
                continue

            old_preview = _content_preview_for_matching(old_clause, limit=200)
            if not old_preview:
                continue

            score = _similarity_ratio(old_preview, new_preview)
            if score > best_score:
                best_score = score
                best_old_index = old_index

        if best_old_index >= 0 and best_score >= content_threshold:
            used_old.add(best_old_index)
            used_new.add(new_index)
            matched_pairs.append(
                {
                    "old_clause": old_items[best_old_index],
                    "new_clause": new_clause,
                    "match_type": "content_fallback",
                    "score": round(best_score, 4),
                }
            )

    unmatched_old = [old_items[index] for index in range(len(old_items)) if index not in used_old]
    unmatched_new = [new_items[index] for index in range(len(new_items)) if index not in used_new]

    for old_clause in unmatched_old:
        matched_pairs.append(
            {
                "old_clause": old_clause,
                "new_clause": None,
                "status": "removed",
            }
        )

    for new_clause in unmatched_new:
        matched_pairs.append(
            {
                "old_clause": None,
                "new_clause": new_clause,
                "status": "added",
            }
        )

    logger.info(
        "Clause matching summary | total_matches=%s unmatched_old=%s unmatched_new=%s",
        len(matched_pairs) - len(unmatched_old) - len(unmatched_new),
        len(unmatched_old),
        len(unmatched_new),
    )

    return matched_pairs


def _normalize_coverage_status(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace(" ", "_")
    if normalized in {"covered", "not_covered", "partial"}:
        return normalized
    return "not_covered"


def _normalize_risk_level(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"low", "medium", "high"}:
        return normalized
    return "medium"


def _extract_change_description(change_item: dict) -> str:
    if not isinstance(change_item, dict):
        return ""
    return str(
        change_item.get("summary")
        or change_item.get("description")
        or change_item.get("change")
        or ""
    ).strip()


def _select_relevant_policy_clauses(change_description: str, policy_clauses: list[dict], limit: int = 3) -> list[dict]:
    if not change_description.strip():
        return []

    scored: list[tuple[float, dict]] = []
    normalized_change = _normalized_similarity_text(change_description)

    for clause in policy_clauses or []:
        if not isinstance(clause, dict):
            continue
        clause_text = " ".join(
            [
                str(clause.get("title") or "").strip(),
                str(clause.get("content") or "")[:400].strip(),
            ]
        ).strip()
        normalized_clause = _normalized_similarity_text(clause_text)
        if not normalized_clause:
            continue
        score = _similarity_ratio(normalized_change, normalized_clause)
        scored.append((score, clause))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:limit] if item[0] > 0.0]


def _parse_policy_coverage_assessment(raw_content: str) -> dict | None:
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

    if parsed is None:
        object_match = re.search(r"\{[\s\S]*\}", candidate)
        if object_match:
            extracted = _strip_trailing_commas(object_match.group(0).strip())
            try:
                parsed = _parse_json_without_duplicate_keys(extracted)
            except Exception:
                parsed = None

    if not isinstance(parsed, dict):
        return None

    return {
        "status": _normalize_coverage_status(parsed.get("status")),
        "risk": _normalize_risk_level(parsed.get("risk")),
        "explanation": trim_text(str(parsed.get("explanation") or "").strip(), 220),
    }


def _assess_change_against_policy(change_description: str, relevant_policy_clauses: list[dict], stats: dict | None = None) -> dict:
    policy_clause_text = "\n\n".join(
        [
            f"- CLAUSE_ID: {str(clause.get('clause_id') or '').strip()}\n"
            f"  TITLE: {trim_text(str(clause.get('title') or '').strip(), 120)}\n"
            f"  CONTENT: {trim_text(str(clause.get('content') or '').strip(), 500)}"
            for clause in (relevant_policy_clauses or [])
            if isinstance(clause, dict)
        ]
    ).strip()

    prompt = (
        "Check if this change is already covered in company policy.\n\n"
        "Output:\n"
        "{\n"
        '  "status": "covered/not_covered/partial",\n'
        '  "risk": "low/medium/high",\n'
        '  "explanation": "short reason"\n'
        "}\n\n"
        "CHANGE DESCRIPTION:\n"
        f"{trim_text(change_description, 350)}\n\n"
        "RELEVANT POLICY CLAUSES:\n"
        f"{policy_clause_text or 'No relevant policy clause found.'}"
    )

    for attempt in range(2):
        if isinstance(stats, dict):
            stats["policy_eval_calls"] = int(stats.get("policy_eval_calls") or 0) + 1
        try:
            content = call_groq_with_retry(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a strict JSON compliance coverage evaluator. Return only valid JSON.",
                    },
                    {"role": "user", "content": _ensure_prompt_token_safe(prompt)},
                ],
                max_tokens=150,
                temperature=0.0,
                retries=1,
                initial_backoff=1.0,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            logger.warning("policy_coverage_assessment failed attempt=%s error=%s", attempt + 1, exc)
            content = ""

        parsed = _parse_policy_coverage_assessment(content)
        if parsed is not None:
            return parsed

    return {
        "status": "not_covered",
        "risk": "medium",
        "explanation": "Unable to confidently map this change to policy coverage.",
    }


def _parse_clause_comparison_payload(raw_content: str) -> list[dict] | None:
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

    if not isinstance(parsed, dict):
        return None

    raw_changes = parsed.get("changes")
    if not isinstance(raw_changes, list):
        return None

    normalized_changes = []
    for item in raw_changes:
        if not isinstance(item, dict):
            continue

        change_type = str(item.get("type") or "").strip().lower()
        if change_type not in {"added", "modified", "removed"}:
            continue

        field = _normalize_change_summary_text(str(item.get("field") or "").strip())
        old_text = _normalize_change_summary_text(str(item.get("old") or "").strip())
        new_text = _normalize_change_summary_text(str(item.get("new") or "").strip())

        if not field and not old_text and not new_text:
            continue

        if old_text and new_text:
            description = f"{field}: {old_text} -> {new_text}" if field else f"{old_text} -> {new_text}"
        elif old_text:
            description = f"{field}: removed {old_text}" if field else f"removed {old_text}"
        else:
            description = f"{field}: added {new_text}" if field else f"added {new_text}"

        normalized_changes.append(
            {
                "type": change_type,
                "field": trim_text(field, 140),
                "old": trim_text(old_text, 220),
                "new": trim_text(new_text, 220),
                "change": trim_text(description, 280),
            }
        )

    return normalized_changes


def filter_changes(changes):
    print("Before filter:", len(changes or []))
    filtered = []
    removed_count = 0
    for c in changes or []:
        text = str(c).lower()

        # remove no-change outputs
        if "no change" in text:
            removed_count += 1
            continue

        # remove type none
        if isinstance(c, dict) and str(c.get("type") or "").strip().lower() == "none":
            removed_count += 1
            continue

        # relaxed rule: only reject very short entries (<5 words)
        if isinstance(c, dict):
            merged_text = " ".join(
                [
                    str(c.get("field") or ""),
                    str(c.get("old") or ""),
                    str(c.get("new") or ""),
                ]
            ).strip()
            if len(merged_text.split()) < 5:
                removed_count += 1
                continue

        filtered.append(c)

    print("Filtered vague changes:", removed_count)
    print("After filter:", len(filtered))
    return filtered


def _has_numeric_or_condition_signal(field: str, old_value: str, new_value: str) -> bool:
    old_text = str(old_value or "")
    new_text = str(new_value or "")
    field_text = str(field or "")
    merged = f"{field_text} {old_text} {new_text}".lower()

    if any(char.isdigit() for char in new_text):
        return True
    if any(char.isdigit() for char in old_text):
        return True

    return any(term in merged for term in CONDITION_SIGNAL_TERMS)


def is_valid(change: dict) -> bool:
    if not isinstance(change, dict):
        return False

    change_type = str(change.get("type") or "").strip().lower()
    if change_type not in {"added", "removed", "modified", "threshold_change", "missing_requirement", "modified_requirement", "extra_policy_rule"}:
        return False

    field = str(change.get("field") or "").strip()
    old_value = str(change.get("old") or "").strip()
    new_value = str(change.get("new") or "").strip()

    merged_text = f"{field} {old_value} {new_value}".lower()
    if "no change" in merged_text:
        return False
    if any(term in merged_text for term in VAGUE_CHANGE_TERMS):
        return False

    if len(merged_text.split()) < 5:
        return False

    if change_type == "modified":
        return old_value != new_value

    if change_type == "threshold_change":
        return old_value != new_value and (any(char.isdigit() for char in old_value) or any(char.isdigit() for char in new_value))

    if change_type in {"missing_requirement", "modified_requirement", "extra_policy_rule"}:
        field = str(change.get("field") or "").strip()
        return len(field.split()) >= 2

    return True


def final_clean(changes):
    clean = []
    seen = set()
    for c in changes or []:
        if not isinstance(c, dict):
            continue

        if not is_valid(c):
            continue

        field = str(c.get("field") or "").strip()
        old_value = str(c.get("old") or "").strip()
        new_value = str(c.get("new") or "").strip()

        signature = (
            _normalize_change_text(field),
            _normalize_change_text(old_value),
            _normalize_change_text(new_value),
        )
        if signature in seen:
            continue
        seen.add(signature)

        clean.append(
            {
                "type": str(c.get("type") or "modified").strip().lower(),
                "field": trim_text(field, 140),
                "old": trim_text(old_value, 220),
                "new": trim_text(new_value, 220),
                "change": trim_text(str(c.get("change") or f"{field}: {old_value} -> {new_value}").strip(), 280),
            }
        )

    return clean


def _contains_vague_change_terms(description: str) -> bool:
    text = _normalize_change_text(description)
    if not text:
        return False
    return any(term in text for term in VAGUE_CHANGE_TERMS)


def _is_high_quality_change_description(description: str) -> bool:
    text = _normalize_change_summary_text(description)
    if not text:
        return False
    if _contains_vague_change_terms(text):
        return False
    return len(text.split()) >= 4


def map_changes_per_clause(clause, stats: dict | None = None) -> list[dict]:
    """Compare one old/new clause pair and return only meaningful regulatory changes."""
    if not isinstance(clause, dict):
        return []

    clause_id = str(clause.get("clause_id") or "unknown")
    old_content = _truncate_text_for_tokens(str(clause.get("old_content") or ""), max_tokens=350)
    new_content = _truncate_text_for_tokens(str(clause.get("new_content") or ""), max_tokens=350)

    if not old_content and not new_content:
        logger.info("Clause compare | clause_id=%s skipped=empty_pair", clause_id)
        return []

    user_prompt = (
        "Compare OLD vs NEW clauses strictly.\n"
        "Extract ONLY:\n"
        "- numeric changes\n"
        "- threshold changes\n"
        "- condition changes\n"
        "- obligations added/removed\n\n"
        "DO NOT summarize.\n"
        "DO NOT generalize.\n"
        "DO NOT interpret.\n"
        "DO NOT infer meaning.\n\n"
        "BAD example:\n"
        "- policy updated\n\n"
        "GOOD example:\n"
        "- Dividend payout limit changed from 50% to 75%\n\n"
        "If no explicit change exists, return exactly: {\"changes\": []}\n"
        "Never output \"no change\" text.\n\n"
        "STRICT OUTPUT FORMAT:\n"
        "{\n"
        '  "changes": [\n'
        "    {\n"
        '      "type": "added/removed/modified",\n'
        '      "field": "...",\n'
        '      "old": "...",\n'
        '      "new": "..."\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "OLD CLAUSE:\n"
        f"{old_content}\n\n"
        "NEW CLAUSE:\n"
        f"{new_content}"
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
                        "content": "You are a strict JSON regulatory clause comparison assistant. Return only valid JSON.",
                    },
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=260,
                temperature=0.0,
                retries=1,
                initial_backoff=1.0,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            logger.warning("map_changes_per_clause LLM call failed clause_id=%s attempt=%s error=%s", clause_id, attempt + 1, exc)
            content = ""

        parsed = _parse_clause_comparison_payload(content)
        if parsed is not None:
            raw_changes = parsed
            # TEMP DEBUG MODE: disable filtering completely.
            filtered_changes = raw_changes
            final_changes = final_clean(filtered_changes)

            print(f"Raw changes: {len(raw_changes)}")
            print(f"After filter: {len(filtered_changes)}")
            print(f"Final clean: {len(final_changes)}")

            logger.info(
                "map_changes_per_clause clause_id=%s tokens_used=%s",
                clause_id,
                prompt_tokens + estimate_tokens(content),
            )

            if not final_changes:
                logger.info("Clause compare | clause_id=%s skipped=none", clause_id)
                return []

            strict_changes = []
            for item in final_changes:
                if not isinstance(item, dict):
                    continue
                description = str(item.get("change") or "").strip()
                change_type = str(item.get("type") or "modified").strip().lower()
                if change_type not in {"added", "modified", "removed"}:
                    continue
                if not description:
                    continue
                if not _is_high_quality_change_description(description):
                    continue
                strict_changes.append(
                    {
                        "change": description,
                        "type": change_type,
                        "field": str(item.get("field") or "").strip(),
                        "old": str(item.get("old") or "").strip(),
                        "new": str(item.get("new") or "").strip(),
                    }
                )

            if not strict_changes:
                logger.info("Clause compare | clause_id=%s skipped=no_strict_changes", clause_id)
                return []

            logger.info("Clause compare | clause_id=%s detected=%s", clause_id, len(strict_changes))
            return strict_changes

        logger.warning("Invalid JSON for clause_id=%s attempt=%s. Retrying once.", clause_id, attempt + 1)

    logger.info("Clause compare | clause_id=%s skipped=invalid_response", clause_id)
    return []


def _parse_missed_changes_payload(raw_content: str) -> list[str] | None:
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

    if not isinstance(parsed, dict):
        return None

    missed = parsed.get("missed_changes")
    if not isinstance(missed, list):
        return []

    cleaned = []
    for value in missed:
        text = _normalize_change_summary_text(str(value or ""))
        if not text:
            continue
        cleaned.append(trim_text(text, 240))
    return cleaned


def find_missed_changes_per_clause(clause: dict, existing_changes: list[dict], stats: dict | None = None) -> list[dict]:
    """Second pass to identify additional missed factual differences for a clause pair."""
    if not isinstance(clause, dict):
        return []

    clause_id = str(clause.get("clause_id") or "unknown")
    old_content = _truncate_text_for_tokens(str(clause.get("old_content") or ""), max_tokens=350)
    new_content = _truncate_text_for_tokens(str(clause.get("new_content") or ""), max_tokens=350)
    if not old_content and not new_content:
        return []

    existing_descriptions = []
    for item in existing_changes or []:
        if not isinstance(item, dict):
            continue
        text = _normalize_change_summary_text(str(item.get("change") or "").strip())
        if text:
            existing_descriptions.append(text)

    previous_list = "\n".join(f"- {entry}" for entry in existing_descriptions) if existing_descriptions else "- None"

    prompt = (
        "Re-check the OLD and NEW clause carefully.\n\n"
        "Previously detected changes:\n"
        f"{previous_list}\n\n"
        "Now identify if ANY additional differences were missed.\n\n"
        "STRICT:\n"
        "- Do not repeat existing changes\n"
        "- Only add new differences\n"
        "- Focus on numbers, conditions, thresholds\n\n"
        "Output JSON:\n"
        "{\n"
        '  "missed_changes": ["..."]\n'
        "}\n\n"
        "OLD CLAUSE:\n"
        f"{old_content}\n\n"
        "NEW CLAUSE:\n"
        f"{new_content}"
    )

    for attempt in range(2):
        if isinstance(stats, dict):
            stats["api_calls"] = int(stats.get("api_calls") or 0) + 1
        try:
            content = call_groq_with_retry(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a strict JSON regulatory comparison assistant. Return only valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=180,
                temperature=0.0,
                retries=1,
                initial_backoff=1.0,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            logger.warning("find_missed_changes_per_clause failed clause_id=%s attempt=%s error=%s", clause_id, attempt + 1, exc)
            content = ""

        parsed = _parse_missed_changes_payload(content)
        if parsed is None:
            continue

        existing_norm = {_normalize_change_text(entry) for entry in existing_descriptions}
        additional = []
        for item in parsed:
            normalized_item = _normalize_change_text(item)
            if not normalized_item or normalized_item in existing_norm:
                continue
            if not _is_high_quality_change_description(item):
                continue
            additional.append({"change": item, "type": "modified"})

        if additional:
            logger.info("Clause recheck | clause_id=%s additional_found=%s", clause_id, len(additional))
        else:
            logger.info("Clause recheck | clause_id=%s additional_found=0", clause_id)
        return additional

    logger.info("Clause recheck | clause_id=%s skipped=invalid_response", clause_id)
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
            merged_items.append(
                {
                    "change": change,
                    "type": change_type,
                    "field": str(item.get("field") or "").strip(),
                    "old": str(item.get("old") or "").strip(),
                    "new": str(item.get("new") or "").strip(),
                }
            )

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
        unique_changes.append(
            {
                "change": re.sub(r"\s+", " ", str(item.get("change") or "").strip()),
                "type": normalized_type,
                "field": str(item.get("field") or "").strip(),
                "old": str(item.get("old") or "").strip(),
                "new": str(item.get("new") or "").strip(),
            }
        )

    logger.info("MAP merge/dedup: before_count=%s after_dedup=%s", before_count, len(unique_changes))
    return unique_changes


def _normalize_change_summary_text(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text


def _normalize_field_label(value: str) -> str:
    text = _normalize_change_summary_text(value)
    lowered = text.lower()

    for alias_pattern, canonical in FIELD_ALIAS_NORMALIZATION:
        if re.search(alias_pattern, lowered, re.IGNORECASE):
            return canonical

    for canonical, patterns in FIELD_NORMALIZATION_RULES:
        if all(re.search(pattern, lowered, re.IGNORECASE) for pattern in patterns):
            return canonical
    return text[:140]


def _clean_detected_changes(changes: list[dict], max_items: int = 10) -> list[dict]:
    """Return only strict high-quality changes in {type, field, old, new} shape."""
    normalized_items = []
    for item in changes or []:
        if not isinstance(item, dict):
            continue

        candidate = {
            "type": str(item.get("type") or "modified").strip().lower(),
            "field": _normalize_change_summary_text(str(item.get("field") or "").strip()),
            "old": _normalize_change_summary_text(str(item.get("old") or "").strip()),
            "new": _normalize_change_summary_text(str(item.get("new") or "").strip()),
            "source": str(item.get("source") or "NEW").strip().upper(),
        }
        if not is_valid(candidate):
            continue

        normalized_items.append(
            {
                "type": candidate["type"],
                "field": trim_text(candidate["field"], 140),
                "old": trim_text(candidate["old"], 220),
                "new": trim_text(candidate["new"], 220),
                "source": candidate["source"] if candidate["source"] in {"NEW", "OLD", "POLICY"} else "NEW",
            }
        )

    before_count = len(normalized_items)
    deduped_exact = []
    seen_exact = set()
    for item in normalized_items:
        exact_key = (
            str(item.get("type") or ""),
            _normalize_change_text(item.get("field") or ""),
            _normalize_change_text(item.get("old") or ""),
            _normalize_change_text(item.get("new") or ""),
        )
        if exact_key in seen_exact:
            continue
        seen_exact.add(exact_key)
        deduped_exact.append(item)

    capped = deduped_exact[: min(10, max_items)]
    logger.info(
        "Change cleaning summary | before=%s after_exact=%s final=%s",
        before_count,
        len(deduped_exact),
        len(capped),
    )
    return capped


def _normalize_reduce_changes(items: list[dict]) -> list[dict]:
    normalized = []
    for item in items or []:
        if not isinstance(item, dict):
            continue

        summary = str(item.get("summary") or item.get("change") or item.get("field") or "").strip()
        if not summary:
            old_text = str(item.get("old") or item.get("old_text") or "").strip()
            new_text = str(item.get("new") or item.get("new_text") or "").strip()
            if old_text or new_text:
                summary = trim_text(f"{old_text} -> {new_text}".strip(" ->"), 220)
        if not summary:
            continue

        change_type = str(item.get("type") or "modified").strip().lower()
        if change_type not in {"added", "modified", "removed", "threshold_change"}:
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


def detect_changes(old_blocks: Any, new_blocks: Any, policy_blocks: Any = None) -> dict:
    """Detect compliance changes using RBI (new) vs Policy (current state) semantics."""
    try:
        def _normalize_blocks(value: Any, prefix: str) -> list[dict]:
            if isinstance(value, list):
                normalized = []
                for index, item in enumerate(value, start=1):
                    if not isinstance(item, dict):
                        continue
                    content = str(item.get("content") or item.get("text") or "").strip()
                    if not content:
                        continue
                    normalized.append(
                        {
                            "block_id": str(item.get("block_id") or item.get("chunk_id") or f"{prefix}-{index}"),
                            "heading": str(item.get("heading") or item.get("title") or "").strip(),
                            "content": content,
                        }
                    )
                return normalized

            source_text = str(value or "").strip()
            if not source_text:
                return []

            blocks = extract_semantic_blocks(source_text)
            if not blocks:
                blocks = _simple_paragraph_blocks(source_text, prefix=f"{prefix}-fallback")
            return [
                {
                    "block_id": str(block.get("block_id") or f"{prefix}-{index}"),
                    "heading": str(block.get("heading") or block.get("title") or "").strip(),
                    "content": str(block.get("content") or "").strip(),
                }
                for index, block in enumerate(blocks, start=1)
                if isinstance(block, dict) and str(block.get("content") or "").strip()
            ]

        rbi_items = _normalize_blocks(new_blocks, prefix="rbi")
        policy_items = _normalize_blocks(policy_blocks, prefix="policy") if policy_blocks is not None else _normalize_blocks(old_blocks, prefix="policy")

        print("Using semantic blocks:", len(rbi_items) + len(policy_items))

        if not rbi_items or not policy_items:
            return _default_changes_response()

        matches = match_blocks(policy_items, rbi_items)
        matched_blocks = to_matched_blocks_payload(matches)

        matched_count = len([item for item in matched_blocks if str(item.get("match_type") or "") == "matched"])
        added_count = len([item for item in matched_blocks if str(item.get("match_type") or "") == "added"])
        removed_count = len([item for item in matched_blocks if str(item.get("match_type") or "") == "removed"])

        print("\n🔍 Matching:")
        print(f"Matched: {matched_count} | Added: {added_count} | Removed: {removed_count}")

        compare_pairs = [
            {
                "pair_id": str(pair.get("pair_id") or "").strip(),
                "old": str(pair.get("old") or "").strip(),
                "new": str(pair.get("new") or "").strip(),
                "old_heading": str(pair.get("old_heading") or "").strip(),
                "new_heading": str(pair.get("new_heading") or "").strip(),
                "match_score": float(pair.get("match_score") or 0.0),
            }
            for pair in matched_blocks
            if isinstance(pair, dict)
            and (str(pair.get("old") or "").strip() or str(pair.get("new") or "").strip())
        ]

        MAX_BLOCKS_PER_CALL = 5
        MAX_TOTAL_COMPARE_BLOCKS = 20
        if len(compare_pairs) > MAX_TOTAL_COMPARE_BLOCKS:
            compare_pairs = sorted(
                compare_pairs,
                key=lambda item: float(item.get("match_score") or 0.0),
                reverse=True,
            )[:MAX_TOTAL_COMPARE_BLOCKS]

        batches = [
            compare_pairs[index:index + MAX_BLOCKS_PER_CALL]
            for index in range(0, len(compare_pairs), MAX_BLOCKS_PER_CALL)
        ]

        raw_changes = []
        print("\n🧠 LLM:")
        for batch_index, batch in enumerate(batches, start=1):
            print(f"Batch {batch_index} -> {len(batch)} blocks")
            if batch:
                sample_old = trim_text(str(batch[0].get("old") or "").replace("\n", " "), 140)
                sample_new = trim_text(str(batch[0].get("new") or "").replace("\n", " "), 140)
                print(f"Sample OLD: {sample_old}")
                print(f"Sample NEW: {sample_new}")
            batch_result = compare_blocks_batch(batch, debug=False)
            if isinstance(batch_result, list):
                raw_changes.extend([item for item in batch_result if isinstance(item, dict)])

        # Normalize to strict output format.
        mapped_changes = []
        banned_terms = {"general update", "no summary provided", "may affect", "needs review"}
        for item in raw_changes:
            change_type = str(item.get("type") or "").strip().lower()
            if change_type not in {"missing_requirement", "modified_requirement", "extra_policy_rule"}:
                continue

            field = trim_text(str(item.get("field") or item.get("statement") or "").strip(), 140)
            field = _normalize_field_label(field)
            old_value = str(item.get("old") if item.get("old") is not None else item.get("old_text") or "").strip()
            new_value = str(item.get("new") if item.get("new") is not None else item.get("new_text") or "").strip()
            evidence = trim_text(str(item.get("evidence") or item.get("statement") or "").strip(), 220)

            merged = f"{field} {old_value} {new_value} {evidence}".lower()
            if any(term in merged for term in banned_terms):
                continue
            if len(field.split()) < 2 or len(evidence.split()) < 4:
                continue

            mapped_changes.append(
                {
                    "type": change_type,
                    "field": field,
                    "old": old_value or None,
                    "new": new_value or None,
                    "evidence": evidence,
                    "source": "RBI" if change_type != "extra_policy_rule" else "POLICY",
                }
            )

        # Deduplicate and cap to meaningful range.
        deduped = []
        seen = set()
        for item in mapped_changes:
            key = (
                _normalize_change_text(str(item.get("field") or "")),
                _normalize_change_text(str(item.get("new") or "")),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)

        if len(deduped) < 5:
            for pair in compare_pairs:
                old_text = str(pair.get("old") or "").strip()
                new_text = str(pair.get("new") or "").strip()
                field = str(pair.get("new_heading") or pair.get("old_heading") or "Regulatory requirement").strip()
                field = _normalize_field_label(field)
                if not new_text:
                    continue
                inferred_type = "modified_requirement" if old_text else "missing_requirement"
                candidate = {
                    "type": inferred_type,
                    "field": trim_text(field, 140),
                    "old": trim_text(old_text, 220) if old_text else None,
                    "new": trim_text(new_text, 220),
                    "evidence": trim_text(new_text, 220),
                    "source": "RBI",
                }
                key = (
                    _normalize_change_text(str(candidate.get("field") or "")),
                    _normalize_change_text(str(candidate.get("new") or "")),
                )
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(candidate)
                if len(deduped) >= 5:
                    break

        cleaned_changes = deduped[:15]

        print("\n✅ FINAL:")
        print(f"Changes: {len(cleaned_changes)}")

        return _schema_response(changes=cleaned_changes)

    except Exception as e:
        logger.error("detect_changes failed: %s", e)
        return _default_changes_response()


def detect_compliance_gaps(new_text: str, policy_text: str, changes: list[dict] | None = None) -> dict:
    """Detect compliance gaps using token-aware batched analysis."""
    try:
        if isinstance(changes, list) and changes:
            gaps = []
            for item in changes:
                if not isinstance(item, dict):
                    continue
                field = str(item.get("field") or "Regulatory requirement").strip()
                evidence = str(item.get("evidence") or "").strip()
                change_type = str(item.get("type") or "").strip().lower()
                old_value = str(item.get("old") or "").strip()
                new_value = str(item.get("new") or "").strip()

                severity = "Low"
                lowered = f"{field} {evidence} {new_value}".lower()
                if any(token in lowered for token in ["%", "threshold", "limit", "ce t1", "cet1", "day", "days", "report", "timeline", "penalty"]):
                    severity = "High"
                elif any(token in lowered for token in ["monitor", "procedure", "process", "control"]):
                    severity = "Medium"

                if change_type == "missing_requirement":
                    gap_text = f"Missing RBI requirement: {field}"
                    reason = f"Policy does not implement RBI rule for {field}; this can create direct non-compliance risk."
                elif change_type == "modified_requirement":
                    gap_text = f"Policy rule differs from RBI for {field}"
                    reason = f"Policy value '{old_value or 'N/A'}' conflicts with RBI value '{new_value or 'N/A'}'."
                elif change_type == "extra_policy_rule":
                    gap_text = f"Policy has extra rule not mapped to RBI: {field}"
                    reason = "Policy contains a requirement not aligned to RBI source text and needs rationalization."
                else:
                    continue

                gaps.append(
                    {
                        "gap": trim_text(gap_text, 220),
                        "severity": severity,
                        "reason": trim_text(reason, 240),
                        "issue": trim_text(gap_text, 220),
                        "risk": severity,
                        "regulation_requirement": trim_text(f"{field}: {new_value or evidence}", 220),
                        "policy_current_state": trim_text(old_value or "Not implemented in policy", 220),
                    }
                )

            deduped = deduplicate_items(gaps)[:15]
            print(f"Compliance gaps generated: {len(deduped)}")
            return _schema_response(compliance_gaps=deduped)

        if not new_text or not policy_text:
            return _default_gaps_response()

        new_text = _truncate_text_for_tokens(trim_text(new_text, 5500))
        policy_text = _truncate_text_for_tokens(trim_text(policy_text, 5500))

        new_text = _filter_text_for_llm(new_text, label="gaps_regulation")
        policy_text = _filter_text_for_llm(policy_text, label="gaps_policy")

        # Analyze extracted clause structure for both documents before pair preparation.
        regulation_clauses = _extract_filtered_clauses_for_map(new_text, label="gaps_regulation", clause_prefix="reg")
        policy_clauses = _extract_filtered_clauses_for_map(policy_text, label="gaps_policy", clause_prefix="pol")
        _log_clause_structure("regulation", regulation_clauses)
        _log_clause_structure("policy", policy_clauses)

        # If changes are provided, evaluate each change against relevant policy clauses.
        if isinstance(changes, list) and changes:
            policy_eval_stats = {"policy_eval_calls": 0}
            evaluated_changes = []

            for change_index, change_item in enumerate(changes, start=1):
                if not isinstance(change_item, dict):
                    continue

                change_description = _extract_change_description(change_item)
                if not change_description:
                    continue

                relevant_policy = _select_relevant_policy_clauses(change_description, policy_clauses, limit=3)
                assessment = _assess_change_against_policy(change_description, relevant_policy, stats=policy_eval_stats)

                logger.info(
                    "Policy coverage check | change_index=%s status=%s risk=%s",
                    change_index,
                    assessment.get("status"),
                    assessment.get("risk"),
                )

                evaluated_changes.append(
                    {
                        **change_item,
                        "policy_check": assessment,
                        "relevant_policy_clauses": [
                            {
                                "clause_id": str(item.get("clause_id") or "").strip(),
                                "title": trim_text(str(item.get("title") or "").strip(), 120),
                            }
                            for item in relevant_policy
                            if isinstance(item, dict)
                        ],
                    }
                )

            compliance_gaps = []
            for item in evaluated_changes:
                policy_check = item.get("policy_check") if isinstance(item.get("policy_check"), dict) else {}
                status = _normalize_coverage_status(policy_check.get("status"))
                risk = _normalize_risk_level(policy_check.get("risk"))
                explanation = str(policy_check.get("explanation") or "").strip()
                change_description = _extract_change_description(item)

                if status == "covered":
                    continue

                compliance_gaps.append(
                    {
                        "issue": trim_text(change_description, 220),
                        "risk": risk.title(),
                        "regulation_requirement": trim_text(change_description, 220),
                        "policy_current_state": explanation or "Policy coverage is incomplete for this change.",
                        "status": status,
                        "policy_check": policy_check,
                        "relevant_policy_clauses": item.get("relevant_policy_clauses") or [],
                    }
                )

            compliance_gaps = sorted(compliance_gaps, key=lambda g: _priority_value((g or {}).get("risk", "Low")), reverse=True)
            deduped = deduplicate_items(compliance_gaps[:6])
            logger.info(
                "Policy coverage summary | input_changes=%s evaluated=%s gaps=%s llm_calls=%s",
                len(changes),
                len(evaluated_changes),
                len(deduped),
                int(policy_eval_stats.get("policy_eval_calls") or 0),
            )
            return _schema_response(compliance_gaps=deduped)

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
            raise ValueError("impact_input is required for impact generation")

        changes = impact_input.get("changes", [])
        gaps = impact_input.get("compliance_gaps", [])

        if not changes and not gaps:
            raise ValueError("No input changes/gaps available for impact generation")

        combined_text = ""
        if changes:
            combined_text += "OLD POLICY / CHANGE BASELINE:\n" + json.dumps(changes[:3], indent=2) + "\n\n"
        if gaps:
            combined_text += "REGULATION DELTAS / COMPLIANCE GAPS:\n" + json.dumps(gaps[:3], indent=2)

        gap_evidence = []
        for gap in gaps[:6]:
            if not isinstance(gap, dict):
                continue
            gap_evidence.append(
                {
                    "title": str(gap.get("title") or gap.get("issue") or gap.get("gap") or "").strip(),
                    "description": str(gap.get("description") or gap.get("reason") or "").strip(),
                    "recommendation": str(gap.get("recommendation") or "").strip(),
                    "severity": str(gap.get("severity") or gap.get("risk") or gap.get("risk_level") or "Medium").strip(),
                }
            )

        required_impacts = max(1, len(gap_evidence) or len([item for item in changes if isinstance(item, dict)]) or 1)

        combined_text = _filter_text_for_llm(combined_text, label="impacts")

        prompt = f"""
Analyze business and compliance impacts from detected changes and gaps.
Return only concrete, non-vague impacts.
For EVERY compliance_gap, you MUST generate at least 1 impact.
If no direct impact is found, infer logical business impact.
Do not return an empty impacts array.

Analyze these documents:

OLD POLICY:
{_truncate_text_for_tokens(json.dumps(changes[:3], indent=2) if changes else "")}

COMPLIANCE GAPS:
{_truncate_text_for_tokens(json.dumps(gap_evidence, indent=2) if gap_evidence else "")}

MAPPING RULES:
- Capital requirement -> Finance impact (HIGH)
- KYC -> Compliance + Operations impact (MEDIUM/HIGH)
- AML -> Risk + Compliance impact (HIGH)

IMPACT STRUCTURE:
Each impact must include:
- department
- severity
- description

TARGET COUNT:
Generate at least {required_impacts} impacts.

REGULATION:
{_truncate_text_for_tokens(combined_text)}

Return ONLY valid JSON. No explanation. No markdown. No text outside JSON.\n\nJSON schema:
{{
  "impacts": [
    {{
            "department": "Finance | Compliance | Risk | Operations | Legal | Audit",
            "severity": "HIGH | MEDIUM | LOW",
            "description": "Specific business consequence"
    }}
  ]
}}
"""
        prompt = _ensure_prompt_token_safe(prompt)
        print("LLM CALLED")
        result = _safe_call(prompt=prompt, max_tokens=BATCH_OUTPUT_TOKENS, retries=2, initial_backoff=4)
        print("LLM RESPONSE:", result)

        if isinstance(result, dict) and "error" not in result and isinstance(result.get("impacts"), list):
            deduped_impacts = deduplicate_items(_normalize_impacts_list(result.get("impacts", [])[:30]))
            if not deduped_impacts:
                deduped_impacts = _infer_impacts_from_inputs(changes, gaps)
            logger.info("deduplicated_output=%s", json.dumps({"impacts": deduped_impacts}, ensure_ascii=True)[:1200])
            return _schema_response(impacts=deduped_impacts)

        inferred_impacts = _infer_impacts_from_inputs(changes, gaps)
        if inferred_impacts:
            logger.info("inferred_impacts=%s", json.dumps({"impacts": inferred_impacts}, ensure_ascii=True)[:1200])
            return _schema_response(impacts=inferred_impacts)

        raise RuntimeError("Impact LLM response invalid or empty")

    except Exception as e:
        logger.error("analyze_impact failed: %s", e)
        raise


def generate_actions(actions_input: dict) -> dict:
    """Generate actionable remediation steps from compliance gaps and impacts."""
    try:
        if not actions_input or not isinstance(actions_input, dict):
            raise ValueError("actions_input is required for action generation")

        changes = actions_input.get("changes", [])
        gaps = actions_input.get("compliance_gaps", [])
        impacts = actions_input.get("impacts", [])

        if not gaps and not impacts:
            raise ValueError("No compliance gaps/impacts available for action generation")

        gap_evidence = []
        for gap in gaps[:6]:
            if not isinstance(gap, dict):
                continue
            gap_evidence.append(
                {
                    "title": str(gap.get("title") or gap.get("issue") or gap.get("gap") or "").strip(),
                    "severity": _normalize_severity(gap.get("severity") or gap.get("risk") or gap.get("risk_level")),
                    "description": str(gap.get("description") or gap.get("reason") or "").strip(),
                    "recommendation": str(gap.get("recommendation") or "").strip(),
                }
            )

        impact_evidence = []
        for impact in impacts[:6]:
            if not isinstance(impact, dict):
                continue
            impact_evidence.append(
                {
                    "title": str(impact.get("title") or impact.get("area") or "").strip(),
                    "severity": _normalize_severity(impact.get("severity") or impact.get("impact_level")),
                    "description": str(impact.get("description") or impact.get("summary") or impact.get("reason") or "").strip(),
                    "departments": impact.get("impacted_departments") if isinstance(impact.get("impacted_departments"), list) else [],
                }
            )

        required_actions = max(1, min(6, len(gap_evidence) or len(impact_evidence) or 1))

        combined_text = ""
        if changes:
            combined_text += "OLD POLICY:\n" + json.dumps(changes[:2], indent=2) + "\n\n"
        if gaps:
            combined_text += "COMPLIANCE GAPS:\n" + json.dumps(gap_evidence, indent=2) + "\n\n"
        if impacts:
            combined_text += "IMPACTS:\n" + json.dumps(impact_evidence, indent=2)

        combined_text = _filter_text_for_llm(combined_text, label="actions")

        prompt = f"""
Generate exactly {required_actions} concrete and implementable compliance actions.
If compliance gaps are present, return one action per gap, capped at 6.
Do not return an empty actions array.
Each action must map to a specific gap title, recommendation, or impact from the evidence.
No placeholders. No vague wording. No generic policy advice.

Analyze these documents:

OLD POLICY:
{_truncate_text_for_tokens(json.dumps(changes[:2], indent=2) if changes else "")}

COMPLIANCE GAPS:
{_truncate_text_for_tokens(json.dumps(gap_evidence, indent=2) if gap_evidence else "")}

IMPACTS:
{_truncate_text_for_tokens(json.dumps(impact_evidence, indent=2) if impact_evidence else "")}

EVIDENCE SUMMARY:
{_truncate_text_for_tokens(combined_text)}

Return ONLY valid JSON. No explanation. No markdown. No text outside JSON.\n\nJSON schema:
{{
  "actions": [
    {{
            "title": "Action title",
            "description": "Execution detail",
            "department": "Owner department",
      "priority": "High | Medium | Low",
            "status": "Pending",
            "deadline": "Current compliance cycle"
    }}
  ]
}}
"""
        prompt = _ensure_prompt_token_safe(prompt)
        print("LLM CALLED")
        result = _safe_call(prompt=prompt, max_tokens=BATCH_OUTPUT_TOKENS, retries=2, initial_backoff=4)
        print("LLM RESPONSE:", result)

        if isinstance(result, dict) and "error" not in result and isinstance(result.get("actions"), list):
            deduped_actions = deduplicate_items(result.get("actions", [])[:6])
            if not deduped_actions:
                raise RuntimeError("Action LLM returned empty actions")
            logger.info("deduplicated_output=%s", json.dumps({"actions": deduped_actions}, ensure_ascii=True)[:1200])
            return _schema_response(actions=deduped_actions)

        raise RuntimeError("Action LLM response invalid or empty")

    except Exception as e:
        logger.error("generate_actions failed: %s", e)
        raise





# ============================================================================
# NEW SYSTEM: Semantic Block-Based Change Detection
# ============================================================================

def detect_regulatory_changes_new(old_text: str, new_text: str) -> dict:
    """
    NEW UNIFIED PIPELINE: Semantic blocks + smart matching + strict diffing
    
    Phases:
    1. Extract semantic blocks from both documents (200-800 token groups)
    2. Match blocks using semantic similarity (no random pairing)
    3. Compare matched blocks with strict factual LLM prompt
    4. Hard validation: reject vague/duplicate/short changes
    5. Dedup and clean output
    6. Return precise final changes
    
    Returns:
    {
        "status": "success|error",
        "changes": [
            {
                "type": "added|removed|modified",
                "statement": "exact factual change",
                "old_text": "original text",
                "new_text": "new text"
            }
        ],
        "stats": {
            "old_blocks": int,
            "new_blocks": int,
            "matched_pairs": int,
            "changes_detected": int,
            "changes_validated": int,
            "changes_final": int
        }
    }
    """
    
    try:
        print("\n" + "=" * 70)
        print("ðŸš€ REGULATORY CHANGE DETECTION - NEW SEMANTIC SYSTEM")
        print("=" * 70)
        
        # Validate inputs
        if not old_text or not isinstance(old_text, str):
            logger.warning("detect_regulatory_changes_new: empty old_text")
            return {
                "status": "error",
                "error": "old_text is empty or invalid",
                "changes": [],
                "stats": {}
            }
        
        if not new_text or not isinstance(new_text, str):
            logger.warning("detect_regulatory_changes_new: empty new_text")
            return {
                "status": "error",
                "error": "new_text is empty or invalid",
                "changes": [],
                "stats": {}
            }
        
        # PHASE 1-2: Extract semantic blocks
        print("\nðŸ“¦ PHASE 1-2: Extracting semantic blocks...")
        old_blocks = extract_semantic_blocks(old_text)
        new_blocks = extract_semantic_blocks(new_text)
        
        if not old_blocks and not new_blocks:
            logger.warning("detect_regulatory_changes_new: no blocks extracted from either document")
            return {
                "status": "error",
                "error": "Failed to extract semantic blocks from documents",
                "changes": [],
                "stats": {
                    "old_blocks": 0,
                    "new_blocks": 0,
                }
            }
        
        # PHASE 3: Match blocks
        print("\nðŸ”— PHASE 3: Matching semantic blocks...")
        matches = match_blocks(old_blocks, new_blocks)
        
        # PHASE 4: Compare matched pairs
        print("\nâš–ï¸  PHASE 4: Comparing matched blocks (strict diff)...")
        all_changes, comparison_stats = compare_all_matched_blocks(matches, debug=False)
        
        # PHASE 5: Hard validation
        print("\nâœ… PHASE 5: Hard validation layer...")
        validated_changes, validation_stats = hard_validate_changes(all_changes)
        
        # PHASE 6: Deduplication
        print("\nðŸ”„ PHASE 6: Dedupling changes...")
        deduped_changes, dedup_stats = deduplicate_changes(validated_changes)
        
        # PHASE 7: Limit and clean output
        print("\nðŸ“‹ PHASE 7: Final output formatting...")
        final_changes = limit_output_changes(deduped_changes, max_count=15)
        
        # PHASE 8: Render output
        print("\n" + "=" * 70)
        output_text = render_final_output(final_changes)
        print(output_text)
        print("=" * 70 + "\n")
        
        # Compile statistics
        stats = {
            "old_blocks": len(old_blocks),
            "new_blocks": len(new_blocks),
            "matched_pairs": len([m for m in matches if m["match_type"] == "matched"]),
            "added_blocks": len([m for m in matches if m["match_type"] == "added"]),
            "removed_blocks": len([m for m in matches if m["match_type"] == "removed"]),
            "changes_initial": len(all_changes),
            "changes_after_validation": validation_stats["valid_count"],
            "changes_after_dedup": dedup_stats["output_count"],
            "changes_final": len(final_changes),
        }
        
        logger.info(
            "detect_regulatory_changes_new completed: old_blocks=%s new_blocks=%s changes=%s",
            stats["old_blocks"],
            stats["new_blocks"],
            stats["changes_final"]
        )
        
        return {
            "status": "success",
            "changes": final_changes,
            "stats": stats,
        }
    
    except Exception as e:
        logger.error("detect_regulatory_changes_new failed: %s", e, exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "changes": [],
            "stats": {}
        }
