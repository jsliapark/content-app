from typing import Annotated, Literal, TypedDict

# Note: Using custom append_list reducer (not add_messages) because these are plain lists, not LangChain Message objects
def append_list(existing: list, new: list) -> list:
    """Reducer that appends new items to existing list."""
    return existing + new


class ContentState(TypedDict, total=False):
    # User inputs (required at start)
    topic: str                 # user-specified topic for content generation
    platform: str              # "linkedin" | "twitter" | "blog"
    tone: str                  # user-specified tone modifier for content generation

    # Pipeline config
    model: str                 # LLM model identifier (for model-agnostic support)
    max_retries: int           # maximum number of retries for content generation
    run_id: str                # unique ID for this pipeline run    

    # Voice context from brandvoice-mcp
    voice_context: str         # prompt injection string from brandvoice-mcp        

    # Draft generation
    draft: str                 # current draft text
    previous_drafts: Annotated[list[str], append_list] # accumulated drafts from retries (for context)

    # Alignment checking
    alignment_score: int       # 0-100 from check_alignment
    alignment_feedback: str    # why the score is what it is    
    retry_count: int           # current retry attempt

    # Pipeline state
    status: Literal["pending", "fetching_voice", "generating", "checking", "done", "failed"] # current status of the pipeline
    events: Annotated[list[dict], append_list] # SSE events (accumulated across nodes)
