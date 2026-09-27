# تصمیم‌های فنی (ADR)

<p class="lead">هر تصمیم مهم معماری در یک سند کوتاه ثبت می‌شود: زمینه، تصمیم، گزینه‌هایی که رد شدند و پیامدها. این اسناد به مرور بازنویسی نمی‌شوند. اگر تصمیمی عوض شود، یک ADR جدید جای قبلی را می‌گیرد.</p>

<div class="grid cards two" markdown>

-   :material-database: __[0001 · ClickHouse](0001-clickhouse.md)__

    چرا پایگاه داده‌ی ستونی و نه PostgreSQL/TimescaleDB؛ موتورهای `MergeTree` و هزینه‌ی نداشتن تراکنش.

-   :material-language-python: __[0002 · پایتون async](0002-python-async-stack.md)__

    asyncio، httpx و FastAPI برای کاری که تقریباً کاملاً I/O-bound است.

-   :material-archive-outline: __[0003 · اول داده‌ی خام](0003-raw-first-ingestion.md)__

    پاسخ منبع پیش از پارس ذخیره می‌شود، چون داده‌ی درون‌روز قابل بازیابی نیست.

-   :material-timer-outline: __[0004 · زمان‌بندی دقیقه‌ای](0004-scheduling.md)__

    حلقه‌ی هم‌تراز با ساعت دیواری به‌جای APScheduler یا Celery.

-   :material-source-branch: __[0005 · مایگریشن](0005-migrations.md)__

    فایل‌های SQL شماره‌دار با checksum به‌جای Alembic.

-   :material-lightning-bolt-outline: __[0006 · کش](0006-caching.md)__

    شش لایه‌ی کش و باطل‌سازی با رویداد تیک.

-   :material-card-account-details-outline: __[0007 · هویت صندوق](0007-fund-identity.md)__

    تابلوی اصلی، تابلوهای فرعی و اختیار معامله‌ها: کدام نماد «صندوق» است؟

-   :material-monitor-dashboard: __[0008 · پنل وب](0008-web-panel.md)__

    React + Vite + ECharts بدون router و state manager؛ nginx هم‌مبدأ با API.

-   :material-chart-bell-curve: __[0009 · پایش](0009-observability.md)__

    Prometheus، Grafana و Alertmanager؛ relay فارسی برای بله و تلگرام؛ قواعد هشدار با تست واحد.

-   :material-server-network: __[0010 · در دسترس بودن](0010-high-availability.md)__

    رهبری collector با lease در Redis؛ چند worker برای API با single-flight توزیع‌شده.

-   :material-database-sync-outline: __[0011 · ریپلیکای ClickHouse](0011-clickhouse-replication.md)__

    دو نسخه‌ی `ReplicatedMergeTree` با یک Keeper، اختیاری؛ و چرا این هنوز HA واقعی نیست.

-   :material-history: __[0012 · بازسازی دقیقه‌های جاافتاده](0012-intraday-backfill.md)__

    ریز معاملات امروز، بررسی‌شده با تیک‌های زنده، در جدولی جدا؛ فقط قیمت و حجم.

-   :material-calendar-clock: __[0013 · بازسازی جلسه‌های گذشته](0013-session-backfill.md)__

    تاریخچه‌ی قیمت (نه ریز معاملات) برای ۵ روز گذشته، بررسی‌شده با رقم رسمی پایان‌روز.

</div>

## قالب

```text
# ADR NNNN — عنوان
وضعیت · تاریخ
زمینه      ← چه مسئله‌ای و چه محدودیت‌هایی
تصمیم      ← چه چیزی انتخاب شد
گزینه‌های ردشده ← و چرا
پیامدها    ← مزایا (➕)، هزینه‌ها (➖) و ریسک‌ها (⚠️)
```
