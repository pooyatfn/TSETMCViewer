import { describe, expect, it } from "vitest";

import type { FundIntradayPoint, FundSnapshot } from "../api/types";
import {
  dailyFlowsOption,
  fundHistoryOption,
  fundIntradayOption,
  marketFlowOption,
  moneyMapOption,
  premiumOption,
  premiumTrendOption,
  returnsOption,
  treemapOption,
} from "./options";
import { diverging, inkOn, type Tokens } from "./theme";

const T: Tokens = {
  surface: "#ffffff", surface2: "#f0efec", ink: "#0b0b0b", ink2: "#52514e", muted: "#898781",
  grid: "#e1e0d9", axis: "#c3c2b7", deemph: "#c3c2b7", divPos: "#2a78d6", divNeg: "#e34948",
  divMid: "#f0efec", good: "#006300", bad: "#d03b3b", font: "Vazirmatn",
  type: { equity: "#2a78d6", sector: "#eb6834", index: "#1baf7a", leveraged: "#eda100" },
  series: ["#2a78d6", "#eb6834"],
};

function fund(p: Partial<FundSnapshot>): FundSnapshot {
  return {
    ins_code: "1", symbol: "الف", name: "صندوق الف", fund_type: "equity", fund_type_fa: "سهامی",
    ts: "2026-09-24T12:00:00+03:30", last_price: 100, close_price: 100, prev_close: 100, change: 0,
    nav: 100, nav_at: null, premium: 0, units: 1, aum: 100, share_of_aum: null, value: 0, volume: 0,
    trade_count: 0, block_value: 0, ind_net_flow: 0, inst_net_flow: 0, buyer_power: null,
    turnover: null, quality_flags: [], status_kind: "open", status_title: "مجاز", status_at: null,
    under_supervision: false, ...p,
  };
}

type Series = { type: string; data: { fund?: FundSnapshot; value?: unknown }[] };
const series = (o: object) => (o as { series: Series[] }).series;

describe("chart option builders", () => {
  const funds = [
    fund({ ins_code: "a", premium: 0.02 }),
    fund({ ins_code: "b", fund_type: "leveraged", fund_type_fa: "اهرمی", premium: null }),
    fund({ ins_code: "c", fund_type: "fixed_income", fund_type_fa: "درآمد ثابت", premium: 0.01 }),
  ];

  it("keeps leveraged funds (no comparable NAV) and non-equity funds off the premium strip", () => {
    const dots = series(premiumOption(funds, T))[0]!.data;
    expect(dots.map((d) => d.fund?.ins_code)).toEqual(["a"]);
  });

  it("clamps extreme premiums to the money map's edge instead of dropping them", () => {
    const dots = series(moneyMapOption([fund({ premium: 0.4 })], T))[0]!.data;
    expect((dots[0]!.value as number[])[0]).toBe(0.1);
  });

  it("groups the treemap by equity type only", () => {
    const groups = series(treemapOption(funds, T))[0]!.data as unknown as { name: string }[];
    expect(groups.map((g) => g.name)).toEqual(["سهامی", "اهرمی"]);
  });
});

describe("time runs left to right", () => {
  type Axis = { inverse?: boolean; data?: string[] };
  const axes = (o: object): Axis[] => {
    const x = (o as { xAxis: Axis | Axis[] }).xAxis;
    return Array.isArray(x) ? x : [x];
  };

  it("never inverts a time axis and sorts points oldest → newest", () => {
    const flow = marketFlowOption(
      [
        { ts: "2026-09-26T10:02:00+03:30", ind_net_flow: 3, value: 1, index_value: 1 },
        { ts: "2026-09-26T10:01:00+03:30", ind_net_flow: 2, value: 1, index_value: 1 },
      ],
      T,
    );
    for (const a of axes(flow)) expect(a.inverse).toBeFalsy();
    expect((series(flow)[0]!.data as unknown as number[])).toEqual([2, 3]);

    const bars = fundHistoryOption(
      [
        { trade_date: "2026-09-23", trade_date_fa: "1405/07/01", close_price: 20, value: 0, ind_net_flow: 0 },
        { trade_date: "2026-09-22", trade_date_fa: "1405/06/31", close_price: 10, value: 0, ind_net_flow: 0 },
      ],
      T,
    );
    for (const a of axes(bars)) expect(a.inverse).toBeFalsy();
    expect((series(bars)[0]!.data as unknown as number[])).toEqual([10, 20]);

    const daily = dailyFlowsOption(
      [
        { trade_date: "2026-09-23", trade_date_fa: "1405/07/01", fund_type: "equity", ind_net_flow: 1, value: 1, estimated: false },
        { trade_date: "2026-09-22", trade_date_fa: "1405/06/31", fund_type: "equity", ind_net_flow: 1, value: 1, estimated: false },
      ],
      T,
    );
    expect(axes(daily)[0]!.inverse).toBeFalsy();
    expect(axes(daily)[0]!.data).toEqual(["۰۶/۳۱", "۰۷/۰۱"]);
  });

  it("orders return horizons short → long, left to right", () => {
    const heat = returnsOption(
      [{ ins_code: "a", symbol: "الف", fund_type: "equity", r_1d: 0, r_1w: 0, r_1m: 0, r_3m: 0, r_ytd: 0 }],
      T,
    );
    const x = axes(heat)[0]!;
    expect(x.inverse).toBeFalsy();
    expect(x.data?.[0]).toBe("۱ روز");
    expect(x.data?.at(-1)).toBe("از ابتدای سال");
  });
});

describe("market premium trend", () => {
  it("draws median solid and weighted dashed, oldest point first", () => {
    const o = premiumTrendOption(
      [
        { at: "2026-09-26", at_fa: "1405/07/04", median: 0.01, weighted: 0.02, funds: 150 },
        { at: "2026-09-23", at_fa: "1405/07/01", median: -0.01, weighted: 0, funds: 150 },
      ],
      T,
      false,
    );
    const s = series(o) as unknown as { data: number[]; lineStyle: { type: string } }[];
    expect(s[0]!.data).toEqual([-0.01, 0.01]);
    expect(s[0]!.lineStyle.type).toBe("solid");
    expect(s[1]!.lineStyle.type).toBe("dashed");
  });
});

describe("fund intraday with backfilled minutes (ADR 0012)", () => {
  const point = (hm: string, price: number, backfilled: boolean): FundIntradayPoint => ({
    ts: `2026-09-26T${hm}:00+03:30`, last_price: price, close_price: price,
    nav: backfilled ? null : price, premium: backfilled ? null : 0,
    ind_net_flow: backfilled ? null : 0, volume: 1, quality_flags: [], backfilled,
  });
  const o = fundIntradayOption(
    [point("11:31", 1030, false), point("09:00", 1000, true), point("11:30", 1020, false), point("09:01", 1010, true)],
    T,
  );

  it("draws rebuilt minutes as a separate dashed price line joined to the first live point", () => {
    const [live, nav, rebuilt] = series(o) as unknown as { data: (number | null)[]; lineStyle: { type?: string } }[];
    expect(live?.data).toEqual([null, null, 102, 103]);
    expect(nav?.data).toEqual([null, null, 102, 103]);
    expect(rebuilt?.data).toEqual([100, 101, 102, null]);
    expect(rebuilt?.lineStyle.type).toBe("dashed");
  });

  it("adds no extra series when nothing was backfilled", () => {
    expect(series(fundIntradayOption([point("11:30", 1020, false)], T))).toHaveLength(2);
  });
});

describe("colour helpers", () => {
  it("diverging scale is neutral at zero and missing values, saturated at the limit", () => {
    expect(diverging(T, 0, 0.03)).toBe("rgb(240, 239, 236)");
    expect(diverging(T, null, 0.03)).toBe(T.divMid);
    expect(diverging(T, 0.5, 0.03)).toBe("rgb(42, 120, 214)");
    expect(diverging(T, -0.5, 0.03)).toBe("rgb(227, 73, 72)");
  });

  it("picks readable text on filled cells", () => {
    expect(inkOn("#0b0b0b")).toBe("#ffffff");
    expect(inkOn("#f0efec")).toBe("#0b0b0b");
  });
});
