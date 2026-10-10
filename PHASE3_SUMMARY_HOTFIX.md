# Phase 3 — Summary-length recovery fix

## Why the 502 happened

`DocumentSummaryWorkflow.run()` previously rejected map-stage notes exceeding 3,500 characters. With real Groq responses, a detailed summary can exceed this limit. The FastAPI endpoint then returned HTTP 502.

## Change

- The per-segment hard limit is now 5,000 characters.
- The map-stage instruction asks for concise notes (roughly 3,000 characters).
- When Groq exceeds 5,000 characters, the workflow makes **one** extra Groq request to condense the notes, without dropping entire sections deliberately.
- Empty notes and still-too-long output continue to fail safely; notes are **never silently truncated**.
- Three targeted tests cover overlong recovery, recovery that still exceeds the limit, and empty output.

## Install (PowerShell)

Stop the running FastAPI server first (Ctrl+C), then from the repository root on `feat/document-summarization`:

```powershell
cd D:\a2a-multi-agent
Expand-Archive -Path "$env:USERPROFILE\Downloads\a2a_phase3_summary_length_fix.zip" -DestinationPath . -Force
uv run pytest -q
npm.cmd --prefix .\web run build
git diff --check
git status --short
```

Start the API again from the project root:

```powershell
uv run python -m web_api.main
```

Keep Writer and Verifier agents running. In Knowledge Base, retry **SUMMARIZE** with cloud permission enabled. Avoid pressing the button multiple times during a running request: each attempt may incur Groq token usage and time.

If a new exception occurs, share the backend traceback and the relevant summary error message. This patch addresses **only** the intermediate note-length error; model/provider availability and final Writer/Verifier failures remain separately diagnosable.

Do not commit or merge until the live summarization returns a usable, cited result and all tests/builds pass.
