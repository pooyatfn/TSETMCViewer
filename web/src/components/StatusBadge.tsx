import type { FundSnapshot } from "../api/types";
import { time } from "../lib/format";

/** TSETMC's own title («مجاز-متوقف», «ممنوع» …), shown only when the fund is not trading normally. */
export function StatusBadge({ f }: { f: Pick<FundSnapshot, "status_kind" | "status_title" | "status_at" | "under_supervision"> }) {
  const halted = f.status_kind !== "open" && f.status_kind !== "unknown";
  const checked = f.status_at ? ` · بررسی ${time(f.status_at)}` : "";
  return (
    <>
      {halted && (
        <span className={`status ${f.status_kind}`} title={`وضعیت نماد در TSETMC${checked}`}>
          {f.status_title ?? "متوقف"}
        </span>
      )}
      {f.under_supervision && (
        <span className="status watch" title={`نماد زیر نظر ناظر بازار است${checked}`}>
          تحت نظر
        </span>
      )}
    </>
  );
}

export const isHalted = (f: Pick<FundSnapshot, "status_kind">) =>
  f.status_kind !== "open" && f.status_kind !== "unknown";
