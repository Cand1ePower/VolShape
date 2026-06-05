"""
Unified LLM client for VolShape.

Supports both plain text prompts and richer OpenAI-compatible message payloads,
including multimodal content blocks for image analysis.
"""

import json
import os
import time
from json import JSONDecodeError
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.errors import AppError, LLMEmptyResponseError, LLMGatewayError

_AsyncOpenAI = None
_VanillaAsyncOpenAI = None
_clients: Dict[str, Any] = {}

RESPONSE_STYLE_GUIDANCE = """

[VolShape response style]
- Use a professional fitness-coach tone. Do not use casual buddy terms such as "兄弟", "哥们", "老铁".
- Be specific, evidence-based, and calm. Prefer actionable coaching over hype.
- For user-facing final answers, provide enough detail to be useful: usually 250-450 Chinese characters unless the user asks for brevity.
- When training history is available, explicitly mention completed sets versus planned sets if relevant.
- Format user-facing final answers for mobile readability:
  - Split content into 2-5 short paragraphs instead of one long block.
  - Use Markdown bold for key labels or conclusions, such as **结论**、**热量估算**、**建议**.
  - When giving several concrete points, use short bullet lines beginning with "- ".
  - Keep each paragraph compact, usually 1-3 sentences.
"""


def _get_async_openai_class(trace_enabled: bool = True):
    global _AsyncOpenAI, _VanillaAsyncOpenAI

    if not trace_enabled:
        if _VanillaAsyncOpenAI is None:
            from openai import AsyncOpenAI as VanillaAsyncOpenAI

            _VanillaAsyncOpenAI = VanillaAsyncOpenAI
        return _VanillaAsyncOpenAI

    if _AsyncOpenAI is not None:
        return _AsyncOpenAI

    try:
        from langfuse.openai import AsyncOpenAI as LangfuseAsyncOpenAI

        if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_PUBLIC_KEY != "pk-lf-default-mock-key":
            _AsyncOpenAI = LangfuseAsyncOpenAI
            print("[Langfuse] Using langfuse.openai.AsyncOpenAI for auto-tracing.")
            return _AsyncOpenAI
    except ImportError:
        pass

    from openai import AsyncOpenAI as VanillaAsyncOpenAI

    _AsyncOpenAI = VanillaAsyncOpenAI
    _VanillaAsyncOpenAI = VanillaAsyncOpenAI
    return _AsyncOpenAI


def get_openai_client(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    *,
    trace_enabled: bool = True,
):
    key = api_key or settings.DEEPSEEK_API_KEY
    url = base_url or settings.DEEPSEEK_BASE_URL
    cache_key = f"{url}|{key[-8:] if key else ''}|{'trace' if trace_enabled else 'plain'}"
    if cache_key not in _clients:
        cls = _get_async_openai_class(trace_enabled=trace_enabled)
        _clients[cache_key] = cls(
            api_key=key,
            base_url=url,
            timeout=30.0,
            max_retries=1,
        )
    return _clients[cache_key]


def _client_supports_langfuse_parent(client: Any) -> bool:
    module = getattr(client.__class__, "__module__", "") or ""
    return module.startswith("langfuse.")


def _prepare_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    prepared = [dict(message) for message in messages]
    if prepared and prepared[0].get("role") == "system" and isinstance(prepared[0].get("content"), str):
        prepared[0]["content"] = f"{prepared[0]['content']}{RESPONSE_STYLE_GUIDANCE}"
        return prepared
    return [{"role": "system", "content": RESPONSE_STYLE_GUIDANCE.strip()}] + prepared


async def _resolve_client_and_model(
    *,
    model: Optional[str],
    user_id: Optional[str],
    db: Optional[AsyncSession],
    trace_enabled: bool = True,
):
    base_url = settings.DEEPSEEK_BASE_URL
    api_key = settings.DEEPSEEK_API_KEY
    newapi_token = None

    if user_id and db and settings.NEWAPI_BASE_URL and os.getenv("TESTING") != "1":
        from app.services.newapi import NewApiService

        api_key, newapi_token = await NewApiService.get_api_key_for_user(user_id, db)
        base_url = f"{settings.NEWAPI_BASE_URL.rstrip('/')}/v1"

    client = get_openai_client(api_key=api_key, base_url=base_url, trace_enabled=trace_enabled)
    resolved_model = model or settings.LLM_LIGHT_MODEL
    return client, resolved_model, newapi_token


async def _record_request(
    *,
    user_id: Optional[str],
    db: Optional[AsyncSession],
    model: str,
    newapi_token: Any,
    session_id: Optional[str],
    status_value: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    latency_ms: int = 0,
    error_code: Optional[str] = None,
    request_id: Optional[str] = None,
) -> None:
    if not (user_id and db):
        return

    from app.services.quota import QuotaService

    await QuotaService.record_llm_request(
        user_id=user_id,
        db=db,
        model=model,
        newapi_token=newapi_token,
        session_id=session_id,
        status_value=status_value,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency_ms,
        error_code=error_code,
        request_id=request_id,
    )


async def llm_call_messages(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    response_format: Optional[Dict[str, str]] = None,
    user_id: Optional[str] = None,
    db: Optional[AsyncSession] = None,
    session_id: Optional[str] = None,
    langfuse_parent: Optional[Any] = None,
    trace_enabled: bool = True,
) -> str:
    client, resolved_model, newapi_token = await _resolve_client_and_model(
        model=model,
        user_id=user_id,
        db=db,
        trace_enabled=trace_enabled,
    )

    kwargs: Dict[str, Any] = {
        "model": resolved_model,
        "messages": _prepare_messages(messages),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        kwargs["response_format"] = response_format
    if langfuse_parent is not None:
        try:
            kwargs["langfuse_parent"] = langfuse_parent
        except Exception:
            pass
    if not _client_supports_langfuse_parent(client):
        kwargs.pop("langfuse_parent", None)

    start = time.perf_counter()
    try:
        response = await client.chat.completions.create(**kwargs)
        latency_ms = int((time.perf_counter() - start) * 1000)
        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        request_id = getattr(response, "id", None)
        content = response.choices[0].message.content
        if not content or not str(content).strip():
            raise LLMEmptyResponseError()

        await _record_request(
            user_id=user_id,
            db=db,
            model=resolved_model,
            newapi_token=newapi_token,
            session_id=session_id,
            status_value="success",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            request_id=request_id,
        )
        return str(content).strip()
    except Exception as e:
        await _record_request(
            user_id=user_id,
            db=db,
            model=resolved_model,
            newapi_token=newapi_token,
            session_id=session_id,
            status_value="error",
            latency_ms=int((time.perf_counter() - start) * 1000),
            error_code=e.__class__.__name__,
        )
        if isinstance(e, AppError):
            raise
        raise LLMGatewayError(str(e), details={"error_type": e.__class__.__name__}) from e


async def llm_call(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    response_format: Optional[Dict[str, str]] = None,
    trace_name: str = "llm_call",
    user_id: Optional[str] = None,
    db: Optional[AsyncSession] = None,
    session_id: Optional[str] = None,
    langfuse_parent: Optional[Any] = None,
    trace_enabled: bool = True,
) -> str:
    del trace_name
    return await llm_call_messages(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
        user_id=user_id,
        db=db,
        session_id=session_id,
        langfuse_parent=langfuse_parent,
        trace_enabled=trace_enabled,
    )


async def llm_call_structured(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    user_id: Optional[str] = None,
    db: Optional[AsyncSession] = None,
    session_id: Optional[str] = None,
    langfuse_parent: Optional[Any] = None,
    trace_enabled: bool = True,
) -> Dict[str, Any]:
    text = await llm_call(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        trace_name="llm_call_structured",
        user_id=user_id,
        db=db,
        session_id=session_id,
        langfuse_parent=langfuse_parent,
        trace_enabled=trace_enabled,
    )
    try:
        return json.loads(text)
    except JSONDecodeError as e:
        raise LLMGatewayError(
            "LLM structured response was not valid JSON",
            details={"error_type": e.__class__.__name__},
        ) from e


async def llm_call_messages_structured(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    user_id: Optional[str] = None,
    db: Optional[AsyncSession] = None,
    session_id: Optional[str] = None,
    langfuse_parent: Optional[Any] = None,
    trace_enabled: bool = True,
) -> Dict[str, Any]:
    text = await llm_call_messages(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        user_id=user_id,
        db=db,
        session_id=session_id,
        langfuse_parent=langfuse_parent,
        trace_enabled=trace_enabled,
    )
    try:
        return json.loads(text)
    except JSONDecodeError as e:
        raise LLMGatewayError(
            "LLM structured response was not valid JSON",
            details={"error_type": e.__class__.__name__},
        ) from e
