// Persian labels for the validator's QualityFlag bits (src/tsetmc_viewer/domain/quality.py).
// kind: "repair" = the pipeline fixed or filled something, "info" = expected caveat,
// "warn" = the value should be read with care.

export type FlagKind = "info" | "repair" | "warn";

export const FLAGS: Record<string, { fa: string; kind: FlagKind; hint: string }> = {
  NAV_MISSING: { fa: "NAV ناموجود", kind: "warn", hint: "سرویس NAV پاسخی نداد؛ حباب محاسبه نشد." },
  NAV_STALE: { fa: "NAV قدیمی", kind: "info", hint: "NAV منتشرشده از آستانه‌ی تازگی قدیمی‌تر است (عادی بعد از بازار)." },
  CLIENT_TYPE_MISSING: { fa: "بدون حقیقی/حقوقی", kind: "warn", hint: "نماد در داده‌ی حقیقی/حقوقی نبود؛ جریان پول صفر در نظر گرفته شد." },
  FLOW_VALUE_ESTIMATED: { fa: "جریان ریالی برآوردی", kind: "info", hint: "ارزش ریالی جریان پول = حجم × میانگین قیمت (TSETMC ارزش رسمی درون‌روز نمی‌دهد)." },
  NO_TRADES: { fa: "بدون معامله", kind: "info", hint: "هنوز معامله‌ای نشده؛ قیمت‌ها قیمت مرجع هستند." },
  PRICE_OUT_OF_RANGE: { fa: "قیمت خارج از دامنه", kind: "warn", hint: "قیمت بیرون از دامنه‌ی مجاز روز بود؛ اگر ممکن بود مقدار دقیقه‌ی قبل جایگزین شد." },
  CUMULATIVE_DECREASE: { fa: "کاهش مقدار تجمعی", kind: "repair", hint: "حجم یا ارزش تجمعی کم شد؛ مقدار قبلی نگه داشته شد." },
  FORWARD_FILLED: { fa: "تکمیل از دقیقه‌ی قبل", kind: "repair", hint: "ردیف در این دقیقه نیامد و از دقیقه‌ی قبل منتقل شد." },
  STALE_QUOTE: { fa: "فید متوقف", kind: "warn", hint: "کل دیده‌بان بازار به‌روز نشده بود." },
  CLIENT_VOLUME_MISMATCH: { fa: "ناهمخوانی حجم", kind: "warn", hint: "جمع خرید حقیقی و حقوقی با حجم معاملات برابر نبود." },
  NAV_CARRIED: { fa: "NAV منتقل‌شده", kind: "repair", hint: "NAV این دقیقه نیامد؛ آخرین NAV معتبر استفاده شد." },
  NAV_JUMP: { fa: "جهش NAV", kind: "warn", hint: "NAV بیش از آستانه‌ی معقول بین دو دقیقه تغییر کرد." },
  RANGE_REPAIRED: { fa: "اصلاح کف/سقف", kind: "repair", hint: "کمینه/بیشینه‌ی روز بازسازی شد تا اولین و آخرین قیمت را دربر بگیرد." },
};

export const KIND_FA: Record<FlagKind, string> = { info: "اطلاع", repair: "اصلاح‌شده", warn: "هشدار" };

export const flagFa = (name: string) => FLAGS[name]?.fa ?? name;
export const flagKind = (name: string): FlagKind => FLAGS[name]?.kind ?? "warn";

/** data_quality_log.check → Persian (see domain/quality.py: Check). */
export const CHECK_FA: Record<string, string> = {
  missing_fund: "صندوق در پاسخ نبود",
  gap: "دقیقه‌ی جاافتاده",
  price_out_of_band: "قیمت خارج از دامنه",
  ohlc_inconsistent: "ناسازگاری کف/سقف",
  cumulative_decrease: "کاهش مقدار تجمعی",
  client_volume_mismatch: "ناهمخوانی حجم حقیقی/حقوقی",
  nav_missing: "NAV ناموجود",
  nav_stale: "NAV قدیمی",
  nav_jump: "جهش NAV",
  feed_stale: "توقف فید بازار",
};

/** data_quality_log.action → what the pipeline did about it. */
export const ACTION_FA: Record<string, string> = {
  flagged: "فقط پرچم‌گذاری",
  kept: "نگه داشته شد",
  kept_previous: "مقدار قبلی حفظ شد",
  replaced_with_previous: "با مقدار قبلی جایگزین شد",
  carried_forward: "آخرین مقدار معتبر منتقل شد",
  forward_filled: "از دقیقه‌ی قبل تکمیل شد",
  recomputed: "بازمحاسبه شد",
  dropped: "کنار گذاشته شد",
  none: "بدون اقدام",
};
