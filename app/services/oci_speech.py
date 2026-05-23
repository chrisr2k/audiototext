"""
OCI Speech AI Service Integration.

This module handles communication with Oracle Cloud Infrastructure Speech AI service
for transcribing audio files to text. It uploads audio to OCI Object Storage,
creates transcription jobs, and retrieves results.
"""

import json
import logging
import os
import random
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


# Try to import OCI SDK, gracefully handle if not installed
try:
    import oci
    from oci.signer import Signer
    from oci.object_storage import ObjectStorageClient
    from oci.ai_speech import AIServiceSpeechClient
    from oci.ai_speech.models import (
        TranscriptionJob,
        TranscriptionModelDetails,
        TranscriptionNormalization,
        ObjectListInlineInputLocation,
        ObjectLocation,
        InputLocation,
        OutputLocation,
        TranscriptionTask,
        TranscriptionSettings,
        Diarization,
    )

    OCI_AVAILABLE = True
except ImportError:
    OCI_AVAILABLE = False


def _get_oci_config() -> dict:
    """Build OCI config dict from settings."""
    return {
        "user": settings.OCI_USER_OCID,
        "tenancy": settings.OCI_TENANCY_OCID,
        "fingerprint": settings.OCI_FINGERPRINT,
        "key_file": settings.OCI_PRIVATE_KEY_PATH,
        "region": settings.OCI_REGION,
    }


def _get_signer() -> "Signer":
    """Create an OCI API signer using configured credentials."""
    return Signer(
        tenancy=settings.OCI_TENANCY_OCID,
        user=settings.OCI_USER_OCID,
        fingerprint=settings.OCI_FINGERPRINT,
        private_key_file_location=settings.OCI_PRIVATE_KEY_PATH,
    )


def _get_speech_client() -> "AIServiceSpeechClient":
    """Create and return an OCI Speech client."""
    if not OCI_AVAILABLE:
        raise ImportError("OCI SDK is not installed. Run: pip install oci")

    config = _get_oci_config()
    signer = _get_signer()
    return AIServiceSpeechClient(
        config=config,
        signer=signer,
        service_endpoint=f"https://speech.aiservice.{settings.OCI_REGION}.oci.oraclecloud.com"
    )


def _get_storage_client() -> "ObjectStorageClient":
    """Create and return an OCI Object Storage client."""
    if not OCI_AVAILABLE:
        raise ImportError("OCI SDK is not installed. Run: pip install oci")

    config = _get_oci_config()
    signer = _get_signer()
    return ObjectStorageClient(config=config, signer=signer)


def _simulate_transcription(audio_path: str, language: str = "en-US") -> dict:
    """
    Simulate transcription for demo mode.
    Returns realistic-looking transcription results.
    """
    filename = os.path.basename(audio_path)
    file_size = os.path.getsize(audio_path) if os.path.exists(audio_path) else 0

    # Simulate processing delay based on file size
    delay = min(max(file_size / (1024 * 50), 1), 10)  # 1-10 seconds
    time.sleep(delay)

    # Generate demo transcription text
    demo_transcriptions = {
        "en-US": (
            "This is a demonstration of the OCI Speech to Text transcription service. "
            "The audio file has been successfully processed and converted to text. "
            "Oracle Cloud Infrastructure's AI services provide powerful speech recognition "
            "capabilities that can be integrated into various applications. "
            "This demo mode simulates what the actual OCI Speech API would return. "
            "To use the real service, configure your OCI credentials in the .env file."
        ),
        "es-ES": (
            "Esta es una demostración del servicio de transcripción de voz a texto de OCI. "
            "El archivo de audio se ha procesado exitosamente y convertido a texto. "
            "Los servicios de IA de Oracle Cloud Infrastructure proporcionan capacidades "
            "potentes de reconocimiento de voz que se pueden integrar en varias aplicaciones."
        ),
        "fr-FR": (
            "Ceci est une démonstration du service de transcription vocale OCI. "
            "Le fichier audio a été traité avec succès et converti en texte. "
            "Les services d'IA d'Oracle Cloud Infrastructure offrent des capacités "
            "puissantes de reconnaissance vocale."
        ),
    }

    text = demo_transcriptions.get(language, demo_transcriptions["en-US"])

    # Simulate confidence score
    confidence = round(random.uniform(0.85, 0.98), 4)

    # Simulate duration based on file size
    duration = round(file_size / (1024 * 16), 2) if file_size > 0 else 30.0

    return {
        "job_id": str(uuid.uuid4()),
        "status": "COMPLETED",
        "text": text,
        "confidence": confidence,
        "duration_seconds": duration,
        "language": language,
        "is_demo": True,
    }


def _upload_to_object_storage(local_path: str) -> str:
    """
    Upload audio file to OCI Object Storage bucket.

    Args:
        local_path: Path to the local audio file

    Returns:
        The object name in the bucket

    Raises:
        RuntimeError: If upload fails
    """
    obj_client = _get_storage_client()
    object_name = f"audio/{uuid.uuid4()}{Path(local_path).suffix}"

    with open(local_path, "rb") as f:
        audio_data = f.read()

    response = obj_client.put_object(
        namespace_name=settings.OCI_NAMESPACE,
        bucket_name=settings.OCI_BUCKET,
        object_name=object_name,
        put_object_body=audio_data,
    )

    logger.info(f"Uploaded {local_path} to OCI Object Storage as {object_name}")
    return object_name


def _wait_for_job_completion(client: "AIServiceSpeechClient", job_id: str, timeout: int = 1800) -> dict:
    """
    Poll for transcription job completion.

    Args:
        client: OCI Speech client
        job_id: Transcription job ID
        timeout: Maximum time to wait in seconds (default 30 minutes)

    Returns:
        Job response data

    Raises:
        TimeoutError: If job doesn't complete within timeout
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        response = client.get_transcription_job(job_id)
        job = response.data

        logger.info(f"Job {job_id} status: {job.lifecycle_state}")

        # OCI uses "SUCCEEDED" (not "COMPLETED") as the final success state
        if job.lifecycle_state in ("SUCCEEDED", "COMPLETED"):
            return job
        elif job.lifecycle_state == "FAILED":
            raise RuntimeError(f"Transcription job {job_id} failed")
        elif job.lifecycle_state == "CANCELED":
            raise RuntimeError(f"Transcription job {job_id} was canceled")

        time.sleep(10)  # Poll every 10 seconds

    raise TimeoutError(f"Transcription job {job_id} did not complete within {timeout} seconds")


def _download_transcription_results(job: "TranscriptionJob") -> dict:
    """
    Download transcription results from OCI Object Storage output location.

    Args:
        job: Completed transcription job object

    Returns:
        dict with:
            - text: Full transcribed text
            - speakers: List of speaker segments with speaker label and text

    Raises:
        RuntimeError: If results cannot be retrieved
    """
    obj_client = _get_storage_client()

    # The output location is in the job's output_location
    output_location = job.output_location
    prefix = output_location.prefix

    # List objects in the output prefix
    objects = obj_client.list_objects(
        namespace_name=output_location.namespace_name,
        bucket_name=output_location.bucket_name,
        prefix=prefix,
    ).data

    # Find the transcription result JSON file (any .json file in the output prefix)
    result_object = None
    for obj in objects.objects:
        if obj.name.endswith(".json"):
            result_object = obj.name
            break

    if not result_object:
        raise RuntimeError("No transcription result file found in output location")

    # Download and parse the result
    response = obj_client.get_object(
        namespace_name=output_location.namespace_name,
        bucket_name=output_location.bucket_name,
        object_name=result_object,
    )
    result_data = json.loads(response.data.content)

    # Extract the transcribed text and speaker diarization from the result
    # OCI transcription results structure with diarization:
    # {
    #   "status": "SUCCESS",
    #   "transcriptions": [
    #     {
    #       "transcription": "the transcribed text string",
    #       "confidence": "1.0",
    #       "tokens": [
    #         {
    #           "token": "word",
    #           "startTime": "0.0",
    #           "endTime": "0.5",
    #           "confidence": 1.0,
    #           "speaker": 1
    #         }
    #       ]
    #     }
    #   ]
    # }
    text_parts = []
    speakers = []
    current_speaker = None
    current_text = ""
    segment_start_time = None
    segment_end_time = None

    for transcription in result_data.get("transcriptions", []):
        text = transcription.get("transcription", "")
        if text:
            text_parts.append(text)

        # Extract speaker diarization from tokens
        # OCI uses "speakerIndex" field (not "speaker") in the token data
        tokens = transcription.get("tokens", [])
        for token_data in tokens:
            token_text = token_data.get("token", "")
            speaker_tag = token_data.get("speakerIndex")
            token_start = token_data.get("startTime", "0.000s")
            token_end = token_data.get("endTime", "0.000s")

            if speaker_tag is not None:
                speaker_label = f"speaker_{speaker_tag}"
                if speaker_label != current_speaker:
                    if current_speaker is not None and current_text.strip():
                        speakers.append({
                            "speaker": current_speaker,
                            "text": current_text.strip(),
                            "start_time": segment_start_time,
                            "end_time": segment_end_time,
                        })
                    current_speaker = speaker_label
                    current_text = ""
                    segment_start_time = token_start
                    segment_end_time = token_end
                else:
                    # Update end time as we go
                    segment_end_time = token_end
                current_text += token_text + " "

    # Don't forget the last speaker segment
    if current_speaker is not None and current_text.strip():
        speakers.append({
            "speaker": current_speaker,
            "text": current_text.strip(),
            "start_time": segment_start_time,
            "end_time": segment_end_time,
        })

    return {
        "text": " ".join(text_parts),
        "speakers": speakers,
    }


def start_transcription_job(audio_path: str, language: str = "en-US") -> dict:
    """
    Start an async transcription job and return immediately with job details.

    This function:
    1. Uploads the audio file to OCI Object Storage
    2. Creates an async transcription job
    3. Returns immediately with the job ID and output prefix

    Args:
        audio_path: Path to the audio file on disk
        language: Language code (e.g., "en-US", "es-ES")

    Returns:
        dict with:
            - job_id: OCI job identifier
            - status: Current status of the job
            - output_prefix: The prefix in the bucket where results will be stored
            - language: Language used
    """
    if settings.DEMO_MODE:
        result = _simulate_transcription(audio_path, language)
        return {
            "job_id": result["job_id"],
            "status": result["status"],
            "output_prefix": None,
            "language": language,
        }

    # Check OCI credentials
    if not all([
        settings.OCI_USER_OCID,
        settings.OCI_TENANCY_OCID,
        settings.OCI_FINGERPRINT,
        settings.OCI_PRIVATE_KEY_PATH,
    ]):
        raise ValueError(
            "OCI credentials not configured. Set OCI_USER_OCID, OCI_TENANCY_OCID, "
            "OCI_FINGERPRINT, and OCI_PRIVATE_KEY_PATH in .env file, "
            "or set DEMO_MODE=true to use demo mode."
        )

    try:
        # Step 1: Upload audio to Object Storage
        object_name = _upload_to_object_storage(audio_path)
        logger.info(f"Audio uploaded to OCI Object Storage: {object_name}")

        # Step 2: Create transcription job
        client = _get_speech_client()

        output_prefix = f"transcriptions/{uuid.uuid4()}/"

        transcription_job = TranscriptionJob(
            display_name=f"transcription_{Path(audio_path).stem}_{uuid.uuid4().hex[:8]}",
            compartment_id=settings.OCI_TENANCY_OCID,
            model_details=TranscriptionModelDetails(
                domain="GENERIC",
                language_code=language,
                transcription_settings=TranscriptionSettings(
                    diarization=Diarization(
                        is_diarization_enabled=True,
                    ),
                ),
            ),
            input_location=ObjectListInlineInputLocation(
                object_locations=[
                    ObjectLocation(
                        namespace_name=settings.OCI_NAMESPACE,
                        bucket_name=settings.OCI_BUCKET,
                        object_names=[object_name],
                    )
                ],
            ),
            output_location=OutputLocation(
                namespace_name=settings.OCI_NAMESPACE,
                bucket_name=settings.OCI_BUCKET,
                prefix=output_prefix,
            ),
        )

        response = client.create_transcription_job(transcription_job)
        job_id = response.data.id
        logger.info(f"Created transcription job: {job_id}")

        return {
            "job_id": job_id,
            "status": response.data.lifecycle_state,
            "output_prefix": output_prefix,
            "language": language,
        }

    except Exception as e:
        raise RuntimeError(f"OCI Speech transcription failed: {str(e)}")


def check_job_status(job_id: str) -> dict:
    """
    Check the status of a transcription job and retrieve results if completed.

    Args:
        job_id: The OCI transcription job ID

    Returns:
        dict with:
            - job_id: OCI job identifier
            - status: Current status of the job
            - text: Transcribed text (if completed)
            - confidence: Confidence score (if available)
    """
    if settings.DEMO_MODE:
        return {
            "job_id": job_id,
            "status": "COMPLETED",
            "text": "Demo transcription completed.",
            "confidence": 0.95,
        }

    try:
        client = _get_speech_client()
        response = client.get_transcription_job(job_id)
        job = response.data

        result = {
            "job_id": job.id,
            "status": job.lifecycle_state,
            "text": None,
            "confidence": None,
        }

        # OCI uses "SUCCEEDED" (not "COMPLETED") as the final success state
        if job.lifecycle_state in ("SUCCEEDED", "COMPLETED"):
            try:
                download_result = _download_transcription_results(job)
                result["text"] = download_result["text"]
                result["speakers"] = download_result.get("speakers", [])
                result["status"] = "COMPLETED"  # Normalize to COMPLETED for our app
            except Exception as e:
                logger.warning(f"Could not download results for job {job_id}: {e}")
                result["text"] = None
                result["speakers"] = []

        return result

    except Exception as e:
        raise RuntimeError(f"Failed to check transcription status: {str(e)}")


def transcribe_audio(audio_path: str, language: str = "en-US") -> dict:
    """
    Transcribe an audio file using OCI Speech AI service (synchronous).

    This function:
    1. Uploads the audio file to OCI Object Storage
    2. Creates an async transcription job
    3. Polls for job completion (up to 30 minutes)
    4. Downloads and returns the transcription results

    Args:
        audio_path: Path to the audio file on disk
        language: Language code (e.g., "en-US", "es-ES")

    Returns:
        dict with transcription results
    """
    if settings.DEMO_MODE:
        return _simulate_transcription(audio_path, language)

    # Check OCI credentials
    if not all([
        settings.OCI_USER_OCID,
        settings.OCI_TENANCY_OCID,
        settings.OCI_FINGERPRINT,
        settings.OCI_PRIVATE_KEY_PATH,
    ]):
        raise ValueError(
            "OCI credentials not configured. Set OCI_USER_OCID, OCI_TENANCY_OCID, "
            "OCI_FINGERPRINT, and OCI_PRIVATE_KEY_PATH in .env file, "
            "or set DEMO_MODE=true to use demo mode."
        )

    try:
        # Start the job
        job_info = start_transcription_job(audio_path, language)
        job_id = job_info["job_id"]

        # Wait for completion (up to 30 minutes)
        client = _get_speech_client()
        completed_job = _wait_for_job_completion(client, job_id, timeout=1800)

        # Download results
        text = _download_transcription_results(completed_job)

        # Get file size for duration estimation
        file_size = os.path.getsize(audio_path) if os.path.exists(audio_path) else 0
        duration = round(file_size / (1024 * 16), 2) if file_size > 0 else 30.0

        return {
            "job_id": job_id,
            "status": "COMPLETED",
            "text": text,
            "confidence": None,
            "duration_seconds": duration,
            "language": language,
            "is_demo": False,
        }

    except Exception as e:
        raise RuntimeError(f"OCI Speech transcription failed: {str(e)}")
