import { useState, useRef, useEffect } from "react";
import { CurrencyGbp, CaretDown, Check } from "@phosphor-icons/react";

const CURRENCIES = [
  { code: "GBP", symbol: "£", name: "British Pound", flag: "🇬🇧" },
  { code: "USD", symbol: "$", name: "US Dollar", flag: "🇺🇸" },
  { code: "EUR", symbol: "€", name: "Euro", flag: "🇪🇺" },
  { code: "AED", symbol: "د.إ", name: "UAE Dirham", flag: "🇦🇪" },
  { code: "SAR", symbol: "﷼", name: "Saudi Riyal", flag: "🇸🇦" },
  { code: "JPY", symbol: "¥", name: "Japanese Yen", flag: "🇯🇵" },
  { code: "CNY", symbol: "¥", name: "Chinese Yuan", flag: "🇨🇳" },
  { code: "INR", symbol: "₹", name: "Indian Rupee", flag: "🇮🇳" },
  { code: "AUD", symbol: "A$", name: "Australian Dollar", flag: "🇦🇺" },
  { code: "CAD", symbol: "C$", name: "Canadian Dollar", flag: "🇨🇦" },
  { code: "CHF", symbol: "CHF", name: "Swiss Franc", flag: "🇨🇭" },
  { code: "SGD", symbol: "S$", name: "Singapore Dollar", flag: "🇸🇬" },
  { code: "KRW", symbol: "₩", name: "Korean Won", flag: "🇰🇷" },
  { code: "THB", symbol: "฿", name: "Thai Baht", flag: "🇹🇭" },
  { code: "MYR", symbol: "RM", name: "Malaysian Ringgit", flag: "🇲🇾" },
  { code: "TRY", symbol: "₺", name: "Turkish Lira", flag: "🇹🇷" },
  { code: "BRL", symbol: "R$", name: "Brazilian Real", flag: "🇧🇷" },
  { code: "RUB", symbol: "₽", name: "Russian Ruble", flag: "🇷🇺" },
];

// Approximate rates from GBP
const RATES = {
  GBP: 1.0, USD: 1.27, EUR: 1.17, AED: 4.67, SAR: 4.76,
  JPY: 192.5, CNY: 9.21, KRW: 1750, INR: 106.5, BRL: 7.35,
  RUB: 118.0, AUD: 1.95, CAD: 1.73, CHF: 1.12, SGD: 1.71,
  THB: 44.2, MYR: 5.65, TRY: 41.5,
};

export function useCurrency() {
  const [currency, setCurrencyState] = useState(() => {
    const stored = localStorage.getItem("booking_currency");
    return stored && RATES[stored] ? stored : "GBP";
  });

  const setCurrency = (code) => {
    if (RATES[code]) {
      setCurrencyState(code);
      localStorage.setItem("booking_currency", code);
    }
  };

  const convert = (gbpAmount) => {
    const rate = RATES[currency] || 1;
    return Math.round(gbpAmount * rate * 100) / 100;
  };

  const format = (gbpAmount) => {
    const curr = CURRENCIES.find(c => c.code === currency) || CURRENCIES[0];
    const converted = convert(gbpAmount);
    // Format based on currency
    if (["JPY", "KRW"].includes(currency)) {
      return `${curr.symbol}${Math.round(converted).toLocaleString()}`;
    }
    return `${curr.symbol}${converted.toFixed(0)}`;
  };

  return { currency, setCurrency, convert, format, currencies: CURRENCIES, symbol: (CURRENCIES.find(c => c.code === currency) || CURRENCIES[0]).symbol };
}

export function CurrencySelector({ currency, setCurrency, currencies }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const current = currencies.find(c => c.code === currency) || currencies[0];

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-sm px-2 py-1 rounded-md hover:bg-white/10 transition-colors"
        data-testid="currency-selector"
        aria-label="Select currency"
      >
        <CurrencyGbp size={15} />
        <span>{current.code}</span>
        <CaretDown size={12} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 bg-white rounded-lg shadow-xl border border-gray-200 py-1 min-w-[200px] z-50 max-h-[320px] overflow-y-auto" data-testid="currency-dropdown">
          {currencies.map(c => (
            <button key={c.code} onClick={() => { setCurrency(c.code); setOpen(false); }}
              className={`w-full flex items-center gap-2.5 px-3 py-2 text-sm hover:bg-gray-50 transition-colors ${c.code === currency ? "bg-gray-50 font-semibold" : ""}`}
              data-testid={`currency-option-${c.code}`}>
              <span className="text-base">{c.flag}</span>
              <span className="text-slate-800 flex-1 text-left">{c.code}</span>
              <span className="text-slate-400 text-xs">{c.symbol}</span>
              {c.code === currency && <Check size={14} weight="bold" className="text-emerald-600" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
