"""Fix stuck transcripts by checking OCI job status and updating the database."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal
from app.models import Transcript
from app.services.oci_speech import check_job_status

db = SessionLocal()

# Find all transcripts stuck in 'processing' with an OCI job ID
stuck = db.query(Transcript).filter(
    Transcript.status == 'processing',
    Transcript.oci_job_id.isnot(None)
).all()

print(f'Found {len(stuck)} stuck transcripts with OCI job IDs')

for t in stuck:
    print(f'\nTranscript {t.id}:')
    print(f'  Current status: {t.status}')
    print(f'  OCI Job ID: {t.oci_job_id}')
    
    try:
        result = check_job_status(t.oci_job_id)
        print(f'  OCI result status: {result.get("status")}')
        print(f'  Text: {repr(result.get("text"))}')
        
        # Fix: also handle empty string text (not just None)
        if result.get("status") == "COMPLETED":
            text = result.get("text") or ""
            t.status = "completed"
            t.text = text
            db.commit()
            print(f'  -> UPDATED to completed! Text length: {len(text)}')
        elif result.get("status") == "FAILED":
            t.status = "failed"
            t.error_message = "OCI transcription job failed"
            db.commit()
            print(f'  -> UPDATED to failed!')
        else:
            print(f'  -> Still processing (status: {result.get("status")})')
    except Exception as e:
        print(f'  -> Error checking status: {e}')

db.close()
print('\nDone!')
