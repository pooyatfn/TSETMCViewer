import { describe, expect, it } from "vitest";

import { faDate, ltr, money, num, pct, price } from "./format";

describe("format", () => {
  it("uses Persian digits and separators", () => {
    expect(num(1234567)).toBe("۱٬۲۳۴٬۵۶۷");
    expect(num(null)).toBe("—");
  });

  it("formats percentages with a real minus sign", () => {
    expect(pct(0.0123)).toBe("۱٫۲٪");
    expect(pct(-0.186)).toBe(ltr("−۱۸٫۶٪"));
    expect(pct(0.05, { signed: true })).toBe(ltr("+۵٫۰٪"));
    expect(pct(null)).toBe("—");
  });

  it("converts Rial to the right Toman unit", () => {
    expect(money(3_752_367_895_747_336)).toBe("۳۷۵٫۲ همت");
    expect(money(5_738_135_670_836, { signed: true })).toBe(`${ltr("+۵۷۴")} میلیارد ت`);
    expect(money(-2_500_000_000)).toBe(`${ltr("−۲۵۰")} میلیون ت`);
  });

  it("isolates signed figures so the sign stays on the left in RTL", () => {
    expect(pct(0.01, { signed: true }).startsWith("\u2066")).toBe(true);
    expect(pct(0.01).includes("\u2066")).toBe(false); // unsigned needs no isolate
  });

  it("shows prices in Toman", () => {
    expect(price(157_615)).toBe("۱۵٬۷۶۲");
    expect(price(0)).toBe("—");
  });

  it("converts Jalali date digits", () => {
    expect(faDate("1405/07/02")).toBe("۱۴۰۵/۰۷/۰۲");
  });
});
