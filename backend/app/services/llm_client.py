"""
Unified LLM Client for VolShape.
Uses langfuse.openai.AsyncOpenAI when Langfuse is configured for auto-tracing.
Falls back to vanilla openai.AsyncOpenAI otherwise.
"""
import json
from typing import Any, Dict, List, Optional
from app.core.config import settings

_AsyncOpenAI = None
_client = None


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


def get_openai_client():
    global _client
    if _client is None:
        cls = _get_async_openai_class()
        _client = cls(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            timeout=30.0,
            max_retries=1,
        )
    return _client


async def llm_call(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    response_format: Optional[Dict[str, str]] = None,
    trace_name: str = "llm_call",
) -> str:
    client = get_openai_client()
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

    response = await client.chat.completions.create(**kwargs)
    return response.choices[0].message.content.strip()


async def llm_call_structured(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> Dict[str, Any]:
    text = await llm_call(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        trace_name="llm_call_structured",
    )
    return json.loads(text)
