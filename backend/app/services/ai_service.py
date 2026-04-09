from groq import Groq
from app.core.config import GROQ_API_KEY
import json
import re
from typing import Any

client = Groq(api_key=GROQ_API_KEY)


def trim_text(text, max_len: int = 300):
    value = text if isinstance(text, str) else str(text or "")
    return value[:max_len]


def safe_llm_call(fn):
    try:
        result = fn()
        if not result:
            raise Exception("Empty response")
        return result
    except Exception as e:
        print("LLM ERROR:", e)
        return None


def default_impact(systems=None):
    return {
        "impact": {
            "departments": ["Compliance", "Risk"],
            "systems": systems if isinstance(systems, list) and systems else ["Core System"],
            "risk_level": "Medium",
            "priority": "Medium",
            "summary": "Impact generated using fallback due to size constraints",
        }
    }


def default_actions():
    return {
        "actions": [
            {
                "title": "Review regulatory gaps",
                "description": "Analyze and update policy accordingly",
                "priority": "Medium",
                "status": "Pending",
                "deadline": "1-2 weeks",
            }
        ]
    }


def _default_changes_response() -> dict:
    return {"changes": []}


def _default_gaps_response() -> dict:
    return {"gaps": []}


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


def _limit_changes(changes) -> list:
    return _extract_changes(changes)[:5]


def _limit_gaps(gaps) -> list:
    items = _extract_gaps(gaps)
    items = sorted(
        items,
        key=lambda item: _priority_value((item or {}).get("risk") or (item or {}).get("risk_level")),
        reverse=True,
    )
    return items[:8]


def _gap_texts(gaps) -> list:
    texts = []
    for gap in _limit_gaps(gaps):
        if not isinstance(gap, dict):
            continue
        issue = trim_text(gap.get("issue") or gap.get("gap") or "", 200)
        if issue:
            texts.append(issue)
    return texts[:5]


def _change_texts(changes) -> list:
    texts = []
    for change in _limit_changes(changes):
        if not isinstance(change, dict):
            continue
        summary = trim_text(change.get("summary") or change.get("section") or "", 200)
        if summary:
            texts.append(summary)
    return texts[:5]


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

    inner = payload.get("impact") if isinstance(payload.get("impact"), dict) else payload
    return {
        "impact": {
            "departments": inner.get("departments") if isinstance(inner.get("departments"), list) else base["impact"]["departments"],
            "systems": inner.get("systems") if isinstance(inner.get("systems"), list) and inner.get("systems") else base["impact"]["systems"],
            "risk_level": inner.get("risk_level") or base["impact"]["risk_level"],
            "priority": inner.get("priority") or base["impact"]["priority"],
            "summary": trim_text(inner.get("summary") or base["impact"]["summary"], 300),
        }
    }


def _parse_json_response(content):
    if not content or not isinstance(content, str):
        return None

    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def detect_changes(old_text: str, new_text: str) -> dict:
    try:
        old_text = trim_text(old_text, 2200)
        new_text = trim_text(new_text, 2200)

        prompt = f"""
You are a senior regulatory analyst specializing in financial regulations (RBI, SEBI, Basel, etc.).

TASK: Identify ONLY material regulatory changes between OLD and NEW context.

CRITICAL RULES:
1. Use ONLY information explicitly present in provided context
2. Do NOT invent or assume missing details
3. Focus on HIGH-IMPORTANCE changes only (ignore minor wording variations)
4. Remove exact duplicates before output
5. Each change must be ≤2 lines, specific and actionable
6. If NO material changes found, return empty array

MATERIAL CHANGE TYPES:
- New regulatory requirements added
- Existing requirements removed or relaxed
- Thresholds, deadlines, or criteria changed
- New penalties, fines, or consequences introduced
- Scope or applicability widened/narrowed

IGNORE:
- Rewordings without substance change
- Clarifications that don't change meaning
- Administrative format changes

Return ONLY valid JSON with NO additional text:
{{
  "changes": [
    {{
      "type": "added | removed | modified",
      "category": "KYC | Risk | Capital | Reporting | Governance | Audit | Other",
      "summary": "Specific change in ≤2 lines. E.g., 'KYC refresh required every 2 years (was 3) for retail customers'",
      "impact": "Brief note of significance"
    }}
  ]
}}

If context insufficient for reliable analysis, return empty changes array.

OLD REGULATORY CONTEXT:
{old_text}

NEW REGULATORY CONTEXT:
{new_text}
"""

        response = safe_llm_call(lambda: client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a regulatory analysis AI. You MUST return ONLY valid JSON with zero extra text, explanation, or markdown. No preamble, no postscript."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=2500,
        ))

        if response is None:
            return _default_changes_response()

        parsed = _parse_json_response(response.choices[0].message.content)
        changes = parsed.get("changes") if isinstance(parsed, dict) else None
        if not isinstance(changes, list):
            return _default_changes_response()

        return {"changes": changes[:5] if changes else []}

    except Exception as e:
        print("detect_changes failed:", e)
        return _default_changes_response()


def detect_compliance_gaps(new_text: str, policy_text: str) -> dict:
    try:
        new_text = trim_text(new_text, 2200)
        policy_text = trim_text(policy_text, 2200)

        prompt = f"""
You are a compliance auditor conducting a regulatory gap assessment.

TASK: Identify gaps where INTERNAL POLICY fails to meet REGULATORY REQUIREMENTS.

CRITICAL RULES:
1. Use ONLY information from provided REGULATION and POLICY texts
2. Do NOT invent compliance requirements not explicitly stated in regulation
3. Focus ONLY on high-impact gaps (significant compliance exposure)
4. Ignore minor administrative differences or formatting variations
5. Deduplicate: if 2 gaps describe same issue, report once
6. Each gap ≤2 lines, specific and backed by regulation+policy references
7. Max 6 gaps; ordered by severity (High → Medium → Low)
8. If NO significant gaps found, return empty array

GAP CRITERIA (must meet ALL):
- Regulation explicitly requires X
- Policy is silent on X, or contradicts X
- Non-compliance creates material risk

IGNORE:
- Gaps requiring information not in provided context
- Ambiguities that could be interpreted either way
- Assumptions about unstated policy details

Return ONLY valid JSON with NO additional text:
{{
  "gaps": [
    {{
      "issue": "Specific gap description in ≤2 lines. E.g., 'No documented procedure for periodic KYC refresh (Reg requires every 2 years; policy is silent)'",
      "risk": "High | Medium | Low",
      "regulation_requirement": "What regulation requires",
      "policy_current_state": "What policy currently says or doesnt say"
    }}
  ]
}}

If analysis cannot be done due to insufficient context, return empty gaps array.

REGULATION TEXT:
{new_text}

INTERNAL POLICY TEXT:
{policy_text}
"""

        response = safe_llm_call(lambda: client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a compliance auditing AI. Return ONLY valid JSON with zero extra text. No explanations, no markdown, no preamble. JSON ONLY."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=2500,
        ))

        if response is None:
            return _default_gaps_response()

        parsed = _parse_json_response(response.choices[0].message.content)
        gaps = parsed.get("gaps") if isinstance(parsed, dict) else None
        if not isinstance(gaps, list):
            return _default_gaps_response()

        # Deduplicate gaps with similar issues
        unique_gaps = []
        seen_issues = set()
        for gap in gaps[:8]:
            issue_key = (gap.get("issue") or "").lower().strip()[:50] if isinstance(gap, dict) else ""
            if issue_key and issue_key not in seen_issues:
                unique_gaps.append(gap)
                seen_issues.add(issue_key)
        
        return {"gaps": unique_gaps[:6] if unique_gaps else []}

    except Exception as e:
        print("detect_compliance_gaps failed:", e)
        return _default_gaps_response()


def analyze_impact(impact_input) -> dict:
    try:
        if isinstance(impact_input, dict):
            gap_texts = [trim_text(text, 200) for text in (impact_input.get("gaps") or []) if text]
            systems = [trim_text(system, 120) for system in (impact_input.get("systems") or []) if system]
        else:
            gap_texts = []
            systems = []

        gap_texts = gap_texts[:4]
        systems = systems[:3]

        if not gap_texts:
            return default_impact(systems=systems)

        prompt = f"""
You are a Compliance & Risk Officer at a financial institution.

TASK: Assess business and regulatory impact of provided compliance gaps.

CRITICAL RULES:
1. Base analysis ONLY on provided gaps (do NOT add external knowledge)
2. Assess impact across: regulatory risk, operational impact, financial/reputation exposure
3. Focus on MATERIAL impacts only (ignore minor/obvious ones)
4. Be precise: "What could actually happen?" not "Might possibly..."
5. Each impact assessment ≤2 lines, concrete and actionable
6. Maximum 4 impacts; order by severity
7. Risk_level: High (regulatory action imminent), Medium (material exposure), Low (minor exposure)
8. If insufficient data for impact assessment, return safe defaults

IMPACT FRAMEWORK:
- REGULATORY IMPACT: Penalties, enforcement, license suspension risk
- OPERATIONAL IMPACT: Process disruption, system changes required
- FINANCIAL/REPUTATIONAL: Fines, loss of customers, brand damage

Return ONLY valid JSON with NO additional text or markdown:
{{
  "impact": {{
    "departments": ["Compliance", "Risk", "Operations", "Finance"],
    "systems": {json.dumps(systems) if systems else '["Core"]'},
    "risk_level": "High | Medium | Low",
    "priority": "High | Medium | Low",
    "summary": "Concrete impact assessment in ≤3 lines. E.g., 'Missing KYC refresh: RBI penalties 0.5-2M, customer onboarding halt, reputational damage in retail segment'"
  }}
}}

COMPLIANCE GAPS TO ANALYZE:
{json.dumps({"gaps": gap_texts, "systems": systems}, ensure_ascii=True)}
"""

        response = safe_llm_call(lambda: client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a risk analysis AI. Return ONLY valid JSON with zero extra text, quotes, markdown, or explanation. Output JSON structure exactly as specified, nothing else."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=1800,
        ))

        if response is None:
            return default_impact(systems=systems)

        parsed = _parse_json_response(response.choices[0].message.content)
        if not isinstance(parsed, dict):
            return default_impact(systems=systems)

        return _normalize_impact_payload(parsed, systems=systems)

    except Exception as e:
        print("analyze_impact failed:", e)
        return default_impact(systems=[])


def generate_actions(actions_input) -> dict:
    try:
        if isinstance(actions_input, dict):
            gap_texts = [trim_text(text, 200) for text in (actions_input.get("gaps") or []) if text]
        elif isinstance(actions_input, list):
            gap_texts = [trim_text(text, 200) for text in actions_input if text]
        else:
            gap_texts = []

        gap_texts = gap_texts[:4]
        if not gap_texts:
            return default_actions()

        prompt = f"""
You are a Compliance Program Manager designing remediation roadmap.

TASK: Generate practical, implementable actions to close compliance gaps.

CRITICAL RULES:
1. Base actions ONLY on provided gaps (no external additions)
2. Each action must directly address a specific gap
3. Actions must be IMPLEMENTABLE (not wishful thinking)
4. Be specific about: WHO does it, WHAT is done, WHEN it's due
5. Estimate realistic timelines (Immediate=<1 week, 1-2 weeks, 1 month)
6. Priority: High gaps → High priority actions
7. Each action ≤2 lines; concrete language
8. Maximum 4 actions
9. Deduplicate: if 2 actions are similar, report most impactful one
10. If insufficient data, return empty actions array

ACTION QUALITY:
✓ "Implement automated KYC refresh every 2 years with audit logging; assign to Ops; 2 weeks"
✗ "Improve compliance processes"

✓ "Document transaction reporting SOP per RBI guidelines; 1 week"
✗ "Better reporting"

Return ONLY valid JSON with NO additional text or markdown:
{{
  "actions": [
    {{
      "title": "Action title in ≤2 lines. E.g., 'Implement KYC Refresh Workflow (2-year cycle)'",
      "description": "How to implement; who owns; acceptance criteria",
      "priority": "High | Medium | Low",
      "status": "Pending",
      "deadline": "Immediate | 1-2 weeks | 1 month | TBD"
    }}
  ]
}}

COMPLIANCE GAPS REQUIRING REMEDIATION:
{json.dumps(gap_texts, ensure_ascii=True)}
"""

        response = safe_llm_call(lambda: client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a remediation planning AI. Return ONLY valid JSON with zero extra text, explanation, or markdown. JSON output exactly as specified, nothing more."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=1200,
        ))

        if response is None:
            return default_actions()

        parsed = _parse_json_response(response.choices[0].message.content)
        actions = parsed.get("actions") if isinstance(parsed, dict) else None
        if not isinstance(actions, list):
            return default_actions()

        # Deduplicate similar actions
        unique_actions = []
        seen_titles = set()
        for action in actions:
            if isinstance(action, dict):
                title_key = (action.get("title") or "").lower().strip()[:50]
                if title_key and title_key not in seen_titles:
                    normalized = _normalize_action(action)
                    unique_actions.append(normalized)
                    seen_titles.add(title_key)
        
        return {"actions": unique_actions[:4] if unique_actions else default_actions()["actions"]}

    except Exception as e:
        print("generate_actions failed:", e)
        return default_actions()
