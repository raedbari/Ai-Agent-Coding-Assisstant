import json
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.config import get_settings


class RepairPlan(BaseModel):
    summary: str
    root_cause: str
    confidence: str = Field(pattern="^(low|medium|high)$")
    target_file: str | None = None
    proposed_change: str
    patch_strategy: str
    needs_more_context: bool = False
    risk_notes: str = ""


class LLMRepairResponse(BaseModel):
    repair_plan: RepairPlan
    raw_response: dict[str, Any]
    usage: dict[str, Any] | None = None


def parse_json_content(content: str) -> dict[str, Any]:
    content = content.strip()

    if not content:
        raise RuntimeError("LLM returned empty content.")

    try:
        return json.loads(content)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"LLM returned invalid JSON: {error}\nContent:\n{content}") from error


def request_repair_plan(
    messages: list[dict[str, str]],
) -> LLMRepairResponse:
    settings = get_settings()

    url = f"{settings.llm_base_url}/chat/completions"

    request_body: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
        "response_format": {
            "type": "json_object",
        },
        "temperature": 0.2,
        "max_tokens": settings.llm_max_tokens,
        "stream": False,
    }

    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    timeout = httpx.Timeout(settings.llm_timeout_seconds)

    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            url,
            headers=headers,
            json=request_body,
        )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        raise RuntimeError(
            f"LLM API request failed: {response.status_code} {response.text}"
        ) from error

    data = response.json()

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError(f"Unexpected LLM response shape: {data}") from error

    parsed_content = parse_json_content(content)

    repair_plan = RepairPlan.model_validate(parsed_content)

    return LLMRepairResponse(
        repair_plan=repair_plan,
        raw_response=data,
        usage=data.get("usage"),
    )