from groq import Groq
from app.core.config import GROQ_API_KEY
import json
import re


client = Groq(api_key=GROQ_API_KEY)
def safe_json_parse(content):
    try:
        return json.loads(content)
    except:
        return {"raw": content}

def clean_json_output(content):
    match = re.search(r'\{.*\}', content, re.DOTALL)
    if match:
        return safe_json_parse(match.group(0))
    return {"error": "Invalid JSON"}

def generate_actions(changes: str, impact: str) -> dict:
    try:
        prompt = f"""
You are a compliance implementation expert helping a financial institution respond to regulatory changes.

Generate clear, actionable, step-by-step compliance actions.

STRICT INSTRUCTIONS:
- Actions must be practical and executable
- Include both technical and operational steps
- Avoid vague statements
- Order actions logically
- Base actions on SOURCE-backed evidence
- DO NOT generate new interpretations
- ONLY extract from given text
- If unsure, return empty

Return ONLY valid JSON:

{{
  "actions": [
    {{
      "step": "short action title",
      "description": "what exactly needs to be done",
      "owner": "Compliance | Risk | IT | Operations",
      "timeline": "Immediate | 1-2 weeks | 1 month",
      "priority": "High | Medium | Low"
    }}
  ]
}}

CHANGES:
{changes}

IMPACT:
{impact}
"""

        print(" Generating actions...")

        response = client.chat.completions.create(
          model="llama-3.1-8b-instant",
          messages=[
            {
              "role": "system",
              "content": "You are a precise regulatory AI that ALWAYS returns valid JSON. Do not include explanations, markdown, or extra text."
            },
            {
              "role": "user",
              "content": prompt
            }
          ],
          temperature=0.0
        )

        content = response.choices[0].message.content
        return clean_json_output(content)
    except Exception as e:
        return {"error": str(e)}

def analyze_impact(changes: str) -> dict:
    try:
        prompt = f"""
You are a compliance and risk officer in a financial institution.

Analyze the regulatory changes and determine their business impact.

STRICT INSTRUCTIONS:
- Think from perspective of a bank/fintech
- Map changes to real departments and systems
- Assign realistic risk level
- Be concise and structured
- MUST reference SOURCE tags where relevant
- DO NOT generate new interpretations
- ONLY extract from given text
- If unsure, return empty

Return ONLY valid JSON:

{{
  "impact": {{
    "departments": ["Compliance", "Risk", "Operations", "IT", "Legal"],
    "systems": ["KYC System", "Transaction Monitoring", "Reporting Engine"],
    "risk_level": "Low | Medium | High",
    "priority": "Low | Medium | High",
    "summary": "clear explanation of operational and regulatory impact"
  }}
}}

TEXT (WITH SOURCES):
{changes}
"""

        print(" Analyzing impact...")

        response = client.chat.completions.create(
          model="llama-3.1-8b-instant",
          messages=[
            {
              "role": "system",
              "content": "You are a precise regulatory AI that ALWAYS returns valid JSON. Do not include explanations, markdown, or extra text."
            },
            {
              "role": "user",
              "content": prompt
            }
          ],
          temperature=0.0
        )

        content = response.choices[0].message.content
        return clean_json_output(content)

    except Exception as e:
        return {"error": str(e)}

def detect_changes(old_text: str, new_text: str) -> dict:
    try:
        prompt = f"""
You are a senior regulatory analyst specializing in financial regulations (RBI, SEBI, Basel, etc.).

Your task is to compare OLD vs NEW regulatory context and identify meaningful changes.

STRICT RULES:
- REMOVE duplicates
- ONLY use the provided context
- DO NOT hallucinate
- MUST reference SOURCE tags in "summary"
- Focus only on meaningful regulatory changes (ignore formatting)
- DO NOT generate new interpretations
- ONLY extract from given text
- If unsure, return empty

Return ONLY valid JSON:

{{
  "changes": [
    {{
      "type": "added | removed | modified",
      "category": "KYC | Risk | Capital | Reporting | Governance | Other",
      "section": "section or clause name",
      "summary": "what changed + include [SOURCE X | collection_name]"
    }}
  ]
}}

OLD CONTEXT:
{old_text}

NEW CONTEXT:
{new_text}
"""

        print("Calling Groq API...")

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise regulatory AI that ALWAYS returns valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.0
        )

        content = response.choices[0].message.content
        return clean_json_output(content)

    except Exception as e:
        return {"error": str(e)}
    
def detect_compliance_gaps(new_text: str, policy_text: str) -> dict:
    try:
        prompt = f"""
You are a compliance auditor.

Compare REGULATION vs INTERNAL POLICY.

Find ONLY mismatches (compliance gaps).

STRICT RULES:
- Identify where policy does NOT meet regulation
- MUST reference SOURCE tags
- DO NOT list general rules
- DO NOT generate new interpretations
- ONLY extract from given text
- If unsure, return empty

Return JSON:

{{
  "gaps": [
    {{
      "issue": "what is missing or incorrect",
      "regulation_reference": "[SOURCE X | new_regulation]",
      "policy_reference": "[SOURCE Y | internal_policy]",
      "risk": "High | Medium | Low"
    }}
  ]
}}

REGULATION:
{new_text}

POLICY:
{policy_text}
"""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Return ONLY valid JSON"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0
        )

        content = response.choices[0].message.content
        return clean_json_output(content)

    except Exception as e:
        return {"error": str(e)}