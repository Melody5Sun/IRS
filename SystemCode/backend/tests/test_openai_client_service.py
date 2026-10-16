import httpx
import openai
import pytest

from app.core.config import settings
from app.services import openai_client_service
from app.services.openai_client_service import GEMINI_OPENAI_BASE_URL, OpenAICompatibleClient


def _status_error(status: int) -> openai.APIStatusError:
    response = httpx.Response(status, request=httpx.Request("POST", GEMINI_OPENAI_BASE_URL))
    return openai.APIStatusError("error", response=response, body=None)


class FakeOpenAI:
    """按顺序返回预设结果，记录每次请求用的模型。"""

    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.models: list[str] = []
        self.chat = self
        self.completions = self

    def __call__(self, **_kwargs: object) -> "FakeOpenAI":
        return self

    def create(self, *, model: str, **_kwargs: object) -> object:
        self.models.append(model)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        message = type("Message", (), {"content": outcome})()
        return type("Response", (), {"choices": [type("Choice", (), {"message": message})()]})()


@pytest.fixture
def gemini(monkeypatch):
    monkeypatch.setattr(openai_client_service, "llm_connection_settings", lambda: ("key", GEMINI_OPENAI_BASE_URL, "main-model"))
    monkeypatch.setattr(settings, "gemini_model", "lite-model")

    def install(outcomes: list[object]) -> FakeOpenAI:
        fake = FakeOpenAI(outcomes)
        monkeypatch.setattr(openai, "OpenAI", fake)
        return fake

    return install


def test_overloaded_main_model_falls_back_to_gemini_model(gemini) -> None:
    fake = gemini([_status_error(503), '{"ok": true}'])

    assert OpenAICompatibleClient().complete(system_prompt="s", user_prompt="u") == '{"ok": true}'
    assert fake.models == ["main-model", "lite-model"]


def test_other_errors_are_not_retried_on_fallback(gemini) -> None:
    fake = gemini([_status_error(400)])

    with pytest.raises(openai.APIStatusError):
        OpenAICompatibleClient().complete(system_prompt="s", user_prompt="u")
    assert fake.models == ["main-model"]
