import { useMemo, useState } from "react";

import type { FundSnapshot } from "../api/types";
import { isEquityType } from "../charts/theme";
import { useTokens } from "../charts/tokens";
import { flagFa, flagKind } from "../lib/flags";
import { money, num, pct, price, signClass } from "../lib/format";
import { StatusBadge } from "./StatusBadge";

type Key = "symbol" | "aum" | "change" | "premium" | "ind_net_flow" | "value" | "buyer_power" | "turnover";

const COLUMNS: { key: Key; label: string; num: boolean; render: (f: FundSnapshot) => string }[] = [
  { key: "aum", label: "خالص دارایی", num: true, render: (f) => money(f.aum) },
  { key: "change", label: "تغییر", num: true, render: (f) => pct(f.change, { signed: true, digits: 2 }) },
  { key: "premium", label: "حباب", num: true, render: (f) => (f.premium == null ? "—" : pct(f.premium, { signed: true })) },
  { key: "ind_net_flow", label: "پول حقیقی", num: true, render: (f) => money(f.ind_net_flow, { signed: true }) },
  { key: "value", label: "ارزش معاملات", num: true, render: (f) => money(f.value) },
  { key: "buyer_power", label: "قدرت خریدار", num: true, render: (f) => (f.buyer_power == null ? "—" : f.buyer_power.toLocaleString("fa-IR", { maximumFractionDigits: 2 })) },
  { key: "turnover", label: "گردش", num: true, render: (f) => pct(f.turnover, { digits: 2 }) },
];

const SIGNED: ReadonlySet<Key> = new Set(["change", "premium", "ind_net_flow"]);

/** The table view behind every chart: sortable, searchable, click → fund page. */
export function FundsTable({ funds, onOpen }: { funds: FundSnapshot[]; onOpen: (ins: string) => void }) {
  const t = useTokens();
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<{ key: Key; desc: boolean }>({ key: "aum", desc: true });

  const rows = useMemo(() => {
    const needle = q.trim();
    const list = needle ? funds.filter((f) => f.symbol.includes(needle) || f.name.includes(needle)) : funds;
    const val = (f: FundSnapshot) => (sort.key === "symbol" ? f.symbol : f[sort.key]);
    return [...list].sort((a, b) => {
      const x = val(a);
      const y = val(b);
      if (x == null) return 1; // nulls last in both directions
      if (y == null) return -1;
      const c = typeof x === "string" ? x.localeCompare(String(y), "fa") : x - (y as number);
      return sort.desc ? -c : c;
    });
  }, [funds, q, sort]);

  const th = (key: Key, label: string, num: boolean) => (
    <th
      key={key}
      className={num ? "num" : undefined}
      aria-sort={sort.key === key ? (sort.desc ? "descending" : "ascending") : "none"}
    >
      <button type="button" onClick={() => setSort((s) => ({ key, desc: s.key === key ? !s.desc : key !== "symbol" }))}>
        {label}
        {sort.key === key ? (sort.desc ? " ▼" : " ▲") : ""}
      </button>
    </th>
  );

  return (
    <>
      <input
        className="search"
        type="search"
        placeholder="جستجوی نماد یا نام صندوق…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        aria-label="جستجوی صندوق"
      />
      <div className="table-wrap">
        <table className="funds">
          <thead>
            <tr>
              {th("symbol", "نماد", false)}
              <th>نوع</th>
              <th className="num">قیمت (ت)</th>
              {COLUMNS.map((c) => th(c.key, c.label, c.num))}
              <th>کیفیت</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((f) => (
              <tr key={f.ins_code} onClick={() => onOpen(f.ins_code)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && onOpen(f.ins_code)}>
                <td title={f.name}>
                  <b>{f.symbol}</b>
                  <StatusBadge f={f} />
                </td>
                <td>
                  <span className="type-dot" style={{ background: isEquityType(f.fund_type) ? t.type[f.fund_type] : t.deemph }} />
                  {f.fund_type_fa}
                </td>
                <td className="num">{price(f.last_price)}</td>
                {COLUMNS.map((c) => (
                  <td
                    key={c.key}
                    className={`num ${SIGNED.has(c.key) ? signClass(f[c.key] as number | null) : ""} ${f[c.key] == null ? "na" : ""}`}
                  >
                    {c.render(f)}
                  </td>
                ))}
                <td>
                  {f.quality_flags.length > 0 && (
                    <span
                      className={`flag ${f.quality_flags.some((q) => flagKind(q) === "warn") ? "warn" : ""}`}
                      title={f.quality_flags.map(flagFa).join("، ")}
                    >
                      {num(f.quality_flags.length)} پرچم
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <div className="empty">صندوقی با این عبارت پیدا نشد.</div>}
      </div>
    </>
  );
}
