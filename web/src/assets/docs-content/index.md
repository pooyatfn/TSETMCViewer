
# TSETMCViewer

دریافت لحظه‌ای، پاک‌سازی، ذخیره‌سازی و تحلیل **صندوق‌های سرمایه‌گذاری قابل معامله‌ی سهامی** بورس و فرابورس تهران. هدف ساختن تصویری کلی از این بازار است، برای معامله‌گر و مدیر پرتفوی.

*هر ۶۰ ثانیه · ClickHouse · FastAPI · React + ECharts · Docker · Python 3.12 · asyncio*

[شروع از معماری](01-architecture.md)
[اجرای سرویس](08-runbook.md)


## این سرویس چه می‌کند؟



#### دریافت دقیقه‌ای

در ساعات بازار، هر دقیقه قیمت، حجم، سفارش‌ها، معاملات حقیقی/حقوقی و NAV همه‌ی صندوق‌های سهامی از TSETMC دریافت می‌شود.

#### کنترل کیفیت

پس از هر دریافت، کامل بودن و درستی داده بررسی می‌شود. هر مشکل یا اصلاح می‌شود یا پرچم می‌خورد، و هیچ اصلاحی بی‌صدا انجام نمی‌شود.

#### غنی‌سازی

داده‌ی خام به شاخص‌هایی مثل حباب، ورود پول حقیقی، بازده و گردش معاملات تبدیل می‌شود.

#### تصویر بزرگ

نمودارهای پنل برای این ساخته شده‌اند که در چند ثانیه نشان دهند پول کجا می‌رود، کدام صندوق گران است و وضع کلی بازار صندوق‌ها چیست.



![پنل](assets/screens/overview-light.webp)

*پنل کاربری روی داده‌ی واقعی پایان جلسه‌ی ۱ مهر ۱۴۰۵. توضیح هر نمودار در [پنل و نمودارها](06-dashboard.md) آمده است.*



- **۱۵۹** — صندوق سهامی، بخشی، شاخصی و اهرمی زیر نظر
- **۱۰** — بررسی کیفیت و ۱۳ پرچم روی هر ردیف دقیقه‌ای
- **۲٫۹ میلی‌ثانیه** — زمان پاسخ API با کش (۳۴۹ درخواست در ثانیه)
- **۲۳۶** — تست خودکار، پوشش ۸۹٪، CI با آزمون دود Docker


## الزامات پروژه و جای پاسخ هر کدام

| # | الزام | کجا پیاده شده | کجا توضیح داده شده |
|:-:|---|---|---|
| ۱ | دریافت لحظه‌ای هر یک دقیقه برای همه‌ی صندوق‌های سهامی | `collector/service.py`، `pipeline/universe.py` | [معماری](01-architecture.md)، [ADR 0004](adr/0004-scheduling.md)، [ADR 0007](adr/0007-fund-identity.md) |
| ۲ | ذخیره پس از هر دریافت | `storage/`، مایگریشن‌های `0001`–`0004` | [مدل داده](03-data-model.md)، [ADR 0001](adr/0001-clickhouse.md)، [ADR 0003](adr/0003-raw-first-ingestion.md) |
| ۳ | بررسی کامل بودن و صحت، و پیش‌پردازش | `pipeline/validate.py`، `domain/quality.py` | [کیفیت داده](04-data-quality.md) |
| ۴ | شناسایی داده‌ی ارائه‌دهنده، ساخت داده‌ی پایه‌ی تکمیلی و مرحله‌ی اضافه شدن هر کدام | `pipeline/transform.py`، `pipeline/history.py`، `domain/metrics.py` | [منابع داده](02-data-sources.md)، [منطق مالی](05-financial-logic.md) |
| ۵ | پنل کاربری برای داده‌ی دریافتی و پردازش‌شده | `web/` (جدول صندوق‌ها، صفحه‌ی هر صندوق، کارت کیفیت) | [پنل و نمودارها](06-dashboard.md) |
| ۶ | نمودارهای تحلیلی برای تصویر بزرگ | `web/src/charts/options.ts` | [پنل و نمودارها](06-dashboard.md) |
| — | Docker و اجرا در هر محیط | `docker-compose.yml`، `docker/` | [اجرا و عملیات](08-runbook.md) |
| — | کیفیت کد و ساختار مخزن | `tests/`، `.github/workflows/ci.yml` | [آزمون و مقاوم‌سازی](09-quality-engineering.md) |
| — | پایش، هشدار و در دسترس بودن | `telemetry.py`، `monitoring/`، `collector/leadership.py` | [پایش و هشدار](11-monitoring.md)، [ADR 0009](adr/0009-observability.md)، [ADR 0010](adr/0010-high-availability.md) |

## از کجا شروع کنم؟



#### ارزیاب فنی

[معماری](01-architecture.md) ← [تصمیم‌های فنی](adr/index.md) ← [آزمون و مقاوم‌سازی](09-quality-engineering.md) ← [محدودیت‌ها](10-limitations.md). بخش‌های «بازبینی روز N» در ADRها نشان می‌دهند کجا تصمیمی با داده‌ی واقعی عوض شد.

#### معامله‌گر و مدیر پرتفوی

[پنل و نمودارها](06-dashboard.md) (روال یک‌دقیقه‌ای خواندن پنل) ← [منطق مالی](05-financial-logic.md) (تعریف هر عدد و یافته‌ی اهرمی‌ها) ← [کیفیت داده](04-data-quality.md).

#### توسعه‌دهنده

[اجرا و عملیات](08-runbook.md) ← [مدل داده](03-data-model.md) ← [API](07-api.md) ← [منابع داده](02-data-sources.md).

#### اجراکننده‌ی سرویس

[اجرا و عملیات](08-runbook.md): VPN و شبکه، راه‌اندازی خارج از ساعات بازار، تعطیلات و عیب‌یابی ← [پایش و هشدار](11-monitoring.md): داشبوردها، هشدار در «بله» و راهنمای رفع هر هشدار.


## معماری در یک نگاه


<svg class="dg" viewBox="0 0 960 436" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="معماری کلی سرویس">
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

*جریان داده از راست به چپ: منبع ← دریافت و پردازش ← ذخیره‌سازی ← API و کش ← پنل. رویداد «تیک جدید» (خط نارنجی) کش را باطل می‌کند و داده‌ی تازه را به پنل می‌فرستد.*


## نقشه‌ی مستندات



#### [معماری](01-architecture.md)

اجزای سیستم، اصول طراحی و جریان یک چرخه‌ی دریافت.

#### [منابع داده](02-data-sources.md)

چه داده‌ای را ارائه‌دهنده می‌دهد، چه چیزی را ما می‌سازیم و در کدام مرحله. همراه با اندازه‌گیری واقعی endpointها.

#### [مدل داده](03-data-model.md)

جدول‌ها، کلیدها، موتورهای ClickHouse و پرچم‌های کیفیت.

#### [کیفیت داده](04-data-quality.md)

ده بررسی در هر چرخه، روش اصلاح هر کدام و دلیل انتخاب آن.

#### [منطق مالی](05-financial-logic.md)

حباب، خالص دارایی، ورود پول حقیقی، بازده‌ها. همراه با یافته‌ی NAV صندوق‌های اهرمی.

#### [پنل و نمودارها](06-dashboard.md)

هر نمودار به کدام سؤال معامله‌گر و مدیر پرتفوی جواب می‌دهد، و چرا این شکل و این رنگ.

#### [API](07-api.md)

endpointها، قرارداد پاسخ، هدرهای کش و رویدادهای زنده.

#### [تصمیم‌های فنی (ADR)](adr/index.md)

هر انتخاب مهم با زمینه، گزینه‌های ردشده و پیامدهایش.

#### [اجرا و عملیات](08-runbook.md)

اجرا با Docker، نکات شبکه (VPN)، پایش و عیب‌یابی.

#### [آزمون و مقاوم‌سازی](09-quality-engineering.md)

راهبرد تست، CI با آزمون دود، رفتار در برابر خرابی‌ها و آزمون بار کش.

#### [پایش و هشدار](11-monitoring.md)

Prometheus، چهار داشبورد Grafana، ۱۶ هشدار با تست واحد و رساندن هشدار به «بله»؛ راهنمای رفع هر هشدار.

#### [محدودیت‌ها و گام‌های بعدی](10-limitations.md)

آنچه سرویس نمی‌داند یا نمی‌کند، و ترتیب پیشنهادی کامل کردن آن.


## وضعیت پیشرفت

| روز | محدوده | وضعیت |
|:---:|---|:---:|
| ۱ | اسکلت مخزن، Docker، طرح‌واره‌ی ClickHouse، کلاینت‌های API، دریافت خام | <span class="pill done">انجام شد</span> |
| ۲ | پارس پاسخ‌ها، فهرست صندوق‌ها، چرخه‌ی دقیقه‌ای کامل، replay | <span class="pill done">انجام شد</span> |
| ۳ | اعتبارسنجی و پیش‌پردازش، گزارش کیفیت | <span class="pill done">انجام شد</span> |
| ۴ | منطق مالی، تاریخچه، API، کش Redis و SSE | <span class="pill done">انجام شد</span> |
| ۵ | پنل و نمودارهای تحلیلی، کانتینر nginx | <span class="pill done">انجام شد</span> |
| ۶ | تست، CI، مقاوم‌سازی، آزمون بار | <span class="pill done">انجام شد</span> |
| ۷ | محور زمان چپ‌به‌راست، وضعیت collector در پنل، محدودیت‌ها، تکمیل مستندات | <span class="pill done">انجام شد</span> |
| + | تقویم تعطیلات، حباب وزنی و سری زمانی حباب، پایش با Grafana و هشدار، رهبری collector و چند worker برای API | <span class="pill done">انجام شد</span> |
