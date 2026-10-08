from typing import Protocol

from app.core.config import settings

GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


class LLMNotConfiguredError(RuntimeError):
    """Raised when an endpoint requiring the LLM is called before it is configured."""


class ChatClient(Protocol):
    """LLM 调用的最小接口，测试里可以换成打桩实现。"""

    def complete(self, *, system_prompt: str, user_prompt: str) -> str: ...


def llm_connection_settings() -> tuple[str | None, str | None, str | None]:
    """Resolve an explicit OpenAI-compatible provider, then fall back to Gemini."""
    if settings.llm_api_key and settings.llm_base_url and settings.llm_model:
        return settings.llm_api_key, settings.llm_base_url, settings.llm_model
    if settings.gemini_api_key and settings.gemini_model:
        return settings.gemini_api_key, GEMINI_OPENAI_BASE_URL, settings.gemini_model
    return None, None, None


class OpenAICompatibleClient:
    """走 OpenAI 兼容的 chat completions 接口。

    供应商由 .env 里的 LLM_BASE_URL/LLM_MODEL/LLM_API_KEY 决定，尚未确定具体接哪家，
    这三项目前都是空占位；真正发起请求时才检查配置是否齐全。
    """

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        api_key, base_url, model = llm_connection_settings()
        if not (api_key and base_url and model):
            raise LLMNotConfiguredError(
                "LLM 未配置：请在仓库根目录 .env 中设置 GEMINI_API_KEY，或完整设置 "
                "LLM_API_KEY / LLM_BASE_URL / LLM_MODEL。"
            )

        # 延迟导入：LLM 供应商未配置时不强制要求已安装/初始化 openai 客户端
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""
