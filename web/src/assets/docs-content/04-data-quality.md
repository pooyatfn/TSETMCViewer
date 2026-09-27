# کیفیت داده و پیش‌پردازش

<p class="lead">پس از هر دریافت، پیش از نوشتن در دیتابیس، کامل بودن و درستی داده بررسی می‌شود. هر مشکل یا با اطلاعات موجود اصلاح می‌شود یا پرچم می‌خورد، و هر دو در گزارش کیفیت ثبت می‌شوند.</p>


- **۱۰** — بررسی در هر چرخه
- **۱۳** — پرچم کیفیت روی هر تیک
- **۰** — اصلاح بی‌صدا
- **۳ میلی‌ثانیه** — میانه‌ی زمان اعتبارسنجی ۱۵۰ صندوق



<svg class="dg" viewBox="0 0 960 360" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="مراحل اعتبارسنجی هر چرخه">
  <defs>
    <marker id="va-a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path class="arrowhead" d="M0,0 L10,5 L0,10 z"/>
    </marker>
  </defs>
  <!-- input -->
  <rect class="src" x="840" y="130" width="105" height="90" rx="10"/>
  <text class="t-title" x="892" y="162" text-anchor="middle">تیک‌های</text>
  <text class="t-title" x="892" y="182" text-anchor="middle">خام چرخه</text>
  <text class="t-small" x="892" y="204" text-anchor="middle">و تیک قبلی هر صندوق</text>
  <!-- stages -->
  <rect class="core" x="700" y="40" width="120" height="270" rx="10"/>
  <text class="t-small" x="760" y="62" text-anchor="middle">۱</text>
  <text class="t-title" x="760" y="84" text-anchor="middle">کامل بودن</text>
  <text class="t-body" x="760" y="118" text-anchor="middle">صندوق غایب</text>
  <text class="t-body" x="760" y="138" text-anchor="middle">دقیقه‌ی جاافتاده</text>
  <text class="t-body" x="760" y="158" text-anchor="middle">فید منجمد</text>
  <line class="grid-line" x1="712" y1="178" x2="808" y2="178"/>
  <text class="t-small" x="760" y="200" text-anchor="middle">اقدام:</text>
  <text class="t-small" x="760" y="218" text-anchor="middle">ادامه‌ی مقدار قبلی</text>
  <text class="t-small" x="760" y="236" text-anchor="middle">یا پرچم</text>
  <rect class="core" x="565" y="40" width="120" height="270" rx="10"/>
  <text class="t-small" x="625" y="62" text-anchor="middle">۲</text>
  <text class="t-title" x="625" y="84" text-anchor="middle">دامنه</text>
  <text class="t-body" x="625" y="118" text-anchor="middle">دامنه‌ی مجاز قیمت</text>
  <text class="t-body" x="625" y="138" text-anchor="middle">سقف و کف روز</text>
  <line class="grid-line" x1="577" y1="178" x2="673" y2="178"/>
  <text class="t-small" x="625" y="200" text-anchor="middle">اقدام:</text>
  <text class="t-small" x="625" y="218" text-anchor="middle">قیمت تیک قبلی</text>
  <text class="t-small" x="625" y="236" text-anchor="middle">یا پرچم</text>
  <rect class="core" x="430" y="40" width="120" height="270" rx="10"/>
  <text class="t-small" x="490" y="62" text-anchor="middle">۳</text>
  <text class="t-title" x="490" y="84" text-anchor="middle">سازگاری</text>
  <text class="t-body" x="490" y="118" text-anchor="middle">سقف/کف شامل آخرین</text>
  <text class="t-body" x="490" y="138" text-anchor="middle">تجمعی نزولی نیست</text>
  <text class="t-body" x="490" y="158" text-anchor="middle">حقیقی+حقوقی = حجم</text>
  <line class="grid-line" x1="442" y1="178" x2="538" y2="178"/>
  <text class="t-small" x="490" y="200" text-anchor="middle">اقدام:</text>
  <text class="t-small" x="490" y="218" text-anchor="middle">بازمحاسبه،</text>
  <text class="t-small" x="490" y="236" text-anchor="middle">مقدار قبلی، پرچم</text>
  <rect class="core" x="295" y="40" width="120" height="270" rx="10"/>
  <text class="t-small" x="355" y="62" text-anchor="middle">۴</text>
  <text class="t-title" x="355" y="84" text-anchor="middle">NAV</text>
  <text class="t-body" x="355" y="118" text-anchor="middle">نبود NAV</text>
  <text class="t-body" x="355" y="138" text-anchor="middle">کهنگی NAV</text>
  <text class="t-body" x="355" y="158" text-anchor="middle">جهش ناگهانی</text>
  <line class="grid-line" x1="307" y1="178" x2="403" y2="178"/>
  <text class="t-small" x="355" y="200" text-anchor="middle">اقدام:</text>
  <text class="t-small" x="355" y="218" text-anchor="middle">ادامه‌ی NAV قبلی</text>
  <text class="t-small" x="355" y="236" text-anchor="middle">یا پرچم</text>
  <!-- outputs -->
  <rect class="store" x="30" y="60" width="235" height="95" rx="10"/>
  <text class="t-title" x="147" y="88" text-anchor="middle">fund_ticks</text>
  <text class="t-body" x="147" y="112" text-anchor="middle">مقدار اصلاح‌شده</text>
  <text class="t-small" x="147" y="132" text-anchor="middle">و بیت در quality_flags</text>
  <rect class="store" x="30" y="190" width="235" height="95" rx="10"/>
  <text class="t-title" x="147" y="218" text-anchor="middle">data_quality_log</text>
  <text class="t-body" x="147" y="242" text-anchor="middle">چه بود، چه کردیم</text>
  <text class="t-small" x="147" y="262" text-anchor="middle">یک ردیف در شروع هر رخداد</text>
  <!-- edges -->
  <path class="edge" d="M840,175 L822,175" marker-end="url(#va-a)"/>
  <path class="edge" d="M700,175 L687,175" marker-end="url(#va-a)"/>
  <path class="edge" d="M565,175 L552,175" marker-end="url(#va-a)"/>
  <path class="edge" d="M430,175 L417,175" marker-end="url(#va-a)"/>
  <path class="edge" d="M295,150 L267,110" marker-end="url(#va-a)"/>
  <path class="edge" d="M295,200 L267,235" marker-end="url(#va-a)"/>
  <text class="t-small" x="560" y="340" text-anchor="middle">هیچ اصلاحی بی‌صدا نیست: هر تغییر هم در ردیف پرچم می‌خورد و هم در گزارش کیفیت ثبت می‌شود</text>
</svg>

*شکل ۱ — چهار گروه بررسی روی تیک‌های هر چرخه، به ترتیب. هر بررسی تیک فعلی را با قواعد بازار و با تیک قبلی همان صندوق مقایسه می‌کند.*


## اصول



#### هیچ اصلاحی بی‌صدا نیست

هر تغییر دو ردپا دارد: یک بیت در `quality_flags` همان ردیف، و یک ردیف در `data_quality_log` که می‌گوید چه دیده شد و چه کاری انجام شد. داده‌ی خام هم دست‌نخورده در `raw_snapshots` می‌ماند.

#### فقط با اطلاعاتی که داریم

اصلاح یعنی ادامه‌ی آخرین مقدار معتبر (forward-fill)، نه درون‌یابی. درون‌یابی حجم یا قیمت یعنی ساختن معامله‌ای که انجام نشده، و برای داده‌ی مالی این از نبود داده بدتر است.

#### قاعده‌ی بازار، نه آمار عمومی

بورس تهران دامنه‌ی نوسان روزانه دارد. قیمتی خارج از این دامنه **ناممکن** است و نیازی به z-score یا MAD نیست. آزمون‌های آماری عمومی در بازاری با دامنه‌ی نوسان یا هشدار کاذب می‌دهند یا خطای واقعی را نمی‌بینند.

#### ثبت لبه‌ای

شرایط ماندگار (NAV کهنه، صندوق غایب، فید منجمد) فقط **در شروع هر رخداد** یک ردیف گزارش می‌سازند، نه یکی در هر دقیقه. پرچم همچنان روی همه‌ی تیک‌های درگیر می‌نشیند. گزارش خوانا می‌ماند و فیلتر داده دقیق.


## فهرست بررسی‌ها

| # | بررسی | شرط | شدت | اقدام | پرچم |
|:-:|---|---|:-:|---|---|
| 1 | `missing_fund` | صندوقِ فهرست امروز در دیده‌بان نیست | warn | ادامه‌ی تیک قبلی (تا ۳۰ دقیقه)؛ وگرنه حذف | `FORWARD_FILLED` |
| 2 | `gap` | فاصله‌ی تیک فعلی با قبلی بیش از یک دقیقه (در ساعات بازار) | warn | ساخت تیک برای دقیقه‌های جاافتاده با مقدار قبلی؛ اگر بیش از ۳۰ دقیقه، باز می‌ماند | `FORWARD_FILLED` |
| 3 | `feed_stale` | بیشترین `hEven` کل دیده‌بان در ۳ چرخه‌ی پیاپی تغییر نکرده | error | پرچم روی همه‌ی تیک‌ها | `STALE_QUOTE` |
| 4 | `price_out_of_band` | آخرین یا پایانی خارج از `[pMin, pMax]` روز | error | جایگزینی با قیمت تیک قبلی؛ اگر نبود، نگه داشتن | `PRICE_OUT_OF_RANGE` |
| 5 | `ohlc_inconsistent` | بیشترین/کمترین شامل اولین و آخرین نیست | warn | بازمحاسبه‌ی بیشترین و کمترین | `RANGE_REPAIRED` |
| 6 | `cumulative_decrease` | حجم، ارزش، تعداد یا حجم حقیقی/حقوقی نسبت به تیک قبلی همان روز کم شده | error | نگه داشتن مقدار قبلی (یکنواخت‌سازی) | `CUMULATIVE_DECREASE` |
| 7 | `client_volume_mismatch` | اختلاف جمع خرید (یا فروش) حقیقی و حقوقی با حجم کل بیش از ۲٪ | warn | فقط پرچم | `CLIENT_VOLUME_MISMATCH` |
| 8 | `nav_missing` | درخواست NAV شکست خورد یا مقدار نداشت | warn | ادامه‌ی NAV قبلی همراه با زمان محاسبه‌ی آن | `NAV_MISSING`، `NAV_CARRIED` |
| 9 | `nav_stale` | زمان محاسبه‌ی NAV بیش از ۲۰ دقیقه قبل از تیک است | info | فقط پرچم | `NAV_STALE` |
| 10 | `nav_jump` | تغییر NAV نسبت به تیک قبلی بیش از ۱۰٪ | warn | فقط پرچم؛ مقدار دست نمی‌خورد | `NAV_JUMP` |

همه‌ی آستانه‌ها با متغیر محیطی قابل تنظیم‌اند (`VALIDATION_NAV_STALE_MINUTES`، `VALIDATION_NAV_JUMP_RATIO`، `VALIDATION_CLIENT_MISMATCH_RATIO`، `VALIDATION_MAX_GAP_FILL_MINUTES`، `VALIDATION_FEED_STALE_CYCLES`).

## چرا این روش‌ها؟

> **چرا forward-fill و نه درون‌یابی خطی؟**
>
> اگر collector ساعت ۱۰:۰۲ تا ۱۰:۰۴ قطع باشد، ما نمی‌دانیم در این سه دقیقه چه معامله‌ای شده است. درون‌یابی خطی حجم تجمعی، معامله‌هایی با توزیع یکنواخت می‌سازد که شاید هرگز رخ نداده‌اند. forward-fill فقط می‌گوید «آخرین چیزی که دیدیم این بود» و پرچم `FORWARD_FILLED` این را صریح می‌کند. نمودارها پیوسته می‌مانند و تحلیلی که دقت لازم دارد این ردیف‌ها را کنار می‌گذارد.

> **چرا قیمت خارج از دامنه با قیمت قبلی جایگزین می‌شود، نه حذف؟**
>
> حذف ردیف یعنی سوراخ در سری زمانی، و بقیه‌ی ستون‌های همان ردیف (NAV، حقیقی/حقوقی) هم از دست می‌روند. خطا فقط در یک ستون است، پس فقط همان ستون اصلاح می‌شود. مقدار اصلی در پاسخ خام محفوظ است و با `replay` قابل بازسازی است.

> **چرا عدم تطابق حقیقی/حقوقی فقط پرچم می‌خورد؟**
>
> `ClientTypeAll` و دیده‌بان دو endpoint جدا هستند و در یک لحظه‌ی دقیق گرفته نمی‌شوند؛ اختلاف چندثانیه‌ای بین آن‌ها طبیعی است. هیچ‌کدام بر دیگری برتری ندارد، پس داده‌ای برای اصلاح وجود ندارد. پرچم به نمودار ورود پول حقیقی اجازه می‌دهد این دقیقه‌ها را کم‌رنگ نشان دهد.

> **چرا جهش NAV اصلاح نمی‌شود؟**
>
> تغییر بیش از ۱۰٪ در چند دقیقه برای صندوق سهامی بعید است، اما برای صندوق اهرمی در روز پرنوسان ممکن است. همچنین ممکن است نشانه‌ی رویداد شرکتی باشد (مثلاً تجزیه‌ی واحدها). تصمیم با تحلیل‌گر است، پس فقط پرچم می‌خورد.

## پر کردن شکاف و ثبت لبه‌ای، در عمل


<svg class="dg" viewBox="0 0 960 300" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="پر کردن شکاف و ثبت لبه‌ای">
  <!-- time axis labels: minute 10:00 (right) → 10:09 (left) -->
  <text class="t-small" x="840" y="280" text-anchor="middle">۱۰:۰۰</text>
  <text class="t-small" x="770" y="280" text-anchor="middle">۱۰:۰۱</text>
  <text class="t-small" x="700" y="280" text-anchor="middle">۱۰:۰۲</text>
  <text class="t-small" x="630" y="280" text-anchor="middle">۱۰:۰۳</text>
  <text class="t-small" x="560" y="280" text-anchor="middle">۱۰:۰۴</text>
  <text class="t-small" x="490" y="280" text-anchor="middle">۱۰:۰۵</text>
  <text class="t-small" x="420" y="280" text-anchor="middle">۱۰:۰۶</text>
  <text class="t-small" x="350" y="280" text-anchor="middle">۱۰:۰۷</text>
  <text class="t-small" x="280" y="280" text-anchor="middle">۱۰:۰۸</text>
  <text class="t-small" x="210" y="280" text-anchor="middle">۱۰:۰۹</text>
  <!-- row 1: gap fill -->
  <text class="t-title" x="945" y="40" text-anchor="start">پر کردن شکاف</text>
  <text class="t-small" x="945" y="58" text-anchor="start">۳ دقیقه قطعی collector</text>
  <line class="grid-line" x1="190" y1="90" x2="860" y2="90"/>
  <circle cx="840" cy="90" r="9" class="bar-core"/>
  <circle cx="770" cy="90" r="9" class="bar-core"/>
  <circle cx="700" cy="90" r="9" class="box"/>
  <circle cx="630" cy="90" r="9" class="box"/>
  <circle cx="560" cy="90" r="9" class="box"/>
  <circle cx="490" cy="90" r="9" class="bar-core"/>
  <circle cx="420" cy="90" r="9" class="bar-core"/>
  <circle cx="350" cy="90" r="9" class="bar-core"/>
  <circle cx="280" cy="90" r="9" class="bar-core"/>
  <circle cx="210" cy="90" r="9" class="bar-core"/>
  <path class="edge dash" d="M770,110 L770,118 L560,118 L560,110"/>
  <text class="t-small" x="665" y="136" text-anchor="middle">سه تیک با مقدار ۱۰:۰۱ و پرچم FORWARD_FILLED</text>
  <!-- row 2: edge-triggered logging -->
  <text class="t-title" x="945" y="175" text-anchor="start">ثبت لبه‌ای</text>
  <text class="t-small" x="945" y="193" text-anchor="start">کهنگی NAV در دو رخداد جدا</text>
  <line class="grid-line" x1="190" y1="220" x2="860" y2="220"/>
  <rect x="826" y="206" width="28" height="28" rx="6" class="box"/>
  <rect x="756" y="206" width="28" height="28" rx="6" class="bar-store"/>
  <rect x="686" y="206" width="28" height="28" rx="6" class="bar-store"/>
  <rect x="616" y="206" width="28" height="28" rx="6" class="bar-store"/>
  <rect x="546" y="206" width="28" height="28" rx="6" class="box"/>
  <rect x="476" y="206" width="28" height="28" rx="6" class="box"/>
  <rect x="406" y="206" width="28" height="28" rx="6" class="bar-store"/>
  <rect x="336" y="206" width="28" height="28" rx="6" class="bar-store"/>
  <rect x="266" y="206" width="28" height="28" rx="6" class="box"/>
  <rect x="196" y="206" width="28" height="28" rx="6" class="box"/>
  <path class="edge hot" d="M770,196 L770,178"/>
  <circle cx="770" cy="172" r="6" class="arrowhead hot"/>
  <path class="edge hot" d="M420,196 L420,178"/>
  <circle cx="420" cy="172" r="6" class="arrowhead hot"/>
  <text class="t-small" x="770" y="160" text-anchor="middle">یک ردیف گزارش</text>
  <text class="t-small" x="420" y="160" text-anchor="middle">یک ردیف گزارش</text>
  <!-- legend -->
  <circle cx="120" cy="84" r="7" class="bar-core"/>
  <text class="t-small" x="105" y="88" text-anchor="start">تیک واقعی</text>
  <circle cx="120" cy="108" r="7" class="box"/>
  <text class="t-small" x="105" y="112" text-anchor="start">تیک پرشده</text>
  <rect x="113" y="206" width="14" height="14" rx="3" class="bar-store"/>
  <text class="t-small" x="105" y="218" text-anchor="start">پرچم روی تیک</text>
  <circle cx="120" cy="242" r="6" class="arrowhead hot"/>
  <text class="t-small" x="105" y="246" text-anchor="start">ردیف گزارش</text>
</svg>

*شکل ۲ — بالا: سه دقیقه‌ی جاافتاده با مقدار آخرین تیک واقعی پر می‌شوند. پایین: NAV کهنه در هر تیک پرچم می‌خورد، اما در شروع هر رخداد فقط یک ردیف گزارش ساخته می‌شود.*


## حالت validator

validator تنها بخش **حالت‌دار** pipeline است، چون چند بررسی به تیک قبلی نیاز دارند:

| حالت | کاربرد | مدیریت |
|---|---|---|
| آخرین تیک هر صندوق | تجمعی، جهش NAV، پر کردن شکاف | ابتدای هر روز معاملاتی پاک می‌شود |
| رخدادهای فعال | ثبت لبه‌ای | از روی پرچم‌های آخرین تیک بازیابی می‌شود |
| `hEven` فید | تشخیص فید منجمد | شمارنده‌ی چرخه‌های بدون تغییر |

**راه‌اندازی دوباره:** اگر collector وسط روز restart شود، در اولین چرخه آخرین تیک هر صندوق از ClickHouse خوانده می‌شود (`LIMIT 1 BY ins_code`) و حالت از همان‌جا ادامه پیدا می‌کند. رخدادهای فعال از پرچم‌های همان تیک‌ها بازسازی می‌شوند تا گزارش تکراری ساخته نشود.

**replay:** با یک validator تازه اجرا می‌شود و چرخه‌ها را به ترتیب زمان پردازش می‌کند، پس نتیجه همان است که collector زنده می‌ساخت. گزارش‌های کیفیت آن روز پیش از replay پاک می‌شوند تا تکراری نشوند.

## گزارش روزانه

```console
$ tsetmc-viewer quality --date 2026-09-26
Data quality — 2026-09-26
  cycles:        211  {'ok': 204, 'partial': 7}
  completeness:  99.61% of expected fund-minutes
  ticks:         31650
    FLOW_VALUE_ESTIMATED       31650  100.0%
    NAV_STALE                   2140    6.8%
    FORWARD_FILLED               123    0.4%
    ...
  issues:
    info   nav_stale                flagged                  96
    warn   missing_fund             forward_filled           11
    ...
```

> **اعداد بالا نمونه‌اند**
>
> قالب خروجی واقعی است، اما اعداد تا اولین روز معاملاتی کامل تخمینی‌اند و پس از آن با خروجی واقعی جایگزین می‌شوند.

کوئری‌های پشت گزارش (`storage/repository.py → quality_report`):

```sql
-- کامل بودن: چه کسری از «صندوق × دقیقه»های مورد انتظار واقعاً دریافت شد
SELECT sum(received_funds) / sum(expected_funds) FROM collection_runs WHERE toDate(tick) = today();

-- سهم هر پرچم
SELECT countIf(bitAnd(quality_flags, 256) != 0) / count() AS forward_filled_ratio
FROM fund_ticks FINAL WHERE toDate(ts) = today();
```

## آنچه عمداً انجام نمی‌شود

- **حذف ردیف‌های مشکوک.** حذف بی‌بازگشت است؛ پرچم بازگشت‌پذیر است.
- **اصلاح بر اساس منبع دوم.** فیپیران در دسترس نیست ([منابع داده](02-data-sources.md)) و منبع دیگری برای مقایسه‌ی درون‌روز وجود ندارد.
- **تشخیص تعطیلات رسمی از روی تقویم.** در روز تعطیل، بررسی `feed_stale` نبود داده‌ی تازه را نشان می‌دهد. فهرست تعطیلات در [گام‌های بعدی](10-limitations.md#گامهای-بعدی) آمده است.
