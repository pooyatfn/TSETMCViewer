import type { Overview } from "../api/types";
import { useTokens } from "../charts/tokens";
import { money, num, pct } from "../lib/format";

function Tile({ label, value, unit, delta }: { label: string; value: string; unit?: string; delta?: { text: string; dir: "up" | "down" | "" } }) {
  return (
    <div className="card tile">
      <div className="label">{label}</div>
      <div className="value">
        {value}
        {unit && <small>{unit}</small>}
      </div>
      {delta && <div className={`delta ${delta.dir}`}>{delta.text}</div>}
    </div>
  );
}

/** Split a money string ("۳۷۵٫۲ همت") into value + unit so the unit can be set smaller. */
function splitUnit(s: string): [string, string | undefined] {
  const i = s.indexOf(" ");
  return i < 0 ? [s, undefined] : [s.slice(0, i), s.slice(i + 1)];
}

const dir = (v: number | null | undefined) => (v == null || v === 0 ? "" : v > 0 ? "up" : "down");

/** The headline row: size, direction of money, valuation, breadth, activity, trust. */
export function KpiTiles({ o }: { o: Overview }) {
  const t = useTokens();
  const [aum, aumUnit] = splitUnit(money(o.total_aum));
  const [flow, flowUnit] = splitUnit(money(o.ind_net_flow, { signed: true }));
  const [val, valUnit] = splitUnit(money(o.total_value));
  const breadthTotal = Math.max(1, o.advancers + o.decliners + o.unchanged);
  return (
    <div className="grid kpis">
      <Tile label="خالص دارایی کل" value={aum} unit={aumUnit} delta={{ text: `${num(o.funds)} صندوق`, dir: "" }} />
      <Tile
        label="ورود پول حقیقی امروز"
        value={flow}
        unit={flowUnit}
        delta={{ text: o.ind_net_flow >= 0 ? "▲ ورود" : "▼ خروج", dir: dir(o.ind_net_flow) }}
      />
      <Tile
        label="میانه‌ی حباب (بدون اهرمی)"
        value={pct(o.median_premium, { signed: true })}
        delta={{
          text: `وزنی ${pct(o.weighted_premium, { signed: true })} · ${num(o.at_premium)} با حباب · ${num(o.at_discount)} با تخفیف`,
          dir: "",
        }}
      />
      <div className="card tile">
        <div className="label">پهنای بازار</div>
        <div className="value">
          {num(o.advancers)}
          <small>مثبت از {num(breadthTotal)}</small>
        </div>
        <div className="breadth" role="img" aria-label={`${num(o.advancers)} مثبت، ${num(o.unchanged)} بی‌تغییر، ${num(o.decliners)} منفی`}>
          <span style={{ flex: o.advancers, background: t.divPos }} />
          <span style={{ flex: o.unchanged, background: t.deemph }} />
          <span style={{ flex: o.decliners, background: t.divNeg }} />
        </div>
      </div>
      <Tile label="ارزش معاملات" value={val} unit={valUnit} />
      <Tile
        label="شاخص کل"
        value={num(o.index_value)}
        delta={{ text: pct(o.index_change, { signed: true, digits: 2 }), dir: dir(o.index_change) }}
      />
      <Tile
        label="کامل بودن داده‌ی امروز"
        value={pct(o.completeness, { digits: 1 })}
        delta={{ text: "دقیقه‌های دریافت‌شده از کل جلسه", dir: "" }}
      />
    </div>
  );
}
