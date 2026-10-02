from __future__ import annotations

from pathlib import Path

from app.clients.cloudflare_stt_client import CloudflareSTTClient
from app.core.config import settings
from app.repositories.interview_recommendation_repository import (
    InterviewRecommendationRepository,
)
from app.schemas.interview_transcription import InterviewTranscriptionResponse


SUPPORTED_AUDIO_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/ogg",
    "audio/wav",
    "audio/webm",
    "video/mp4",
    "video/webm",
}
SUPPORTED_AUDIO_SUFFIXES = {".m4a", ".mp3", ".mp4", ".ogg", ".wav", ".webm"}


class InterviewTranscriptionJobNotFoundError(LookupError):
    pass


class InterviewTranscriptionQuestionNotFoundError(LookupError):
    pass


class InterviewAudioValidationError(ValueError):
    pass


class InterviewAudioTooLargeError(InterviewAudioValidationError):
    pass


class InterviewTranscriptionService:
    def __init__(
        self,
        repository: InterviewRecommendationRepository | None = None,
        client: CloudflareSTTClient | None = None,
        max_audio_bytes: int | None = None,
    ) -> None:
        self.repository = repository or InterviewRecommendationRepository()
        self.client = client or CloudflareSTTClient()
        self.max_audio_bytes = (
            settings.interview_audio_max_bytes
            if max_audio_bytes is None
            else max_audio_bytes
        )

    def transcribe(
        self,
        job_id: int,
        question_id: int,
        audio: bytes,
        filename: str | None,
        content_type: str | None,
    ) -> InterviewTranscriptionResponse:
        self._validate_audio(audio, filename, content_type)

        job = self.repository.get_job_context(job_id)
        if job is None:
            raise InterviewTranscriptionJobNotFoundError(
                f"Job {job_id} was not found."
            )

        question = self.repository.get_question_context(question_id)
        if question is None:
            raise InterviewTranscriptionQuestionNotFoundError(
                f"Interview question {question_id} was not found."
            )

        role_matches = self.repository.list_role_matches(job_id, limit=3)
        role_names = ", ".join(item.role for item in role_matches)
        context_parts = [
            "Transcribe an English interview answer accurately.",
            f"Job title: {job.title}.",
            f"Interview question: {question.question_text_en}.",
        ]
        if role_names:
            context_parts.append(f"Relevant role terminology: {role_names}.")

        transcript = self.client.transcribe(audio, " ".join(context_parts))
        return InterviewTranscriptionResponse(
            job_id=job_id,
            question_id=question_id,
            transcript=transcript,
            model=self.client.model,
        )

    def _validate_audio(
        self,
        audio: bytes,
        filename: str | None,
        content_type: str | None,
    ) -> None:
        if not audio:
            raise InterviewAudioValidationError("The uploaded audio file is empty.")
        if len(audio) > self.max_audio_bytes:
            limit_mb = self.max_audio_bytes // (1024 * 1024)
            raise InterviewAudioTooLargeError(
                f"The uploaded audio file exceeds the {limit_mb} MB limit."
            )

        suffix = Path(filename or "").suffix.casefold()
        normalized_type = (content_type or "").split(";", 1)[0].strip().casefold()
        type_supported = normalized_type in SUPPORTED_AUDIO_TYPES
        suffix_supported = suffix in SUPPORTED_AUDIO_SUFFIXES
        if not type_supported and not suffix_supported:
            raise InterviewAudioValidationError(
                "Unsupported audio format. Use WebM, WAV, MP3, M4A, MP4, or OGG."
            )
