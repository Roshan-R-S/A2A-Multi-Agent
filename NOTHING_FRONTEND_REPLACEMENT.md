# A2A Nothing-inspired frontend replacement

Scope: **React/Vite frontend only**. Does not modify Python agents, FastAPI endpoints, SQLite storage, `package.json`, `package-lock.json`, `api.ts`, or Vite configuration.

## Existing baseline

- Project root: `D:\a2a-multi-agent`
- Recommended branch: `feat/phase2-intelligent-assistant`
- Last confirmed before replacement: commit `a95c4bc`, 248 Python tests passing, 1 skipped, React build passing.

## Installation in Windows PowerShell

1. Save the ZIP in your Downloads folder.
2. Close the Vite dev server (Ctrl+C in its terminal). Keep the Python agents and FastAPI services running if desired.
3. Make a backup branch and unpack:

```powershell
cd D:\a2a-multi-agent
git status --short
git branch backup/before-nothing-frontend
Expand-Archive -Path "$env:USERPROFILE\Downloads\a2a_nothing_frontend_replacement.zip" -DestinationPath . -Force
```

The archive contains `web/index.html`, replacement `web/src/App.tsx`, `web/src/main.tsx`, new feature components and CSS styles, and two Markdown instruction files.

4. Remove obsolete stylesheet **only after the archive extraction succeeds**:

```powershell
Remove-Item .\web\src\style.css
```

The new `main.tsx` imports `web/src/styles/*.css`. Do not remove `api.ts` or anything in the backend.

5. Build and run:

```powershell
cd D:\a2a-multi-agent\web
npm.cmd run build
npm.cmd run dev
```

6. Open `http://127.0.0.1:5173`. Continue using the existing Python `web_api.main` server on port 8010.

## Verification checklist

- Toggle **SYSTEM / DARK / LIGHT** at the top, refresh and confirm preference persists.
- Test Auto → Planner research or plan, with **ALLOW EXTERNAL AI** enabled. Without consent, submission must be blocked.
- Test Documents → Writer/Verifier, with consent enabled, and view local citations.
- Test Local Search → search indexed README without cloud permission.
- Open KNOWLEDGE: check indexed documents, search `A2A orchestration`, and upload a small `.md` file.
- Test the separate AGENTS station (four known roles, status explicitly unchecked).
- Enable SAVE HISTORY, send a message, refresh, and open it from HISTORY (including mobile bottom nav).
- Verify at 360px, 768px, 1440px, both themes, keyboard Tab focus, long code and tables.
- Run `uv run pytest -q` at repository root; no backend test count should change.

## Expected behavior / constraints

- **Cloud consent is explicit and off by default.** Auto/Documents transmit relevant text to external services only with permission. Local Search stays local.
- No real-time per-agent health/telemetry or tool execution is added. `API CONNECTED` is just FastAPI status.
- Chat message history is stored only when saving is opted in. Metadata like source mapping isn't persisted by the existing backend, so some citation cards may not survive a page refresh on old saved messages; this requires a later backend/schema change.
- Frontend does not use saved conversation messages as automatic conversational context; this is a future backend milestone.
- Google Fonts may require network; fallback fonts keep the UI usable offline.
- `npm.cmd install` is **not necessary** if the currently working Web UI dependencies are already installed; no package dependencies were added.

## Rollback

Before committing the new frontend, restore the old UI files with:

```powershell
cd D:\a2a-multi-agent
git restore web
```

Then delete the newly added, untracked frontend component/style directories shown by `git status --short` (only those introduced by this package). The backup branch preserves the prior state even after a new commit.

## Commit after tests

```powershell
cd D:\a2a-multi-agent
git add web FRONTEND_RULES.md NOTHING_FRONTEND_REPLACEMENT.md
git diff --cached --check
git diff --cached --stat
git commit -m "feat: replace web UI with Nothing-inspired workspace"
git push origin feat/phase2-intelligent-assistant
```

Before committing, verify that no `web/node_modules`, `web/dist`, `.env` or `.a2a_data` content is staged.
