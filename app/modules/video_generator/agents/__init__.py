"""Agents for the video generator pipeline (prompt upgrade, code gen, fixers).

Uses pydantic-ai with Gemini (model: google-gla:gemini-2.5-pro).

If configured (see CONTEXT7_* settings), agents also connect to the Context7
MCP server to fetch docs tools (prefixed "ctx7_") for libraries like
"/manimcommunity/manim" and "/pydantic/pydantic-ai". The pipeline captures
and logs the first lines of any ctx7 tool results during runs.
"""
