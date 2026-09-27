# آزمون، CI و مقاوم‌سازی

<p class="lead">این صفحه می‌گوید از کجا می‌دانیم سرویس درست کار می‌کند و وقتی چیزی خراب شود چه رفتاری دارد: چه چیزی تست می‌شود و چرا، CI روی هر تغییر چه چیزهایی را بررسی می‌کند، سرویس در برابر قطعی TSETMC، ClickHouse و Redis چه می‌کند، و آزمون بار درباره‌ی کش چه نشان داد.</p>


- **۲۳۶** — تست خودکار (۲۱۲ پایتون، ۱۶ پنل، ۸ سناریوی هشدار)
- **۸۹٪** — پوشش شاخه‌ای کد پایتون (حداقل مجاز ۸۵٪)
- **۴** — کار CI روی هر push و PR
- **×۷** — توان عملیاتی API با کش، در آزمون بار


## راهبرد آزمون

سه اصل، که هر کدام از یک مشکل واقعی همین پروژه آمده است:



#### پاسخ واقعی، نه داده‌ی ساختگی

تست‌ها با **پاسخ‌های ضبط‌شده‌ی واقعی TSETMC** (`tests/fixtures/sample`) اجرا می‌شوند، که `respx` آن‌ها را روی همان آدرس‌های واقعی سرو می‌کند. شکل واقعی پاسخ‌ها (فیلدهای خالی، تابلوهای فرعی، صندوق‌های بدون NAV) همان چیزی است که pipeline باید با آن کنار بیاید.

#### ClickHouse واقعی، نه mock

۱۲ تست یکپارچگی روی یک ClickHouse واقعی و در یک دیتابیس یک‌بارمصرف اجرا می‌شوند: مایگریشن‌ها، materialized view، `FINAL`، replay و پرس‌وجوهای تحلیلی. باگ مایگریشن ۰۰۰۴ ([ADR 0005](adr/0005-migrations.md)) فقط روی دیتابیس واقعی دیده می‌شد.

#### زمان تزریق‌شدنی

هیچ کدی مستقیم `datetime.now()` را صدا نمی‌زند: همه از `MarketClock` می‌پرسند. تست‌ها ساعت ثابت می‌دهند: «پنجشنبه ساعت ۱۰»، «شنبه وسط جلسه»، «بعد از بسته شدن». رفتار وابسته به تقویم (bootstrap، عکس پایانی، سلامت collector) این‌طور قطعی تست می‌شود.

#### هر باگ، یک تست

هر مشکلی که در اجرای واقعی پیدا شد اول با یک تست بازتولید شد و بعد اصلاح شد: تبدیل تغییر شاخص به درصد، مایگریشن روی 24.8.14، خالص دارایی صفر در عکس پایانی و ازدحام درخواست‌ها روی کش (پایین‌تر).


### نقشه‌ی تست‌ها

| لایه | فایل‌ها | چه چیزی را تضمین می‌کند |
|---|---|---|
| منطق مالی و دامنه | `test_metrics`، `test_domain`، `test_clock` | حباب، خالص دارایی، جریان پول، قدرت خریدار، تقویم جلالی، ساعات بازار |
| پارس و تبدیل | `test_tsetmc_models`، `test_transform`، `test_universe` | پاسخ واقعی به مدل تبدیل می‌شود. هویت صندوق و تابلوی اصلی درست تشخیص داده می‌شود |
| کیفیت داده | `test_validate` (۲۰ تست) | هر ۱۰ بررسی، هر روش اصلاح، ثبت لبه‌ای رخدادها و بازیابی وضعیت پس از restart |
| جمع‌آوری | `test_collector`، `test_bootstrap`، `test_collector_loop`، `test_history`، `test_http` | چرخه‌ی کامل، خرابی جزئی و کامل، retry، راه‌اندازی خارج از ساعات بازار، توقف تمیز، هشدار خرابی پیاپی |
| ذخیره‌سازی | `test_migrate` و تست‌های یکپارچگی | مایگریشن‌ها idempotent هستند، با checksum قفل‌اند و روی ClickHouse واقعی و هر دو حالت نام‌گذاری tuple اجرا می‌شوند |
| API | `test_api`، `test_api_cache`، `test_analytics_api`، `test_stream` | قرارداد پاسخ‌ها، ETag و 304، single-flight، حفظ تاریخ جلسه به‌ازای هر تیک، SSE، خطای 503 |
| پیکربندی | `test_repo_consistency` | تگ ClickHouse در CI و compose یکی است. هر تنظیم کد در `.env.example` مستند شده است |
| پنل | `format.test.ts`، `options.test.ts` | قالب‌بندی فارسی اعداد و علامت‌ها، و تصمیم‌های نمایشی نمودارها (اهرمی‌ها، لبه‌ها، رنگ، زمان از چپ به راست) |

> **دو تست که از «ناسازگاری فایل‌ها» جلوگیری می‌کنند**
>
> `test_repo_consistency.py` کد محصول را تست نمی‌کند، بلکه **هماهنگی فایل‌ها** را. اولین اجرای آن بلافاصله چهار تنظیم را پیدا کرد که در کد بودند ولی در `.env.example` نه. تست دوم تضمین می‌کند که CI تست‌ها را روی همان نسخه‌ی ClickHouse اجرا کند که کاربر اجرا می‌کند.

## CI


<svg class="dg" viewBox="0 0 960 400" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="مراحل CI: یک رویداد، سه کار موازی و یک آزمون دود">
  <style>
    :root {
      --bg:#f7fafb; --surface:#ffffff; --line:#9fb6bc; --text:#16303a; --muted:#5b7680;
      --src:#e9f3ee; --src-line:#58a37b; --core:#e3eff2; --core-line:#2c7486;
      --store:#fbf0dd; --store-line:#d98e1f; --serve:#efeaf7; --serve-line:#7a62b3;
      --arrow:#5b7680; --hot:#d98e1f;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg:#151f24; --surface:#1b272d; --line:#3c525a; --text:#e2ecef; --muted:#9ab0b7;
        --src:#16302a; --src-line:#5cc48a; --core:#15313a; --core-line:#4fb3c4;
        --store:#33291a; --store-line:#f0b04f; --serve:#262036; --serve-line:#a58ee0;
        --arrow:#8aa3ab; --hot:#f0b04f;
      }
    }
    .dg-bg   { fill: var(--bg); }
    text     { font-family: "Vazirmatn", "Segoe UI", Tahoma, sans-serif; fill: var(--text); direction: rtl; unicode-bidi: plaintext; }
    .t-title { font-size: 16px; font-weight: 700; }
    .t-body  { font-size: 13px; }
    .t-small { font-size: 11.5px; fill: var(--muted); }
    .t-mono  { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 10.5px; fill: var(--muted); direction: ltr; }
    .t-zone  { font-size: 11px; font-weight: 700; fill: var(--muted); letter-spacing: .02em; }
    .box     { fill: var(--surface); stroke: var(--line); stroke-width: 1.2; }
    .src     { fill: var(--src);   stroke: var(--src-line);   stroke-width: 1.4; }
    .core    { fill: var(--core);  stroke: var(--core-line);  stroke-width: 1.4; }
    .store   { fill: var(--store); stroke: var(--store-line); stroke-width: 1.4; }
    .serve   { fill: var(--serve); stroke: var(--serve-line); stroke-width: 1.4; }
    .zone    { fill: none; stroke: var(--line); stroke-width: 1; stroke-dasharray: 5 4; }
    .edge    { fill: none; stroke: var(--arrow); stroke-width: 1.5; }
    .edge.dash { stroke-dasharray: 5 4; }
    .edge.hot  { stroke: var(--hot); stroke-width: 2; }
    .arrowhead { fill: var(--arrow); }
    .arrowhead.hot { fill: var(--hot); }
    .bar-src   { fill: var(--src-line); }
    .bar-core  { fill: var(--core-line); }
    .bar-store { fill: var(--store-line); }
    .bar-serve { fill: var(--serve-line); }
    .grid-line { stroke: var(--line); stroke-width: 1; stroke-dasharray: 2 4; }
  </style>
  <rect class="dg-bg" x="0" y="0" width="960" height="400" rx="16"/>
  <defs>
    <marker id="ci-a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path class="arrowhead" d="M0,0 L10,5 L0,10 z"/>
    </marker>
    <marker id="ci-h" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path class="arrowhead hot" d="M0,0 L10,5 L0,10 z"/>
    </marker>
  </defs>
  <!-- trigger -->
  <rect class="src" x="800" y="160" width="140" height="80" rx="12"/>
  <text class="t-title" x="926" y="192" text-anchor="start">رویداد</text>
  <text class="t-small" x="926" y="214" text-anchor="start">ارسال به main یا PR</text>
  <!-- parallel jobs -->
  <text class="t-zone" x="760" y="30" text-anchor="start">کارهای موازی</text>
  <rect class="zone" x="410" y="40" width="360" height="330" rx="14"/>
  <rect class="core" x="430" y="56" width="320" height="110" rx="12"/>
  <text class="t-title" x="736" y="84" text-anchor="start">پایتون</text>
  <text class="t-body" x="736" y="106" text-anchor="start">بررسی با ruff، ruff format و mypy strict</text>
  <text class="t-body" x="736" y="126" text-anchor="start">تست‌های واحد و یکپارچگی، پوشش دست‌کم ۸۵٪</text>
  <rect class="store" x="444" y="136" width="292" height="22" rx="6"/>
  <text class="t-small" x="728" y="151" text-anchor="start">سرویس ClickHouse 24.8 (همان تگ compose)</text>
  <rect class="core" x="430" y="182" width="320" height="80" rx="12"/>
  <text class="t-title" x="736" y="210" text-anchor="start">پنل وب</text>
  <text class="t-body" x="736" y="234" text-anchor="start">بررسی نوع با tsc، تست‌های vitest و build</text>
  <rect class="core" x="430" y="278" width="320" height="76" rx="12"/>
  <text class="t-title" x="736" y="306" text-anchor="start">مستندات</text>
  <text class="t-body" x="736" y="330" text-anchor="start">ساخت سخت‌گیرانه با mkdocs: لینک شکسته = شکست</text>
  <!-- smoke -->
  <rect class="serve" x="20" y="96" width="340" height="208" rx="12"/>
  <text class="t-title" x="346" y="126" text-anchor="start">آزمون دود با Docker</text>
  <text class="t-small" x="346" y="146" text-anchor="start">فقط اگر پایتون و پنل سبز باشند</text>
  <text class="t-body" x="346" y="176" text-anchor="start">۱. ساخت هر دو ایمیج (سرویس، پنل)</text>
  <text class="t-body" x="346" y="200" text-anchor="start">۲. بالا آوردن stack بدون collector</text>
  <text class="t-body" x="346" y="224" text-anchor="start">۳. کد خروج migrate باید ۰ باشد</text>
  <text class="t-body" x="346" y="248" text-anchor="start">۴. سلامت API و nginx، پراکسی /api</text>
  <text class="t-body" x="346" y="272" text-anchor="start">۵. سایت مستندات بالا است</text>
  <!-- edges -->
  <path class="edge" d="M800,190 C780,190 775,111 752,111" marker-end="url(#ci-a)"/>
  <path class="edge" d="M800,200 L752,222" marker-end="url(#ci-a)"/>
  <path class="edge" d="M800,210 C780,210 775,316 752,316" marker-end="url(#ci-a)"/>
  <path class="edge hot" d="M430,111 C395,111 395,170 362,170" marker-end="url(#ci-h)"/>
  <path class="edge hot" d="M430,222 C395,222 395,230 362,230" marker-end="url(#ci-h)"/>
</svg>

*شکل ۱ — هر push و PR سه کار موازی دارد. آزمون دود فقط وقتی اجرا می‌شود که کد پایتون و پنل سالم باشند، چون ساخت ایمیج‌ها گران‌ترین مرحله است.*


آزمون دود مهم‌ترین قسمت CI است: کل سیستم را همان‌طور که کاربر اجرا می‌کند بالا می‌آورد (`docker compose up`) و از بیرون بررسی می‌کند. خطای مایگریشن روز ۵ دقیقاً از همین نوع بود: همه‌ی تست‌های واحد سبز بودند و فقط `docker compose up` آن را نشان می‌داد. collector در CI اجرا نمی‌شود، چون TSETMC از سرورهای خارج از ایران در دسترس نیست. رفتار آن با پاسخ‌های ضبط‌شده تست می‌شود.



#### همه چیز از lockfile

`uv sync --frozen` و `npm ci`: CI دقیقاً همان نسخه‌هایی را نصب می‌کند که روی سیستم توسعه‌دهنده بوده است. hookهای pre-commit هم ruff، mypy و tsc را از همان lockfileها اجرا می‌کنند، پس ممکن نیست hook و CI درباره‌ی نسخه‌ی ruff اختلاف داشته باشند.

#### سریع برای بازخورد

کارها موازی‌اند و کش uv و npm فعال است. اگر push جدیدی روی همان شاخه بیاید، اجرای قبلی لغو می‌شود (`concurrency`).


## مقاوم‌سازی

جدول زیر رفتار سرویس را در برابر هر خرابی نشان می‌دهد. اصل کلی این است: **خرابی یک جزء نباید اجزای سالم را از کار بیندازد، و نباید بی‌صدا باشد.**

| خرابی | رفتار | کجا دیده می‌شود |
|---|---|---|
| TSETMC در دسترس نیست (VPN روشن، IP مسدود) | چرخه با وضعیت `failed` ثبت می‌شود و حلقه ادامه می‌دهد. بعد از ۳ چرخه‌ی ناموفق پیاپی **یک** خطا با راهنمای «VPN؟» لاگ می‌شود (نه یک خطا در هر دقیقه)، و هنگام بازگشت پیام «بازیابی شد» | لاگ collector، بخش `collector` در `/health` |
| یک endpoint جزئی خراب است (مثلاً NAV یک صندوق) | ردیف صندوق با پرچم `NAV_MISSING` نوشته می‌شود، وضعیت چرخه `partial` | کارت کیفیت داده در پنل |
| ClickHouse قطع است | API پاسخ **503** با `Retry-After: 10` می‌دهد، نه 500 و traceback. خطای SQL (باگ) همچنان 500 می‌ماند | پنل پیام خطا نشان می‌دهد و در تیک بعد دوباره تلاش می‌کند |
| Redis قطع است | کش و رویدادها غیرفعال می‌شوند (fail-open). API مستقیم از ClickHouse می‌خواند | لاگ هشدار ([ADR 0006](adr/0006-caching.md)) |
| حلقه‌ی collector گیر کرده است | فایل heartbeat موعدی را که خودش تعیین کرده بود رد می‌کند و healthcheck داکر `unhealthy` می‌شود | `docker compose ps` |
| `docker stop` وسط یک چرخه | سیگنال SIGTERM فقط خواب بین چرخه‌ها را قطع می‌کند. چرخه‌ی جاری کامل نوشته می‌شود (مهلت ۳۰ ثانیه) و بعد برنامه خارج می‌شود | لاگ `collector stopped` |
| راه‌اندازی بعد از بسته شدن بازار | تاریخچه تکمیل می‌شود و از آخرین جلسه یک عکس پایانی گرفته می‌شود ([ADR 0004](adr/0004-scheduling.md#بازبینی-روز-۵-راهاندازی-خارج-از-ساعات-بازار)) | پنل خالی نیست |

### دو نوع سلامت، عمداً جدا



#### زنده بودن حلقه (Docker)

`tsetmc-viewer healthcheck` فقط می‌پرسد: «آیا حلقه به قولش عمل کرده است؟» حلقه قبل از هر خواب یا چرخه، موعد ضربان بعدی را در یک فایل می‌نویسد. قطعی TSETMC حلقه را **ناسالم** نمی‌کند، چون restart کانتینر آن را درست نمی‌کند.

#### تازگی داده (API)

`/health` وضعیت collector را در بدنه‌ی پاسخ گزارش می‌دهد: `ok`، `stale` یا `idle`، همراه با تأخیر و تعداد شکست‌های پیاپی. کد HTTP فقط به دیتابیس بستگی دارد، چون سرویس `web` منتظر سالم بودن `api` است و collector خراب نباید پنل را هم از کار بیندازد.


```console
$ curl -s localhost:8000/health | jq
{
  "status": "ok",
  "clickhouse": true,
  "version": "0.1.0",
  "collector": {
    "state": "stale",
    "last_run": {"tick": "…T10:41:00+03:30", "finished_at": "…", "status": "failed"},
    "lag_seconds": 312,
    "failed_streak": 5
  }
}
```

## آزمون بار

`scripts/loadtest.py` چند کاربر مجازی می‌سازد که هر کدام مثل مرورگر، شش endpoint داشبورد را پشت سر هم و پیوسته درخواست می‌کنند. نتایج روی داده‌ی واقعی (۱۵۹ صندوق و ۴۰۰ روز تاریخچه)، یک پروسه‌ی uvicorn و ۲ هسته‌ی پردازنده، **با ClickHouse و مولد بار روی همان ماشین**:


<svg class="dg" viewBox="0 0 960 250" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="نتیجه‌ی آزمون بار: توان عملیاتی و زمان پاسخ در سه حالت کش">
  <style>
    :root {
      --bg:#f7fafb; --surface:#ffffff; --line:#9fb6bc; --text:#16303a; --muted:#5b7680;
      --src:#e9f3ee; --src-line:#58a37b; --core:#e3eff2; --core-line:#2c7486;
      --store:#fbf0dd; --store-line:#d98e1f; --serve:#efeaf7; --serve-line:#7a62b3;
      --arrow:#5b7680; --hot:#d98e1f;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg:#151f24; --surface:#1b272d; --line:#3c525a; --text:#e2ecef; --muted:#9ab0b7;
        --src:#16302a; --src-line:#5cc48a; --core:#15313a; --core-line:#4fb3c4;
        --store:#33291a; --store-line:#f0b04f; --serve:#262036; --serve-line:#a58ee0;
        --arrow:#8aa3ab; --hot:#f0b04f;
      }
    }
    .dg-bg   { fill: var(--bg); }
    text     { font-family: "Vazirmatn", "Segoe UI", Tahoma, sans-serif; fill: var(--text); direction: rtl; unicode-bidi: plaintext; }
    .t-title { font-size: 16px; font-weight: 700; }
    .t-body  { font-size: 13px; }
    .t-small { font-size: 11.5px; fill: var(--muted); }
    .t-mono  { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 10.5px; fill: var(--muted); direction: ltr; }
    .t-zone  { font-size: 11px; font-weight: 700; fill: var(--muted); letter-spacing: .02em; }
    .box     { fill: var(--surface); stroke: var(--line); stroke-width: 1.2; }
    .src     { fill: var(--src);   stroke: var(--src-line);   stroke-width: 1.4; }
    .core    { fill: var(--core);  stroke: var(--core-line);  stroke-width: 1.4; }
    .store   { fill: var(--store); stroke: var(--store-line); stroke-width: 1.4; }
    .serve   { fill: var(--serve); stroke: var(--serve-line); stroke-width: 1.4; }
    .zone    { fill: none; stroke: var(--line); stroke-width: 1; stroke-dasharray: 5 4; }
    .edge    { fill: none; stroke: var(--arrow); stroke-width: 1.5; }
    .edge.dash { stroke-dasharray: 5 4; }
    .edge.hot  { stroke: var(--hot); stroke-width: 2; }
    .arrowhead { fill: var(--arrow); }
    .arrowhead.hot { fill: var(--hot); }
    .bar-src   { fill: var(--src-line); }
    .bar-core  { fill: var(--core-line); }
    .bar-store { fill: var(--store-line); }
    .bar-serve { fill: var(--serve-line); }
    .grid-line { stroke: var(--line); stroke-width: 1; stroke-dasharray: 2 4; }
  </style>
  <rect class="dg-bg" x="0" y="0" width="960" height="250" rx="16"/>
  <!-- right panel: throughput, 20 users; 250 px = 349 req/s -->
  <text class="t-title" x="940" y="30" text-anchor="start">توان عملیاتی</text>
  <text class="t-small" x="940" y="50" text-anchor="start">درخواست در ثانیه، ۲۰ کاربر هم‌زمان (بیشتر بهتر)</text>
  <line class="grid-line" x1="790" y1="66" x2="790" y2="220"/>
  <text class="t-body" x="940" y="96" text-anchor="start">بدون کش</text>
  <rect class="bar-store" x="755" y="81" width="35" height="22" rx="4"/>
  <text class="t-body" x="733" y="97" text-anchor="middle">۴۹</text>
  <text class="t-body" x="940" y="146" text-anchor="start">کش Redis</text>
  <rect class="bar-core" x="587" y="131" width="203" height="22" rx="4"/>
  <text class="t-body" x="563" y="147" text-anchor="middle">۲۸۳</text>
  <text class="t-body" x="940" y="196" text-anchor="start">Redis و ETag</text>
  <text class="t-small" x="940" y="212" text-anchor="start">پاسخ ۳۰۴ بدون بدنه</text>
  <rect class="bar-core" x="540" y="181" width="250" height="22" rx="4"/>
  <text class="t-body" x="516" y="197" text-anchor="middle">۳۴۹</text>
  <!-- left panel: median latency, 1 user; 250 px = 37.2 ms -->
  <text class="t-title" x="460" y="30" text-anchor="start">زمان پاسخ</text>
  <text class="t-small" x="460" y="50" text-anchor="start">میانه برای یک کاربر، میلی‌ثانیه (کمتر بهتر)</text>
  <line class="grid-line" x1="310" y1="66" x2="310" y2="220"/>
  <text class="t-body" x="460" y="96" text-anchor="start">بدون کش</text>
  <rect class="bar-store" x="60" y="81" width="250" height="22" rx="4"/>
  <text class="t-body" x="36" y="97" text-anchor="middle">۳۷</text>
  <text class="t-body" x="460" y="146" text-anchor="start">کش Redis</text>
  <rect class="bar-core" x="280" y="131" width="30" height="22" rx="4"/>
  <text class="t-body" x="258" y="147" text-anchor="middle">۴٫۴</text>
  <text class="t-body" x="460" y="196" text-anchor="start">Redis و ETag</text>
  <rect class="bar-core" x="290" y="181" width="20" height="22" rx="4"/>
  <text class="t-body" x="268" y="197" text-anchor="middle">۲٫۹</text>
</svg>

*شکل ۲ — با کش، توان عملیاتی ۶ تا ۷ برابر و زمان پاسخ حدود ۱۰ برابر بهتر می‌شود. در حالت ETag، مرورگر پاسخ ۳۰۴ بدون بدنه می‌گیرد.*


| حالت | ۱ کاربر: میانه / p95 | ۲۰ کاربر: توان عملیاتی | ۲۰ کاربر: میانه / p95 |
|---|---|---|---|
| بدون کش (`REDIS_URL=`) | ۳۷ / ۶۶ ms | ۴۹ درخواست در ثانیه | ۳۷۲ / ۶۷۱ ms |
| کش Redis | ۴٫۴ / ۹٫۵ ms | ۲۸۳ درخواست در ثانیه | ۴۴ / ۲۱۴ ms |
| Redis و ETag | ۲٫۹ / ۴٫۶ ms | ۳۴۹ درخواست در ثانیه | ۳۴ / ۱۶۹ ms |

یک بار تازه شدن پنل شش درخواست است. پس یک پروسه‌ی API روی همین سخت‌افزار ضعیف، با کش، حدود **۳۵۰۰ پنل باز** را در هر دقیقه تازه می‌کند، و بار ClickHouse **مستقل از تعداد کاربران** است: در هر تیک، هر کلید فقط یک بار محاسبه می‌شود.

### دو یافته‌ی آزمون بار که کد را عوض کرد

> **۱. ازدحام روی کش (cache stampede)**
>
> در اولین اجرا با ۲۰ کاربر، ۵۶ درخواست cache miss شد، نه ۶. وقتی تیک جدیدی می‌رسد، همه‌ی پنل‌های باز هم‌زمان همان کلیدها را می‌خواهند و همه با هم به ClickHouse می‌روند. این اتفاق **هر دقیقه** تکرار می‌شد.
>
> **اصلاح:** در `api/cache.py` محاسبه‌ی کلیدهای ازدست‌رفته *single-flight* شد: اولین درخواست محاسبه می‌کند و بقیه منتظر همان نتیجه می‌مانند (`X-Cache: shared`). اگر محاسبه خطا بدهد، همه‌ی منتظرها همان خطا را می‌گیرند و چیزی کش نمی‌شود. نتیجه: ۶ محاسبه به‌جای ۵۶. تست: `test_concurrent_misses_compute_once`.

> **۲. یک پرس‌وجوی پنهان در هر درخواست**
>
> حتی پاسخ‌های کش‌شده و ۳۰۴ حدود ۱۱ تا ۱۴ میلی‌ثانیه طول می‌کشیدند. علت این بود که «آخرین جلسه» (پیش‌فرض `?date=`) **قبل از** رسیدن به کش، در هر درخواست از ClickHouse پرسیده می‌شد.
>
> **اصلاح:** آخرین جلسه فقط با یک تیک جدید عوض می‌شود، پس به‌ازای هر تیک (و حداکثر یک دقیقه) در حافظه نگه داشته می‌شود. شماره‌ی تیک هم فقط یک بار از Redis خوانده می‌شود. نتیجه: زمان پاسخ کش ۱۴٫۵ → ۴٫۴ ms و ۳۰۴ از ۱۱٫۴ → ۲٫۹ ms. با هر دو اصلاح، توان عملیاتی حالت کش از ۱۳۲ به ۲۸۳ درخواست در ثانیه رسید. تست: `test_session_date_is_memoised_per_tick`.

```bash
# تکرار آزمون (API روی :8000، یک بار با REDIS_URL= و یک بار با Redis)
uv run python scripts/loadtest.py --users 20 --seconds 20 --mode plain
uv run python scripts/loadtest.py --users 20 --seconds 20 --mode etag
```

## پاک‌سازی

- کلاینت فیپیران که در روز ۱ نوشته شده بود و بعد از روز ۲ استفاده نمی‌شد حذف شد ([منابع داده](02-data-sources.md)). کدی که اجرا نمی‌شود تست هم نمی‌شود، ولی خواننده‌ی کد باید آن را بفهمد.
- hook بررسی YAML در pre-commit روی `mkdocs.yml` شکست می‌خورد (به‌خاطر تگ `!!python`)، یعنی هر commit توسعه‌دهنده را متوقف می‌کرد. حالا فقط syntax بررسی می‌شود. پاسخ‌های ضبط‌شده‌ی API و فایل‌های فونت از hookهای ویرایشگر مستثنا شدند تا بایت‌به‌بایت دست‌نخورده بمانند.
- `uv sync` (یعنی `make install`) حالا ابزار مستندات را هم نصب می‌کند (`default-groups`). بدون آن، `make docs` روی یک clone تازه شکست می‌خورد. ایمیج سرویس با `--no-default-groups` ساخته می‌شود، پس ابزار توسعه و مستندات وارد ایمیج تولیدی نمی‌شوند.
