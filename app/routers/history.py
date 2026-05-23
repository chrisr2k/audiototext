import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response

from app.templates import templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User, Transcript
from app.auth import get_current_user, get_optional_user
from app.services.oci_speech import check_job_status

logger = logging.getLogger(__name__)



router = APIRouter(prefix="/history", tags=["history"])


@router.get("/", response_class=HTMLResponse)
async def history_page(request: Request, user: User = Depends(get_optional_user)):
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "demo_mode": settings.DEMO_MODE,
    })



@router.get("/list")
async def list_transcripts(
    page: int = 1,
    per_page: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total = db.query(Transcript).filter(Transcript.user_id == user.id).count()
    transcripts = (
        db.query(Transcript)
        .filter(Transcript.user_id == user.id)
        .order_by(Transcript.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    # Check OCI status for any processing transcripts (so the UI auto-updates)
    if not settings.DEMO_MODE:
        for t in transcripts:
            if t.status == "processing" and t.oci_job_id:
                try:
                    status_result = check_job_status(t.oci_job_id)
                    if status_result.get("status") == "COMPLETED":
                        t.status = "completed"
                        t.text = status_result.get("text") or ""
                        speakers = status_result.get("speakers", [])
                        if speakers:
                            t.speakers_data = json.dumps(speakers)
                        db.commit()
                    elif status_result.get("status") == "FAILED":
                        t.status = "failed"
                        t.error_message = "OCI transcription job failed"
                        db.commit()
                except Exception as e:
                    logger.warning(f"Error checking OCI job status for {t.oci_job_id}: {e}")

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
        "transcripts": [t.to_dict() for t in transcripts],
    }



@router.get("/{transcript_id}")
async def view_transcript(
    transcript_id: str,
    request: Request,
    user: User = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    if not user:
        return RedirectResponse(url="/auth/login")

    transcript = db.query(Transcript).filter(
        Transcript.id == transcript_id,
        Transcript.user_id == user.id,
    ).first()

    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found",
        )

    return templates.TemplateResponse("transcript.html", {
        "request": request,
        "user": user,
        "transcript": transcript.to_dict(),
        "demo_mode": settings.DEMO_MODE,
    })



@router.delete("/{transcript_id}")
async def delete_transcript(
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

    db.delete(transcript)
    db.commit()

    return {"message": "Transcript deleted successfully"}


@router.get("/{transcript_id}/download")
async def download_transcript(
    transcript_id: str,
    format: str = "txt",
    user: User = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    transcript = db.query(Transcript).filter(
        Transcript.id == transcript_id,
        Transcript.user_id == user.id,
    ).first()

    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found",
        )

    if not transcript.text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transcript has no text content",
        )

    if format == "txt":
        content = transcript.text
        media_type = "text/plain"
        filename = f"{Path(transcript.original_filename).stem}_transcript.txt"
        return PlainTextResponse(
            content=content,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    elif format == "srt":
        content = _generate_srt(transcript.text, transcript.duration_seconds or 0)
        media_type = "text/plain"
        filename = f"{Path(transcript.original_filename).stem}_transcript.srt"
        return PlainTextResponse(
            content=content,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    elif format == "pdf_speaker":
        transcript_dict = transcript.to_dict()
        pdf_content = _generate_pdf_speaker(transcript_dict)
        filename = f"{Path(transcript.original_filename).stem}_speaker_view.pdf"
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    elif format == "pdf_timed":
        transcript_dict = transcript.to_dict()
        pdf_content = _generate_pdf_timed(transcript_dict)
        filename = f"{Path(transcript.original_filename).stem}_timed_transcript.pdf"
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format: {format}. Supported: txt, srt, pdf_speaker, pdf_timed",
        )


def _generate_srt(text: str, duration_seconds: float) -> str:
    """Generate a simple SRT subtitle format from transcript text."""
    words = text.split()
    if not words:
        return ""

    # Roughly estimate timing: assume ~3 words per second
    words_per_second = 3.0
    total_seconds = max(len(words) / words_per_second, duration_seconds)

    # Create chunks of ~10 words per subtitle entry
    chunk_size = 10
    srt_lines = []
    subtitle_num = 1

    for i in range(0, len(words), chunk_size):
        chunk = words[i:i + chunk_size]
        start_time = (i / words_per_second)
        end_time = min((i + chunk_size) / words_per_second, total_seconds)

        srt_lines.append(str(subtitle_num))
        srt_lines.append(
            f"{_format_srt_time(start_time)} --> {_format_srt_time(end_time)}"
        )
        srt_lines.append(" ".join(chunk))
        srt_lines.append("")
        subtitle_num += 1

    return "\n".join(srt_lines)


def _format_srt_time(seconds: float) -> str:
    """Format seconds to SRT timestamp format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _build_timed_chunks(speakers: list, full_text: str, duration_seconds: float, chunk_duration: int = 30) -> list:
    """Build ~30-second timed chunks from speaker segments or estimate from text.

    Returns list of (start_seconds, end_seconds, text) tuples.
    """
    if speakers:
        # Use speaker segment timestamps to build accurate 30-second chunks
        chunks = []
        current_chunk_start = 0.0
        current_chunk_text_parts = []

        for segment in speakers:
            seg_start_str = segment.get("start_time", "0").replace("s", "")
            seg_end_str = segment.get("end_time", "0").replace("s", "")
            try:
                seg_start = float(seg_start_str)
                seg_end = float(seg_end_str)
            except (ValueError, TypeError):
                seg_start = 0.0
                seg_end = 0.0

            seg_text = segment.get("text", "")

            # If this segment starts a new chunk boundary
            if seg_start >= current_chunk_start + chunk_duration and current_chunk_text_parts:
                chunk_end = current_chunk_start + chunk_duration
                chunks.append((current_chunk_start, chunk_end, " ".join(current_chunk_text_parts)))
                current_chunk_start = chunk_duration * int(seg_start / chunk_duration)
                current_chunk_text_parts = []

            current_chunk_text_parts.append(seg_text)

        # Add the last chunk
        if current_chunk_text_parts:
            chunk_end = duration_seconds if duration_seconds else (current_chunk_start + chunk_duration)
            chunks.append((current_chunk_start, chunk_end, " ".join(current_chunk_text_parts)))

        return chunks
    else:
        # No speaker data - estimate timing from word count (~3 words/sec)
        words = full_text.split()
        if not words:
            return [(0, chunk_duration, "")]

        words_per_second = 3.0
        total_seconds = max(len(words) / words_per_second, duration_seconds)
        chunks = []
        words_per_chunk = int(words_per_second * chunk_duration)

        for i in range(0, len(words), words_per_chunk):
            chunk_words = words[i:i + words_per_chunk]
            chunk_start = i / words_per_second
            chunk_end = min((i + len(chunk_words)) / words_per_second, total_seconds)
            chunks.append((chunk_start, chunk_end, " ".join(chunk_words)))

        return chunks


def _add_pdf_header(pdf, transcript):
    """Add common header, title, metadata, and footer to a PDF."""
    # --- Header ---
    pdf.set_font('Helvetica', 'I', 8)
    pdf.set_text_color(107, 114, 128)
    pdf.cell(0, 5, 'AudioToText - OCI Speech Transcription', align='C')
    pdf.ln(8)

    # --- Title ---
    pdf.set_font('Helvetica', 'B', 18)
    pdf.set_text_color(17, 24, 39)
    title = transcript.get("filename", "Transcript")
    if len(title) > 60:
        title = title[:57] + "..."
    pdf.cell(0, 8, title)
    pdf.ln(7)

    # --- Subtitle (date) ---
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(107, 114, 128)
    created_at = transcript.get("created_at", "")
    pdf.cell(0, 5, f"Generated on {created_at}")
    pdf.ln(8)

    # --- Metadata Grid ---
    meta_x = pdf.get_x()
    meta_y = pdf.get_y()
    meta_w = pdf.w - 2 * pdf.l_margin

    pdf.set_fill_color(249, 250, 251)
    pdf.set_draw_color(229, 231, 235)
    pdf.rect(meta_x, meta_y, meta_w, 28, style='DF')
    pdf.ln(3)

    meta_items = []
    meta_items.append(("Status", transcript.get("status", "").title()))
    meta_items.append(("Language", transcript.get("language", "en-US")))

    confidence = transcript.get("confidence")
    if confidence:
        meta_items.append(("Confidence", f"{confidence * 100:.1f}%"))

    duration_seconds = transcript.get("duration_seconds")
    if duration_seconds:
        mins = int(duration_seconds // 60)
        secs = int(duration_seconds % 60)
        meta_items.append(("Duration", f"{mins}m {secs}s"))

    file_size = transcript.get("file_size")
    if file_size:
        if file_size < 1024:
            size_str = f"{file_size} B"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        else:
            size_str = f"{file_size / (1024 * 1024):.1f} MB"
        meta_items.append(("File Size", size_str))

    col_w = meta_w / max(len(meta_items), 1)
    for label, value in meta_items:
        idx = meta_items.index((label, value))
        pdf.set_xy(meta_x + (idx % 5) * col_w + 3, meta_y + 3)
        pdf.set_font('Helvetica', 'B', 7)
        pdf.set_text_color(107, 114, 128)
        pdf.cell(col_w - 6, 4, label.upper())
        pdf.set_xy(meta_x + (idx % 5) * col_w + 3, meta_y + 8)
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(31, 41, 55)
        pdf.cell(col_w - 6, 5, value)

    pdf.set_y(meta_y + 32)


def _add_pdf_footer(pdf):
    """Add common footer to a PDF."""
    pdf.ln(10)
    pdf.set_draw_color(229, 231, 235)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(4)
    pdf.set_font('Helvetica', 'I', 7)
    pdf.set_text_color(156, 163, 175)
    pdf.cell(0, 4, 'Generated by AudioToText using Oracle Cloud Infrastructure (OCI) Speech Services', align='C')


def _generate_pdf_speaker(transcript: dict) -> bytes:
    """Generate a PDF with color-coded speaker view segments."""
    from fpdf import FPDF

    colors = [
        (59, 130, 246),    # blue
        (16, 185, 129),    # green
        (245, 158, 11),    # amber
        (239, 68, 68),     # red
        (139, 92, 246),    # purple
    ]

    pdf = FPDF(orientation='P', unit='mm', format='Letter')
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    _add_pdf_header(pdf, transcript)

    speakers = transcript.get("speakers", [])
    full_text = transcript.get("text", "")

    if speakers:
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(17, 24, 39)
        pdf.cell(0, 8, 'Speaker View')
        pdf.ln(10)

        for segment in speakers:
            speaker_raw = segment.get("speaker", "speaker_0")
            speaker_num = 0
            try:
                speaker_num = int(speaker_raw.replace("speaker_", ""))
            except ValueError:
                speaker_num = 0
            r, g, b = colors[speaker_num % len(colors)]
            speaker_label = speaker_raw.replace("_", " ").title()
            seg_text = segment.get("text", "")

            if pdf.get_y() > 250:
                pdf.add_page()

            pdf.set_fill_color(249, 250, 251)
            pdf.set_draw_color(229, 231, 235)
            seg_x = pdf.get_x()
            seg_y = pdf.get_y()

            pdf.set_font('Helvetica', '', 10)
            text_lines = pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin - 8, 5, seg_text, split_only=True)
            text_height = len(text_lines) * 5 + 2

            pdf.set_fill_color(r, g, b)
            pdf.rect(seg_x, seg_y, 2, 14 + text_height, style='F')

            pdf.set_fill_color(249, 250, 251)
            pdf.set_draw_color(229, 231, 235)
            pdf.rect(seg_x + 2, seg_y, pdf.w - pdf.l_margin - pdf.r_margin - 2, 14 + text_height, style='DF')

            pdf.set_xy(seg_x + 8, seg_y + 2)
            pdf.set_font('Helvetica', 'B', 8)
            pdf.set_text_color(r, g, b)
            pdf.cell(40, 4, speaker_label)

            start_time = segment.get("start_time", "")
            end_time = segment.get("end_time", "")
            if start_time:
                from app.templates import format_timestamp
                start_fmt = format_timestamp(start_time.replace("s", ""))
                end_fmt = format_timestamp(end_time.replace("s", "")) if end_time else ""
                pdf.set_font('Courier', '', 7)
                pdf.set_text_color(107, 114, 128)
                pdf.cell(0, 4, f"{start_fmt} - {end_fmt}", align='R')

            pdf.set_xy(seg_x + 8, seg_y + 8)
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(31, 41, 55)
            pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin - 16, 5, seg_text)
            pdf.ln(4)
    else:
        # No speaker data - just show the full text
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(17, 24, 39)
        pdf.cell(0, 8, 'Transcribed Text')
        pdf.ln(10)

        if pdf.get_y() > 250:
            pdf.add_page()

        pdf.set_fill_color(249, 250, 251)
        pdf.set_draw_color(229, 231, 235)
        pdf.rect(pdf.get_x(), pdf.get_y(), pdf.w - pdf.l_margin - pdf.r_margin, 6, style='DF')
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(31, 41, 55)
        pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin, 5.5, full_text)

    _add_pdf_footer(pdf)
    return bytes(pdf.output())


def _generate_pdf_timed(transcript: dict) -> bytes:
    """Generate a PDF with the full text broken into ~30-second timed chunks."""
    from fpdf import FPDF

    pdf = FPDF(orientation='P', unit='mm', format='Letter')
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    _add_pdf_header(pdf, transcript)

    speakers = transcript.get("speakers", [])
    full_text = transcript.get("text", "")
    duration_seconds = transcript.get("duration_seconds") or 0
    chunk_duration = 30

    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(17, 24, 39)
    pdf.cell(0, 8, 'Timed Transcript (30-second chunks)')
    pdf.ln(10)

    chunks = _build_timed_chunks(speakers, full_text, duration_seconds, chunk_duration)

    for chunk_start, chunk_end, chunk_text in chunks:
        if pdf.get_y() > 250:
            pdf.add_page()

        start_mm = int(chunk_start // 60)
        start_ss = int(chunk_start % 60)
        end_mm = int(chunk_end // 60)
        end_ss = int(chunk_end % 60)
        timestamp_label = f"{start_mm:02d}:{start_ss:02d} - {end_mm:02d}:{end_ss:02d}"

        pdf.set_fill_color(243, 244, 246)
        pdf.set_draw_color(209, 213, 219)
        pdf.rect(pdf.get_x(), pdf.get_y(), pdf.w - pdf.l_margin - pdf.r_margin, 7, style='DF')
        pdf.set_font('Courier', 'B', 8)
        pdf.set_text_color(55, 65, 81)
        pdf.set_xy(pdf.get_x() + 3, pdf.get_y() + 1)
        pdf.cell(0, 5, timestamp_label)
        pdf.ln(9)

        pdf.set_x(pdf.get_x() + 3)
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(31, 41, 55)
        pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin - 6, 5.5, chunk_text)
        pdf.ln(3)

    _add_pdf_footer(pdf)
    return bytes(pdf.output())
