import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import worker_ai
from app.core.config import GROQ_API_KEY
from app.services.llm_router import key_health_snapshot

logger = logging.getLogger(__name__)

PORT = int(os.getenv("PORT", os.getenv("WORKER_PORT", "8001")))
logger.info(
    "Worker running on PORT %s using KEY %s",
    PORT,
    (GROQ_API_KEY[:5] + "***") if GROQ_API_KEY else "MISSING",
)

app = FastAPI(title="RegIntel AI Worker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(worker_ai.router)


@app.get("/")
async def root():
    return {"message": "RegIntel AI Worker Running"}


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "worker",
        "port": PORT,
        "groq_key": (GROQ_API_KEY[:5] + "***") if GROQ_API_KEY else "MISSING",
        "key_pool": key_health_snapshot(),
    }
