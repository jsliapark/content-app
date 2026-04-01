import asyncio
import click

from content_app.config import configure_logging
from content_app.runner import run_pipeline_blocking


@click.command()
@click.option("--topic", required=True, help="Topic for content generation")
@click.option("--platform", required=True, type=click.Choice(["linkedin", "twitter", "blog"]))
@click.option("--tone", required=True, help="Tone modifier (e.g., professional, casual)")
def main(topic: str, platform: str, tone: str):
    """Generate brand-aligned content using LangGraph pipeline."""
    asyncio.run(_cli_async(topic, platform, tone))


async def _cli_async(topic: str, platform: str, tone: str) -> None:
    configure_logging()
    result = await run_pipeline_blocking(topic, platform, tone)

    print(f"\n{'='*50}")
    print(f"Run ID: {result.get('run_id')}")
    print(f"Status: {result.get('status')}")
    print(f"Alignment Score: {result.get('alignment_score')}")
    print(f"Retries: {result.get('retry_count')}")
    print(f"{'='*50}")
    print(f"\nDraft:\n{result.get('draft')}")


if __name__ == "__main__":
    main()
