# Phase 3 Hotfix — Groq 8,000-TPM request sizing

## Why this patch exists

The earlier `DocumentSummaryWorkflow` read every source segment and then sent the
raw segment **again** through Writer, Verifier, and Writer revision requests.
The latest live failure reported `Requested 8780`, exceeding the Groq model's
`8000` tokens-per-minute (TPM) tier limit. Ordinary retry logic cannot make an
individual request larger than that maximum succeed. A separate transient
HTTP 429 can still occur when several smaller requests deplete the rolling TPM
budget; the existing Groq client already has bounded retries for that case.

## Changes

- Keep the full ordered document read during the **map stage**. No indexed
  document chunk is skipped by this patch.
- Send only shortened segment notes (rather than complete raw text) to the A2A
  Writer and Verifier; allocate a conservative total budget of **5,000 note
  characters**, at most **900** per segment. Over-budget map notes are sent for
  one more bounded shortening attempt; no silent truncation.
- Refuse any resulting `ResearchResult` JSON longer than **15,000 characters**.
  These are character-based safety margins rather than precise tokenizer counts;
  actual Groq throughput limitations may still require waiting.
- Respond with a sanitized **429** and specific guidance for Groq token/rate
  limits, instead of a generic **502**. The API never exposes provider account
  IDs or the raw internal exception.
- Add tests for bounded evidence, consent preservation, too-long notes, and
  sanitized API error handling.

### Important accuracy tradeoff

The final Verifier now compares the final draft **against the compressed map
notes**, not the complete original document. The map stage still reads the
entire indexed document, but a model-generated note can omit or distort facts.
Consequently `verified: true` means verification against **those notes only**;
it does not prove a complete or completely faithful summary of the raw file.
The UI may still show the usual `VERIFIED` marker; interpret it with this caveat.
Do not rely on this feature for high-stakes source-critical summarization.

## Install on Windows PowerShell

Stop the running API (Ctrl+C). Keep this branch:

```
cd D:\a2a-multi-agent
git branch --show-current
Expand-Archive -Path "$env:USERPROFILE\Downloads\a2a_phase3_groq_token_budget_fix.zip" -DestinationPath . -Force
uv run pytest -q
npm.cmd --prefix .\web run build
git diff --check
git status --short
```

The branch must remain `feat/document-summarization`.
The patch replaces only three code/test files plus this document:

- `orchestrator/document_summary.py`
- `web_api/app.py`
- `tests/test_document_summary.py`
- `PHASE3_GROQ_TOKEN_BUDGET_HOTFIX.md` (new)

No change to `.env` or frontend packages is needed. Restart the API:

```
uv run python -m web_api.main
```

Wait at least one minute before re-running the README summary if a provider
rate-limit occurred recently. A 429 may still arise from accumulated map-stage
calls, even if the individual revision request is now smaller.

The package was checked with 13 targeted tests using stubbed agent/Groq modules;
**a full Windows regression run and live Groq test have not been performed here**.
Please share the full test output and one live README summary result (or trace)
before committing or opening a PR.
