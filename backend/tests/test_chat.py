import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)

@pytest.mark.anyio
async def test_read_root(anyio_backend):
    """测试根节点健康检查"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "online"
    assert "VolShape Backend Service" in response.json()["app"]


@pytest.mark.anyio
async def test_auth_unauthorized(anyio_backend):
    """测试未授权请求流式接口时返回 401"""
    response = client.post("/api/chat/stream", json={"user_input": "测试输入"})
    assert response.status_code == 401


@pytest.mark.anyio
async def test_auth_development_bypass(anyio_backend):
    """测试本地开发环境（ENV=development）下的 mock 认证后门是否正常工作"""
    # 强制将配置设为 development 环境进行测试
    old_env = settings.ENV
    settings.ENV = "development"
    
    try:
        # 携带以 test-user- 开头的 Token 进行请求
        headers = {"Authorization": "Bearer test-user-candlepw"}
        response = client.post(
            "/api/chat/stream",
            json={"user_input": "今天想练胸部，但肩膀有点不舒服", "session_id": "test_sess"},
            headers=headers
        )
        
        # 验证通过并进入流式传输
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        
        # 读取流式响应内容，确保返回包含 mock Agent 节点状态
        stream_content = response.text
        assert "event: state" in stream_content
        assert "node" in stream_content
        assert "Intent Classifier" in stream_content
        
    finally:
        # 还原配置
        settings.ENV = old_env
