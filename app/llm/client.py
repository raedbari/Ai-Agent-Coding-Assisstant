from langchain_openai import ChatOpenAI

from app.config import get_settings


def get_llm() -> ChatOpenAI:
    settings = get_settings()

    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout_seconds,
    )