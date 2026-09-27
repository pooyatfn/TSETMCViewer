// ECharts option builders — pure functions of (data, tokens), one per chart.
// Every chart answers one question; see docs/06-dashboard.md for the "why".

import type {
  DailyBar,
  DailyFlow,
  FundIntradayPoint,
  FundReturns,
  FundRisk,
  FundSnapshot,
  MarketFlowPoint,
  PremiumPoint,
} from "../api/types";
import { axisMilliard, faDate, money, num, pct, price, time } from "../lib/format";
import type { ChartOption } from "./Chart";
import {
  axisStyle,
  base,
  diverging,
  inkOn,
  isEquityType,
  type EquityType,
  type Tokens,
  TYPE_FA,
  TYPE_ORDER,
} from "./theme";

const esc = (s: string) => s.replace(/[<>&]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" })[c] ?? c);

/**
 * Time runs left → right (oldest → newest) in every chart, whatever order the API used.
 * ISO timestamps/dates of one timezone sort correctly as strings.
 */
export function chronological<T>(items: readonly T[], key: (item: T) => string): T[] {
  return [...items].sort((a, b) => key(a).localeCompare(key(b)));
}

function tipRows(title: string, rows: [string, string][]): string {
  const body = rows
    .map(([k, v]) => `<div style="display:flex;gap:16px;justify-content:space-between"><span style="opacity:.7">${k}</span><b>${v}</b></div>`)
    .join("");
  return `<div style="min-width:170px"><div style="font-weight:700;margin-bottom:4px">${esc(title)}</div>${body}</div>`;
}

// ---------------------------------------------------------------------------
// 1. Treemap — "Where is the money, and how did it move today?"
//    area = net assets, colour = daily change (diverging, ±3% saturates)
// ---------------------------------------------------------------------------
export function treemapOption(funds: FundSnapshot[], t: Tokens): ChartOption {
  const groups = TYPE_ORDER.map((type) => ({
    name: TYPE_FA[type],
    children: funds
      .filter((f) => f.fund_type === type && f.aum)
      .map((f) => {
        const fill = diverging(t, f.change, 0.03);
        return {
          name: f.symbol,
          value: f.aum,
          ins: f.ins_code,
          fund: f,
          itemStyle: { color: fill },
          label: { color: inkOn(fill) },
        };
      }),
  })).filter((g) => g.children.length);

  return {
    ...base(t),
    tooltip: {
      ...base(t).tooltip,
      formatter: (p: { data?: { fund?: FundSnapshot }; name: string; value: number }) => {
        const f = p.data?.fund;
        if (!f) return tipRows(p.name, [["خالص دارایی", money(p.value)]]);
        return tipRows(`${f.symbol} · ${f.fund_type_fa}`, [
          ["خالص دارایی", money(f.aum)],
          ["سهم از کل", pct(f.share_of_aum)],
          ["تغییر امروز", pct(f.change, { signed: true })],
          ["حباب", f.premium == null ? "قابل محاسبه نیست" : pct(f.premium, { signed: true })],
          ["ورود پول حقیقی", money(f.ind_net_flow, { signed: true })],
        ]);
      },
    },
    series: [
      {
        type: "treemap",
        data: groups,
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        width: "100%",
        height: "100%",
        top: 0,
        left: 0,
        leafDepth: 2,
        squareRatio: 1.2,
        label: {
          show: true,
          fontFamily: t.font,
          fontSize: 12,
          overflow: "truncate",
          formatter: (p: { name: string; data?: { fund?: FundSnapshot } }) =>
            p.data?.fund ? `${p.name}\n${pct(p.data.fund.change, { signed: true })}` : p.name,
        },
        upperLabel: {
          show: true,
          height: 22,
          color: t.ink,
          fontFamily: t.font,
          fontWeight: 700,
          backgroundColor: t.surface,
        },
        itemStyle: { borderColor: t.surface, borderWidth: 2, gapWidth: 2 },
        levels: [
          { itemStyle: { borderWidth: 0, gapWidth: 6, borderColor: t.surface } },
          { itemStyle: { borderColor: t.surface, borderWidth: 3, gapWidth: 2 }, upperLabel: { show: true } },
          { itemStyle: { borderColor: t.surface, borderWidth: 1, gapWidth: 1 } },
        ],
      },
    ],
  };
}

// ---------------------------------------------------------------------------
// 2. Intraday money flow + index — "Is retail money entering or leaving right now?"
//    two stacked panels on one time axis (never a dual y-axis)
// ---------------------------------------------------------------------------
export function marketFlowOption(input: MarketFlowPoint[], t: Tokens): ChartOption {
  const points = chronological(input, (p) => p.ts);
  const ax = axisStyle(t);
  const x = points.map((p) => time(p.ts));
  const flow = points.map((p) => p.ind_net_flow);
  const last = flow.at(-1) ?? 0;
  const color = last >= 0 ? t.divPos : t.divNeg;
  return {
    ...base(t),
    tooltip: {
      ...base(t).tooltip,
      trigger: "axis",
      axisPointer: { type: "line", lineStyle: { color: t.axis } },
      formatter: (ps: { dataIndex: number }[]) => {
        const i = ps[0]?.dataIndex ?? 0;
        const p = points[i];
        if (!p) return "";
        return tipRows(time(p.ts), [
          ["ورود پول حقیقی (تجمعی)", money(p.ind_net_flow, { signed: true })],
          ["ارزش معاملات", money(p.value)],
          ["شاخص کل", p.index_value ? num(p.index_value) : "—"],
        ]);
      },
    },
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    grid: [
      { top: 12, left: 60, right: 104, height: "58%" },
      { bottom: 24, left: 60, right: 104, height: "22%" },
    ],
    xAxis: [
      { type: "category", data: x, gridIndex: 0, boundaryGap: false, ...ax, axisLabel: { show: false } },
      { type: "category", data: x, gridIndex: 1, boundaryGap: false, ...ax },
    ],
    yAxis: [
      { type: "value", gridIndex: 0, position: "left", ...ax, axisLabel: { ...ax.axisLabel, formatter: axisMilliard } },
      { type: "value", gridIndex: 1, position: "left", scale: true, ...ax, splitNumber: 2,
        axisLabel: { ...ax.axisLabel, formatter: (v: number) => num(v / 1e6, 2) } },
    ],
    series: [
      {
        name: "ورود پول حقیقی",
        type: "line",
        data: flow,
        xAxisIndex: 0,
        yAxisIndex: 0,
        showSymbol: points.length < 3,
        symbolSize: 8,
        lineStyle: { width: 2, color },
        itemStyle: { color },
        areaStyle: { color, opacity: 0.1 },
        markLine: { silent: true, symbol: "none", data: [{ yAxis: 0 }], lineStyle: { color: t.axis, type: "solid" }, label: { show: false } },
        endLabel: { show: true, formatter: () => money(last, { signed: true }), color: t.ink, fontFamily: t.font, fontWeight: 700 },
      },
      {
        name: "شاخص کل",
        type: "line",
        data: points.map((p) => p.index_value),
        xAxisIndex: 1,
        yAxisIndex: 1,
        showSymbol: points.length < 3,
        symbolSize: 8,
        lineStyle: { width: 2, color: t.deemph },
        itemStyle: { color: t.deemph },
      },
    ],
  };
}

// ---------------------------------------------------------------------------
// 3. Daily individual flow by fund type — "Which kind of fund is money rotating into?"
//    stacked by sign; today's live estimate drawn lighter and labelled
// ---------------------------------------------------------------------------
export function dailyFlowsOption(flows: DailyFlow[], t: Tokens): ChartOption {
  const ax = axisStyle(t);
  const days = [...new Set(flows.map((f) => f.trade_date))].sort();
  const faLabel = new Map(flows.map((f) => [f.trade_date, faDate(f.trade_date_fa).slice(5)]));
  const estimated = new Set(flows.filter((f) => f.estimated).map((f) => f.trade_date));
  const cell = new Map(flows.map((f) => [`${f.trade_date}|${f.fund_type}`, f]));
  return {
    ...base(t),
    tooltip: {
      ...base(t).tooltip,
      trigger: "axis",
      axisPointer: { type: "shadow", shadowStyle: { color: t.surface2, opacity: 0.6 } },
      formatter: (ps: { dataIndex: number }[]) => {
        const d = days[ps[0]?.dataIndex ?? 0];
        if (!d) return "";
        const rows: [string, string][] = TYPE_ORDER.map((ty) => [
          TYPE_FA[ty],
          money(cell.get(`${d}|${ty}`)?.ind_net_flow ?? 0, { signed: true }),
        ]);
        const total = TYPE_ORDER.reduce((s, ty) => s + (cell.get(`${d}|${ty}`)?.ind_net_flow ?? 0), 0);
        rows.push(["جمع", money(total, { signed: true })]);
        return tipRows(`${faLabel.get(d)}${estimated.has(d) ? " · تخمینی" : ""}`, rows);
      },
    },
    grid: { top: 12, left: 56, right: 12, bottom: 28 },
    xAxis: {
      type: "category",
      data: days.map((d) => (estimated.has(d) ? `${faLabel.get(d)} *` : faLabel.get(d))),
      ...ax,
      splitLine: { show: false },
      axisLabel: { ...ax.axisLabel, interval: "auto", hideOverlap: true },
    },
    yAxis: { type: "value", position: "left", ...ax, axisLabel: { ...ax.axisLabel, formatter: axisMilliard } },
    series: TYPE_ORDER.map((ty) => ({
      name: TYPE_FA[ty],
      type: "bar",
      stack: "flow",
      stackStrategy: "samesign",
      barMaxWidth: 24,
      itemStyle: { color: t.type[ty], borderColor: t.surface, borderWidth: 1 },
      emphasis: { focus: "series" },
      data: days.map((d) => ({
        value: cell.get(`${d}|${ty}`)?.ind_net_flow ?? 0,
        itemStyle: estimated.has(d) ? { opacity: 0.45 } : undefined,
      })),
    })),
  };
}

// ---------------------------------------------------------------------------
// 4. NAV premium by type — "Is the market paying up or getting a discount, and where?"
//    one row per type, dot size = net assets, orange tick = row median
// ---------------------------------------------------------------------------
export function premiumOption(funds: FundSnapshot[], t: Tokens): ChartOption {
  const ax = axisStyle(t);
  const rows = TYPE_ORDER;
  const maxAum = Math.max(1, ...funds.map((f) => f.aum ?? 0));
  const jitter = (s: string) => ((s.split("").reduce((a, c) => a + c.charCodeAt(0), 0) % 21) - 10) / 40;
  const pts = funds
    .filter((f) => isEquityType(f.fund_type) && f.premium != null)
    .map((f) => ({
      value: [Math.max(-0.35, Math.min(0.15, f.premium ?? 0)), rows.indexOf(f.fund_type as EquityType) + jitter(f.symbol)],
      fund: f,
      symbolSize: 6 + 18 * Math.sqrt((f.aum ?? 0) / maxAum),
      itemStyle: { color: t.type[f.fund_type as EquityType] },
    }));
  const medians = rows.map((ty, i) => {
    const v = funds.filter((f) => f.fund_type === ty && f.premium != null).map((f) => f.premium as number).sort((a, b) => a - b);
    const m = v.length ? (v[Math.floor((v.length - 1) / 2)]! + v[Math.ceil((v.length - 1) / 2)]!) / 2 : null;
    return m == null ? null : [[m, i - 0.35], [m, i + 0.35]];
  });
  return {
    ...base(t),
    tooltip: {
      ...base(t).tooltip,
      formatter: (p: { data: { fund: FundSnapshot } }) => {
        const f = p.data.fund;
        return tipRows(`${f.symbol} · ${f.fund_type_fa}`, [
          ["حباب", pct(f.premium, { signed: true })],
          ["قیمت پایانی", `${price(f.close_price)} ت`],
          ["NAV ابطال", `${price(f.nav)} ت`],
          ["خالص دارایی", money(f.aum)],
        ]);
      },
    },
    grid: { top: 8, left: 16, right: 64, bottom: 28 },
    xAxis: {
      type: "value",
      min: -0.35,
      max: 0.15,
      ...ax,
      axisLine: { ...ax.axisLine, onZero: false }, // rows are categories: keep the axis at the bottom
      axisLabel: { ...ax.axisLabel, formatter: (v: number) => pct(v, { digits: 0, signed: true }) },
    },
    // Rows are drawn as labelled bands; a value axis keeps the jitter continuous.
    yAxis: { type: "value", min: -0.5, max: rows.length - 0.5, show: false },
    series: [
      {
        type: "scatter",
        data: pts,
        itemStyle: { opacity: 0.75, borderColor: t.surface, borderWidth: 1 },
        emphasis: { itemStyle: { opacity: 1 } },
        markLine: {
          silent: true,
          symbol: "none",
          label: { show: false },
          lineStyle: { color: t.axis, type: "solid", width: 1 },
          data: [{ xAxis: 0 }],
        },
      },
      ...medians.flatMap((seg, i) =>
        seg
          ? [{ type: "line", data: seg, symbol: "none", silent: true, lineStyle: { color: t.ink, width: 3 }, z: 5, name: `median-${i}` }]
          : [],
      ),
      {
        type: "scatter",
        silent: true,
        symbolSize: 0,
        data: [
          ...rows.map((ty, i) => ({
            value: [0.15, i],
            label: { formatter: TYPE_FA[ty], position: "right", color: t.ink2, fontSize: 12, distance: 10 },
          })),
          {
            value: [-0.1, rows.indexOf("leveraged")],
            label: { formatter: "حباب اهرمی‌ها قابل محاسبه نیست", position: "inside", color: t.muted, fontSize: 11.5 },
          },
        ],
        label: { show: true, fontFamily: t.font },
      },
    ],
  };
}

// ---------------------------------------------------------------------------
// 5. Money × valuation map — "Is retail chasing expensive funds or buying discounts?"
//    x = premium, y = today's individual flow as % of net assets, size = net assets
// ---------------------------------------------------------------------------
export function moneyMapOption(funds: FundSnapshot[], t: Tokens): ChartOption {
  const ax = axisStyle(t);
  const pts = funds
    .filter((f) => f.premium != null && f.aum)
    .map((f) => ({ f, x: Math.max(-0.1, Math.min(0.1, f.premium as number)), y: f.ind_net_flow / (f.aum as number) }));
  const yMax = Math.max(0.002, ...pts.map((p) => Math.abs(p.y))) * 1.1;
  const maxAum = Math.max(1, ...pts.map((p) => p.f.aum ?? 0));
  const labelled = new Set([...pts].sort((a, b) => Math.abs(b.f.ind_net_flow) - Math.abs(a.f.ind_net_flow)).slice(0, 6).map((p) => p.f.ins_code));
  const quadrant = (x: number, y: number, text: string, align: "left" | "right") => ({
    value: [x, y],
    label: { show: true, formatter: text, color: t.muted, fontFamily: t.font, fontSize: 11.5, align },
  });
  return {
    ...base(t),
    tooltip: {
      ...base(t).tooltip,
      formatter: (p: { data: { fund?: FundSnapshot } }) => {
        const f = p.data.fund;
        if (!f) return "";
        return tipRows(`${f.symbol} · ${f.fund_type_fa}`, [
          ["حباب", pct(f.premium, { signed: true })],
          ["ورود پول حقیقی", money(f.ind_net_flow, { signed: true })],
          ["نسبت به دارایی", pct(f.ind_net_flow / (f.aum ?? 1), { signed: true, digits: 2 })],
          ["خالص دارایی", money(f.aum)],
        ]);
      },
    },
    grid: { top: 16, left: 64, right: 24, bottom: 28 },
    xAxis: { type: "value", min: -0.1, max: 0.1, ...ax, axisLabel: { ...ax.axisLabel, formatter: (v: number) => pct(v, { digits: 0, signed: true }) } },
    yAxis: { type: "value", min: -yMax, max: yMax, position: "left", ...ax, axisLabel: { ...ax.axisLabel, formatter: (v: number) => pct(v, { digits: 1, signed: true }) } },
    series: [
      {
        type: "scatter",
        data: pts.map((p) => ({
          value: [p.x, p.y],
          fund: p.f,
          symbolSize: 7 + 22 * Math.sqrt((p.f.aum ?? 0) / maxAum),
          label: labelled.has(p.f.ins_code)
            ? { show: true, formatter: p.f.symbol, position: "top", color: t.ink2, fontFamily: t.font, fontSize: 11 }
            : undefined,
        })),
        itemStyle: { color: t.type.equity, opacity: 0.65, borderColor: t.surface, borderWidth: 1 },
        markLine: {
          silent: true,
          symbol: "none",
          label: { show: false },
          lineStyle: { color: t.axis, type: "solid", width: 1 },
          data: [{ xAxis: 0 }, { yAxis: 0 }],
        },
      },
      {
        type: "scatter",
        silent: true,
        symbolSize: 0,
        data: [
          quadrant(0.095, yMax * 0.92, "ورود پول با حباب · هیجان", "right"),
          quadrant(-0.095, yMax * 0.92, "ورود پول با تخفیف · فرصت‌یابی", "left"),
          quadrant(-0.095, -yMax * 0.92, "خروج پول با تخفیف · ترس", "left"),
          quadrant(0.095, -yMax * 0.92, "خروج پول با حباب · سودگیری", "right"),
        ],
      },
    ],
  };
}

// ---------------------------------------------------------------------------
// 5b. Risk / return — "For the ride this fund gave you, did it pay enough?"
//     x = annualised volatility (always ≥ 0), y = price return over the same
//     window, size = net assets, colour = fund type. Top-left is the quadrant
//     every allocator wants: low bumps, real return.
// ---------------------------------------------------------------------------
export function riskReturnOption(funds: FundRisk[], t: Tokens): ChartOption {
  const ax = axisStyle(t);
  const pts = funds.filter((f) => f.volatility != null && f.period_return != null);
  const xMax = Math.max(0.05, ...pts.map((p) => p.volatility as number)) * 1.08;
  const yAbs = Math.max(0.02, ...pts.map((p) => Math.abs(p.period_return as number))) * 1.15;
  const maxAum = Math.max(1, ...pts.map((p) => p.aum ?? 0));
  const labelled = new Set(
    [...pts].sort((a, b) => (b.aum ?? 0) - (a.aum ?? 0)).slice(0, 6).map((p) => p.ins_code),
  );
  const quadrant = (x: number, y: number, text: string, align: "left" | "right") => ({
    value: [x, y],
    label: { show: true, formatter: text, color: t.muted, fontFamily: t.font, fontSize: 11.5, align },
  });
  return {
    ...base(t),
    tooltip: {
      ...base(t).tooltip,
      formatter: (p: { data: { f?: FundRisk } }) => {
        const f = p.data.f;
        if (!f) return "";
        return tipRows(`${f.symbol} · ${TYPE_FA[f.fund_type as EquityType] ?? ""}`, [
          ["بازده دوره", pct(f.period_return, { signed: true })],
          ["نوسان سالانه‌شده", pct(f.volatility, { digits: 1 })],
          ["خالص دارایی", money(f.aum)],
        ]);
      },
    },
    grid: { top: 16, left: 64, right: 24, bottom: 32 },
    xAxis: {
      type: "value",
      min: 0,
      max: xMax,
      ...ax,
      axisLabel: { ...ax.axisLabel, formatter: (v: number) => pct(v, { digits: 0 }) },
    },
    yAxis: {
      type: "value",
      min: -yAbs,
      max: yAbs,
      position: "left",
      ...ax,
      axisLabel: { ...ax.axisLabel, formatter: (v: number) => pct(v, { digits: 0, signed: true }) },
    },
    series: [
      {
        type: "scatter",
        data: pts.map((f) => ({
          value: [f.volatility, f.period_return],
          f,
          symbolSize: 7 + 22 * Math.sqrt((f.aum ?? 0) / maxAum),
          itemStyle: { color: t.type[f.fund_type as EquityType], opacity: 0.75, borderColor: t.surface, borderWidth: 1 },
          label: labelled.has(f.ins_code)
            ? { show: true, formatter: f.symbol, position: "top", color: t.ink2, fontFamily: t.font, fontSize: 11 }
            : undefined,
        })),
        markLine: {
          silent: true,
          symbol: "none",
          label: { show: false },
          lineStyle: { color: t.axis, type: "solid", width: 1 },
          data: [{ yAxis: 0 }],
        },
      },
      {
        type: "scatter",
        silent: true,
        symbolSize: 0,
        data: [
          quadrant(xMax * 0.04, yAbs * 0.92, "نوسان کم، بازده مثبت", "left"),
          quadrant(xMax * 0.98, yAbs * 0.92, "نوسان زیاد، بازده مثبت", "right"),
          quadrant(xMax * 0.98, -yAbs * 0.92, "نوسان زیاد، بازده منفی", "right"),
        ],
      },
    ],
  };
}

// ---------------------------------------------------------------------------
// 6. Returns heatmap — "Who led and who lagged, over which horizon?"
//    colour is scaled per column (1W and YTD live on different scales)
// ---------------------------------------------------------------------------
const HORIZONS = [
  ["r_1d", "۱ روز"],
  ["r_1w", "۱ هفته"],
  ["r_1m", "۱ ماه"],
  ["r_3m", "۳ ماه"],
  ["r_ytd", "از ابتدای سال"],
] as const;

export function returnsOption(rows: FundReturns[], t: Tokens): ChartOption {
  const limits = HORIZONS.map(([k]) => {
    const abs = rows.map((r) => Math.abs(r[k] ?? 0)).sort((a, b) => a - b);
    return Math.max(0.005, abs[Math.floor(abs.length * 0.9)] ?? 0.01);
  });
  const data = rows.flatMap((r, y) =>
    HORIZONS.map(([k], x) => {
      const v = r[k];
      const fill = diverging(t, v, limits[x] ?? 0.1);
      return {
        value: [x, y, v],
        itemStyle: { color: fill, borderColor: t.surface, borderWidth: 2 },
        label: { color: inkOn(fill) },
      };
    }),
  );
  return {
    ...base(t),
    tooltip: {
      ...base(t).tooltip,
      formatter: (p: { value: [number, number, number | null] }) => {
        const r = rows[p.value[1]];
        const h = HORIZONS[p.value[0]];
        return r && h ? tipRows(r.symbol, [[h[1], pct(p.value[2], { signed: true })]]) : "";
      },
    },
    grid: { top: 28, left: 88, right: 8, bottom: 8 },
    xAxis: {
      type: "category",
      position: "top",
      data: HORIZONS.map(([, fa]) => fa),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: t.ink2, fontFamily: t.font, fontSize: 12 },
    },
    yAxis: {
      type: "category",
      position: "left",
      inverse: true, // largest fund on top
      data: rows.map((r) => r.symbol),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: t.ink2, fontFamily: t.font, fontSize: 12 },
    },
    series: [
      {
        type: "heatmap",
        data,
        label: {
          show: true,
          fontFamily: t.font,
          fontSize: 11,
          formatter: (p: { value: [number, number, number | null] }) => pct(p.value[2], { digits: 1 }),
        },
      },
    ],
  };
}

// ---------------------------------------------------------------------------
// 7. Market premium over time — "Is the market getting more expensive or cheaper?"
//    two lines on one % axis: the median fund, and net-assets-weighted (dashed)
// ---------------------------------------------------------------------------
export function premiumTrendOption(input: PremiumPoint[], t: Tokens, intraday: boolean): ChartOption {
  const points = chronological(input, (p) => p.at);
  const ax = axisStyle(t);
  const x = points.map((p) => (intraday ? time(p.at) : faDate(p.at_fa).slice(5)));
  const [c1, c2] = t.series;
  const line = (name: string, key: "median" | "weighted", color: string, dashed: boolean) => ({
    name,
    type: "line",
    data: points.map((p) => p[key]),
    showSymbol: points.length < 12,
    symbolSize: 7,
    lineStyle: { width: 2, color, type: dashed ? "dashed" : "solid" },
    itemStyle: { color },
    connectNulls: true,
    endLabel: { show: true, formatter: name, color: t.ink2, fontFamily: t.font },
  });
  return {
    ...base(t),
    tooltip: {
      ...base(t).tooltip,
      trigger: "axis",
      formatter: (ps: { dataIndex: number }[]) => {
        const p = points[ps[0]?.dataIndex ?? 0];
        return p
          ? tipRows(intraday ? time(p.at) : faDate(p.at_fa), [
              ["میانه", pct(p.median, { signed: true, digits: 2 })],
              ["وزنی (خالص دارایی)", pct(p.weighted, { signed: true, digits: 2 })],
              ["تعداد صندوق", num(p.funds)],
            ])
          : "";
      },
    },
    grid: { top: 16, left: 56, right: 72, bottom: 28 },
    xAxis: { type: "category", data: x, boundaryGap: false, ...ax, axisLabel: { ...ax.axisLabel, hideOverlap: true } },
    yAxis: {
      type: "value",
      position: "left",
      ...ax,
      axisLabel: { ...ax.axisLabel, formatter: (v: number) => pct(v, { digits: 1, signed: true }) },
    },
    series: [
      {
        ...line("میانه", "median", c1, false),
        markLine: { silent: true, symbol: "none", label: { show: false }, lineStyle: { color: t.axis, type: "solid" }, data: [{ yAxis: 0 }] },
      },
      line("وزنی", "weighted", c2, true),
    ],
  };
}


// ---------------------------------------------------------------------------
// Fund detail: intraday price vs NAV (same unit, one axis) and 120-day history
// ---------------------------------------------------------------------------
export function fundIntradayOption(input: FundIntradayPoint[], t: Tokens): ChartOption {
  const points = chronological(input, (p) => p.ts);
  const ax = axisStyle(t);
  const x = points.map((p) => time(p.ts));
  const firstLive = points.some((p) => p.backfilled) ? points.findIndex((p) => !p.backfilled) : -1;
  const line = (name: string, data: (number | null)[], color: string) => ({
    name,
    type: "line",
    data: data.map((v) => (v ? v / 10 : null)),
    showSymbol: data.filter((v) => v != null).length < 3, // a lone point needs a dot to be seen
    symbolSize: 8,
    lineStyle: { width: 2, color },
    itemStyle: { color },
    connectNulls: true,
    endLabel: { show: true, formatter: name, color: t.ink2, fontFamily: t.font },
  });
  return {
    ...base(t),
    tooltip: {
      ...base(t).tooltip,
      trigger: "axis",
      formatter: (ps: { dataIndex: number }[]) => {
        const p = points[ps[0]?.dataIndex ?? 0];
        if (!p) return "";
        if (p.backfilled) {
          return tipRows(`${time(p.ts)} · بازسازی از ریز معاملات`, [
            ["آخرین قیمت", `${price(p.last_price)} ت`],
            ["NAV و ورود پول", "در ریز معاملات نیست"],
          ]);
        }
        return tipRows(time(p.ts), [
          ["آخرین قیمت", `${price(p.last_price)} ت`],
          ["NAV ابطال", `${price(p.nav)} ت`],
          ["حباب", p.premium == null ? "—" : pct(p.premium, { signed: true })],
          ["ورود پول حقیقی", p.ind_net_flow == null ? "—" : money(p.ind_net_flow, { signed: true })],
        ]);
      },
    },
    grid: { top: 16, left: 64, right: 56, bottom: 28 },
    xAxis: { type: "category", data: x, boundaryGap: false, ...ax },
    yAxis: { type: "value", scale: true, position: "left", ...ax, axisLabel: { ...ax.axisLabel, formatter: (v: number) => num(v) } },
    series: [
      line("قیمت", points.map((p) => (p.backfilled ? null : p.last_price)), t.type.equity),
      line("NAV", points.map((p) => p.nav), t.deemph),
      ...(firstLive > 0
        ? [
            {
              // Minutes before the collector started, rebuilt from trades (ADR 0012):
              // same colour, dashed, and joined to the first live point.
              ...line("", points.map((p, i) => (p.backfilled || i === firstLive ? p.last_price : null)), t.type.equity),
              name: "قیمت (بازسازی)",
              lineStyle: { width: 1.5, color: t.type.equity, type: "dashed" },
              endLabel: { show: false },
            },
          ]
        : []),
    ],
  };
}

export function fundHistoryOption(input: DailyBar[], t: Tokens): ChartOption {
  const bars = chronological(input, (b) => b.trade_date);
  const ax = axisStyle(t);
  const x = bars.map((b) => faDate(b.trade_date_fa).slice(2));
  return {
    ...base(t),
    tooltip: {
      ...base(t).tooltip,
      trigger: "axis",
      formatter: (ps: { dataIndex: number }[]) => {
        const b = bars[ps[0]?.dataIndex ?? 0];
        return b
          ? tipRows(faDate(b.trade_date_fa), [
              ["قیمت پایانی", `${price(b.close_price)} ت`],
              ["ارزش معاملات", money(b.value)],
              ["ورود پول حقیقی", money(b.ind_net_flow, { signed: true })],
            ])
          : "";
      },
    },
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    grid: [
      { top: 12, left: 64, right: 16, height: "52%" },
      { bottom: 28, left: 64, right: 16, height: "26%" },
    ],
    xAxis: [
      { type: "category", data: x, gridIndex: 0, ...ax, axisLabel: { show: false } },
      { type: "category", data: x, gridIndex: 1, ...ax, axisLabel: { ...ax.axisLabel, hideOverlap: true } },
    ],
    yAxis: [
      { type: "value", gridIndex: 0, scale: true, position: "left", ...ax, axisLabel: { ...ax.axisLabel, formatter: (v: number) => num(v / 10) } },
      { type: "value", gridIndex: 1, position: "left", ...ax, splitNumber: 2, axisLabel: { ...ax.axisLabel, formatter: axisMilliard } },
    ],
    series: [
      { name: "قیمت پایانی", type: "line", data: bars.map((b) => b.close_price), xAxisIndex: 0, yAxisIndex: 0, showSymbol: false, lineStyle: { width: 2, color: t.type.equity }, itemStyle: { color: t.type.equity } },
      {
        name: "ورود پول حقیقی",
        type: "bar",
        xAxisIndex: 1,
        yAxisIndex: 1,
        barMaxWidth: 8,
        data: bars.map((b) => ({ value: b.ind_net_flow, itemStyle: { color: b.ind_net_flow >= 0 ? t.divPos : t.divNeg } })),
      },
    ],
  };
}
