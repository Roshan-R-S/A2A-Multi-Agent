"""Phase 2 local knowledge and memory CLI; simple to use from PowerShell.

Index/search/history are entirely local. RAG answer generation explicitly
requires --allow-cloud because Writer/Verifier use the Groq API.
"""

import argparse
import asyncio
from pathlib import Path

from knowledge.store import KnowledgeStore
from memory.store import ConversationMemory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local RAG and SQLite memory")
    parser.add_argument("--db", type=Path, default=None,
                        help="Optional SQLite database path")
    commands = parser.add_subparsers(dest="command", required=True)

    ingest = commands.add_parser("ingest", help="Index a .txt/.md document")
    ingest.add_argument("file", type=Path)

    search = commands.add_parser("search", help="Search without a network request")
    search.add_argument("question", nargs="+")
    search.add_argument("--limit", type=int, default=5)

    ask = commands.add_parser("ask", help="Answer with local passages + Groq Writer/Verifier")
    ask.add_argument("question", nargs="+")
    ask.add_argument("--allow-cloud", action="store_true",
                     help="I agree to send matching local passages to Groq")
    ask.add_argument("--save-history", action="store_true",
                     help="Persist the question and answer in local SQLite")
    ask.add_argument("--conversation", default="default")

    documents = commands.add_parser("documents", help="List indexed documents")
    delete = commands.add_parser("delete", help="Remove an indexed document")
    delete.add_argument("document_id", type=int)
    delete.add_argument("--yes", action="store_true", help="Confirm deletion")

    remember = commands.add_parser("remember", help="Save an explicit memory message")
    remember.add_argument("conversation")
    remember.add_argument("role", choices=["user", "assistant"])
    remember.add_argument("text", nargs="+")

    history = commands.add_parser("history", help="Read saved conversation messages")
    history.add_argument("conversation")
    history.add_argument("--limit", type=int, default=50)

    forget = commands.add_parser("forget", help="Delete local conversation history")
    forget.add_argument("conversation")
    forget.add_argument("--yes", action="store_true", help="Confirm deletion")
    return parser


async def run() -> None:
    args = build_parser().parse_args()
    if args.command == "ask" and not args.allow_cloud:
        raise SystemExit(
            "Cloud permission required. Add --allow-cloud ONLY if you want "
            "matching private document passages sent to the Groq API. "
            "Use 'search' for fully local retrieval."
        )
    knowledge = KnowledgeStore(args.db)

    if args.command == "ingest":
        result = knowledge.ingest_file(args.file)
        print(f"Document {result.document_id}: {result.title} "
              f"({result.chunk_count} chunks; unchanged={result.unchanged})")
    elif args.command == "documents":
        for document in knowledge.list_documents():
            print(f"{document.document_id}: {document.title} ({document.chunk_count} chunks)")
    elif args.command == "delete":
        if not args.yes:
            raise SystemExit("Pass --yes to confirm deleting this indexed document.")
        print("Deleted." if knowledge.delete_document(args.document_id) else "Not found.")
    elif args.command == "search":
        hits = knowledge.search(" ".join(args.question), limit=args.limit)
        if not hits:
            print("No matching passages in the local index.")
        for i, hit in enumerate(hits, start=1):
            print(f"\n[{i}] Document {hit.document_id}: {hit.title}")
            print(hit.body[:400] + ("..." if len(hit.body) > 400 else ""))
    elif args.command == "ask":
        # Import cloud-facing modules only when an explicit cloud question is asked.
        from orchestrator.local_rag import LocalRAGWorkflow, NoLocalEvidenceError
        workflow = LocalRAGWorkflow(
            knowledge=knowledge,
            memory=ConversationMemory(args.db),
        )
        try:
            result = await workflow.run(
                " ".join(args.question), allow_cloud=True,
                conversation_id=args.conversation,
                save_history=args.save_history,
            )
        except NoLocalEvidenceError as exc:
            print(str(exc))
            return
        print("\nVERIFIED LOCAL-DOCUMENT ANSWER\n")
        print(result.answer)
        print("\nSources (local index):")
        for source in result.research.sources:
            print(f"  [{source.id}] {source.title} ({source.url})")
    elif args.command in {"remember", "history", "forget"}:
        memory = ConversationMemory(args.db)
        if args.command == "remember":
            memory.add_message(args.conversation, args.role, " ".join(args.text))
            print("Message saved to local SQLite.")
        elif args.command == "history":
            for item in memory.history(args.conversation, limit=args.limit):
                print(f"{item.created_at} {item.role}: {item.content}")
        else:
            if not args.yes:
                raise SystemExit("Pass --yes to confirm deleting conversation history.")
            print("Deleted." if memory.delete_conversation(args.conversation) else "Not found.")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
