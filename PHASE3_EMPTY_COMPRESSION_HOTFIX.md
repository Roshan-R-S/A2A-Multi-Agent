# Phase 3 hotfix: empty Groq compression response

## Symptom

A live `POST /api/documents/1/summary` request returned HTTP 502 with:

```text
orchestrator/document_summary.py → _compress_notes
core/llm.py → RuntimeError: Groq returned an empty response.
```

This is **not** evidence of a token-limit rejection. Groq returned no usable
text to the additional note-compression call.

## Fix

- Keep the 900-character per-segment cap and 5,000-character aggregate note
  budget from the prior token-budget hotfix. All indexed document chunks are
  still sent to the initial map-stage model prompts in order.
- Attempt model note compression once as before. If it returns empty text,
  throws the exact known empty-response error, or returns oversized text,
  build a **bounded local extractive selection from the already-generated
  map-stage notes**. This does not create another Groq call.
- Spread excerpts across the note rather than taking only the beginning, and
  explicitly label them **Selected note excerpts (details omitted)**.
- Add a ResearchResult caveat naming parts that used fallback and warning that
  topics and details may be missing.
- Reject repetitive or uninformative input when a useful extractive fallback
  cannot be constructed. Do not conceal actual 429/413/quota/network errors.
- Add tests for empty-model-error recovery, whitespace-only output, source
  coverage, excerpt sizing, and provider-failure propagation.

## Limitations

This change prevents the *specific* empty **compression** response from
terminating the pipeline. It does not guarantee that subsequent Groq Writer
or Verifier calls will succeed, and it cannot fix an empty *initial map-stage*
response. The final Verifier checks condensed notes, not the raw document.
An extractive fallback can omit important details and **does not establish
complete factual coverage**; inspect the output before relying on it.

## Install on PowerShell

Stop the API process first (Ctrl+C), then run from the existing
`feat/document-summarization` branch:

```powershell
cd D:\a2a-multi-agent
git branch --show-current
Expand-Archive -Path "$env:USERPROFILE\Downloads\a2a_phase3_empty_compression_fix.zip" -DestinationPath . -Force
uv run pytest -q
npm.cmd --prefix .\web run build
git diff --check
git status --short
```

Restart the API:

```powershell
uv run python -m web_api.main
```

Keep Writer and Verifier running. Test **SUMMARIZE** for `README.md` once.
Report the output or the latest traceback. Do **not commit** until live
summarization and the full tests pass.

## Contents

- `orchestrator/document_summary.py`: compression fallback
- `tests/test_document_summary.py`: regression tests
- `PHASE3_EMPTY_COMPRESSION_HOTFIX.md`: this guide

Tested with **47 focused API/store/summary tests** against mocked Groq/A2A
components in a container. A full Windows project test suite and live Groq
run remain to be done by the user.
