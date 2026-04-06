"""Tool definitions for Claude ``tool_use`` during draft generation."""

from __future__ import annotations

from typing import Any

AGENT_TOOLS: list[dict[str, Any]] = [
    {
        "name": "web_search",
        "description": (
            "Search the web for recent information, statistics, trends, or examples "
            "related to a topic. Use when current data or real-world examples would "
            "make the content more compelling."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_writing_examples",
        "description": (
            "Fetch relevant past writing samples that match the user's voice and "
            "relate to the current topic. Use for style reference for similar subjects."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic to find relevant writing examples for",
                },
            },
            "required": ["topic"],
        },
    },
    {
        "name": "draft_content",
        "description": (
            "Submit the final draft. Call ONLY when ready to output the finished piece. "
            "The content you pass becomes the pipeline draft. No preamble or meta-commentary "
            "in the content — start as the post itself."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The final draft content to submit",
                },
            },
            "required": ["content"],
        },
    },
]
