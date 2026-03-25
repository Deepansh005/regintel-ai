from fastapi import APIRouter

router = APIRouter()

@router.get("/test")
def test_route():
    return {"status": "Upload route working"}