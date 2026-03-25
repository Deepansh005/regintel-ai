from fastapi import APIRouter, UploadFile, File
import os
import shutil

from app.services.pdf_service import extract_text_from_pdf
from app.services.ai_service import detect_changes  

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload-documents")
async def upload_documents(
    old_doc: UploadFile = File(...),
    new_doc: UploadFile = File(...)
):
    try:
        old_path = os.path.join(UPLOAD_DIR, old_doc.filename)
        new_path = os.path.join(UPLOAD_DIR, new_doc.filename)

        with open(old_path, "wb") as buffer:
            shutil.copyfileobj(old_doc.file, buffer)

        with open(new_path, "wb") as buffer:
            shutil.copyfileobj(new_doc.file, buffer)

        #  Extract text
        old_text = extract_text_from_pdf(old_path)
        new_text = extract_text_from_pdf(new_path)

        #  CALL AI
        changes = detect_changes(old_text, new_text)

        return {
            "changes": changes
        }

    except Exception as e:
        return {"error": str(e)}