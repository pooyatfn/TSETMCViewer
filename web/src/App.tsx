import { useEffect, useState } from "react";

import { api } from "./api/client";
import { readTokens, type Tokens } from "./charts/theme";
import { TokensContext } from "./charts/tokens";
import { faDate, num, time } from "./lib/format";
import { useHashRoute, useHeartbeat, useLiveTicks, useQuery, useTheme } from "./lib/hooks";
import { Dashboard, TABS, type TabId } from "./views/Dashboard";
import { FundDetail } from "./views/FundDetail";

const TAB_IDS = new Set<string>(TABS.map(([id]) => id));

export function App() {
  const [theme, toggleTheme] = useTheme();
  const [route, go] = useHashRoute();
  const live = useLiveTicks();
  // Chart tokens are re-read after data-theme is applied (useTheme's effect runs first).
  const [tokens, setTokens] = useState<Tokens | null>(null);
  useEffect(() => setTokens(readTokens()), [theme]);

  const beat = useHeartbeat();
  // undefined = latest session (the default and the only "live" one).
  const [session, setSession] = useState<string | undefined>(undefined);
  const sessions = useQuery((s) => api.sessions(s), [live.tick]);
  // Also on the heartbeat: at the close no tick may arrive, but «زنده» must still turn off.
  const overview = useQuery((s) => api.overview(session, s), [live.tick, beat, session]);
  const health = useQuery((s) => api.health(s), [live.tick, beat]);
  const o = overview.data;
  const collector = health.data?.collector;
  const stale = collector?.state === "stale";
  const fundIns = /^\/fund\/(.+)$/.exec(route)?.[1];
  const tabMatch = /^\/t\/([a-z]+)$/.exec(route)?.[1];
  const tab: TabId = tabMatch && TAB_IDS.has(tabMatch) ? (tabMatch as TabId) : "overview";

  return (
    <TokensContext.Provider value={tokens}>
      <header className="topbar">
        <a className="title" href="#/">
          دیده‌بان صندوق‌های سهامی
        </a>
        <a
          className={`docs-link${tab === "docs" ? " active" : ""}`}
          href="#/t/docs"
          aria-current={tab === "docs" ? "page" : undefined}
        >
          مستندات
        </a>
        {o && tab !== "docs" && (
          <select
            className="session-select"
            aria-label="انتخاب جلسه"
            title="جلسه‌ی دیگری را برای مشاهده انتخاب کنید"
            value={session ?? ""}
            onChange={(e) => setSession(e.target.value || undefined)}
          >
            <option value="">جلسه‌ی زنده (آخرین)</option>
            {(sessions.data ?? []).map((si) => (
              <option key={si.day} value={si.day}>
                {faDate(si.day_fa)}
                {si.has_intraday ? "" : " · فقط پایانی"}
              </option>
            ))}
          </select>
        )}
        <span className="spacer" />
        {tab !== "docs" && (
          <span
            className="chip"
            title={live.connected ? "اتصال زنده به سرور برقرار است" : "اتصال زنده قطع است؛ مرورگر دوباره تلاش می‌کند"}
          >
            <span className={`dot${stale ? " warn" : o?.is_live && live.connected ? " live" : ""}`} />
            {stale ? "داده‌ی قدیمی" : o?.is_live ? "زنده" : "بازار بسته"} · {o?.is_live ? "" : "آخرین داده "}
            {time(o?.last_update)}
          </span>
        )}
        <button type="button" className="icon-btn" onClick={toggleTheme} aria-label="تغییر پوسته‌ی روشن و تیره">
          {theme === "dark" ? "☀" : "☾"}
        </button>
      </header>
      <main>
        {tab !== "docs" && stale && (
          <div className="banner warn" role="status">
            بازار باز است اما {num(Math.round((collector?.lag_seconds ?? 0) / 60))} دقیقه است که داده‌ی تازه‌ای ثبت نشده
            {collector?.failed_streak ? ` (${num(collector.failed_streak)} چرخه‌ی ناموفق پیاپی)` : ""}. معمولاً یعنی
            TSETMC از سرور در دسترس نیست (مثلاً VPN روشن است). اعداد این صفحه مربوط به آخرین دریافت موفق هستند.
          </div>
        )}
        {tab !== "docs" && o && !o.is_live && !stale && (
          <div className="banner">
            {session ? (
              <>
                در حال مشاهده‌ی جلسه‌ی {faDate(o.session_date_fa)} هستید، نه جلسه‌ی زنده. برای بازگشت، «جلسه‌ی زنده» را
                از بالای صفحه انتخاب کنید.
              </>
            ) : (
              <>
                {o.holiday_today ? `امروز تعطیل است (${o.holiday_today}). ` : "بازار بسته است؛ "}
                داده‌ها مربوط به آخرین جلسه‌ی معاملاتی ({faDate(o.session_date_fa)}) هستند.
              </>
            )}
          </div>
        )}
        {tokens &&
          (fundIns ? (
            <FundDetail
              ins={decodeURIComponent(fundIns)}
              tick={live.tick}
              date={session}
              live={o?.is_live ?? false}
              onBack={() => go("/")}
            />
          ) : (
            <Dashboard
              tick={live.tick}
              date={session}
              tab={tab}
              onTab={(id) => go(id === "overview" ? "/" : `/t/${id}`)}
              onOpen={(ins) => go(`/fund/${ins}`)}
            />
          ))}
      </main>
    </TokensContext.Provider>
  );
}
