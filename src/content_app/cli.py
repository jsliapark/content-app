import asyncio
import uuid
import click

from content_app.config import configure_logging, get_settings
from content_app.db.sqlite import init_db, save_run
from content_app.graph.builder import build_graph
from content_app.mcp.brandvoice import BrandvoiceClient
from content_app.providers.claude import ClaudeProvider


@click.command()
@click.option("--topic", required=True, help="Topic for content generation")
@click.option("--platform", required=True, type=click.Choice(["linkedin", "twitter", "blog"]))
@click.option("--tone", required=True, help="Tone modifier (e.g., professional, casual)")
def main(topic: str, platform: str, tone: str):
    """Generate brand-aligned content using LangGraph pipeline."""
    asyncio.run(run_pipeline(topic, platform, tone))


async def run_pipeline(topic: str, platform: str, tone: str):
    configure_logging()
    await init_db()

    run_id = str(uuid.uuid4())
    initial_state = {
        "run_id": run_id,
        "topic": topic,
        "platform": platform,
        "tone": tone,
        "max_retries": get_settings().max_retries,
    }

    async with BrandvoiceClient() as client:
        # TODO: Implement OpenAI provider
        provider = ClaudeProvider() 
        graph = build_graph(client, provider)
        result = await graph.ainvoke(initial_state)

    await save_run(result)

    print(f"\n{'='*50}")
    print(f"Run ID: {result.get('run_id')}")
    print(f"Status: {result.get('status')}")
    print(f"Alignment Score: {result.get('alignment_score')}")
    print(f"Retries: {result.get('retry_count')}")
    print(f"{'='*50}")
    print(f"\nDraft:\n{result.get('draft')}")


if __name__ == "__main__":
    main()