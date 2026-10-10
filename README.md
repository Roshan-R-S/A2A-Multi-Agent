# A2A Multi-Agent System

A Python **Agent2Agent (A2A)** multi-agent research and writing prototype. Three independently running agents collaborate over A2A JSON-RPC to research a question, write a source-cited answer, and verify the result. Failed verification can trigger an automatic Writer revision.

**Version:** `0.1.0`
**Stage:** Local development MVP
**Latest automated validation (2026-10-10):** 181 passed, 1 non-blocking warning
**Latest live integration run (2026-10-10):** PASS after 1 revision, 73.34 seconds

## How it works

```text
User question
    |
    v
Orchestrator (A2A discovery, capability checks, workflow)
    |
    v
Research Agent  :8001
    | Tavily search -> bounded webpage extraction
    |              -> search-snippet fallback when needed
    |              -> evidence-linked claims and synthesis
    v
Structured ResearchResult (claims -> evidence -> sources)
    |
    v
Writer Agent    :8002
    | Citation-backed draft ([src_1], [src_2], ...)
    | Citation validation / normalization / repair
    v
Verifier Agent  :8003
    | Deterministic citation checks + semantic verification
    |
    +---- PASS ------------------------> Final answer
    |
    +---- FAIL -> feedback -> Writer revision -> reverify
                                 (at most 2 revisions)
```

The orchestrator discovers agents using `/.well-known/agent-card.json`, validates advertised A2A capabilities, and communicates through JSON-RPC `POST /`. This is a service-based system, not a browser application.

## Technology

- Python 3.10, [`uv`](https://docs.astral.sh/uv/)
- A2A SDK, Starlette, Uvicorn
- Groq SDK with model `openai/gpt-oss-120b`
- Tavily web search
- HTTPX, Pydantic, python-dotenv
- pytest, pytest-asyncio

For exact supported package requirements, see [`pyproject.toml`](pyproject.toml).

## Project layout

```text
.
|-- agents/
|   |-- research/
|   |   |-- app.py, card.py, executor.py, factory.py
|   |   |-- search.py, sources.py, schemas.py
|   |   |-- evidence.py, web_evidence.py
|   |   |-- claims.py, synthesizer.py, assembler.py, pipeline.py
|   |   `-- providers/tavily.py
|   |-- writer/
|   |   |-- app.py, card.py, executor.py
|   |   `-- context.py, generator.py, revision.py, prompts.py
|   `-- verifier/
|       |-- app.py, card.py, executor.py, schemas.py
|       `-- context.py, generator.py, prompts.py
|-- core/
|   |-- config.py
|   |-- llm.py
|   `-- logging_config.py
|-- orchestrator/
|   |-- client.py, discovery.py, workflow.py
|   `-- revision_loop.py, main.py
|-- tests/
|   |-- test_llm.py
|   |-- test_web_evidence.py
|   `-- ... other test modules
|-- .env.example
|-- pyproject.toml
`-- README.md
```

## Setup on Windows PowerShell

Prerequisites: Python 3.10, `uv`, a Groq API key, and a Tavily API key.

```powershell
cd D:\a2a-multi-agent
uv venv --python 3.10
uv sync
```

Create `.env` from `.env.example` **only if it doesn't already exist**. Required configuration:

```dotenv
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
TAVILY_API_KEY=your_tavily_api_key_here

RESEARCH_AGENT_HOST=127.0.0.1
RESEARCH_AGENT_PORT=8001
WRITER_AGENT_HOST=127.0.0.1
WRITER_AGENT_PORT=8002
VERIFIER_AGENT_HOST=127.0.0.1
VERIFIER_AGENT_PORT=8003
```

Never commit `.env` or real credentials. Keep `.env.example` free of secrets.

## Run the agents

Run each command in a **separate PowerShell terminal**, from the project root.

**Terminal 1 â€” Research**

```powershell
uv run python -m agents.research.app
```

**Terminal 2 â€” Writer**

```powershell
uv run python -m agents.writer.app
```

**Terminal 3 â€” Verifier**

```powershell
uv run python -m agents.verifier.app
```

**Terminal 4 â€” Orchestrator**

```powershell
uv run python -m orchestrator.main
```

Example prompt:

```text
What are the differences between RAG and fine-tuning?
```

### Service endpoints

| Agent | Health endpoint | Agent Card |
|---|---|---|
| Research | `http://127.0.0.1:8001/health` | `http://127.0.0.1:8001/.well-known/agent-card.json` |
| Writer | `http://127.0.0.1:8002/health` | `http://127.0.0.1:8002/.well-known/agent-card.json` |
| Verifier | `http://127.0.0.1:8003/health` | `http://127.0.0.1:8003/.well-known/agent-card.json` |

Each agent's A2A JSON-RPC endpoint is `POST /`. Opening `/` in a browser uses GET and may result in **405 Method Not Allowed**, which is expected.

Check health from PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
Invoke-RestMethod http://127.0.0.1:8002/health
Invoke-RestMethod http://127.0.0.1:8003/health
```

## Research and evidence provenance

Research retrieves Tavily results and creates normalized `Source` objects. The webpage extractor tries up to **3 public HTTP(S) pages**, reads supported HTML/plain-text responses, picks query-relevant passages, and falls back to the associated Tavily snippets when a fetch is unsuccessful.

Current webpage extraction bounds and restrictions:

- HTTP timeout of 6 seconds per request and maximum response body of 500,000 bytes
- Up to 2 candidate passages from a fetched page
- Redirects disabled; simple private/loopback URL checks; HTTP(S) standard ports only
- Unsupported response types, including PDFs, use snippet fallback
- Evidence retains explicit `source_id` references; claims reference evidence IDs

The `ResearchResult` schema validates that referenced source and evidence IDs exist. This improves traceability but does not guarantee that a source is correct or authoritative.

## Writer, Verifier, and revision loop

The Writer converts supported research claims into an answer with citations of the form `[src_N]`. It validates sources, normalizes supported citation formatting, and can attempt a targeted citation repair.

The Verifier checks citation presence/validity, sentence-level citation coverage, evidence consistency, unsupported statements, citation mismatch, contradictions, changed facts, missing caveats, and overstated certainty. An initial `FAIL` creates structured feedback for the Writer. At most two Writer revisions are allowed.

A `PASS` is an automated quality-control judgment, **not** a guarantee that every real-world fact is true.

## Groq reliability

The shared client in `core/llm.py` has bounded retries for HTTP 429, temporary 5xx responses, connection errors, and timeouts. It uses exponential backoff (up to 3 retries) and respects `Retry-After` response hints where possible. Permanent failures, such as HTTP 401, are not retried. SDK-level retries are disabled to avoid duplicate retry policies.

## Tests and validation

```powershell
uv run python -m compileall -f core agents orchestrator tests
uv run pytest tests\test_llm.py -v
uv run pytest tests\test_web_evidence.py -v
uv run pytest -q
```

**Latest user-reported test result (October 10, 2026):** `181 passed, 1 warning`. The warning is a non-blocking Starlette/httpx deprecation notice.

**Latest user-reported live workflow:** Research completed, Writer produced a cited draft, Verifier identified missing uncertainty qualifiers, Writer revised once, Verifier returned `PASS` on attempt 2, and the orchestrator returned a final answer in **73.34 seconds**.

The live run confirms end-to-end operation. It does **not** independently prove how many webpages yielded full text rather than snippet fallbacks; evaluate that separately if full-page retrieval coverage matters.

## Scope and limitations

This is a **working local-development MVP**, not a production-secure or fully general-purpose agent platform.

- PDF/document parsing is not implemented; PDF search results use snippet fallback.
- HTML passage extraction is basic and does not fully handle JavaScript-rendered content or complex page structures.
- URL safety checks are **not sufficient against DNS rebinding** or other advanced SSRF attacks. Do not expose arbitrary URL fetching to untrusted public clients without network-level controls.
- No authentication, HTTPS/TLS configuration, persistent task storage, or production monitoring.
- No comprehensive defenses against prompt injection in retrieved webpages.
- Semantic verification incurs model latency; individual model outputs can still be incorrect.
- Groq retry behavior is covered by mocked tests; recovery from an actual live 429 has not been independently demonstrated.

Potential future enhancements: PDF parsing, better article extraction and passage chunking, source-quality evaluation, lower-latency verification, observability, secure public deployment, persistent memory, and additional specialized agents.

## License

No license has been declared yet.
