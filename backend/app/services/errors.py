from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AppError(Exception):
    code: str
    user_message: str
    technical_message: str = ""
    retryable: bool = False
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.technical_message or self.user_message

    def to_payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.user_message,
            "retryable": self.retryable,
            "details": self.details or {},
        }


class NewApiProvisionError(AppError):
    def __init__(self, technical_message: str = "", details: dict[str, Any] | None = None):
        super().__init__(
            code="newapi_token_provision_failed",
            user_message="模型网关账号初始化失败，请稍后重试或联系管理员检查 New API 配置。",
            technical_message=technical_message,
            retryable=True,
            details=details,
        )


class LLMGatewayError(AppError):
    def __init__(self, technical_message: str = "", details: dict[str, Any] | None = None):
        super().__init__(
            code="llm_gateway_failed",
            user_message="模型服务暂时不可用，我已停止本次处理以避免生成不可靠结果。",
            technical_message=technical_message,
            retryable=True,
            details=details,
        )


class LLMEmptyResponseError(AppError):
    def __init__(self, technical_message: str = "LLM returned empty content"):
        super().__init__(
            code="llm_empty_response",
            user_message="模型返回了空内容，本次没有生成有效回复，请稍后再试。",
            technical_message=technical_message,
            retryable=True,
        )


def error_payload(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, AppError):
        return exc.to_payload()
    return {
        "code": "workflow_unhandled_error",
        "message": "系统处理本次消息时出现异常，本次结果已停止生成。",
        "retryable": True,
        "details": {"error_type": exc.__class__.__name__},
    }
