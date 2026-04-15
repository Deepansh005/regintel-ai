import traceback
import re
import os
import uuid
import asyncio
import logging
import json

logger = logging.getLogger(__name__)

from db.database import update_task

# ✅ existing services
from app.services.pdf_service import extract_pdf_pages
from app.services.ai_service import (
    deduplicate_items,
    detect_changes,
    detect_compliance_gaps,
    run_full_analysis,
)
from app.services.context_optimizer import optimize_context_chunks
from app.services.semantic_block_extractor import extract_semantic_blocks, extract_semantic_blocks_from_pages

from app.rag.retriever import retrieve_with_metadata
from app.rag.vector_store import store_chunks


def _tokenize(text: str):
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _normalize_change_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


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

    all_text = "\n\n".join(str((page or {}).get("text") or "").strip() for page in (page_records or []) if str((page or {}).get("text") or "").strip())
    blocks = extract_semantic_blocks_from_pages(page_records, file_name=source_file_name) if page_records else []

    if not blocks and all_text:
        # Failsafe: fallback to simple paragraph blocks when semantic extraction yields zero.
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", all_text) if part and part.strip()]
        blocks = [
            {
                "block_id": f"fallback-{index}",
                "heading": "Paragraph Block",
                "content": paragraph,
            }
            for index, paragraph in enumerate(paragraphs, start=1)
        ]

    print("Using semantic blocks:", len(blocks))

    for block_index, block in enumerate(blocks, start=1):
        normalized_text = str(block.get("content") or "").strip()
        if not normalized_text:
            continue

        chunk_page_number = block.get("page") if block.get("page") is not None else "unknown"

        chunk_records.append(
            {
                "chunk_id": f"{source_file_name}-p{chunk_page_number}-b{block_index}-{uuid.uuid4().hex[:8]}",
                "text": normalized_text,
                "page_number": chunk_page_number if chunk_page_number != "unknown" else None,
                "source_file_name": source_file_name,
                "block_id": block.get("block_id") or f"block-{block_index}",
                "title": block.get("heading") or "Semantic Block",
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
        "results": [],
    }


def _dedupe_changes_by_field_new(changes: list[dict]) -> list[dict]:
    deduped = []
    seen = set()
    for item in changes or []:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field") or "").strip().lower()
        new_value = str(item.get("new") or "").strip().lower()
        if not field:
            continue
        key = f"{field}|{new_value}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _build_action_from_gap(gap: dict) -> dict:
    issue = str((gap or {}).get("title") or (gap or {}).get("gap") or (gap or {}).get("issue") or "Regulatory gap").strip()
    severity = str((gap or {}).get("severity") or (gap or {}).get("risk") or "Medium").strip().title()
    if severity not in {"High", "Medium", "Low"}:
        severity = "Medium"
    return {
        "title": f"Close gap: {issue[:90]}",
        "description": f"Implement control update in policy and operating workflow to close: {issue}",
        "department": "Compliance",
        "priority": severity,
        "status": "Pending",
        "deadline": "Current compliance cycle",
    }


def _align_actions_to_gaps(actions: list[dict], gaps: list[dict]) -> list[dict]:
    target = len(gaps or [])
    normalized = [item for item in (actions or []) if isinstance(item, dict)]
    if target <= 0:
        return normalized
    if len(normalized) > target:
        return normalized[:target]
    if len(normalized) < target:
        for gap in (gaps or [])[len(normalized):target]:
            normalized.append(_build_action_from_gap(gap if isinstance(gap, dict) else {}))
    return normalized


_INVALID_TEXT_VALUES = {
    "",
    "-",
    "n/a",
    "na",
    "none",
    "null",
    "no description provided",
    "no summary provided",
    "tbd",
}

_PLACEHOLDER_REF_VALUES = {
    "",
    "-",
    "n/a",
    "na",
    "none",
    "null",
    "not specified in provided documents",
    "not specified",
}


def _clean_text(value, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    compact = re.sub(r"\s+", " ", text)
    if compact.lower() in _INVALID_TEXT_VALUES:
        return fallback
    return compact


def _normalize_level(value: str, default: str = "Medium") -> str:
    normalized = str(value or "").strip().title()
    if normalized in {"High", "Medium", "Low"}:
        return normalized
    return default


def _dedupe_items(items: list[dict], key_builder) -> list[dict]:
    result = []
    seen = set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        key = key_builder(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


_SEMANTIC_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "to", "of", "for", "and", "or", "in", "on", "with", "by", "as",
    "policy", "regulation", "requirement", "rule", "clause", "section", "must", "shall", "should",
}


def _semantic_key(text: str) -> str:
    tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", str(text or "").lower())
        if token and token not in _SEMANTIC_STOP_WORDS and len(token) > 2
    ]
    return "|".join(sorted(set(tokens))[:20])


def _is_placeholder_reference(value: str) -> bool:
    return str(value or "").strip().lower() in _PLACEHOLDER_REF_VALUES


def _best_gap_match(gaps: list[dict], text: str) -> dict | None:
    target_tokens = _tokenize(text)
    if not target_tokens:
        return None

    best_gap = None
    best_score = -1
    for gap in gaps or []:
        if not isinstance(gap, dict):
            continue
        gap_text = " ".join(
            [
                str(gap.get("gap") or ""),
                str(gap.get("title") or ""),
                str(gap.get("description") or ""),
                str(gap.get("reference") or ""),
                str(gap.get("regulation_reference") or ""),
            ]
        )
        score = len(target_tokens & _tokenize(gap_text))
        if score > best_score:
            best_gap = gap
            best_score = score
    return best_gap if best_score > 0 else None


def _resolve_gap_link(
    provided_gap_id: str,
    provided_gap_reference: str,
    evidence_text: str,
    gaps: list[dict],
) -> tuple[str, str, dict | None]:
    gap_id = str(provided_gap_id or "").strip()
    gap_reference = str(provided_gap_reference or "").strip()

    for gap in gaps or []:
        if not isinstance(gap, dict):
            continue
        candidate_id = str(gap.get("gap_id") or "").strip()
        candidate_ref = str(gap.get("reference") or gap.get("regulation_reference") or "").strip()
        if gap_id and (gap_id == candidate_id or gap_id == candidate_ref):
            return candidate_id or candidate_ref, candidate_ref or candidate_id, gap
        if gap_reference and (gap_reference == candidate_ref or gap_reference == candidate_id):
            return candidate_id or candidate_ref, candidate_ref or candidate_id, gap

    best = _best_gap_match(gaps, evidence_text)
    if isinstance(best, dict):
        candidate_id = str(best.get("gap_id") or "").strip()
        candidate_ref = str(best.get("reference") or best.get("regulation_reference") or "").strip()
        return candidate_id or candidate_ref, candidate_ref or candidate_id, best

    return gap_id, gap_reference, None


def _chunk_ids_to_block_ids(chunk_ids: list[str], lookups: list[dict]) -> list[str]:
    block_ids = []
    seen = set()
    for chunk_id in chunk_ids or []:
        if not chunk_id:
            continue
        for lookup in lookups:
            record = lookup.get(chunk_id) if isinstance(lookup, dict) else None
            if not isinstance(record, dict):
                continue
            block_id = str(record.get("block_id") or "").strip()
            if block_id and block_id not in seen:
                seen.add(block_id)
                block_ids.append(block_id)
    return block_ids


def _sanitize_results_payload(results_payload: list[dict], gaps: list[dict]) -> list[dict]:
    if not isinstance(results_payload, list):
        return []

    valid_ids = {
        str((gap or {}).get("gap_id") or "").strip()
        for gap in gaps or []
        if isinstance(gap, dict)
    }
    valid_refs = {
        str((gap or {}).get("reference") or (gap or {}).get("regulation_reference") or "").strip()
        for gap in gaps or []
        if isinstance(gap, dict)
    }

    if not valid_ids and not valid_refs:
        return []

    cleaned = []
    for entry in results_payload:
        if not isinstance(entry, dict):
            continue
        impacts = entry.get("impacts") if isinstance(entry.get("impacts"), list) else []
        actions = entry.get("actions") if isinstance(entry.get("actions"), list) else []

        filtered_impacts = []
        for impact in impacts:
            if not isinstance(impact, dict):
                continue
            gap_id = str(impact.get("gap_id") or "").strip()
            gap_ref = str(impact.get("gap_reference") or impact.get("reference") or "").strip()
            if (gap_id and gap_id in valid_ids) or (gap_ref and gap_ref in valid_refs):
                filtered_impacts.append(impact)

        filtered_actions = []
        for action in actions:
            if not isinstance(action, dict):
                continue
            gap_id = str(action.get("gap_id") or "").strip()
            gap_ref = str(action.get("gap_reference") or action.get("reference") or "").strip()
            if (gap_id and gap_id in valid_ids) or (gap_ref and gap_ref in valid_refs):
                filtered_actions.append(action)

        cleaned.append(
            {
                "change": entry.get("change") if isinstance(entry.get("change"), dict) else {},
                "impacts": filtered_impacts,
                "actions": filtered_actions,
            }
        )

    return cleaned


def _select_structured_by_gap_refs(items: list[dict], refs: set[str], ids: set[str]) -> list[dict]:
    selected = []
    seen = set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        gap_id = str(item.get("gap_id") or "").strip()
        gap_ref = str(item.get("gap_reference") or item.get("reference") or "").strip()
        if refs and gap_ref not in refs and gap_id not in refs:
            continue
        if ids and gap_id not in ids and gap_ref not in ids:
            continue
        key = json.dumps(item, sort_keys=True, ensure_ascii=True)
        if key in seen:
            continue
        seen.add(key)
        selected.append(item)
    return selected


def _build_results_from_structured(
    results_payload: list[dict],
    gaps: list[dict],
    structured_impacts: list[dict],
    structured_actions: list[dict],
) -> list[dict]:
    if not isinstance(results_payload, list):
        return []

    valid_ids = {
        str((gap or {}).get("gap_id") or "").strip()
        for gap in gaps or []
        if isinstance(gap, dict)
    }
    valid_refs = {
        str((gap or {}).get("reference") or (gap or {}).get("regulation_reference") or "").strip()
        for gap in gaps or []
        if isinstance(gap, dict)
    }

    rebuilt = []
    for entry in results_payload:
        if not isinstance(entry, dict):
            continue
        change = entry.get("change") if isinstance(entry.get("change"), dict) else None
        if not isinstance(change, dict) or not _is_real_extra_policy_rule(change):
            continue

        refs = set()
        ids = set()
        for impact in entry.get("impacts") if isinstance(entry.get("impacts"), list) else []:
            if not isinstance(impact, dict):
                continue
            gap_ref = str(impact.get("gap_reference") or impact.get("reference") or "").strip()
            gap_id = str(impact.get("gap_id") or "").strip()
            if gap_ref:
                refs.add(gap_ref)
            if gap_id:
                ids.add(gap_id)

        for action in entry.get("actions") if isinstance(entry.get("actions"), list) else []:
            if not isinstance(action, dict):
                continue
            gap_ref = str(action.get("gap_reference") or action.get("reference") or "").strip()
            gap_id = str(action.get("gap_id") or "").strip()
            if gap_ref:
                refs.add(gap_ref)
            if gap_id:
                ids.add(gap_id)

        refs = {value for value in refs if value in valid_refs or value in valid_ids}
        ids = {value for value in ids if value in valid_ids or value in valid_refs}
        if not refs and not ids:
            refs = set(valid_refs)
            ids = set(valid_ids)

        rebuilt.append(
            {
                "change": change,
                "impacts": _select_structured_by_gap_refs(structured_impacts, refs, ids),
                "actions": _select_structured_by_gap_refs(structured_actions, refs, ids),
            }
        )

    return rebuilt


def _select_best_impact_for_gap(gap: dict, impacts: list[dict]) -> dict | None:
    if not isinstance(gap, dict):
        return None

    gap_reference = str(gap.get("reference") or "").strip().lower()
    if gap_reference:
        for item in impacts or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("gap_reference") or "").strip().lower() == gap_reference:
                return item

    gap_text = str(gap.get("gap") or gap.get("title") or gap.get("description") or "")
    gap_tokens = _tokenize(gap_text)
    best_item = None
    best_score = -1
    for item in impacts or []:
        if not isinstance(item, dict):
            continue
        item_text = f"{item.get('impact') or ''} {item.get('description') or ''} {item.get('reason') or ''}"
        score = len(gap_tokens & _tokenize(item_text))
        if score > best_score:
            best_score = score
            best_item = item
    return best_item


def _select_best_action_for_gap(gap: dict, actions: list[dict]) -> dict | None:
    if not isinstance(gap, dict):
        return None

    gap_reference = str(gap.get("reference") or "").strip().lower()
    if gap_reference:
        for item in actions or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("gap_reference") or "").strip().lower() == gap_reference:
                return item

    gap_text = str(gap.get("gap") or gap.get("title") or gap.get("description") or "")
    gap_tokens = _tokenize(gap_text)
    best_item = None
    best_score = -1
    for item in actions or []:
        if not isinstance(item, dict):
            continue
        item_text = f"{item.get('action') or ''} {item.get('title') or ''} {item.get('description') or ''}"
        score = len(gap_tokens & _tokenize(item_text))
        if score > best_score:
            best_score = score
            best_item = item
    return best_item


def _build_fallback_impact(gap: dict) -> dict:
    gap_text = _clean_text(gap.get("gap") or gap.get("title") or gap.get("description"), "Compliance gap identified")
    reason = _clean_text(
        gap.get("description") or gap.get("regulation_evidence") or gap.get("regulation_requirement"),
        f"Non-alignment detected for: {gap_text}",
    )
    risk = _clean_text(gap.get("severity") or gap.get("risk_level") or gap.get("risk"), "Medium").title()
    return {
        "department": "Compliance",
        "risk_level": risk,
        "reason": reason,
    }


def _build_fallback_action(gap: dict) -> str:
    gap_text = _clean_text(gap.get("gap") or gap.get("title") or gap.get("description"), "Compliance gap identified")
    return f"Update policy controls and procedures to fully address: {gap_text}."


def _build_strict_changes(changes: list[dict]) -> list[dict]:
    result = []
    seen = set()
    for item in changes or []:
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get("title"), "Regulatory change")
        description = _clean_text(item.get("description") or item.get("summary"), "Regulatory change identified")
        key = _semantic_key(f"{title} {description}")
        if not key or key in seen:
            continue
        seen.add(key)
        result.append({"title": title, "description": description})
        if len(result) >= 10:
            break
    return result


def _build_strict_gaps(gaps: list[dict], impacts: list[dict], actions: list[dict]) -> list[dict]:
    strict = []
    seen = set()

    for gap in gaps or []:
        if not isinstance(gap, dict):
            continue
        gap_text = _clean_text(gap.get("gap") or gap.get("title") or gap.get("description"), "Compliance gap identified")
        semantic = _semantic_key(gap_text)
        if not semantic or semantic in seen:
            continue
        seen.add(semantic)

        selected_impact = _select_best_impact_for_gap(gap, impacts)
        selected_action = _select_best_action_for_gap(gap, actions)

        if not isinstance(selected_impact, dict):
            selected_impact = _build_fallback_impact(gap)
        if not isinstance(selected_action, dict):
            selected_action = {"action": _build_fallback_action(gap)}

        impact_reason = _clean_text(
            selected_impact.get("reason") or selected_impact.get("description") or selected_impact.get("impact"),
            _build_fallback_impact(gap).get("reason"),
        )
        action_text = _clean_text(
            selected_action.get("action") or selected_action.get("description") or selected_action.get("title"),
            _build_fallback_action(gap),
        )

        impact_obj = {
            "department": _clean_text(selected_impact.get("department"), "Compliance"),
            "risk_level": _clean_text(selected_impact.get("risk_level") or selected_impact.get("severity"), "Medium").title(),
            "reason": impact_reason,
        }

        strict.append(
            {
                "gap": gap_text,
                "impact": impact_obj,
                "action": action_text,
            }
        )

        if len(strict) >= 10:
            break

    return strict


def _normalize_change_type(change_type: str) -> str:
    normalized = str(change_type or "").strip().lower()
    if normalized in {"added", "missing_requirement"}:
        return "added"
    if normalized in {"removed", "extra_policy_rule"}:
        return "removed"
    return "modified"


def _is_real_extra_policy_rule(change: dict) -> bool:
    if not isinstance(change, dict):
        return False
    change_type = str(change.get("type") or "").strip().lower()
    if change_type != "extra_policy_rule":
        return True
    field = str(change.get("field") or "").strip()
    evidence = str(change.get("evidence") or "").strip()
    old_value = str(change.get("old") or "").strip()
    return len(field.split()) >= 2 and len(evidence.split()) >= 6 and len(old_value) >= 6


def _build_change_summary(change: dict) -> str:
    old_value = str(change.get("old") or "").strip()
    new_value = str(change.get("new") or "").strip()
    evidence = str(change.get("evidence") or "").strip()
    field = str(change.get("field") or "Regulatory requirement").strip()
    if old_value and new_value:
        return _clean_text(f"{field} updated from '{old_value}' to '{new_value}'.", "Regulatory requirement updated.")
    if new_value and not old_value:
        return _clean_text(f"New requirement introduced for {field}: '{new_value}'.", "New regulatory requirement introduced.")
    if old_value and not new_value:
        return _clean_text(f"Policy-only rule removed for {field}: '{old_value}'.", "Policy-only rule removed.")
    return _clean_text(evidence, f"Requirement change identified for {field}.")


def _to_structured_changes(changes: list[dict]) -> list[dict]:
    mapped = []
    for change in changes or []:
        if not isinstance(change, dict):
            continue
        if not _is_real_extra_policy_rule(change):
            continue
        title = _clean_text(change.get("field"), "Regulatory requirement updated")
        mapped.append(
            {
                "title": title,
                "description": _build_change_summary(change),
                "type": _normalize_change_type(change.get("type")),
                "summary": _build_change_summary(change),
                "source": _clean_text(change.get("source"), "RBI/POLICY"),
                "source_blocks": change.get("source_blocks") if isinstance(change.get("source_blocks"), list) else [],
                "source_chunks": change.get("source_chunks") if isinstance(change.get("source_chunks"), list) else [],
            }
        )

    deduped = _dedupe_items(
        mapped,
        lambda item: (
            str(item.get("type") or "").lower(),
            str(item.get("title") or "").lower(),
            str(item.get("summary") or "").lower(),
        ),
    )
    return deduped


def _to_structured_impacts(impacts: list[dict], gaps: list[dict]) -> list[dict]:
    mapped = []
    emitted_gap_keys = set()
    for impact in impacts or []:
        if not isinstance(impact, dict):
            continue

        departments = impact.get("impacted_departments") if isinstance(impact.get("impacted_departments"), list) else []
        reason = _clean_text(impact.get("description") or impact.get("reason"), "Regulatory change requires operational control updates.")
        severity = _normalize_level(impact.get("severity") or impact.get("impact_level"), default="Medium")
        risk_level = _clean_text(impact.get("risk_level") or severity.lower(), "medium").lower()
        provided_gap_id = _clean_text(impact.get("gap_id"), "")
        provided_gap_reference = _clean_text(impact.get("gap_reference") or impact.get("reference"), "")
        impact_text = _clean_text(impact.get("impact") or reason, reason)
        resolved_gap_id, resolved_gap_reference, matched_gap = _resolve_gap_link(
            provided_gap_id,
            provided_gap_reference,
            f"{impact_text} {reason}",
            gaps,
        )
        gap_key = str(resolved_gap_reference or resolved_gap_id or "").strip().lower()
        if gap_key and gap_key in emitted_gap_keys:
            continue
        if _is_placeholder_reference(resolved_gap_id) and _is_placeholder_reference(resolved_gap_reference):
            continue

        source = _clean_text(impact.get("source"), "")
        if _is_placeholder_reference(source):
            source = ""
        if not source and isinstance(matched_gap, dict):
            source = _clean_text(matched_gap.get("source") or matched_gap.get("regulation_reference"), "")
        if not source:
            source = "Not specified in provided documents"

        if not departments and str(impact.get("department") or "").strip():
            departments = [str(impact.get("department") or "").strip()]

        for department in departments:
            label = _clean_text(department, "Compliance")
            mapped.append(
                {
                    "gap_id": _clean_text(resolved_gap_id, resolved_gap_reference),
                    "gap_reference": _clean_text(resolved_gap_reference, resolved_gap_id),
                    "impact": impact_text,
                    "risk_level": risk_level,
                    "department": label,
                    "severity": severity,
                    "reason": reason,
                    "description": reason,
                    "source": source,
                    "based_on_blocks": impact.get("based_on_blocks") if isinstance(impact.get("based_on_blocks"), list) else [],
                    "source_chunks": impact.get("source_chunks") if isinstance(impact.get("source_chunks"), list) else [],
                }
            )
            if gap_key:
                emitted_gap_keys.add(gap_key)
            break

    deduped = _dedupe_items(
        mapped,
        lambda item: (
            str(item.get("gap_reference") or "").lower(),
            str(item.get("department") or "").lower(),
            str(item.get("severity") or "").lower(),
            str(item.get("reason") or "").lower(),
        ),
    )
    return deduped[:10]


def _to_structured_gaps(gaps: list[dict]) -> list[dict]:
    mapped = []
    for gap in gaps or []:
        if not isinstance(gap, dict):
            continue
        title = _clean_text(gap.get("issue") or gap.get("gap") or gap.get("title"), "Compliance gap identified")
        severity = _normalize_level(gap.get("severity") or gap.get("risk") or gap.get("risk_level"), default="Medium")
        regulation_requirement = _clean_text(gap.get("regulation_requirement"), "Regulatory requirement is not fully covered.")
        policy_state = _clean_text(gap.get("policy_current_state"), "Current policy coverage is incomplete.")
        description = _clean_text(gap.get("description") or gap.get("reason"), f"{regulation_requirement} Current policy state: {policy_state}")
        recommendation = _clean_text(
            gap.get("recommendation"),
            f"Update policy controls to align with: {regulation_requirement}",
        )
        gap_text = _clean_text(gap.get("gap") or gap.get("title") or gap.get("issue"), title)
        reference = _clean_text(gap.get("reference") or gap.get("source") or gap.get("regulation_requirement"), "Not specified in provided documents")
        source = _clean_text(
            gap.get("source") or gap.get("regulation_requirement"),
            "Not specified in provided documents",
        )
        mapped.append(
            {
                "gap_id": _clean_text(gap.get("gap_id"), reference),
                "gap": gap_text,
                "reference": reference,
                "regulation_reference": _clean_text(gap.get("regulation_reference"), reference),
                "title": title,
                "severity": severity.lower(),
                "description": description,
                "recommendation": recommendation,
                "source": source,
                "policy_blocks": gap.get("policy_blocks") if isinstance(gap.get("policy_blocks"), list) else [],
                "regulation_blocks": gap.get("regulation_blocks") if isinstance(gap.get("regulation_blocks"), list) else [],
                "source_blocks": gap.get("source_blocks") if isinstance(gap.get("source_blocks"), list) else [],
                "policy_evidence": _clean_text(gap.get("policy_evidence"), policy_state),
                "regulation_evidence": _clean_text(gap.get("regulation_evidence"), regulation_requirement),
                "source_chunks": gap.get("source_chunks") if isinstance(gap.get("source_chunks"), list) else [],
            }
        )

    deduped = _dedupe_items(
        mapped,
        lambda item: (
            str(item.get("reference") or "").lower(),
            str(item.get("title") or "").lower(),
            str(item.get("severity") or "").lower(),
            str(item.get("description") or "").lower(),
        ),
    )
    return deduped[:10]


def _to_structured_actions(actions: list[dict], gaps: list[dict]) -> list[dict]:
    mapped = []
    for action in actions or []:
        if not isinstance(action, dict):
            continue
        title = _clean_text(action.get("title") or action.get("action") or action.get("step"), "Compliance action required")
        action_text = _clean_text(action.get("action") or action.get("title") or action.get("step"), title)
        description = _clean_text(
            action.get("description") or action.get("summary"),
            f"Execute control update for: {title}",
        )
        department = _clean_text(action.get("department") or action.get("owner"), "Compliance")
        priority = _normalize_level(action.get("priority"), default="Medium")
        provided_gap_id = _clean_text(action.get("gap_id"), "")
        provided_gap_reference = _clean_text(action.get("gap_reference") or action.get("reference"), "")
        resolved_gap_id, resolved_gap_reference, matched_gap = _resolve_gap_link(
            provided_gap_id,
            provided_gap_reference,
            f"{action_text} {description}",
            gaps,
        )
        if _is_placeholder_reference(resolved_gap_id) and _is_placeholder_reference(resolved_gap_reference):
            continue
        mapped.append(
            {
                "gap_id": _clean_text(resolved_gap_id, resolved_gap_reference),
                "gap_reference": _clean_text(resolved_gap_reference, resolved_gap_id),
                "action": action_text,
                "title": title,
                "description": description,
                "department": department,
                "priority": priority.lower(),
                "status": _clean_text(action.get("status"), "Pending"),
                "deadline": _clean_text(action.get("deadline") or action.get("timeline"), "Current compliance cycle"),
                "based_on_blocks": action.get("based_on_blocks") if isinstance(action.get("based_on_blocks"), list) else [],
                "source_chunks": action.get("source_chunks") if isinstance(action.get("source_chunks"), list) else [],
                "source": _clean_text(action.get("source") or (matched_gap or {}).get("source"), "Not specified in provided documents"),
            }
        )

    aligned = _align_actions_to_gaps(mapped, gaps)
    deduped = _dedupe_items(
        aligned,
        lambda item: (
            str(item.get("gap_reference") or "").lower(),
            str(item.get("title") or "").lower(),
            str(item.get("department") or "").lower(),
        ),
    )
    return deduped[:10]


def _compute_department_risk_from_impacts(impacts: list[dict]) -> list[dict]:
    counts = {}
    for impact in impacts or []:
        if not isinstance(impact, dict):
            continue
        department = str(impact.get("department") or "").strip()
        if not department:
            continue
        counts[department] = counts.get(department, 0) + 1

    total = sum(counts.values())
    if total <= 0:
        return []

    result = []
    allocated = 0
    items = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    for index, (department, count) in enumerate(items):
        if index == len(items) - 1:
            percent = 100 - allocated
        else:
            percent = int(round((count / total) * 100))
            allocated += percent
        result.append({"department": department, "risk_percent": max(0, min(100, percent))})

    result.sort(key=lambda item: item.get("risk_percent", 0), reverse=True)
    return result


def _build_department_risk(results_payload: list[dict]) -> list[dict]:
    if not isinstance(results_payload, list) or not results_payload:
        return []

    total_changes = len([item for item in results_payload if isinstance(item, dict) and isinstance(item.get("change"), dict)])
    if total_changes <= 0:
        return []

    department_change_counts: dict[str, int] = {}
    for result in results_payload:
        if not isinstance(result, dict):
            continue
        impacts = result.get("impacts") if isinstance(result.get("impacts"), list) else []
        departments = set()
        for impact in impacts:
            if not isinstance(impact, dict):
                continue
            department = str(impact.get("department") or "").strip()
            if department:
                departments.add(department)
        for department in departments:
            department_change_counts[department] = department_change_counts.get(department, 0) + 1

    result = [
        {
            "department": department,
            "risk_percent": int(round((count / total_changes) * 100)),
        }
        for department, count in department_change_counts.items()
    ]
    result.sort(key=lambda item: item.get("risk_percent", 0), reverse=True)
    return result


def _merge_section_payloads(section_name: str, *payloads) -> list[dict]:
    merged = []
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        items = payload.get(section_name)
        if isinstance(items, list):
            merged.extend([item for item in items if isinstance(item, dict)])
    return deduplicate_items(merged)


def build_impacts(gaps: list[dict]) -> list[dict]:
    impacts = []
    for gap in gaps or []:
        if not isinstance(gap, dict):
            continue
        impact_obj = gap.get("impact") if isinstance(gap.get("impact"), dict) else None
        if impact_obj is None:
            impact_obj = _build_fallback_impact(gap)
        impacts.append(
            {
                "gap_id": str(gap.get("gap_id") or gap.get("reference") or "").strip(),
                "gap_reference": str(gap.get("reference") or gap.get("regulation_reference") or gap.get("gap_id") or "").strip(),
                "department": str((impact_obj or {}).get("department") or "Compliance").strip(),
                "risk_level": str((impact_obj or {}).get("risk_level") or (impact_obj or {}).get("severity") or "medium").strip().lower(),
                "severity": str((impact_obj or {}).get("risk_level") or (impact_obj or {}).get("severity") or "medium").strip().title(),
                "description": str((impact_obj or {}).get("reason") or (impact_obj or {}).get("description") or gap.get("description") or "").strip(),
                "reason": str((impact_obj or {}).get("reason") or (impact_obj or {}).get("description") or gap.get("description") or "").strip(),
                "impact": str((impact_obj or {}).get("reason") or (impact_obj or {}).get("description") or gap.get("description") or "").strip(),
                "source": str(gap.get("source") or gap.get("regulation_reference") or "Not specified in provided documents").strip(),
                "based_on_blocks": gap.get("source_blocks") if isinstance(gap.get("source_blocks"), list) else [],
                "source_chunks": gap.get("source_chunks") if isinstance(gap.get("source_chunks"), list) else [],
            }
        )
    return deduplicate_items([item for item in impacts if isinstance(item, dict)])


async def _run_analysis_pipeline(
    mode: str,
    old_context: str,
    new_context: str,
    policy_context: str,
    old_blocks: list[dict],
    new_blocks: list[dict],
    policy_blocks: list[dict],
):
    """
    Dependency-safe flow: changes -> compliance_gaps -> impacts -> actions
    Stage internals remain batched/parallel in ai_service.
    """
    logger.warning(
        "[FLOW] pipeline_start mode=%s old_blocks=%s new_blocks=%s policy_blocks=%s",
        mode,
        len(old_blocks or []),
        len(new_blocks or []),
        len(policy_blocks or []),
    )
    if not old_context or not new_context or not policy_context:
        raise ValueError("Missing input data")

    analysis_payload = await asyncio.to_thread(run_full_analysis, old_context, new_context, policy_context)
    if not isinstance(analysis_payload, dict):
        raise RuntimeError("LLM pipeline failed")

    detected_changes = await asyncio.to_thread(detect_changes, old_blocks, new_blocks)
    merged_changes = _merge_section_payloads("changes", detected_changes, analysis_payload)

    detected_gaps = await asyncio.to_thread(detect_compliance_gaps, new_context, policy_context, merged_changes)
    merged_gaps = _merge_section_payloads("compliance_gaps", detected_gaps, analysis_payload)

    logger.info(
        "[FLOW] pipeline_ai_counts changes=%s compliance_gaps=%s impacts=%s actions=%s",
        len(merged_changes),
        len(merged_gaps),
        len(analysis_payload.get("impacts") if isinstance(analysis_payload.get("impacts"), list) else []),
        len(analysis_payload.get("actions") if isinstance(analysis_payload.get("actions"), list) else []),
    )

    return (
        {"changes": merged_changes},
        {"compliance_gaps": merged_gaps},
        analysis_payload,
        analysis_payload,
        analysis_payload.get("results") if isinstance(analysis_payload.get("results"), list) else [],
    )


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
        blocks = extract_semantic_blocks(markdown_text)
        if blocks:
            print("Using semantic blocks:", len(blocks))
            return [
                (block.get("content") or "").strip()
                for block in blocks
                if (block.get("content") or "").strip()
            ]
    except Exception as exc:
        logger.warning("Semantic block extraction failed, falling back to paragraph split: %s", exc)

    # Semantic-only fallback: paragraph grouping, no clause-system fallback.
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", markdown_text or "") if part and part.strip()]
    return paragraphs


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
                "gap_id": "",
                "gap_reference": "",
                "source": "",
                "impact": "Impact identified from regulatory changes and policy gaps",
                "reason": "Impact identified from regulatory changes and policy gaps",
                "risk_level": "medium",
                "based_on_blocks": [],
                "source_chunks": [],
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
            "gap_id": str(item.get("gap_id") or "").strip(),
            "gap_reference": str(item.get("gap_reference") or item.get("reference") or "").strip(),
            "impact": str(item.get("impact") or item.get("description") or item.get("summary") or "").strip(),
            "reason": str(item.get("reason") or item.get("description") or item.get("summary") or "").strip(),
            "risk_level": str(item.get("risk_level") or "").strip(),
            "source": str(item.get("source") or item.get("evidence") or "").strip(),
            "based_on_blocks": item.get("based_on_blocks") if isinstance(item.get("based_on_blocks"), list) else [],
            "source_chunks": item.get("source_chunks") if isinstance(item.get("source_chunks"), list) else [],
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

        # ✅ SAFE EXTRACTION WITH VALIDATION
        try:
            policy_source_chunks = []
            old_source_chunks = []
            new_source_chunks = []
            per_pdf_block_map = {}

            policy_files = _as_file_list(file_paths.get("policy"))
            old_files = _as_file_list(file_paths.get("old"))
            new_files = _as_file_list(file_paths.get("new"))

            old_file = os.path.basename(old_files[0]) if old_files else "N/A"
            new_file = os.path.basename(new_files[0]) if new_files else "N/A"
            policy_file = os.path.basename(policy_files[0]) if policy_files else "N/A"
            print("==============================")
            print("🔍 Comparing:")
            print(f"OLD: {old_file}")
            print(f"NEW: {new_file}")
            print(f"POLICY: {policy_file}")

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
                    per_pdf_block_map[os.path.basename(policy_file)] = file_chunks
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
                    per_pdf_block_map[os.path.basename(old_file)] = file_chunks
                    logger.info(f"📦 Old regulation PDF: Created {len(file_chunks)} chunks")
                    store_chunks(file_chunks, "old_regulation", old_file)

                old_sources = retrieve_with_metadata("key regulatory semantic blocks", "old_regulation", k=5)
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
                    per_pdf_block_map[os.path.basename(new_file)] = file_chunks
                    logger.info(f"📦 New regulation PDF: Created {len(file_chunks)} chunks")
                    store_chunks(file_chunks, "new_regulation", new_file)

                new_sources = retrieve_with_metadata("latest regulatory changes", "new_regulation", k=5)
                if not new_sources:
                    raise ValueError("New regulation PDF chunks could not be indexed or retrieved")
                new_sources, new_context = optimize_context_chunks(new_sources, max_chunks=5, compress=True)

            print(f"📄 {old_file} -> Blocks: {len([item for item in old_source_chunks if isinstance(item, dict)])}")
            print(f"📄 {new_file} -> Blocks: {len([item for item in new_source_chunks if isinstance(item, dict)])}")
            print(f"📄 {policy_file} -> Blocks: {len([item for item in policy_source_chunks if isinstance(item, dict)])}")
            print("==============================")
        
        except Exception as e:
            return _handle_extraction_error(task_id, e)

        # ✅ VALIDATE THAT WE HAVE CONTENT TO PROCESS
        total_context = len((old_context + new_context + policy_context).replace(" ", "").replace("\n", ""))
        print("OLD:", len(old_context or ""))
        print("NEW:", len(new_context or ""))
        print("POLICY:", len(policy_context or ""))
        if not old_context or not new_context or not policy_context:
            raise ValueError("One or more documents are empty after extraction")
        docs_identical = _normalize_change_text(old_context) == _normalize_change_text(new_context)
        if docs_identical:
            logger.warning("OLD and NEW regulation documents are identical after normalization")
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

        changes_payload, compliance_gaps_payload, impacts_payload, actions_payload, results_payload = asyncio.run(
            _run_analysis_pipeline(
                mode=mode,
                old_context=old_context,
                new_context=new_context,
                policy_context=policy_context,
                old_blocks=[
                    {
                        "block_id": str(item.get("block_id") or item.get("chunk_id") or ""),
                        "heading": str(item.get("title") or "").strip(),
                        "content": str(item.get("text") or "").strip(),
                    }
                    for item in old_source_chunks
                    if isinstance(item, dict) and str(item.get("text") or "").strip()
                ],
                new_blocks=[
                    {
                        "block_id": str(item.get("block_id") or item.get("chunk_id") or ""),
                        "heading": str(item.get("title") or "").strip(),
                        "content": str(item.get("text") or "").strip(),
                    }
                    for item in new_source_chunks
                    if isinstance(item, dict) and str(item.get("text") or "").strip()
                ],
                policy_blocks=[
                    {
                        "block_id": str(item.get("block_id") or item.get("chunk_id") or ""),
                        "heading": str(item.get("title") or "").strip(),
                        "content": str(item.get("text") or "").strip(),
                    }
                    for item in policy_source_chunks
                    if isinstance(item, dict) and str(item.get("text") or "").strip()
                ],
            )
        )

        changes_items_raw = _extract_changes(changes_payload)
        changes_items_raw = _dedupe_changes_by_field_new(changes_items_raw)
        gaps_items_raw = _extract_gaps(compliance_gaps_payload)
        gaps_items_raw = sorted(gaps_items_raw, key=lambda item: _risk_priority((item or {}).get("risk") or (item or {}).get("risk_level")), reverse=True)
        gaps_items_raw = deduplicate_items(gaps_items_raw)
        impacts_items_raw = deduplicate_items(_normalize_impact(impacts_payload))
        actions_items_raw = deduplicate_items(_normalize_actions(actions_payload))

        print("CHANGES RAW:", changes_items_raw)
        print("GAPS RAW:", gaps_items_raw)
        print("ACTIONS RAW:", actions_items_raw)

        logger.info(
            "[FLOW] ai_raw_counts changes=%s compliance_gaps=%s impacts=%s actions=%s",
            len(changes_items_raw),
            len(gaps_items_raw),
            len(impacts_items_raw),
            len(actions_items_raw),
        )

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

        changes_items_raw = _attach_source_chunks(changes_items_raw, change_candidates, ["field", "new", "evidence"], max_sources=2)
        gaps_items_raw = _attach_source_chunks(gaps_items_raw, gap_candidates, ["issue", "regulation_requirement", "policy_current_state"], max_sources=2)

        if gaps_items_raw and not impacts_items_raw:
            impacts_items_raw = build_impacts(gaps_items_raw)

        actions_items_raw = _align_actions_to_gaps(actions_items_raw, gaps_items_raw)

        gap_source_ids = _collect_source_chunks_from_items(gaps_items_raw)
        gap_candidate_lookup = {chunk_id: record for chunk_id, record in {**old_lookup, **new_lookup, **policy_lookup}.items()}
        gap_source_candidates = [gap_candidate_lookup[chunk_id] for chunk_id in gap_source_ids if chunk_id in gap_candidate_lookup]

        action_source_candidates = gap_source_candidates or gap_candidates
        for impact_item in impacts_items_raw:
            if isinstance(impact_item, dict):
                impact_item["source_chunks"] = _pick_source_chunks(
                    f"{impact_item.get('title') or ''} {impact_item.get('description') or ''}",
                    gap_source_candidates or gap_candidates,
                    max_sources=3,
                )

        for action in actions_items_raw:
            if isinstance(action, dict):
                action["source_chunks"] = _pick_source_chunks(
                    f"{action.get('action') or ''} {action.get('owner') or ''}",
                    action_source_candidates,
                    max_sources=2,
                )

        changes_items = _to_structured_changes(changes_items_raw)
        gaps_items = _to_structured_gaps(gaps_items_raw)
        impacts_items = _to_structured_impacts(impacts_items_raw, gaps_items)
        actions_items = _to_structured_actions(actions_items_raw, gaps_items)

        if not docs_identical and len(changes_items) == 0:
            changes_items = [
                {
                    "title": "Regulation Updated",
                    "description": "Differences detected but parsing failed",
                    "type": "modified",
                    "summary": "Differences detected but parsing failed",
                    "source": "RBI/POLICY",
                    "source_blocks": [],
                    "source_chunks": [],
                }
            ]

        if not docs_identical and len(gaps_items) == 0:
            gaps_items = [
                {
                    "gap_id": "GAP-FALLBACK-001",
                    "gap": "Detected regulatory differences require policy review",
                    "reference": "Not specified in provided documents",
                    "regulation_reference": "Not specified in provided documents",
                    "title": "Policy alignment review required",
                    "severity": "medium",
                    "description": "Differences were detected between OLD and NEW regulations, but detailed mapping was incomplete.",
                    "recommendation": "Review policy controls and align with updated regulation.",
                    "source": "Not specified in provided documents",
                    "policy_blocks": [],
                    "regulation_blocks": [],
                    "source_blocks": [],
                    "policy_evidence": "Not specified in provided documents",
                    "regulation_evidence": "Not specified in provided documents",
                    "source_chunks": [],
                }
            ]

        if len(impacts_items) == 0 and len(gaps_items) > 0:
            impacts_items = _to_structured_impacts(build_impacts(gaps_items), gaps_items)

        if len(actions_items) == 0 and len(gaps_items) > 0:
            actions_items = _to_structured_actions([], gaps_items)

        lookup_list = [old_lookup, new_lookup, policy_lookup]
        for gap in gaps_items:
            if not isinstance(gap, dict):
                continue
            if not isinstance(gap.get("source_blocks"), list) or not gap.get("source_blocks"):
                gap["source_blocks"] = _chunk_ids_to_block_ids(gap.get("source_chunks") or [], lookup_list)

        for impact in impacts_items:
            if not isinstance(impact, dict):
                continue
            if not isinstance(impact.get("based_on_blocks"), list) or not impact.get("based_on_blocks"):
                impact["based_on_blocks"] = _chunk_ids_to_block_ids(impact.get("source_chunks") or [], lookup_list)

        for action in actions_items:
            if not isinstance(action, dict):
                continue
            if not isinstance(action.get("based_on_blocks"), list) or not action.get("based_on_blocks"):
                action["based_on_blocks"] = _chunk_ids_to_block_ids(action.get("source_chunks") or [], lookup_list)

        results_payload = _sanitize_results_payload(results_payload, gaps_items)
        results_payload = _build_results_from_structured(results_payload, gaps_items, impacts_items, actions_items)
        strict_changes = _build_strict_changes(changes_items)
        strict_gaps = _build_strict_gaps(gaps_items, impacts_items, actions_items)

        logger.info("dashboard_raw_payload=%s", json.dumps({
            "changes": changes_items_raw,
            "compliance_gaps": gaps_items_raw,
            "impacts": impacts_items_raw,
            "actions": actions_items_raw,
        }, ensure_ascii=True)[:2000])
        logger.info("dashboard_structured_payload=%s", json.dumps({
            "changes": changes_items,
            "compliance_gaps": gaps_items,
            "impacts": impacts_items,
            "actions": actions_items,
        }, ensure_ascii=True)[:2000])

        response = {
            "changes": strict_changes,
            "changes_detailed": changes_items,
            "compliance_gaps": gaps_items,
            "impacts": impacts_items,
            "actions": actions_items,
            "results": results_payload if isinstance(results_payload, list) else [],
            "department_risk": _compute_department_risk_from_impacts(impacts_items),
            "file_block_map": {
                file_name: [
                    {
                        "block_id": item.get("block_id") or item.get("clause_id"),
                        "title": item.get("title"),
                        "page_number": item.get("page_number"),
                        "text": item.get("text"),
                    }
                    for item in items
                ]
                for file_name, items in per_pdf_block_map.items()
            },
        }

        assert isinstance(response.get("changes"), list)
        assert isinstance(response.get("compliance_gaps"), list)
        assert isinstance(response.get("impacts"), list)
        assert isinstance(response.get("actions"), list)

        response["file_clause_map"] = response.get("file_block_map", {})
        print("FINAL JSON:", response)
        logger.info("dashboard_final_response=%s", json.dumps(response, ensure_ascii=True)[:2000])
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