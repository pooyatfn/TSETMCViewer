# ADR 0007 — Fund Identity: Main Board and Sub-Boards

<div class="adr-meta"><span>Status: Accepted</span><span>Date: Day 2</span></div>

!!! abstract "Summary"
    A fund in TSETMC can have multiple symbols: the main board (e.g. "Atlas"), sub-boards (e.g. "Sahamdar2" and "Yaghut4"), and dozens of options written on it. **The key for each fund is the main-board symbol.** Sub-board turnover is aggregated into the same fund, and options are discarded.

## Context

In the real watchlist data (2 Mehr 1405):

| Group | Count | Example | ISIN |
|---|--:|---|---|
| Fund main board | 332 | Atlas | `IRT3SATF0001` |
| Fund sub-board | 100 | Sahamdar2, Yaghut4, Kara4 | `IRT3SAHF0002`, `IRT1YGHT0004` |
| Options on a fund | 561 | ZATLAS090802, TAVAN918 | `IROASATF8461`, `IROB…` |

All of these symbols are in **group 68**. If we assume group 68 is "funds", 661 symbols enter the analysis incorrectly. If we take only the main board and ignore sub-boards, part of the fund's real turnover is lost. Of the 100 sub-boards, 100 symbols traded that same day.

## Decision

1. **Fund unit** = group `68` **and** an ISIN with the `IRT` prefix. The `IRO` (option) prefix is excluded.
2. **Fund identity** = the main-board symbol (ISIN with the `0001` suffix). NAV, fund type, and unit count are read only for this symbol.
3. **ISIN root** (without the last 4 characters, e.g. `IRT3SATF`) links sub-boards to the fund. Their volume and value are aggregated into `block_volume` and `block_value` for that same tick, and **not added to the main board's volume**, since sub-board pricing may differ.
4. **Fund type** is read from the main symbol's `faraDesc`. If it's only "Equity" ("سهامی"), the fund's name is checked to distinguish "Index" and "Sector" types. The `IRTK` prefix means a commodity fund.

## Rejected Options

- **A manual fund list:** silently goes stale whenever a new fund is listed.
- **Detection from the symbol name** (e.g. a trailing number): names follow no fixed rule (e.g. "Petrosaba2" vs. "Dara1"). ISIN is standardized.
- **Using FIPIRAN for the list:** the domain wasn't accessible ([Data Sources](../02-data-sources.md)).

## Consequences

- ➕ The fund list updates automatically every day with no manual maintenance.
- ➕ Liquidity analysis also sees block trades.
- ➖ If TSETMC changes its ISIN pattern, identification breaks. Real-data tests and the `expected_funds` metric in `collection_runs` surface this risk early (a sudden drop in fund count).
- ⚠️ The "Dara1" fund is an index fund, but its `faraDesc` is only "Equity", and its name gives no hint either. This fund is classified as "Equity". For cases like this, a small override table is planned for later steps.

## Review — Day 4: When `faraDesc` Is Empty

A full market capture showed that 81 of 333 funds have no `faraDesc`, including 21 equity and sector funds. Clause 4 of this decision was completed: if the official description is empty, the **type letter at the end of the name** (`-س`, `-ب`, `-د`, `-م`) is used, followed by keywords in the name. This rule was measured against the 252 funds that have both, with 99.2% agreement, and is kept as a test against the full real list ([Data Sources](../02-data-sources.md#classification-coverage-across-the-whole-market)). Result: the equity family grew from 138 to **159** funds.
