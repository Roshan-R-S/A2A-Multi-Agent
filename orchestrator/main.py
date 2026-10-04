from core.logging_config import configure_logging

import argparse
import asyncio

from orchestrator.workflow import ResearchWriterWorkflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the A2A Research -> Writer multi-agent workflow."
        )
    )

    parser.add_argument(
        "question",
        nargs="*",
        help="Question to send through the multi-agent workflow.",
    )

    parser.add_argument(
        "--show-research",
        action="store_true",
        help="Show the intermediate Research Agent output.",
    )

    return parser.parse_args()


async def run() -> None:
    args = parse_args()

    if args.question:
        question = " ".join(args.question)
    else:
        print()
        question = input(
            "Ask a question: "
        ).strip()

    if not question:
        print("No question provided.")
        return

    workflow = ResearchWriterWorkflow()

    print()
    print("Research Agent is working...")

    try:
        result = await workflow.run(question)

    except Exception as exc:
        print()
        print("Workflow failed:")
        print(f"{type(exc).__name__}: {exc}")
        return

    if args.show_research:
        print()
        print("=" * 70)
        print("RESEARCH BRIEF")
        print("=" * 70)
        print()
        print(result.research)

    print()
    print("=" * 70)
    print("FINAL ANSWER")
    print("=" * 70)
    print()
    print(result.final_answer)
    print()


def main() -> None:
    configure_logging()
    asyncio.run(run())


if __name__ == "__main__":
    main()
