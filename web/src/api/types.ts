// Mirrors src/tsetmc_viewer/analytics/models.py (the API contract, see /docs).
// Money is integer Rial; ratios are plain fractions (0.012 = 1.2%).

export type FundType =
  | "equity"
  | "index"
  | "sector"
  | "leveraged"
  | "fixed_income"
  | "mixed"
  | "commodity"
  | "other";

export interface FundSnapshot {
  ins_code: string;
  symbol: string;
  name: string;
  fund_type: FundType;
  fund_type_fa: string;
  ts: string;
  last_price: number;
  close_price: number;
  prev_close: number;
  change: number | null;
  nav: number | null;
  nav_at: string | null;
  premium: number | null;
  units: number | null;
  aum: number | null;
  share_of_aum: number | null;
  value: number;
  volume: number;
  trade_count: number;
  block_value: number;
  ind_net_flow: number;
  inst_net_flow: number;
  buyer_power: number | null;
  turnover: number | null;
  quality_flags: string[];
  /** TSETMC trading status, refreshed every few minutes; "unknown" before the first check. */
  status_kind: "open" | "suspended" | "reserved" | "blocked" | "forbidden" | "unknown";
  status_title: string | null;
  status_at: string | null;
  under_supervision: boolean;
}

export interface Overview {
  session_date: string;
  session_date_fa: string;
  last_update: string | null;
  is_live: boolean;
  funds: number;
  total_aum: number;
  total_value: number;
  ind_net_flow: number;
  median_premium: number | null;
  weighted_premium: number | null;
  at_premium: number;
  at_discount: number;
  advancers: number;
  decliners: number;
  unchanged: number;
  index_value: number | null;
  index_change: number | null;
  completeness: number | null;
  holiday_today: string | null;
  not_trading: number; // funds whose status is not «مجاز»
}

export interface PremiumPoint {
  at: string; // ISO datetime (intraday) or date (daily)
  at_fa: string; // "1405/07/01"
  median: number | null;
  weighted: number | null;
  funds: number;
}

export interface MarketFlowPoint {
  ts: string;
  ind_net_flow: number;
  value: number;
  index_value: number | null;
}

export interface FundIntradayPoint {
  ts: string;
  last_price: number;
  close_price: number;
  nav: number | null;
  premium: number | null;
  ind_net_flow: number | null; // null on backfilled minutes
  volume: number;
  quality_flags: string[];
  /** Rebuilt from today's trades (collector started late): price and volume only. */
  backfilled: boolean;
}

export interface DailyFlow {
  trade_date: string;
  trade_date_fa: string;
  fund_type: FundType;
  ind_net_flow: number;
  value: number;
  estimated: boolean;
}

export interface FundReturns {
  ins_code: string;
  symbol: string;
  fund_type: FundType;
  r_1d: number | null;
  r_1w: number | null;
  r_1m: number | null;
  r_3m: number | null;
  r_ytd: number | null;
}

export interface FundRisk {
  ins_code: string;
  symbol: string;
  fund_type: FundType;
  volatility: number | null;
  period_return: number | null;
  aum: number | null;
}

export interface DailyBar {
  trade_date: string;
  trade_date_fa: string;
  close_price: number;
  value: number;
  ind_net_flow: number;
}

export interface FundDetail {
  snapshot: FundSnapshot;
  returns: FundReturns | null;
  history: DailyBar[];
}

export interface QualityReport {
  runs_by_status: Record<string, number>;
  completeness: number;
  ticks: number;
  flag_counts: Record<string, number>;
  issues: [string, string, string, number][];
}

export interface SessionInfo {
  day: string;
  day_fa: string;
  has_intraday: boolean;
}

export interface Health {
  status: "ok" | "degraded";
  clickhouse: boolean;
  version: string;
  collector?: {
    state: "ok" | "stale" | "idle";
    last_run: { tick: string; finished_at: string; status: string } | null;
    lag_seconds?: number;
    failed_streak?: number;
  };
}
