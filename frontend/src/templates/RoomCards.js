import React from "react";
import {
  Users, Bed, CheckCircle, Lightning, Check,
  WifiHigh, Snowflake, Television, Coffee, Bathtub,
} from "@phosphor-icons/react";
import { PhotoCarousel } from "./PhotoCarousel";
import { RatePlanRows } from "./RatePlanRows";
import { RoomDetailModal } from "./RoomDetailModal";
import { useState } from "react";
import { useLanguage } from "../i18n/LanguageContext";

const amenityIcons = {
  "Free WiFi": WifiHigh, "Air conditioning": Snowflake, "Flat-screen TV": Television,
  "55\" Smart TV": Television, "65\" Smart TV": Television, "Tea/coffee maker": Coffee,
  "Nespresso machine": Coffee, "Bathtub": Bathtub, "Rain shower": Bathtub, "Jacuzzi bath": Bathtub,
};

export function RoomPreviewCards({ t, rooms, searchRooms }) {
  const { t: tr } = useLanguage();
  if (!rooms || rooms.length === 0) return null;
  return (
    <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16" data-testid="rooms-preview-section">
      <h2 className="text-2xl sm:text-3xl font-semibold text-slate-900 mb-2" style={{ fontFamily: t.fonts.heading }}>
        {t.layout === "airbnb" ? tr("hero.roomsSuites") : tr("hero.ourRooms")}
      </h2>
      <p className="text-slate-500 mb-8">{tr("hero.chooseRooms")}</p>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {rooms.slice(0, 6).map((room) => (
          <div key={room.id} className="bg-white border border-gray-200 overflow-hidden hover:shadow-lg transition-all hover:-translate-y-1" style={{ borderRadius: t.borderRadius }} data-testid={`room-preview-${room.id}`}>
            <div className="h-48 bg-slate-200 relative overflow-hidden">
              <PhotoCarousel photos={room.photos} borderRadius={t.borderRadius} />
              {t.showFreeCancellation && room.free_cancellation && (
                <div className="absolute top-3 left-3 text-xs font-semibold px-2 py-1 rounded flex items-center gap-1" style={{ background: t.colors.badgeBg, color: t.colors.success, border: `1px solid ${t.colors.success}20` }}>
                  <CheckCircle size={12} weight="fill" /> {tr("room.freeCancellation")}
                </div>
              )}
            </div>
            <div className="p-4">
              <h3 className="font-semibold text-slate-900 text-lg mb-1" style={{ fontFamily: t.fonts.heading }}>{room.name}</h3>
              <div className="flex items-center gap-3 text-xs text-slate-500 mb-3">
                <span className="flex items-center gap-1"><Users size={12} /> {room.max_guests} {tr("room.guests")}</span>
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
                  <span className="text-sm text-slate-500 ml-1">{tr("room.perNight")}</span>
                  {room.breakfast_included && (
                    <div className="text-[11px] font-medium mt-0.5 flex items-center gap-1" style={{ color: t.colors.success }}>
                      <CheckCircle size={11} weight="fill" /> {tr("room.breakfastIncluded")}
                    </div>
                  )}
                </div>
                <button onClick={searchRooms} className="text-white px-4 py-2 rounded-lg text-sm font-semibold transition-colors" style={{ background: t.colors.accent, borderRadius: t.borderRadius }} data-testid={`see-availability-${room.id}`}>
                  {tr("room.seeAvailability")}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export function RoomSelectionStep({ t, rooms, loading, nights, adults, children, roomCount, checkIn, checkOut, onSelectRoom, onChangeSearch, ratePlans, cart, flexData, onApplyDates, fmt, memberPct, onMemberCheck, onWaitlist }) {
  const { t: tr } = useLanguage();
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="room-selection">
      <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6 flex flex-wrap items-center gap-4" style={{ borderRadius: t.borderRadius }}>
        <div className="flex items-center gap-2 text-sm">
          <span className="font-medium text-slate-700" style={{ color: t.colors.accent }}>
            {new Date(checkIn).toLocaleDateString("en-GB", { day: "numeric", month: "short" })} — {new Date(checkOut).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}
          </span>
          <span className="text-slate-400">({nights} {nights !== 1 ? tr("room.nights") : tr("room.night")})</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <Users size={16} style={{ color: t.colors.accent }} />
          <span className="font-medium text-slate-700">{adults} {adults !== 1 ? tr("search.adults") : tr("search.adult")}{children > 0 ? `, ${children} ${children !== 1 ? tr("search.children") : tr("search.child")}` : ""}</span>
        </div>
        <button onClick={onChangeSearch} className="ml-auto text-sm font-semibold hover:underline" style={{ color: t.colors.accent }} data-testid="change-search-btn">{tr("room.changeSearch")}</button>
      </div>

      <FlexDatesStrip t={t} flexData={flexData} onApplyDates={onApplyDates} fmt={fmt} />
      {onMemberCheck && <MemberRateBar t={t} memberPct={memberPct} onMemberCheck={onMemberCheck} />}

      <div className="flex items-end justify-between mb-6 gap-4 flex-wrap">
        <h2 className="text-2xl font-semibold text-slate-900" style={{ fontFamily: t.fonts.heading }}>{tr("room.availableRooms")}</h2>
        {ratePlans?.length > 1 && <p className="text-sm text-slate-500">{tr("plan.chooseHint")}</p>}
      </div>

      {loading ? (
        <div className="flex justify-center py-20">
          <div className="w-10 h-10 border-4 border-t-transparent rounded-full animate-spin" style={{ borderColor: t.colors.accent, borderTopColor: "transparent" }} />
        </div>
      ) : rooms.length === 0 ? (
        <div className="text-center py-20 bg-white rounded-lg border border-gray-200">
          <Bed size={48} className="mx-auto text-slate-300 mb-4" />
          <h3 className="text-lg font-semibold text-slate-700">{tr("room.noRooms")}</h3>
          <p className="text-slate-500 mt-1">{tr("room.tryDifferentDates")}</p>
          {onWaitlist && <WaitlistForm t={t} onSubmit={onWaitlist} />}
        </div>
      ) : (
        <div className="space-y-4">
          {rooms.map((room) => (
            <RoomCard key={room.id} room={room} t={t} nights={nights} adults={adults} roomCount={roomCount} onSelect={onSelectRoom} ratePlans={ratePlans} cart={cart} fmt={fmt} memberPct={memberPct} />
          ))}
        </div>
      )}
    </div>
  );
}

function MemberRateBar({ t, memberPct, onMemberCheck }) {
  const { t: tr } = useLanguage();
  const [email, setEmail] = useState("");
  const [open, setOpen] = useState(false);
  if (memberPct > 0) return null;
  return (
    <div className="mb-6 rounded-lg border border-gray-200 bg-white p-3 flex flex-wrap items-center gap-3" style={{ borderRadius: t.borderRadius }} data-testid="member-rate-bar">
      <span className="text-sm font-semibold text-slate-800">★ {tr("member.title")}</span>
      <span className="text-xs text-slate-500">{tr("member.sub")}</span>
      {open ? (
        <form className="ml-auto flex gap-2" onSubmit={(e) => { e.preventDefault(); onMemberCheck(email); }}>
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email" className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm" data-testid="member-email-input" />
          <button type="submit" className="px-3 py-1.5 rounded-lg text-white text-sm font-semibold" style={{ background: t.colors.accent }} data-testid="member-check-btn">{tr("member.check")}</button>
        </form>
      ) : <button onClick={() => setOpen(true)} className="ml-auto text-sm font-semibold hover:underline" style={{ color: t.colors.accent }} data-testid="member-open-btn">{tr("member.iAm")}</button>}
    </div>
  );
}

function FlexDatesStrip({ t, flexData, onApplyDates, fmt = (v) => `£${Math.round(v)}` }) {
  const { t: tr } = useLanguage();
  const alts = flexData?.alternatives?.filter((a) => a.saving > 0) || [];
  if (!alts.length) return null;
  const fd = (d) => new Date(d).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  return (
    <div className="mb-6 rounded-lg border p-4" style={{ borderRadius: t.borderRadius, borderColor: `${t.colors.success}55`, background: `${t.colors.success}08` }} data-testid="flex-dates-strip">
      <div className="flex items-center gap-2 mb-3">
        <Lightning size={16} weight="fill" style={{ color: t.colors.success }} />
        <span className="text-sm font-semibold text-slate-800">{tr("flex.title")}</span>
        <span className="text-xs text-slate-500">{tr("flex.sub", { pct: alts[0].saving_pct })}</span>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {alts.slice(0, 5).map((a) => (
          <button key={a.offset} type="button" onClick={() => onApplyDates(a.check_in, a.check_out)}
            className="flex-shrink-0 bg-white border border-gray-200 rounded-lg px-3 py-2 text-left hover:shadow-md transition-shadow" style={{ borderRadius: t.borderRadius }}
            data-testid={`flex-date-${a.offset}`}>
            <div className="text-xs font-semibold text-slate-800">{fd(a.check_in)} → {fd(a.check_out)}</div>
            <div className="text-[11px] mt-0.5"><span className="font-bold text-slate-900">{fmt(a.total)}</span> <span className="font-semibold" style={{ color: t.colors.success }}>−{fmt(a.saving)} ({a.saving_pct}%)</span></div>
          </button>
        ))}
      </div>
    </div>
  );
}

function RoomCard({ room, t, nights, adults, onSelect, ratePlans, cart, fmt = (v) => `£${Math.round(v)}`, memberPct = 0 }) {
  const { t: tr } = useLanguage();
  const [detail, setDetail] = useState(false);
  return (
    <div className="bg-white border border-gray-200 overflow-hidden hover:shadow-md transition-shadow" style={{ borderRadius: t.borderRadius }} data-testid={`room-card-${room.id}`}>
      {detail && <RoomDetailModal t={t} room={room} onClose={() => setDetail(false)} fmt={fmt} nights={nights} />}
      <div className="flex flex-col md:flex-row">
        <div className="md:w-72 h-48 md:h-auto bg-slate-200 flex-shrink-0 overflow-hidden" style={{ minHeight: "180px" }}>
          <PhotoCarousel photos={room.photos} borderRadius="0" />
        </div>
        <div className="flex-1 p-5">
          <div className="flex items-start justify-between mb-3">
            <div>
              <h3 className="text-xl font-semibold" style={{ color: t.colors.accent, fontFamily: t.fonts.heading }}>{room.name}</h3>
              <div className="flex items-center gap-3 text-sm text-slate-500 mt-1">
                <span className="flex items-center gap-1"><Users size={14} /> {room.max_guests} {tr("room.guests")}</span>
                <span className="flex items-center gap-1"><Bed size={14} /> {room.bed_type}</span>
                {room.size_sqm > 0 && <span>{room.size_sqm} m&sup2;</span>}
              </div>
            </div>
            {t.showUrgency && room.available_rooms <= 3 && room.available_rooms > 0 && (
              <span className="text-sm font-semibold flex items-center gap-1 flex-shrink-0" style={{ color: t.colors.urgency }} data-testid={`urgency-${room.id}`}>
                <Lightning size={14} weight="fill" /> {tr("room.onlyLeft", { count: room.available_rooms })}
              </span>
            )}
          </div>
          <p className="text-sm text-slate-600 mb-1 line-clamp-2">{room.description}</p>
          <button type="button" onClick={() => setDetail(true)} className="text-sm font-semibold hover:underline mb-3" style={{ color: t.colors.accent }} data-testid={`room-detail-btn-${room.id}`}>{tr("detail.open")} →</button>
          <div className="flex flex-wrap gap-2">
            {room.amenities?.slice(0, 6).map((a) => {
              const Icon = amenityIcons[a];
              return <span key={a} className="text-xs text-slate-600 flex items-center gap-1">{Icon ? <Icon size={12} style={{ color: t.colors.accent }} /> : <Check size={12} style={{ color: t.colors.success }} />}{a}</span>;
            })}
          </div>
        </div>
      </div>
      <RatePlanRows t={t} room={room} plans={ratePlans} nights={nights} adults={adults} cart={cart} onAdd={onSelect} fmt={fmt} memberPct={memberPct} />
    </div>
  );
}

function WaitlistForm({ t, onSubmit }) {
  const { t: tr } = useLanguage();
  const [email, setEmail] = React.useState("");
  const [name, setName] = React.useState("");
  const [done, setDone] = React.useState(false);
  if (done) return <p className="mt-4 text-sm font-semibold text-emerald-700" data-testid="waitlist-done">✓ {tr("waitlist.done")}</p>;
  return (
    <div className="mt-5 max-w-md mx-auto text-left" data-testid="waitlist-form">
      <div className="text-sm font-semibold text-slate-800">{tr("waitlist.title")}</div>
      <div className="text-xs text-slate-500 mb-2">{tr("waitlist.sub")}</div>
      <div className="flex flex-col sm:flex-row gap-2">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder={tr("guest.name")} className="border border-gray-300 rounded-lg px-3 py-2 text-sm flex-1" data-testid="waitlist-name" />
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email@example.com" className="border border-gray-300 rounded-lg px-3 py-2 text-sm flex-1" data-testid="waitlist-email" />
        <button type="button" disabled={!email.includes("@")} onClick={async () => { const ok = await onSubmit({ email, name }); if (ok) setDone(true); }} className="px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-40" style={{ background: t.colors.primary, borderRadius: t.borderRadius }} data-testid="waitlist-submit">{tr("waitlist.btn")}</button>
      </div>
    </div>
  );
}
