# Phase 2 Web UI — local development setup

Adds a **FastAPI** backend and **React + TypeScript + Vite** frontend. No login or signup. This is strictly a **single-user local development UI**; do not put the backend on a public IP or expose the app to the Internet without authentication, authorization, CSRF protection, rate limits, and other hardening.

## 1. Extract files

Extract `a2a_phase2_web_ui.zip` into `D:\a2a-multi-agent` on your existing `feat/phase2-intelligent-assistant` branch. This package adds `web_api/`, `web/`, `tests/test_web_api.py`, and this document. It does not replace your current agents or orchestrators.

## 2. Install dependencies

```powershell
cd D:\a2a-multi-agent
uv add "fastapi>=0.115,<1"
cd .\web
npm.cmd install
cd ..
```

`uv add` edits `pyproject.toml` and `uv.lock` to record the backend dependency; `npm.cmd install` creates `web/package-lock.json`. Commit both lockfiles later. No new paid API keys are needed beyond what you already use for Groq and Tavily.

Add generated frontend outputs to `.gitignore`:

```powershell
@('web/node_modules/', 'web/dist/') | ForEach-Object {
    if (-not (Select-String -Path .gitignore -Pattern ([regex]::Escape($_) + '$') -Quiet)) { Add-Content .gitignore $_ }
}
```

## 3. Test

```powershell
uv run pytest tests\test_web_api.py -q
uv run pytest -q
cd web
npm.cmd run build
cd ..
```

## 4. Start required services (one terminal each)

From `D:\a2a-multi-agent`:

```powershell
uv run python -m agents.research.app
```

```powershell
uv run python -m agents.writer.app
```

```powershell
uv run python -m agents.verifier.app
```

```powershell
uv run python -m agents.planner.app
```

```powershell
uv run python -m web_api.main
```

In a separate terminal:

```powershell
cd D:\a2a-multi-agent\web
npm.cmd run dev
```

Open <http://127.0.0.1:5173> in your browser. Check backend health at <http://127.0.0.1:8010/api/health>. Vite proxies `/api` requests to port 8010.

## How it works

- **Auto:** Planner (8004) chooses research workflow or returns a plan. Enables remote Groq and possibly Tavily calls. Needs **Allow external AI/search services** checked.
- **Documents:** Local SQLite FTS5 searches indexed files, then Groq-backed Writer (8002) and Verifier (8003) produce a verified answer with local-source citations. Retrieved excerpts **leave your computer**. Needs cloud consent. No Research or Planner agent is required for this mode.
- **Local search:** Fully local SQLite keyword search, **no external calls**; works even if all agents are stopped.
- **Upload:** File picker accepts `.txt`, `.md`, `.markdown` up to 2 MiB. Uploaded files and index are stored under ignored `.a2a_data/`. PDF, DOCX, embeddings and vector search are not yet supported.
- **Memory:** Check **Save conversation locally** to store successful requests/responses in SQLite; saved chats appear in the sidebar. Reopening a chat shows its history. **This does not yet inject earlier turns into LLM prompts.**

### Limitations and privacy

The database is not encrypted. Keep sensitive documents out of it unless you control your machine and understand the risks. Groq/Tavily use external APIs and their usage limits; local search is free. The frontend does not use a third-party font CDN, and external Markdown images are suppressed.

This initial UI uses request/response; a long verified answer can take tens of seconds. There is no streaming token display or background task queue. The API is bound to `127.0.0.1`; the frontend dev server also listens only on `127.0.0.1`. A local network device cannot connect directly by default. The API is not for multi-user or hosted deployment.

The cloud consent is required on **each web chat request**, and the web UI does not send your indexed document excerpts to Groq unless Documents mode is chosen with that consent enabled.

## Git after successful tests

```powershell
git status --short
git add web_api web tests/test_web_api.py PHASE2_WEB_UI.md pyproject.toml uv.lock .gitignore
git diff --cached --check
git commit -m "feat: add local web chat interface with RAG and memory"
git push origin feat/phase2-intelligent-assistant
```

Be sure no `.env`, `.a2a_data`, `node_modules`, or frontend build outputs are staged.
