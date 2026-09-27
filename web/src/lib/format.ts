// Persian number formatting for the panel.
//
// Money arrives in Rial. Iranian market readers think in Toman and in
// "همت" (هزار میلیارد تومان = 10^13 Rial) for fund-size figures, so the
// panel converts at the edge and always says which unit it shows.

const faDigits = new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 0 });
const fa1 = new Intl.NumberFormat("fa-IR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export const RIAL_PER_TOMAN = 10;
export const RIAL_PER_HEMAT = 1e13; // هزار میلیارد تومان
export const RIAL_PER_MILLIARD_TOMAN = 1e10; // میلیارد تومان

/**
 * Wrap a signed figure in a left-to-right isolate (LRI…PDI) so "+۱٫۲٪" keeps its
 * sign on the left inside RTL text, in HTML and in the charts' SVG alike.
 */
export const ltr = (s: string) => `\u2066${s}\u2069`;

export function num(n: number | null | undefined, digits = 0): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return digits === 0
    ? faDigits.format(n)
    : new Intl.NumberFormat("fa-IR", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      }).format(n);
}

/** 0.0123 → "۱٫۲٪" ; signed adds "+" for positive values. */
export function pct(ratio: number | null | undefined, opts: { signed?: boolean; digits?: number } = {}): string {
  if (ratio == null || !Number.isFinite(ratio)) return "—";
  const { signed = false, digits = 1 } = opts;
  const v = ratio * 100;
  const body = new Intl.NumberFormat("fa-IR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(Math.abs(v));
  const sign = v < 0 ? "−" : signed && v > 0 ? "+" : "";
  return sign ? ltr(`${sign}${body}٪`) : `${body}٪`;
}

/** Rial → a compact Toman figure with its unit: همت / میلیارد / میلیون تومان. */
export function money(rial: number | null | undefined, opts: { signed?: boolean } = {}): string {
  if (rial == null || !Number.isFinite(rial)) return "—";
  const abs = Math.abs(rial);
  const sign = rial < 0 ? "−" : opts.signed && rial > 0 ? "+" : "";
  const n = (x: string) => (sign ? ltr(sign + x) : x);
  if (abs >= RIAL_PER_HEMAT) return `${n(fa1.format(abs / RIAL_PER_HEMAT))} همت`;
  if (abs >= RIAL_PER_MILLIARD_TOMAN)
    return `${n(faDigits.format(abs / RIAL_PER_MILLIARD_TOMAN))} میلیارد ت`;
  if (abs >= 1e7) return `${n(faDigits.format(abs / 1e7))} میلیون ت`;
  return `${n(faDigits.format(abs / RIAL_PER_TOMAN))} ت`;
}

/** Rial → Toman with thousands separators (prices). */
export function price(rial: number | null | undefined): string {
  if (rial == null || !Number.isFinite(rial) || rial === 0) return "—";
  return faDigits.format(Math.round(rial / RIAL_PER_TOMAN));
}

/** Axis ticks: Rial → billion Toman, short. */
export function axisMilliard(rial: number): string {
  return faDigits.format(Math.round(rial / RIAL_PER_MILLIARD_TOMAN));
}

export function time(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("fa-IR", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Tehran",
  });
}

/** "1405/07/02" → "۱۴۰۵/۰۷/۰۲" */
export function faDate(jalali: string): string {
  return jalali.replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[Number(d)] ?? d);
}

export function signClass(v: number | null | undefined): string {
  if (v == null || v === 0) return "";
  return v > 0 ? "pos" : "neg";
}
