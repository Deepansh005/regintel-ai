import os
import uuid
import shutil
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Form, HTTPException
from typing import Optional
from db.database import get_task, create_task, get_all_tasks
from app.services.task_worker import process_task

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
    mode: str = Form("all"),
    old_file: Optional[UploadFile] = File(None),
    new_file: Optional[UploadFile] = File(None),
    policy_file: Optional[UploadFile] = File(None)
):
    task_id = str(uuid.uuid4())
    file_paths = {}

    if old_file and old_file.filename:
        path = os.path.join(UPLOAD_DIR, f"{task_id}_old.pdf")
        with open(path, "wb") as buffer:
            shutil.copyfileobj(old_file.file, buffer)
        file_paths["old"] = path

    if new_file and new_file.filename:
        path = os.path.join(UPLOAD_DIR, f"{task_id}_new.pdf")
        with open(path, "wb") as buffer:
            shutil.copyfileobj(new_file.file, buffer)
        file_paths["new"] = path

    if policy_file and policy_file.filename:
        path = os.path.join(UPLOAD_DIR, f"{task_id}_policy.pdf")
        with open(path, "wb") as buffer:
            shutil.copyfileobj(policy_file.file, buffer)
        file_paths["policy"] = path

    file_paths["mode"] = mode

    create_task(task_id)
    background_tasks.add_task(process_task, task_id, file_paths)

    return {
        "task_id": task_id,
        "status": "processing"
    }