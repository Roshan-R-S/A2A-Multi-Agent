"""Start the optional Planner-enabled CLI (old CLI remains unchanged)."""

import argparse
import asyncio

from core.logging_config import configure_logging
from orchestrator.routed_workflow import RoutedWorkflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the planner-enabled A2A workflow")
    parser.add_argument("question", nargs="*", help="User request")
    parser.add_argument("--show-research", action="store_true")
    return parser.parse_args()


async def run() -> None:
    args = parse_args()
    question = " ".join(args.question).strip() if args.question else input("Ask a question: ").strip()
    if not question:
        print("No question provided.")
        return

    try:
        result = await RoutedWorkflow().run(question)
    except Exception as exc:
        print(f"Workflow failed: {type(exc).__name__}: {exc}")
        return

    print(f"\nPlanner route: {result.decision.route}")
    print(f"Reason: {result.decision.reason}")
    if args.show_research and result.research is not None:
        print("\nRESEARCH BRIEF\n" + result.research)
    print("\nFINAL ANSWER" if result.verified else "\nPLANNING OUTPUT (UNVERIFIED)")
    print(result.final_answer)


def main() -> None:
    configure_logging()
    asyncio.run(run())


if __name__ == "__main__":
    main()
