# A2A / Nothing Frontend Rules

Design basis: the uploaded Nothing Design Skill 3.0 documents (`SKILL.md`, `tokens.md`, `components.md`, `platform-mapping.md`). This is a Nothing-*inspired* interface, not an official product or affiliation.

## Visual contract

- Both `data-theme="dark"` and `data-theme="light"` are first-class. `system` preference is supported.
- Tokens live in `web/src/styles/tokens.css`. Avoid hard-coded colors in components; keep contrast adequate in each theme.
- UI/reading font: Space Grotesk; technical labels: Space Mono; hero typography only: Doto. Google Fonts link with system fallbacks; offline font loading must not block use.
- Primary: the user's message/reading task. Secondary: citations and actions. Tertiary: technical labels/status.
- OLED black/off-white surfaces; no glassmorphism, gradients, shadows, oversized rounded containers, generic illustration cards, or decorative emoji.
- Red signals action-worthy interruption, errors, or one active-state marker. Monochrome conveys regular hierarchy.
- Spacing: 4, 8, 16, 24, 32, 48, 64, 96px. Flat cards radius <=16px; pills are for buttons.
- Monoline Lucide icons and purposeful 150–250ms motion. Honor `prefers-reduced-motion`.

## Behavior contract

- Keep existing API contracts and request modes: `auto`, `documents`, `search`. Do not change the backend.
- `auto` and `documents` require explicit consent to cloud processing. `search` is local only.
- Never label Planner's proposed steps as executed actions.
- Web API `/api/health` checks only the API. Never claim each A2A agent is online from that check.
- Render LLM Markdown without raw HTML insertion. Only open HTTPS/HTTP source links. Do not display externally fetched image URLs by default.
- Local documents stay local until the user opts into a mode that sends retrieved passages to Groq.
- Saving conversation history remains opt-in. Stored history is not automatically injected into new prompts.
- Text, buttons and controls must have keyboard access, visible focus, meaningful accessible names, and responsive layouts.
- All network operations require loading, failure, no-results/empty and success states appropriate to the operation.
- Keep the API client in `web/src/api.ts` until a separate tested change warrants refactoring it.

## Regression procedure

After any feature change:
1. `npm.cmd run build` in `web/`.
2. `uv run pytest -q` in repository root.
3. Confirm dark/light/system toggle and persistence after refresh.
4. Confirm desktop 1440px, tablet 768px, mobile 360px layouts. Check for horizontal scrolling and accessible navigation.
5. Check chat auto, documents, local search, upload, delete, saved history, source links, source-free plans, errors and disabled states.
6. Commit the smallest working diff. Never stage `.env`, `.a2a_data`, `web/node_modules`, or `web/dist`.
