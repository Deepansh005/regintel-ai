import traceback
import re
import os
import uuid
import asyncio
import logging

logger = logging.getLogger(__name__)

from db.database import update_task

# ✅ existing services
from app.services.pdf_service import extract_pdf_pages
from app.services.ai_service import (
    deduplicate_items,
    detect_changes,
    analyze_impact,
    generate_actions,
    detect_compliance_gaps,
)
from app.services.context_optimizer import optimize_context_chunks
from app.services.clause_extractor import extract_clauses_from_text, extract_clauses_from_pages

from app.rag.retriever import retrieve_with_metadata
from app.rag.vector_store import store_chunks


def _tokenize(text: str):
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


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
        gaps = payload.get("compliance_gaps")
        if not isinstance(gaps, list):
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


def _build_chunk_records(page_records: list[dict], file_path: str) -> list[dict]:
    source_file_name = os.path.basename(file_path)
    chunk_records = []

    try:
        logger.info("📄 Processing PDF: %s", source_file_name)
        clauses = extract_clauses_from_pages(page_records or [])
        logger.info("Clause summary for %s: clauses=%s pages=%s", source_file_name, len(clauses), len(page_records or []))
    except Exception as exc:
        logger.error("Clause extraction failed, falling back to chunking: %s", exc)
        clauses = []

    if clauses:
        page_items = clauses
    else:
        page_items = []
        for page_record in page_records or []:
            page_number = page_record.get("page_number")
            page_text = page_record.get("text") or ""
            page_items.extend(
                {
                    "clause_id": f"legacy-{page_number}-{index}",
                    "title": f"Legacy Chunk {index}",
                    "content": chunk_text,
                    "page_number": page_number,
                    "source_file_name": source_file_name,
                }
                for index, chunk_text in enumerate(chunk_markdown_text(page_text), start=1)
            )

    for clause_index, clause in enumerate(page_items, start=1):
        normalized_text = (clause.get("content") or "").strip()
        if not normalized_text:
            continue

        clause_page_number = clause.get("page_number")
        chunk_page_number = clause_page_number if clause_page_number is not None else "unknown"

        chunk_records.append(
            {
                "chunk_id": f"{source_file_name}-p{chunk_page_number}-c{clause_index}-{uuid.uuid4().hex[:8]}",
                "text": normalized_text,
                "page_number": clause_page_number,
                "source_file_name": source_file_name,
                "clause_id": clause.get("clause_id"),
                "title": clause.get("title"),
            }
        )

    return chunk_records


def _as_file_list(file_value):
    if not file_value:
        return []
    if isinstance(file_value, list):
        return [item for item in file_value if item]
    return [file_value]


def _legacy_chunk_markdown_text(markdown_text: str, max_chunk_size: int = 800):
    if not markdown_text or not markdown_text.strip():
        return []

    sections = re.split(r"\n(?=#{1,6} )", markdown_text)
    chunks = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        if len(section) <= max_chunk_size:
            chunks.append(section)
        else:
            sub_chunks = split_large_section(section, max_chunk_size)
            chunks.extend(sub_chunks)

    return [chunk for chunk in chunks if chunk and chunk.strip()]


def _build_source_lookup(*source_groups):
    lookup = {}
    for group in source_groups:
        for record in group or []:
            chunk_id = record.get("chunk_id")
            if chunk_id:
                lookup[chunk_id] = record
    return lookup


def _format_chunk_context(chunks: list[dict], limit: int = 3000):
    lines = []
    for record in chunks or []:
        chunk_id = record.get("chunk_id") or "unknown"
        page_number = record.get("page_number")
        source_file_name = record.get("source_file_name") or "unknown.pdf"
        text = (record.get("text") or "").strip()
        lines.append(f"[{chunk_id} | page {page_number} | {source_file_name}] {text}")

    return "\n\n".join(lines)[:limit]


def _seed_gap_texts_from_chunks(chunks: list[dict], max_items: int = 5):
    seeded = []
    for chunk in chunks or []:
        text = (chunk.get("text") or "").strip()
        if not text:
            continue
        seeded.append(text[:200])
        if len(seeded) >= max_items:
            break
    return seeded


def _empty_pipeline_schema() -> dict:
    return {
        "changes": [],
        "compliance_gaps": [],
        "impacts": [],
        "actions": [],
        "department_risk": [],
    }


def _build_department_risk(impacts: list[dict]) -> list[dict]:
    if not isinstance(impacts, list) or not impacts:
        return []

    severity_weight = {"high": 3, "medium": 2, "low": 1}
    scores = {}

    for impact in impacts:
        if not isinstance(impact, dict):
            continue

        severity = str(impact.get("severity") or "Medium").strip().lower()
        weight = severity_weight.get(severity, 2)
        departments = impact.get("impacted_departments")
        if isinstance(departments, str):
            departments = [departments]
        if not isinstance(departments, list):
            departments = []

        for department in departments:
            label = str(department or "").strip()
            if not label:
                continue
            scores[label] = scores.get(label, 0) + weight

    if not scores:
        return []

    max_score = max(scores.values()) or 1
    result = [
        {
            "department": department,
            "risk_percent": int(round((score / max_score) * 100)),
        }
        for department, score in scores.items()
    ]
    result.sort(key=lambda item: item.get("risk_percent", 0), reverse=True)
    return result


async def _run_analysis_pipeline(mode: str, old_context: str, new_context: str, policy_context: str):
    """
    Dependency-safe flow: changes -> compliance_gaps -> impacts -> actions
    Stage internals remain batched/parallel in ai_service.
    """
    changes_payload = {"changes": [], "compliance_gaps": [], "impacts": [], "actions": []}
    gaps_payload = {"changes": [], "compliance_gaps": [], "impacts": [], "actions": []}
    impacts_payload = {"changes": [], "compliance_gaps": [], "impacts": [], "actions": []}
    actions_payload = {"changes": [], "compliance_gaps": [], "impacts": [], "actions": []}

    if mode == "all" and old_context and new_context:
        changes_payload = await asyncio.to_thread(detect_changes, old_context, new_context)

    if mode == "all" and new_context and policy_context:
        gaps_payload = await asyncio.to_thread(detect_compliance_gaps, new_context, policy_context)
    elif mode == "old" and old_context and policy_context:
        gaps_payload = await asyncio.to_thread(detect_compliance_gaps, old_context, policy_context)
    elif mode == "new" and new_context and policy_context:
        gaps_payload = await asyncio.to_thread(detect_compliance_gaps, new_context, policy_context)

    impacts_input = {
        "changes": (changes_payload or {}).get("changes", []),
        "compliance_gaps": (gaps_payload or {}).get("compliance_gaps", []),
    }
    impacts_payload = await asyncio.to_thread(analyze_impact, impacts_input)

    actions_input = {
        "changes": (changes_payload or {}).get("changes", []),
        "compliance_gaps": (gaps_payload or {}).get("compliance_gaps", []),
        "impacts": (impacts_payload or {}).get("impacts", []),
    }
    actions_payload = await asyncio.to_thread(generate_actions, actions_input)

    return changes_payload, gaps_payload, impacts_payload, actions_payload


def _pick_source_chunks(item_text: str, candidate_chunks: list[dict], max_sources: int = 2):
    if not candidate_chunks:
        return []

    item_tokens = _tokenize(item_text)
    ranked = []

    for record in candidate_chunks:
        source_tokens = _tokenize(record.get("text"))
        score = len(item_tokens & source_tokens)
        if record.get("source_file_name") and record.get("source_file_name").lower() in (item_text or "").lower():
            score += 1
        ranked.append((score, record.get("chunk_id")))

    ranked.sort(key=lambda item: item[0], reverse=True)
    selected = [chunk_id for score, chunk_id in ranked if chunk_id][:max_sources]

    if not selected:
        selected = [record.get("chunk_id") for record in candidate_chunks[:max_sources] if record.get("chunk_id")]

    return selected[:max_sources]


def _attach_source_chunks(items: list[dict], candidate_chunks: list[dict], text_fields: list[str], max_sources: int = 2):
    for item in items or []:
        if not isinstance(item, dict):
            continue

        item_text = " ".join(str(item.get(field) or "") for field in text_fields)
        item["source_chunks"] = _pick_source_chunks(item_text, candidate_chunks, max_sources=max_sources)

    return items


def _collect_source_chunks_from_items(items: list[dict]):
    source_ids = []
    seen = set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        for chunk_id in item.get("source_chunks") or []:
            if chunk_id and chunk_id not in seen:
                seen.add(chunk_id)
                source_ids.append(chunk_id)
    return source_ids


# =============================
# 🔥 SEMANTIC CHUNKING
# =============================
def chunk_markdown_text(markdown_text: str, max_chunk_size: int = 800):
    """
    Split markdown into semantic chunks, filtering empty/whitespace-only chunks
    """
    if not markdown_text or not markdown_text.strip():
        return []

    try:
        clauses = extract_clauses_from_text(markdown_text)
        if clauses:
            return [
                (clause.get("content") or "").strip()
                for clause in clauses
                if (clause.get("content") or "").strip()
            ]
    except Exception as exc:
        logger.warning("Clause extraction failed, falling back to legacy chunking: %s", exc)

    return _legacy_chunk_markdown_text(markdown_text, max_chunk_size=max_chunk_size)


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
    text_parts = []

    for chunk in chunks or []:
        if isinstance(chunk, dict):
            chunk_id = chunk.get("chunk_id") or "unknown"
            page_number = chunk.get("page_number")
            source_file_name = chunk.get("source_file_name") or "unknown.pdf"
            text = (chunk.get("text") or "").strip()
            text_parts.append(f"[{chunk_id} | page {page_number} | {source_file_name}] {text}")
        else:
            text_parts.append(str(chunk))

    text = "\n\n".join(text_parts)
    return text[:limit]


def _default_response_template():
    return _empty_pipeline_schema()


def _normalize_changes(payload):
    if isinstance(payload, dict) and isinstance(payload.get("changes"), list):
        return payload.get("changes", [])
    if isinstance(payload, list):
        return payload
    return []


def _normalize_gaps(payload):
    if isinstance(payload, dict) and isinstance(payload.get("compliance_gaps"), list):
        return payload.get("compliance_gaps", [])
    if isinstance(payload, dict) and isinstance(payload.get("gaps"), list):
        return payload.get("gaps", [])
    if isinstance(payload, list):
        return payload
    return []


def _normalize_impact(payload):
    def _normalize_severity(value):
        level = str(value or "").strip().lower()
        if level == "high":
            return "High"
        if level == "medium":
            return "Medium"
        if level == "low":
            return "Low"
        return "Medium"

    def _normalize_item(item):
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

        return {
            "title": str(item.get("title") or item.get("area") or "Compliance Impact").strip(),
            "description": str(item.get("description") or item.get("summary") or "Impact identified from regulatory changes and policy gaps").strip(),
            "severity": _normalize_severity(item.get("severity")),
            "impacted_departments": normalized_departments,
        }

    raw_impacts = []
    if isinstance(payload, dict) and isinstance(payload.get("impacts"), list):
        raw_impacts = payload.get("impacts", [])
    elif isinstance(payload, dict) and isinstance(payload.get("impact"), dict):
        raw_impacts = [payload.get("impact")]
    elif isinstance(payload, list):
        raw_impacts = payload

    return [_normalize_item(item) for item in raw_impacts if isinstance(item, dict)]


def _normalize_actions(payload):
    if isinstance(payload, dict) and isinstance(payload.get("actions"), list):
        return payload.get("actions", [])
    if isinstance(payload, list):
        return payload
    return []


# =============================
# EDGE CASE HANDLING
# =============================
def _handle_extraction_error(task_id: str, error: Exception) -> dict:
    """Handle extraction/processing failures gracefully with user-friendly messages"""
    error_msg = str(error).lower()
    failed_response = _default_response_template()
    
    # Provide helpful error messages based on the error type
    if "no text" in error_msg or "image-only" in error_msg or "scanned" in error_msg:
        failed_response["error"] = (
            "⚠️ This PDF appears to be scanned or image-based. "
            "Trying OCR extraction... "
            "For best results, ensure Tesseract OCR is installed: "
            "https://github.com/UB-Mannheim/tesseract/wiki"
        )
    elif "corrupted" in error_msg or "invalid" in error_msg:
        failed_response["error"] = "❌ PDF appears to be corrupted or invalid. Please try another file."
    elif "empty" in error_msg:
        failed_response["error"] = "❌ PDF is empty or contains no readable content."
    elif "encrypted" in error_msg or "password" in error_msg:
        failed_response["error"] = "❌ PDF is password-protected. Please remove password protection and try again."
    elif "meaningful content" in error_msg:
        failed_response["error"] = (
            "⚠️ Could not extract meaningful text from PDF. "
            "If this is a scanned document, OCR will be attempted on retry."
        )
    else:
        failed_response["error"] = (
            f"Processing failed: {str(error)} "
            "If the issue persists, ensure the PDF is valid and not corrupted."
        )
    
    logger.error(f"Extraction failed for task {task_id}: {str(error)}")
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
            hashes = []
            for section in ("old", "new", "policy"):
                section_hashes = file_hashes.get(section)
                if isinstance(section_hashes, list):
                    hashes.extend([item for item in section_hashes if item])
                elif section_hashes:
                    hashes.append(section_hashes)
            if len(hashes) >= 2 and len(set(hashes)) < len(hashes):
                update_task(task_id, status="completed", result=response)
                return

        # ✅ SAFE EXTRACTION WITH VALIDATION
        try:
            policy_source_chunks = []
            old_source_chunks = []
            new_source_chunks = []
            per_pdf_clause_map = {}

            policy_files = _as_file_list(file_paths.get("policy"))
            old_files = _as_file_list(file_paths.get("old"))
            new_files = _as_file_list(file_paths.get("new"))

            if policy_files:
                for policy_file in policy_files:
                    logger.info(f"📄 Processing Policy PDF: {os.path.basename(policy_file)}")
                    policy_pages = extract_pdf_pages(policy_file)
                    logger.info(f"📄 Policy PDF: Extracted {len(policy_pages)} pages")
                    file_chunks = _build_chunk_records(policy_pages, policy_file)
                    if not file_chunks:
                        raise ValueError(
                            "Policy PDF produced no text chunks. "
                            "PDF may be blank or image-only. Enable OCR for scanned PDFs."
                        )
                    policy_source_chunks.extend(file_chunks)
                    per_pdf_clause_map[os.path.basename(policy_file)] = file_chunks
                    logger.info(f"📦 Policy PDF: Created {len(file_chunks)} chunks")
                    store_chunks(file_chunks, "internal_policy", policy_file)

                policy_sources = retrieve_with_metadata("internal compliance rules", "internal_policy", k=5)
                if not policy_sources:
                    raise ValueError("Policy PDF chunks could not be indexed or retrieved")
                policy_sources, policy_context = optimize_context_chunks(policy_sources, max_chunks=5, compress=True)
                
            if old_files:
                for old_file in old_files:
                    logger.info(f"📄 Processing Old Regulation PDF: {os.path.basename(old_file)}")
                    old_pages = extract_pdf_pages(old_file)
                    logger.info(f"📄 Old regulation PDF: Extracted {len(old_pages)} pages")
                    file_chunks = _build_chunk_records(old_pages, old_file)
                    if not file_chunks:
                        raise ValueError(
                            "Old regulation PDF produced no text chunks. "
                            "PDF may be blank or image-only. Enable OCR for scanned PDFs."
                        )
                    old_source_chunks.extend(file_chunks)
                    per_pdf_clause_map[os.path.basename(old_file)] = file_chunks
                    logger.info(f"📦 Old regulation PDF: Created {len(file_chunks)} chunks")
                    store_chunks(file_chunks, "old_regulation", old_file)

                old_sources = retrieve_with_metadata("key regulatory clauses", "old_regulation", k=5)
                if not old_sources:
                    raise ValueError("Old regulation PDF chunks could not be indexed or retrieved")
                old_sources, old_context = optimize_context_chunks(old_sources, max_chunks=5, compress=True)

            if new_files:
                for new_file in new_files:
                    logger.info(f"📄 Processing New Regulation PDF: {os.path.basename(new_file)}")
                    new_pages = extract_pdf_pages(new_file)
                    logger.info(f"📄 New regulation PDF: Extracted {len(new_pages)} pages")
                    file_chunks = _build_chunk_records(new_pages, new_file)
                    if not file_chunks:
                        raise ValueError(
                            "New regulation PDF produced no text chunks. "
                            "PDF may be blank or image-only. Enable OCR for scanned PDFs."
                        )
                    new_source_chunks.extend(file_chunks)
                    per_pdf_clause_map[os.path.basename(new_file)] = file_chunks
                    logger.info(f"📦 New regulation PDF: Created {len(file_chunks)} chunks")
                    store_chunks(file_chunks, "new_regulation", new_file)

                new_sources = retrieve_with_metadata("latest regulatory changes", "new_regulation", k=5)
                if not new_sources:
                    raise ValueError("New regulation PDF chunks could not be indexed or retrieved")
                new_sources, new_context = optimize_context_chunks(new_sources, max_chunks=5, compress=True)
        
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
        analysis_source_pool = []
        if mode == "all":
            analysis_source_pool = (old_sources if 'old_sources' in locals() else []) + (new_sources if 'new_sources' in locals() else []) + (policy_sources if 'policy_sources' in locals() else [])
        elif mode == "old":
            analysis_source_pool = (old_sources if 'old_sources' in locals() else []) + (policy_sources if 'policy_sources' in locals() else [])
        elif mode == "new":
            analysis_source_pool = (new_sources if 'new_sources' in locals() else []) + (policy_sources if 'policy_sources' in locals() else [])

        try:
            changes_payload, compliance_gaps_payload, impacts_payload, actions_payload = asyncio.run(
                _run_analysis_pipeline(
                    mode=mode,
                    old_context=old_context,
                    new_context=new_context,
                    policy_context=policy_context,
                )
            )
        except Exception:
            changes_payload = _empty_pipeline_schema()
            compliance_gaps_payload = _empty_pipeline_schema()
            impacts_payload = _empty_pipeline_schema()
            actions_payload = _empty_pipeline_schema()

        changes_items = _extract_changes(changes_payload)[:5]
        gaps_items = _extract_gaps(compliance_gaps_payload)
        gaps_items = sorted(gaps_items, key=lambda item: _risk_priority((item or {}).get("risk") or (item or {}).get("risk_level")), reverse=True)
        gaps_items = deduplicate_items(gaps_items[:8])
        impacts_items = deduplicate_items(_normalize_impact(impacts_payload)[:6])
        actions_items = deduplicate_items(_normalize_actions(actions_payload)[:8])

        old_lookup = _build_source_lookup(old_source_chunks)
        new_lookup = _build_source_lookup(new_source_chunks)
        policy_lookup = _build_source_lookup(policy_source_chunks)

        if mode == "all":
            change_candidates = list(old_lookup.values()) + list(new_lookup.values())
            gap_candidates = list(new_lookup.values()) + list(policy_lookup.values())
        elif mode == "old":
            change_candidates = list(old_lookup.values()) + list(policy_lookup.values())
            gap_candidates = list(old_lookup.values()) + list(policy_lookup.values())
        else:
            change_candidates = list(new_lookup.values()) + list(policy_lookup.values())
            gap_candidates = list(new_lookup.values()) + list(policy_lookup.values())

        changes_items = _attach_source_chunks(changes_items, change_candidates, ["summary", "impact"], max_sources=2)
        gaps_items = _attach_source_chunks(gaps_items, gap_candidates, ["issue", "regulation_requirement", "policy_current_state"], max_sources=2)

        gap_source_ids = _collect_source_chunks_from_items(gaps_items)
        gap_candidate_lookup = {chunk_id: record for chunk_id, record in {**old_lookup, **new_lookup, **policy_lookup}.items()}
        gap_source_candidates = [gap_candidate_lookup[chunk_id] for chunk_id in gap_source_ids if chunk_id in gap_candidate_lookup]

        action_source_candidates = gap_source_candidates or gap_candidates
        for impact_item in impacts_items:
            if isinstance(impact_item, dict):
                impact_item["source_chunks"] = _pick_source_chunks(
                    f"{impact_item.get('title') or ''} {impact_item.get('description') or ''}",
                    gap_source_candidates or gap_candidates,
                    max_sources=3,
                )

        for action in actions_items:
            if isinstance(action, dict):
                action["source_chunks"] = _pick_source_chunks(
                    f"{action.get('action') or ''} {action.get('owner') or ''}",
                    action_source_candidates,
                    max_sources=2,
                )

        response = {
            "changes": changes_items,
            "compliance_gaps": gaps_items,
            "impacts": impacts_items,
            "actions": actions_items,
            "department_risk": _build_department_risk(impacts_items),
            "file_clause_map": {
                file_name: [
                    {
                        "clause_id": item.get("clause_id"),
                        "title": item.get("title"),
                        "page_number": item.get("page_number"),
                        "text": item.get("text"),
                    }
                    for item in items
                ]
                for file_name, items in per_pdf_clause_map.items()
            },
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