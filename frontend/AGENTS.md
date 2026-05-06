# frontend/AGENTS.md — React frontend

Stack-specific guide for anything under `frontend/`. Cross-cutting
context (layout, secrets, ports, default login, architecture cheatsheet)
lives in the [root `AGENTS.md`](../AGENTS.md) — read that first.

## Toolchain

- Node **20+** with npm.
- React 18 + Vite + TanStack Query + React Router (see
  [`package.json`](package.json)).

## Install & run

From `frontend/`:

```bash
npm install
npm run dev          # Vite on http://localhost:5173, proxies /api -> :8001
npm run test:watch   # Vitest watcher
npm run typecheck    # tsc --noEmit
npm run lint         # eslint src --max-warnings=0
npm run build        # tsc --noEmit && vite build
```

Override the backend target with `VITE_BACKEND_URL` (see
[`vite.config.ts`](vite.config.ts)).

## Tests (Vitest + Testing Library)

- Place tests next to the unit under test as `*.test.ts` /
  `*.test.tsx`.
- Keep `npm run test:watch` running while editing — that's the inner
  loop.
- One-shot run before commit: `npm test`.
- Single file:

  ```bash
  npx vitest run src/<path>/<file>.test.tsx
  ```

Always run `npm run typecheck` before handing off — `npm run build`
runs `tsc --noEmit` first and will fail on type errors.

## Style

- Functional components only. Extract reusable logic into hooks under
  [`src/hooks/`](src/hooks/) and pure helpers into
  [`src/lib/`](src/lib/).
- Server state goes through TanStack Query; don't roll your own
  caching.
- API calls live in `src/lib/` (typed wrappers around axios). UI
  components must **not** call axios directly.
- Always send the CSRF header on mutating requests — the shared API
  client already does this; don't bypass it.
- Don't add narrating comments; only comment non-obvious intent.

## Pointers

- Root [`AGENTS.md`](../AGENTS.md) — secrets, ports, architecture,
  cross-stack pre-commit gate.
- [`README.md`](../README.md) — full frontend setup, Docker frontend on
  `8080`, manual end-to-end verification flow.
