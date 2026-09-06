import { useState } from "react";
import { X, Users, Bed, Ruler, Check, CaretLeft, CaretRight } from "@phosphor-icons/react";
import { useLanguage } from "../i18n/LanguageContext";

export function RoomDetailModal({ t, room, onClose, fmt, nights }) {
  const { t: tr, lang } = useLanguage();
  const [i, setI] = useState(0);
  const photos = room.photos?.length ? room.photos : [];
  const ex = room.price_explanation;
  return (
    <div className="fixed inset-0 z-[75] bg-black/60 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={room.name} onClick={onClose} data-testid="room-detail-modal">
      <div className="bg-white max-w-3xl w-full max-h-[90vh] overflow-y-auto relative" style={{ borderRadius: t.borderRadius }} onClick={(e) => e.stopPropagation()}>
        <button onClick={onClose} className="absolute top-3 right-3 z-10 w-9 h-9 rounded-full bg-white/90 shadow flex items-center justify-center text-slate-600 hover:text-slate-900" aria-label="close" data-testid="room-detail-close"><X size={18} /></button>
        <div className="relative h-72 bg-slate-200">
          {photos[i] ? <img src={photos[i]} alt={`${room.name} ${i + 1}`} className="w-full h-full object-cover" /> : <div className="w-full h-full flex items-center justify-center"><Bed size={48} className="text-slate-300" /></div>}
          {photos.length > 1 && (
            <>
              <button onClick={() => setI((i - 1 + photos.length) % photos.length)} className="absolute left-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-white/90 flex items-center justify-center" aria-label="prev" data-testid="room-detail-prev"><CaretLeft size={16} /></button>
              <button onClick={() => setI((i + 1) % photos.length)} className="absolute right-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-white/90 flex items-center justify-center" aria-label="next" data-testid="room-detail-next"><CaretRight size={16} /></button>
              <div className="absolute bottom-3 left-0 right-0 flex justify-center gap-1.5">{photos.map((_, k) => <span key={k} className={`w-2 h-2 rounded-full ${k === i ? "bg-white" : "bg-white/50"}`} />)}</div>
            </>
          )}
        </div>
        {photos.length > 1 && <div className="flex gap-2 p-3 overflow-x-auto">{photos.map((p, k) => <img key={k} src={p} alt="" onClick={() => setI(k)} className={`w-20 h-14 object-cover rounded-md cursor-pointer border-2 ${k === i ? "" : "border-transparent opacity-70"}`} style={k === i ? { borderColor: t.colors.accent } : {}} />)}</div>}
        <div className="p-6">
          <h3 className="text-2xl font-semibold" style={{ color: t.colors.accent, fontFamily: t.fonts.heading }} data-testid="room-detail-title">{room.name}</h3>
          <div className="flex flex-wrap items-center gap-4 text-sm text-slate-600 mt-2">
            <span className="flex items-center gap-1"><Users size={16} /> {room.max_guests} {tr("room.guests")}</span>
            {room.bed_type && <span className="flex items-center gap-1"><Bed size={16} /> {room.bed_type}</span>}
            {room.size_sqm > 0 && <span className="flex items-center gap-1"><Ruler size={16} /> {room.size_sqm} m²</span>}
            {room.view && <span>{room.view}</span>}
          </div>
          <p className="text-sm text-slate-700 leading-relaxed mt-4 whitespace-pre-line">{room.description}</p>
          {room.amenities?.length > 0 && (
            <div className="mt-5">
              <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">{tr("detail.amenities")}</div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">{room.amenities.map((a) => <span key={a} className="text-sm text-slate-700 flex items-center gap-1.5"><Check size={14} style={{ color: t.colors.success }} /> {a}</span>)}</div>
            </div>
          )}
          {ex && (
            <div className="mt-5 rounded-lg p-3 text-sm" style={{ background: `${t.colors.accent}0d` }} data-testid="room-detail-explanation">
              <b>{ex[`headline_${lang}`] || ex.headline_en}</b>
              {ex.drivers?.length > 0 && <ul className="mt-1 text-xs text-slate-600 list-disc list-inside">{ex.drivers.map((d, k) => <li key={k}>{d[`label_${lang}`] || d.label_en} · {d.nights} {tr("room.nights")} {d.direction === "up" ? "↑" : "↓"}</li>)}</ul>}
            </div>
          )}
          {room.nightly?.length > 0 && (
            <div className="mt-4">
              <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">{tr("detail.nightly")}</div>
              <div className="flex flex-wrap gap-1.5">{room.nightly.map((n) => <span key={n.date} className="text-[11px] px-2 py-1 rounded bg-slate-100 text-slate-700">{n.date.slice(5)} · <b>{fmt(n.rate)}</b></span>)}</div>
            </div>
          )}
          <div className="mt-6 flex items-center justify-between">
            <div><div className="text-xs text-slate-500">{nights} {tr("room.nights")}</div><div className="text-2xl font-bold text-slate-900">{fmt((room.stay_total ?? room.base_price * nights))}</div></div>
            <button onClick={onClose} className="px-5 py-2.5 rounded-lg font-semibold text-white text-sm" style={{ background: t.colors.accent, borderRadius: t.borderRadius }} data-testid="room-detail-choose">{tr("detail.chooseRate")}</button>
          </div>
        </div>
      </div>
    </div>
  );
}
