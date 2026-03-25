from fastapi import FastAPI
from app.routes import upload
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Include routes
app.include_router(upload.router)

@app.get("/")
def root():
    return {"message": "RegIntel AI Backend Running 🚀"}