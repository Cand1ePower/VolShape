"""
Tavily web search integration for exercise images and latest research.
"""
from typing import List, Dict, Any, Optional
from app.core.config import settings

_client: Optional[Any] = None


def get_tavily_client():
    global _client
    if _client is None and settings.TAVILY_API_KEY:
        try:
            from tavily import TavilyClient
            _client = TavilyClient(api_key=settings.TAVILY_API_KEY)
        except Exception:
            pass
    return _client


async def search_exercise_info(
    exercise_name: str,
    max_results: int = 3,
) -> List[Dict[str, Any]]:
    client = get_tavily_client()
    if not client:
        return []
    query = f"{exercise_name} exercise proper form technique guide"
    response = client.search(
        query=query,
        max_results=max_results,
        include_images=True,
    )
    return response.get("results", [])


async def search_fitness_knowledge(
    query: str,
    max_results: int = 3,
) -> List[Dict[str, Any]]:
    client = get_tavily_client()
    if not client:
        return []
    response = client.search(
        query=query,
        max_results=max_results,
    )
    return response.get("results", [])
