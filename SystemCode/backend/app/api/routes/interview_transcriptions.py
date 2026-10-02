from fastapi import APIRouter, File, HTTPException, UploadFile

from app.clients.cloudflare_stt_client import (
    CloudflareSTTConfigurationError,
    CloudflareSTTError,
)
from app.core.config import settings
from app.schemas.interview_transcription import InterviewTranscriptionResponse
from app.services.interview_transcription_service import (
    InterviewAudioTooLargeError,
    InterviewAudioValidationError,
    InterviewTranscriptionJobNotFoundError,
    InterviewTranscriptionQuestionNotFoundError,
    InterviewTranscriptionService,
)

router = APIRouter()
interview_transcription_service = InterviewTranscriptionService()


@router.post(
    "/{job_id}/interview-questions/{question_id}/transcription",
    response_model=InterviewTranscriptionResponse,
)
def transcribe_interview_answer(
    job_id: int,
    question_id: int,
    audio: UploadFile = File(...),
) -> InterviewTranscriptionResponse:
    try:
        audio_bytes = audio.file.read(settings.interview_audio_max_bytes + 1)
        return interview_transcription_service.transcribe(
            job_id=job_id,
            question_id=question_id,
            audio=audio_bytes,
            filename=audio.filename,
            content_type=audio.content_type,
        )
    except InterviewTranscriptionJobNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except InterviewTranscriptionQuestionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except InterviewAudioTooLargeError as error:
        raise HTTPException(status_code=413, detail=str(error)) from error
    except InterviewAudioValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except CloudflareSTTConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except CloudflareSTTError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    finally:
        audio.file.close()
