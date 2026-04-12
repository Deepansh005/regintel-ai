import json
import logging
import re
from typing import Any

from app.services.llm_router import call_groq_with_retry

logger = logging.getLogger(__name__)

DEPARTMENTS = [
    "Finance",
    "Compliance",
    "Risk",
    "Legal",
    "Operations",
    "Audit",
]

_ALLOWED_LEVELS = {"Low", "Medium", "High"}
_VAGUE_REASON_TERMS = {
    "may affect",
    "might affect",
    "could affect",
    "potentially",
    "possibly",
    "as needed",
}


def _extract_change_text(change: Any) -> str:
    if isinstance(change, str):
        return change.strip()
    if not isinstance(change, dict):
        return ""

    for key in ("statement", "summary", "change", "field"):
        value = str(change.get(key) or "").strip()
        if value:
            return value

    old_text = str(change.get("old") or change.get("old_text") or "").strip()
    new_text = str(change.get("new") or change.get("new_text") or "").strip()
    if old_text or new_text:
        return f"{old_text} -> {new_text}".strip()

    return ""


def _parse_impact_payload(raw_content: str) -> list[dict]:
    if not raw_content or not isinstance(raw_content, str):
        return []

    parsed = None
    candidate = str(raw_content or "").strip()
    try:
        parsed = json.loads(candidate)
    except Exception:
        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", candidate, re.IGNORECASE)
        if fenced:
            try:
                parsed = json.loads(fenced.group(1).strip())
            except Exception:
                parsed = None
        else:
            parsed = None

    if not isinstance(parsed, dict):
        return []

    impacts = parsed.get("impacts")
    if not isinstance(impacts, list):
        return []

    return [item for item in impacts if isinstance(item, dict)]


def _validate_impacts(impacts: list[dict]) -> list[dict]:
    validated = []

    for item in impacts or []:
        department = str(item.get("department") or "").strip()
        impact_level = str(item.get("impact_level") or "").strip().title()
        reason = str(item.get("reason") or "").strip()

        # Reject if department is not in the predefined list.
        if department not in DEPARTMENTS:
            continue

        if impact_level not in _ALLOWED_LEVELS:
            continue

        # Reject if reason is too vague/short.
        if len(reason) < 10:
            continue
        if any(term in reason.lower() for term in _VAGUE_REASON_TERMS):
            continue

        validated.append(
            {
                "department": department,
                "impact_level": impact_level,
                "reason": reason,
            }
        )

    return validated


def _build_prompt(change_text: str) -> str:
    return (
        "You are a regulatory impact analysis engine.\n\n"
        "Given a regulatory change, identify:\n"
        "1. Impacted departments\n"
        "2. Impact level (Low, Medium, High)\n"
        "3. Reason\n\n"
        "STRICT RULES:\n"
        "- Be specific\n"
        "- No generic answers\n"
        "- Map logically\n"
        f"- Use ONLY these departments: {', '.join(DEPARTMENTS)}\n\n"
        "Output JSON:\n"
        "{\n"
        '  "impacts": [\n'
        "    {\n"
        '      "department": "...",\n'
        '      "impact_level": "Low/Medium/High",\n'
        '      "reason": "..."\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Regulatory change:\n"
        f"{change_text}"
    )


def generate_impacts(changes: list[Any]) -> list[dict]:
    """
    Generate per-change impact analysis.

    Output structure:
    [
      {
        "change": "...",
        "impacts": [
          {"department": "Compliance", "impact_level": "High", "reason": "..."}
        ]
      }
    ]

    Important: each change is analyzed independently. No merging across changes.
    """
    if not isinstance(changes, list):
        print("Impact generated for 0 changes")
        return []

    def _deterministic_impacts(change_item: dict) -> list[dict]:
        field = str(change_item.get("field") or "Regulatory requirement").strip()
        change_type = str(change_item.get("type") or "").strip().lower()
        evidence = str(change_item.get("evidence") or "").strip()
        lowered = f"{field} {evidence}".lower()

        impacts = []

        if any(token in lowered for token in ["dividend", "payout", "cet1", "pat", "%", "threshold", "limit"]):
            impacts.extend(
                [
                    {"department": "Finance", "impact_level": "High", "reason": f"Finance must enforce RBI value changes for {field}."},
                    {"department": "Risk", "impact_level": "High", "reason": f"Risk controls must be recalibrated to the updated {field} rule."},
                    {"department": "Compliance", "impact_level": "High", "reason": f"Compliance monitoring must verify adherence to {field}."},
                ]
            )
        elif any(token in lowered for token in ["report", "reporting", "str", "day", "timeline", "deadline"]):
            impacts.extend(
                [
                    {"department": "Compliance", "impact_level": "High", "reason": f"Compliance must enforce regulatory reporting obligations for {field}."},
                    {"department": "Operations", "impact_level": "Medium", "reason": f"Operations workflow timelines must satisfy {field}."},
                    {"department": "Legal", "impact_level": "Medium", "reason": f"Legal exposure increases if {field} reporting is missed."},
                ]
            )
        elif any(token in lowered for token in ["eligib", "condition", "restriction", "prohibit", "must not", "shall not"]):
            impacts.extend(
                [
                    {"department": "Compliance", "impact_level": "High", "reason": f"Eligibility and restriction controls must reflect {field}."},
                    {"department": "Legal", "impact_level": "Medium", "reason": f"Policy wording and legal controls must align to {field}."},
                    {"department": "Risk", "impact_level": "Medium", "reason": f"Control failures are possible if {field} remains misaligned."},
                ]
            )
        else:
            impacts.extend(
                [
                    {"department": "Compliance", "impact_level": "Medium", "reason": f"Compliance framework must be updated for {field}."},
                    {"department": "Operations", "impact_level": "Low", "reason": f"Operational SOPs require updates tied to {field}."},
                ]
            )

        if change_type == "extra_policy_rule":
            for impact in impacts:
                if impact["impact_level"] == "High":
                    impact["impact_level"] = "Medium"

        return _validate_impacts(impacts)

    output = []
    for item in changes:
        if not isinstance(item, dict):
            continue
        change_text = _extract_change_text(item)
        if not change_text:
            continue

        valid_impacts = _deterministic_impacts(item)
        output.append({"change": change_text, "impacts": valid_impacts})

    print(f"Impact generated for {len(output)} changes")
    return output
