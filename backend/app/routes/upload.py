import os
import uuid
import hashlib
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Form, HTTPException, Query
from typing import Optional
from db.database import (
    get_task,
    create_task,
    get_all_tasks,
    clear_task_history,
    delete_old_tasks,
    get_cached_result,
    update_task,
)
from app.services.task_worker import process_task

router = APIRouter()

# =============================
# 🔒 PDF VALIDATION CONSTANTS
# =============================
MAX_FILE_SIZE_MB = 50  # 50 MB max
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MIN_FILE_SIZE_BYTES = 100  # At least 100 bytes
ALLOWED_MIME_TYPES = {"application/pdf"}


def validate_pdf_file(file_bytes: bytes, filename: str) -> None:
    """
    Validate PDF file: size, type, content.
    Raises HTTPException if validation fails.
    """
    
    # Check file size
    if len(file_bytes) < MIN_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File '{filename}' is too small (must be at least {MIN_FILE_SIZE_BYTES} bytes)"
        )
    
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File '{filename}' exceeds max size of {MAX_FILE_SIZE_MB}MB"
        )
    
    # Check PDF magic bytes
    if not file_bytes.startswith(b'%PDF'):
        raise HTTPException(
            status_code=400,
            detail=f"File '{filename}' is not a valid PDF (invalid magic bytes)"
        )
    
    # Check filename
    if not filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail=f"File '{filename}' must have .pdf extension"
        )

@router.get("/tasks")
def get_tasks():
    return get_all_tasks()


@router.delete("/tasks/clear-history")
def clear_tasks_history():
    result = clear_task_history()
    return {
        "message": "All task history cleared successfully",
        **result,
    }


@router.delete("/tasks/delete-old")
def delete_old_tasks_history(days: int = Query(default=7, ge=1, le=3650)):
    result = delete_old_tasks(days)
    return {
        "message": f"Tasks older than {days} days deleted successfully",
        **result,
    }

@router.get("/status/{task_id}")
def get_status(task_id: str):
    task = get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "result": task["result"]
    } 

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def generate_file_hash(file_bytes):
    return hashlib.md5(file_bytes).hexdigest()


def generate_combined_hash(file_hashes: list[str], mode: str) -> str:
    normalized = [h for h in file_hashes if h]
    combined = "".join(normalized) + f":{mode or 'all'}"
    return hashlib.md5(combined.encode("utf-8")).hexdigest()

@router.post("/upload-documents")
async def upload_documents(
    background_tasks: BackgroundTasks,
    mode: str = Form("all"),
    old_file: Optional[UploadFile] = File(None),
    new_file: Optional[UploadFile] = File(None),
    policy_file: Optional[UploadFile] = File(None)
):
    task_id = str(uuid.uuid4())
    file_paths = {}
    file_hashes = {}

    async def _read_and_store(upload_file: UploadFile, suffix: str, section: str):
        if not upload_file or not upload_file.filename:
            return None

        content = await upload_file.read()
        
        # ✅ VALIDATE PDF
        try:
            validate_pdf_file(content, upload_file.filename)
        except HTTPException as e:
            raise e
        
        file_hash = generate_file_hash(content)
        path = os.path.join(UPLOAD_DIR, f"{task_id}_{suffix}.pdf")
        with open(path, "wb") as buffer:
            buffer.write(content)

        file_paths[section] = path
        file_hashes[section] = file_hash
        return file_hash

    if old_file and old_file.filename:
        await _read_and_store(old_file, "old", "old")

    if new_file and new_file.filename:
        await _read_and_store(new_file, "new", "new")

    if policy_file and policy_file.filename:
        await _read_and_store(policy_file, "policy", "policy")

    file_paths["mode"] = mode

    combined_hash = generate_combined_hash(
        [file_hashes.get("old"), file_hashes.get("new"), file_hashes.get("policy")],
        mode,
    )

    cached = get_cached_result(combined_hash)
    if cached:
        create_task(task_id, file_hash=combined_hash)
        update_task(task_id, status="completed", result=cached)
        return {
            "task_id": task_id,
            "status": "completed",
            "cached": True,
            "result": cached,
        }

    create_task(task_id, file_hash=combined_hash)
    background_tasks.add_task(process_task, task_id, file_paths, file_hashes)

    return {
        "task_id": task_id,
        "status": "processing",
        "cached": False
    }