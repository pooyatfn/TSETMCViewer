# اجرا و عملیات

<p class="lead">نصب، اجرا، پایش و عیب‌یابی سرویس. همه‌چیز با Docker Compose اجرا می‌شود و روی هر محیطی که Docker دارد بالا می‌آید.</p>

## پیش‌نیازها

| ابزار | نسخه | برای |
|---|---|---|
| Docker Engine | 24 به بالا | اجرای همه‌ی سرویس‌ها |
| Docker Compose | 2.24 به بالا | `env_file` اختیاری و `depends_on` شرطی |
| [uv](https://docs.astral.sh/uv/) | 0.8 به بالا | فقط برای توسعه‌ی محلی؛ پایتون ۳.۱۲ را خودش نصب می‌کند |

## شبکه: VPN و TSETMC

!!! danger "مهم‌ترین نکته‌ی اجرا در ایران"
    دو محدودیت خلاف جهت هم وجود دارد. **ساخت** ایمیج به اینترنت بین‌الملل نیاز دارد، اما **اجرا** به IP ایران.

| مقصد | از داخل ایران | با VPN خارجی |
|---|:---:|:---:|
| Docker Hub (ایمیج‌ها) | :material-close-circle:{ style="color: var(--bad)" } معمولاً مسدود | :material-check-circle:{ style="color: var(--ok)" } |
| PyPI و npm (هنگام build) | :material-check-circle:{ style="color: var(--ok)" } گاهی کند | :material-check-circle:{ style="color: var(--ok)" } |
| **TSETMC** | :material-check-circle:{ style="color: var(--ok)" } | :material-close-circle:{ style="color: var(--bad)" } IP خارجی رد می‌شود |

```text
۱. VPN روشن  →  docker compose build && docker compose pull
۲. VPN خاموش →  docker compose up -d
```

!!! tip "split tunneling"
    اگر VPN از split tunneling پشتیبانی می‌کند، دامنه‌ی `tsetmc.com` را از تونل مستثنا کنید تا نیازی به خاموش کردن VPN نباشد. اگر TSETMC فقط از طریق یک پراکسی داخلی در دسترس است، `HTTPS_PROXY` را در `.env` تنظیم کنید. httpx آن را رعایت می‌کند.

## اجرا

=== "Docker (پیشنهادی)"

    ```bash
    cp .env.example .env            # در صورت نیاز رمز ClickHouse را عوض کنید
    docker compose up -d --build
    docker compose ps               # migrate باید Exited (0) باشد
    curl localhost:8000/health      # {"status":"ok","clickhouse":true,...}
    ```

    | آدرس | سرویس |
    |---|---|
    | <http://localhost:8080> | **پنل کاربری** (تب «مستندات» شامل خلاصه‌ی همین اسناد است) |
    | <http://localhost:8000/docs> | مستندات تعاملی API (Swagger) |
    | <http://localhost:8123/play> | کنسول کوئری ClickHouse |

    **پنل از همان اولین اجرا خالی نیست.** اگر `collector` خارج از ساعات بازار شروع شود (VPN خاموش)، خودش این کارها را انجام می‌دهد:

    1. تاریخچه‌ی رسمی روزانه را تا آخرین جلسه بارگذاری می‌کند: ۴۰۰ روز در دیتابیس خالی (`HISTORY_MAX_DAYS`)، و در دفعات بعد فقط روزهای جاافتاده.
    2. اگر از آخرین جلسه هیچ داده‌ی دقیقه‌ای نیست، یک **عکس پایانی** (closing snapshot) از آن جلسه می‌گیرد، با برچسب زمانی ساعت بسته شدن همان جلسه.

    این کار حدود یک تا دو دقیقه طول می‌کشد. پیشرفت آن را با `docker compose logs -f collector` ببینید (پیام `bootstrap done`). برای اجرای دستی:

    ```bash
    docker compose run --rm collector bootstrap
    ```

    اگر کالکتور در ساعات بازار شروع شود، این مرحله انجام نمی‌شود: چرخه‌های زنده بلافاصله شروع می‌شوند و تاریخچه نیم ساعت بعد از بسته شدن بازار بارگذاری می‌شود.

=== "توسعه‌ی محلی"

    ```bash
    make install                    # uv sync + pre-commit
    docker compose up -d clickhouse migrate
    uv run tsetmc-viewer collect-once
    uv run tsetmc-viewer api --port 8000
    uv run mkdocs serve             # مستندات روی :8000 با بارگذاری خودکار
    ```

## فرمان‌ها

همه‌ی فرمان‌ها هم با `uv run tsetmc-viewer …` و هم در Docker با `docker compose run --rm collector …` اجرا می‌شوند.

| فرمان | کار |
|---|---|
| `migrate` | ساخت دیتابیس و اعمال مایگریشن‌ها |
| `sync-funds` | ساخت فهرست امروز صندوق‌ها و چاپ آن به تفکیک نوع |
| `collect` | حلقه‌ی دائمی: همگام‌سازی پیش از بازگشایی و یک چرخه در هر دقیقه |
| `collect-once` | یک چرخه‌ی فوری |
| `replay --date 2026-09-26` | بازسازی `fund_ticks` یک روز از `raw_snapshots` (پس از اصلاح پارسر) |
| `quality --date 2026-09-26` | گزارش کیفیت داده‌ی یک روز: کامل بودن، پرچم‌ها و رخدادها |
| `bootstrap` | خارج از ساعات بازار: تاریخچه تا آخرین جلسه + عکس پایانی آن جلسه اگر داده‌ی دقیقه‌ای ندارد (collector هنگام شروع خودش اجرا می‌کند) |
| `backfill-intraday` | بازسازی دقیقه‌های امروز پیش از روشن شدن collector از ریز معاملات (collector خودش پس از سومین چرخه اجرا می‌کند؛ [ADR 0012](adr/0012-intraday-backfill.md)). :warning: VPN خاموش |
| `backfill-sessions [--through DAY] [--days N]` | بازسازی دقیقه‌های `N` روز معاملاتی اخیر (پیش‌فرض `SESSION_BACKFILL_DAYS`) تا و شامل `--through` از تاریخچه‌ی قیمت (collector خودش در bootstrap اجرا می‌کند؛ [ADR 0013](adr/0013-session-backfill.md)). خروجی هر `BackfillReport` را چاپ می‌کند؛ `rejected_symbols` نشان می‌دهد کدام صندوق با رقم رسمی نخوانده. :warning: VPN خاموش |
| `backfill --days N` | بارگذاری دوباره‌ی تاریخچه‌ی رسمی روزانه با پنجره‌ی دلخواه (پیش‌فرض `HISTORY_MAX_DAYS`) |
| `api` | اجرای API |
| `healthcheck` | کد خروج ۰ اگر حلقه‌ی collector زنده است (healthcheck داکر) |
| `alert-relay` | رساندن هشدارهای Alertmanager به بله، تلگرام یا webhook |
| `api --workers N` | API با N پروسه (پیش‌فرض `API_WORKERS`) |

خارج از ساعات بازار (شنبه تا چهارشنبه، ۹:۰۰ تا ۱۲:۳۰) collector می‌خوابد. برای آزمایش:

```bash
make collect-once                                          # یک چرخه‌ی فوری
COLLECT_IGNORE_MARKET_HOURS=true docker compose up -d collector   # دریافت دائمی
```

## پایش

برای داشبورد و هشدار، profile پایش را هم بالا بیاورید (Grafana روی <http://localhost:3000>). راه‌اندازی، گرفتن هشدار در بله و راهنمای رفع هر هشدار در [پایش و هشدار](11-monitoring.md) آمده است:

```bash
docker compose --profile monitoring up -d
```

بدون آن هم ابزارهای زیر در دسترس‌اند:

```bash
docker compose ps                                    # collector: healthy = حلقه زنده است
curl -s localhost:8000/health | jq .collector        # ok / stale / idle + تأخیر و شکست‌های پیاپی
make logs                                            # لاگ JSON از collector و api
curl 'localhost:8000/api/v1/pipeline/runs?limit=10'  # آخرین چرخه‌ها
```

دو نوع سلامت عمداً از هم جدا هستند ([جزئیات](09-quality-engineering.md#دو-نوع-سلامت-عمدا-جدا)): «حلقه زنده است» (داکر) و «داده تازه است» (`/health`). بعد از ۳ چرخه‌ی ناموفق پیاپی، collector **یک** پیام `collector failing` در سطح ERROR لاگ می‌کند و هنگام بازگشت، پیام `collector recovered`.

??? example "کوئری‌های مفید ClickHouse"

    ```sql
    -- سلامت چرخه‌ها در یک ساعت اخیر
    SELECT status, count(), avg(dateDiff('millisecond', started_at, finished_at)) AS avg_ms
    FROM collection_runs WHERE started_at > now() - INTERVAL 1 HOUR GROUP BY status;

    -- تأخیر و نرخ خطای هر endpoint
    SELECT endpoint, count(), countIf(status_code != 200) AS errors,
           quantile(0.95)(latency_ms) AS p95_ms
    FROM raw_snapshots WHERE fetched_at > now() - INTERVAL 1 DAY GROUP BY endpoint;
    ```

## تقویم و تعطیلات

- تعطیلات رسمی ۱۴۰۵ و تعطیلات شمسی هر سال در `src/tsetmc_viewer/domain/calendar.py` هستند. فهرست یک سال را از API ببینید: `curl localhost:8000/api/v1/calendar?year=1405`.
- **تعطیلی اعلام‌شده توسط بورس** (مثلاً تعطیلی ناگهانی): در `.env` بنویسید `MARKET_EXTRA_HOLIDAYS={"2026-10-05": "دلیل"}` و collector را restart کنید.
- **تعطیلی اعلام‌نشده:** لازم نیست کاری بکنید. اگر تا ۲۰ دقیقه پس از بازگشایی معامله‌ای ثبت نشود، collector آن روز را تعطیل ثبت می‌کند و تا جلسه‌ی بعد می‌خوابد (`MARKET_SESSION_GUARD_MINUTES`).
- **سال جدید:** در ابتدای هر سال شمسی، تعطیلات قمری آن سال را از تقویم رسمی به `LUNAR_HOLIDAYS` اضافه کنید. تا آن موقع، نگهبان جلسه روزهای تعطیل را از رفتار بازار تشخیص می‌دهد و collector در لاگ یک هشدار ثبت می‌کند.

## چند نمونه

در compose دو collector اجرا می‌شود (`COLLECTOR_REPLICAS`) و فقط یکی رهبر است ([ADR 0010](adr/0010-high-availability.md)). نمونه‌ی رهبر را از لاگ (`leadership acquired`) یا از داشبورد «دریافت داده» پیدا کنید. برای آزمایش جابه‌جایی رهبر:

```bash
docker compose stop collector && docker compose up -d collector   # یا یک نمونه را kill کنید
docker compose logs collector | grep leadership
```

## عیب‌یابی

| نشانه | علت محتمل | راه‌حل |
|---|---|---|
| همه‌ی چرخه‌ها `failed` با `ConnectError` یا `403` | VPN روشن است یا IP مسدود شده | VPN را خاموش یا split tunnel کنید |
| `migrate` با خطای احراز هویت خارج می‌شود | رمز `.env` با volume قبلی ClickHouse نمی‌خواند | رمز قبلی را برگردانید یا `docker compose down -v` (:warning: داده پاک می‌شود) |
| `collector failing` در لاگ و `stale` در `/health` | TSETMC در دسترس نیست (معمولاً VPN) | VPN را خاموش کنید. حلقه خودش ادامه می‌دهد و نیازی به restart نیست |
| پنل پیام «database unavailable» (503) نشان می‌دهد | ClickHouse بالا نیست یا راه‌اندازی آن تمام نشده | `docker compose ps clickhouse` و `docker compose logs clickhouse` |
| لاگ `waiting for the first trade of the day` در ساعات بازار | TSETMC هنوز معامله‌ی امروز را نشان نمی‌دهد | طبیعی است؛ تا ۲۰ دقیقه منتظر می‌ماند و بعد روز را تعطیل ثبت می‌کند |
| همه‌ی collectorها `standby` هستند | lease رهبری در Redis گیر کرده است (نباید رخ دهد: TTL دارد) | پس از حداکثر ۶۰ ثانیه خودش آزاد می‌شود؛ `docker compose logs redis` |
| ClickHouse بالا نمی‌آید: `Access to file denied: …/config.d/prometheus.xml` و `dependency failed to start: … is unhealthy` | ایمیج قدیمی که فایل پیکربندی را از دیسک mount می‌کرد؛ فایلی که روی میزبان فقط برای صاحبش خواندنی است (`0600`) برای کاربر ClickHouse داخل کانتینر (uid ۱۰۱) خواندنی نیست | `docker compose --profile monitoring up -d --build`. از این نسخه پیکربندی‌ها با مجوز ثابت داخل ایمیج کپی می‌شوند ([ADR 0009](adr/0009-observability.md#بازبینی-پیکربندی-داخل-ایمیج-نه-mount)) |
| collector دیر روشن شد ولی صفحه‌ی صندوق خط‌چین صبح را ندارد | بازسازی پس از **سومین** چرخه اجرا می‌شود؛ یا آن صندوق رد شد چون زمان معاملاتش با تیک‌های زنده نمی‌خواند | لاگ `intraday backfill done` (فهرست `rejected_symbols`)، یا `SELECT status, count() FROM intraday_backfill_log FINAL WHERE day = today() GROUP BY status` ([ADR 0012](adr/0012-intraday-backfill.md)) |
| collector مدام «market closed» لاگ می‌کند | خارج از ساعات بازار | طبیعی است؛ برای آزمایش `COLLECT_IGNORE_MARKET_HOURS=true` |
| build روی `uv sync` گیر می‌کند | دسترسی به PyPI | VPN روشن، یا `UV_INDEX_URL` را روی یک mirror تنظیم کنید |

## تست

| فرمان | چه چیزی | نیاز |
|---|---|---|
| `make test` | تست‌های واحد | هیچ (بدون شبکه و دیتابیس) |
| `make test-all` | به‌علاوه‌ی تست یکپارچگی روی ClickHouse واقعی | `docker compose up -d clickhouse` |
| `make fixtures` | ضبط پاسخ واقعی APIها در `tests/fixtures/captured` و ساخت نمونه‌ی کوچک در `tests/fixtures/sample` | :warning: VPN خاموش |
| `make probe` | اندازه‌گیری دریافت تغییرات (delta) دیده‌بان | :warning: VPN خاموش، در ساعات بازار |
| `make docs` | ساخت سایت مستندات با `--strict` | — |
| `make check` | همه‌ی بررسی‌های CI به‌جز آزمون دود: lint، type، تست‌ها با پوشش، پنل، مستندات | ClickHouse در حال اجرا |
| `make web-test` | بررسی نوع و تست‌های پنل | `make web-install` |
| `uv run python scripts/loadtest.py` | آزمون بار مسیر خواندن API ([نتایج](09-quality-engineering.md#آزمون-بار)) | API در حال اجرا |
