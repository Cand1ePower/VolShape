from __future__ import annotations

import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

from app.core.config import settings


def _is_langfuse_enabled() -> bool:
    return bool(
        settings.LANGFUSE_PUBLIC_KEY
        and settings.LANGFUSE_PUBLIC_KEY != "pk-lf-default-mock-key"
        and settings.LANGFUSE_SECRET_KEY
        and settings.LANGFUSE_SECRET_KEY != "sk-lf-default-mock-key"
    )


@lru_cache(maxsize=1)
def get_langfuse_client():
    """Return a cached Langfuse client when tracing is configured."""
    if not _is_langfuse_enabled():
        return None
    try:
        from langfuse import Langfuse

        return Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
    except Exception as exc:
        print(f"[Langfuse] Failed to create client: {exc}")
        return None


@dataclass
class TraceHandle:
    client: Any
    root_observation: Any
    propagation_cm: Any | None = None
    root_cm: Any | None = None

    @property
    def trace_id(self) -> Optional[str]:
        return getattr(self.root_observation, "trace_id", None) or getattr(self.root_observation, "id", None)

    def start_observation(self, **kwargs: Any) -> Any:
        return self.root_observation.start_observation(**kwargs)

    def update(self, **kwargs: Any) -> Any:
        return self.root_observation.update(**kwargs)

    def end(self) -> Any:
        return self.root_observation.end()


def create_trace(
    user_id: str,
    session_id: str,
    mode: str,
    user_input: str,
) -> Tuple[Optional[Any], Optional[str]]:
    """Create the root trace/span for a chat request."""
    lf = get_langfuse_client()
    if lf is None:
        return None, None

    propagation_cm = None
    try:
        from langfuse import propagate_attributes

        propagation_cm = propagate_attributes(
            user_id=user_id,
            session_id=session_id,
            trace_name=f"volshape_chat_{mode}",
        )
        propagation_cm.__enter__()

        root_cm = None
        if hasattr(lf, "start_as_current_observation"):
            root_cm = lf.start_as_current_observation(
                name="chat_request",
                as_type="chain",
                input={"user_input": user_input, "mode": mode},
                metadata={"mode": mode, "session_id": session_id, "user_id": user_id},
                end_on_exit=False,
            )
            root = root_cm.__enter__()
        else:
            root = lf.start_observation(
                name="chat_request",
                as_type="chain",
                input={"user_input": user_input, "mode": mode},
                metadata={"mode": mode, "session_id": session_id, "user_id": user_id},
            )
        handle = TraceHandle(client=lf, root_observation=root, propagation_cm=propagation_cm, root_cm=root_cm)
        return handle, handle.trace_id
    except Exception as exc:
        if propagation_cm is not None:
            try:
                propagation_cm.__exit__(None, None, None)
            except Exception:
                pass
        print(f"[Langfuse] create_trace failed: {exc}")
        return None, None


def finish_trace(trace: Optional[Any], final_response: str, intent: str = "", metadata: dict | None = None):
    """Finalize the root trace/span and flush pending events."""
    if trace is None:
        return
    try:
        trace.update(
            output={"final_response": final_response[:500], "intent": intent},
            metadata=metadata or {},
        )
        client = getattr(trace, "client", None) or get_langfuse_client()
        if hasattr(trace, "end"):
            trace.end()
        if client:
            client.flush()
    except Exception as exc:
        print(f"[Langfuse] finish_trace failed: {exc}")
    finally:
        root_cm = getattr(trace, "root_cm", None)
        if root_cm is not None:
            try:
                root_cm.__exit__(None, None, None)
            except Exception as exit_exc:
                print(f"[Langfuse] root context close failed: {exit_exc}")
        propagation_cm = getattr(trace, "propagation_cm", None)
        if propagation_cm is not None:
            try:
                propagation_cm.__exit__(None, None, None)
            except Exception as exit_exc:
                print(f"[Langfuse] propagation context close failed: {exit_exc}")


class NodeSpan:
    """Small context manager for nested workflow spans."""

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
        self._span = None
        self._start = time.perf_counter()
        self._output: Optional[Dict[str, Any]] = None

    @property
    def observation(self):
        return self._span

    def __enter__(self):
        if self._trace is not None:
            try:
                if hasattr(self._trace, "start_observation"):
                    self._span = self._trace.start_observation(
                        name=self._node_name,
                        as_type="span",
                        input=self._input_data,
                        metadata=self._metadata,
                    )
                elif hasattr(self._trace, "span"):
                    self._span = self._trace.span(
                        name=self._node_name,
                        input=self._input_data,
                        metadata=self._metadata,
                    )
            except Exception as exc:
                print(f"[Langfuse] span({self._node_name}) start failed: {exc}")
        return self

    def set_output(self, output: Dict[str, Any]):
        self._output = output

    def set_error(self, error: str):
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
        except Exception as exc:
            print(f"[Langfuse] span({self._node_name}) end failed: {exc}")
        return False


def get_trace_from_config(config: Dict[str, Any]) -> Optional[Any]:
    return config.get("configurable", {}).get("langfuse_trace")
