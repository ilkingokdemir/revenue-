import { useState } from "react";
import {
  CalendarBlank, Users, CaretDown, MagnifyingGlass, Tag,
} from "@phosphor-icons/react";
import { useLanguage } from "../i18n/LanguageContext";
import { PriceCalendar } from "./PriceCalendar";

export function SearchWidget({ t, checkIn, setCheckIn, checkOut, setCheckOut, adults, setAdults, children, setChildren, roomCount, setRoomCount, showGuestPicker, setShowGuestPicker, searchRooms, propertyId, childAges = [], setChildAges }) {
  const { t: tr } = useLanguage();
  const [showCal, setShowCal] = useState(false);
  const isAirbnb = t.layout === "airbnb";
  return (
    <div className={`${isAirbnb ? "bg-white border border-gray-200 shadow-md" : "bg-white shadow-2xl border border-gray-200"} p-6 sm:p-8`}
      style={{ borderRadius: isAirbnb ? "16px" : t.borderRadius }} data-testid="search-widget">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div>
          <label className="text-xs font-bold tracking-wider uppercase text-slate-500 mb-1.5 block">{tr("search.checkIn")}</label>
          <div className="relative">
            <CalendarBlank size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input type="date" value={checkIn} onChange={e => setCheckIn(e.target.value)} min={new Date().toISOString().split("T")[0]}
              className="w-full border border-gray-300 rounded-lg pl-10 pr-3 py-3 text-slate-800 font-medium focus:ring-2 focus:border-transparent"
              data-testid="check-in-input" />
          </div>
        </div>
        <div>
          <label className="text-xs font-bold tracking-wider uppercase text-slate-500 mb-1.5 block">{tr("search.checkOut")}</label>
          <div className="relative">
            <CalendarBlank size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input type="date" value={checkOut} onChange={e => setCheckOut(e.target.value)} min={checkIn}
              className="w-full border border-gray-300 rounded-lg pl-10 pr-3 py-3 text-slate-800 font-medium focus:ring-2 focus:border-transparent"
              data-testid="check-out-input" />
          </div>
        </div>
        <div>
          <label className="text-xs font-bold tracking-wider uppercase text-slate-500 mb-1.5 block">{tr("search.guests")}</label>
          <div className="relative">
            <button onClick={() => setShowGuestPicker(!showGuestPicker)}
              className="w-full border border-gray-300 rounded-lg px-3 py-3 text-left text-slate-800 font-medium flex items-center gap-2" data-testid="guest-picker-trigger">
              <Users size={18} className="text-slate-400" />
              <span>{adults} {adults !== 1 ? tr("search.adults") : tr("search.adult")}{children > 0 ? `, ${children} ${children !== 1 ? tr("search.children") : tr("search.child")}` : ""}</span>
              <CaretDown size={14} className="ml-auto text-slate-400" />
            </button>
            {showGuestPicker && (
              <div className="absolute top-full mt-1 left-0 right-0 bg-white border border-gray-200 rounded-lg shadow-xl p-4 z-20" data-testid="guest-picker-dropdown">
                {[
                  { label: tr("search.adults"), value: adults, set: setAdults, min: 1, max: 10 },
                  { label: tr("search.children"), value: children, set: setChildren, min: 0, max: 6 },
                  { label: tr("search.rooms"), value: roomCount, set: setRoomCount, min: 1, max: 5 },
                ].map(({ label, value, set, min, max }) => (
                  <div key={label} className="flex items-center justify-between py-2">
                    <span className="text-sm text-slate-700 font-medium">{label}</span>
                    <div className="flex items-center gap-3">
                      <button onClick={() => set(Math.max(min, value - 1))} className="w-8 h-8 rounded-full border border-gray-300 flex items-center justify-center text-slate-600 hover:bg-slate-50">-</button>
                      <span className="w-6 text-center font-semibold">{value}</span>
                      <button onClick={() => set(Math.min(max, value + 1))} className="w-8 h-8 rounded-full border border-gray-300 flex items-center justify-center text-slate-600 hover:bg-slate-50">+</button>
                    </div>
                  </div>
                ))}
                {children > 0 && setChildAges && (
                  <div className="pt-2 border-t border-gray-100 mt-1" data-testid="child-ages">
                    <div className="text-xs font-semibold text-slate-500 mb-1.5">{tr("search.childAges")}</div>
                    <div className="flex flex-wrap gap-1.5">
                      {Array.from({ length: children }).map((_, i) => (
                        <select key={i} value={childAges[i] ?? 6} onChange={(e) => { const n = [...childAges]; n[i] = Number(e.target.value); setChildAges(n.slice(0, children)); }} className="border border-gray-300 rounded-lg px-2 py-1 text-xs" aria-label={`${tr("search.child")} ${i + 1}`} data-testid={`child-age-${i}`}>
                          {Array.from({ length: 18 }).map((__, a) => <option key={a} value={a}>{a === 0 ? "<1" : a}</option>)}
                        </select>
                      ))}
                    </div>
                  </div>
                )}
                <button onClick={() => setShowGuestPicker(false)} className="w-full mt-2 text-white py-2 rounded-lg font-semibold text-sm" style={{ background: t.colors.accent }}>{tr("search.done")}</button>
              </div>
            )}
          </div>
        </div>
        <div className="flex items-end">
          <button onClick={searchRooms} className="w-full text-white py-3 rounded-lg font-semibold text-base transition-colors flex items-center justify-center gap-2 shadow-lg"
            style={{ background: t.colors.accent, borderRadius: t.borderRadius }} data-testid="search-rooms-btn">
            <MagnifyingGlass size={18} weight="bold" /> {tr("search.search")}
          </button>
        </div>
      </div>
      {propertyId && (
        <div className="mt-3 flex items-center justify-between">
          <button type="button" onClick={() => setShowCal((v) => !v)} className="text-sm font-semibold flex items-center gap-1.5 hover:underline" style={{ color: t.colors.accent }} data-testid="price-calendar-toggle">
            <Tag size={15} weight="fill" /> {showCal ? tr("cal.hide") : tr("cal.show")}
          </button>
        </div>
      )}
      {showCal && propertyId && (
        <PriceCalendar t={t} propertyId={propertyId} checkIn={checkIn} checkOut={checkOut} adults={adults}
          onChange={(ci, co) => { setCheckIn(ci); setCheckOut(co || ""); }} onClose={() => setShowCal(false)} />
      )}
    </div>
  );
}
