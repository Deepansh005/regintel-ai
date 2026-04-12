import json
import logging
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
    try:
        parsed = json.loads(raw_content)
    except Exception:
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

    output = []

    for item in changes:
        change_text = _extract_change_text(item)
        if not change_text:
            continue

        prompt = _build_prompt(change_text)

        try:
            content = call_groq_with_retry(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a strict JSON impact analysis assistant. Return only valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=300,
                temperature=0.0,
                retries=1,
                initial_backoff=1.0,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            logger.warning("generate_impacts LLM call failed for change: %s", exc)
            content = ""

        parsed_impacts = _parse_impact_payload(content)
        valid_impacts = _validate_impacts(parsed_impacts)

        output.append(
            {
                "change": change_text,
                "impacts": valid_impacts,
            }
        )

    print(f"Impact generated for {len(output)} changes")
    return output
