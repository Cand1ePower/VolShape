"""
Unified LLM Client for VolShape.
Uses langfuse.openai.AsyncOpenAI when Langfuse is configured for auto-tracing.
Falls back to vanilla openai.AsyncOpenAI otherwise.
"""
import json
import os
import time
from json import JSONDecodeError
from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.services.errors import AppError, LLMEmptyResponseError, LLMGatewayError
from sqlalchemy.ext.asyncio import AsyncSession

_AsyncOpenAI = None
_clients: Dict[str, Any] = {}


def _get_async_openai_class():
    global _AsyncOpenAI
    if _AsyncOpenAI is not None:
        return _AsyncOpenAI

    # Try Langfuse-instrumented OpenAI client first (auto-traces all calls)
    try:
        from langfuse.openai import AsyncOpenAI as LangfuseAsyncOpenAI
        if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_PUBLIC_KEY != "pk-lf-default-mock-key":
            _AsyncOpenAI = LangfuseAsyncOpenAI
            print("[Langfuse] Using langfuse.openai.AsyncOpenAI — all LLM calls will be auto-traced.")
            return _AsyncOpenAI
    except ImportError:
        pass

    # Fallback to vanilla OpenAI
    from openai import AsyncOpenAI as VanillaAsyncOpenAI
    _AsyncOpenAI = VanillaAsyncOpenAI
    return _AsyncOpenAI


def get_openai_client(api_key: Optional[str] = None, base_url: Optional[str] = None):
    key = api_key or settings.DEEPSEEK_API_KEY
    url = base_url or settings.DEEPSEEK_BASE_URL
    cache_key = f"{url}|{key[-8:] if key else ''}"
    if cache_key not in _clients:
        cls = _get_async_openai_class()
        _clients[cache_key] = cls(
            api_key=key,
            base_url=url,
            timeout=30.0,
            max_retries=1,
        )
    return _clients[cache_key]


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
) -> str:
    base_url = settings.DEEPSEEK_BASE_URL
    api_key = settings.DEEPSEEK_API_KEY
    newapi_token = None

    if user_id and db and settings.NEWAPI_BASE_URL and os.getenv("TESTING") != "1":
        from app.services.newapi import NewApiService

        api_key, newapi_token = await NewApiService.get_api_key_for_user(user_id, db)
        base_url = f"{settings.NEWAPI_BASE_URL.rstrip('/')}/v1"

    client = get_openai_client(api_key=api_key, base_url=base_url)
    model = model or settings.LLM_LIGHT_MODEL

    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        kwargs["response_format"] = response_format

    # langfuse.openai.AsyncOpenAI reads LANGFUSE_* env vars automatically
    # We just need to set langfuse_observation_id in extra_headers if needed
    # For auto-tracing, nothing extra is needed — it just works.

    start = time.perf_counter()
    try:
        response = await client.chat.completions.create(**kwargs)
        latency_ms = int((time.perf_counter() - start) * 1000)
        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        request_id = getattr(response, "id", None)
        content = response.choices[0].message.content
        if not content or not content.strip():
            raise LLMEmptyResponseError()
        if user_id and db:
            from app.services.quota import QuotaService

            await QuotaService.record_llm_request(
                user_id=user_id,
                db=db,
                model=model,
                newapi_token=newapi_token,
                session_id=session_id,
                status_value="success",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                request_id=request_id,
            )
        return content.strip()
    except Exception as e:
        if user_id and db:
            from app.services.quota import QuotaService

            await QuotaService.record_llm_request(
                user_id=user_id,
                db=db,
                model=model,
                newapi_token=newapi_token,
                session_id=session_id,
                status_value="error",
                error_code=e.__class__.__name__,
                latency_ms=int((time.perf_counter() - start) * 1000),
            )
        if isinstance(e, AppError):
            raise
        raise LLMGatewayError(str(e), details={"error_type": e.__class__.__name__}) from e


async def llm_call_structured(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    user_id: Optional[str] = None,
    db: Optional[AsyncSession] = None,
    session_id: Optional[str] = None,
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
    )
    try:
        return json.loads(text)
    except JSONDecodeError as e:
        raise LLMGatewayError(
            "LLM structured response was not valid JSON",
            details={"error_type": e.__class__.__name__},
        ) from e
