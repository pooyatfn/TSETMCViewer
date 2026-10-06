# ADR 0008 — Web Panel Stack

<div class="adr-meta"><span>Status: Accepted</span><span>Date: Day 5</span><span>Implementation: Day 5</span></div>

!!! abstract "Summary"
    A small SPA with **React + Vite + TypeScript** and **ECharts** (SVG rendering), with no router, state manager, or UI library. The panel is served by **nginx** on the same origin as the API. Each chart's option is a pure function of (data, color tokens).

## Context

- The panel has two views (dashboard and fund page), six analytical charts, and one table. Data only changes once a minute, and the server announces it via SSE ([ADR 0006](0006-caching.md)).
- The language is Persian and right-to-left: correct glyph shaping in charts, a right-to-left time axis, and number signs in RTL text.
- The deadline for the whole panel is one day, so every added dependency must earn back its own learning and maintenance cost.
- In the technical interview, code structure and quality are evaluated. The code must be small, typed, and testable.

## Decision

| Area | Choice | Reason |
|---|---|---|
| Framework | React 19 + TypeScript strict | A large ecosystem and precise types. `noUncheckedIndexedAccess` catches common array-access errors at compile time. |
| Build tool | Vite 7 | A dev server with an `/api` proxy, fast builds, and ECharts split into its own chunk. |
| Charts | ECharts 6 with SVG rendering | Has treemap, heatmap, scatter, and multiple grids on a shared axis ready to go. SVG shapes Persian text with the page's font. Only the charts actually used are registered (`echarts/core`). |
| Data | A small `useQuery` + `useLiveTicks` hook | The panel's only "server state" is a tick counter. Each card refetches its own data when the tick changes, and shows the previous data until then. |
| Routing | Hash-based (`#/fund/<ins>`) | Two views. Needs no server configuration, and each fund's address is shareable. |
| Styling | Plain CSS with color tokens | The same tokens are used in CSS and, via `getComputedStyle`, in ECharts. The dark theme has its own separate values. |
| Serving | nginx in the `web` container | Same origin as the API, so CORS is not needed at runtime. Unbuffered SSE, and a one-year cache for hashed files. |

### Chart Option as a Pure Function

```ts
// web/src/charts/options.ts
export function premiumOption(funds: FundSnapshot[], t: Tokens): ChartOption
```

No option builder touches the DOM or React state. As a result:

- Display-related financial decisions (excluding leveraged funds, pinning large bubbles to the edge, each column's color scale) have **unit tests** and run without a browser.
- A theme change just means re-reading the tokens and rebuilding the option. The `Chart` component is just a thin wrapper around the ECharts instance.

## Rejected Options

| Option | Why not |
|---|---|
| **Streamlit / Dash** | Fast for a first prototype, but RTL control, theming, and layout are limited. Every interaction is also a round trip to a Python server. |
| **Next.js** | Server-side rendering and file-based routing are unnecessary for a two-view dashboard behind an API, and it adds another Node server to compose. |
| **Recharts / Chart.js** | Either lack a treemap and heatmap or have weak support for them. Multiple aligned grids on one time axis (instead of a dual Y-axis) are ready-made in ECharts. |
| **TanStack Query + React Router + a UI library** | All three are built for a bigger problem. Here, ~60 lines of hooks do the same job, and the code is clearer for the interviewer. |
| **ECharts Canvas rendering** | Blurs on browser zoom, and Persian text shapes worse in it. Our element count (at most a few hundred points) is too small to need it over SVG. |
| **Polling every 10 seconds** | With SSE in place, every extra request is wasted. Outside market hours the panel sends no requests at all. |

## Consequences

- ➕ The panel's total JavaScript is about 285 KB gzipped (ECharts accounts for 204 KB of that).
- ➕ No runtime dependencies other than React, ECharts, and the Vazirmatn font.
- ➕ The panel and API share one origin. The browser revalidates with `ETag`, and unchanged data gets a `304`.
- ➖ Adding a third view or complex forms may later need a router or data library. Moving to one is easy since each view only depends on `api` and the hooks.
- ⚠️ ECharts lays out text left-to-right. The chart container has `direction: ltr`, and tooltips are RTL. Signed numbers are printed with Unicode isolates so the sign stays on the left.

## Day 7 Review

The charts' time axis is no longer reversed, and dates now increase left to right, matching the convention for financial charts and per the user's request. The reasoning and details of this change are in [Panel and Charts](../06-dashboard.md#day-7-review-time-axis-direction). The rest of the UI stays right-to-left.
