import json
import logging
from typing import Any

from app.services.llm_router import call_groq_with_retry

logger = logging.getLogger(__name__)

_ALLOWED_PRIORITIES = {"Low", "Medium", "High"}
_VAGUE_TERMS = {"improve", "enhance"}


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


def _build_prompt(change_text: str) -> str:
    return (
        "You are a compliance action engine.\n\n"
        "Given a regulatory change, generate:\n"
        "1. Action required\n"
        "2. Owner (department/team)\n"
        "3. Priority (Low/Medium/High)\n\n"
        "STRICT RULES:\n"
        "- Actions must be executable\n"
        "- No vague suggestions\n"
        "- Must be specific to change\n\n"
        "BAD:\n"
        '"Improve compliance"\n\n'
        "GOOD:\n"
        '"Update internal dividend payout policy to reflect new 75% limit"\n\n'
        "Output JSON:\n"
        "{\n"
        '  "actions": [\n'
        "    {\n"
        '      "action": "...",\n'
        '      "owner": "...",\n'
        '      "priority": "Low/Medium/High"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Regulatory change:\n"
        f"{change_text}"
    )


def _parse_actions_payload(raw_content: str) -> list[dict]:
    if not raw_content or not isinstance(raw_content, str):
        return []

    parsed = None
    try:
        parsed = json.loads(raw_content)
    except Exception:
        parsed = None

    if not isinstance(parsed, dict):
        return []

    actions = parsed.get("actions")
    if not isinstance(actions, list):
        return []

    return [item for item in actions if isinstance(item, dict)]


def _is_vague_action(action_text: str) -> bool:
    lowered = action_text.lower()
    return any(term in lowered for term in _VAGUE_TERMS)


def _validate_actions(actions: list[dict]) -> list[dict]:
    validated = []

    for item in actions or []:
        action_text = str(item.get("action") or "").strip()
        owner = str(item.get("owner") or "").strip()
        priority = str(item.get("priority") or "").strip().title()

        if len(action_text) < 10:
            continue

        if _is_vague_action(action_text):
            continue

        if priority not in _ALLOWED_PRIORITIES:
            continue

        if not owner:
            continue

        validated.append(
            {
                "action": action_text,
                "owner": owner,
                "priority": priority,
            }
        )

    return validated


def generate_actions(changes: list[Any]) -> list[dict]:
    """
    Generate concrete actions per regulatory change.

    Output:
    [
      {
        "change": "...",
        "actions": [
          {
            "action": "...",
            "owner": "...",
            "priority": "High"
          }
        ]
      }
    ]

    Each change is handled independently.
    """
    if not isinstance(changes, list):
        print("Actions generated for 0 changes")
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
                        "content": "You are a strict JSON action generation assistant. Return only valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=320,
                temperature=0.0,
                retries=1,
                initial_backoff=1.0,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            logger.warning("generate_actions LLM call failed for change: %s", exc)
            content = ""

        parsed_actions = _parse_actions_payload(content)
        valid_actions = _validate_actions(parsed_actions)

        output.append(
            {
                "change": change_text,
                "actions": valid_actions,
            }
        )

    print(f"Actions generated for {len(output)} changes")
    return output
