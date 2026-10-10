# Phase 3 — Full-document summarization

Implement on branch `feat/document-summarization` (not on `main`). The patch
preserves chat, existing RAG, the four agent services, and the Nothing-inspired
frontend. No new dependencies are required.

## Install (Windows PowerShell)

Run from `D:\a2a-multi-agent` after downloading the zip into Downloads:

```powershell
cd D:\a2a-multi-agent
git branch --show-current
git status --short
Expand-Archive -Path "$env:USERPROFILE\Downloads\a2a_phase3_document_summarization.zip" -DestinationPath . -Force
uv run pytest -q
npm.cmd --prefix .\web run build
git diff --check
git status --short
```

The branch must be `feat/document-summarization`. The existing `.gitignore`
change to add `web/.vite/` is deliberately not overwritten by this patch.

## Run and test the feature

1. Start the Writer agent: `uv run python -m agents.writer.app`.
2. Start the Verifier agent: `uv run python -m agents.verifier.app`.
3. Start the FastAPI server: `uv run python -m web_api.main`.
4. Run the frontend from `web`: `npm.cmd run dev`.
5. Open <http://127.0.0.1:5173>, choose **Knowledge base**.
6. Select the cloud consent checkbox next to document summarization.
7. Click **SUMMARIZE** on the indexed `README.md`. You should see a structured,
   citation-backed full-document summary below the document list.

The Research and Planner services are **not** required for the dedicated
summarization button. The Writer and Verifier are required.

### API

`POST /api/documents/{id}/summary` with JSON `{ "allow_cloud": true }`.

- `200`: `{document_id,title,answer,covered_chunks,segments,verified,sources}`
- `403`: no cloud consent (no model calls)
- `404`: invalid/missing indexed document ID
- `413`: document exceeds the bounded summarization limit
- `422`: invalid request
- `502`: model/agent/verifier failure (generic message; inspect server logs)

This endpoint is loopback-only as part of the existing development API. Do not
expose it publicly without authentication, CSRF protection, rate limiting,
secure file handling, and resource controls.

### Coverage and limits

- Reads **all** SQLite-indexed chunks in ascending position (rather than top-5
  FTS5 search hits). Does not open arbitrary filesystem paths.
- Supports documents of at most 48,000 indexed characters and 80 chunks. Larger
  files remain searchable; summarization returns HTTP 413 without silent truncation.
- Splits ordered chunks into bounded groups of at most 7,600 characters.
- Each group is summarized using the existing Groq configuration. Those notes
  and their original indexed text are passed to the existing A2A Writer and
  Verifier workflow, with a local citation source for each group.
- Cloud consent is explicit for this action and defaults to **off**. Every
  indexed passage processed by the action is transmitted to Groq; **do not
  summarize secrets or sensitive documents**. Database and indexed files are
  stored locally but are not encrypted.
- This is a model-generated synopsis, not a lossless rewrite. Reviewing all
  chunks does **not** guarantee every detail appears in the final summary.
  The Verifier checks against the supplied document evidence, not outside truth.
- No token streaming, background task queue, or provider cost controls are
  implemented. Long documents require multiple model calls and may take time.

## Tests

New `tests/test_document_summary.py` checks ordered reads, oversize behavior,
batch coverage, consent enforcement, end-to-end pipeline integration with
mocks, and API error codes. No paid calls occur during automated tests.

**Package-author validation:** 7 targeted tests passed with unavailable
external dependencies stubbed, and the changed TypeScript files passed syntax
parsing. This package has **not yet been validated against your full Windows
repository** with `uv run pytest -q` and `npm.cmd --prefix .\web run build`.
Run the commands above and share their exact output before committing.
