import json
import logging
import re
from typing import Any

from app.services.llm_router import call_groq_with_retry

logger = logging.getLogger(__name__)

_ALLOWED_PRIORITIES = {"Low", "Medium", "High"}
_VAGUE_TERMS = {"improve", "enhance", "review", "optimize", "strengthen", "address"}


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

    def _deterministic_actions(change_item: dict) -> list[dict]:
        field = str(change_item.get("field") or "Regulatory requirement").strip()
        change_type = str(change_item.get("type") or "").strip().lower()
        lowered = field.lower()

        actions: list[dict] = []
        if any(token in lowered for token in ["cet1", "dividend", "payout", "pat", "threshold", "%", "limit"]):
            actions.append(
                {
                    "action": f"Implement automated rule validation in the finance decision workflow for {field} using RBI thresholds.",
                    "owner": "Finance",
                    "priority": "High",
                }
            )
            actions.append(
                {
                    "action": f"Update compliance control matrix and regression test pack for {field} in policy governance process.",
                    "owner": "Compliance",
                    "priority": "High",
                }
            )
        elif any(token in lowered for token in ["str", "report", "timeline", "day", "deadline"]):
            actions.append(
                {
                    "action": f"Configure automated deadline checks in transaction monitoring/reporting system for {field}.",
                    "owner": "Compliance",
                    "priority": "High",
                }
            )
            actions.append(
                {
                    "action": f"Deploy SLA escalation in operations workflow to enforce {field} submission timelines.",
                    "owner": "Operations",
                    "priority": "Medium",
                }
            )
        elif any(token in lowered for token in ["eligib", "condition", "restriction", "prohibit"]):
            actions.append(
                {
                    "action": f"Implement eligibility and restriction checks in risk control process aligned with {field}.",
                    "owner": "Risk",
                    "priority": "High",
                }
            )
            actions.append(
                {
                    "action": f"Revise policy clause text in compliance documentation process to align legal wording for {field}.",
                    "owner": "Compliance",
                    "priority": "Medium",
                }
            )
        else:
            actions.append(
                {
                    "action": f"Update implementation controls in policy management process for {field}.",
                    "owner": "Compliance",
                    "priority": "Medium",
                }
            )

        if change_type == "extra_policy_rule":
            actions.insert(
                0,
                {
                    "action": f"Remove or justify policy-only rule for {field} in policy governance workflow with RBI mapping evidence.",
                    "owner": "Compliance",
                    "priority": "Medium",
                },
            )

        return _validate_actions(actions)

    output = []
    for item in changes:
        if not isinstance(item, dict):
            continue
        change_text = _extract_change_text(item)
        if not change_text:
            continue

        valid_actions = _deterministic_actions(item)
        output.append({"change": change_text, "actions": valid_actions})

    print(f"Actions generated for {len(output)} changes")
    return output
