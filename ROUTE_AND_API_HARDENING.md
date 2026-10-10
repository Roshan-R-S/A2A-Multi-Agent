# A2A Multi-Agent — routing and API release-hardening patch

Base: Phase 4 merged `main` (commit `c1b3035`). Apply on a NEW feature branch from a clean `main`.

## What changed

- URL-aware SPA routes: `/` (Chat), `/chat` alias, `/knowledge`, `/agents`, `/history`.
- Browser back and forward buttons restore the matching page.
- Unknown frontend URLs render a custom 404 screen. The **Return Home** button navigates immediately; otherwise an automatic redirect to `/` occurs after five seconds. No conversation or document content is rendered on the unknown route.
- FastAPI keeps **real HTTP 404** for unknown API endpoints and now returns 404 for nonexistent conversation history instead of an empty list. Invalid conversation IDs still return 422.
- API responses include `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, and `Referrer-Policy: no-referrer`.
- Requests originating from unapproved browser origins, or labeled `Sec-Fetch-Site: cross-site`, receive 403. The expected localhost Vite UI (port 5173) and loopback API (port 8010) remain allowed.
- Existing test for deleted-conversation history updated to expect 404. Added regression tests for URL/API errors and headers.

## Installation (PowerShell)

```powershell
cd D:\a2a-multi-agent
git status --short
git switch -c fix/routing-and-404
Expand-Archive -Path "$env:USERPROFILE\Downloads\a2a_routing_404_security_patch.zip" -DestinationPath . -Force
uv run pytest -q
npm.cmd --prefix .\web run build
git diff --check
git status --short
```

If you see unexpected changes before switching branches, stop and inspect them rather than overwriting them.

## Browser smoke checks

Restart the FastAPI backend (if needed) and keep Vite running:

1. Visit `http://127.0.0.1:5173/knowledge` directly; Knowledge opens.
2. Click Agents, then Back; Knowledge returns, and the address bar changes correctly.
3. Visit `http://127.0.0.1:5173/unknown/secret`; a 404 screen appears, then the address changes to `/` after five seconds. The button should go home immediately.
4. Visit `http://127.0.0.1:5173/` again; your saved conversations should still be available.
5. Check API responses with `curl.exe -i http://127.0.0.1:8010/api/does-not-exist` (404) and `curl.exe -i http://127.0.0.1:8010/api/health` (200, no-store).
6. Verify missing conversation IDs return 404; unknown IDs must not reveal other conversation content.
7. Verify Local Search still works with **ALLOW EXTERNAL AI** unchecked.

## Security limitations (important)

This is still a **single-user, loopback-only development application without authentication**. The origin guard reduces browser-based cross-site requests, but it does not authenticate users and can be spoofed by non-browser clients. Any local process able to reach the API may still access known conversation IDs; hiding IDs or redirecting page URLs is not authorization. Do not expose port 8010 or Vite publicly without proper authentication, per-resource authorization, session protections, and deployment-specific hardening.

The Vite development server may serve `index.html` with HTTP 200 for an unknown UI path before the client renders its 404 screen. This is normal SPA fallback behavior. Unlike API URLs, actual HTTP 404 for invalid browser-facing UI routes requires production host routing rules; the client provides a visible 404 and redirect.

## Verification completed in the patch-building environment

- 75 targeted backend/memory/knowledge tests passed using local package sources, including 14 new API-hardening checks.
- TypeScript syntax parsing passed for the modified App and new routing/404 components.
- 14 URL mapping checks passed.
- The full project Python test suite and Vite production build must run on the user's own installation before merge.
