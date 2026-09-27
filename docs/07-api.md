# API

<p class="lead">پنل فقط از طریق این API داده می‌خواند. همه‌ی پاسخ‌ها JSON هستند و قرارداد کامل (OpenAPI) به‌طور خودکار در <code>/docs</code> و <code>/redoc</code> منتشر می‌شود.</p>

## endpointها

| مسیر | پاسخ | کاربرد در پنل |
|---|---|---|
| `GET /api/v1/overview` | `Overview` | کارت‌های بالای صفحه: AUM، ورود پول، حباب، پهنا، شاخص کل |
| `GET /api/v1/funds` | `FundSnapshot[]` | جدول صندوق‌ها و treemap |
| — | `FundSnapshot.status_kind` · `status_title` · `status_at` · `under_supervision` | وضعیت نماد در TSETMC (`open` · `suspended` · `reserved` · `blocked` · `forbidden` · `unknown`) در همه‌ی پاسخ‌های صندوق؛ `Overview.not_trading` تعداد صندوق‌های غیرعادی |
| `GET /api/v1/funds/{ins_code}?days=` | `FundDetail` | صفحه‌ی صندوق: وضعیت، بازده‌ها، تاریخچه‌ی روزانه‌ی `days` روز اخیر (تقویمی، ۵ تا ۴۰۰۰، پیش‌فرض ۱۲۰) |
| `GET /api/v1/funds/{ins_code}/intraday` | `FundIntradayPoint[]` | نمودار درون‌روز قیمت، NAV و حباب؛ دقیقه‌های پیش از روشن شدن collector با `backfilled: true` و بدون NAV و ورود پول ([ADR 0012](adr/0012-intraday-backfill.md)) |
| `GET /api/v1/market/flow` | `MarketFlowPoint[]` | ورود پول حقیقی تجمعی کل بازار در طول روز، کنار شاخص |
| `GET /api/v1/flows/daily?days=60` | `DailyFlow[]` | ورود پول روزانه به تفکیک نوع صندوق |
| `GET /api/v1/returns` | `FundReturns[]` | heatmap بازده ۱ روز تا ابتدای سال |
| `GET /api/v1/premium/daily?days=120` | `PremiumPoint[]` | حباب بازار (میانه و وزنی) در پایان هر جلسه |
| `GET /api/v1/premium/intraday` | `PremiumPoint[]` | حباب بازار دقیقه به دقیقه در طول جلسه |
| `GET /api/v1/calendar?year=1405` | `CalendarDay[]` | تعطیلات رسمی، تعطیلی‌های اعلام‌شده و مشاهده‌شده‌ی یک سال شمسی |
| `GET /api/v1/sessions?limit=90` | `SessionInfo[]` | فهرست جلسه‌هایی که `fund_ticks` برایشان داده دارد (نودست‌ترین اول)؛ انتخابگر جلسه در سربرگ پنل را پر می‌کند |
| `GET /api/v1/quality` | گزارش کیفیت | نشانگر سلامت داده |
| `GET /api/v1/stream` | `text/event-stream` | اعلام «تیک جدید» به پنل |
| `GET /health` · `GET /api/v1/health` · `GET /api/v1/pipeline/runs` | — | سلامت API و تازگی داده‌ی collector (نوار «داده‌ی قدیمی» در پنل) |
| `GET /metrics` | متن Prometheus | فقط برای Prometheus؛ nginx آن را به بیرون نمی‌دهد ([پایش](11-monitoring.md)) |

همه‌ی endpointهای تحلیلی پارامتر اختیاری `?date=YYYY-MM-DD` دارند. **پیش‌فرض آخرین جلسه‌ی معاملاتی‌ای است که داده دارد**، نه تاریخ امروز. پنل در روز تعطیل خالی نمی‌ماند و جلسه‌ی قبل را نشان می‌دهد، با برچسب `is_live: false` و تاریخ شمسی `session_date_fa`. انتخابگر جلسه در سربرگ پنل همین پارامتر را ست می‌کند؛ گزینه‌هایش از `GET /api/v1/sessions` می‌آید و «فقط پایانی» را کنار جلسه‌هایی می‌گذارد که فقط عکس پایان جلسه دارند، نه سری دقیقه‌ای (`has_intraday: false`).

```console
$ curl -s localhost:8000/api/v1/overview | jq
{
  "session_date": "2026-09-24",
  "session_date_fa": "1405/07/02",
  "is_live": false,
  "funds": 159,
  "total_aum": 3752367895747336,
  "ind_net_flow": 5738135670836,
  "median_premium": -0.0051,
  "advancers": 137, "decliners": 21, "unchanged": 1,
  "index_value": 7257043.42,
  "index_change": 0.0125,
  ...
}
```

## قراردادها

<div class="grid cards two" markdown>

-   :material-currency-usd-off: __مبلغ‌ها ریال و عدد صحیح__

    ---

    تبدیل به تومان یا «همت» فقط در لایه‌ی نمایش انجام می‌شود. API هیچ‌وقت عدد گردشده برنمی‌گرداند.

-   :material-percent-outline: __نسبت‌ها کسر ساده__

    ---

    `0.012` یعنی ۱٫۲٪. نسبتی که معنی ندارد `null` است، نه صفر (مثل حباب صندوق اهرمی یا گردش صندوقی که AUM ندارد).

-   :material-clock-time-four-outline: __زمان‌ها با منطقه‌ی زمانی__

    ---

    ISO 8601 با `+03:30`. تاریخ‌ها میلادی‌اند و کنار هر کدام نسخه‌ی شمسی (`*_fa`) آمده است.

-   :material-flag-outline: __پرچم‌های کیفیت با نام__

    ---

    `quality_flags: ["NAV_STALE", "FLOW_VALUE_ESTIMATED"]`، نه bitmask. پنل با همین نام‌ها داده‌ی مشکوک را کم‌رنگ نشان می‌دهد.

</div>

## کش و هدرها

هر پاسخ تحلیلی از مسیر `cached_json` می‌گذرد ([ADR 0006](adr/0006-caching.md)):

| هدر | مقدار | معنا |
|---|---|---|
| `X-Tick` | `2026-09-26T10:41:00+03:30` | پاسخ مربوط به کدام تیک است |
| `X-Cache` | `hit` / `miss` | از Redis آمد یا از ClickHouse |
| `ETag` | `W/"…"` | از (مسیر، پارامترها، تیک) ساخته می‌شود |
| `Cache-Control` | `private, max-age=N` | N = ثانیه‌های مانده تا تیک بعد |

```console
$ curl -sI localhost:8000/api/v1/funds | grep -iE 'x-cache|etag'
x-cache: miss
etag: W/"3f5a…"
$ curl -sI localhost:8000/api/v1/funds -H 'If-None-Match: W/"3f5a…"' | head -1
HTTP/1.1 304 Not Modified
```

اگر Redis در دسترس نباشد، API بدون خطا مستقیماً از ClickHouse پاسخ می‌دهد (`X-Tick: none`).

## رویدادهای زنده (SSE)

```javascript
const events = new EventSource("/api/v1/stream");
events.addEventListener("tick", (e) => {
  const { tick, funds, status } = JSON.parse(e.data);
  refetchDashboard();          // پاسخ‌ها در این لحظه تازه‌اند و کش سمت سرور هم آماده است
});
```

| فریم | زمان |
|---|---|
| `event: hello` | هنگام اتصال، با آخرین تیک |
| `event: tick` | پس از commit شدن داده‌ی هر دقیقه |
| `: keep-alive` | هر ۱۵ ثانیه، تا پراکسی‌ها اتصال را نبندند |

**چرا SSE و نه WebSocket؟** جریان داده یک‌طرفه است (سرور به مرورگر). SSE روی HTTP معمولی کار می‌کند، اتصال دوباره را خود مرورگر انجام می‌دهد و در FastAPI فقط یک `StreamingResponse` است.

## کارایی

روی داده‌ی واقعی (۱۵۹ صندوق، ۴۹ هزار ردیف تاریخچه)، **بدون کش**:

| endpoint | اندازه | زمان |
|---|--:|--:|
| `/overview` | ۰٫۴ KB | ۷۸ ms |
| `/funds` | ۱۰۸ KB (با gzip ۲۵ KB) | ۳۲ ms |
| `/returns` | ۲۹ KB | ۶۸ ms |
| `/flows/daily?days=60` | ۲۴ KB | ۵۵ ms |
| `/funds/{ins}` | ۱۱ KB | ۸۵ ms |

## بازبینی روز ۵

- `index_change` در `overview` از **امتیاز** (همان چیزی که TSETMC می‌دهد) به **کسر** تغییر داده شد (۰٫۰۱۲۵ یعنی +۱٫۲۵٪)، تا با قرارداد «نسبت‌ها کسر ساده» یکی باشد. این ناسازگاری وقتی پیدا شد که پنل عدد را برای اولین بار نمایش داد: کاشی شاخص «+۸٬۹۶۳٬۷۹۱٪» نشان می‌داد. تست `test_overview` حالا این تبدیل را بررسی می‌کند.

## بازبینی پس از روز ۷

- `overview` دو فیلد تازه دارد: `weighted_premium` (حباب وزنی بر اساس خالص دارایی، [منطق مالی](05-financial-logic.md#حباب-میانه-یا-وزنی)) و `holiday_today` (نام تعطیلی امروز، رسمی یا مشاهده‌شده).
- سه endpoint تازه: `premium/daily`، `premium/intraday` و `calendar`. همه مثل بقیه با تیک کش می‌شوند.
- API با چند worker اجرا می‌شود. کش بین پروسه‌ها یک بار محاسبه می‌شود ([ADR 0010](adr/0010-high-availability.md)).
