import type {
  DailyFlow,
  FundDetail,
  FundIntradayPoint,
  FundReturns,
  FundRisk,
  FundSnapshot,
  Health,
  MarketFlowPoint,
  Overview,
  PremiumPoint,
  QualityReport,
  SessionInfo,
} from "./types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  // Same-origin: Vite (dev) and nginx (Docker) both proxy /api to FastAPI.
  // The browser revalidates with If-None-Match, so unchanged data costs a 304.
  const res = await fetch(path, { signal, headers: { Accept: "application/json" } });
  if (!res.ok) {
    const detail = await res.json().then((b) => b?.detail, () => res.statusText);
    throw new ApiError(res.status, String(detail ?? res.statusText));
  }
  return (await res.json()) as T;
}

/** Every endpoint below takes the session date as `date=YYYY-MM-DD`; omit for the latest session. */
function q(params: Record<string, string | number | undefined>): string {
  const parts = Object.entries(params).filter(([, v]) => v !== undefined) as [string, string | number][];
  return parts.length ? `?${parts.map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join("&")}` : "";
}

export const api = {
  health: (s?: AbortSignal) => get<Health>("/api/v1/health", s),
  sessions: (s?: AbortSignal) => get<SessionInfo[]>("/api/v1/sessions", s),
  overview: (date: string | undefined, s?: AbortSignal) =>
    get<Overview>(`/api/v1/overview${q({ date })}`, s),
  funds: (date: string | undefined, s?: AbortSignal) =>
    get<FundSnapshot[]>(`/api/v1/funds${q({ date })}`, s),
  returns: (date: string | undefined, s?: AbortSignal) =>
    get<FundReturns[]>(`/api/v1/returns${q({ date })}`, s),
  dailyFlows: (days: number, date: string | undefined, s?: AbortSignal) =>
    get<DailyFlow[]>(`/api/v1/flows/daily${q({ date, days })}`, s),
  risk: (days: number, date: string | undefined, s?: AbortSignal) =>
    get<FundRisk[]>(`/api/v1/risk${q({ date, days })}`, s),
  premiumDaily: (days: number, date: string | undefined, s?: AbortSignal) =>
    get<PremiumPoint[]>(`/api/v1/premium/daily${q({ date, days })}`, s),
  premiumIntraday: (date: string | undefined, s?: AbortSignal) =>
    get<PremiumPoint[]>(`/api/v1/premium/intraday${q({ date })}`, s),
  marketFlow: (date: string | undefined, s?: AbortSignal) =>
    get<MarketFlowPoint[]>(`/api/v1/market/flow${q({ date })}`, s),
  quality: (date: string | undefined, s?: AbortSignal) =>
    get<QualityReport>(`/api/v1/quality${q({ date })}`, s),
  fund: (ins: string, days: number, date: string | undefined, s?: AbortSignal) =>
    get<FundDetail>(`/api/v1/funds/${encodeURIComponent(ins)}${q({ date, days })}`, s),
  fundIntraday: (ins: string, date: string | undefined, s?: AbortSignal) =>
    get<FundIntradayPoint[]>(`/api/v1/funds/${encodeURIComponent(ins)}/intraday${q({ date })}`, s),
};
