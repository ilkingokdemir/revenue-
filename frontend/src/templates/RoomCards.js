import {
  Users, Bed, CheckCircle, Lightning, Check,
  WifiHigh, Snowflake, Television, Coffee, Bathtub,
} from "@phosphor-icons/react";
import { PhotoCarousel } from "./PhotoCarousel";

const amenityIcons = {
  "Free WiFi": WifiHigh, "Air conditioning": Snowflake, "Flat-screen TV": Television,
  "55\" Smart TV": Television, "65\" Smart TV": Television, "Tea/coffee maker": Coffee,
  "Nespresso machine": Coffee, "Bathtub": Bathtub, "Rain shower": Bathtub, "Jacuzzi bath": Bathtub,
};

export function RoomPreviewCards({ t, rooms, searchRooms }) {
  if (!rooms || rooms.length === 0) return null;
  return (
    <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16" data-testid="rooms-preview-section">
      <h2 className="text-2xl sm:text-3xl font-semibold text-slate-900 mb-2" style={{ fontFamily: t.fonts.heading }}>
        {t.layout === "airbnb" ? "Rooms & Suites" : "Our Rooms"}
      </h2>
      <p className="text-slate-500 mb-8">Choose from our selection of comfortable rooms</p>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {rooms.slice(0, 6).map((room) => (
          <div key={room.id} className="bg-white border border-gray-200 overflow-hidden hover:shadow-lg transition-all hover:-translate-y-1" style={{ borderRadius: t.borderRadius }} data-testid={`room-preview-${room.id}`}>
            <div className="h-48 bg-slate-200 relative overflow-hidden">
              <PhotoCarousel photos={room.photos} borderRadius={t.borderRadius} />
              {t.showFreeCancellation && room.free_cancellation && (
                <div className="absolute top-3 left-3 text-xs font-semibold px-2 py-1 rounded flex items-center gap-1" style={{ background: t.colors.badgeBg, color: t.colors.success, border: `1px solid ${t.colors.success}20` }}>
                  <CheckCircle size={12} weight="fill" /> Free cancellation
                </div>
              )}
            </div>
            <div className="p-4">
              <h3 className="font-semibold text-slate-900 text-lg mb-1" style={{ fontFamily: t.fonts.heading }}>{room.name}</h3>
              <div className="flex items-center gap-3 text-xs text-slate-500 mb-3">
                <span className="flex items-center gap-1"><Users size={12} /> {room.max_guests} guests</span>
                <span className="flex items-center gap-1"><Bed size={12} /> {room.bed_type}</span>
                {room.size_sqm > 0 && <span>{room.size_sqm} m&sup2;</span>}
              </div>
              <div className="flex flex-wrap gap-1.5 mb-4">
                {room.amenities?.slice(0, 4).map((a) => (
                  <span key={a} className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded">{a}</span>
                ))}
              </div>
              <div className="flex items-end justify-between border-t border-gray-100 pt-3">
                <div>
                  <span className="text-2xl font-bold text-slate-900">&pound;{room.base_price}</span>
                  <span className="text-sm text-slate-500 ml-1">/ night</span>
                  {room.breakfast_included && (
                    <div className="text-[11px] font-medium mt-0.5 flex items-center gap-1" style={{ color: t.colors.success }}>
                      <CheckCircle size={11} weight="fill" /> Breakfast included
                    </div>
                  )}
                </div>
                <button onClick={searchRooms} className="text-white px-4 py-2 rounded-lg text-sm font-semibold transition-colors" style={{ background: t.colors.accent, borderRadius: t.borderRadius }} data-testid={`see-availability-${room.id}`}>
                  See availability
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export function RoomSelectionStep({ t, rooms, loading, nights, adults, children, roomCount, checkIn, checkOut, onSelectRoom, onChangeSearch }) {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="room-selection">
      <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6 flex flex-wrap items-center gap-4" style={{ borderRadius: t.borderRadius }}>
        <div className="flex items-center gap-2 text-sm">
          <span className="font-medium text-slate-700" style={{ color: t.colors.accent }}>
            {new Date(checkIn).toLocaleDateString("en-GB", { day: "numeric", month: "short" })} — {new Date(checkOut).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}
          </span>
          <span className="text-slate-400">({nights} night{nights !== 1 ? "s" : ""})</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <Users size={16} style={{ color: t.colors.accent }} />
          <span className="font-medium text-slate-700">{adults} adult{adults !== 1 ? "s" : ""}{children > 0 ? `, ${children} child${children !== 1 ? "ren" : ""}` : ""}</span>
        </div>
        <button onClick={onChangeSearch} className="ml-auto text-sm font-semibold hover:underline" style={{ color: t.colors.accent }} data-testid="change-search-btn">Change search</button>
      </div>

      <h2 className="text-2xl font-semibold text-slate-900 mb-6" style={{ fontFamily: t.fonts.heading }}>Available rooms</h2>

      {loading ? (
        <div className="flex justify-center py-20">
          <div className="w-10 h-10 border-4 border-t-transparent rounded-full animate-spin" style={{ borderColor: t.colors.accent, borderTopColor: "transparent" }} />
        </div>
      ) : rooms.length === 0 ? (
        <div className="text-center py-20 bg-white rounded-lg border border-gray-200">
          <Bed size={48} className="mx-auto text-slate-300 mb-4" />
          <h3 className="text-lg font-semibold text-slate-700">No rooms available</h3>
          <p className="text-slate-500 mt-1">Try different dates</p>
        </div>
      ) : (
        <div className="space-y-4">
          {rooms.map((room) => (
            <RoomCard key={room.id} room={room} t={t} nights={nights} adults={adults} roomCount={roomCount} onSelect={onSelectRoom} />
          ))}
        </div>
      )}
    </div>
  );
}

function RoomCard({ room, t, nights, adults, roomCount, onSelect }) {
  return (
    <div className="bg-white border border-gray-200 overflow-hidden hover:shadow-md transition-shadow" style={{ borderRadius: t.borderRadius }} data-testid={`room-card-${room.id}`}>
      <div className="flex flex-col md:flex-row">
        <div className="md:w-72 h-48 md:h-auto bg-slate-200 flex-shrink-0 overflow-hidden" style={{ minHeight: "180px" }}>
          <PhotoCarousel photos={room.photos} borderRadius="0" />
        </div>
        <div className="flex-1 p-5">
          <div className="flex items-start justify-between mb-3">
            <div>
              <h3 className="text-xl font-semibold" style={{ color: t.colors.accent, fontFamily: t.fonts.heading }}>{room.name}</h3>
              <div className="flex items-center gap-3 text-sm text-slate-500 mt-1">
                <span className="flex items-center gap-1"><Users size={14} /> {room.max_guests} guests</span>
                <span className="flex items-center gap-1"><Bed size={14} /> {room.bed_type} bed</span>
                {room.size_sqm > 0 && <span>{room.size_sqm} m&sup2;</span>}
              </div>
            </div>
            {t.showUrgency && room.available_rooms <= 3 && room.available_rooms > 0 && (
              <span className="text-sm font-semibold flex items-center gap-1 flex-shrink-0" style={{ color: t.colors.urgency }} data-testid={`urgency-${room.id}`}>
                <Lightning size={14} weight="fill" /> Only {room.available_rooms} left!
              </span>
            )}
          </div>
          <p className="text-sm text-slate-600 mb-3 line-clamp-2">{room.description}</p>
          <div className="flex flex-wrap gap-2 mb-4">
            {room.amenities?.slice(0, 6).map((a) => {
              const Icon = amenityIcons[a];
              return <span key={a} className="text-xs text-slate-600 flex items-center gap-1">{Icon ? <Icon size={12} style={{ color: t.colors.accent }} /> : <Check size={12} style={{ color: t.colors.success }} />}{a}</span>;
            })}
          </div>
          <div className="flex flex-wrap gap-2">
            {t.showFreeCancellation && room.free_cancellation && (
              <span className="text-xs font-semibold px-2.5 py-1 rounded flex items-center gap-1" style={{ background: t.colors.badgeBg, color: t.colors.success }}>
                <CheckCircle size={13} weight="fill" /> Free cancellation
              </span>
            )}
            {room.breakfast_included && (
              <span className="text-xs font-semibold px-2.5 py-1 rounded flex items-center gap-1" style={{ background: t.colors.badgeBg, color: t.colors.success }}>
                <CheckCircle size={13} weight="fill" /> Breakfast included
              </span>
            )}
          </div>
        </div>
        <div className="md:w-56 p-5 border-l border-gray-200 flex flex-col justify-between" style={{ background: t.colors.priceBg }}>
          <div>
            <div className="text-xs text-slate-500 mb-1">{nights} night{nights !== 1 ? "s" : ""}, {adults} adult{adults !== 1 ? "s" : ""}</div>
            <div className="text-3xl font-bold text-slate-900">&pound;{(room.base_price * nights * roomCount).toFixed(0)}</div>
            <div className="text-xs text-slate-500 mt-0.5">Includes taxes and fees</div>
          </div>
          <button onClick={() => onSelect(room)} disabled={!room.is_available}
            className="mt-4 w-full py-3 rounded-lg font-semibold text-sm transition-colors text-white disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed"
            style={{ background: room.is_available ? t.colors.accent : undefined, borderRadius: t.borderRadius }}
            data-testid={`select-room-${room.id}`}>
            {room.is_available ? "Reserve" : "Sold out"}
          </button>
          <div className="mt-2 text-center text-[10px] text-slate-400 flex items-center justify-center gap-1">Secure booking</div>
        </div>
      </div>
    </div>
  );
}
