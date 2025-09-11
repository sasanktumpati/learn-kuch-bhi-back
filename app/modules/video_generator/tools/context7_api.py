"""Context7 API tool for fetching documentation and code examples.

This module provides a direct API integration with Context7 instead of using MCP.
"""

from __future__ import annotations

import httpx
from app.core.config import settings


class Context7APIError(Exception):
    """Exception raised when Context7 API calls fail."""

    pass


async def context7_tool(topic: str, tokens: int = 5000, use_manim: bool = True) -> str:
    """Context7 tool function for use with pydantic-ai agents.

    This function fetches documentation from Context7 and returns the raw text
    response that can be used directly by the LLM.

    Args:
        topic: The topic to search for
        tokens: Maximum number of tokens in response
        use_manim: If True, search manim library; if False, search pydantic library

    Returns:
        Raw text response from Context7 API
    """
    if not settings.context7_enabled or not settings.context7_api_key:
        return f"Context7 is disabled or API key not configured"

    # Choose library based on use_manim parameter
    library = "manimcommunity/manim" if use_manim else "pydantic/pydantic-ai"
    url = f"https://context7.com/api/v1/{library}"

    headers = {
        "Authorization": f"Bearer {settings.context7_api_key}",
        "Content-Type": "application/json",
    }
    params = {"type": "txt", "topic": topic, "tokens": tokens}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()

            # Return the raw text response directly
            text = response.text.strip()
            if not text:
                return f"No Context7 documentation found for topic: {topic}"

            return text

    except httpx.HTTPError as e:
        return f"HTTP error calling Context7 API: {e}"
    except Exception as e:
        return f"Unexpected error calling Context7 API: {e}"
