import { useMemo, useState } from "react";

import { api } from "../api/client";
import { Chart } from "../charts/Chart";
import { fundHistoryOption, fundIntradayOption } from "../charts/options";
import { useTokens } from "../charts/tokens";
import { Card, Empty, Seg } from "../components/Card";
import { StatusBadge } from "../components/StatusBadge";
import { FLAGS, flagFa, flagKind } from "../lib/flags";
import { faDate, money, num, pct, price, signClass, time } from "../lib/format";
import { useQuery } from "../lib/hooks";

const HORIZONS = [
  ["r_1d", "۱ روز"],
  ["r_1w", "۱ هفته"],
  ["r_1m", "۱ ماه"],
  ["r_3m", "۳ ماه"],
  ["r_ytd", "از ابتدای سال"],
] as const;

/** History windows in calendar days; ALL is the API's upper bound (≈ 11 years). */
const ALL = 4000;
const RANGES = [
  [30, "۱ ماه"],
  [90, "۳ ماه"],
  [180, "۶ ماه"],
  [365, "۱ سال"],
  [ALL, "همه"],
] as const;
type Range = (typeof RANGES)[number][0];

function Kv({ label, value, cls }: { label: string; value: string; cls?: string }) {
  return (
    <div>
      {label}
      <b className={cls}>{value}</b>
    </div>
  );
}

export function FundDetail({
  ins,
  tick,
  date,
  live,
  onBack,
}: {
  ins: string;
  tick: number;
  /** Selected session, `YYYY-MM-DD`; undefined means the latest session. */
  date?: string;
  live: boolean;
  onBack: () => void;
}) {
  const t = useTokens();
  const [range, setRange] = useState<Range>(90);
  const detail = useQuery((s) => api.fund(ins, range, date, s), [ins, tick, date, range]);
  const intraday = useQuery((s) => api.fundIntraday(ins, date, s), [ins, tick, date]);

  const intradayOpt = useMemo(() => fundIntradayOption(intraday.data ?? [], t), [intraday.data, t]);
  const historyOpt = useMemo(() => fundHistoryOption(detail.data?.history ?? [], t), [detail.data, t]);

  const back = (
    <button type="button" className="back" onClick={onBack}>
      → بازگشت به داشبورد
    </button>
  );
  if (detail.error && !detail.data) {
    return (
      <>
        {back}
        <div className="banner">{detail.error.message}</div>
      </>
    );
  }
  if (!detail.data) return <Empty>در حال بارگذاری…</Empty>;

  const { snapshot: f, returns: r, history } = detail.data;
  return (
    <>
      {back}
      <div className="detail-head">
        <h1>{f.symbol}</h1>
        <span className="name">{f.name}</span>
        <span className="chip">{f.fund_type_fa}</span>
        <StatusBadge f={f} />
        <span className="name">آخرین به‌روزرسانی {time(f.ts)}</span>
      </div>

      <section className="card" style={{ marginBottom: 16 }}>
        <div className="kv">
          <Kv label="آخرین قیمت (ت)" value={price(f.last_price)} />
          <Kv label="تغییر امروز" value={pct(f.change, { signed: true, digits: 2 })} cls={signClass(f.change)} />
          <Kv label="NAV ابطال (ت)" value={price(f.nav)} />
          <Kv label="حباب" value={f.premium == null ? "قابل محاسبه نیست" : pct(f.premium, { signed: true })} cls={signClass(f.premium)} />
          <Kv label="خالص دارایی" value={money(f.aum)} />
          <Kv label="ورود پول حقیقی" value={money(f.ind_net_flow, { signed: true })} cls={signClass(f.ind_net_flow)} />
          <Kv label="ارزش معاملات" value={money(f.value)} />
          <Kv label="معاملات بلوکی" value={money(f.block_value)} />
          <Kv label="قدرت خریدار" value={f.buyer_power == null ? "—" : num(f.buyer_power, 2)} />
          <Kv label="گردش واحدها" value={pct(f.turnover, { digits: 2 })} />
          <Kv label="تعداد معاملات" value={num(f.trade_count)} />
        </div>
        {f.quality_flags.length > 0 && (
          <div className="note">
            پرچم‌های کیفیت آخرین دقیقه:{" "}
            {f.quality_flags.map((q) => (
              <span className={`flag ${flagKind(q)}`} key={q} title={FLAGS[q]?.hint}>
                {flagFa(q)}
              </span>
            ))}
          </div>
        )}
      </section>

      <div className="grid two">
        <Card
          title="قیمت و NAV در طول جلسه"
          question="قیمت بازار از ارزش ذاتی جلو افتاده یا عقب مانده است؟"
          stale={intraday.refreshing}
          note={
            intraday.data?.some((p) => p.backfilled)
              ? "هر دو خط به تومان و روی یک محورند، پس فاصله‌ی آن‌ها همان حباب است. بخش خط‌چین پیش از روشن شدن کالکتور از ریز معاملات بازسازی شده است و NAV ندارد."
              : "هر دو خط به تومان و روی یک محور هستند، پس فاصله‌ی آن‌ها همان حباب است."
          }
        >
          {(intraday.data?.length ?? 0) < 2 ? (
            <Empty>
              {live
                ? "منحنی درون‌روز پس از دو دقیقه از شروع جلسه رسم می‌شود."
                : "از این جلسه فقط وضعیت پایانی ذخیره شده است. منحنی درون‌روز از اولین جلسه‌ای رسم می‌شود که کالکتور در آن روشن باشد."}
            </Empty>
          ) : (
            <Chart option={intradayOpt} height={300} ariaLabel="قیمت و NAV صندوق در طول جلسه" />
          )}
        </Card>

        <Card
          title="تاریخچه‌ی روزانه"
          question="روند قیمت و اینکه پول حقیقی در کدام روزها وارد یا خارج شده است."
          stale={detail.refreshing}
          actions={<Seg label="بازه‌ی تاریخچه" options={RANGES} value={range} onChange={setRange} />}
          note={
            range === ALL && history[0]
              ? (
                  <>
                    {num(history.length)} روز معاملاتی ذخیره شده است، از {faDate(history[0].trade_date_fa)}. برای
                    تاریخچه‌ی بلندتر: <code dir="ltr">tsetmc-viewer backfill --days N</code>
                  </>
                )
              : undefined
          }
        >
          {history.length === 0 ? (
            <Empty>تاریخچه‌ی روزانه برای این صندوق هنوز دریافت نشده است.</Empty>
          ) : (
            <Chart option={historyOpt} height={300} ariaLabel="قیمت پایانی و ورود پول حقیقی روزانه" />
          )}
        </Card>

        <Card wide title="بازده" question="بازده قیمتی صندوق در افق‌های مختلف (بر پایه‌ی قیمت پایانی).">
          <div className="kv">
            {HORIZONS.map(([k, label]) => (
              <Kv key={k} label={label} value={pct(r?.[k], { signed: true })} cls={signClass(r?.[k])} />
            ))}
          </div>
        </Card>
      </div>
    </>
  );
}
