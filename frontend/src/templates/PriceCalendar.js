import { useEffect, useState, useMemo } from "react";
import axios from "axios";
import { CaretLeft, CaretRight, CalendarBlank, X } from "@phosphor-icons/react";
import { useLanguage } from "../i18n/LanguageContext";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const iso = (d) => d.toISOString().split("T")[0];
const addMonths = (ym, n) => { const [y, m] = ym.split("-").map(Number); const d = new Date(Date.UTC(y, m - 1 + n, 1)); return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`; };

function useMonth(propertyId, ym, adults) {
  const [data, setData] = useState(null);
  useEffect(() => {
    let live = true;
    axios.get(`${API}/booking/price-calendar/${propertyId}?month=${ym}&adults=${adults}`)
      .then(({ data: d }) => live && setData(d)).catch(() => live && setData({ days: [] }));
    return () => { live = false; };
  }, [propertyId, ym, adults]);
  return data;
}

function MonthGrid({ t, data, ym, checkIn, checkOut, hover, setHover, onPick, lang }) {
  const [y, m] = ym.split("-").map(Number);
  const first = new Date(Date.UTC(y, m - 1, 1));
  const lead = (first.getUTCDay() + 6) % 7;
  const days = data?.days || [];
  const byDate = useMemo(() => Object.fromEntries(days.map((d) => [d.date, d])), [days]);
  const label = first.toLocaleDateString(lang === "tr" ? "tr-TR" : lang === "de" ? "de-DE" : "en-GB", { month: "long", year: "numeric", timeZone: "UTC" });
  const dow = lang === "tr" ? ["Pt", "Sa", "Ça", "Pe", "Cu", "Ct", "Pz"] : lang === "de" ? ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"] : ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];
  const rangeEnd = checkOut || hover;
  const inRange = (d) => checkIn && rangeEnd && d > checkIn && d < rangeEnd;
  const cells = [];
  for (let i = 0; i < lead; i++) cells.push(null);
  const total = new Date(Date.UTC(y, m, 0)).getUTCDate();
  for (let d = 1; d <= total; d++) cells.push(`${ym}-${String(d).padStart(2, "0")}`);
  return (
    <div className="flex-1 min-w-[280px]" data-testid={`price-cal-month-${ym}`}>
      <div className="text-center font-semibold text-slate-800 mb-3 capitalize" style={{ fontFamily: t.fonts.heading }}>{label}</div>
      <div className="grid grid-cols-7 gap-1 text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">
        {dow.map((d) => <div key={d} className="text-center py-1">{d}</div>)}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {cells.map((d, i) => {
          if (!d) return <div key={`e${i}`} />;
          const info = byDate[d] || {};
          const disabled = info.past || (info.sold_out && d !== checkOut);
          const isStart = d === checkIn, isEnd = d === checkOut, mid = inRange(d);
          const price = info.min_price;
          return (
            <button key={d} type="button" disabled={disabled} onClick={() => onPick(d)} onMouseEnter={() => setHover(d)}
              data-testid={`price-cal-day-${d}`}
              className="relative h-14 rounded-lg flex flex-col items-center justify-center text-xs transition-all disabled:cursor-not-allowed"
              style={{
                background: isStart || isEnd ? t.colors.accent : mid ? `${t.colors.accent}18` : info.is_cheapest && !disabled ? `${t.colors.success}12` : "transparent",
                color: isStart || isEnd ? "#fff" : disabled ? "#cbd5e1" : "#0f172a",
                border: `1px solid ${isStart || isEnd ? t.colors.accent : info.is_cheapest && !disabled ? `${t.colors.success}55` : "#f1f5f9"}`,
                borderRadius: t.borderRadius,
              }}>
              <span className={`font-semibold ${info.sold_out ? "line-through" : ""}`}>{Number(d.slice(-2))}</span>
              {!info.past && (
                <span className="text-[10px] font-medium leading-none mt-0.5" style={{ color: isStart || isEnd ? "rgba(255,255,255,.85)" : info.sold_out ? "#94a3b8" : info.is_cheapest ? t.colors.success : "#64748b" }}>
                  {info.sold_out ? "—" : price != null ? `£${Math.round(price)}` : ""}
                </span>
              )}
              {info.available > 0 && info.available <= 2 && !isStart && !isEnd && (
                <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full" style={{ background: t.colors.urgency }} />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function PriceCalendar({ t, propertyId, checkIn, checkOut, adults, onChange, onClose }) {
  const { t: tr, lang } = useLanguage();
  const [ym, setYm] = useState(() => (checkIn || iso(new Date())).slice(0, 7));
  const [hover, setHover] = useState(null);
  const [picking, setPicking] = useState(false);
  const m1 = useMonth(propertyId, ym, adults);
  const m2 = useMonth(propertyId, addMonths(ym, 1), adults);
  const today = iso(new Date());

  const pick = (d) => {
    if (!picking || !checkIn || d <= checkIn) { onChange(d, ""); setPicking(true); return; }
    onChange(checkIn, d); setPicking(false);
  };
  const nights = checkIn && checkOut ? Math.round((new Date(checkOut) - new Date(checkIn)) / 86400000) : 0;
  const minP = [m1?.min_price, m2?.min_price].filter((x) => x != null);

  return (
    <div className="bg-white border border-gray-200 shadow-2xl p-5 mt-3" style={{ borderRadius: t.borderRadius }} data-testid="price-calendar">
      <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
          <CalendarBlank size={18} weight="fill" style={{ color: t.colors.accent }} /> {tr("cal.title")}
          {minP.length > 0 && <span className="text-xs font-medium px-2 py-0.5 rounded-full" style={{ background: `${t.colors.success}15`, color: t.colors.success }}>{tr("cal.from")} £{Math.round(Math.min(...minP))}</span>}
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => setYm(addMonths(ym, -1))} disabled={ym <= today.slice(0, 7)} className="w-8 h-8 rounded-full border border-gray-200 flex items-center justify-center hover:bg-slate-50 disabled:opacity-30" data-testid="price-cal-prev"><CaretLeft size={14} /></button>
          <button type="button" onClick={() => setYm(addMonths(ym, 1))} className="w-8 h-8 rounded-full border border-gray-200 flex items-center justify-center hover:bg-slate-50" data-testid="price-cal-next"><CaretRight size={14} /></button>
          {onClose && <button type="button" onClick={onClose} className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-slate-100 text-slate-400" data-testid="price-cal-close"><X size={16} /></button>}
        </div>
      </div>
      <div className="flex flex-col lg:flex-row gap-8" onMouseLeave={() => setHover(null)}>
        <MonthGrid t={t} data={m1} ym={ym} checkIn={checkIn} checkOut={checkOut} hover={picking ? hover : null} setHover={setHover} onPick={pick} lang={lang} />
        <div className="hidden lg:block"><MonthGrid t={t} data={m2} ym={addMonths(ym, 1)} checkIn={checkIn} checkOut={checkOut} hover={picking ? hover : null} setHover={setHover} onPick={pick} lang={lang} /></div>
      </div>
      <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-100 text-xs text-slate-500 flex-wrap gap-2">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm" style={{ background: `${t.colors.success}25`, border: `1px solid ${t.colors.success}` }} /> {tr("cal.cheapest")}</span>
          <span className="flex items-center gap-1.5"><span className="line-through">15</span> {tr("cal.soldOut")}</span>
          <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full" style={{ background: t.colors.urgency }} /> {tr("cal.fewLeft")}</span>
        </div>
        <span className="font-medium text-slate-700" data-testid="price-cal-hint">
          {picking ? tr("cal.pickCheckOut") : nights > 0 ? `${nights} ${nights !== 1 ? tr("room.nights") : tr("room.night")}` : tr("cal.pickCheckIn")}
        </span>
      </div>
    </div>
  );
}
