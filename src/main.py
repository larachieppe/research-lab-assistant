from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown

from src.graph import build_graph

OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs"


def _slugify(question: str) -> str:
    slug = "-".join(question.lower().split()[:8])
    return re.sub(r"[^a-z0-9-]", "", slug) or "report"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search PubMed and arXiv, extract findings, and synthesize a cited summary."
    )
    parser.add_argument("question", help="Research question to investigate")
    parser.add_argument("--max-papers", type=int, default=12, help="Max total papers to retrieve (default: 12)")
    parser.add_argument("--max-queries", type=int, default=5, help="Max search queries to generate (default: 5)")
    parser.add_argument("--no-save", action="store_true", help="Don't save the report to outputs/")
    args = parser.parse_args()

    console = Console()
    graph = build_graph()

    with console.status("[bold cyan]Running research pipeline..."):
        result = graph.invoke(
            {
                "question": args.question,
                "max_papers": args.max_papers,
                "max_queries": args.max_queries,
            }
        )

    console.print()
    console.print(Markdown(result["summary"]))

    if not args.no_save:
        OUTPUTS_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = OUTPUTS_DIR / f"{timestamp}_{_slugify(args.question)}.md"
        path.write_text(f"# {args.question}\n\n{result['summary']}\n")
        console.print(f"\n[dim]Saved report to {path}[/dim]")


if __name__ == "__main__":
    main()
