# مدل داده

<p class="lead">جدول‌ها، کلیدها و موتورهای ClickHouse، و دلیل هر انتخاب. طرح‌واره فقط با فایل‌های مایگریشن تغییر می‌کند (<a href="../adr/0005-migrations.md">ADR 0005</a>) و این صفحه نسخه‌ی خوانای همان فایل‌هاست.</p>


<svg class="dg" viewBox="0 0 960 470" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="مدل داده">
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
  <rect class="dg-bg" x="0" y="0" width="960" height="470" rx="16"/>
  <defs>
    <marker id="dm-a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path class="arrowhead" d="M0,0 L10,5 L0,10 z"/>
    </marker>
  </defs>
  <!-- column labels -->
  <text class="t-zone" x="840" y="24" text-anchor="middle">مرجع (روزانه)</text>
  <text class="t-zone" x="520" y="24" text-anchor="middle">سری زمانی (دقیقه‌ای)</text>
  <text class="t-zone" x="160" y="24" text-anchor="middle">عملیات و ممیزی</text>
  <!-- funds -->
  <rect class="src" x="740" y="40" width="200" height="170" rx="10"/>
  <text class="t-title" x="840" y="64" text-anchor="middle">funds</text>
  <text class="t-small" x="840" y="82" text-anchor="middle">ReplacingMergeTree(updated_at)</text>
  <line class="grid-line" x1="755" y1="92" x2="925" y2="92"/>
  <text class="t-mono" x="840" y="112" text-anchor="middle">PK  ins_code</text>
  <text class="t-mono" x="840" y="130" text-anchor="middle">symbol · name · isin</text>
  <text class="t-mono" x="840" y="148" text-anchor="middle">fund_type · market · board</text>
  <text class="t-mono" x="840" y="166" text-anchor="middle">is_active</text>
  <text class="t-small" x="840" y="194" text-anchor="middle">یک نسخه‌ی جدید در هر همگام‌سازی</text>
  <!-- fund_daily -->
  <rect class="src" x="740" y="240" width="200" height="140" rx="10"/>
  <text class="t-title" x="840" y="264" text-anchor="middle">fund_daily</text>
  <text class="t-small" x="840" y="282" text-anchor="middle">ReplacingMergeTree(updated_at)</text>
  <line class="grid-line" x1="755" y1="292" x2="925" y2="292"/>
  <text class="t-mono" x="840" y="312" text-anchor="middle">PK  ins_code, trade_date</text>
  <text class="t-mono" x="840" y="330" text-anchor="middle">units · net_assets</text>
  <text class="t-mono" x="840" y="348" text-anchor="middle">*_weight (رزرو)</text>
  <!-- fund_ticks -->
  <rect class="core" x="400" y="40" width="240" height="250" rx="10"/>
  <text class="t-title" x="520" y="64" text-anchor="middle">fund_ticks</text>
  <text class="t-small" x="520" y="82" text-anchor="middle">ReplacingMergeTree(ingested_at) · ماهانه</text>
  <line class="grid-line" x1="415" y1="92" x2="625" y2="92"/>
  <text class="t-mono" x="520" y="112" text-anchor="middle">PK  ins_code, ts</text>
  <text class="t-mono" x="520" y="132" text-anchor="middle">last · close · open · high · low</text>
  <text class="t-mono" x="520" y="150" text-anchor="middle">volume · value · trade_count</text>
  <text class="t-mono" x="520" y="168" text-anchor="middle">block_volume · block_value</text>
  <text class="t-mono" x="520" y="186" text-anchor="middle">nav_redemption · nav_subscription</text>
  <text class="t-mono" x="520" y="204" text-anchor="middle">nav_at · bid · ask (price, volume)</text>
  <text class="t-mono" x="520" y="222" text-anchor="middle">ind/inst · buy/sell · vol/value/count</text>
  <text class="t-mono" x="520" y="240" text-anchor="middle">quality_flags · run_id</text>
  <text class="t-small" x="520" y="272" text-anchor="middle">یک ردیف برای هر صندوق در هر دقیقه</text>
  <!-- market_ticks -->
  <rect class="core" x="400" y="320" width="240" height="110" rx="10"/>
  <text class="t-title" x="520" y="344" text-anchor="middle">market_ticks</text>
  <text class="t-small" x="520" y="362" text-anchor="middle">ReplacingMergeTree(ingested_at)</text>
  <text class="t-mono" x="520" y="384" text-anchor="middle">PK  ts</text>
  <text class="t-mono" x="520" y="402" text-anchor="middle">index_value · eq_index_value · state</text>
  <!-- ops -->
  <rect class="store" x="30" y="40" width="260" height="110" rx="10"/>
  <text class="t-title" x="160" y="64" text-anchor="middle">collection_runs</text>
  <text class="t-small" x="160" y="82" text-anchor="middle">MergeTree</text>
  <text class="t-mono" x="160" y="104" text-anchor="middle">run_id · tick · status</text>
  <text class="t-mono" x="160" y="122" text-anchor="middle">expected_funds · received_funds</text>
  <rect class="store" x="30" y="175" width="260" height="115" rx="10"/>
  <text class="t-title" x="160" y="199" text-anchor="middle">raw_snapshots</text>
  <text class="t-small" x="160" y="217" text-anchor="middle">MergeTree · ZSTD · روزانه · TTL ۳۰ روز</text>
  <text class="t-mono" x="160" y="239" text-anchor="middle">run_id · endpoint · ins_code</text>
  <text class="t-mono" x="160" y="257" text-anchor="middle">status_code · latency_ms · payload</text>
  <rect class="store" x="30" y="320" width="260" height="110" rx="10"/>
  <text class="t-title" x="160" y="344" text-anchor="middle">data_quality_log</text>
  <text class="t-small" x="160" y="362" text-anchor="middle">MergeTree · TTL ۱۸۰ روز</text>
  <text class="t-mono" x="160" y="384" text-anchor="middle">run_id · ins_code · check</text>
  <text class="t-mono" x="160" y="402" text-anchor="middle">severity · action · detail</text>
  <!-- relations -->
  <path class="edge" d="M740,112 L642,112" marker-end="url(#dm-a)"/>
  <text class="t-small" x="691" y="104" text-anchor="middle">ins_code</text>
  <path class="edge dash" d="M740,312 L700,312 L700,140 L642,140" marker-end="url(#dm-a)"/>
  <path class="edge" d="M400,240 L292,95" marker-end="url(#dm-a)"/>
  <path class="edge" d="M400,250 L292,230" marker-end="url(#dm-a)"/>
  <path class="edge dash" d="M400,270 L292,370" marker-end="url(#dm-a)"/>
  <text class="t-small" x="340" y="162" text-anchor="middle">run_id</text>
  <text class="t-small" x="345" y="455" text-anchor="middle">هر ردیف تمیز با run_id به پاسخ خام و چرخه‌ی سازنده‌اش برمی‌گردد</text>
</svg>

*شکل ۱ — سه دسته جدول: مرجع (روزانه)، سری زمانی (دقیقه‌ای)، و عملیات و ممیزی. <code>run_id</code> هر ردیف تمیز را به چرخه و پاسخ خامی که آن را ساخته وصل می‌کند.*


## اصول مدل‌سازی



#### کلید مرتب‌سازی = الگوی پرسش

در ClickHouse، `ORDER BY` نقش ایندکس اصلی را دارد. تقریباً همه‌ی پرسش‌های پنل «یک یا چند صندوق در یک بازه‌ی زمانی» است، پس کلید `fund_ticks` برابر `(ins_code, ts)` است.

#### یکتایی بدون قفل

`ReplacingMergeTree(ingested_at)` برای هر کلید فقط آخرین نسخه را نگه می‌دارد. اجرای دوباره‌ی یک چرخه یا replay یک روز، ردیف تکراری نمی‌سازد.

#### پارتیشن ماهانه

حدود ۱۵۰ صندوق × ۲۱۰ دقیقه × ۲۲ روز ≈ ۷۰۰ هزار ردیف در ماه. پارتیشن کوچک‌تر فقط تعداد part‌ها را زیاد می‌کند. داده‌ی خام استثناست: پارتیشن روزانه دارد تا TTL کل پارتیشن را یکجا حذف کند.

#### زمان همیشه با منطقه‌ی زمانی

همه‌ی ستون‌های زمانی `DateTime('Asia/Tehran')` هستند، پس `toDate(ts)` روز معاملاتی درست را می‌دهد، نه روز UTC را.


## جدول‌ها

##### fund_ticks


**یک ردیف برای هر صندوق در هر دقیقه.** قلب سیستم است و همه‌ی تحلیل‌ها از آن ساخته می‌شوند.

| گروه | ستون‌ها | منبع |
|---|---|---|
| کلید | `ins_code`، `ts` (دقیقه‌ی گردشده) | — |
| قیمت | `last_price`، `close_price`، `open_price`، `high_price`، `low_price`، `prev_close` | دیده‌بان |
| معاملات | `volume`، `value`، `trade_count` | دیده‌بان |
| تابلوی فرعی | `block_volume`، `block_value` | جمع تابلوهای `…0002`/`…0004` ([ADR 0007](adr/0007-fund-identity.md)) |
| NAV | `nav_redemption`، `nav_subscription`، `nav_at` | ETF |
| سفارش‌ها | `bid_price`، `bid_volume`، `ask_price`، `ask_volume` (سطح اول) | دیده‌بان |
| حقیقی/حقوقی | حجم، ارزش و تعداد خرید و فروش برای هر دو گروه | ClientTypeAll |
| کیفیت | `quality_flags` (bitmask)، `run_id`، `ingested_at` | [اعتبارسنجی](04-data-quality.md) |

همه‌ی قیمت‌ها و ارزش‌ها **ریال و عدد صحیح** (`UInt64`) هستند. خطای ممیز شناور در جمع ارزش معاملات قابل قبول نیست.

##### funds / fund_daily


| جدول | کلید | محتوا | به‌روزرسانی |
|---|---|---|---|
| `funds` | `ins_code` | نماد، نام، ISIN، نوع، بازار، تابلو، `is_active` | هر روز پیش از بازگشایی |
| `fund_daily` | `(ins_code, trade_date)` | تعداد واحد صادرشده، خالص دارایی | هر روز |

صندوقی که از بازار حذف شود **پاک نمی‌شود**؛ یک نسخه‌ی جدید با `is_active = 0` می‌گیرد تا تاریخچه‌اش در نمودارها باقی بماند.

##### market_ticks


شاخص کل، شاخص هم‌وزن، ارزش بازار و وضعیت بازار در هر دقیقه. معیار مقایسه‌ی بازده صندوق‌ها با کل بازار است.

##### روزانه


| جدول | موتور | کلید | محتوا |
|---|---|---|---|
| `fund_history_daily` | `ReplacingMergeTree(updated_at)`، پارتیشن سالانه | `(ins_code, trade_date)` | قیمت‌های روز و **ارزش رسمی** حقیقی/حقوقی؛ backfill اولیه‌ی ۴۰۰ روزه و به‌روزرسانی ۳۰ دقیقه پس از بسته شدن بازار |
| `fund_eod` | `AggregatingMergeTree` و MV `fund_eod_mv` | `(ins_code, trade_date)` | آخرین وضعیت هر روز از داده‌ی زنده: پایانی، ارزش، NAV، ورود پول |

`fund_eod` فقط از `argMax(…, (ts, ingested_at))` ساخته شده است. آخرین مقدار روز مستقل از تعداد تکرار ردیف‌هاست، پس replay و forward-fill آن را خراب نمی‌کنند. جمع (`sum`) این ویژگی را ندارد و به همین دلیل در MV استفاده نشده است.

##### عملیاتی


| جدول | نقش | نگهداری |
|---|---|---|
| `raw_snapshots` | پاسخ خام هر درخواست | ۳۰ روز |
| `collection_runs` | وضعیت هر چرخه: صندوق‌های مورد انتظار در برابر دریافت‌شده | دائمی |
| `data_quality_log` | هر یافته‌ی اعتبارسنجی و اقدام اصلاحی | ۱۸۰ روز |
| `schema_migrations` | نسخه و checksum مایگریشن‌ها | دائمی |

## پرچم‌های کیفیت

هر ردیف `fund_ticks` یک عدد `quality_flags` دارد که هر بیت آن یک وضعیت است. با این روش جدول باریک می‌ماند و فیلتر کردن ارزان است:

```sql
-- فقط تیک‌هایی که NAV دارند
SELECT * FROM fund_ticks WHERE bitAnd(quality_flags, 2) = 0
```

| بیت | مقدار | پرچم | معنا | از |
|:-:|--:|---|---|---|
| 1 | 2 | `NAV_MISSING` | NAV دریافت نشد | روز ۲ |
| 2 | 4 | `NAV_STALE` | زمان محاسبه‌ی NAV از آستانه قدیمی‌تر است | روز ۳ |
| 3 | 8 | `CLIENT_TYPE_MISSING` | صندوق در داده‌ی حقیقی/حقوقی نبود | روز ۲ |
| 4 | 16 | `FLOW_VALUE_ESTIMATED` | ارزش ریالی حقیقی/حقوقی تخمینی است (حجم × میانگین قیمت) | روز ۲ |
| 5 | 32 | `NO_TRADES` | امروز هنوز معامله‌ای نشده | روز ۲ |
| 6 | 64 | `PRICE_OUT_OF_RANGE` | قیمت خارج از دامنه‌ی مجاز روز | روز ۳ |
| 7 | 128 | `CUMULATIVE_DECREASE` | حجم یا ارزش تجمعی کاهش یافته | روز ۳ |
| 8 | 256 | `FORWARD_FILLED` | ردیف از تیک قبلی پر شده | روز ۳ |
| 9 | 512 | `STALE_QUOTE` | کل فید دیده‌بان چند چرخه تغییر نکرده | روز ۳ |
| 10 | 1024 | `CLIENT_VOLUME_MISMATCH` | جمع حقیقی و حقوقی با حجم کل نمی‌خواند | روز ۳ |
| 11 | 2048 | `NAV_CARRIED` | NAV از تیک قبلی ادامه یافته | روز ۳ |
| 12 | 4096 | `NAV_JUMP` | تغییر NAV بیش از آستانه | روز ۳ |
| 13 | 8192 | `RANGE_REPAIRED` | بیشترین/کمترین بازمحاسبه شده | روز ۳ |

> **⚠ قرارداد ذخیره‌سازی**
>
> شماره‌ی بیت‌ها بخشی از قالب داده‌ی ذخیره‌شده است. بیت جدید فقط به انتها اضافه می‌شود و هیچ بیتی تغییر شماره نمی‌دهد (`domain/quality.py`).

## تاریخچه‌ی مایگریشن‌ها

| فایل | تغییر | دلیل |
|---|---|---|
| `0001_init.sql` | جدول‌های پایه | روز ۱ |
| `0002_pipeline_columns.sql` | `nav_at`، ارزش و تعداد حقوقی، `block_*`، `funds.market/board`، جدول `market_ticks` | نتیجه‌ی نگاشت پاسخ‌های واقعی TSETMC |
| `0003_quality_counters.sql` | `collection_runs.issues/filled/repaired` | پایش کیفیت در سطح چرخه |
| `0004_history_and_eod.sql` | `fund_history_daily`، `fund_eod` و `fund_eod_mv` | بازده دوره‌ای، ورود پول رسمی، NAV پایان روز |

همه‌ی دستورهای `0002` به شکل `ADD COLUMN IF NOT EXISTS` هستند، پس اجرای دوباره‌ی آن روی دیتابیسی که نیمه‌کاره مانده بی‌خطر است.
