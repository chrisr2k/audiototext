import json
import logging
import os
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Request
from fastapi.responses import HTMLResponse, JSONResponse
from app.templates import templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User, Transcript
from app.auth import get_current_user, get_optional_user

from app.services.oci_speech import transcribe_audio, start_transcription_job, check_job_status

router = APIRouter(prefix="/transcribe", tags=["transcribe"])


@router.get("/", response_class=HTMLResponse)
async def transcribe_page(request: Request, user: User = Depends(get_optional_user)):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user,
        "languages": settings.SUPPORTED_LANGUAGES,
        "demo_mode": settings.DEMO_MODE,
    })



@router.post("/upload")
async def upload_audio(
    request: Request,
    file: UploadFile = File(...),
    language: str = Form("en-US"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Validate file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format: {file_ext}. "
                   f"Supported formats: {', '.join(sorted(settings.ALLOWED_EXTENSIONS))}",
        )

    # Validate language
    if language not in settings.SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported language: {language}. "
                   f"Supported languages: {', '.join(settings.SUPPORTED_LANGUAGES.keys())}",
        )

    # Save uploaded file
    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}{file_ext}"
    upload_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE // (1024*1024)} MB",
        )

    with open(upload_path, "wb") as f:
        f.write(content)

    # Create transcript record
    transcript = Transcript(
        user_id=user.id,
        filename=safe_filename,
        original_filename=file.filename,
        file_size=len(content),
        file_format=file_ext.lstrip("."),
        language=language,
        status="pending",
    )
    db.add(transcript)
    db.commit()
    db.refresh(transcript)

    # Start transcription job (async - returns immediately)
    try:
        transcript.status = "processing"
        db.commit()

        # Use start_transcription_job for async flow (returns immediately)
        # Falls back to synchronous transcribe_audio for demo mode
        if settings.DEMO_MODE:
            result = transcribe_audio(upload_path, language)
            transcript.status = "completed"
            transcript.text = result.get("text", "")
            transcript.confidence = result.get("confidence")
            transcript.duration_seconds = result.get("duration_seconds")
            transcript.oci_job_id = result.get("job_id")
            # Demo mode: generate simulated speaker segments
            speakers = _generate_demo_speakers(result.get("text", ""))
            transcript.speakers_data = json.dumps(speakers)
            db.commit()
        else:
            # Start the OCI job asynchronously
            job_info = start_transcription_job(upload_path, language)
            transcript.oci_job_id = job_info.get("job_id")
            transcript.status = "processing"
            db.commit()

            # Try to check status immediately (may still be processing)
            try:
                status_result = check_job_status(job_info["job_id"])
                if status_result.get("status") == "COMPLETED":
                    transcript.status = "completed"
                    transcript.text = status_result.get("text") or ""
                    speakers = status_result.get("speakers", [])
                    if speakers:
                        transcript.speakers_data = json.dumps(speakers)
                    db.commit()
            except Exception:
                pass  # Job is still processing, that's expected

    except Exception as e:
        transcript.status = "failed"
        transcript.error_message = str(e)
        db.commit()

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Transcription failed: {str(e)}", "transcript_id": transcript.id},
        )

    return {
        "transcript_id": transcript.id,
        "status": transcript.status,
        "text": transcript.text,
        "confidence": transcript.confidence,
        "duration_seconds": transcript.duration_seconds,
        "language": transcript.language,
        "filename": transcript.original_filename,
        "is_demo": settings.DEMO_MODE,
        "oci_job_id": transcript.oci_job_id,
    }


@router.get("/status/{transcript_id}")
async def get_transcript_status(
    transcript_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    transcript = db.query(Transcript).filter(
        Transcript.id == transcript_id,
        Transcript.user_id == user.id,
    ).first()

    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found",
        )

    # If still processing and has an OCI job ID, check OCI for status update
    if transcript.status == "processing" and transcript.oci_job_id and not settings.DEMO_MODE:
        try:
            status_result = check_job_status(transcript.oci_job_id)
            if status_result.get("status") == "COMPLETED":
                transcript.status = "completed"
                transcript.text = status_result.get("text") or ""
                speakers = status_result.get("speakers", [])
                if speakers:
                    transcript.speakers_data = json.dumps(speakers)
                db.commit()
            elif status_result.get("status") == "FAILED":
                transcript.status = "failed"
                transcript.error_message = "OCI transcription job failed"
                db.commit()
        except Exception as e:
            logger.warning(f"Error checking OCI job status for {transcript.oci_job_id}: {e}")
            # Job still processing or error checking - just return current state

    return transcript.to_dict()


def _generate_demo_speakers(text: str) -> list:
    """Generate simulated speaker segments for demo mode."""
    if not text:
        return []

    words = text.split()
    if len(words) < 5:
        return [{"speaker": "speaker_0", "text": text}]

    # Split text into alternating speaker segments
    speakers = []
    chunk_size = max(3, len(words) // 4)  # ~4 alternating segments
    current_speaker = "speaker_0"

    for i in range(0, len(words), chunk_size):
        chunk = words[i:i + chunk_size]
        speakers.append({
            "speaker": current_speaker,
            "text": " ".join(chunk),
        })
        # Alternate between speaker_0 and speaker_1
        current_speaker = "speaker_1" if current_speaker == "speaker_0" else "speaker_0"

    return speakers
