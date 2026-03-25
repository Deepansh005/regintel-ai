from fastapi import FastAPI
from app.routes import upload

app = FastAPI()

# Include routes
app.include_router(upload.router)

@app.get("/")
def root():
    return {"message": "RegIntel AI Backend Running 🚀"}