from langgraph.graph import StateGraph, START, END
from content_app.graph.nodes import create_nodes
from content_app.graph.state import ContentState
from content_app.mcp.brandvoice import BrandvoiceClient
from content_app.providers.protocol import LLMProvider

def build_graph(client: BrandvoiceClient, provider: LLMProvider) -> StateGraph:
    """Build the content generation graph."""
    nodes = create_nodes(client, provider)
    graph = StateGraph(ContentState)

    graph.add_node("fetch_voice_context", nodes["fetch_voice_context"])
    graph.add_node("generate_draft", nodes["generate_draft"])
    graph.add_node("check_alignment", nodes["check_alignment"])

    graph.add_edge("fetch_voice_context", "generate_draft")
    graph.add_edge("generate_draft", "check_alignment")

    def route_after_alignment(state: ContentState) -> str:
        if state["status"] == "generating":  # retry
            return "generate_draft"
        if state["status"] == "failed":      # max retries exceeded
            return END
        return END                           # status == "done"

    graph.add_conditional_edges("check_alignment", route_after_alignment)

    graph.set_entry_point("fetch_voice_context")
    return graph.compile()
