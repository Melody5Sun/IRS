import base64

import httpx
from fastapi.testclient import TestClient
import pytest

from app.api.routes import interview_transcriptions as transcription_route
from app.clients.cloudflare_stt_client import (
    CloudflareSTTClient,
    CloudflareSTTConfigurationError,
    CloudflareSTTError,
)
from app.main import app
from app.repositories.interview_recommendation_repository import (
    InterviewJobContext,
    InterviewQuestionContext,
    InterviewRoleMatch,
)
from app.schemas.interview_transcription import InterviewTranscriptionResponse
from app.services.interview_transcription_service import (
    InterviewAudioTooLargeError,
    InterviewAudioValidationError,
    InterviewTranscriptionJobNotFoundError,
    InterviewTranscriptionQuestionNotFoundError,
    InterviewTranscriptionService,
)


class FakeRepository:
    def __init__(self, *, job_exists: bool = True, question_exists: bool = True):
        self.job_exists = job_exists
        self.question_exists = question_exists

    def get_job_context(self, job_id: int):
        if not self.job_exists:
            return None
        return InterviewJobContext(job_id=job_id, title="Backend Engineer Intern")

    def get_question_context(self, question_id: int):
        if not self.question_exists:
            return None
        return InterviewQuestionContext(
            question_id=question_id,
            question_text_en="How would you design a reliable REST API?",
        )

    def list_role_matches(self, job_id: int, limit: int = 3):
        return [
            InterviewRoleMatch(role="Backend Developer", similarity=0.8, rank=1),
            InterviewRoleMatch(role="Full Stack Developer", similarity=0.6, rank=2),
        ][:limit]


class FakeCloudflareClient:
    model = "@cf/openai/whisper-large-v3-turbo"

    def __init__(self):
        self.prompt = ""

    def transcribe(self, audio: bytes, initial_prompt: str) -> str:
        self.prompt = initial_prompt
        return "I designed the API with FastAPI and PostgreSQL."


def test_service_returns_english_transcript_with_interview_context() -> None:
    client = FakeCloudflareClient()
    service = InterviewTranscriptionService(FakeRepository(), client)

    response = service.transcribe(74, 1024, b"audio", "answer.webm", "audio/webm")

    assert response.model_dump() == {
        "job_id": 74,
        "question_id": 1024,
        "transcript": "I designed the API with FastAPI and PostgreSQL.",
        "language": "en",
        "model": "@cf/openai/whisper-large-v3-turbo",
    }
    assert "Backend Engineer Intern" in client.prompt
    assert "How would you design a reliable REST API?" in client.prompt
    assert "Backend Developer" in client.prompt


def test_service_validates_job_question_and_audio() -> None:
    with pytest.raises(InterviewTranscriptionJobNotFoundError):
        InterviewTranscriptionService(
            FakeRepository(job_exists=False), FakeCloudflareClient()
        ).transcribe(999, 1, b"audio", "answer.webm", "audio/webm")

    with pytest.raises(InterviewTranscriptionQuestionNotFoundError):
        InterviewTranscriptionService(
            FakeRepository(question_exists=False), FakeCloudflareClient()
        ).transcribe(1, 999, b"audio", "answer.webm", "audio/webm")

    service = InterviewTranscriptionService(
        FakeRepository(), FakeCloudflareClient(), max_audio_bytes=4
    )
    with pytest.raises(InterviewAudioValidationError):
        service.transcribe(1, 1, b"", "answer.webm", "audio/webm")
    with pytest.raises(InterviewAudioTooLargeError):
        service.transcribe(1, 1, b"12345", "answer.webm", "audio/webm")
    with pytest.raises(InterviewAudioValidationError):
        InterviewTranscriptionService(
            FakeRepository(), FakeCloudflareClient()
        ).transcribe(1, 1, b"audio", "answer.txt", "text/plain")


def test_cloudflare_client_sends_base64_audio_and_extracts_text() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["authorization"]
        captured["body"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {"text": "  A clear   interview answer.  "},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = CloudflareSTTClient(
            account_id="account",
            api_token="secret",
            http_client=http_client,
        )
        transcript = client.transcribe(b"audio", "Interview context")

    assert transcript == "A clear interview answer."
    assert captured["authorization"] == "Bearer secret"
    assert base64.b64encode(b"audio").decode("ascii") in captured["body"]
    assert "Interview context" in captured["body"]


def test_cloudflare_client_requires_credentials_and_handles_provider_errors() -> None:
    with pytest.raises(CloudflareSTTConfigurationError):
        CloudflareSTTClient(account_id="", api_token="").transcribe(b"audio", "prompt")

    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(429))
    ) as http_client:
        with pytest.raises(CloudflareSTTError, match="HTTP 429"):
            CloudflareSTTClient(
                account_id="account",
                api_token="secret",
                http_client=http_client,
            ).transcribe(b"audio", "prompt")


class FakeRouteService:
    def transcribe(self, job_id, question_id, audio, filename, content_type):
        return InterviewTranscriptionResponse(
            job_id=job_id,
            question_id=question_id,
            transcript="My answer in English.",
            model="@cf/openai/whisper-large-v3-turbo",
        )


def test_api_accepts_audio_upload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        transcription_route,
        "interview_transcription_service",
        FakeRouteService(),
    )

    response = TestClient(app).post(
        "/api/jobs/74/interview-questions/1024/transcription",
        files={"audio": ("answer.webm", b"audio", "audio/webm")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "job_id": 74,
        "question_id": 1024,
        "transcript": "My answer in English.",
        "language": "en",
        "model": "@cf/openai/whisper-large-v3-turbo",
    }
