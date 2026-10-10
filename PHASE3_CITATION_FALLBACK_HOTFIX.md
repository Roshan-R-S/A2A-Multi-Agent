# Phase 3: Citation-rejection graceful fallback

The live pipeline reached Verifier but the Writer draft (and a revised draft) lacked citations in some research-backed sentences. The Verifier correctly rejected it; the API returned 502. This patch does **not** modify the general Writer or Verifier behavior. It changes only full-document summaries.

- On an explicitly citation-related verification failure, return attributed map-stage notes with `verified: false` rather than falsely claiming verification or returning no result. These notes are **not** a substitute for a complete, source-checked summary. Other failure types still raise errors.
- Default document-summary revision count is now **zero** (one Writer draft and one Verifier attempt). This avoids extra Groq calls on a low-TPM tier. Normal A2A research chat retains its original revision policy.
- Default oversized segment notes are shortened locally with explicit `details omitted` labeling rather than requiring an additional Groq compression request. An injected test compressor remains supported.
- The Knowledge Base visibly labels fallback notes `NOT AGENT VERIFIED` and discloses limitations. If verification passes, the label says `VERIFIED AGAINST SUMMARY NOTES`, not the original full document.

## Installation

Stop the API; the Writer and Verifier can stay running as their code is unchanged. On branch `feat/document-summarization`:

```powershell
cd D:\a2a-multi-agent
Expand-Archive -Path "$env:USERPROFILE\Downloads\a2a_phase3_citation_fallback_fix.zip" -DestinationPath . -Force
uv run pytest -q
npm.cmd --prefix .\web run build
git diff --check
```

Restart the API with `uv run python -m web_api.main`. Try the README summary once, allowing time for Groq's rolling TPM usage to clear. The Writer/Verifier may still be rate limited. If a model request fails before verification, the API still returns an error. Do **not** commit or merge before a live result has been reviewed.
