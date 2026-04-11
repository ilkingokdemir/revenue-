import {
  CalendarBlank, Users, CaretDown, MagnifyingGlass,
} from "@phosphor-icons/react";

export function SearchWidget({ t, checkIn, setCheckIn, checkOut, setCheckOut, adults, setAdults, children, setChildren, roomCount, setRoomCount, showGuestPicker, setShowGuestPicker, searchRooms }) {
  const isAirbnb = t.layout === "airbnb";
  return (
    <div className={`${isAirbnb ? "bg-white border border-gray-200 shadow-md" : "bg-white shadow-2xl border border-gray-200"} p-6 sm:p-8`}
      style={{ borderRadius: isAirbnb ? "16px" : t.borderRadius }} data-testid="search-widget">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div>
          <label className="text-xs font-bold tracking-wider uppercase text-slate-500 mb-1.5 block">Check-in</label>
          <div className="relative">
            <CalendarBlank size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input type="date" value={checkIn} onChange={e => setCheckIn(e.target.value)} min={new Date().toISOString().split("T")[0]}
              className="w-full border border-gray-300 rounded-lg pl-10 pr-3 py-3 text-slate-800 font-medium focus:ring-2 focus:border-transparent"
              data-testid="check-in-input" />
          </div>
        </div>
        <div>
          <label className="text-xs font-bold tracking-wider uppercase text-slate-500 mb-1.5 block">Check-out</label>
          <div className="relative">
            <CalendarBlank size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input type="date" value={checkOut} onChange={e => setCheckOut(e.target.value)} min={checkIn}
              className="w-full border border-gray-300 rounded-lg pl-10 pr-3 py-3 text-slate-800 font-medium focus:ring-2 focus:border-transparent"
              data-testid="check-out-input" />
          </div>
        </div>
        <div>
          <label className="text-xs font-bold tracking-wider uppercase text-slate-500 mb-1.5 block">Guests</label>
          <div className="relative">
            <button onClick={() => setShowGuestPicker(!showGuestPicker)}
              className="w-full border border-gray-300 rounded-lg px-3 py-3 text-left text-slate-800 font-medium flex items-center gap-2" data-testid="guest-picker-trigger">
              <Users size={18} className="text-slate-400" />
              <span>{adults} Adult{adults !== 1 ? "s" : ""}{children > 0 ? `, ${children} Child${children !== 1 ? "ren" : ""}` : ""}</span>
              <CaretDown size={14} className="ml-auto text-slate-400" />
            </button>
            {showGuestPicker && (
              <div className="absolute top-full mt-1 left-0 right-0 bg-white border border-gray-200 rounded-lg shadow-xl p-4 z-20" data-testid="guest-picker-dropdown">
                {[
                  { label: "Adults", value: adults, set: setAdults, min: 1, max: 10 },
                  { label: "Children", value: children, set: setChildren, min: 0, max: 6 },
                  { label: "Rooms", value: roomCount, set: setRoomCount, min: 1, max: 5 },
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
                <button onClick={() => setShowGuestPicker(false)} className="w-full mt-2 text-white py-2 rounded-lg font-semibold text-sm" style={{ background: t.colors.accent }}>Done</button>
              </div>
            )}
          </div>
        </div>
        <div className="flex items-end">
          <button onClick={searchRooms} className="w-full text-white py-3 rounded-lg font-semibold text-base transition-colors flex items-center justify-center gap-2 shadow-lg"
            style={{ background: t.colors.accent, borderRadius: t.borderRadius }} data-testid="search-rooms-btn">
            <MagnifyingGlass size={18} weight="bold" /> Search
          </button>
        </div>
      </div>
    </div>
  );
}
