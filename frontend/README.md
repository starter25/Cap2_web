# Frontend (React + TypeScript + Vite)

The stress-detection dashboard UI. It talks to the FastAPI backend
(`web_viz.backend.app`) over the fixed JSON API (`/api/state`, `/api/normal/toggle`,
`/api/stress/toggle`, `/api/exit`). The API contract is typed in
[`src/types.ts`](src/types.ts) and must stay in lockstep with
`controller.py:get_state()`.

## Develop

```bash
npm install
npm run dev          # http://127.0.0.1:5173, proxies /api -> 127.0.0.1:5080
```

Point the proxy at a different backend with `VITE_API_TARGET`:

```bash
VITE_API_TARGET=http://192.168.0.10:5080 npm run dev
```

If the backend is unreachable the app falls back to an offline mock
([`src/mock.ts`](src/mock.ts)) so the UI keeps animating — useful for design work.

## Build (production)

```bash
npm run build        # type-checks, then emits ./dist
```

The FastAPI backend serves `frontend/dist` automatically when it exists, so the
whole app still runs from a single process:

```bash
python -m web_viz.backend.app   # serves SPA + API on http://127.0.0.1:5080
```

## Structure

- `src/types.ts` — backend JSON contract (single source of truth for the UI).
- `src/api.ts` — fetch/POST wrappers for the API.
- `src/hooks/useBackendState.ts` — 400 ms polling with offline fallback.
- `src/components/` — `TopBar`, `Hero` (mascot + score), `BaselineCard`,
  `LivePanel` (Plotly charts), `Actions`, `Sparkles`.
- `src/visual.ts` — displayState → mascot/label/color mapping.

The previous vanilla HTML/CSS/JS implementation is kept under
[`legacy/`](legacy/) for reference.
