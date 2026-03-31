import os
import uuid
import shutil
from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from db.database import get_task
from fastapi import HTTPException

from db.database import create_task
from app.services.task_worker import process_task
from db.database import get_all_tasks
from app.services.pdf_service import compute_file_hash

router = APIRouter()

@router.get("/tasks")
def get_tasks():
    return get_all_tasks()

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


@router.post("/upload-documents")
async def upload_documents(
    background_tasks: BackgroundTasks,
    old_file: UploadFile = File(...),
    new_file: UploadFile = File(...),
    policy_file: UploadFile = File(...)
):
    # ✅ 1. Generate task_id
    task_id = str(uuid.uuid4())

    # ✅ 2. Save files
    old_path = os.path.join(UPLOAD_DIR, f"{task_id}_old.pdf")
    new_path = os.path.join(UPLOAD_DIR, f"{task_id}_new.pdf")
    policy_path = os.path.join(UPLOAD_DIR, f"{task_id}_policy.pdf")

    with open(old_path, "wb") as buffer:
        shutil.copyfileobj(old_file.file, buffer)

    with open(new_path, "wb") as buffer:
        shutil.copyfileobj(new_file.file, buffer)

    with open(policy_path, "wb") as buffer:
        shutil.copyfileobj(policy_file.file, buffer)

    # Compute content hashes to detect same file uploaded across sections.
    old_hash = compute_file_hash(old_path)
    new_hash = compute_file_hash(new_path)
    policy_hash = compute_file_hash(policy_path)

    # ✅ 3. Create DB task
    create_task(task_id)

    # ✅ 4. Start background task
    background_tasks.add_task(
        process_task,
        task_id,
        {
            "old": old_path,
            "new": new_path,
            "policy": policy_path
        },
        {
            "old": old_hash,
            "new": new_hash,
            "policy": policy_hash,
        },
    )

    # ✅ 5. Instant response
    return {
        "task_id": task_id,
        "status": "processing"
    }