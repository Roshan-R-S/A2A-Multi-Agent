"""Loopback-only web API exposing existing A2A workflows and local stores.

The API is a single-user development UI, not an authenticated internet service.
Cloud A2A actions require explicit consent per request.
"""

import logging
import re
from pathlib import Path
from uuid import uuid4
from typing import Callable, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field

from knowledge.db import connect, default_db_path
from knowledge.store import KnowledgeStore, SummaryLimitError
from memory.store import ConversationMemory, _validate_conversation_id

logger = logging.getLogger(__name__)
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
ALLOWED_SUFFIXES = {".txt", ".md", ".markdown"}
NAME_RE = re.compile(r'^[^\\/<>:"|?*\x00-\x1f\x7f]{1,120}$')


class UploadBody(BaseModel):
    filename: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=MAX_UPLOAD_BYTES)


class DocumentSummaryBody(BaseModel):
    allow_cloud: bool = False


class ChatBody(BaseModel):
    message: str = Field(min_length=1, max_length=1500)
    conversation_id: str = Field(min_length=1, max_length=64)
    mode: Literal["auto", "documents", "search"] = "auto"
    allow_cloud: bool = False
    save_history: bool = False


def create_app(
    *,
    db_path: Path | str | None = None,
    knowledge: KnowledgeStore | None = None,
    memory: ConversationMemory | None = None,
    routed_factory: Callable | None = None,
    rag_factory: Callable | None = None,
    summary_factory: Callable | None = None,
) -> FastAPI:
    database = Path(db_path).expanduser() if db_path is not None else default_db_path()
    knowledge = knowledge if knowledge is not None else KnowledgeStore(database)
    memory = memory if memory is not None else ConversationMemory(database)
    upload_dir = database.parent / "uploads"

    app = FastAPI(title="A2A Local Assistant", version="0.3.0")
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
    )

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "service": "a2a-web-api"}

    @app.get("/api/documents")
    async def list_documents():
        return [
            {"id": doc.document_id, "title": doc.title, "chunks": doc.chunk_count}
            for doc in knowledge.list_documents()
        ]

    @app.post("/api/documents", status_code=201)
    async def upload_document(body: UploadBody):
        name = body.filename.strip()
        if (
            not NAME_RE.fullmatch(name)
            or name in {".", ".."}
            or name.endswith((".", " "))
            or name.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
        ):
            raise HTTPException(422, "Provide a simple filename without folder paths.")
        if Path(name).suffix.lower() not in ALLOWED_SUFFIXES:
            raise HTTPException(422, "Only .txt, .md, and .markdown are accepted.")
        if "\x00" in body.content or not body.content.strip():
            raise HTTPException(422, "Document must contain nonempty text (no NUL bytes).")
        data = body.content.encode("utf-8")
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Document must be 2 MiB or smaller.")

        upload_dir.mkdir(parents=True, exist_ok=True)
        # Never trust client path components or overwrite an existing file.
        storage_folder = upload_dir / uuid4().hex
        storage_folder.mkdir(mode=0o700)
        stored = storage_folder / name
        try:
            with stored.open("xb") as handle:
                handle.write(data)
            result = knowledge.ingest_file(stored)
        except (OSError, ValueError) as exc:
            stored.unlink(missing_ok=True)
            storage_folder.rmdir()
            logger.exception("Document indexing failed")
            raise HTTPException(422, "Unable to index this document.") from exc
        return {
            "id": result.document_id,
            "title": name,
            "chunks": result.chunk_count,
        }

    @app.delete("/api/documents/{document_id}")
    async def delete_document(document_id: int):
        if document_id <= 0:
            raise HTTPException(404, "Document not found.")
        # Only delete a disk file if it was created inside our managed upload dir.
        with connect(database) as con:
            row = con.execute(
                "SELECT path FROM knowledge_documents WHERE id=?", (document_id,)
            ).fetchone()
        if row is None:
            raise HTTPException(404, "Document not found.")
        path = Path(row["path"])
        managed = path.parent.parent.resolve() == upload_dir.resolve()
        deleted = knowledge.delete_document(document_id)
        if deleted and managed:
            path.unlink(missing_ok=True)
            path.parent.rmdir()
        return {"deleted": deleted}

    @app.post("/api/documents/{document_id}/summary")
    async def summarize_document(document_id: int, body: DocumentSummaryBody):
        if not body.allow_cloud:
            raise HTTPException(
                403, "Explicit cloud consent required: summarization sends "
                "indexed document content to Groq."
            )
        if document_id <= 0:
            raise HTTPException(404, "Document not found.")
        try:
            if summary_factory is None:
                from orchestrator.document_summary import DocumentSummaryWorkflow
                workflow = DocumentSummaryWorkflow(knowledge=knowledge)
            else:
                workflow = summary_factory()
            result = await workflow.run(document_id, allow_cloud=True)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except SummaryLimitError as exc:
            raise HTTPException(413, str(exc)) from exc
        except (PermissionError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc
        except Exception as exc:
            # A2A transport errors may wrap a Groq 413/429 as an InternalError.
            # Keep the provider's account/org details out of HTTP responses.
            message = str(exc).casefold()
            if "request too large for model" in message and "tokens per minute" in message:
                logger.warning("Groq rejected an oversized document-summary request.")
                raise HTTPException(
                    429, "Groq rejected an oversized model request under the "
                    "current tokens-per-minute limit. Reduce the source size "
                    "or adjust the summary workflow budget. Retrying the "
                    "identical oversized request will not fix it."
                ) from exc
            if ("rate_limit_exceeded" in message or "http 429" in message
                    or "error code: 429" in message):
                logger.warning("Groq rate limit reached during document summary.")
                raise HTTPException(
                    429, "Groq's rate limit was reached. Wait for the "
                    "provider's retry window before running the summary again."
                ) from exc
            logger.exception("Document summary workflow failed")
            raise HTTPException(
                502, "Document summarization failed. Check Groq availability and "
                "that the Writer and Verifier agents are running."
            ) from exc
        return {
            "document_id": result.document_id,
            "title": result.title,
            "answer": result.answer,
            "covered_chunks": result.covered_chunks,
            "segments": result.segments,
            "verified": result.verified,
            "sources": result.sources,
        }

    @app.get("/api/search")
    async def search(q: str = Query(min_length=1, max_length=500), limit: int = Query(5, ge=1, le=20)):
        hits = knowledge.search(q, limit=limit)
        return [
            {
                "document_id": hit.document_id,
                "title": hit.title,
                "chunk_id": hit.chunk_id,
                "snippet": hit.body[:1600],
            }
            for hit in hits
        ]

    @app.get("/api/conversations")
    async def conversations():
        with connect(database) as con:
            rows = con.execute(
                """SELECT c.id AS id, COUNT(m.id) AS messages,
                          MAX(m.created_at) AS updated_at
                   FROM memory_conversations AS c
                   LEFT JOIN memory_messages AS m ON m.conversation_id=c.id
                   GROUP BY c.id ORDER BY updated_at DESC, c.id LIMIT 100"""
            ).fetchall()
        return [dict(row) for row in rows]

    @app.get("/api/conversations/{conversation_id}")
    async def history(conversation_id: str):
        try:
            return [vars(item) for item in memory.history(conversation_id, limit=200)]
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.delete("/api/conversations/{conversation_id}")
    async def forget(conversation_id: str):
        try:
            deleted = memory.delete_conversation(conversation_id)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"deleted": deleted}

    @app.post("/api/chat")
    async def chat(body: ChatBody):
        question = body.message.strip()
        if not question:
            raise HTTPException(422, "Message cannot be empty.")
        try:
            _validate_conversation_id(body.conversation_id)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

        if body.mode != "search" and not body.allow_cloud:
            raise HTTPException(
                403,
                "Cloud permission required: this mode sends your request to "
                "external services. For Documents mode, matching document "
                "passages are sent to Groq. Enable cloud consent or use Search.",
            )

        try:
            if body.mode == "search":
                hits = knowledge.search(question, limit=5)
                if hits:
                    answer = "LOCAL SEARCH RESULTS (no cloud call)\n\n" + "\n\n".join(
                        f"{i}. {hit.title}\n{hit.body[:700]}"
                        for i, hit in enumerate(hits, start=1)
                    )
                else:
                    answer = "No matching passages in your local document index."
                sources = [
                    {"id": f"doc_{hit.document_id}", "title": hit.title,
                     "url": f"local://document/{hit.document_id}"}
                    for hit in hits
                ]
                route, verified = "search", False
            elif body.mode == "documents":
                if rag_factory is None:
                    from orchestrator.local_rag import LocalRAGWorkflow
                    workflow = LocalRAGWorkflow(knowledge=knowledge, memory=memory)
                else:
                    workflow = rag_factory()
                result = await workflow.run(question, allow_cloud=True, save_history=False)
                answer = result.answer
                verified = result.verified
                route = "documents"
                sources = [
                    {"id": s.id, "title": s.title, "url": s.url}
                    for s in result.research.sources
                ]
            else:
                if routed_factory is None:
                    from orchestrator.routed_workflow import RoutedWorkflow
                    workflow = RoutedWorkflow()
                else:
                    workflow = routed_factory()
                result = await workflow.run(question)
                answer = result.final_answer
                route = result.decision.route
                verified = result.verified
                sources = []
                if result.research:
                    from agents.research.schemas import ResearchResult
                    research = ResearchResult.model_validate_json(result.research)
                    sources = [
                        {"id": s.id, "title": s.title, "url": s.url}
                        for s in research.sources
                    ]
            if body.save_history:
                memory.add_exchange(body.conversation_id, question, answer)
        except (ValueError, PermissionError) as exc:
            raise HTTPException(422, str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Chat workflow failed")
            raise HTTPException(
                502,
                "Agent workflow failed. Check that the required A2A agents "
                "are running and review the backend terminal logs.",
            ) from exc
        return {"answer": answer, "route": route, "verified": verified,
                "sources": sources, "saved": body.save_history,
                "conversation_id": body.conversation_id}

    return app


app = create_app()
