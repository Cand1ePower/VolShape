import datetime
import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.chat import _ensure_conversation_sessions, _load_history
from app.core.config import settings
from app.database.models import AppUser, ConversationMessage, ConversationSession
from app.database.session import AsyncSessionLocal
from app.main import app
from app.services.llm_client import llm_call

client = TestClient(app)


@pytest.mark.anyio
async def test_read_root(anyio_backend):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "online"
    assert "VolShape Backend Service" in response.json()["app"]


@pytest.mark.anyio
async def test_auth_unauthorized(anyio_backend):
    response = client.post("/api/chat/stream", json={"user_input": "test"})
    assert response.status_code == 401


@pytest.mark.anyio
async def test_auth_development_bypass(anyio_backend):
    old_env = settings.ENV
    settings.ENV = "development"
    try:
        headers = {"Authorization": "Bearer test-user-candlepw"}
        response = client.post(
            "/api/chat/stream",
            json={"user_input": "今天想练胸部", "session_id": "test_sess"},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert "event: state" in response.text
        assert "Intent Classifier" in response.text
    finally:
        settings.ENV = old_env


class _FakeChoice:
    def __init__(self, content: str):
        self.message = type("Message", (), {"content": content})()


class _FakeResponse:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]
        self.usage = type("Usage", (), {"prompt_tokens": 1, "completion_tokens": 1})()
        self.id = "req_test"


class _FakeLangfuseClient:
    __module__ = "langfuse.openai"

    def __init__(self, sink: dict):
        self.chat = type("Chat", (), {})()
        self.chat.completions = type("Completions", (), {})()

        async def create(**kwargs):
            sink.update(kwargs)
            return _FakeResponse("ok")

        self.chat.completions.create = create


class _FakeVanillaClient:
    __module__ = "openai"

    def __init__(self, sink: dict):
        self.chat = type("Chat", (), {})()
        self.chat.completions = type("Completions", (), {})()

        async def create(**kwargs):
            sink.update(kwargs)
            return _FakeResponse("ok")

        self.chat.completions.create = create


@pytest.mark.anyio
async def test_llm_call_passes_langfuse_parent_only_to_langfuse_client(monkeypatch, anyio_backend):
    captured_langfuse = {}
    monkeypatch.setattr("app.services.llm_client.get_openai_client", lambda **kwargs: _FakeLangfuseClient(captured_langfuse))
    await llm_call("system", "user", langfuse_parent="parent-123")
    assert captured_langfuse["langfuse_parent"] == "parent-123"

    captured_vanilla = {}
    monkeypatch.setattr("app.services.llm_client.get_openai_client", lambda **kwargs: _FakeVanillaClient(captured_vanilla))
    await llm_call("system", "user", langfuse_parent="parent-456")
    assert "langfuse_parent" not in captured_vanilla


@pytest.mark.anyio
async def test_load_history_returns_latest_messages_in_chronological_order(anyio_backend):
    user_id = f"test-history-window-user-{uuid.uuid4()}"
    session_id = f"test-history-session-{uuid.uuid4()}"

    async with AsyncSessionLocal() as db:
        base_time = datetime.datetime(2026, 1, 1, 12, 0, 0)
        for idx in range(60):
            db.add(
                ConversationMessage(
                    id=f"hist-{idx}-{uuid.uuid4()}",
                    user_id=user_id,
                    session_id=session_id,
                    role="user" if idx % 2 == 0 else "assistant",
                    content=f"message-{idx}",
                    created_at=base_time + datetime.timedelta(seconds=idx),
                )
            )
        await db.commit()

        history = await _load_history(user_id, session_id, db)

    assert len(history) == 50
    assert history[0]["content"] == "message-10"
    assert history[-1]["content"] == "message-59"


@pytest.mark.anyio
async def test_ensure_conversation_sessions_backfills_legacy_message_thread(anyio_backend):
    user_id = f"legacy-user-{uuid.uuid4()}"
    session_id = f"legacy-session-{uuid.uuid4()}"

    async with AsyncSessionLocal() as db:
        db.add(AppUser(id=user_id, email=f"{user_id}@example.com", username=user_id, role="user", status="active"))
        db.add(
            ConversationMessage(
                id=str(uuid.uuid4()),
                user_id=user_id,
                session_id=session_id,
                role="user",
                content="昨天练腿了",
                created_at=datetime.datetime(2026, 6, 1, 8, 0, 0),
            )
        )
        db.add(
            ConversationMessage(
                id=str(uuid.uuid4()),
                user_id=user_id,
                session_id=session_id,
                role="assistant",
                content="记录好了",
                created_at=datetime.datetime(2026, 6, 1, 8, 1, 0),
            )
        )
        await db.commit()

        sessions = await _ensure_conversation_sessions(user_id, db)

    assert len(sessions) == 1
    assert sessions[0].id == session_id
    assert sessions[0].title == "昨天练腿了"


@pytest.mark.anyio
async def test_list_chat_sessions_returns_default_session_for_new_user(anyio_backend):
    old_env = settings.ENV
    settings.ENV = "development"
    try:
        headers = {"Authorization": "Bearer test-user-fresh-session-list"}
        response = client.get("/api/chat/sessions", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) == 1
        assert data["active_session_id"] == data["sessions"][0]["id"]
    finally:
        settings.ENV = old_env


@pytest.mark.anyio
async def test_list_chat_sessions_orders_pinned_session_first(anyio_backend):
    user_id = f"pin-user-{uuid.uuid4()}"
    pinned_session_id = f"pin-session-{uuid.uuid4()}"
    regular_session_id = f"regular-session-{uuid.uuid4()}"

    async with AsyncSessionLocal() as db:
        db.add(AppUser(id=user_id, email=f"{user_id}@example.com", username=user_id, role="user", status="active"))
        db.add(
            ConversationSession(
                id=regular_session_id,
                user_id=user_id,
                title="regular",
                created_at=datetime.datetime(2026, 6, 1, 8, 0, 0),
                updated_at=datetime.datetime(2026, 6, 1, 8, 5, 0),
                last_message_at=datetime.datetime(2026, 6, 1, 8, 5, 0),
            )
        )
        db.add(
            ConversationSession(
                id=pinned_session_id,
                user_id=user_id,
                title="pinned",
                created_at=datetime.datetime(2026, 6, 1, 7, 0, 0),
                updated_at=datetime.datetime(2026, 6, 1, 7, 5, 0),
                pinned_at=datetime.datetime(2026, 6, 3, 9, 0, 0),
                last_message_at=datetime.datetime(2026, 6, 1, 7, 5, 0),
            )
        )
        await db.commit()

        sessions = await _ensure_conversation_sessions(user_id, db)

    assert sessions[0].id == pinned_session_id
    assert sessions[1].id == regular_session_id
