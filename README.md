# A2A Multi-Agent Assistant

A **local-first, multi-agent AI assistant** built with Python and the **Agent2Agent (A2A)** protocol. Four independently running agents collaborate to **plan**, **research**, **write source-cited answers**, and **verify** them. A FastAPI backend and React web interface provide chat, local document retrieval, and saved conversation history.

> **Project status:** Working **single-user development MVP**, not a publicly deployable or fully autonomous assistant. The repository package version remains `0.1.0` (see `pyproject.toml`).
>
> **Last confirmed validation (October 10, 2026):** 248 Python tests passed, 1 skipped, 1 non-blocking Starlette/httpx deprecation warning; the previously committed React frontend built successfully. The newer Nothing-inspired frontend replacement is being tested separately: **run its build before treating that redesign as validated**.

## Features

| Feature | Current implementation |
|---|---|
| **Planner Agent** | Routes requests to `research` or `plan_only`; a plan is **not executed** |
| **Research Agent** | Tavily web search, bounded webpage extraction, structured sources/evidence/claims |
| **Writer Agent** | Converts evidence to readable responses with `[src_N]` citations |
| **Verifier Agent** | Citation checks, semantic verification, feedback, and up to two Writer revisions |
| **Local document RAG** | SQLite FTS5 **keyword-based** retrieval over explicitly indexed text/Markdown files |
| **Persistent memory** | SQLite storage for saved conversations; previous turns are **not automatically injected** into future prompts |
| **Web app** | FastAPI + React/TypeScript/Vite with chat, knowledge management, and history |
| **Frontend design** | Optional Nothing-inspired redesign with OLED dark / paper light themes and an informational Agent Control Station; local replacement may not yet be committed |

**What it does not do yet:** general tool execution, browser/computer control, vector/embedding-based semantic retrieval, PDF/DOCX ingestion, real-time token streaming, guaranteed fact-checking, or autonomous task execution.

## Architecture

```text
                       USER / REACT WEB UI :5173
                                  |
                                  | /api (Vite development proxy)
                                  v
                       FASTAPI WEB API :8010
                                  |
                   +--------------+----------------+
                   |              |                |
                   v              v                v
              AUTO MODE      DOCUMENTS MODE   LOCAL SEARCH
                   |              |                |
                   v              v                v
             Planner :8004   SQLite FTS5       SQLite FTS5
                   |         indexed passages    results only
            +------+------+     |
            |             |     |
        plan_only       research |
            |             |     |
       Proposed plan   Research :8001
       (not run)          |     |
                          v     v
                      Writer :8002
                          |
                          v
                      Verifier :8003
                          |
                 +--------+--------+
                 |                 |
                PASS              FAIL
                 |                 |
             Cited answer     Feedback to Writer
                                   |
                              Reverify (max 2
                              Writer revisions)

          SQLite: indexed documents + opt-in saved chat history
```

- **Auto mode:** The Planner returns a proposed plan or delegates research to the existing Research → Writer → Verifier workflow. The Planner currently supports **only** `research` and `plan_only`, not direct UI/tool actions.
- **Documents mode:** Retrieved local passages become structured `ResearchResult` evidence, then go through Writer → Verifier; it does **not** invoke Tavily, Research, or Planner.
- **Local Search mode:** Returns matched SQLite passages without calling external AI/search services. Search results are not model-verified.

A2A services advertise capabilities at `/.well-known/agent-card.json`. The orchestrators validate relevant capabilities and communicate via JSON-RPC **`POST /`**. Visiting an agent's `/` URL with a normal browser GET can return **405 Method Not Allowed**; that is expected. Unlike the original CLI-only version, this project **does have a browser interface**, provided by React and FastAPI.

## Technology stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.10 used for development; `pyproject.toml` declares `>=3.10,<3.15` |
| Environment / packages | `uv`, `pyproject.toml`, `uv.lock` |
| Agent communication | A2A SDK, JSON-RPC over HTTP, Starlette, Uvicorn, HTTPX |
| AI generation | Groq SDK; configured model `openai/gpt-oss-120b` |
| Web research | Tavily, bounded public webpage extraction and snippet fallback |
| Backend API | FastAPI, Pydantic |
| Local knowledge | Built-in SQLite with FTS5 (lexical search, **no embeddings**) |
| Conversation persistence | SQLite (`.a2a_data/assistant.sqlite3` by default) |
| Frontend | React 19, TypeScript, Vite 7, Lucide, React Markdown |
| Frontend visual direction | Nothing-inspired tokens: Space Grotesk / Space Mono / Doto, monochromatic surfaces, dark and light modes (frontend replacement under validation) |
| Testing | pytest, pytest-asyncio; TypeScript and Vite build |

See [`pyproject.toml`](pyproject.toml) and [`web/package.json`](web/package.json) for declared dependencies; lockfiles record resolved versions.

## Project layout

```text
.
|-- agents/
|   |-- planner/              # A2A intent router / proposed plans :8004
|   |-- research/             # Tavily, source/evidence collection :8001
|   |-- writer/               # Cited answer generation / revisions :8002
|   `-- verifier/             # Citation/semantic checks :8003
|-- core/                    # Shared configuration, Groq client, logging
|-- orchestrator/
|   |-- main.py               # Original Research -> Writer -> Verifier CLI
|   |-- smart_main.py         # Planner-enabled CLI
|   |-- routed_workflow.py    # Planner -> research or plan_only
|   |-- workflow.py           # Research -> Writer -> Verifier
|   |-- revision_loop.py      # Verification feedback and bounded revisions
|   |-- knowledge_main.py     # Local document / memory CLI
|   `-- local_rag.py          # Local passages -> Writer -> Verifier
|-- knowledge/               # SQLite FTS5 indexing and chunk retrieval
|-- memory/                  # SQLite conversation history
|-- web_api/                 # FastAPI API and server runner :8010
|-- web/                     # React + TypeScript + Vite UI :5173
|   |-- src/
|   |-- package.json
|   `-- vite.config.ts
|-- tests/                   # Agent, workflow, RAG, API regression tests
|-- .a2a_data/               # Local database/uploads (Git-ignored, generated)
|-- .env.example             # Example config; no real secrets
|-- pyproject.toml
|-- uv.lock
|-- PHASE2_RAG_MEMORY.md
|-- PHASE2_WEB_UI.md
`-- README.md
```

Additional frontend design files, component folders, and design-rule documents may appear after installing the Nothing-inspired frontend replacement. They are frontend-only additions, not changes to the API contract.

## Setup on Windows PowerShell

### Prerequisites

- Python 3.10 (the version used for live development/testing)
- `uv`
- Node.js and npm for the React web UI
- Groq API key for LLM-based writing/verification/planning
- Tavily API key for web research (not needed for local-only SQLite search)

From the project root:

```powershell
cd D:\a2a-multi-agent
uv venv --python 3.10
uv sync
npm.cmd --prefix .\web install
```

`uv venv` is needed only for a fresh environment. Do not overwrite your working `.env`. If you have not configured one yet:

```powershell
Copy-Item .env.example .env
```

Edit `.env` privately to include your API keys. **Never commit `.env` or post real API keys in logs/screenshots.**

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

# Optional: Planner defaults to these even if omitted
PLANNER_AGENT_HOST=127.0.0.1
PLANNER_AGENT_PORT=8004
```

The Planner settings are loaded separately and have defaults; the optional Planner lines above need not already exist in `.env.example`.

## Run the browser assistant

Run each service in a **separate PowerShell terminal**. In each terminal, first go to the project root:

```powershell
cd D:\a2a-multi-agent
```

Start the agents:

| Service | Command | Local port |
|---|---|---|
| Research | `uv run python -m agents.research.app` | 8001 |
| Writer | `uv run python -m agents.writer.app` | 8002 |
| Verifier | `uv run python -m agents.verifier.app` | 8003 |
| Planner | `uv run python -m agents.planner.app` | 8004 |

Start FastAPI in another terminal:

```powershell
cd D:\a2a-multi-agent
uv run python -m web_api.main
```

Start Vite in another terminal:

```powershell
cd D:\a2a-multi-agent\web
npm.cmd run dev
```

**Web app:** <http://127.0.0.1:5173>
**API health:** <http://127.0.0.1:8010/api/health>

Vite proxies `/api` calls to the locally bound FastAPI server on port 8010. The API health endpoint indicates that **FastAPI is reachable**, **not** that all four agents are healthy.

### Agent health and discovery

| Agent | Health | Discovery card |
|---|---|---|
| Research | `http://127.0.0.1:8001/health` | `http://127.0.0.1:8001/.well-known/agent-card.json` |
| Writer | `http://127.0.0.1:8002/health` | `http://127.0.0.1:8002/.well-known/agent-card.json` |
| Verifier | `http://127.0.0.1:8003/health` | `http://127.0.0.1:8003/.well-known/agent-card.json` |
| Planner | `http://127.0.0.1:8004/health` | `http://127.0.0.1:8004/.well-known/agent-card.json` |

PowerShell quick checks:

```powershell
1..4 | ForEach-Object {
    $port = 8000 + $_
    Invoke-RestMethod "http://127.0.0.1:$port/health"
}
Invoke-RestMethod http://127.0.0.1:8010/api/health
```

### Alternative CLI entry points

Use the Research/Writer/Verifier workflow directly:

```powershell
uv run python -m orchestrator.main
```

Use the Planner-enabled route:

```powershell
uv run python -m orchestrator.smart_main "Explain RAG versus fine-tuning"
```

## Web UI modes, privacy, and history

The web client sends these modes to `POST /api/chat`: `auto`, `documents`, and `search`.

| Mode | Behavior | External services? |
|---|---|---|
| **Auto** | Planner decides between plan-only and web-backed research | **Yes**: Groq, and Tavily when researching |
| **Documents** | SQLite passages → Writer → Verifier | **Yes**: matched passages sent to Groq |
| **Local Search** | SQLite keyword results, without LLM inference | **No** external AI/search calls |

Cloud-powered modes require an **explicit `allow_cloud` option** on each request. Do not enable it for sensitive indexed documents unless you are comfortable sending their matching passages to external services.

The frontend can store successful exchanges when **Save conversation locally** is enabled. Saved chats survive refresh and can be reopened or deleted. **History storage is not contextual memory:** earlier turns are not yet automatically provided to the model when answering a new question.

The default local database is **not encrypted at rest**; SQLite and uploaded document content reside in ignored local storage under `.a2a_data/`.

### Existing web API endpoints

| Method and path | Purpose |
|---|---|
| `GET /api/health` | FastAPI liveness |
| `GET /api/documents` | List indexed files |
| `POST /api/documents` | Index a TXT/Markdown upload |
| `DELETE /api/documents/{id}` | Remove indexed document |
| `GET /api/search?q=...` | Local full-text retrieval |
| `GET /api/conversations` | Saved conversation summaries |
| `GET /api/conversations/{id}` | Read saved history |
| `DELETE /api/conversations/{id}` | Delete saved history |
| `POST /api/chat` | Chat request with mode and consent flags |

This API is intended for a loopback-only single-user development setup. No login or signup is implemented.

## Local knowledge: ingest, search, and ask

Supported file types: `.txt`, `.md`, `.markdown`; each file must be UTF-8 and at most **2 MiB**. Only explicitly selected files are indexed. The index is **SQLite FTS5 lexical search**, not semantic/vector search. Match quality depends on the query terms and document coverage.

Run without an external model:

```powershell
uv run python -m orchestrator.knowledge_main ingest .\README.md
uv run python -m orchestrator.knowledge_main documents
uv run python -m orchestrator.knowledge_main search "Planner Writer Verifier FastAPI"
```

For an LLM-generated, citation-backed answer from indexed documents, start **Writer and Verifier** and opt in to remote passage processing:

```powershell
uv run python -m orchestrator.knowledge_main ask "Explain this project's architecture" --allow-cloud
```

To persist that exchange:

```powershell
uv run python -m orchestrator.knowledge_main ask "What does the planner do?" --allow-cloud --save-history --conversation sprint
uv run python -m orchestrator.knowledge_main history sprint
```

To delete local stored data:

```powershell
uv run python -m orchestrator.knowledge_main documents
uv run python -m orchestrator.knowledge_main delete 1 --yes
uv run python -m orchestrator.knowledge_main forget sprint --yes
```

**Important after replacing this README:** Re-ingest it so SQLite does not continue answering from the outdated indexed version:

```powershell
uv run python -m orchestrator.knowledge_main ingest .\README.md
```

Indexing the same filesystem file updates its stored chunks if the content has changed; it does not require a new document ID.

## Research, citation checking, and reliability

The Research Agent normalizes Tavily sources and collects evidence-linked passages from supported public HTTP(S) pages, with snippet fallback when webpage extraction fails. Web extraction is intentionally bounded (up to three candidate pages; size/time limits) and does not reliably handle PDFs or heavily JavaScript-rendered pages.

The `ResearchResult` schema links **claims → evidence → sources**, and the Writer uses `[src_N]` markers. The Verifier performs citation-presence/coverage checks and LLM-based semantic assessment. Failed verification can trigger **up to two revisions**. A `PASS` means the automated verification checks passed, **not** that every statement is independently true.

The Groq client has bounded retry handling for transient failures (for example HTTP 429/5xx and connection errors). LLM-powered requests can take tens of seconds; the current web chat uses normal request/response, **not streaming**.

## Nothing-inspired frontend (replacement under validation)

A Nothing Design Skill-inspired React frontend has been installed locally as a replacement for the initial UI. Its goals are:

- Dark **OLED black** and light **paper white** themes, with a system theme option.
- Space Grotesk, Space Mono, and selective Doto display typography (with font fallbacks).
- Monochrome flat surfaces, restrained semantic red, Lucide line icons, and dot-matrix accents.
- Chat, Knowledge Base, saved history, and an informational four-agent Control Station.
- Responsive navigation, readable source citations, and explicit cloud/data consent controls.

**Branch distinction:** The latest known pushed Web UI commit is `a95c4bc`. The Nothing-inspired replacement is being tested locally and may not yet be committed or pushed. Do not treat a design goal as completed unless you have confirmed it in your checked-out frontend.

The Agent Control Station describes the existing four agents; it must **not** imply that individual agents are online without individual health checks supplied by a backend API.

## Validation

From `D:\a2a-multi-agent`:

```powershell
uv run pytest -q
npm.cmd --prefix .\web run build
git status --short
```

**Known baseline before the uncommitted frontend replacement:** `248 passed, 1 skipped, 1 non-blocking warning` in pytest and a successful Vite production build of the committed frontend. Re-run both commands after changing the frontend or README; do not assume a new build has passed without running it.

Suggested manual smoke tests:

1. In Auto mode, request a plan and a web-backed research answer (cloud consent enabled).
2. In Documents mode, ask about the indexed README; check local `[src_N]` citations (cloud consent enabled).
3. In Local Search mode, retrieve README passages with cloud consent **off**.
4. Save a conversation, refresh the page, and reopen its history.
5. Switch between dark, light, and system themes if the Nothing-inspired replacement is installed.
6. Test Chat, Knowledge, and Agent Control Station at desktop and narrow mobile widths.

## Limitations and security

- **Not production-secure:** The development web API has no authentication, authorization, CSRF protection, HTTPS termination, rate limiting, or public deployment hardening. Keep it bound to `127.0.0.1`.
- **Local data is not encrypted:** Never index sensitive information without understanding local and cloud exposure.
- **Prompt injection / web safety:** Retrieved web/document content is untrusted. Current defenses are incomplete; remote page retrieval is **not** hardened against all SSRF scenarios (including DNS rebinding).
- **RAG is lexical:** FTS5 searches text terms. No semantic embeddings, vector database, PDF, or DOCX document parsing yet.
- **Memory is storage:** Saved messages are not automatically used as conversational context in model prompts.
- **Planning is non-executing:** Planner `plan_only` proposes steps; the assistant does not yet execute arbitrary tools, browser actions, or UI navigation requests.
- **Verification is fallible:** Model-based checks can miss incorrect claims; citations show provenance, not absolute truth.
- **Agent monitoring:** `/api/health` covers FastAPI availability only, not per-agent status or live execution traces.

## Development and roadmap

Potential next milestones include: improving source/result formatting and full-document summarization; verifying the Nothing-inspired frontend build and accessibility; refactoring API/frontend modules; contextual conversation retrieval; dedicated validated tool actions; better evaluation and monitoring; and security hardening before any public hosting.

Useful project notes: [`PHASE2_RAG_MEMORY.md`](PHASE2_RAG_MEMORY.md) and [`PHASE2_WEB_UI.md`](PHASE2_WEB_UI.md).

## License

No project-level license has been declared in this repository. Do not assume that bundled third-party dependencies or external design inspirations change this project's license status.
