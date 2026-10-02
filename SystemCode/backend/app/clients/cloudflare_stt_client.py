from __future__ import annotations

import base64

import httpx

from app.core.config import settings


class CloudflareSTTConfigurationError(RuntimeError):
    pass


class CloudflareSTTError(RuntimeError):
    pass


class CloudflareSTTClient:
    def __init__(
        self,
        account_id: str | None = None,
        api_token: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.account_id = settings.cloudflare_account_id if account_id is None else account_id
        self.api_token = settings.cloudflare_api_token if api_token is None else api_token
        self.model = settings.cloudflare_stt_model if model is None else model
        self.timeout_seconds = (
            settings.cloudflare_stt_timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        )
        self.http_client = http_client

    def transcribe(self, audio: bytes, initial_prompt: str) -> str:
        if not self.account_id or not self.api_token:
            raise CloudflareSTTConfigurationError(
                "Cloudflare speech-to-text credentials are not configured."
            )

        url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{self.account_id}/ai/run/{self.model}"
        )
        payload = {
            "audio": base64.b64encode(audio).decode("ascii"),
            "task": "transcribe",
            "language": "en",
            "vad_filter": True,
            "initial_prompt": initial_prompt,
        }
        headers = {"Authorization": f"Bearer {self.api_token}"}

        try:
            if self.http_client is not None:
                response = self.http_client.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout_seconds,
                )
            else:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(url, headers=headers, json=payload)
        except httpx.RequestError as error:
            raise CloudflareSTTError(
                "The speech-to-text service could not be reached."
            ) from error

        if response.status_code >= 400:
            raise CloudflareSTTError(
                f"The speech-to-text service returned HTTP {response.status_code}."
            )

        try:
            body = response.json()
        except ValueError as error:
            raise CloudflareSTTError(
                "The speech-to-text service returned an invalid response."
            ) from error

        if not isinstance(body, dict) or not body.get("success", False):
            raise CloudflareSTTError("The speech-to-text service rejected the request.")

        result = body.get("result") or {}
        if not isinstance(result, dict):
            raise CloudflareSTTError(
                "The speech-to-text service returned an invalid response."
            )
        transcript = result.get("text")
        if not transcript and isinstance(result.get("transcription_info"), dict):
            transcript = result["transcription_info"].get("text")
        if not isinstance(transcript, str) or not transcript.strip():
            raise CloudflareSTTError(
                "The speech-to-text service returned an empty transcript."
            )
        return " ".join(transcript.split())
