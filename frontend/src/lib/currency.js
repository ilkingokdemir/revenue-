/**
 * Currency helper — derives the correct symbol + locale from a city name or
 * ISO currency code. Keeps all Market Robot charts/tables consistent when the
 * user scans non-UK cities (Zurich → CHF, Paris → €, Tokyo → ¥ etc.).
 */

// Major city → { symbol, code, locale }
const CITY_CURRENCY_MAP = {
  london: { symbol: "£", code: "GBP", locale: "en-GB" },
  manchester: { symbol: "£", code: "GBP", locale: "en-GB" },
  edinburgh: { symbol: "£", code: "GBP", locale: "en-GB" },
  dublin: { symbol: "€", code: "EUR", locale: "en-IE" },
  paris: { symbol: "€", code: "EUR", locale: "fr-FR" },
  berlin: { symbol: "€", code: "EUR", locale: "de-DE" },
  munich: { symbol: "€", code: "EUR", locale: "de-DE" },
  amsterdam: { symbol: "€", code: "EUR", locale: "nl-NL" },
  rome: { symbol: "€", code: "EUR", locale: "it-IT" },
  madrid: { symbol: "€", code: "EUR", locale: "es-ES" },
  barcelona: { symbol: "€", code: "EUR", locale: "es-ES" },
  vienna: { symbol: "€", code: "EUR", locale: "de-AT" },
  lisbon: { symbol: "€", code: "EUR", locale: "pt-PT" },
  athens: { symbol: "€", code: "EUR", locale: "el-GR" },
  zurich: { symbol: "CHF ", code: "CHF", locale: "de-CH" },
  geneva: { symbol: "CHF ", code: "CHF", locale: "fr-CH" },
  basel: { symbol: "CHF ", code: "CHF", locale: "de-CH" },
  oslo: { symbol: "kr ", code: "NOK", locale: "nb-NO" },
  stockholm: { symbol: "kr ", code: "SEK", locale: "sv-SE" },
  copenhagen: { symbol: "kr ", code: "DKK", locale: "da-DK" },
  istanbul: { symbol: "₺", code: "TRY", locale: "tr-TR" },
  ankara: { symbol: "₺", code: "TRY", locale: "tr-TR" },
  "new york": { symbol: "$", code: "USD", locale: "en-US" },
  "los angeles": { symbol: "$", code: "USD", locale: "en-US" },
  chicago: { symbol: "$", code: "USD", locale: "en-US" },
  miami: { symbol: "$", code: "USD", locale: "en-US" },
  toronto: { symbol: "CA$ ", code: "CAD", locale: "en-CA" },
  vancouver: { symbol: "CA$ ", code: "CAD", locale: "en-CA" },
  sydney: { symbol: "AU$ ", code: "AUD", locale: "en-AU" },
  melbourne: { symbol: "AU$ ", code: "AUD", locale: "en-AU" },
  auckland: { symbol: "NZ$ ", code: "NZD", locale: "en-NZ" },
  tokyo: { symbol: "¥", code: "JPY", locale: "ja-JP" },
  osaka: { symbol: "¥", code: "JPY", locale: "ja-JP" },
  beijing: { symbol: "¥", code: "CNY", locale: "zh-CN" },
  shanghai: { symbol: "¥", code: "CNY", locale: "zh-CN" },
  "hong kong": { symbol: "HK$ ", code: "HKD", locale: "en-HK" },
  singapore: { symbol: "S$ ", code: "SGD", locale: "en-SG" },
  bangkok: { symbol: "฿", code: "THB", locale: "th-TH" },
  dubai: { symbol: "AED ", code: "AED", locale: "en-AE" },
  "abu dhabi": { symbol: "AED ", code: "AED", locale: "en-AE" },
  johannesburg: { symbol: "R", code: "ZAR", locale: "en-ZA" },
  "cape town": { symbol: "R", code: "ZAR", locale: "en-ZA" },
  "mexico city": { symbol: "MX$ ", code: "MXN", locale: "es-MX" },
  "sao paulo": { symbol: "R$ ", code: "BRL", locale: "pt-BR" },
  "rio de janeiro": { symbol: "R$ ", code: "BRL", locale: "pt-BR" },
  moscow: { symbol: "₽", code: "RUB", locale: "ru-RU" },
  mumbai: { symbol: "₹", code: "INR", locale: "en-IN" },
  delhi: { symbol: "₹", code: "INR", locale: "en-IN" },
};

// UK/London postcode prefixes (E1, NW1, EC2N etc.) → GBP
const UK_POSTCODE_RE = /^(E|EC|N|NW|SE|SW|W|WC|BR|CR|DA|EN|HA|IG|KT|RM|SM|TW|UB|WD)\d/i;

const DEFAULT = { symbol: "£", code: "GBP", locale: "en-GB" };

export function getCurrencyInfo(cityOrLocation) {
  if (!cityOrLocation) return DEFAULT;
  const raw = String(cityOrLocation).trim();
  // Postcode-ish prefix → GBP (UK)
  if (UK_POSTCODE_RE.test(raw)) return DEFAULT;
  const key = raw.toLowerCase();
  // Exact match
  if (CITY_CURRENCY_MAP[key]) return CITY_CURRENCY_MAP[key];
  // Find any map key that appears in the location string
  for (const cityKey of Object.keys(CITY_CURRENCY_MAP)) {
    if (key.includes(cityKey)) return CITY_CURRENCY_MAP[cityKey];
  }
  // Country-code heuristic
  const countryHints = {
    uk: DEFAULT, "united kingdom": DEFAULT, england: DEFAULT,
    france: CITY_CURRENCY_MAP.paris, germany: CITY_CURRENCY_MAP.berlin,
    switzerland: CITY_CURRENCY_MAP.zurich, netherlands: CITY_CURRENCY_MAP.amsterdam,
    italy: CITY_CURRENCY_MAP.rome, spain: CITY_CURRENCY_MAP.madrid,
    turkey: CITY_CURRENCY_MAP.istanbul, türkiye: CITY_CURRENCY_MAP.istanbul,
    usa: CITY_CURRENCY_MAP["new york"], "united states": CITY_CURRENCY_MAP["new york"],
    japan: CITY_CURRENCY_MAP.tokyo, china: CITY_CURRENCY_MAP.beijing,
    india: CITY_CURRENCY_MAP.mumbai,
  };
  for (const k of Object.keys(countryHints)) {
    if (key.includes(k)) return countryHints[k];
  }
  return DEFAULT;
}

export function formatCurrency(value, cityOrLocation, { decimals = 0 } = {}) {
  const { symbol, locale } = getCurrencyInfo(cityOrLocation);
  return symbol + (Number(value) || 0).toLocaleString(locale, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** Returns a memoized formatter bound to a given city. */
export function makeCurrencyFormatter(cityOrLocation) {
  const info = getCurrencyInfo(cityOrLocation);
  return {
    info,
    /** Full number: CHF 1,250 */
    format: (v, decimals = 0) =>
      info.symbol + (Number(v) || 0).toLocaleString(info.locale, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      }),
    /** Short (for chart labels): CHF 120 */
    short: (v) => info.symbol + Math.round(Number(v) || 0),
  };
}
