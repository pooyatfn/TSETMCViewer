# معماری

<p class="lead">سیستم از چه اجزایی ساخته شده، داده در آن چطور جریان پیدا می‌کند و کدام اصول طراحی این ساختار را شکل داده‌اند.</p>


<svg class="dg" viewBox="0 0 960 436" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="معماری کلی سرویس">
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
  <rect class="dg-bg" x="0" y="0" width="960" height="436" rx="16"/>
  <defs>
    <marker id="arch-a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path class="arrowhead" d="M0,0 L10,5 L0,10 z"/>
    </marker>
    <marker id="arch-h" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path class="arrowhead hot" d="M0,0 L10,5 L0,10 z"/>
    </marker>
  </defs>
  <!-- zones (right → left: sources, ingest, store, serve, present) -->
  <rect class="zone" x="795" y="30" width="155" height="370" rx="14"/>
  <text class="t-zone" x="872" y="52" text-anchor="middle">منابع داده</text>
  <rect class="zone" x="560" y="30" width="220" height="370" rx="14"/>
  <text class="t-zone" x="670" y="52" text-anchor="middle">دریافت و پردازش</text>
  <rect class="zone" x="335" y="30" width="210" height="370" rx="14"/>
  <text class="t-zone" x="440" y="52" text-anchor="middle">ذخیره‌سازی</text>
  <rect class="zone" x="135" y="30" width="185" height="370" rx="14"/>
  <text class="t-zone" x="227" y="52" text-anchor="middle">ارائه</text>
  <rect class="zone" x="10" y="30" width="112" height="370" rx="14"/>
  <text class="t-zone" x="66" y="52" text-anchor="middle">کاربر</text>
  <!-- sources -->
  <rect class="src" x="808" y="80" width="130" height="118" rx="10"/>
  <text class="t-title" x="873" y="106" text-anchor="middle">TSETMC</text>
  <text class="t-small" x="873" y="124" text-anchor="middle">هر دقیقه</text>
  <text class="t-body" x="873" y="148" text-anchor="middle">دیده‌بان بازار</text>
  <text class="t-body" x="873" y="166" text-anchor="middle">حقیقی / حقوقی</text>
  <text class="t-body" x="873" y="184" text-anchor="middle">ارزش خالص (NAV)</text>
  <rect class="src" x="808" y="230" width="130" height="100" rx="10"/>
  <text class="t-title" x="873" y="256" text-anchor="middle">TSETMC</text>
  <text class="t-small" x="873" y="274" text-anchor="middle">روزانه، پیش از بازگشایی</text>
  <text class="t-body" x="873" y="298" text-anchor="middle">اطلاعات نماد</text>
  <text class="t-body" x="873" y="316" text-anchor="middle">نوع صندوق، تعداد واحد</text>
  <!-- collector -->
  <rect class="core" x="575" y="70" width="190" height="280" rx="12"/>
  <text class="t-title" x="670" y="96" text-anchor="middle">collector</text>
  <text class="t-small" x="670" y="113" text-anchor="middle">هم‌تراز با دقیقه · asyncio</text>
  <g class="t-body">
    <rect class="box" x="590" y="126" width="160" height="28" rx="7"/>
    <text x="670" y="145" text-anchor="middle">۱ – دریافت موازی</text>
    <rect class="box" x="590" y="162" width="160" height="28" rx="7"/>
    <text x="670" y="181" text-anchor="middle">۲ – ذخیره‌ی پاسخ خام</text>
    <rect class="box" x="590" y="198" width="160" height="28" rx="7"/>
    <text x="670" y="217" text-anchor="middle">۳ – پارس و فیلتر صندوق‌ها</text>
    <rect class="box" x="590" y="234" width="160" height="28" rx="7"/>
    <text x="670" y="253" text-anchor="middle">۴ – اعتبارسنجی و اصلاح</text>
    <rect class="box" x="590" y="270" width="160" height="28" rx="7"/>
    <text x="670" y="289" text-anchor="middle">۵ – نوشتن دسته‌ای</text>
    <rect class="box" x="590" y="306" width="160" height="28" rx="7"/>
    <text x="670" y="325" text-anchor="middle">۶ – اعلام «تیک جدید»</text>
  </g>
  <!-- ClickHouse -->
  <path class="store" d="M350,92 a90,16 0 0,1 180,0 v250 a90,16 0 0,1 -180,0 z"/>
  <path class="store" d="M350,92 a90,16 0 0,0 180,0"/>
  <text class="t-title" x="440" y="134" text-anchor="middle">ClickHouse</text>
  <text class="t-mono" x="440" y="162" text-anchor="middle">raw_snapshots</text>
  <text class="t-mono" x="440" y="182" text-anchor="middle">fund_ticks</text>
  <text class="t-mono" x="440" y="202" text-anchor="middle">funds · fund_daily</text>
  <text class="t-mono" x="440" y="222" text-anchor="middle">data_quality_log</text>
  <text class="t-mono" x="440" y="242" text-anchor="middle">collection_runs</text>
  <line class="grid-line" x1="370" y1="262" x2="510" y2="262"/>
  <text class="t-body" x="440" y="286" text-anchor="middle">Materialized Views</text>
  <text class="t-small" x="440" y="304" text-anchor="middle">تجمیع روزانه و درون‌روز</text>
  <!-- serve -->
  <rect class="serve" x="148" y="80" width="160" height="112" rx="10"/>
  <text class="t-title" x="228" y="108" text-anchor="middle">FastAPI</text>
  <text class="t-body" x="228" y="132" text-anchor="middle">REST + SSE</text>
  <text class="t-small" x="228" y="152" text-anchor="middle">اعتبارسنجی پاسخ با Pydantic</text>
  <text class="t-small" x="228" y="170" text-anchor="middle">مستندات خودکار Swagger</text>
  <rect class="serve" x="148" y="236" width="160" height="96" rx="10"/>
  <text class="t-title" x="228" y="264" text-anchor="middle">Redis</text>
  <text class="t-body" x="228" y="288" text-anchor="middle">کش پاسخ‌ها</text>
  <text class="t-small" x="228" y="308" text-anchor="middle">کانال رویداد «تیک جدید»</text>
  <!-- panel -->
  <rect class="box" x="20" y="120" width="92" height="150" rx="10"/>
  <text class="t-title" x="66" y="150" text-anchor="middle">پنل وب</text>
  <text class="t-small" x="66" y="172" text-anchor="middle">React</text>
  <text class="t-small" x="66" y="190" text-anchor="middle">ECharts</text>
  <rect x="34" y="208" width="10" height="40" rx="2" class="bar-core"/>
  <rect x="50" y="222" width="10" height="26" rx="2" class="bar-store"/>
  <rect x="66" y="200" width="10" height="48" rx="2" class="bar-src"/>
  <rect x="82" y="214" width="10" height="34" rx="2" class="bar-serve"/>
  <!-- edges -->
  <path class="edge" d="M808,139 L767,139" marker-end="url(#arch-a)"/>
  <path class="edge dash" d="M808,280 L767,280" marker-end="url(#arch-a)"/>
  <path class="edge" d="M575,210 L532,210" marker-end="url(#arch-a)"/>
  <path class="edge" d="M350,150 L310,150" marker-end="url(#arch-a)"/>
  <path class="edge" d="M148,195 L114,195" marker-end="url(#arch-a)"/>
  <path class="edge dash" d="M228,236 L228,194" marker-end="url(#arch-a)" marker-start="url(#arch-a)"/>
  <!-- tick event: collector → redis (hot) -->
  <path class="edge hot" d="M590,320 C 560,418 340,418 310,300" marker-end="url(#arch-h)"/>
  <text class="t-small" x="455" y="424" text-anchor="middle">رویداد تیک ← باطل‌شدن کش و push به پنل</text>
</svg>

*شکل ۱ — نمای کلی سرویس. جهت جریان داده از راست به چپ است.*


## اجزا

| سرویس | مسئولیت | چرخه‌ی عمر |
|---|---|---|
| `clickhouse` | ذخیره‌ی داده‌ی خام، تمیز، مرجع و تجمیعی | دائمی |
| `migrate` | ساخت دیتابیس و اعمال مایگریشن‌ها | یک بار اجرا می‌شود؛ بقیه منتظر پایان موفق آن می‌مانند |
| `collector` | دریافت، ذخیره‌ی خام، پارس، اعتبارسنجی، نوشتن، اعلام تیک | دائمی؛ خارج از ساعات بازار می‌خوابد |
| `api` | خواندن و ارائه‌ی داده، کش پاسخ‌ها، push به پنل | دائمی |
| `redis` | کش پاسخ‌ها و کانال رویداد تیک | دائمی |
| `web` | پنل کاربری روی پورت ۸۰۸۰: فایل‌های ایستای React پشت nginx، و پراکسی `/api` به API؛ تب «مستندات» همین‌جاست | دائمی |

> **یک ایمیج، چند فرمان**
>
> سه سرویس پایتونی (`migrate`، `collector` و `api`) از **یک ایمیج** ساخته می‌شوند و فقط فرمانشان فرق دارد (`tsetmc-viewer migrate | collect | api`). نتیجه: یک بار build، یک نسخه از کد و نبود ناسازگاری بین سرویس‌ها.

## اصول طراحی



#### جدایی انتقال از تفسیر

کلاینت‌ها فقط بایت و متادیتا برمی‌گردانند (`RawResponse`) و پارس یک مرحله‌ی جداست. پاسخ خام همیشه ذخیره می‌شود، پیش از هر فرضی درباره‌ی ساختارش. ([ADR 0003](adr/0003-raw-first-ingestion.md))

#### هر چرخه یک شناسه

هر اجرای collector یک `run_id` دارد. پاسخ‌های خام، ردیف‌های تمیز و یافته‌های کیفیت به آن گره می‌خورند، پس «داده‌ی ساعت ۱۰:۴۱ از کجا آمد؟» با یک کوئری جواب داده می‌شود.

#### Idempotency

جدول `fund_ticks` روی کلید `(ins_code, ts)` است. تکرار یک چرخه داده‌ی تکراری نمی‌سازد، و مایگریشن‌ها هم بارها قابل اجرا هستند.

#### شکست جزئی، نه کلی

اگر یک endpoint خطا بدهد، بقیه ذخیره می‌شوند و چرخه با وضعیت `partial` ثبت می‌شود. خطای برنامه‌نویسی عمداً بلعیده نمی‌شود تا دیده شود.

#### زمان آگاه از منطقه‌ی زمانی

همه‌ی زمان‌ها در پایتون و ClickHouse به وقت `Asia/Tehran` هستند. ایران از ۱۴۰۱ ساعت تابستانی ندارد و `zoneinfo` این را درست مدل می‌کند.

#### پیکربندی فقط از محیط

همه‌ی تنظیمات با `pydantic-settings` از متغیرهای محیطی خوانده و هنگام شروع اعتبارسنجی می‌شوند (12-factor).


## لایه‌های داده


<svg class="dg" viewBox="0 0 960 300" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="لایه‌های داده">
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
  <rect class="dg-bg" x="0" y="0" width="960" height="300" rx="16"/>
  <defs>
    <marker id="dl-a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path class="arrowhead" d="M0,0 L10,5 L0,10 z"/>
    </marker>
    <marker id="dl-h" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path class="arrowhead hot" d="M0,0 L10,5 L0,10 z"/>
    </marker>
  </defs>
  <!-- layer 1: raw -->
  <rect class="src" x="745" y="40" width="200" height="180" rx="12"/>
  <text class="t-small" x="845" y="64" text-anchor="middle">لایه‌ی ۱</text>
  <text class="t-title" x="845" y="86" text-anchor="middle">خام</text>
  <text class="t-mono" x="845" y="110" text-anchor="middle">raw_snapshots</text>
  <text class="t-body" x="845" y="140" text-anchor="middle">پاسخ دست‌نخورده‌ی منبع</text>
  <text class="t-small" x="845" y="162" text-anchor="middle">نگهداری ۳۰ روز · فشرده با ZSTD</text>
  <text class="t-small" x="845" y="182" text-anchor="middle">حسابرسی و بازپخش</text>
  <!-- layer 2: clean -->
  <rect class="core" x="505" y="40" width="200" height="180" rx="12"/>
  <text class="t-small" x="605" y="64" text-anchor="middle">لایه‌ی ۲</text>
  <text class="t-title" x="605" y="86" text-anchor="middle">تمیز</text>
  <text class="t-mono" x="605" y="110" text-anchor="middle">fund_ticks · data_quality_log</text>
  <text class="t-body" x="605" y="140" text-anchor="middle">فقط صندوق‌های سهامی، دقیقه‌ای</text>
  <text class="t-small" x="605" y="162" text-anchor="middle">اعتبارسنجی‌شده + پرچم کیفیت</text>
  <text class="t-small" x="605" y="182" text-anchor="middle">یکتا روی (صندوق، دقیقه)</text>
  <!-- layer 3: reference -->
  <rect class="box" x="505" y="235" width="200" height="50" rx="10"/>
  <text class="t-body" x="605" y="256" text-anchor="middle">مرجع: funds · fund_daily</text>
  <text class="t-small" x="605" y="274" text-anchor="middle">نوع صندوق، تعداد واحد، خالص دارایی</text>
  <!-- layer 4: aggregates -->
  <rect class="store" x="265" y="40" width="200" height="180" rx="12"/>
  <text class="t-small" x="365" y="64" text-anchor="middle">لایه‌ی ۳</text>
  <text class="t-title" x="365" y="86" text-anchor="middle">تحلیلی</text>
  <text class="t-mono" x="365" y="110" text-anchor="middle">Materialized Views</text>
  <text class="t-body" x="365" y="140" text-anchor="middle">حباب، ورود پول، بازده</text>
  <text class="t-small" x="365" y="162" text-anchor="middle">هنگام درج محاسبه می‌شود</text>
  <text class="t-small" x="365" y="182" text-anchor="middle">نه هنگام خواندن</text>
  <!-- consumer -->
  <rect class="serve" x="25" y="80" width="200" height="100" rx="12"/>
  <text class="t-title" x="125" y="115" text-anchor="middle">پنل و API</text>
  <text class="t-small" x="125" y="140" text-anchor="middle">فقط از لایه‌ی ۲ و ۳ می‌خوانند</text>
  <!-- edges -->
  <path class="edge" d="M745,130 L707,130" marker-end="url(#dl-a)"/>
  <path class="edge" d="M505,130 L467,130" marker-end="url(#dl-a)"/>
  <path class="edge dash" d="M605,235 L605,222" marker-end="url(#dl-a)"/>
  <path class="edge" d="M265,130 L227,130" marker-end="url(#dl-a)"/>
  <path class="edge hot" d="M800,40 C 780,22 650,22 630,38" marker-end="url(#dl-h)"/>
  <text class="t-small" x="715" y="13" text-anchor="middle">بازپخش پس از اصلاح پارسر</text>
</svg>

*شکل ۲ — داده از «خام» به «تمیز» و سپس «تحلیلی» می‌رسد. API هیچ‌وقت داده‌ی خام را نمی‌خواند.*


## لایه‌های کد

| ماژول | مسئولیت | نوع I/O |
|---|---|---|
| `config.py` | تنظیمات تایپ‌شده از متغیرهای محیطی | — |
| `clock.py` | «الان بازار باز است؟» و هم‌ترازی با مرز دقیقه | — |
| `sources/` | کلاینت‌های HTTP: `http.py` (retry، backoff، semaphore)، `tsetmc.py` | شبکه |
| `collector/` | ارکستراسیون یک چرخه و حلقه‌ی دائمی | — |
| `storage/` | اتصال ClickHouse، مایگریشن‌ها، repository | دیتابیس |
| `api/` | لایه‌ی ارائه: `app.py`، `deps.py`، `routes/` | HTTP |

وابستگی‌ها فقط در یک جهت‌اند: `api` و `collector` به `storage` و `sources` وابسته‌اند، نه برعکس. `collector` به یک `Protocol` (`RunSink`) وابسته است، نه به کلاس مشخص، پس بدون دیتابیس و با یک پیاده‌سازی درون‌حافظه تست می‌شود.

## یک چرخه‌ی دریافت


<svg class="dg" viewBox="0 0 960 360" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="بودجه‌ی زمانی یک چرخه‌ی دقیقه‌ای">
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
  <rect class="dg-bg" x="0" y="0" width="960" height="360" rx="16"/>
  <!-- axis: t=0 at x=780, t=60s at x=120 → 11 px per second (RTL) -->
  <text class="t-title" x="940" y="30" text-anchor="start">یک چرخه در ۶۰ ثانیه (اندازه‌گیری واقعی، ۲ مهر ۱۴۰۵)</text>
  <g>
    <line class="grid-line" x1="780" y1="50" x2="780" y2="300"/>
    <line class="grid-line" x1="670" y1="50" x2="670" y2="300"/>
    <line class="grid-line" x1="560" y1="50" x2="560" y2="300"/>
    <line class="grid-line" x1="450" y1="50" x2="450" y2="300"/>
    <line class="grid-line" x1="340" y1="50" x2="340" y2="300"/>
    <line class="grid-line" x1="230" y1="50" x2="230" y2="300"/>
    <line class="grid-line" x1="120" y1="50" x2="120" y2="300"/>
    <text class="t-small" x="780" y="318" text-anchor="middle">۰ ث</text>
    <text class="t-small" x="670" y="318" text-anchor="middle">۱۰</text>
    <text class="t-small" x="560" y="318" text-anchor="middle">۲۰</text>
    <text class="t-small" x="450" y="318" text-anchor="middle">۳۰</text>
    <text class="t-small" x="340" y="318" text-anchor="middle">۴۰</text>
    <text class="t-small" x="230" y="318" text-anchor="middle">۵۰</text>
    <text class="t-small" x="120" y="318" text-anchor="middle">۶۰ ث</text>
  </g>
  <!-- lanes -->
  <text class="t-body" x="940" y="80" text-anchor="start">دیده‌بان بازار با gzip</text>
  <text class="t-small" x="940" y="95" text-anchor="start">۶۱۰ کیلوبایت، ۳۸۴۵ نماد</text>
  <rect class="bar-src" x="769" y="70" width="11" height="22" rx="5"/>
  <text class="t-body" x="758" y="86" text-anchor="start">۱٫۰ ث</text>
  <text class="t-body" x="940" y="125" text-anchor="start">دیده‌بان نسخه‌ی قدیمی</text>
  <text class="t-small" x="940" y="140" text-anchor="start">۴۲۵ کیلوبایت gzip</text>
  <rect class="bar-src" x="762" y="115" width="18" height="22" rx="5"/>
  <text class="t-body" x="750" y="131" text-anchor="start">۱٫۷ ث</text>
  <text class="t-body" x="940" y="170" text-anchor="start">حقیقی/حقوقی همه</text>
  <rect class="bar-src" x="756" y="160" width="24" height="22" rx="5"/>
  <text class="t-body" x="744" y="176" text-anchor="start">۲٫۲ ث</text>
  <text class="t-body" x="940" y="215" text-anchor="start">خالص ارزش دارایی (NAV)</text>
  <text class="t-small" x="940" y="230" text-anchor="start">~۱۶۰ درخواست، ۸ هم‌زمان</text>
  <rect class="bar-src" x="670" y="205" width="110" height="22" rx="5"/>
  <text class="t-body" x="658" y="221" text-anchor="start">≈ ۱۰ ث (تخمین)</text>
  <text class="t-body" x="940" y="265" text-anchor="start">ذخیره و پردازش</text>
  <rect class="bar-core" x="758" y="255" width="22" height="22" rx="5"/>
  <text class="t-body" x="748" y="271" text-anchor="start">&lt; ۲ ث</text>
  <!-- slack -->
  <rect x="130" y="112" width="440" height="80" rx="12" fill="none" class="zone"/>
  <text class="t-title" x="350" y="148" text-anchor="middle">حاشیه‌ی امن ≈ ۴۵ ثانیه</text>
  <text class="t-small" x="350" y="172" text-anchor="middle">برای retry، کندی TSETMC و رشد تعداد صندوق‌ها</text>
</svg>

*شکل ۳ — بودجه‌ی زمانی یک چرخه بر اساس اندازه‌گیری واقعی. با فشرده‌سازی gzip دیده‌بان کل بازار حدود ۱ ثانیه طول می‌کشد و بیشترین زمان صرف درخواست‌های NAV می‌شود (<a href="adr/0006-caching.md">ADR 0006، بازبینی روز ۴</a>).*


1. `tick` = زمان جاری گردشده به دقیقه. همه‌ی صندوق‌ها یک برچسب زمانی مشترک می‌گیرند.
2. دریافت موازی endpointهای تجمیعی (دیده‌بان بازار، حقیقی/حقوقی) و NAV هر صندوق، با سقف هم‌زمانی.
3. ذخیره‌ی پاسخ‌های خام در `raw_snapshots`.
4. پارس ← فیلتر به فهرست صندوق‌های سهامی ← اعتبارسنجی ← اصلاح یا پرچم‌گذاری.
5. نوشتن دسته‌ای در `fund_ticks` و `data_quality_log`.
6. ثبت `collection_runs` و انتشار رویداد «تیک N».

> **وضعیت پیاده‌سازی**
>
> - [x] ذخیره‌ی خام و ثبت چرخه — روز ۱
> - [x] فهرست روزانه‌ی صندوق‌ها، NAV هر صندوق، پارس، ساخت تیک، `market_ticks` — روز ۲
> - [x] `replay`: بازسازی تیک‌های یک روز از داده‌ی خام — روز ۲
> - [x] اعتبارسنجی و اصلاح، گزارش کیفیت — روز ۳
> - [x] تاریخچه‌ی روزانه، منطق مالی، API، انتشار تیک، کش Redis و SSE — روز ۴
