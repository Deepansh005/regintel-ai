import sys
import io
import logging

# Force UTF-8 for standard output to avoid UnicodeEncodeError in Windows console
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.WARNING)

from fastapi import FastAPI
from app.routes import upload, report
from fastapi.middleware.cors import CORSMiddleware
from db.database import init_db
from app.services.llm_router import reload_key_pool, validate_keys_on_startup

app = FastAPI()
@app.on_event("startup")
def startup_event():
    init_db()
    pool_snapshot = reload_key_pool(force_reload_env=True)
    validation = validate_keys_on_startup()

    if validation.get("usable", 0) <= 0:
        raise RuntimeError(
            f"No usable Groq API keys on startup. pool={pool_snapshot} validation={validation}"
        )
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3001", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routes
app.include_router(upload.router)
app.include_router(report.router)


@app.get("/")
def root():
    return {"message": "RegIntel AI Backend Running 🚀"}


@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "backend": "running"}
