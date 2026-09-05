import { useState } from "react";
import axios from "axios";
import { Star, MapPin, Phone, EnvelopeSimple, CaretDown, Users, Bed, MagnifyingGlass, CheckCircle } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const apiBase = process.env.REACT_APP_BACKEND_URL;
const iso = (d) => d.toISOString().split("T")[0];

export function Section({ th, title, children, testId, id }) {
  return (
    <section id={id} className="py-14" data-testid={testId}>
      <div className="max-w-5xl mx-auto px-6">
        {title && <h2 className="text-base md:text-lg font-bold uppercase tracking-[0.2em] mb-6" style={{ color: th.accent, fontFamily: th.heading }}>{title}</h2>}
        {children}
      </div>
    </section>
  );
}

export function AvailabilityBlock({ th, propertyId, currency = "GBP" }) {
  const t = new Date(); const d1 = new Date(t); d1.setDate(d1.getDate() + 1); const d2 = new Date(t); d2.setDate(d2.getDate() + 3);
  const [ci, setCi] = useState(iso(d1)); const [co, setCo] = useState(iso(d2)); const [adults, setAdults] = useState(2);
  const [rooms, setRooms] = useState(null); const [busy, setBusy] = useState(false);
  const nights = Math.max(1, Math.round((new Date(co) - new Date(ci)) / 86400000));
  const sym = currency === "TRY" ? "₺" : currency === "EUR" ? "€" : currency === "USD" ? "$" : "£";
  const search = async () => {
    setBusy(true);
    try { const { data } = await axios.get(`${API}/booking/rooms/${propertyId}?check_in=${ci}&check_out=${co}&adults=${adults}`); setRooms(data); }
    catch { setRooms([]); } finally { setBusy(false); }
  };
  const inp = { background: th.card, color: th.text, border: `1px solid ${th.cardBorder}`, borderRadius: th.radius };
  return (
    <div className="-mt-10 relative z-10 max-w-5xl mx-auto px-6" data-testid="site-availability-block">
      <div className="shadow-2xl p-5 sm:p-6" style={{ background: th.card, borderRadius: th.radius, border: `1px solid ${th.cardBorder}` }}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <label className="text-[10px] font-bold uppercase tracking-wider" style={{ color: th.muted }}>Giriş<input type="date" value={ci} min={iso(t)} onChange={(e) => setCi(e.target.value)} className="mt-1 w-full px-3 py-2.5 text-sm" style={inp} data-testid="site-avail-checkin" /></label>
          <label className="text-[10px] font-bold uppercase tracking-wider" style={{ color: th.muted }}>Çıkış<input type="date" value={co} min={ci} onChange={(e) => setCo(e.target.value)} className="mt-1 w-full px-3 py-2.5 text-sm" style={inp} data-testid="site-avail-checkout" /></label>
          <label className="text-[10px] font-bold uppercase tracking-wider" style={{ color: th.muted }}>Misafir<select value={adults} onChange={(e) => setAdults(Number(e.target.value))} className="mt-1 w-full px-3 py-2.5 text-sm" style={inp} data-testid="site-avail-adults">{[1, 2, 3, 4, 5, 6].map((n) => <option key={n} value={n}>{n} yetişkin</option>)}</select></label>
          <button onClick={search} disabled={busy} className="self-end h-[42px] font-bold text-sm flex items-center justify-center gap-2 transition-transform hover:scale-[1.02] disabled:opacity-60" style={{ background: th.accent, color: th.accentText, borderRadius: th.radius }} data-testid="site-avail-search-btn"><MagnifyingGlass size={16} weight="bold" /> Müsaitlik & Fiyat</button>
        </div>
        {rooms && (
          <div className="mt-4 divide-y" style={{ borderColor: th.cardBorder }} data-testid="site-avail-results">
            {rooms.length === 0 && <p className="text-sm py-3" style={{ color: th.muted }}>Bu tarihlerde müsait oda bulunamadı.</p>}
            {rooms.map((r) => (
              <div key={r.id} className="flex items-center justify-between gap-3 py-3" data-testid={`site-avail-room-${r.id}`}>
                <div className="flex items-center gap-3 min-w-0">
                  {r.photos?.[0] && <img src={r.photos[0]} alt="" className="w-16 h-12 object-cover flex-shrink-0" style={{ borderRadius: th.radius }} />}
                  <div className="min-w-0"><div className="text-sm font-bold truncate">{r.name}</div><div className="text-[11px]" style={{ color: th.muted }}>{r.max_guests} misafir · {r.is_available ? `${r.available_rooms} oda müsait` : "Dolu"}</div></div>
                </div>
                <div className="text-right flex-shrink-0">
                  <div className="text-lg font-black">{sym}{(r.base_price * nights).toFixed(0)}</div>
                  <div className="text-[10px]" style={{ color: th.muted }}>{nights} gece</div>
                </div>
                <a href={`/book?property=${propertyId}&check_in=${ci}&check_out=${co}&adults=${adults}`} className={`px-3 py-2 text-xs font-bold whitespace-nowrap ${r.is_available ? "" : "pointer-events-none opacity-40"}`} style={{ background: th.accent, color: th.accentText, borderRadius: th.radius }} data-testid={`site-avail-book-${r.id}`}>Rezerve Et</a>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function RoomsBlock({ th, rooms, propertyId, onCta, currency = "GBP" }) {
  const sym = currency === "TRY" ? "₺" : currency === "EUR" ? "€" : "£";
  if (!rooms?.length) return null;
  return (
    <Section th={th} title="Odalarımız" testId="site-rooms-block">
      <div className="grid sm:grid-cols-2 gap-5">
        {rooms.map((r) => (
          <div key={r.id} className="overflow-hidden group" style={{ background: th.card, border: `1px solid ${th.cardBorder}`, borderRadius: th.radius }} data-testid={`site-room-${r.id}`}>
            {r.photos?.[0] ? <img src={r.photos[0]} alt={r.name} className="w-full h-48 object-cover group-hover:scale-[1.03] transition-transform duration-500" loading="lazy" /> : <div className="w-full h-32 flex items-center justify-center" style={{ background: th.bg }}><Bed size={32} style={{ color: th.muted }} /></div>}
            <div className="p-5">
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-base font-bold" style={{ fontFamily: th.heading }}>{r.name}</h3>
                <div className="text-right"><div className="text-lg font-black">{sym}{r.base_price || r.base_rate || "-"}</div><div className="text-[10px]" style={{ color: th.muted }}>gece'den</div></div>
              </div>
              {r.description && <p className="text-xs mt-2 leading-relaxed line-clamp-2" style={{ color: th.muted }}>{r.description}</p>}
              <div className="flex items-center gap-3 text-[11px] mt-3" style={{ color: th.muted }}>
                {r.max_guests && <span className="flex items-center gap-1"><Users size={12} /> {r.max_guests}</span>}
                {r.bed_type && <span className="flex items-center gap-1"><Bed size={12} /> {r.bed_type}</span>}
                {r.size_sqm > 0 && <span>{r.size_sqm} m²</span>}
              </div>
              <a href={`/book?property=${propertyId}`} onClick={onCta} className="inline-block mt-4 text-xs font-bold px-4 py-2" style={{ background: th.accent, color: th.accentText, borderRadius: th.radius }}>Müsaitliğe bak →</a>
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
}

export function ReviewsBlock({ th, reviews, rating }) {
  if (!reviews?.length) return null;
  return (
    <Section th={th} title="Misafirlerimiz Ne Diyor" testId="site-reviews-block">
      {rating && <div className="flex items-center gap-2 mb-6"><span className="text-3xl font-black">{rating.avg}</span><div className="flex">{[1, 2, 3, 4, 5].map((s) => <Star key={s} size={16} weight={s <= Math.round(rating.avg) ? "fill" : "regular"} style={{ color: th.accent }} />)}</div><span className="text-xs" style={{ color: th.muted }}>{rating.count} yorum</span></div>}
      <div className="grid md:grid-cols-3 gap-4">
        {reviews.map((r) => (
          <div key={r.id} className="p-5" style={{ background: th.card, border: `1px solid ${th.cardBorder}`, borderRadius: th.radius }}>
            <div className="flex mb-2">{[1, 2, 3, 4, 5].map((s) => <Star key={s} size={12} weight={s <= r.rating ? "fill" : "regular"} style={{ color: th.accent }} />)}</div>
            <p className="text-sm leading-relaxed line-clamp-4">"{r.review_text}"</p>
            <div className="text-xs font-bold mt-3" style={{ color: th.muted }}>— {r.guest_name || "Misafir"}</div>
          </div>
        ))}
      </div>
    </Section>
  );
}

export function MapBlock({ th, content, propertyName }) {
  const q = content.map_query || content.address;
  if (!q) return null;
  return (
    <Section th={th} title="Konum" testId="site-map-block">
      <div className="grid md:grid-cols-[1fr_2fr] gap-5 items-stretch">
        <div className="p-5 text-sm space-y-3" style={{ background: th.card, border: `1px solid ${th.cardBorder}`, borderRadius: th.radius }}>
          <div className="font-bold" style={{ fontFamily: th.heading }}>{propertyName}</div>
          {content.address && <div className="flex gap-2"><MapPin size={16} style={{ color: th.accent }} className="flex-shrink-0 mt-0.5" /><span>{content.address}</span></div>}
          {content.phone && <div className="flex gap-2"><Phone size={16} style={{ color: th.accent }} /><a href={`tel:${content.phone}`}>{content.phone}</a></div>}
          {content.email && <div className="flex gap-2"><EnvelopeSimple size={16} style={{ color: th.accent }} /><a href={`mailto:${content.email}`}>{content.email}</a></div>}
          <a href={`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(q)}`} target="_blank" rel="noreferrer" className="inline-block text-xs font-bold px-3 py-2 mt-2" style={{ background: th.accent, color: th.accentText, borderRadius: th.radius }}>Yol tarifi al</a>
        </div>
        <iframe title="map" loading="lazy" className="w-full min-h-[280px] border-0" style={{ borderRadius: th.radius, filter: th.bg.startsWith("#0") || th.bg.startsWith("#1") ? "invert(0.9) hue-rotate(180deg)" : "none" }}
          src={`https://maps.google.com/maps?q=${encodeURIComponent(q)}&z=15&output=embed`} data-testid="site-map-iframe" />
      </div>
    </Section>
  );
}

export function FaqBlock({ th, faqs }) {
  const [open, setOpen] = useState(0);
  if (!faqs?.length) return null;
  return (
    <Section th={th} title="Sık Sorulan Sorular" testId="site-faq-block">
      <div className="space-y-2 max-w-3xl">
        {faqs.map((f, i) => (
          <div key={i} style={{ background: th.card, border: `1px solid ${th.cardBorder}`, borderRadius: th.radius }}>
            <button onClick={() => setOpen(open === i ? -1 : i)} className="w-full flex items-center justify-between gap-3 p-4 text-left text-sm font-bold" data-testid={`site-faq-${i}`}>
              {f.q}<CaretDown size={16} className={`transition-transform ${open === i ? "rotate-180" : ""}`} style={{ color: th.accent }} />
            </button>
            {open === i && <div className="px-4 pb-4 text-sm leading-relaxed" style={{ color: th.muted }}>{f.a}</div>}
          </div>
        ))}
      </div>
    </Section>
  );
}

export function ContactBlock({ th, propertyId }) {
  const [f, setF] = useState({ name: "", email: "", phone: "", message: "" });
  const [done, setDone] = useState(false); const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const inp = { background: th.bg, color: th.text, border: `1px solid ${th.cardBorder}`, borderRadius: th.radius };
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr("");
    try { await axios.post(`${API}/site-builder/public/contact`, { property_id: propertyId, ...f }); setDone(true); }
    catch (ex) { setErr(ex.response?.data?.detail || "Gönderilemedi"); } finally { setBusy(false); }
  };
  return (
    <Section th={th} title="Bize Ulaşın" testId="site-contact-block">
      <div className="p-6 max-w-2xl" style={{ background: th.card, border: `1px solid ${th.cardBorder}`, borderRadius: th.radius }}>
        {done ? (
          <div className="flex items-center gap-3 text-sm font-semibold" data-testid="site-contact-done"><CheckCircle size={24} weight="fill" style={{ color: th.accent }} /> Mesajınız alındı, en kısa sürede dönüş yapacağız.</div>
        ) : (
          <form onSubmit={submit} className="grid sm:grid-cols-2 gap-3">
            <input required placeholder="Ad Soyad" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="px-3 py-2.5 text-sm" style={inp} data-testid="site-contact-name" />
            <input required type="email" placeholder="E-posta" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} className="px-3 py-2.5 text-sm" style={inp} data-testid="site-contact-email" />
            <input placeholder="Telefon (opsiyonel)" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} className="px-3 py-2.5 text-sm sm:col-span-2" style={inp} data-testid="site-contact-phone" />
            <textarea required rows={4} placeholder="Mesajınız" value={f.message} onChange={(e) => setF({ ...f, message: e.target.value })} className="px-3 py-2.5 text-sm sm:col-span-2" style={inp} data-testid="site-contact-message" />
            {err && <p className="text-xs text-red-500 sm:col-span-2">{err}</p>}
            <button type="submit" disabled={busy} className="sm:col-span-2 py-3 text-sm font-bold disabled:opacity-60" style={{ background: th.accent, color: th.accentText, borderRadius: th.radius }} data-testid="site-contact-submit">Gönder</button>
          </form>
        )}
      </div>
    </Section>
  );
}

export function GalleryBlock({ th, gallery, full }) {
  if (!gallery?.length) return null;
  return (
    <Section th={th} title="Galeri" testId="site-gallery">
      <div className={`grid gap-3 ${full ? "grid-cols-2 sm:grid-cols-3" : "grid-cols-2 sm:grid-cols-4"}`}>
        {gallery.map((p, i) => (
          <img key={p.id} src={`${apiBase}${p.url}`} alt="galeri" loading="lazy" className={`w-full object-cover hover:opacity-90 transition-opacity ${full ? "h-56" : "h-40"} ${i === 0 && !full ? "col-span-2 row-span-2 sm:h-full" : ""}`} style={{ borderRadius: th.radius }} />
        ))}
      </div>
    </Section>
  );
}
