import os
from mem0 import Memory
from app.core.config import settings
import logging
import inspect

logger = logging.getLogger(__name__)

def get_mem0_client() -> Memory:
    # Build mem0 config
    config = {
        "llm": {
            "provider": "openai",
            "config": {
                "model": settings.LLM_LIGHT_MODEL,
                "temperature": 0.0,
                "api_key": settings.DEEPSEEK_API_KEY,
                "openai_base_url": settings.DEEPSEEK_BASE_URL,
            }
        },
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "volshape_memories_v3",
                "path": "data/mem0_qdrant",
                "embedding_model_dims": settings.EMBEDDING_DIMS
            }
        }
    }

    # Use embedding config if provided
    if settings.EMBEDDING_API_KEY and settings.EMBEDDING_BASE_URL and settings.EMBEDDING_MODEL:
        config["embedder"] = {
            "provider": "openai",
            "config": {
                "model": settings.EMBEDDING_MODEL,
                "api_key": settings.EMBEDDING_API_KEY,
                "openai_base_url": settings.EMBEDDING_BASE_URL,
                "embedding_dims": settings.EMBEDDING_DIMS
            }
        }
    else:
        # Default to huggingface or something local if supported by mem0
        config["embedder"] = {
            "provider": "huggingface",
            "config": {
                "model": "sentence-transformers/all-MiniLM-L6-v2"
            }
        }

    try:
        mem = Memory.from_config(config)
        return mem
    except Exception as e:
        logger.error(f"Failed to initialize Mem0 client: {e}")
        raise e

# Create a singleton instance
memory_client = get_mem0_client()


def _supports_kwarg(method, name: str) -> bool:
    try:
        return name in inspect.signature(method).parameters
    except (TypeError, ValueError):
        return False


def _build_mem0_kwargs(method, *, user_id: str, limit: int | None = None):
    kwargs = {}
    if _supports_kwarg(method, "user_id"):
        kwargs["user_id"] = user_id
    if _supports_kwarg(method, "filters"):
        kwargs["filters"] = {"user_id": user_id}
    if limit is not None:
        if _supports_kwarg(method, "limit"):
            kwargs["limit"] = limit
        elif _supports_kwarg(method, "top_k"):
            kwargs["top_k"] = limit
    return kwargs

async def add_memory_async(messages: list, user_id: str):
    """
    Asynchronously adds memory. Uses run_in_executor to avoid blocking event loop.
    messages: list of dict e.g. [{"role": "user", "content": "..."}]
    """
    import asyncio
    from functools import partial
    try:
        loop = asyncio.get_running_loop()
        func = partial(memory_client.add, messages, **_build_mem0_kwargs(memory_client.add, user_id=user_id))
        await loop.run_in_executor(None, func)
    except Exception as e:
        logger.error(f"Failed to add memory: {e}")

async def search_memory_async(query: str, user_id: str, limit: int = 10) -> str:
    """
    Search memory and return formatted string for context.
    """
    import asyncio
    from functools import partial
    try:
        loop = asyncio.get_running_loop()
        kwargs = _build_mem0_kwargs(memory_client.search, user_id=user_id, limit=limit)
        func = partial(memory_client.search, query, **kwargs)
        res_dict = await loop.run_in_executor(None, func)
        
        results = res_dict.get("results", []) if res_dict else []
        if not results:
            return ""
        
        context_lines = []
        for res in results:
            context_lines.append(f"- {res['memory']}")
        return "\n".join(context_lines)
    except Exception as e:
        logger.error(f"Failed to search memory: {e}")
        return ""

async def get_all_memory_async(user_id: str) -> list:
    """
    Get all memories for a user.
    """
    import asyncio
    from functools import partial
    try:
        loop = asyncio.get_running_loop()
        kwargs = _build_mem0_kwargs(memory_client.get_all, user_id=user_id, limit=100)
        func = partial(memory_client.get_all, **kwargs)
        res_dict = await loop.run_in_executor(None, func)
        return res_dict.get("results", []) if res_dict else []
    except Exception as e:
        logger.error(f"Failed to get all memory: {e}")
        return []
