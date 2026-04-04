import logging
from collections.abc import Awaitable, Callable
from typing import Any

from content_app.agent.executor import run_draft_agent
from content_app.agent.handlers import (
    build_get_writing_examples_handler,
    handle_web_search,
)
from content_app.config import get_settings
from content_app.graph.state import ContentState
from content_app.mcp.brandvoice import BrandvoiceClient
from content_app.providers.protocol import LLMProvider

logger = logging.getLogger(__name__)

EmitFn = Callable[[dict[str, Any]], Awaitable[None]] | None

_AGENT_FAILURE_MARKERS = (
    "Agent reached max iterations",
    "Agent produced no output.",
)


def _agent_output_needs_fallback(text: str | None) -> bool:
    if text is None:
        return True
    return any(text.startswith(m) for m in _AGENT_FAILURE_MARKERS)


def _build_task_description(state: ContentState) -> str:
    """Build task description from state fields."""
    return f"Write a {state['platform']} post about {state['topic']} with {state['tone']} tone"


def create_nodes(
    client: BrandvoiceClient,
    provider: LLMProvider,
    emit: EmitFn = None,
) -> dict:
    """Factory that creates node functions with injected dependencies."""

    async def fetch_voice_context(state: ContentState) -> dict:
        if emit:
            await emit({"type": "node_start", "node": "fetch_voice_context"})
        try:
            task_description = _build_task_description(state)
            try:
                voice_context = await client.get_voice_context(task_description)
            except Exception as e:
                logger.error(f"Error fetching voice context: {e}")
                return {"status": "failed"}
            return {"voice_context": voice_context, "status": "generating"}
        finally:
            if emit:
                await emit({"type": "node_end", "node": "fetch_voice_context"})

    async def generate_draft(state: ContentState) -> dict:
        if emit:
            await emit({"type": "node_start", "node": "generate_draft"})
        try:
            fallback_user = (
                "Do not include any preamble, meta-commentary, or description "
                "of what you're about to write. Start directly with the content itself.\n\n"
            )
            fallback_user += _build_task_description(state)

            previous_drafts = state.get("previous_drafts", [])
            if state.get("alignment_feedback") and previous_drafts:
                fallback_user += (
                    f"\n\nYour previous draft scored {state['alignment_score']}/100."
                    f"\nFeedback: {state['alignment_feedback']}"
                    f"\nPrevious draft: {previous_drafts[-1]}"
                    f"\n\nPlease revise to better match the brand voice while addressing the feedback."
                )

            agent_user = (
                fallback_user
                + "\n\nYou may call web_search for recent facts or examples, and "
                "get_writing_examples for on-brand reference snippets. "
                "When ready, call draft_content with the full final post only "
                "(the content field should be the post itself, no preamble)."
            )

            system_prompt = (
                f"{state['voice_context']}\n\n"
                "You are an agent that may use tools before submitting the draft via draft_content."
            )

            tool_handlers: dict[str, Any] = {
                "web_search": handle_web_search,
                "get_writing_examples": build_get_writing_examples_handler(client),
            }

            draft: str | None = None
            if getattr(provider, "generate_with_tools", None) is not None:
                try:
                    draft = await run_draft_agent(
                        provider=provider,
                        system_prompt=system_prompt,
                        user_message=agent_user,
                        tool_handlers=tool_handlers,
                        max_iterations=6,
                        on_tool_call=emit if emit else None,
                    )
                except Exception as e:
                    logger.exception("Error in agent draft generation: %s", e)
                    draft = None

            if _agent_output_needs_fallback(draft):
                messages = [
                    {"role": "system", "content": state["voice_context"]},
                    {"role": "user", "content": fallback_user},
                ]
                try:
                    draft = await provider.generate(messages)
                except Exception as e:
                    logger.error(f"Error generating draft: {e}")
                    return {"status": "failed"}

            assert draft is not None
            return {"draft": draft, "previous_drafts": [draft], "status": "checking"}
        finally:
            if emit:
                await emit({"type": "node_end", "node": "generate_draft"})

    async def check_alignment(state: ContentState) -> dict:
        if emit:
            await emit({"type": "node_start", "node": "check_alignment"})
        alignment_score_emit: int | None = None
        retry_count_emit: int | None = None
        try:
            try:
                alignment = await client.check_alignment(state["draft"])
                score = alignment["score"]
                feedback = alignment["feedback"]
                retry_count = state.get("retry_count", 0) + 1
                max_retries = state.get("max_retries", 3)

                if score >= get_settings().alignment_threshold:
                    status = "done"
                elif retry_count >= max_retries:
                    status = "failed"
                else:
                    status = "generating"

                alignment_score_emit = score
                retry_count_emit = retry_count

                return {
                    "alignment_score": score,
                    "alignment_feedback": feedback,
                    "retry_count": retry_count,
                    "status": status,
                }
            except Exception as e:
                logger.error(f"Error checking alignment: {e}")
                return {"status": "failed"}
        finally:
            if emit:
                end_payload: dict[str, Any] = {
                    "type": "node_end",
                    "node": "check_alignment",
                }
                if alignment_score_emit is not None:
                    end_payload["alignment_score"] = alignment_score_emit
                if retry_count_emit is not None:
                    end_payload["retry_count"] = retry_count_emit
                await emit(end_payload)

    return {
        "fetch_voice_context": fetch_voice_context,
        "generate_draft": generate_draft,
        "check_alignment": check_alignment,
    }
