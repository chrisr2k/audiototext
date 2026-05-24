import uuid
from datetime import datetime, timezone

import json

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, Float, Boolean
from sqlalchemy.orm import relationship


from app.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)

    transcripts = relationship("Transcript", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.email}>"


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=True)
    file_format = Column(String(10), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    language = Column(String(10), default="en-US")
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    text = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    oci_job_id = Column(String(255), nullable=True)
    speakers_data = Column(Text, nullable=True)  # JSON string of speaker segments
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="transcripts")

    def __repr__(self):
        return f"<Transcript {self.original_filename} ({self.status})>"

    def to_dict(self):
        speakers = []
        if self.speakers_data:
            try:
                speakers = json.loads(self.speakers_data)
            except (json.JSONDecodeError, TypeError):
                speakers = []

        return {
            "id": self.id,
            "filename": self.original_filename,
            "file_size": self.file_size,
            "file_format": self.file_format,
            "duration_seconds": self.duration_seconds,
            "language": self.language,
            "status": self.status,
            "text": self.text,
            "confidence": self.confidence,
            "speakers": speakers,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
