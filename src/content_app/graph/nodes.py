import logging
from collections.abc import Awaitable, Callable
from typing import Any

from content_app.config import get_settings
from content_app.graph.state import ContentState
from content_app.mcp.brandvoice import BrandvoiceClient
from content_app.providers.protocol import LLMProvider

logger = logging.getLogger(__name__)

ALIGNMENT_THRESHOLD = get_settings().alignment_threshold

EmitFn = Callable[[dict[str, Any]], Awaitable[None]] | None


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
            user_content = _build_task_description(state)

            previous_drafts = state.get("previous_drafts", [])
            if state.get("alignment_feedback") and previous_drafts:
                user_content += (
                    f"\n\nYour previous draft scored {state['alignment_score']}/100."
                    f"\nFeedback: {state['alignment_feedback']}"
                    f"\nPrevious draft: {previous_drafts[-1]}"
                    f"\n\nPlease revise to better match the brand voice while addressing the feedback."
                )

            messages = [
                {"role": "system", "content": state["voice_context"]},
                {"role": "user", "content": user_content},
            ]
            try:
                draft = await provider.generate(messages)
            except Exception as e:
                logger.error(f"Error generating draft: {e}")
                return {"status": "failed"}
            return {"draft": draft, "previous_drafts": [draft], "status": "checking"}
        finally:
            if emit:
                await emit({"type": "node_end", "node": "generate_draft"})

    async def check_alignment(state: ContentState) -> dict:
        if emit:
            await emit({"type": "node_start", "node": "check_alignment"})
        try:
            try:
                alignment = await client.check_alignment(state["draft"])
                score = alignment["score"]
                feedback = alignment["feedback"]
                retry_count = state.get("retry_count", 0) + 1
                max_retries = state.get("max_retries", 3)

                if score >= ALIGNMENT_THRESHOLD:
                    status = "done"
                elif retry_count >= max_retries:
                    status = "failed"
                else:
                    status = "generating"

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
                await emit({"type": "node_end", "node": "check_alignment"})

    return {
        "fetch_voice_context": fetch_voice_context,
        "generate_draft": generate_draft,
        "check_alignment": check_alignment,
    }
