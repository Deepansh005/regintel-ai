from groq import Groq
from app.core.config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)


def detect_changes(old_text: str, new_text: str) -> dict:
    try:
        prompt = f"""
You are a regulatory analyst AI.

Compare OLD and NEW regulation documents.

Return ONLY JSON:

{{
  "changes": [
    {{
      "type": "added | removed | modified",
      "section": "section name",
      "old": "old text",
      "new": "new text",
      "summary": "short explanation"
    }}
  ]
}}

OLD:
{old_text[:3000]}

NEW:
{new_text[:3000]}
"""
        print("🚀 Calling Groq API...")
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )

        content = response.choices[0].message.content

        return {
            "changes": content
        }

    except Exception as e:
        return {"error": str(e)}