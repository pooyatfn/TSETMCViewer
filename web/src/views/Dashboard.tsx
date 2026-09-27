import type { ECElementEvent } from "echarts/core";
import { lazy, Suspense, useMemo, useState } from "react";

import { api } from "../api/client";
import type { FundSnapshot } from "../api/types";
import { Chart } from "../charts/Chart";
import {
  dailyFlowsOption,
  marketFlowOption,
  moneyMapOption,
  premiumOption,
  premiumTrendOption,
  returnsOption,
  riskReturnOption,
  treemapOption,
} from "../charts/options";
import { isEquityType } from "../charts/theme";
import { useTokens } from "../charts/tokens";
import { Card, Empty, Seg, Tabs } from "../components/Card";
import { DivergingLegend, TypeLegend } from "../components/Legend";
import { FundsTable } from "../components/FundsTable";
import { KpiTiles } from "../components/KpiTiles";
import { QualityCard } from "../components/QualityCard";
import { isHalted } from "../components/StatusBadge";
import { num } from "../lib/format";
import { useQuery } from "../lib/hooks";

// The docs tab pulls in react-markdown + the full docs/ content (~700 KB before
// gzip); split it out of the main bundle so the dashboard's first load stays light.
const Docs = lazy(() => import("./Docs").then((m) => ({ default: m.Docs })));

const DAYS = [
  [20, "۲۰ روز"],
  [60, "۶۰ روز"],
  [120, "۱۲۰ روز"],
] as const;
type Days = (typeof DAYS)[number][0];

export const TABS = [
  ["overview", "نمای کلی"],
  ["valuation", "ارزش‌گذاری"],
  ["flows", "جریان پول"],
  ["returns", "بازده"],
  ["table", "جدول"],
  ["docs", "مستندات"],
] as const;
export type TabId = (typeof TABS)[number][0];

// "مستندات" is a separate link beside the panel title (see App.tsx), not one
// of the content-section pills, so it's kept out of the row rendered here.
const SECTION_TABS = TABS.filter(([id]) => id !== "docs");

/** Chart marks carry their fund (scatter) or ins_code (treemap) in the data item. */
interface MarkData {
  fund?: FundSnapshot;
  ins?: string;
}

export function Dashboard({
  tick,
  date,
  tab,
  onTab,
  onOpen,
}: {
  tick: number;
  /** Selected session, `YYYY-MM-DD`; undefined means the latest session. */
  date?: string;
  tab: TabId;
  onTab: (tab: TabId) => void;
  onOpen: (ins: string) => void;
}) {
  const t = useTokens();
  const [days, setDays] = useState<Days>(60);

  const overview = useQuery((s) => api.overview(date, s), [tick, date]);
  const funds = useQuery((s) => api.funds(date, s), [tick, date]);
  const flow = useQuery((s) => api.marketFlow(date, s), [tick, date]);
  const daily = useQuery((s) => api.dailyFlows(days, date, s), [tick, date, days]);
  const returns = useQuery((s) => api.returns(date, s), [tick, date]);
  const risk = useQuery((s) => api.risk(90, date, s), [tick, date]);
  const premIntraday = useQuery((s) => api.premiumIntraday(date, s), [tick, date]);
  const premDaily = useQuery((s) => api.premiumDaily(120, date, s), [tick, date]);
  const [premView, setPremView] = useState<"auto" | "intraday" | "daily">("auto");
  const intradayReady = (premIntraday.data?.length ?? 0) >= 2;
  const premMode = premView === "auto" ? (intradayReady ? "intraday" : "daily") : premView;
  const premPoints = (premMode === "intraday" ? premIntraday.data : premDaily.data) ?? [];

  const equity = useMemo(() => (funds.data ?? []).filter((f) => isEquityType(f.fund_type)), [funds.data]);
  const halted = useMemo(() => equity.filter(isHalted), [equity]);
  const topReturns = useMemo(() => {
    const aum = new Map(equity.map((f) => [f.ins_code, f.aum ?? 0]));
    return (returns.data ?? [])
      .filter((r) => aum.has(r.ins_code))
      .sort((a, b) => (aum.get(b.ins_code) ?? 0) - (aum.get(a.ins_code) ?? 0))
      .slice(0, 25);
  }, [returns.data, equity]);

  const opts = useMemo(
    () => ({
      treemap: treemapOption(equity, t),
      premium: premiumOption(equity, t),
      moneyMap: moneyMapOption(equity, t),
      flow: marketFlowOption(flow.data ?? [], t),
      daily: dailyFlowsOption(daily.data ?? [], t),
      returns: returnsOption(topReturns, t),
      premTrend: premiumTrendOption(premPoints, t, premMode === "intraday"),
      risk: riskReturnOption(risk.data ?? [], t),
    }),
    [equity, flow.data, daily.data, topReturns, t, premPoints, premMode, risk.data],
  );

  const open = (p: ECElementEvent) => {
    const d = (p.data ?? {}) as MarkData;
    const ins = d.fund?.ins_code ?? d.ins;
    if (ins) onOpen(ins);
  };

  // مستندات is its own page, not a dashboard section: skip the KPI tiles,
  // banners, section tabs and chart grid entirely (and don't gate it behind
  // fund-data loading/error, since it doesn't need that data at all).
  if (tab === "docs") {
    return (
      <Suspense fallback={<Empty>در حال بارگذاری مستندات…</Empty>}>
        <Docs />
      </Suspense>
    );
  }

  const error = overview.error ?? funds.error;
  if (error && !overview.data) {
    return <div className="banner">دریافت داده از API ممکن نشد: {error.message}</div>;
  }
  if (overview.loading || funds.loading) return <Empty>در حال بارگذاری…</Empty>;
  const o = overview.data;
  if (!o || equity.length === 0) {
    return <Empty>هنوز داده‌ای ذخیره نشده است. کالکتور را اجرا کنید (make up) یا یک چرخه بگیرید (collect-once).</Empty>;
  }

  return (
    <>
      <KpiTiles o={o} />
      {halted.length > 0 && (
        <div className="banner" role="status">
          {num(halted.length)} صندوق امروز در حالت عادی معامله نمی‌شوند:{" "}
          {halted.map((f, i) => (
            <span key={f.ins_code}>
              {i > 0 && "، "}
              <button type="button" className="link" onClick={() => onOpen(f.ins_code)}>
                {f.symbol}
              </button>{" "}
              ({f.status_title})
            </span>
          ))}
          . قیمت و حباب این صندوق‌ها ممکن است مربوط به آخرین معامله‌ی پیش از توقف باشد.
        </div>
      )}
      <Tabs options={SECTION_TABS} value={tab} onChange={onTab} />

      <div className="grid two">
        {tab === "overview" && (
          <>
            <Card
              wide
              title="نقشه‌ی بازار صندوق‌ها"
              question="پول کجاست و امروز چطور حرکت کرد؟ مساحت = خالص دارایی، رنگ = تغییر قیمت امروز."
              stale={funds.refreshing}
              actions={<DivergingLegend neg="منفی (تا −۳٪)" pos="مثبت (تا +۳٪)" />}
              note="روی هر خانه کلیک کنید تا صفحه‌ی صندوق باز شود."
            >
              <Chart option={opts.treemap} height={440} ariaLabel="نقشه‌ی درختی صندوق‌های سهامی بر اساس خالص دارایی و تغییر روزانه" onClick={open} />
            </Card>

            <Card
              title="ورود پول حقیقی در طول جلسه"
              question="همین حالا پول حقیقی وارد صندوق‌ها می‌شود یا خارج؟ و شاخص کل همراه آن چه می‌کند؟ (پول: میلیارد تومان، شاخص: میلیون واحد)"
              stale={flow.refreshing}
              note="دو پنل روی یک محور زمان؛ عمداً دو محور عمودی روی یک نمودار نگذاشته‌ایم."
            >
              {(flow.data?.length ?? 0) < 2 ? (
                <Empty>
                  {o.is_live
                    ? "منحنی درون‌روز پس از دو دقیقه از شروع جلسه‌ی معاملاتی رسم می‌شود."
                    : "از این جلسه فقط وضعیت پایانی ذخیره شده است، چون کالکتور در طول جلسه روشن نبود. منحنی درون‌روز از اولین جلسه‌ای رسم می‌شود که کالکتور در آن روشن باشد."}
                </Empty>
              ) : (
                <Chart option={opts.flow} height={340} ariaLabel="ورود پول حقیقی تجمعی و شاخص کل در طول جلسه" />
              )}
            </Card>

            <Card
              wide
              title="حباب بازار در طول زمان"
              question="بازار صندوق‌ها گران‌تر می‌شود یا ارزان‌تر؟ میانه‌ی صندوق‌ها و میانگین وزنی بر اساس خالص دارایی."
              stale={premIntraday.refreshing || premDaily.refreshing}
              actions={
                <Seg
                  label="بازه‌ی حباب"
                  options={[
                    ["intraday", "امروز"],
                    ["daily", "روزانه"],
                  ] as const}
                  value={premMode}
                  onChange={setPremView}
                />
              }
              note="میانه نشان می‌دهد «صندوق معمولی» چقدر گران است؛ خط وزنی نشان می‌دهد پول بازار کجا نشسته است. اگر فاصله‌ی دو خط زیاد شود، چند صندوق بزرگ با بقیه‌ی بازار هم‌جهت نیستند. اهرمی‌ها کنار گذاشته شده‌اند."
            >
              <div className="legend">
                <span>
                  <i style={{ background: t.series[0] }} />
                  میانه
                </span>
                <span>
                  <i style={{ background: t.series[1] }} />
                  وزنی (خط‌چین)
                </span>
              </div>
              {premPoints.length < 2 ? (
                <Empty>
                  {premMode === "intraday"
                    ? "منحنی درون‌روز حباب پس از دو دقیقه داده از داخل جلسه رسم می‌شود."
                    : `TSETMC تاریخچه‌ی NAV نمی‌دهد؛ این سری از اولین روزی که سرویس داده گرفته ساخته می‌شود (تا الان ${num(premPoints.length)} روز).`}
                </Empty>
              ) : (
                <Chart option={opts.premTrend} height={280} ariaLabel="میانه و میانگین وزنی حباب صندوق‌ها در طول زمان" />
              )}
            </Card>

            <QualityCard tick={tick} date={date} />
          </>
        )}

        {tab === "valuation" && (
          <>
            <Card
              title="حباب و تخفیف نسبت به NAV"
              question="بازار صندوق‌ها را گران می‌خرد یا ارزان؟ هر نقطه یک صندوق، اندازه = خالص دارایی."
              stale={funds.refreshing}
              note="حباب صندوق‌های اهرمی نمایش داده نمی‌شود: NAV منتشرشده با ارزش واحد عادیِ معامله‌شده برابر نیست."
            >
              <TypeLegend />
              <Chart option={opts.premium} height={300} ariaLabel="توزیع حباب صندوق‌ها به تفکیک نوع" onClick={open} />
            </Card>

            <Card
              title="نقشه‌ی پول و ارزش‌گذاری"
              question="پول حقیقی دنبال صندوق‌های گران است یا ارزان؟ محور افقی = حباب، عمودی = ورود پول نسبت به دارایی."
              stale={funds.refreshing}
              note="شش صندوق با بیشترین جابه‌جایی پول برچسب خورده‌اند؛ حباب بیش از ±۱۰٪ روی لبه نشسته است."
            >
              <Chart option={opts.moneyMap} height={340} ariaLabel="نمودار پراکندگی حباب در برابر ورود پول حقیقی" onClick={open} />
            </Card>
          </>
        )}

        {tab === "flows" && (
          <Card
            wide
            title="ورود پول حقیقی روزانه به تفکیک نوع"
            question="روند چند هفته‌ی اخیر: پول به کدام نوع صندوق می‌رود؟ (میلیارد تومان)"
            stale={daily.refreshing}
            actions={<Seg label="بازه" options={DAYS} value={days} onChange={setDays} />}
            note={<>ستون‌های کم‌رنگ با * روزهایی‌اند که جریان پول از روی داده‌ی تاریخی برآورد شده است.</>}
          >
            <TypeLegend />
            {(daily.data?.length ?? 0) === 0 ? (
              <Empty>تاریخچه‌ی روزانه هنوز پر نشده است (دستور backfill).</Empty>
            ) : (
              <Chart option={opts.daily} height={310} ariaLabel="ورود پول حقیقی روزانه به تفکیک نوع صندوق" />
            )}
          </Card>
        )}

        {tab === "returns" && (
          <Card
            wide
            title="بازده در افق‌های مختلف"
            question="چه کسی جلو افتاد و چه کسی عقب ماند؟ ۲۵ صندوق بزرگ."
            stale={returns.refreshing}
            actions={<DivergingLegend neg="زیان" pos="سود" />}
            note="رنگ هر ستون جداگانه مقیاس شده است (صدک ۹۰ همان افق)، چون بازده یک روزه و از ابتدای سال هم‌مقیاس نیستند."
          >
            {topReturns.length === 0 ? (
              <Empty>بازده‌ها پس از پر شدن تاریخچه‌ی روزانه محاسبه می‌شوند.</Empty>
            ) : (
              <Chart option={opts.returns} height={Math.max(240, 28 + topReturns.length * 26)} ariaLabel="نقشه‌ی حرارتی بازده صندوق‌ها" onClick={(p) => {
                const r = topReturns[(p.value as [number, number])[1]];
                if (r) onOpen(r.ins_code);
              }} />
            )}
          </Card>
        )}

        {tab === "returns" && (
          <Card
            wide
            title="ریسک و بازده، ۹۰ روز گذشته"
            question="برای نوسانی که این صندوق تحمل کرد، بازده‌اش می‌ارزید؟ اندازه = خالص دارایی، رنگ = نوع صندوق."
            stale={risk.refreshing}
            note="نوسان = انحراف معیار بازده روزانه، سالانه‌شده (√۲۵۲)؛ زیر ۵ روز داده نمایش داده نمی‌شود."
          >
            <TypeLegend />
            {(risk.data?.filter((f) => f.volatility != null && f.period_return != null).length ?? 0) < 3 ? (
              <Empty>این نمودار پس از چند روز جمع شدن تاریخچه‌ی روزانه پر می‌شود.</Empty>
            ) : (
              <Chart option={opts.risk} height={340} ariaLabel="پراکندگی نوسان در برابر بازده صندوق‌ها" onClick={(p) => {
                const f = (p.data as { f?: { ins_code: string } })?.f;
                if (f) onOpen(f.ins_code);
              }} />
            )}
          </Card>
        )}

        {tab === "table" && (
          <Card wide title="همه‌ی صندوق‌ها" question="جدول کامل همان داده‌ها؛ برای مرتب‌سازی روی سرستون کلیک کنید." stale={funds.refreshing}>
            <FundsTable funds={equity} onOpen={onOpen} />
          </Card>
        )}

      </div>
    </>
  );
}
