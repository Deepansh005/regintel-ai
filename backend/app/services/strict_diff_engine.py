"""
Strict Legal Diff Engine

Deterministic comparison of regulatory blocks.
ONLY extracts explicit, factual differences.
NO interpretation, NO summarization, NO vague language.

Focus: numeric changes, conditions, obligations, additions, removals
"""

import json
import logging
import re
from typing import Dict, List, Tuple

from app.services.llm_router import call_groq_with_retry

logger = logging.getLogger(__name__)

MAX_BATCH_PAIRS = 5
MAX_BATCH_CALLS = 5

RULE_SPLIT_REGEX = re.compile(r"(?<=[.!?])\s+|\n+")
VALUE_PERCENT_REGEX = re.compile(r"\b\d+(?:\.\d+)?\s*%\b", re.IGNORECASE)
VALUE_TIMELINE_REGEX = re.compile(r"\b\d+\s*(?:day|days|month|months|year|years)\b", re.IGNORECASE)
VALUE_NUMBER_REGEX = re.compile(r"\b\d+(?:\.\d+)?\b")

RULE_FIELD_PATTERNS = [
    ("Dividend payout cap", [r"dividend", r"payout|distribution", r"cap|limit|not exceed|up to|maximum"]),
    ("CET1 ratio eligibility", [r"cet1|common equity tier\s*1", r"eligib|minimum|threshold|bucket"]),
    ("STR reporting timeline", [r"str|suspicious transaction report", r"report|timeline|submit|file", r"day|days|month|months"]),
    ("Reporting requirement", [r"report|reporting|return filing|disclosure", r"shall|must|required|within"]),
    ("Eligibility condition", [r"eligib|qualif|criteria|condition", r"shall|must|required|subject to"]),
    ("Restriction or prohibition", [r"prohibit|not allowed|shall not|must not|restricted|restriction"]),
    ("Formula requirement", [r"pat|profit after tax|cet1|capital adequacy|formula|ratio"]),
]


def _estimate_tokens(text: str) -> int:
    """Rough token estimation."""
    return len(text.split())


def _truncate_text(text: str, max_tokens: int = 500) -> str:
    """Truncate text to approximate token length."""
    words = text.split()
    if len(words) <= max_tokens:
        return text
    return " ".join(words[:max_tokens]) + "..."


def _parse_diff_response(content: str) -> Dict | None:
    """
    Parse LLM response expecting JSON structure:
    {
      "changes": [
        {
          "type": "added|removed|modified",
          "statement": "exact factual difference",
          "old_text": "...",
          "new_text": "..."
        }
      ]
    }
    """
    
    if not content or not isinstance(content, str):
        return None
    
    content = content.strip()
    
    # Try direct JSON parsing
    try:
        data = json.loads(content)
        if isinstance(data, dict) and "changes" in data:
            return data
    except json.JSONDecodeError:
        pass
    
    # Try extracting JSON from markdown fence
    fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", content, re.IGNORECASE)
    if fence_match:
        try:
            data = json.loads(fence_match.group(1))
            if isinstance(data, dict) and "changes" in data:
                return data
        except json.JSONDecodeError:
            pass
    
    # Try extracting bare JSON object
    brace_match = re.search(r"\{[\s\S]*\}", content)
    if brace_match:
        try:
            data = json.loads(brace_match.group(0))
            if isinstance(data, dict) and "changes" in data:
                return data
        except json.JSONDecodeError:
            pass
    
    return None


def _is_valid_change(change: Dict) -> bool:
    """Validate change entry."""
    
    if not isinstance(change, dict):
        return False
    
    # Must have type
    change_type = str(change.get("type", "")).strip().lower()
    if change_type not in {"added", "removed", "modified"}:
        return False
    
    # Must have statement
    statement = str(change.get("statement", "")).strip()
    if not statement or len(statement) < 10:
        return False
    
    # old_text and new_text should differ
    old_text = str(change.get("old_text", "")).strip()
    new_text = str(change.get("new_text", "")).strip()
    
    # For "modified", both should exist and differ
    if change_type == "modified":
        if not old_text or not new_text or old_text == new_text:
            return False
    
    # For "added", must have new_text
    if change_type == "added":
        if not new_text:
            return False
    
    # For "removed", must have old_text
    if change_type == "removed":
        if not old_text:
            return False
    
    return True


def _contains_vague_terms(text: str) -> bool:
    """Check if text contains vague regulatory language."""
    
    vague_terms = [
        "improve", "enhance", "develop", "various",
        "more", "less", "better", "worse",
        "somehow", "some of", "etc",
        "generally", "typically", "usually",
        "could", "might", "may"  # uncertain language
    ]
    
    text_lower = text.lower()
    return any(term in text_lower for term in vague_terms)


def _split_sentences(text: str) -> List[str]:
    return [part.strip() for part in RULE_SPLIT_REGEX.split(str(text or "")) if part and part.strip()]


def _normalize_value(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _extract_value(sentence: str) -> str:
    sentence_text = str(sentence or "")
    percent = VALUE_PERCENT_REGEX.search(sentence_text)
    if percent:
        return percent.group(0).strip()

    timeline = VALUE_TIMELINE_REGEX.search(sentence_text)
    if timeline:
        return timeline.group(0).strip()

    number = VALUE_NUMBER_REGEX.search(sentence_text)
    if number:
        return number.group(0).strip()

    if re.search(r"\bshall not\b|\bmust not\b|\bprohibited\b|\brestricted\b", sentence_text, re.IGNORECASE):
        return "prohibited"

    return sentence_text[:80].strip()


def _match_field(sentence: str) -> str | None:
    lowered = str(sentence or "").lower()
    for field_name, pattern_group in RULE_FIELD_PATTERNS:
        if all(re.search(pattern, lowered, re.IGNORECASE) for pattern in pattern_group):
            return field_name
    return None


def _extract_structured_rules(text: str, source_label: str) -> List[Dict]:
    rules = []
    seen = set()

    for sentence in _split_sentences(text):
        field = _match_field(sentence)
        if not field:
            continue

        value = _extract_value(sentence)
        key = (field.lower(), _normalize_value(value))
        if key in seen:
            continue
        seen.add(key)

        rules.append(
            {
                "field": field,
                "value": value,
                "evidence": sentence[:220].strip(),
                "source": source_label,
            }
        )

    return rules


def _compare_rules(policy_rules: List[Dict], rbi_rules: List[Dict]) -> List[Dict]:
    changes = []
    used_policy = set()

    for rbi_rule in rbi_rules:
        field = str(rbi_rule.get("field") or "").strip()
        rbi_value = str(rbi_rule.get("value") or "").strip()
        evidence = str(rbi_rule.get("evidence") or "").strip()

        policy_index = next(
            (
                index
                for index, policy_rule in enumerate(policy_rules)
                if index not in used_policy
                and str(policy_rule.get("field") or "").strip().lower() == field.lower()
            ),
            None,
        )

        if policy_index is None:
            changes.append(
                {
                    "type": "missing_requirement",
                    "field": field,
                    "old": None,
                    "new": rbi_value,
                    "evidence": evidence,
                    "source": "RBI",
                }
            )
            continue

        used_policy.add(policy_index)
        policy_value = str(policy_rules[policy_index].get("value") or "").strip()
        if _normalize_value(policy_value) != _normalize_value(rbi_value):
            changes.append(
                {
                    "type": "modified_requirement",
                    "field": field,
                    "old": policy_value,
                    "new": rbi_value,
                    "evidence": evidence,
                    "source": "RBI",
                }
            )

    for index, policy_rule in enumerate(policy_rules):
        if index in used_policy:
            continue
        changes.append(
            {
                "type": "extra_policy_rule",
                "field": str(policy_rule.get("field") or "").strip(),
                "old": str(policy_rule.get("value") or "").strip(),
                "new": None,
                "evidence": str(policy_rule.get("evidence") or "").strip(),
                "source": "POLICY",
            }
        )

    deduped = []
    seen_changes = set()
    for item in changes:
        key = (
            str(item.get("type") or "").lower(),
            str(item.get("field") or "").lower(),
            _normalize_value(str(item.get("old") or "")),
            _normalize_value(str(item.get("new") or "")),
        )
        if key in seen_changes:
            continue
        seen_changes.add(key)
        deduped.append(item)

    return deduped


def _chunk_list(items: List[Dict], size: int) -> List[List[Dict]]:
    if size <= 0:
        return [items]
    return [items[index:index + size] for index in range(0, len(items), size)]


def _build_batch_input(matched_pairs: List[Dict]) -> List[Dict]:
    batch_input = []
    for index, match in enumerate(matched_pairs, start=1):
        old_block = match.get("old_block") if isinstance(match.get("old_block"), dict) else {}
        new_block = match.get("new_block") if isinstance(match.get("new_block"), dict) else {}

        explicit_old = str(match.get("old") or "").strip()
        explicit_new = str(match.get("new") or "").strip()

        pair_id = str(match.get("pair_id") or "").strip() or str(
            new_block.get("block_id")
            or old_block.get("block_id")
            or f"pair-{index}"
        )
        batch_input.append(
            {
                "pair_id": pair_id,
                "old_heading": str(match.get("old_heading") or old_block.get("heading") or "").strip(),
                "new_heading": str(match.get("new_heading") or new_block.get("heading") or "").strip(),
                "old": _truncate_text(explicit_old or str(old_block.get("content") or "").strip(), 250),
                "new": _truncate_text(explicit_new or str(new_block.get("content") or "").strip(), 250),
            }
        )
    return batch_input


def _parse_batch_diff_response(content: str) -> List[Dict]:
    if not content or not isinstance(content, str):
        return []

    parsed = None
    try:
        parsed = json.loads(content)
    except Exception:
        parsed = _parse_diff_response(content)

    if not isinstance(parsed, dict):
        return []

    results = parsed.get("results")
    if not isinstance(results, list):
        return []

    normalized = []
    for result in results:
        if not isinstance(result, dict):
            continue
        pair_id = str(result.get("pair_id") or "").strip()
        changes = result.get("changes") if isinstance(result.get("changes"), list) else []

        for change in changes:
            if not _is_valid_change(change):
                continue

            statement = str(change.get("statement") or "").strip()
            if _contains_vague_terms(statement):
                continue

            normalized.append(
                {
                    "type": str(change.get("type") or "modified").strip().lower(),
                    "statement": statement,
                    "old_text": str(change.get("old_text") or "").strip(),
                    "new_text": str(change.get("new_text") or "").strip(),
                    "block_id": pair_id,
                }
            )

    return normalized


def compare_blocks_batch(matched_pairs: List[Dict], debug: bool = False) -> List[Dict]:
    if not matched_pairs:
        return []

    batch_input = _build_batch_input(matched_pairs)
    if not batch_input:
        return []

    parsed_changes: List[Dict] = []
    total_rbi_rules = 0
    total_policy_rules = 0
    rbi_rule_fields: List[str] = []
    policy_rule_fields: List[str] = []

    for pair in batch_input:
        policy_text = str(pair.get("old") or "").strip()
        rbi_text = str(pair.get("new") or "").strip()
        pair_id = str(pair.get("pair_id") or "").strip()

        policy_rules = _extract_structured_rules(policy_text, source_label="POLICY")
        rbi_rules = _extract_structured_rules(rbi_text, source_label="RBI")
        total_policy_rules += len(policy_rules)
        total_rbi_rules += len(rbi_rules)
        rbi_rule_fields.extend([str(rule.get("field") or "") for rule in rbi_rules])
        policy_rule_fields.extend([str(rule.get("field") or "") for rule in policy_rules])

        pair_changes = _compare_rules(policy_rules, rbi_rules)
        for change in pair_changes:
            parsed_changes.append(
                {
                    "type": str(change.get("type") or "modified_requirement"),
                    "statement": str(change.get("field") or "Regulatory rule change"),
                    "old_text": "" if change.get("old") is None else str(change.get("old")),
                    "new_text": "" if change.get("new") is None else str(change.get("new")),
                    "field": str(change.get("field") or "").strip(),
                    "old": change.get("old"),
                    "new": change.get("new"),
                    "evidence": str(change.get("evidence") or "").strip(),
                    "source": str(change.get("source") or "RBI").strip().upper(),
                    "block_id": pair_id,
                }
            )

    print(f"RBI rules extracted: {total_rbi_rules}")
    print(f"Policy rules extracted: {total_policy_rules}")
    print(f"RBI rule sample: {', '.join([field for field in rbi_rule_fields if field][:4])}")
    print(f"Policy rule sample: {', '.join([field for field in policy_rule_fields if field][:4])}")
    print(f"Matching results: {len(parsed_changes)} structured changes")

    if debug:
        logger.info("Batch comparison parsed_changes=%s pairs=%s", len(parsed_changes), len(batch_input))
    return parsed_changes


def compare_blocks(old_block: Dict, new_block: Dict, debug: bool = False) -> List[Dict]:
    """
    Compare OLD and NEW regulatory blocks.
    
    Returns list of changes:
    [
        {
            "type": "added|removed|modified",
            "statement": "exact factual difference",
            "old_text": "original text",
            "new_text": "new text"
        }
    ]
    """
    
    # Extract content
    old_content = str(old_block.get("content", "") or "").strip() if old_block else ""
    new_content = str(new_block.get("content", "") or "").strip() if new_block else ""
    old_heading = str(old_block.get("heading", "") or "").strip() if old_block else ""
    new_heading = str(new_block.get("heading", "") or "").strip() if new_block else ""
    block_id = str(old_block.get("block_id", "") or new_block.get("block_id", "") or "unknown")
    
    # Handle added/removed blocks
    if not old_content and new_content:
        # Block was added
        return [{
            "type": "added",
            "statement": f"New regulatory requirement added: {new_heading or 'Untitled section'}",
            "old_text": "",
            "new_text": _truncate_text(new_content, 200),
            "block_id": block_id,
        }]
    
    if old_content and not new_content:
        # Block was removed
        return [{
            "type": "removed",
            "statement": f"Regulatory requirement removed: {old_heading or 'Untitled section'}",
            "old_text": _truncate_text(old_content, 200),
            "new_text": "",
            "block_id": block_id,
        }]
    
    if not old_content and not new_content:
        return []
    
    # Both exist → compare for modifications
    # Truncate for LLM (stay within token budget)
    old_for_llm = _truncate_text(old_content, 400)
    new_for_llm = _truncate_text(new_content, 400)
    
    # Construct comparison prompt
    prompt = f"""You are a legal diff engine. Extract ONLY explicit differences.

STRICT RULES:
- Only factual differences
- NO summarization
- NO interpretation
- NO generalization
- NO inferred meaning
- Compare actual text only

Focus ONLY on:
- numeric changes (%, limits, values, amounts)
- dates or timeframes
- conditions or requirements
- obligations (shall, must, required, should)
- explicit added/removed text

If NO difference exists → return {{"changes": []}}
Do NOT return empty descriptions.
Do NOT infer meaning.

Return ONLY valid JSON:
{{
  "changes": [
    {{
      "type": "added|removed|modified",
      "statement": "exact factual difference statement",
      "old_text": "exact original text",
      "new_text": "exact new text"
    }}
  ]
}}

OLD TEXT:
{old_for_llm}

NEW TEXT:
{new_for_llm}"""
    
    try:
        response = call_groq_with_retry(
            messages=[
                {
                    "role": "system",
                    "content": "You are a strict JSON legal comparison tool. Return ONLY valid JSON matching the required schema.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            max_tokens=500,
            temperature=0.0,
            retries=1,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        logger.error("LLM comparison failed for block %s: %s", block_id, exc)
        return []
    
    # Parse response
    parsed = _parse_diff_response(response)
    if not parsed or not isinstance(parsed.get("changes"), list):
        logger.warning("Failed to parse diff response for block %s", block_id)
        return []
    
    # Validate changes
    valid_changes = []
    
    for change in parsed.get("changes", []):
        if not _is_valid_change(change):
            if debug:
                logger.debug("Skipping invalid change: %s", change)
            continue
        
        statement = str(change.get("statement", "")).strip()
        
        # Reject vague language
        if _contains_vague_terms(statement):
            if debug:
                logger.debug("Skipping vague change: %s", statement)
            continue
        
        valid_changes.append({
            "type": change.get("type"),
            "statement": statement,
            "old_text": str(change.get("old_text", "")).strip(),
            "new_text": str(change.get("new_text", "")).strip(),
            "block_id": block_id,
        })
    
    if debug:
        logger.info(
            "Block comparison %s: extracted=%s valid=%s",
            block_id,
            len(parsed.get("changes", [])),
            len(valid_changes)
        )
    
    return valid_changes


def compare_all_matched_blocks(matches: List[Dict], debug: bool = False) -> Tuple[List[Dict], Dict]:
    """
    Compare all matched block pairs.
    
    Returns:
    - List of all detected changes
    - Stats dict with summary
    """
    
    all_changes = []
    stats = {
        "total_comparisons": 0,
        "matched_pairs": 0,
        "added_blocks": 0,
        "removed_blocks": 0,
        "total_changes_detected": 0,
        "api_calls": 0,
    }
    
    matched_pairs = []

    for match in matches:
        match_type = match.get("match_type", "")
        stats["total_comparisons"] += 1
        
        if match_type == "added":
            stats["added_blocks"] += 1
            # Return generic "added" change
            new_block = match.get("new_block")
            if new_block:
                all_changes.append({
                    "type": "added",
                    "statement": f"Section added: {new_block.get('heading', 'Untitled')}",
                    "old_text": "",
                    "new_text": _truncate_text(new_block.get("content", ""), 200),
                    "block_id": new_block.get("block_id"),
                })
        
        elif match_type == "removed":
            stats["removed_blocks"] += 1
            # Return generic "removed" change
            old_block = match.get("old_block")
            if old_block:
                all_changes.append({
                    "type": "removed",
                    "statement": f"Section removed: {old_block.get('heading', 'Untitled')}",
                    "old_text": _truncate_text(old_block.get("content", ""), 200),
                    "new_text": "",
                    "block_id": old_block.get("block_id"),
                })
        
        elif match_type == "matched":
            stats["matched_pairs"] += 1
            matched_pairs.append(match)

    # Batch strategy:
    # - If <=10 matched pairs => single call
    # - If >10 matched pairs => split into batches of 5
    if matched_pairs:
        if len(matched_pairs) > (MAX_BATCH_PAIRS * MAX_BATCH_CALLS):
            matched_pairs = sorted(
                matched_pairs,
                key=lambda item: float(item.get("match_score") or 0.0),
                reverse=True,
            )[: (MAX_BATCH_PAIRS * MAX_BATCH_CALLS)]
            logger.info(
                "Matched pairs truncated to control LLM calls | kept=%s max_calls=%s",
                len(matched_pairs),
                MAX_BATCH_CALLS,
            )

        batches = [matched_pairs] if len(matched_pairs) <= 10 else _chunk_list(matched_pairs, MAX_BATCH_PAIRS)
        batches = batches[:MAX_BATCH_CALLS]
        stats["api_calls"] += len(batches)
        for batch in batches:
            batch_changes = compare_blocks_batch(batch, debug=debug)
            all_changes.extend(batch_changes)
    
    stats["total_changes_detected"] = len(all_changes)
    
    logger.info(
        "Block comparison summary: comparisons=%s changes=%s added=%s removed=%s",
        stats["total_comparisons"],
        stats["total_changes_detected"],
        stats["added_blocks"],
        stats["removed_blocks"],
    )
    
    print(f"\n⚖️  Block Comparison Results:")
    print(f"   Total comparisons: {stats['total_comparisons']}")
    print(f"   Changes detected: {stats['total_changes_detected']}")
    print(f"   Added blocks: {stats['added_blocks']}")
    print(f"   Removed blocks: {stats['removed_blocks']}")
    print()
    
    return all_changes, stats
