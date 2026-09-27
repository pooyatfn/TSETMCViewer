import type { ReactNode } from "react";

interface Props {
  title: string;
  question: string;
  wide?: boolean;
  stale?: boolean;
  actions?: ReactNode;
  note?: ReactNode;
  /** Do not stretch to the row height (content shorter than its neighbour). */
  compact?: boolean;
  children: ReactNode;
}

/** Every chart sits in a card whose subtitle is the question it answers. */
export function Card({ title, question, wide, stale, actions, note, compact, children }: Props) {
  return (
    <section className={`card${wide ? " wide" : ""}`} style={compact ? { alignSelf: "start" } : undefined}>
      <div className="card-head">
        <h2>{title}</h2>
        <span className="spacer" />
        {actions}
      </div>
      <p className="q">{question}</p>
      <div className={stale ? "stale" : undefined}>{children}</div>
      {note && <div className="note">{note}</div>}
    </section>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

/** Page-level section switcher (distinct from `Seg`, which toggles one card's view). */
export function Tabs<T extends string>({
  options,
  value,
  onChange,
}: {
  options: readonly (readonly [T, string])[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="tabs" role="tablist" aria-label="بخش‌های پنل">
      {options.map(([v, text]) => (
        <button
          key={v}
          type="button"
          role="tab"
          aria-selected={v === value}
          onClick={() => onChange(v)}
        >
          {text}
        </button>
      ))}
    </div>
  );
}

export function Seg<T extends string | number>({
  options,
  value,
  onChange,
  label,
}: {
  options: readonly (readonly [T, string])[];
  value: T;
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map(([v, text]) => (
        <button key={String(v)} type="button" aria-pressed={v === value} onClick={() => onChange(v)}>
          {text}
        </button>
      ))}
    </div>
  );
}
