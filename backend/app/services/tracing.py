"""
VolShape Langfuse Tracing 工具
==============================
使用 langfuse_context (observe 模式) 实现全链路追踪。

核心原理：
  langfuse.openai 的 patched AsyncOpenAI 会自动读取 langfuse_context 中的
  当前 observation，并将 LLM Generation 嵌套到该 observation 下。
  因此只要在每个节点中正确调用 langfuse_context.update_current_observation()，
  就能自动实现：

  Trace: volshape_chat_quick
    ├── Span: intent_classifier
    │     └── Generation: deepseek-chat
    ├── Span: profile_retrieval
    ├── Span: planner
    │     └── Generation: deepseek-chat
    └── Span: quick_combined
          └── Generation: deepseek-chat

关键：使用 langfuse_context.update_current_trace() 来绑定 trace_id，
      使 langfuse.openai 的 auto-tracing 自动嵌套到我们的 trace 下。
"""
from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Optional, Tuple

from app.core.config import settings


def _is_langfuse_enabled() -> bool:
    return bool(
        settings.LANGFUSE_PUBLIC_KEY
        and settings.LANGFUSE_PUBLIC_KEY != "pk-lf-default-mock-key"
        and settings.LANGFUSE_SECRET_KEY
        and settings.LANGFUSE_SECRET_KEY != "sk-lf-default-mock-key"
    )


# ── 单例 Langfuse 客户端 ────────────────────────────────────────
_langfuse_client = None


def get_langfuse_client():
    """获取 Langfuse 客户端单例实例"""
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client
    if not _is_langfuse_enabled():
        return None
    try:
        from langfuse import Langfuse
        _langfuse_client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
        return _langfuse_client
    except Exception as e:
        print(f"[Langfuse] Failed to create client: {e}")
        return None


def create_trace(
    user_id: str,
    session_id: str,
    mode: str,
    user_input: str,
) -> Tuple[Optional[Any], Optional[str]]:
    """
    在一次对话入口处创建顶级 Trace。
    返回 (trace, trace_id)，Langfuse 未配置时均为 None。
    """
    lf = get_langfuse_client()
    if lf is None:
        return None, None

    try:
        trace = lf.start_observation(
            name=f"volshape_chat_{mode}",
            as_type="span",
            input={"user_input": user_input, "mode": mode},
            metadata={"mode": mode, "session_id": session_id, "user_id": user_id},
        )
        return trace, getattr(trace, "trace_id", None) or getattr(trace, "id", None)
    except Exception as e:
        print(f"[Langfuse] create_trace failed: {e}")
        return None, None


def finish_trace(trace: Optional[Any], final_response: str, intent: str = "", metadata: dict | None = None):
    """在对话结束时更新顶级 Trace 的 output 字段并 flush"""
    if trace is None:
        return
    try:
        trace.update(output={"final_response": final_response[:500], "intent": intent}, metadata=metadata or {})
        if hasattr(trace, "end"):
            trace.end()
        lf = get_langfuse_client()
        if lf:
            lf.flush()
    except Exception as e:
        print(f"[Langfuse] finish_trace failed: {e}")


class NodeSpan:
    """
    在一个 LangGraph 节点内使用的 Span 上下文管理器。
    
    核心改进：将 span 对象传递给 langfuse.openai 作为 parent，
    使 LLM Generation 自动嵌套在节点 span 下。

    用法:
        with NodeSpan(trace, "intent_classifier", input_data={...}) as span:
            result = await _safe_llm_structured(..., langfuse_parent=span.observation)
            span.set_output(result)
    """

    def __init__(
        self,
        trace: Optional[Any],
        node_name: str,
        input_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self._trace = trace
        self._node_name = node_name
        self._input_data = input_data or {}
        self._metadata = metadata or {}
        self._span = None  # StatefulSpanClient
        self._start = time.perf_counter()
        self._output: Optional[Dict[str, Any]] = None

    @property
    def observation(self):
        """返回可作为 langfuse_parent 传给 langfuse.openai 的 span 对象"""
        return self._span

    def __enter__(self):
        if self._trace is not None:
            try:
                self._span = self._trace.start_observation(
                    name=self._node_name,
                    as_type="span",
                    input=self._input_data,
                    metadata=self._metadata,
                )
            except Exception as e:
                print(f"[Langfuse] span({self._node_name}) start failed: {e}")
        return self

    def set_output(self, output: Dict[str, Any]):
        """在 with 块内调用，设置该节点的输出数据"""
        self._output = output

    def set_error(self, error: str):
        """在 with 块内调用，标记该节点为错误状态"""
        self._output = {"error": error}

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._span is None:
            return False
        try:
            latency_ms = int((time.perf_counter() - self._start) * 1000)
            if exc_type is not None:
                self._span.update(output={"error": str(exc_val)}, level="ERROR", status_message=str(exc_val))
                self._span.end()
            else:
                self._span.update(output=self._output or {}, metadata={**self._metadata, "latency_ms": latency_ms})
                self._span.end()
        except Exception as e:
            print(f"[Langfuse] span({self._node_name}) end failed: {e}")
        return False  # 不吞掉异常


def get_trace_from_config(config: Dict[str, Any]) -> Optional[Any]:
    """从 LangGraph RunnableConfig 的 configurable 中取出 langfuse_trace 对象"""
    return config.get("configurable", {}).get("langfuse_trace")
