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

from app.rag.retriever import get_vector_db, retrieve_with_metadata
from langchain_core.documents import Document


# =============================
# 🔥 SEMANTIC CHUNKING
# =============================
def chunk_markdown_text(markdown_text: str, max_chunk_size: int = 800):
    sections = re.split(r"\n(?=#{1,6} )", markdown_text)

    chunks = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        if len(section) <= max_chunk_size:
            chunks.append(section)
        else:
            chunks.extend(split_large_section(section, max_chunk_size))

    return chunks


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
# 🔥 STORE IN VECTOR DB
# =============================
def store_chunks(chunks, collection_name, source):
    vectordb = get_vector_db(collection_name)

    documents = [
        Document(
            page_content=chunk,
            metadata={"source": source}
        )
        for chunk in chunks
    ]

    vectordb.add_documents(documents)


# =============================
# CONTEXT BUILDER
# =============================
def build_context(chunks, limit=3000):
    text = "\n\n".join(chunks)
    return text[:limit]


# =============================
# MAIN TASK PROCESSOR
# =============================
def process_task(task_id: str, file_paths: dict, file_hashes: dict | None = None):
    try:
        old_path = file_paths["old"]
        new_path = file_paths["new"]
        policy_path = file_paths["policy"]

        # If any 2+ sections have the same PDF content, return deterministic no-change response.
        if file_hashes:
            hashes = [file_hashes.get("old"), file_hashes.get("new"), file_hashes.get("policy")]
            hashes = [h for h in hashes if h]
            if len(hashes) >= 2 and len(set(hashes)) < len(hashes):
                result = {
                    "changes_detected": 0,
                    "message": "Same PDF uploaded in multiple sections. No changes or impact detected.",
                    "changes": [],
                    "compliance_gaps": [],
                    "impact": [],
                    "actions": [],
                }
                update_task(task_id, status="completed", result=result)
                return

        # -----------------------------
        # 1. EXTRACT TEXT (MARKDOWN)
        # -----------------------------
        old_text = extract_text_from_pdf(old_path)
        new_text = extract_text_from_pdf(new_path)
        policy_text = extract_text_from_pdf(policy_path)

        # -----------------------------
        # 2. SEMANTIC CHUNKING
        # -----------------------------
        old_chunks = chunk_markdown_text(old_text)
        new_chunks = chunk_markdown_text(new_text)
        policy_chunks = chunk_markdown_text(policy_text)

        print(f"\n📦 OLD chunks: {len(old_chunks)}")
        print(f"📦 NEW chunks: {len(new_chunks)}")
        print(f"📦 POLICY chunks: {len(policy_chunks)}")

        print("\n🧠 Sample Chunk:\n", new_chunks[0][:500])

        # -----------------------------
        # 3. STORE IN RAG (IMPROVED)
        # -----------------------------
        store_chunks(old_chunks, "old_regulation", old_path)
        store_chunks(new_chunks, "new_regulation", new_path)
        store_chunks(policy_chunks, "internal_policy", policy_path)

        # -----------------------------
        # 4. RETRIEVE CONTEXT
        # -----------------------------
        old_context = build_context(
            retrieve_with_metadata("key regulatory clauses", "old_regulation")
        )

        new_context = build_context(
            retrieve_with_metadata("latest regulatory changes", "new_regulation")
        )

        policy_context = build_context(
            retrieve_with_metadata("internal compliance rules", "internal_policy")
        )

        # -----------------------------
        # 5. AI PROCESSING
        # -----------------------------
        changes = detect_changes(old_context, new_context)

        compliance_gaps = detect_compliance_gaps(new_context, policy_context)

        impact = analyze_impact(
            str(changes) + "\n" + str(compliance_gaps)
        )

        actions = generate_actions(
            str(changes),
            str(impact) + "\n" + str(compliance_gaps)
        )

        result = {
            "changes": changes,
            "compliance_gaps": compliance_gaps,
            "impact": impact,
            "actions": actions
        }

        # ✅ SAVE SUCCESS
        update_task(task_id, status="completed", result=result)

    except Exception as e:
        traceback.print_exc()

        update_task(
            task_id,
            status="failed",
            result={"error": str(e)}
        )