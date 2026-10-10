# Phase 2: SQLite local RAG + persistent conversation history

This is a **local-document retrieval MVP**, not vector/embedding-based semantic RAG.
No new Python dependencies are needed; Python's SQLite with FTS5 is used.
Existing A2A Research, Writer, Verifier, Planner, and smart_main are unchanged.

## Install

Extract `a2a_phase2_rag_memory.zip` into the root of `D:\a2a-multi-agent`.
Protect locally stored content from accidental Git commits by adding `.a2a_data/`
to `.gitignore` (installer instructions include the command).

## Run: local-only document index and retrieval

```powershell
uv run python -m orchestrator.knowledge_main ingest .\README.md
uv run python -m orchestrator.knowledge_main documents
uv run python -m orchestrator.knowledge_main search "A2A protocol agents"
```

Only explicitly chosen **.txt, .md, and .markdown** files can be indexed, up to
2 MiB each. PDF and semantic/vector retrieval are future enhancements.
Queries use SQLite FTS5 keywords with parameterized SQL.

## Run: answer from local documents (requires cloud permission)

Start the existing Writer and Verifier services in separate terminals:

```powershell
uv run python -m agents.writer.app
uv run python -m agents.verifier.app
```

Then:

```powershell
uv run python -m orchestrator.knowledge_main ask "What is the project architecture?" --allow-cloud
```

`--allow-cloud` is **required** because the Writer and Verifier use **Groq**.
Relevant excerpts of your indexed documents leave your computer to those
services. Do **not** opt in for sensitive documents. Without the flag, only
`search` is available and nothing is sent to Groq. Your database is local.

The retrieved passages are packed into the existing `ResearchResult` schema,
then sent through the existing Writer -> Verifier + revision loop with
`[src_N]` citations. No Tavily or Research Agent is invoked for local-doc RAG.
Source IDs map to document titles in the printed result. Verification checks
faithfulness to retrieved excerpts, not external truth.

## Save and inspect history

History is **off by default** for generated answers; opt in:

```powershell
uv run python -m orchestrator.knowledge_main ask "What is A2A?" --allow-cloud --save-history --conversation sprint
uv run python -m orchestrator.knowledge_main history sprint
```

Manually store a note without network access:

```powershell
uv run python -m orchestrator.knowledge_main remember sprint user "Remember our goal is a local assistant"
uv run python -m orchestrator.knowledge_main history sprint
```

Delete a saved conversation or indexed document:

```powershell
uv run python -m orchestrator.knowledge_main forget sprint --yes
uv run python -m orchestrator.knowledge_main documents
uv run python -m orchestrator.knowledge_main delete 1 --yes
```

Note: stored history is **retrievable**, but is not yet automatically injected
into follow-up questions. Memory-aware multi-turn chat is a later milestone.
The SQLite database is not encrypted, and deletions are not cryptographic
secure erasures. Keep `.a2a_data/` out of Git, and do not index secrets.

## Testing

```powershell
uv run pytest tests\test_knowledge_store.py tests\test_memory_store.py tests\test_local_rag.py -v
uv run pytest -q
```

The 200-test baseline should remain intact. Tests added in this package verify
indexing, lexical retrieval, search query safety, persistence, consent checks,
schema compatibility, and the existing Writer/Verifier call path using mocks.
