from groq import Groq
from app.core.config import GROQ_API_KEY
import json


client = Groq(api_key=GROQ_API_KEY)


def safe_json_parse(content):
    try:
        return json.loads(content)
    except:
        return {"raw": content}

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
          temperature=0.2
        )

        content = response.choices[0].message.content
        return safe_json_parse(content)
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

CHANGES:
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
          temperature=0.2
        )

        content = response.choices[0].message.content
        return safe_json_parse(content)

    except Exception as e:
        return {"error": str(e)}


def detect_changes(old_text: str, new_text: str) -> dict:
    try:
        prompt = f"""
You are a senior regulatory analyst specializing in financial regulations (RBI, SEBI, Basel, etc.).

Your task is to compare two regulatory documents and identify meaningful changes.

STRICT INSTRUCTIONS:
- Focus ONLY on meaningful regulatory differences (ignore formatting, numbering, whitespace)
- Group similar changes together
- Be concise but precise
- Extract actual regulatory meaning, not raw text dumps

Return ONLY valid JSON (no explanation, no markdown):

{{
  "changes": [
    {{
      "type": "added | removed | modified",
      "category": "KYC | Risk | Capital | Reporting | Governance | Other",
      "section": "section or topic name",
      "old": "short relevant excerpt or null",
      "new": "short relevant excerpt or null",
      "summary": "clear explanation of what changed and why it matters"
    }}
  ]
}}

OLD:
{old_text[:3000]}

NEW:
{new_text[:3000]}
"""
        print(" Calling Groq API...")
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
          temperature=0.2
        )

        content = response.choices[0].message.content
        return safe_json_parse(content)

    except Exception as e:
        return {"error": str(e)}