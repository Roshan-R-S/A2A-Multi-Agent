# Phase 3: Verifier structured-output hotfix

## Why this patch exists

The Phase 3 README summarization progressed to the Verifier, but Groq returned a truncated/invalid JSON verdict ("Unterminated string..."). This used to crash the A2A Verifier and surface as HTTP 502. Several HTTP 429 retries were also observed.

The configured model, `openai/gpt-oss-120b`, supports Groq **strict JSON Schema** output. This patch requests a constrained response for Verifier calls, uses **low reasoning effort**, and caps the completion at **1,200 tokens** to reduce avoidable token consumption. Schema enforcement handles formatting, not truth. The existing semantic and deterministic checks remain in place; malformed or logically inconsistent results continue to fail, not automatically PASS.

## Files

- `core/llm.py` — optional `response_format`, `reasoning_effort`, and `max_completion_tokens` for the existing `generate_text` helper; regular callers are unchanged.
- `agents/verifier/generator.py` — verifier now requests a strict JSON schema matching its response contract.
- `tests/test_llm.py` and `tests/test_verifier_generator.py` — updated stubs and added regression tests.

## Install (PowerShell)

Work on the feature branch `feat/document-summarization`. Stop **FastAPI**, **Writer**, and **Verifier** processes using Ctrl+C before replacing the source files. Leave the other agents stopped if not needed.

```powershell
cd D:\a2a-multi-agent
Expand-Archive -Path "$env:USERPROFILE\Downloads\a2a_phase3_verifier_structured_json_fix.zip" -DestinationPath . -Force
uv run pytest -q
npm.cmd --prefix .\web run build
git diff --check
git status --short
```

Start each service from the project root in a **separate terminal**:

```powershell
uv run python -m agents.writer.app
```

```powershell
uv run python -m agents.verifier.app
```

```powershell
uv run python -m web_api.main
```

The frontend dev server on `:5173` can remain running. Retry **Knowledge Base -> README.md -> Summarize** with explicit cloud permission.

## Limits and honesty

- Groq's rolling tokens-per-minute quota is unchanged. HTTP 429 can still occur; wait for quota recovery rather than clicking repeatedly.
- Structured output improves JSON syntax and schema adherence but cannot guarantee fact correctness or document coverage.
- The final Verifier still checks compressed map-stage notes, not the original entire README; the summary's `verified` flag is not a full-source audit.
- A bounded completion can still fail if the service cannot complete the response; failures should not be relabeled PASS.
- This package does not modify `.env`, your indexed files, SQLite, or the frontend.
- This patch was tested against mocked models (30 focused Python tests); **live provider validation and your entire Python suite still need to be run locally**.

Reference: https://console.groq.com/docs/structured-outputs
