import { api } from "../api/client";
import { ACTION_FA, CHECK_FA, FLAGS, KIND_FA, flagFa, flagKind } from "../lib/flags";
import { num, pct } from "../lib/format";
import { useQuery } from "../lib/hooks";
import { Card, Empty } from "./Card";

const STATUS_FA: Record<string, string> = { ok: "موفق", partial: "ناقص", failed: "ناموفق" };

/** Requirement 3 made visible: what the validator saw and repaired in today's session. */
export function QualityCard({ tick, date }: { tick: number; date?: string }) {
  const q = useQuery((s) => api.quality(date, s), [tick, date]);
  const r = q.data;
  const flags = r ? Object.entries(r.flag_counts).sort((a, b) => b[1] - a[1]) : [];
  return (
    <Card
      compact
      title="کیفیت داده‌ی امروز"
      question="چقدر می‌توان به اعداد این صفحه اعتماد کرد؟ اعتبارسنج بعد از هر دریافت چه دید و چه اصلاح کرد؟"
      stale={q.refreshing}
      note="درصد هر پرچم نسبت به کل ردیف‌های دقیقه‌ای امروز است. «اطلاع» عادی است؛ «اصلاح‌شده» یعنی پیش‌پردازش مقدار را ترمیم کرده است."
    >
      {!r ? (
        <Empty>{q.error ? q.error.message : "در حال بارگذاری…"}</Empty>
      ) : (
        <>
          <div className="kv" style={{ marginBottom: 14 }}>
            <div>
              کامل بودن
              <b>{pct(r.completeness)}</b>
            </div>
            <div>
              ردیف دقیقه‌ای
              <b>{num(r.ticks)}</b>
            </div>
            {Object.entries(r.runs_by_status).map(([k, v]) => (
              <div key={k}>
                چرخه‌ی {STATUS_FA[k] ?? k}
                <b>{num(v)}</b>
              </div>
            ))}
          </div>
          {flags.length === 0 ? (
            <Empty>هیچ پرچمی ثبت نشده است.</Empty>
          ) : (
            <ul className="bars">
              {flags.map(([name, count]) => {
                const share = r.ticks ? count / r.ticks : 0;
                const kind = flagKind(name);
                return (
                  <li key={name} title={FLAGS[name]?.hint}>
                    <span className="bar-label">
                      {flagFa(name)} <span className={`flag ${kind}`}>{KIND_FA[kind]}</span>
                    </span>
                    <span className="bar-track">
                      <span className={`bar-fill ${kind}`} style={{ width: `${Math.max(1, share * 100)}%` }} />
                    </span>
                    <span className="bar-value">{pct(share, { digits: 0 })}</span>
                  </li>
                );
              })}
            </ul>
          )}
          {r.issues.length > 0 && (
            <table className="funds" style={{ marginTop: 16 }}>
              <thead>
                <tr>
                  <th>رخداد اعتبارسنجی</th>
                  <th>اقدام پیش‌پردازش</th>
                  <th className="num">تعداد</th>
                </tr>
              </thead>
              <tbody>
                {r.issues.slice(0, 8).map(([check, , action, n]) => (
                  <tr key={`${check}-${action}`} style={{ cursor: "default" }}>
                    <td>{CHECK_FA[check] ?? check}</td>
                    <td>{ACTION_FA[action] ?? action}</td>
                    <td className="num">{num(n)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </Card>
  );
}
