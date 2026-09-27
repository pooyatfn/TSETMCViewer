import type { FundType } from "../api/types";

/** Resolved design tokens for ECharts (which cannot read CSS variables itself). */
export interface Tokens {
  surface: string;
  surface2: string;
  ink: string;
  ink2: string;
  muted: string;
  grid: string;
  axis: string;
  deemph: string;
  divPos: string;
  divNeg: string;
  divMid: string;
  good: string;
  bad: string;
  font: string;
  type: Record<"equity" | "sector" | "index" | "leveraged", string>;
  /** Generic categorical slots 1–2 (same validated hues) for charts without fund types. */
  series: [string, string];
}

export function readTokens(): Tokens {
  const cs = getComputedStyle(document.documentElement);
  const v = (name: string) => cs.getPropertyValue(name).trim();
  return {
    surface: v("--surface"),
    surface2: v("--surface-2"),
    ink: v("--ink"),
    ink2: v("--ink-2"),
    muted: v("--muted"),
    grid: v("--grid"),
    axis: v("--axis"),
    deemph: v("--deemph"),
    divPos: v("--div-pos"),
    divNeg: v("--div-neg"),
    divMid: v("--div-mid"),
    good: v("--good"),
    bad: v("--bad"),
    font: v("--font"),
    type: {
      equity: v("--s-equity"),
      sector: v("--s-sector"),
      index: v("--s-index"),
      leveraged: v("--s-leveraged"),
    },
    series: [v("--s-equity"), v("--s-sector")],
  };
}

/** Fixed order and labels of the equity family — colour follows the type, never its rank. */
export const TYPE_ORDER = ["equity", "sector", "index", "leveraged"] as const;
export type EquityType = (typeof TYPE_ORDER)[number];
export const TYPE_FA: Record<EquityType, string> = {
  equity: "سهامی",
  sector: "بخشی",
  index: "شاخصی",
  leveraged: "اهرمی",
};

export function isEquityType(t: FundType): t is EquityType {
  return (TYPE_ORDER as readonly string[]).includes(t);
}

/** Shared chrome: recessive hairline axes, Persian font, tooltip on the surface. */
export function base(t: Tokens) {
  return {
    backgroundColor: "transparent",
    textStyle: { fontFamily: t.font, color: t.ink2, fontSize: 12 },
    animationDuration: 300,
    tooltip: {
      backgroundColor: t.surface,
      borderColor: t.grid,
      textStyle: { color: t.ink, fontFamily: t.font, fontSize: 12 },
      extraCssText: "direction: rtl; text-align: right; box-shadow: 0 4px 16px rgba(0,0,0,.12); border-radius: 10px;",
    },
  };
}

export function axisStyle(t: Tokens) {
  return {
    axisLine: { lineStyle: { color: t.axis } },
    axisTick: { show: false },
    axisLabel: { color: t.muted, fontFamily: t.font, fontSize: 11 },
    splitLine: { lineStyle: { color: t.grid, width: 1, type: "solid" as const } },
  };
}

/** Diverging colour for a signed value, symmetric around zero, clipped at ±limit. */
export function diverging(t: Tokens, value: number | null, limit: number): string {
  if (value == null || !Number.isFinite(value)) return t.divMid;
  const k = Math.max(-1, Math.min(1, value / limit));
  return mix(t.divMid, k >= 0 ? t.divPos : t.divNeg, Math.abs(k));
}

function hex(c: string): [number, number, number] {
  const h = c.replace("#", "");
  const n = parseInt(h.length === 3 ? h.replace(/./g, (x) => x + x) : h, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function mix(a: string, b: string, k: number): string {
  const [r1, g1, b1] = hex(a);
  const [r2, g2, b2] = hex(b);
  const m = (x: number, y: number) => Math.round(x + (y - x) * k);
  return `rgb(${m(r1, r2)}, ${m(g1, g2)}, ${m(b1, b2)})`;
}

/** Relative luminance → pick ink or white for text drawn inside a filled cell. */
export function inkOn(fill: string): string {
  const rgb = fill.startsWith("rgb")
    ? (fill.match(/\d+/g) ?? ["0", "0", "0"]).map(Number)
    : hex(fill);
  const [r, g, b] = rgb.map((x) => {
    const s = (x ?? 0) / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  }) as [number, number, number];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.4 ? "#0b0b0b" : "#ffffff";
}
