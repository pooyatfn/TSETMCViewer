import { TYPE_FA, TYPE_ORDER, type EquityType } from "../charts/theme";
import { useTokens } from "../charts/tokens";

/** HTML legend for the four equity-fund types (text in ink, the swatch carries identity). */
export function TypeLegend({ only }: { only?: readonly EquityType[] }) {
  const t = useTokens();
  return (
    <div className="legend">
      {TYPE_ORDER.filter((k) => !only || only.includes(k)).map((k) => (
        <span key={k}>
          <i style={{ background: t.type[k] }} />
          {TYPE_FA[k]}
        </span>
      ))}
    </div>
  );
}

/** Legend for diverging scales: negative ← neutral → positive. */
export function DivergingLegend({ neg, pos }: { neg: string; pos: string }) {
  const t = useTokens();
  return (
    <div className="legend">
      <span>
        <i style={{ background: t.divNeg }} />
        {neg}
      </span>
      <span>
        <i style={{ background: t.divMid, outline: `1px solid ${t.axis}` }} />
        بی‌تغییر
      </span>
      <span>
        <i style={{ background: t.divPos }} />
        {pos}
      </span>
    </div>
  );
}
