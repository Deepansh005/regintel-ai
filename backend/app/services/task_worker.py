import traceback
import re

from db.database import update_task

# ✅ existing services
from app.services.pdf_service import extract_text_from_pdf
from app.services.ai_service import (
    detect_changes,
    analyze_impact,
    generate_actions,
    detect_compliance_gaps
)

from app.rag.retriever import retrieve_with_metadata
from app.rag.vector_store import get_vector_db, store_chunks
from langchain_core.documents import Document


def _extract_changes(payload):
    if isinstance(payload, dict):
        changes = payload.get("changes")
        if isinstance(changes, list):
            return changes
    if isinstance(payload, list):
        return payload
    return []


def _extract_gaps(payload):
    if isinstance(payload, dict):
        gaps = payload.get("gaps")
        if isinstance(gaps, list):
            return gaps
    if isinstance(payload, list):
        return payload
    return []


def _risk_priority(risk):
    order = {"High": 3, "Medium": 2, "Low": 1}
    return order.get((risk or "Low").title(), 1)


def _gap_issue_text(gap):
    if not isinstance(gap, dict):
        return ""
    return str(gap.get("issue") or gap.get("gap") or "")[:200]


def _infer_systems_from_texts(texts):
    joined = " ".join((text or "").lower() for text in texts)
    systems = []

    if "kyc" in joined:
        systems.append("KYC System")
    if "transaction" in joined:
        systems.append("Transaction Monitoring")
    if "report" in joined:
        systems.append("Reporting Engine")

    if not systems:
        systems.append("Core System")

    return systems[:3]


# =============================
# 🔥 SEMANTIC CHUNKING
# =============================
def chunk_markdown_text(markdown_text: str, max_chunk_size: int = 800):
    """
    Split markdown into semantic chunks, filtering empty/whitespace-only chunks
    """
    if not markdown_text or not markdown_text.strip():
        return []
    
    sections = re.split(r"\n(?=#{1,6} )", markdown_text)

    chunks = []

    for section in sections:
        section = section.strip()
        if not section:  # Skip empty sections
            continue

        if len(section) <= max_chunk_size:
            chunks.append(section)
        else:
            sub_chunks = split_large_section(section, max_chunk_size)
            chunks.extend(sub_chunks)

    # Final filter: ensure all chunks have content
    return [c for c in chunks if c and c.strip()]


def split_large_section(text: str, max_chunk_size: int):
    chunks = []
    current = ""

    for line in text.split("\n"):
        if len(current) + len(line) < max_chunk_size:
            current += line + "\n"
        else:
            chunks.append(current.strip())
            current = line + "\n"

    if current:
        chunks.append(current.strip())

    return chunks


# =============================
# CONTEXT BUILDER
# =============================
def build_context(chunks, limit=3000):
    text = "\n\n".join(chunks)
    return text[:limit]


def _default_response_template():
    return {
        "changes": {"changes": []},
        "compliance_gaps": {"gaps": []},
        "impact": {
            "impact": {
                "departments": [],
                "systems": [],
                "risk_level": "Low",
                "priority": "Low",
                "summary": "",
            }
        },
        "actions": {"actions": []},
        "departments": [],
        "systems": [],
    }


def _normalize_changes(payload):
    if isinstance(payload, dict) and isinstance(payload.get("changes"), list):
        return {"changes": payload.get("changes", [])}
    if isinstance(payload, list):
        return {"changes": payload}
    return {"changes": []}


def _normalize_gaps(payload):
    if isinstance(payload, dict) and isinstance(payload.get("gaps"), list):
        return {"gaps": payload.get("gaps", [])}
    if isinstance(payload, list):
        return {"gaps": payload}
    return {"gaps": []}


def _normalize_impact(payload):
    default_impact = {
        "departments": [],
        "systems": [],
        "risk_level": "Low",
        "priority": "Low",
        "summary": "",
    }

    if isinstance(payload, dict):
        inner = payload.get("impact") if isinstance(payload.get("impact"), dict) else payload
        return {
            "impact": {
                "departments": inner.get("departments") if isinstance(inner.get("departments"), list) else [],
                "systems": inner.get("systems") if isinstance(inner.get("systems"), list) else [],
                "risk_level": inner.get("risk_level") or "Low",
                "priority": inner.get("priority") or "Low",
                "summary": inner.get("summary") or "",
            }
        }

    return {"impact": default_impact}


def _normalize_actions(payload):
    if isinstance(payload, dict) and isinstance(payload.get("actions"), list):
        return {"actions": payload.get("actions", [])}
    if isinstance(payload, list):
        return {"actions": payload}
    return {"actions": []}


# =============================
# EDGE CASE HANDLING
# =============================
def _handle_extraction_error(task_id: str, error: Exception) -> dict:
    """Handle extraction/processing failures gracefully"""
    failed_response = _default_response_template()
    failed_response["error"] = f"Processing failed: {str(error)}"
    update_task(task_id, status="failed", result=failed_response)
    return failed_response


def _validate_pdf_content(text: str) -> bool:
    """Validate that PDF extraction produced meaningful content"""
    if not text or not text.strip():
        return False
    
    # Check minimum content (at least 50 non-whitespace characters)
    if len(text.replace("\n", "").replace(" ", "")) < 50:
        return False
    
    return True


# =============================
# MAIN TASK PROCESSOR
# =============================
def process_task(task_id: str, file_paths: dict, file_hashes: dict | None = None):
    try:
        mode = file_paths.get("mode", "all")
        response = _default_response_template()
        
        old_context = ""
        new_context = ""
        policy_context = ""

        # If any 2+ sections have the same PDF content, return deterministic no-change response.
        if file_hashes:
            hashes = [file_hashes.get("old"), file_hashes.get("new"), file_hashes.get("policy")]
            hashes = [h for h in hashes if h]
            if len(hashes) >= 2 and len(set(hashes)) < len(hashes):
                update_task(task_id, status="completed", result=response)
                return

        # ✅ SAFE EXTRACTION WITH VALIDATION
        try:
            if "policy" in file_paths:
                policy_text = extract_text_from_pdf(file_paths["policy"])
                if not _validate_pdf_content(policy_text):
                    raise ValueError("Policy PDF produced no meaningful content (empty or image-only)")
                policy_chunks = chunk_markdown_text(policy_text)
                if not policy_chunks:
                    raise ValueError("Policy PDF produced no text chunks after processing")
                store_chunks(policy_chunks, "internal_policy", file_paths["policy"])
                policy_context = build_context(retrieve_with_metadata("internal compliance rules", "internal_policy"))
                
            if "old" in file_paths:
                old_text = extract_text_from_pdf(file_paths["old"])
                if not _validate_pdf_content(old_text):
                    raise ValueError("Old regulation PDF produced no meaningful content")
                old_chunks = chunk_markdown_text(old_text)
                if not old_chunks:
                    raise ValueError("Old regulation PDF produced no text chunks")
                store_chunks(old_chunks, "old_regulation", file_paths["old"])
                old_context = build_context(retrieve_with_metadata("key regulatory clauses", "old_regulation"))

            if "new" in file_paths:
                new_text = extract_text_from_pdf(file_paths["new"])
                if not _validate_pdf_content(new_text):
                    raise ValueError("New regulation PDF produced no meaningful content")
                new_chunks = chunk_markdown_text(new_text)
                if not new_chunks:
                    raise ValueError("New regulation PDF produced no text chunks")
                store_chunks(new_chunks, "new_regulation", file_paths["new"])
                new_context = build_context(retrieve_with_metadata("latest regulatory changes", "new_regulation"))
        
        except Exception as e:
            return _handle_extraction_error(task_id, e)

        # ✅ VALIDATE THAT WE HAVE CONTENT TO PROCESS
        total_context = len((old_context + new_context + policy_context).replace(" ", "").replace("\n", ""))
        if total_context < 100:
            error_msg = "Insufficient meaningful content extracted from PDFs to perform analysis"
            failed_response = _default_response_template()
            failed_response["error"] = error_msg
            update_task(task_id, status="failed", result=failed_response)
            return

        # =============================
        # 5. AI PROCESSING
        # =============================
        changes = {"changes": []}
        compliance_gaps = {"gaps": []}
        
        if mode == "all":
            if old_context and new_context:
                try:
                    changes = detect_changes(old_context, new_context)
                except Exception:
                    pass
            if new_context and policy_context:
                try:
                    compliance_gaps = detect_compliance_gaps(new_context, policy_context)
                except Exception:
                    pass
        elif mode == "old":
            if old_context and policy_context:
                try:
                    compliance_gaps = detect_compliance_gaps(old_context, policy_context)
                except Exception:
                    pass
        elif mode == "new":
            if new_context and policy_context:
                try:
                    compliance_gaps = detect_compliance_gaps(new_context, policy_context)
                except Exception:
                    pass

        changes_items = _extract_changes(changes)[:5]
        gaps_items = _extract_gaps(compliance_gaps)
        gaps_items = sorted(gaps_items, key=lambda item: _risk_priority((item or {}).get("risk") or (item or {}).get("risk_level")), reverse=True)
        gaps_items = gaps_items[:8]

        gap_texts = [_gap_issue_text(gap) for gap in gaps_items]
        gap_texts = [text for text in gap_texts if text][:5]
        systems = _infer_systems_from_texts(gap_texts + [str(change.get("summary") or "") for change in changes_items if isinstance(change, dict)])

        impact_input = {
            "gaps": gap_texts[:5],
            "systems": systems[:3],
        }

        actions_input = gap_texts[:5]

        impact = None
        try:
            impact = analyze_impact(impact_input)
        except Exception:
            pass

        if not impact:
            impact = {
                "impact": {
                    "departments": ["Compliance", "Risk"],
                    "systems": systems[:3] if systems else ["Core System"],
                    "risk_level": "Medium",
                    "priority": "Medium",
                    "summary": "Impact generated using fallback due to size constraints",
                }
            }

        actions = None
        try:
            actions = generate_actions(actions_input)
        except Exception:
            pass

        if not actions:
            actions = {
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

        response = {
            "changes": {"changes": changes_items},
            "compliance_gaps": {"gaps": gaps_items},
            "impact": impact,
            "actions": actions,
            "departments": (impact.get("impact", {}) if isinstance(impact, dict) else {}).get("departments", ["Compliance", "Risk"]),
            "systems": (impact.get("impact", {}) if isinstance(impact, dict) else {}).get("systems", systems[:3] if systems else ["Core System"]),
        }

        # ✅ SAVE SUCCESS
        update_task(task_id, status="completed", result=response)

    except Exception as e:
        traceback.print_exc()

        failed_response = _default_response_template()
        failed_response["error"] = str(e)

        update_task(
            task_id,
            status="failed",
            result=failed_response
        )