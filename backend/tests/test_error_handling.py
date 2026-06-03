import json

import pytest

from app.api.chat import live_agent_stream
from app.database.models import UserProfile
from app.services.errors import LLMEmptyResponseError, LLMGatewayError, NewApiProvisionError
from app.services.llm_client import llm_call
from app.services.newapi import NewApiService


class _Message:
    content = ""


class _Choice:
    message = _Message()


class _Usage:
    prompt_tokens = 1
    completion_tokens = 0


class _Response:
    id = "empty-response"
    usage = _Usage()
    choices = [_Choice()]


class _Completions:
    async def create(self, **kwargs):
        return _Response()


class _Chat:
    completions = _Completions()


class _EmptyClient:
    chat = _Chat()


class _FailingWorkflow:
    async def astream(self, state, config):
        yield {"intent_classifier": {"intent": "chat"}}
        raise LLMGatewayError("simulated gateway outage")


@pytest.mark.anyio
async def test_llm_empty_response_is_explicit_error(monkeypatch, anyio_backend):
    monkeypatch.setattr("app.services.llm_client.get_openai_client", lambda **kwargs: _EmptyClient())

    with pytest.raises(LLMEmptyResponseError) as exc:
        await llm_call("system", "user", model="test-model")

    assert exc.value.code == "llm_empty_response"
    assert "空内容" in exc.value.user_message


@pytest.mark.anyio
async def test_newapi_token_provision_error_is_typed(monkeypatch, anyio_backend):
    from app.core.config import settings
    from app.database.session import AsyncSessionLocal

    monkeypatch.setattr(settings, "NEWAPI_SHARED_TOKEN", "")

    async with AsyncSessionLocal() as session:
        with pytest.raises(NewApiProvisionError) as exc:
            await NewApiService.ensure_user_token("test-user-no-newapi-token", session)

    assert exc.value.code == "newapi_token_provision_failed"
    assert exc.value.retryable is True


@pytest.mark.anyio
async def test_live_agent_stream_emits_structured_error(monkeypatch, anyio_backend):
    from app.database.session import AsyncSessionLocal

    monkeypatch.setattr("app.api.chat.app_workflow", _FailingWorkflow())

    async with AsyncSessionLocal() as session:
        user_id = "test-user-stream-error"
        session.add(UserProfile(user_id=user_id))
        await session.commit()

        events = []
        async for event in live_agent_stream("测试错误链路", user_id, "quick", "s1", session):
            events.append(event)

    error_events = [event for event in events if event["event"] == "error"]
    assert error_events
    payload = json.loads(error_events[0]["data"])
    assert payload["code"] == "llm_gateway_failed"
    assert "模型服务暂时不可用" in payload["message"]
    assert events[-1]["event"] == "done"
