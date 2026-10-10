# Phase 4 — Context-aware conversation memory (opt-in MVP)

**Branch:** `feat/context-aware-memory`. This package is for the Phase 3 code already merged into `main`. It updates only 6 existing files, adds an `orchestrator/conversation_context.py` module and new tests. No migration or extra dependency required.

## Install on Windows PowerShell

1. Verify branch: `git branch --show-current` should show `feat/context-aware-memory`. Working tree should be clean.
2. Back up with Git if needed: `git branch backup/before-phase4-context`.
3. Download `a2a_phase4_context_memory.zip` and extract to the repository root:

```powershell
cd D:\a2a-multi-agent
Expand-Archive -Path "$env:USERPROFILE\Downloads\a2a_phase4_context_memory.zip" -DestinationPath . -Force
uv run pytest -q
npm.cmd --prefix .\web run build
git diff --check
git status --short
```

Stop and restart `web_api.main` after extraction. Restarting Writer/Verifier/Planner/Research isn't required because their source files are unchanged. Do not commit until full tests and live behavior are checked.

## Behavior and privacy

- **ALLOW EXTERNAL AI** remains required for Auto and Documents mode.
- **SAVE HISTORY** controls whether *new* successful question-answer pairs are recorded locally; it is not implied by `USE SAVED CONTEXT`.
- **USE SAVED CONTEXT** is a new, **off-by-default** checkbox. When enabled with cloud consent, up to **6 latest saved messages** (limited to 360 characters each, and roughly 1900 characters overall) from the **same conversation ID** are included as lower-trust context in external requests.
- The previously stored conversations **are not automatically uploaded**. Only the bounded messages selected for the specific request are sent if opt-in is on. Auto mode may send the augmented question to Planner and the web-research pipeline, possibly reaching Groq and Tavily. Documents mode sends augmented question to Writer and Verifier via local-document RAG and Groq.
- Local Search ignores history and never sends model requests. The API rejects requests with `mode=search` and `use_context=true`.
- History is not cross-conversation; deleted conversations cannot contribute context. Unanswered/unsaved turns are not remembered.
- Previous assistant messages are **context cues only**, not independent evidence. As before, the SQLite database is not encrypted.
- The UI displays `CONTEXT / N SAVED MESSAGES` on any response that actually used context.

## Live smoke test

Start the required services for Auto (Planner, Research, Writer, Verifier, web API, Vite) or Documents (Writer, Verifier, web API, Vite). In the Chat workspace:

1. Turn on **ALLOW EXTERNAL AI** and **SAVE HISTORY**; leave **USE SAVED CONTEXT** off. Ask a question and wait for a successful answer.
2. Now turn on **USE SAVED CONTEXT** and ask a follow-up such as `What are its limitations?`.
3. Confirm the second answer displays `CONTEXT / 2 SAVED MESSAGES`; check whether it connects to the prior topic. The model's actual answer quality may vary.
4. Switch to **LOCAL SEARCH** and confirm context is unavailable there; local search must work with cloud unchecked.
5. Start a **new chat**. The previous chat's messages should not appear in the new chat context.
6. Delete the first saved conversation. It must not be recoverable through API context injection.

The feature is not semantic long-term memory or a fact database; it does not automatically summarize large histories, remember unsaved turns, or guarantee pronoun resolution. Keep `main` stable and test before merging.
