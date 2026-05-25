"""
AudioToText - OCI Speech to Text Web Application

A web-based application that converts audio files to text using
Oracle Cloud Infrastructure (OCI) Speech AI service.
"""

import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import auth, transcribe, history, admin

# Create FastAPI app
app = FastAPI(
    title="AudioToText - OCI Speech Transcription",
    description="Convert audio files to text using Oracle Cloud Infrastructure Speech AI",
    version="1.0.0",
)

# CORS middleware - restrict to your domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://transcribe.chrisreinke.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(transcribe.router)
app.include_router(history.router)
app.include_router(admin.router)


@app.on_event("startup")
async def startup():
    """Initialize the database on startup."""
    # Ensure upload directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    # Initialize database tables
    init_db()


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Redirect to the login page."""
    return RedirectResponse(url="/auth/login")



@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
