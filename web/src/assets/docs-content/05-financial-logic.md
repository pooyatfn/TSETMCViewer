# منطق مالی

<p class="lead">شاخص‌هایی که از داده‌ی خام ساخته می‌شوند: تعریف دقیق هر کدام، دلیل انتخابش، و اینکه به چه سؤالی از معامله‌گر یا مدیر پرتفوی پاسخ می‌دهد. همه‌ی فرمول‌ها در <code>domain/metrics.py</code> هستند و تست واحد دارند.</p>


- **۱۵۹** — صندوق سهامی، شاخصی، بخشی و اهرمی
- **۳۷۵ همت** — خالص دارایی تخمینی (پایان ۱ مهر ۱۴۰۵)
- **−۰٫۵٪** — میانه‌ی حباب (بدون صندوق‌های اهرمی)
- ⚠ **−۱۸٪** — «حباب» ساختگی صندوق‌های اهرمی


> **داده‌ی این صفحه**
>
> اعداد این صفحه از داده‌ی واقعی TSETMC در پایان جلسه‌ی ۱ مهر ۱۴۰۵ آمده‌اند: فهرست کامل ۳۳۳ صندوق، NAV همه‌ی آن‌ها و ۴۰۰ روز تاریخچه، که با `scripts/capture_offhours.py` ضبط و از همان pipeline سرویس عبور داده شدند. «همت» یعنی هزار میلیارد تومان (۱۰<sup>۱۳</sup> ریال).

## شاخص‌ها

| شاخص | فرمول | واحد | سؤالی که جواب می‌دهد |
|---|---|---|---|
| **بازده روزانه** | پایانی ÷ پایانی دیروز − ۱ | ٪ | امروز صندوق چه کرد؟ |
| **حباب (NAV premium)** | پایانی ÷ NAV ابطال − ۱ | ٪ | خریدار چقدر بیشتر (یا کمتر) از ارزش دارایی‌ها می‌پردازد؟ |
| **خالص دارایی (AUM)** | NAV ابطال × تعداد واحد صادرشده | ریال | صندوق چقدر بزرگ است؟ |
| **سهم از بازار صندوق‌ها** | AUM صندوق ÷ مجموع AUM | ٪ | وزن صندوق در تصویر کلی چقدر است؟ |
| **ورود پول حقیقی** | ارزش خرید حقیقی − ارزش فروش حقیقی | ریال | پول مردم به کدام صندوق می‌رود و از کدام خارج می‌شود؟ |
| **قدرت خریدار حقیقی** | (خرید حقیقی ÷ تعداد خریدار) ÷ (فروش حقیقی ÷ تعداد فروشنده) | نسبت | خریدارها درشت‌ترند یا فروشنده‌ها؟ |
| **گردش معاملات** | ارزش معاملات ÷ خالص دارایی | ٪ | صندوق چقدر نقدشونده است؟ آیا امروز غیرعادی معامله شد؟ |
| **بازده دوره‌ای** | پایانی امروز ÷ پایانی مبدأ − ۱ برای ۱ هفته، ۱ ماه، ۳ ماه و از ابتدای سال | ٪ | روند میان‌مدت کدام صندوق‌ها بهتر بوده؟ |

## حباب: مهم‌ترین شاخص صندوق قابل معامله

صندوق ETF دو قیمت دارد: **قیمت بازار** که خریدار و فروشنده تعیین می‌کنند، و **NAV** که ارزش واقعی دارایی‌های پشت هر واحد است. اختلاف این دو، حباب است:

- **حباب مثبت:** خریدار بیش از ارزش دارایی‌ها پول می‌دهد. معمولاً نشانه‌ی هیجان خرید است، و بازارگردان یا صدور واحد جدید معمولاً آن را از بین می‌برد.
- **حباب منفی:** واحد صندوق ارزان‌تر از دارایی‌هایش معامله می‌شود. این نشانه‌ی فشار فروش است، یا (در صندوق‌های خاص) نشانه‌ی محدودیت ابطال.

مبنای محاسبه **NAV ابطال** است، نه NAV صدور، چون فروشنده‌ای که واحدش را ابطال کند همین مبلغ را می‌گیرد، پس این کف ارزش واحد است.


<svg class="dg" viewBox="0 0 960 400" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="حباب صندوق‌ها به تفکیک نوع">
  <text class="t-title" x="940" y="28" text-anchor="start">حباب (قیمت ÷ NAV ابطال − ۱) هر صندوق، پایان جلسه‌ی ۱ مهر ۱۴۰۵</text>
  <line class="grid-line" x1="139.0" y1="50" x2="139.0" y2="345"/>
  <text class="t-small" x="139.0" y="365" text-anchor="middle">−۳۰٪</text>
  <line class="grid-line" x1="277.0" y1="50" x2="277.0" y2="345"/>
  <text class="t-small" x="277.0" y="365" text-anchor="middle">−۲۰٪</text>
  <line class="grid-line" x1="415.0" y1="50" x2="415.0" y2="345"/>
  <text class="t-small" x="415.0" y="365" text-anchor="middle">−۱۰٪</text>
  <line class="grid-line" x1="553.0" y1="50" x2="553.0" y2="345"/>
  <text class="t-small" x="553.0" y="365" text-anchor="middle">۰</text>
  <line class="grid-line" x1="691.0" y1="50" x2="691.0" y2="345"/>
  <text class="t-small" x="691.0" y="365" text-anchor="middle">+۱۰٪</text>
  <line class="edge" x1="553.0" y1="50" x2="553.0" y2="345"/>
  <text class="t-body" x="940" y="94" text-anchor="start">سهامی</text>
  <text class="t-small" x="940" y="112" text-anchor="start">۸۰ صندوق · میانه −۰.۳٪</text>
  <circle cx="84.9" cy="92" r="4.2" class="bar-core" fill-opacity="0.75"><title>دارا یکم: -33.9%</title></circle>
  <circle cx="554.0" cy="98" r="4.2" class="bar-core" fill-opacity="0.75"><title>اطلس: 0.1%</title></circle>
  <circle cx="529.2" cy="100" r="4.2" class="bar-core" fill-opacity="0.75"><title>آگاس: -1.7%</title></circle>
  <circle cx="558.3" cy="88" r="4.2" class="bar-core" fill-opacity="0.75"><title>ثروتم: 0.4%</title></circle>
  <circle cx="518.4" cy="96" r="4.2" class="bar-core" fill-opacity="0.75"><title>سرو: -2.5%</title></circle>
  <circle cx="554.0" cy="93" r="4.2" class="bar-core" fill-opacity="0.75"><title>داریوش: 0.1%</title></circle>
  <circle cx="538.9" cy="95" r="4.2" class="bar-core" fill-opacity="0.75"><title>ارزش: -1.0%</title></circle>
  <circle cx="536.4" cy="97" r="4.2" class="bar-core" fill-opacity="0.75"><title>افق ملت: -1.2%</title></circle>
  <circle cx="538.0" cy="97" r="4.2" class="bar-core" fill-opacity="0.75"><title>تکپاد: -1.1%</title></circle>
  <circle cx="539.1" cy="98" r="4.2" class="bar-core" fill-opacity="0.75"><title>آتیمس: -1.0%</title></circle>
  <circle cx="554.5" cy="98" r="4.2" class="bar-core" fill-opacity="0.75"><title>مانا: 0.1%</title></circle>
  <circle cx="564.1" cy="95" r="4.2" class="bar-core" fill-opacity="0.75"><title>سلام: 0.8%</title></circle>
  <circle cx="544.2" cy="93" r="4.2" class="bar-core" fill-opacity="0.75"><title>بذر: -0.6%</title></circle>
  <circle cx="535.7" cy="93" r="4.2" class="bar-core" fill-opacity="0.75"><title>آساس: -1.3%</title></circle>
  <circle cx="544.4" cy="100" r="4.2" class="bar-core" fill-opacity="0.75"><title>مدیر: -0.6%</title></circle>
  <circle cx="555.5" cy="84" r="4.2" class="bar-core" fill-opacity="0.75"><title>انار: 0.2%</title></circle>
  <circle cx="566.0" cy="94" r="4.2" class="bar-core" fill-opacity="0.75"><title>دی سهام: 0.9%</title></circle>
  <circle cx="541.4" cy="98" r="4.2" class="bar-core" fill-opacity="0.75"><title>جوانه کوچک: -0.8%</title></circle>
  <circle cx="568.8" cy="84" r="4.2" class="bar-core" fill-opacity="0.75"><title>هامون: 1.1%</title></circle>
  <circle cx="535.1" cy="85" r="4.2" class="bar-core" fill-opacity="0.75"><title>کاریس: -1.3%</title></circle>
  <circle cx="543.5" cy="86" r="4.2" class="bar-core" fill-opacity="0.75"><title>ثمین: -0.7%</title></circle>
  <circle cx="548.9" cy="92" r="4.2" class="bar-core" fill-opacity="0.75"><title>آوان: -0.3%</title></circle>
  <circle cx="584.8" cy="91" r="4.2" class="bar-core" fill-opacity="0.75"><title>پرتوسا: 2.3%</title></circle>
  <circle cx="545.2" cy="94" r="4.2" class="bar-core" fill-opacity="0.75"><title>رشدی کیان: -0.6%</title></circle>
  <circle cx="520.5" cy="88" r="4.2" class="bar-core" fill-opacity="0.75"><title>خلیج: -2.4%</title></circle>
  <circle cx="471.6" cy="88" r="4.2" class="bar-core" fill-opacity="0.75"><title>خبرگان: -5.9%</title></circle>
  <circle cx="556.6" cy="90" r="4.2" class="bar-core" fill-opacity="0.75"><title>عقیق: 0.3%</title></circle>
  <circle cx="555.1" cy="93" r="4.2" class="bar-core" fill-opacity="0.75"><title>تاراز: 0.2%</title></circle>
  <circle cx="526.7" cy="97" r="4.2" class="bar-core" fill-opacity="0.75"><title>اعتبارسهام: -1.9%</title></circle>
  <circle cx="552.9" cy="83" r="4.2" class="bar-core" fill-opacity="0.75"><title>آوا: -0.0%</title></circle>
  <circle cx="552.4" cy="97" r="4.2" class="bar-core" fill-opacity="0.75"><title>نارین: -0.0%</title></circle>
  <circle cx="563.6" cy="93" r="4.2" class="bar-core" fill-opacity="0.75"><title>اوج: 0.8%</title></circle>
  <circle cx="548.6" cy="94" r="4.2" class="bar-core" fill-opacity="0.75"><title>دریا: -0.3%</title></circle>
  <circle cx="590.6" cy="94" r="4.2" class="bar-core" fill-opacity="0.75"><title>هومان: 2.7%</title></circle>
  <circle cx="560.1" cy="98" r="4.2" class="bar-core" fill-opacity="0.75"><title>الماس: 0.5%</title></circle>
  <circle cx="543.2" cy="83" r="4.2" class="bar-core" fill-opacity="0.75"><title>آبنوس: -0.7%</title></circle>
  <circle cx="616.3" cy="87" r="4.2" class="bar-core" fill-opacity="0.75"><title>زرین: 4.6%</title></circle>
  <circle cx="565.7" cy="92" r="4.2" class="bar-core" fill-opacity="0.75"><title>هیوا: 0.9%</title></circle>
  <circle cx="522.9" cy="84" r="4.2" class="bar-core" fill-opacity="0.75"><title>امتیاز: -2.2%</title></circle>
  <circle cx="575.5" cy="90" r="4.2" class="bar-core" fill-opacity="0.75"><title>آوید: 1.6%</title></circle>
  <circle cx="523.4" cy="89" r="4.2" class="bar-core" fill-opacity="0.75"><title>پیروز: -2.1%</title></circle>
  <circle cx="560.2" cy="90" r="4.2" class="bar-core" fill-opacity="0.75"><title>رادان: 0.5%</title></circle>
  <circle cx="570.6" cy="84" r="4.2" class="bar-core" fill-opacity="0.75"><title>تیام: 1.3%</title></circle>
  <circle cx="552.4" cy="96" r="4.2" class="bar-core" fill-opacity="0.75"><title>کوانتوم: -0.0%</title></circle>
  <circle cx="548.9" cy="83" r="4.2" class="bar-core" fill-opacity="0.75"><title>ثهام: -0.3%</title></circle>
  <circle cx="543.2" cy="97" r="4.2" class="bar-core" fill-opacity="0.75"><title>یلدا: -0.7%</title></circle>
  <circle cx="587.1" cy="86" r="4.2" class="bar-core" fill-opacity="0.75"><title>برلیان: 2.5%</title></circle>
  <circle cx="566.1" cy="91" r="4.2" class="bar-core" fill-opacity="0.75"><title>عرش: 1.0%</title></circle>
  <circle cx="589.7" cy="82" r="4.2" class="bar-core" fill-opacity="0.75"><title>فراز: 2.7%</title></circle>
  <circle cx="544.8" cy="90" r="4.2" class="bar-core" fill-opacity="0.75"><title>اکستریم: -0.6%</title></circle>
  <circle cx="551.5" cy="81" r="4.2" class="bar-core" fill-opacity="0.75"><title>اکسیژن: -0.1%</title></circle>
  <circle cx="520.2" cy="85" r="4.2" class="bar-core" fill-opacity="0.75"><title>هم ارز: -2.4%</title></circle>
  <circle cx="513.3" cy="82" r="4.2" class="bar-core" fill-opacity="0.75"><title>جام سهند: -2.9%</title></circle>
  <circle cx="538.8" cy="95" r="4.2" class="bar-core" fill-opacity="0.75"><title>پادا: -1.0%</title></circle>
  <circle cx="554.7" cy="85" r="4.2" class="bar-core" fill-opacity="0.75"><title>ترمه: 0.1%</title></circle>
  <circle cx="573.4" cy="85" r="4.2" class="bar-core" fill-opacity="0.75"><title>همتا: 1.5%</title></circle>
  <circle cx="531.1" cy="90" r="4.2" class="bar-core" fill-opacity="0.75"><title>سهامدار: -1.6%</title></circle>
  <circle cx="533.4" cy="85" r="4.2" class="bar-core" fill-opacity="0.75"><title>سبزآبنوس: -1.4%</title></circle>
  <circle cx="552.8" cy="93" r="4.2" class="bar-core" fill-opacity="0.75"><title>یکم: -0.0%</title></circle>
  <circle cx="524.1" cy="93" r="4.2" class="bar-core" fill-opacity="0.75"><title>دیار: -2.1%</title></circle>
  <circle cx="531.5" cy="87" r="4.2" class="bar-core" fill-opacity="0.75"><title>آمیتیس: -1.6%</title></circle>
  <circle cx="522.3" cy="98" r="4.2" class="bar-core" fill-opacity="0.75"><title>ابتکار: -2.2%</title></circle>
  <circle cx="598.7" cy="80" r="4.2" class="bar-core" fill-opacity="0.75"><title>ثروین: 3.3%</title></circle>
  <circle cx="549.9" cy="99" r="4.2" class="bar-core" fill-opacity="0.75"><title>سها: -0.2%</title></circle>
  <circle cx="528.6" cy="91" r="4.2" class="bar-core" fill-opacity="0.75"><title>مروارید: -1.8%</title></circle>
  <circle cx="558.1" cy="99" r="4.2" class="bar-core" fill-opacity="0.75"><title>ویستا: 0.4%</title></circle>
  <circle cx="570.7" cy="100" r="4.2" class="bar-core" fill-opacity="0.75"><title>صدف: 1.3%</title></circle>
  <circle cx="529.9" cy="91" r="4.2" class="bar-core" fill-opacity="0.75"><title>رویش همراه: -1.7%</title></circle>
  <circle cx="477.5" cy="91" r="4.2" class="bar-core" fill-opacity="0.75"><title>ثروت ساز: -5.5%</title></circle>
  <circle cx="566.4" cy="85" r="4.2" class="bar-core" fill-opacity="0.75"><title>پرتو: 1.0%</title></circle>
  <circle cx="568.0" cy="96" r="4.2" class="bar-core" fill-opacity="0.75"><title>بزرگ: 1.1%</title></circle>
  <circle cx="556.6" cy="90" r="4.2" class="bar-core" fill-opacity="0.75"><title>جاودان: 0.3%</title></circle>
  <circle cx="713.4" cy="89" r="4.2" class="bar-core" fill-opacity="0.75"><title>سپینود: 11.6%</title></circle>
  <circle cx="504.4" cy="92" r="4.2" class="bar-core" fill-opacity="0.75"><title>درسا: -3.5%</title></circle>
  <circle cx="518.2" cy="88" r="4.2" class="bar-core" fill-opacity="0.75"><title>فرصت: -2.5%</title></circle>
  <circle cx="490.1" cy="89" r="4.2" class="bar-core" fill-opacity="0.75"><title>رونق: -4.6%</title></circle>
  <circle cx="504.4" cy="85" r="4.2" class="bar-core" fill-opacity="0.75"><title>آس: -3.5%</title></circle>
  <circle cx="611.1" cy="92" r="4.2" class="bar-core" fill-opacity="0.75"><title>ثنا: 4.2%</title></circle>
  <circle cx="528.7" cy="96" r="4.2" class="bar-core" fill-opacity="0.75"><title>هوشیار: -1.8%</title></circle>
  <circle cx="541.8" cy="95" r="4.2" class="bar-core" fill-opacity="0.75"><title>رخش: -0.8%</title></circle>
  <line x1="548.7" y1="72" x2="548.7" y2="108" class="edge hot"/>
  <text class="t-body" x="940" y="166" text-anchor="start">بخشی</text>
  <text class="t-small" x="940" y="184" text-anchor="start">۶۲ صندوق · میانه −۰.۵٪</text>
  <circle cx="141.2" cy="160" r="4.2" class="bar-src" fill-opacity="0.75"><title>پالایش: -29.8%</title></circle>
  <circle cx="580.7" cy="171" r="4.2" class="bar-src" fill-opacity="0.75"><title>دارونو: 2.0%</title></circle>
  <circle cx="551.8" cy="170" r="4.2" class="bar-src" fill-opacity="0.75"><title>سیمانو: -0.1%</title></circle>
  <circle cx="562.0" cy="156" r="4.2" class="bar-src" fill-opacity="0.75"><title>فارما کیان: 0.7%</title></circle>
  <circle cx="549.3" cy="164" r="4.2" class="bar-src" fill-opacity="0.75"><title>بنکوداریوش: -0.3%</title></circle>
  <circle cx="547.2" cy="153" r="4.2" class="bar-src" fill-opacity="0.75"><title>آذرین: -0.4%</title></circle>
  <circle cx="528.1" cy="155" r="4.2" class="bar-src" fill-opacity="0.75"><title>نمک: -1.8%</title></circle>
  <circle cx="538.1" cy="166" r="4.2" class="bar-src" fill-opacity="0.75"><title>استیل: -1.1%</title></circle>
  <circle cx="512.2" cy="157" r="4.2" class="bar-src" fill-opacity="0.75"><title>آلیاژ: -3.0%</title></circle>
  <circle cx="547.0" cy="167" r="4.2" class="bar-src" fill-opacity="0.75"><title>پتروآگاه: -0.4%</title></circle>
  <circle cx="502.1" cy="165" r="4.2" class="bar-src" fill-opacity="0.75"><title>مسگون: -3.7%</title></circle>
  <circle cx="605.0" cy="162" r="4.2" class="bar-src" fill-opacity="0.75"><title>اکتان: 3.8%</title></circle>
  <circle cx="549.6" cy="170" r="4.2" class="bar-src" fill-opacity="0.75"><title>بانکا: -0.2%</title></circle>
  <circle cx="550.0" cy="165" r="4.2" class="bar-src" fill-opacity="0.75"><title>بنکر: -0.2%</title></circle>
  <circle cx="525.8" cy="171" r="4.2" class="bar-src" fill-opacity="0.75"><title>پتروفارس: -2.0%</title></circle>
  <circle cx="563.9" cy="166" r="4.2" class="bar-src" fill-opacity="0.75"><title>بازبیمه: 0.8%</title></circle>
  <circle cx="549.7" cy="169" r="4.2" class="bar-src" fill-opacity="0.75"><title>پتروصبا: -0.2%</title></circle>
  <circle cx="550.4" cy="158" r="4.2" class="bar-src" fill-opacity="0.75"><title>بهین رو: -0.2%</title></circle>
  <circle cx="550.5" cy="153" r="4.2" class="bar-src" fill-opacity="0.75"><title>رسانا: -0.2%</title></circle>
  <circle cx="593.6" cy="154" r="4.2" class="bar-src" fill-opacity="0.75"><title>فارمانی: 2.9%</title></circle>
  <circle cx="542.3" cy="163" r="4.2" class="bar-src" fill-opacity="0.75"><title>فرا الگوریتم: -0.8%</title></circle>
  <circle cx="546.2" cy="171" r="4.2" class="bar-src" fill-opacity="0.75"><title>معدن: -0.5%</title></circle>
  <circle cx="530.5" cy="165" r="4.2" class="bar-src" fill-opacity="0.75"><title>پتروداریوش: -1.6%</title></circle>
  <circle cx="562.9" cy="157" r="4.2" class="bar-src" fill-opacity="0.75"><title>بانکپاد: 0.7%</title></circle>
  <circle cx="557.2" cy="159" r="4.2" class="bar-src" fill-opacity="0.75"><title>اتوداریوش: 0.3%</title></circle>
  <circle cx="506.3" cy="171" r="4.2" class="bar-src" fill-opacity="0.75"><title>سورنافود: -3.4%</title></circle>
  <circle cx="545.6" cy="164" r="4.2" class="bar-src" fill-opacity="0.75"><title>سیمان: -0.5%</title></circle>
  <circle cx="554.4" cy="165" r="4.2" class="bar-src" fill-opacity="0.75"><title>خودران: 0.1%</title></circle>
  <circle cx="557.4" cy="155" r="4.2" class="bar-src" fill-opacity="0.75"><title>بانکو: 0.3%</title></circle>
  <circle cx="567.0" cy="154" r="4.2" class="bar-src" fill-opacity="0.75"><title>فلزفارابی: 1.0%</title></circle>
  <circle cx="548.9" cy="164" r="4.2" class="bar-src" fill-opacity="0.75"><title>مزه: -0.3%</title></circle>
  <circle cx="543.4" cy="163" r="4.2" class="bar-src" fill-opacity="0.75"><title>سمان: -0.7%</title></circle>
  <circle cx="567.6" cy="156" r="4.2" class="bar-src" fill-opacity="0.75"><title>اتوآگاه: 1.1%</title></circle>
  <circle cx="541.5" cy="153" r="4.2" class="bar-src" fill-opacity="0.75"><title>رویین: -0.8%</title></circle>
  <circle cx="551.3" cy="165" r="4.2" class="bar-src" fill-opacity="0.75"><title>سیمانا: -0.1%</title></circle>
  <circle cx="541.6" cy="164" r="4.2" class="bar-src" fill-opacity="0.75"><title>نفتوداریوش: -0.8%</title></circle>
  <circle cx="549.1" cy="167" r="4.2" class="bar-src" fill-opacity="0.75"><title>یوتیلیتی: -0.3%</title></circle>
  <circle cx="532.0" cy="159" r="4.2" class="bar-src" fill-opacity="0.75"><title>آلکان: -1.5%</title></circle>
  <circle cx="516.7" cy="156" r="4.2" class="bar-src" fill-opacity="0.75"><title>بانکیا: -2.6%</title></circle>
  <circle cx="541.0" cy="153" r="4.2" class="bar-src" fill-opacity="0.75"><title>پتروسورین: -0.9%</title></circle>
  <circle cx="544.2" cy="162" r="4.2" class="bar-src" fill-opacity="0.75"><title>اتوکار: -0.6%</title></circle>
  <circle cx="442.5" cy="162" r="4.2" class="bar-src" fill-opacity="0.75"><title>تخت گاز: -8.0%</title></circle>
  <circle cx="522.9" cy="153" r="4.2" class="bar-src" fill-opacity="0.75"><title>چاشنی: -2.2%</title></circle>
  <circle cx="489.5" cy="167" r="4.2" class="bar-src" fill-opacity="0.75"><title>چتر: -4.6%</title></circle>
  <circle cx="520.5" cy="159" r="4.2" class="bar-src" fill-opacity="0.75"><title>نبات: -2.4%</title></circle>
  <circle cx="560.8" cy="166" r="4.2" class="bar-src" fill-opacity="0.75"><title>پناه: 0.6%</title></circle>
  <circle cx="470.1" cy="165" r="4.2" class="bar-src" fill-opacity="0.75"><title>لذیذ: -6.0%</title></circle>
  <circle cx="551.8" cy="169" r="4.2" class="bar-src" fill-opacity="0.75"><title>پتروپاداش: -0.1%</title></circle>
  <circle cx="495.7" cy="159" r="4.2" class="bar-src" fill-opacity="0.75"><title>طعام: -4.2%</title></circle>
  <circle cx="538.2" cy="159" r="4.2" class="bar-src" fill-opacity="0.75"><title>فلزا: -1.1%</title></circle>
  <circle cx="518.0" cy="163" r="4.2" class="bar-src" fill-opacity="0.75"><title>سیمانیا: -2.5%</title></circle>
  <circle cx="554.9" cy="160" r="4.2" class="bar-src" fill-opacity="0.75"><title>ناوگان: 0.1%</title></circle>
  <circle cx="489.5" cy="169" r="4.2" class="bar-src" fill-opacity="0.75"><title>متال: -4.6%</title></circle>
  <circle cx="556.7" cy="157" r="4.2" class="bar-src" fill-opacity="0.75"><title>پتروما: 0.3%</title></circle>
  <circle cx="532.7" cy="152" r="4.2" class="bar-src" fill-opacity="0.75"><title>ولتاژ: -1.5%</title></circle>
  <circle cx="503.8" cy="166" r="4.2" class="bar-src" fill-opacity="0.75"><title>نیروانا: -3.6%</title></circle>
  <circle cx="585.6" cy="152" r="4.2" class="bar-src" fill-opacity="0.75"><title>بانکدار: 2.4%</title></circle>
  <circle cx="600.4" cy="171" r="4.2" class="bar-src" fill-opacity="0.75"><title>تراست: 3.4%</title></circle>
  <circle cx="512.8" cy="172" r="4.2" class="bar-src" fill-opacity="0.75"><title>امگا: -2.9%</title></circle>
  <circle cx="516.2" cy="158" r="4.2" class="bar-src" fill-opacity="0.75"><title>پتروآبان: -2.7%</title></circle>
  <circle cx="549.6" cy="155" r="4.2" class="bar-src" fill-opacity="0.75"><title>دلتا: -0.2%</title></circle>
  <circle cx="532.7" cy="155" r="4.2" class="bar-src" fill-opacity="0.75"><title>پولاد: -1.5%</title></circle>
  <line x1="545.9" y1="144" x2="545.9" y2="180" class="edge hot"/>
  <text class="t-body" x="940" y="238" text-anchor="start">شاخصی</text>
  <text class="t-small" x="940" y="256" text-anchor="start">۸ صندوق · میانه −۱.۱٪</text>
  <circle cx="558.7" cy="229" r="4.2" class="bar-serve" fill-opacity="0.75"><title>همسنگ: 0.4%</title></circle>
  <circle cx="544.8" cy="240" r="4.2" class="bar-serve" fill-opacity="0.75"><title>هم وزن: -0.6%</title></circle>
  <circle cx="563.4" cy="243" r="4.2" class="bar-serve" fill-opacity="0.75"><title>آرام: 0.8%</title></circle>
  <circle cx="519.6" cy="238" r="4.2" class="bar-serve" fill-opacity="0.75"><title>فیروزه: -2.4%</title></circle>
  <circle cx="548.2" cy="228" r="4.2" class="bar-serve" fill-opacity="0.75"><title>کاردان: -0.3%</title></circle>
  <circle cx="511.4" cy="230" r="4.2" class="bar-serve" fill-opacity="0.75"><title>هم تراز: -3.0%</title></circle>
  <circle cx="525.4" cy="236" r="4.2" class="bar-serve" fill-opacity="0.75"><title>وبازار: -2.0%</title></circle>
  <circle cx="531.0" cy="234" r="4.2" class="bar-serve" fill-opacity="0.75"><title>هوشمند: -1.6%</title></circle>
  <line x1="537.9" y1="216" x2="537.9" y2="252" class="edge hot"/>
  <text class="t-body" x="940" y="310" text-anchor="start">اهرمی</text>
  <text class="t-small" x="940" y="328" text-anchor="start">۹ صندوق · میانه −۱۸.۶٪</text>
  <circle cx="294.8" cy="308" r="4.2" class="bar-store" fill-opacity="0.75"><title>اهرم: -18.7%</title></circle>
  <circle cx="296.4" cy="311" r="4.2" class="bar-store" fill-opacity="0.75"><title>موج: -18.6%</title></circle>
  <circle cx="311.8" cy="305" r="4.2" class="bar-store" fill-opacity="0.75"><title>توان: -17.5%</title></circle>
  <circle cx="288.5" cy="298" r="4.2" class="bar-store" fill-opacity="0.75"><title>بیدار: -19.2%</title></circle>
  <circle cx="322.1" cy="314" r="4.2" class="bar-store" fill-opacity="0.75"><title>جهش: -16.7%</title></circle>
  <circle cx="295.6" cy="304" r="4.2" class="bar-store" fill-opacity="0.75"><title>نارنج اهرم: -18.7%</title></circle>
  <circle cx="289.2" cy="309" r="4.2" class="bar-store" fill-opacity="0.75"><title>شتاب: -19.1%</title></circle>
  <circle cx="579.0" cy="299" r="4.2" class="bar-store" fill-opacity="0.75"><title>دوایکس: 1.9%</title></circle>
  <circle cx="418.7" cy="311" r="4.2" class="bar-store" fill-opacity="0.75"><title>پیشران: -9.7%</title></circle>
  <line x1="296.4" y1="288" x2="296.4" y2="324" class="edge hot"/>
  <text class="t-small" x="296.3" y="340" text-anchor="middle">۷ از ۹ صندوق اهرمی ≈ −۱۸٪: خطای ساختاری NAV، نه حباب</text>
  <text class="t-small" x="92.9" y="76" text-anchor="end">دارا یکم</text>
  <text class="t-small" x="149.2" y="148" text-anchor="end">پالایش</text>
  <text class="t-small" x="415" y="390" text-anchor="middle">خط نارنجی: میانه‌ی هر گروه</text>
</svg>

*شکل ۱ — حباب همه‌ی صندوق‌ها به تفکیک نوع (داده‌ی واقعی). صندوق‌های سهامی، بخشی و شاخصی دور صفر جمع شده‌اند. صندوق‌های اهرمی همگی حدود −۱۸٪ هستند: یک خطای ساختاری، نه یک فرصت خرید.*


### یافته: NAV صندوق‌های اهرمی قابل مقایسه با قیمت نیست

در داده‌ی واقعی، **۷ صندوق از ۹ صندوق اهرمی** (اهرم، شتاب، بیدار، موج، نارنج اهرم، توان، جهش) «حبابی» بین −۱۶٫۷٪ و −۱۹٫۲٪ دارند. این هم‌خوانی بین صندوق‌هایی با مدیران و دارایی‌های متفاوت نشان می‌دهد که علت در **تعریف NAV** است، نه در بازار.

صندوق اهرمی دو نوع واحد دارد: **واحد ممتاز** (سرمایه‌گذار با سود تضمین‌شده) و **واحد عادی** (همان واحدی که در بورس معامله می‌شود و بازده اهرمی دارد). NAV منتشرشده در TSETMC با ارزش واحد عادی برابر نیست، پس مقایسه‌ی قیمت واحد عادی با آن معنی ندارد.

> **⚠ تصمیم**
>
> `nav_premium()` برای صندوق‌های اهرمی **`null`** برمی‌گرداند، و پنل به‌جای عدد، «قابل محاسبه نیست» نمایش می‌دهد. نمایش −۱۸٪ به معامله‌گر یعنی نشان دادن فرصت خریدی که وجود ندارد. خالص دارایی این صندوق‌ها هم با احتیاط و با برچسب «تقریبی» نمایش داده می‌شود.

**دو صندوق «دارا یکم» (−۳۴٪) و «پالایش» (−۳۰٪)** هم تخفیف بزرگی دارند، اما این تخفیف واقعی است. این دو ETF واگذاری سهام دولتی هستند و سال‌هاست زیر NAV معامله می‌شوند. آن‌ها حذف نمی‌شوند، ولی شاخص کلان بازار از **میانه** ساخته می‌شود تا این دو صندوق بزرگ تصویر کلی را منحرف نکنند (`robust_center`).

## ورود پول حقیقی و ارزش تخمینی

TSETMC در طول روز فقط **حجم** معاملات حقیقی و حقوقی را می‌دهد، نه ارزش ریالی آن‌ها را. ارزش درون‌روز این‌طور تخمین زده می‌شود:

```text
ارزش خرید حقیقی ≈ حجم خرید حقیقی × (ارزش کل معاملات ÷ حجم کل معاملات)
```

یعنی حجم ضرب در میانگین موزون قیمت امروز. پس از بسته شدن بازار، مقدار **رسمی** از `GetClientTypeHistory` جایگزین می‌شود. هر دو نسخه نگه داشته می‌شوند و پرچم `FLOW_VALUE_ESTIMATED` نسخه‌ی تخمینی را مشخص می‌کند. نمودار ورود پول روزانه، روزهای گذشته را با مقدار رسمی و امروز را با علامت «تخمینی» نشان می‌دهد.

> **بررسی صحت روی داده‌ی واقعی**
>
> در تاریخچه‌ی رسمی «اطلس» برای ۱ مهر: خرید حقیقی ۷٬۷۶۸٬۷۴۴ + خرید حقوقی ۱٬۸۱۶٬۶۱۴ = **۹٬۵۸۵٬۳۵۸** واحد، که دقیقاً برابر حجم کل معاملات همان روز است. بررسی `client_volume_mismatch` در [کیفیت داده](04-data-quality.md) روی همین اتحاد بنا شده است.

## بازده دوره‌ای و تقویم شمسی

بازده‌ها بر پایه‌ی **قیمت پایانی رسمی** و **پنجره‌های تقویمی** محاسبه می‌شوند (۷، ۳۰ و ۹۱ روز). مبدأ هر پنجره آخرین روز معاملاتی **قبل از یا برابر با** تاریخ مبدأ است، پس تعطیلات دقت را کم نمی‌کنند.

«از ابتدای سال» یعنی از **۱ فروردین**، نه ۱ ژانویه. سال مالی بیشتر صندوق‌ها و گزارش‌های بازار سرمایه‌ی ایران شمسی است. تبدیل تاریخ با الگوریتم چرخه‌ی ۳۳ ساله‌ی تقویم جلالی در `domain/jalali.py` انجام می‌شود (بدون وابستگی خارجی، با تست روی نوروزهای ۱۴۰۲ تا ۱۴۰۶ و سال کبیسه‌ی ۱۴۰۳).

> **چرا بازده بر پایه‌ی قیمت و نه NAV؟**
>
> تاریخچه‌ی روزانه‌ی NAV در TSETMC وجود ندارد و فقط NAV لحظه‌ای منتشر می‌شود. بازده قیمتی همان چیزی است که معامله‌گر واقعاً به دست آورده است. سرویس از روز اول جمع‌آوری، NAV پایان هر روز را در `fund_eod` ذخیره می‌کند، پس بازده NAV به‌تدریج قابل محاسبه می‌شود.

## جمع‌بندی در سطح بازار

| شاخص کلان | روش تجمیع | چرا |
|---|---|---|
| خالص دارایی کل | جمع | مقداری جمع‌پذیر است |
| ورود پول حقیقی کل | جمع | مقداری جمع‌پذیر است |
| حباب بازار | **میانه**، بدون اهرمی‌ها | در برابر صندوق‌های خاص (دارا یکم، پالایش) مقاوم است |
| حباب وزنی بازار | میانگین وزنی با خالص دارایی، بدون اهرمی‌ها | نشان می‌دهد پول بازار در کجا نشسته است (بخش بعد) |
| پهنای بازار | تعداد صندوق‌های مثبت، منفی و بدون تغییر | میانگین وزنی را چند صندوق بزرگ تعیین می‌کنند؛ پهنا وضعیت عمومی را نشان می‌دهد |

### حباب: میانه یا وزنی؟ {#حباب-میانه-یا-وزنی}

این دو عدد به دو سؤال متفاوت جواب می‌دهند و پنل هر دو را کنار هم نشان می‌دهد:

- **میانه:** صندوق «معمولی» چقدر گران یا ارزان است؟ برای معامله‌گری که دنبال صندوق برای خرید است.
- **وزنی (با خالص دارایی):** یک ریال سرمایه‌گذاری‌شده در این بازار، به‌طور متوسط با چه حبابی خریده شده است؟ برای مدیر پرتفوی که کل بازار را نگاه می‌کند.

روی داده‌ی واقعی پایان جلسه‌ی ۱ مهر ۱۴۰۵ فاصله‌ی این دو خیلی زیاد بود:


- **−۰٫۵٪** — میانه‌ی حباب ۱۵۰ صندوق
- ⚠ **−۱۱٫۸٪** — حباب وزنی
- **۳۶٫۶٪** — سهم پالایش و دارا یکم از خالص دارایی
- **−۰٫۵٪** — حباب وزنی بدون آن دو صندوق


دو صندوق بزرگ **پالایش** (−۲۹٫۸٪، ۲۱٫۶٪ کل دارایی) و **دارا یکم** (−۳۳٫۹٪، ۱۵٪ کل دارایی) به‌تنهایی عدد وزنی را پایین می‌کشند. بدون آن‌ها، حباب وزنی دقیقاً برابر میانه است. پس «حباب وزنی −۱۲٪» یعنی «این دو صندوق خصوصی‌سازی با تخفیف معامله می‌شوند»، نه اینکه «بازار صندوق‌ها ۱۲٪ ارزان است». به همین دلیل کاشی اصلی پنل میانه را نشان می‌دهد و عدد وزنی کنار آن آمده است. نمودار «حباب بازار در طول زمان» هر دو خط را رسم می‌کند: اگر فاصله‌ی آن‌ها تغییر کند، رفتار صندوق‌های بزرگ از بقیه‌ی بازار جدا شده است.

تاریخچه‌ی این نمودار از `fund_eod` ساخته می‌شود (NAV پایانی هر روز از داده‌ی دقیقه‌ای). TSETMC تاریخچه‌ی NAV نمی‌دهد، پس سری از اولین روزی که سرویس داده گرفته شروع می‌شود و هر جلسه یک نقطه اضافه می‌شود.

## پیاده‌سازی

- **SQL فقط داده را بازیابی می‌کند**، با `FINAL`، `LIMIT 1 BY` و `argMaxIf` روی حداکثر چند صد هزار ردیف. **پایتون محاسبه می‌کند** (`analytics/service.py` و `domain/metrics.py`)، چون فرمول‌ها در پایتون تست واحد دارند و مجموعه‌ی نتیجه کوچک است: یک ردیف برای هر صندوق.
- جدول `fund_eod` با یک materialized view آخرین وضعیت هر صندوق در هر روز را نگه می‌دارد. فقط تجمیع‌هایی از نوع «آخرین مقدار» (`argMax`) استفاده شده‌اند، چون در برابر ردیف‌های تکراری (replay، forward-fill) مقاوم‌اند. تجمیع `sum` روی منبع `ReplacingMergeTree` تکراری‌ها را دو بار می‌شمارد.
- زمان پاسخ روی داده‌ی واقعی (۱۵۹ صندوق، ۴۹ هزار ردیف تاریخچه) **بدون کش** زیر ۹۰ میلی‌ثانیه است. کش (ADR 0006) این را برای بقیه‌ی درخواست‌های هر دقیقه به چند میلی‌ثانیه می‌رساند.
