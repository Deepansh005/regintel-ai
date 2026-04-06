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
def process_task(task_id: str, file_paths: dict):
    try:
        mode = file_paths.get("mode", "all")
        
        old_context = ""
        new_context = ""
        policy_context = ""

        # -----------------------------
        # 1-4. EXTRACT, CHUNK, STORE & RETRIEVE
        # -----------------------------
        if "policy" in file_paths:
            policy_text = extract_text_from_pdf(file_paths["policy"])
            policy_chunks = chunk_markdown_text(policy_text)
            store_chunks(policy_chunks, "internal_policy", file_paths["policy"])
            policy_context = build_context(retrieve_with_metadata("internal compliance rules", "internal_policy"))
            
        if "old" in file_paths:
            old_text = extract_text_from_pdf(file_paths["old"])
            old_chunks = chunk_markdown_text(old_text)
            store_chunks(old_chunks, "old_regulation", file_paths["old"])
            old_context = build_context(retrieve_with_metadata("key regulatory clauses", "old_regulation"))

        if "new" in file_paths:
            new_text = extract_text_from_pdf(file_paths["new"])
            new_chunks = chunk_markdown_text(new_text)
            store_chunks(new_chunks, "new_regulation", file_paths["new"])
            new_context = build_context(retrieve_with_metadata("latest regulatory changes", "new_regulation"))

        # -----------------------------
        # 5. AI PROCESSING
        # -----------------------------
        changes = "No temporal comparison was requested for this analysis mode."
        compliance_gaps = "No compliance gap analysis was requested for this analysis mode."
        
        if mode == "all":
            if old_context and new_context:
                changes = detect_changes(old_context, new_context)
            if new_context and policy_context:
                compliance_gaps = detect_compliance_gaps(new_context, policy_context)
        elif mode == "old":
            if old_context and policy_context:
                compliance_gaps = detect_compliance_gaps(old_context, policy_context)
        elif mode == "new":
            if new_context and policy_context:
                compliance_gaps = detect_compliance_gaps(new_context, policy_context)

        impact = analyze_impact(str(changes) + "\n" + str(compliance_gaps))
        actions = generate_actions(str(changes), str(impact) + "\n" + str(compliance_gaps))

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