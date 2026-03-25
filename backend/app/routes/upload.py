from fastapi import APIRouter, UploadFile, File
import os
import shutil

from app.services.pdf_service import extract_text_from_pdf
from app.services.ai_service import detect_changes, analyze_impact, generate_actions


router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload-documents")
async def upload_documents(
    old_file: UploadFile = File(...),
    new_file: UploadFile = File(...)
):
    try:
        old_path = os.path.join(UPLOAD_DIR, old_file.filename)
        new_path = os.path.join(UPLOAD_DIR, new_file.filename)

        with open(old_path, "wb") as buffer:
            shutil.copyfileobj(old_file.file, buffer)

        with open(new_path, "wb") as buffer:
            shutil.copyfileobj(new_file.file, buffer)

        #  Extract text
        old_text = extract_text_from_pdf(old_path)
        new_text = extract_text_from_pdf(new_path)

        #  CALL AI
        # Detect change 
        changes = detect_changes(old_text, new_text)
        # Impact analaysis
        impact = analyze_impact(str(changes))
        # Action generation
        actions = generate_actions(str(changes), str(impact))


        return {
            "changes": changes,
            "impact": impact ,
            "actions": actions
        }

    except Exception as e:
        return {"error": str(e)}