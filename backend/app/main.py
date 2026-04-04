from fastapi import FastAPI
from app.routes import upload
from fastapi.middleware.cors import CORSMiddleware
from db.database import init_db

app = FastAPI()
@app.on_event("startup")
def startup_event():
    init_db()
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3001", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routes
app.include_router(upload.router)



@app.get("/")
def root():
    return {"message": "RegIntel AI Backend Running 🚀"}