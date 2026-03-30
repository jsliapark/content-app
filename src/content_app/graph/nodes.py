import logging

from content_app.graph.state import ContentState
from content_app.mcp.brandvoice import BrandvoiceClient
from content_app.providers.protocol import LLMProvider

logger = logging.getLogger(__name__)


def create_nodes(client: BrandvoiceClient, provider: LLMProvider) -> dict:
    """Factory that creates node functions with injected dependencies."""

    async def fetch_voice_context(state: ContentState) -> dict:
        task_description = f"Write a {state['platform']} post about {state['topic']} with {state['tone']} tone"

        try:
            voice_context = await client.get_voice_context(task_description)
        except Exception as e:
            logger.error(f"Error fetching voice context: {e}")
            return {
                "status": "failed",
            }
        return {"voice_context": voice_context, "status": "generating"}

    async def generate_draft(state: ContentState) -> dict:
        user_content = f"Write a {state['platform']} post about {state['topic']} with {state['tone']} tone"
        
        # If this is a retry, add feedback context
        if state.get("alignment_feedback"):
            user_content += f"""
            Your previous draft scored {state['alignment_score']}/100.
            Feedback: {state['alignment_feedback']}
            Previous draft: {state['previous_drafts'][-1]}

            Please revise to better match the brand voice while addressing the feedback."""

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

    async def check_alignment(state: ContentState) -> dict:
        try:
            alignment = await client.check_alignment(state["draft"])
            score = alignment["score"]
            feedback = alignment["feedback"]
            retry_count = state.get("retry_count", 0) + 1
            max_retries = state.get("max_retries", 3)
            THRESHOLD = 70

            if score >= THRESHOLD:
                return {
                    "alignment_score": score,
                    "alignment_feedback": feedback,
                    "retry_count": retry_count,
                    "status": "done",
                }
            elif retry_count >= max_retries:
                return {
                    "alignment_score": score,
                    "alignment_feedback": feedback,
                    "retry_count": retry_count,
                    "status": "failed",
                }
            else:
                return {
                    "alignment_score": score,
                    "alignment_feedback": feedback,
                    "retry_count": retry_count,
                    "status": "generating",
                }
        except Exception as e:
            logger.error(f"Error checking alignment: {e}")
            return {"status": "failed"}

    return {
        "fetch_voice_context": fetch_voice_context,
        "generate_draft": generate_draft,
        "check_alignment": check_alignment,
    }