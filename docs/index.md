---
hide:
  - navigation
  - toc
---

<div class="hero" markdown>

# TSETMCViewer

دریافت لحظه‌ای، پاک‌سازی، ذخیره‌سازی و تحلیل **صندوق‌های سرمایه‌گذاری قابل معامله‌ی سهامی** بورس و فرابورس تهران. هدف ساختن تصویری کلی از این بازار است، برای معامله‌گر و مدیر پرتفوی.

<div class="hero-tags">
<span>هر ۶۰ ثانیه</span><span>ClickHouse</span><span>FastAPI</span><span>React + ECharts</span><span>Docker</span><span>Python 3.12 · asyncio</span>
</div>

[شروع از معماری](01-architecture.md){ .md-button .md-button--primary }
[اجرای سرویس](08-runbook.md){ .md-button }

</div>

## این سرویس چه می‌کند؟

<div class="grid cards two" markdown>

-   :material-clock-fast:{ .lg .middle } __دریافت دقیقه‌ای__

    ---

    در ساعات بازار، هر دقیقه قیمت، حجم، سفارش‌ها، معاملات حقیقی/حقوقی و NAV همه‌ی صندوق‌های سهامی از TSETMC دریافت می‌شود.

-   :material-shield-check-outline:{ .lg .middle } __کنترل کیفیت__

    ---

    پس از هر دریافت، کامل بودن و درستی داده بررسی می‌شود. هر مشکل یا اصلاح می‌شود یا پرچم می‌خورد، و هیچ اصلاحی بی‌صدا انجام نمی‌شود.

-   :material-database-cog-outline:{ .lg .middle } __غنی‌سازی__

    ---

    داده‌ی خام به شاخص‌هایی مثل حباب، ورود پول حقیقی، بازده و گردش معاملات تبدیل می‌شود.

-   :material-chart-box-outline:{ .lg .middle } __تصویر بزرگ__

    ---

    نمودارهای پنل برای این ساخته شده‌اند که در چند ثانیه نشان دهند پول کجا می‌رود، کدام صندوق گران است و وضع کلی بازار صندوق‌ها چیست.

</div>

<figure class="shot" markdown>
![پنل](assets/screens/overview-light.webp#only-light)
![پنل در پوسته‌ی تیره](assets/screens/overview-dark.webp#only-dark)
<figcaption markdown="span">پنل کاربری روی داده‌ی واقعی پایان جلسه‌ی ۱ مهر ۱۴۰۵. توضیح هر نمودار در [پنل و نمودارها](06-dashboard.md) آمده است.</figcaption>
</figure>

<div class="kpis">
  <div class="kpi"><b>۱۵۹</b><span>صندوق سهامی، بخشی، شاخصی و اهرمی زیر نظر</span></div>
  <div class="kpi"><b>۱۰</b><span>بررسی کیفیت و ۱۳ پرچم روی هر ردیف دقیقه‌ای</span></div>
  <div class="kpi"><b>۲٫۹ میلی‌ثانیه</b><span>زمان پاسخ API با کش (۳۴۹ درخواست در ثانیه)</span></div>
  <div class="kpi"><b>۲۳۶</b><span>تست خودکار، پوشش ۸۹٪، CI با آزمون دود Docker</span></div>
</div>

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

<div class="grid cards two" markdown>

-   :material-account-tie-outline: __ارزیاب فنی__

    ---

    [معماری](01-architecture.md) ← [تصمیم‌های فنی](adr/index.md) ← [آزمون و مقاوم‌سازی](09-quality-engineering.md) ← [محدودیت‌ها](10-limitations.md). بخش‌های «بازبینی روز N» در ADRها نشان می‌دهند کجا تصمیمی با داده‌ی واقعی عوض شد.

-   :material-chart-line: __معامله‌گر و مدیر پرتفوی__

    ---

    [پنل و نمودارها](06-dashboard.md) (روال یک‌دقیقه‌ای خواندن پنل) ← [منطق مالی](05-financial-logic.md) (تعریف هر عدد و یافته‌ی اهرمی‌ها) ← [کیفیت داده](04-data-quality.md).

-   :material-code-braces: __توسعه‌دهنده__

    ---

    [اجرا و عملیات](08-runbook.md) ← [مدل داده](03-data-model.md) ← [API](07-api.md) ← [منابع داده](02-data-sources.md).

-   :material-server-outline: __اجراکننده‌ی سرویس__

    ---

    [اجرا و عملیات](08-runbook.md): VPN و شبکه، راه‌اندازی خارج از ساعات بازار، تعطیلات و عیب‌یابی ← [پایش و هشدار](11-monitoring.md): داشبوردها، هشدار در «بله» و راهنمای رفع هر هشدار.

</div>

## معماری در یک نگاه

<figure class="diagram">
--8<-- "assets/diagrams/architecture.svg"
<figcaption>جریان داده از راست به چپ: منبع ← دریافت و پردازش ← ذخیره‌سازی ← API و کش ← پنل. رویداد «تیک جدید» (خط نارنجی) کش را باطل می‌کند و داده‌ی تازه را به پنل می‌فرستد.</figcaption>
</figure>

## نقشه‌ی مستندات

<div class="grid cards two" markdown>

-   :material-sitemap-outline: __[معماری](01-architecture.md)__

    اجزای سیستم، اصول طراحی و جریان یک چرخه‌ی دریافت.

-   :material-database-arrow-down-outline: __[منابع داده](02-data-sources.md)__

    چه داده‌ای را ارائه‌دهنده می‌دهد، چه چیزی را ما می‌سازیم و در کدام مرحله. همراه با اندازه‌گیری واقعی endpointها.

-   :material-table-large: __[مدل داده](03-data-model.md)__

    جدول‌ها، کلیدها، موتورهای ClickHouse و پرچم‌های کیفیت.

-   :material-shield-check-outline: __[کیفیت داده](04-data-quality.md)__

    ده بررسی در هر چرخه، روش اصلاح هر کدام و دلیل انتخاب آن.

-   :material-finance: __[منطق مالی](05-financial-logic.md)__

    حباب، خالص دارایی، ورود پول حقیقی، بازده‌ها. همراه با یافته‌ی NAV صندوق‌های اهرمی.

-   :material-chart-areaspline: __[پنل و نمودارها](06-dashboard.md)__

    هر نمودار به کدام سؤال معامله‌گر و مدیر پرتفوی جواب می‌دهد، و چرا این شکل و این رنگ.

-   :material-api: __[API](07-api.md)__

    endpointها، قرارداد پاسخ، هدرهای کش و رویدادهای زنده.

-   :material-scale-balance: __[تصمیم‌های فنی (ADR)](adr/index.md)__

    هر انتخاب مهم با زمینه، گزینه‌های ردشده و پیامدهایش.

-   :material-console: __[اجرا و عملیات](08-runbook.md)__

    اجرا با Docker، نکات شبکه (VPN)، پایش و عیب‌یابی.

-   :material-shield-bug-outline: __[آزمون و مقاوم‌سازی](09-quality-engineering.md)__

    راهبرد تست، CI با آزمون دود، رفتار در برابر خرابی‌ها و آزمون بار کش.

-   :material-chart-bell-curve: __[پایش و هشدار](11-monitoring.md)__

    Prometheus، چهار داشبورد Grafana، ۱۶ هشدار با تست واحد و رساندن هشدار به «بله»؛ راهنمای رفع هر هشدار.

-   :material-map-marker-path: __[محدودیت‌ها و گام‌های بعدی](10-limitations.md)__

    آنچه سرویس نمی‌داند یا نمی‌کند، و ترتیب پیشنهادی کامل کردن آن.

</div>

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
