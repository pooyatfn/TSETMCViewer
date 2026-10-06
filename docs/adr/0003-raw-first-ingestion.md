# ADR 0003 — Storing the Raw Response Before Parsing

<div class="adr-meta"><span>Status: Accepted</span><span>Date: Day 1</span></div>

!!! abstract "Summary"
    The TSETMC site API is undocumented, and intraday data cannot be re-fetched. So every response, before any interpretation, is stored untouched so it can later be replayed and audited.

## Context

- The TSETMC site API has no official, versioned documentation. Field names are abbreviations (`pDrCotVal`, `qTotTran5J`) and may change without notice.
- Intraday data **cannot be recovered**: if the parser errors today at 10:30, TSETMC will not give back tomorrow's snapshot of that 10:30 moment.

## Decision

Every HTTP response, **whatever it is** (200, 404, or a non-JSON body), is stored in `raw_snapshots` along with `run_id`, timestamp, endpoint, status code, latency, and attempt count, before any parsing. Parsing, validation, and writing clean data are later stages whose input is this raw response.

For this, clients return a `RawResponse`, not a parsed model.

## Consequences

- ➕ **Replay:** once the parser is fixed, clean data for recent days can be rebuilt from the raw data.
- ➕ **Audit:** for any number shown on the dashboard, the exact source response can be displayed.
- ➕ **Provider monitoring:** TSETMC's latency and error rate can be analyzed over time.
- ➖ Storage: with ZSTD compression and a 30-day TTL, the cost is negligible (estimate: under 1 GB per month).
