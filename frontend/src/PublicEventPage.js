/**
 * Public Event Page — /events/{slug}
 *
 * Server-rendered-ish event detail page (Tripleseat Social SEO parity).
 * Includes JSON-LD structured data so Google indexes it as an Event.
 * No auth required.
 */
import { useState, useEffect } from "react";
import axios from "axios";
import { Calendar, MapPin, Ticket, Users, ArrowRight } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PublicEventPage() {
  const slug = window.location.pathname.replace(/^\/events\//, "");
  const [ev, setEv] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (!slug) { setErr("Slug yok"); return; }
    axios.get(`${API}/public-events/${slug}`)
         .then(r => {
           setEv(r.data);
           // Inject JSON-LD structured data for SEO
           const sd = r.data.structured_data;
           if (sd) {
             const script = document.createElement("script");
             script.type = "application/ld+json";
             script.text = JSON.stringify(sd);
             document.head.appendChild(script);
             document.title = `${r.data.title} · ${r.data.property_name}`;
             // OG meta
             const setMeta = (prop, val) => {
               let m = document.querySelector(`meta[property="${prop}"]`);
               if (!m) { m = document.createElement("meta"); m.setAttribute("property", prop); document.head.appendChild(m); }
               m.setAttribute("content", val);
             };
             setMeta("og:title", r.data.title);
             setMeta("og:description", (r.data.description || "").slice(0, 200));
             setMeta("og:type", "event");
             if (r.data.hero_image) setMeta("og:image", r.data.hero_image);
           }
         })
         .catch(e => setErr(e?.response?.data?.detail || "Etkinlik bulunamadı"));
  }, [slug]);

  if (err) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center p-6" data-testid="event-not-found">
        <div className="text-center">
          <div className="text-4xl mb-3">😔</div>
          <div className="text-stone-700">{err}</div>
        </div>
      </div>
    );
  }

  if (!ev) {
    return <div className="min-h-screen bg-stone-50 flex items-center justify-center text-stone-400 text-sm">Yükleniyor…</div>;
  }

  return (
    <div className="min-h-screen bg-stone-50" data-testid="public-event-page">
      <div className="max-w-3xl mx-auto bg-white shadow-sm">
        {ev.hero_image && (
          <img src={ev.hero_image} alt={ev.title} className="w-full h-72 object-cover" />
        )}
        <div className="p-8">
          <div className="text-[11px] uppercase tracking-[0.18em] text-rose-600 mb-2">
            {ev.property_name} · {ev.property_city}
          </div>
          <h1 className="text-4xl sm:text-5xl font-semibold text-stone-900 leading-tight">
            {ev.title}
          </h1>
          <div className="flex flex-wrap gap-6 mt-6 text-sm text-stone-700">
            <Info icon={Calendar} label={`${ev.date} · ${ev.start_time}-${ev.end_time}`} />
            {ev.property_address && <Info icon={MapPin} label={ev.property_address} />}
            <Info icon={Users} label={`${ev.capacity} kişi kapasiteli`} />
            {ev.price_from > 0 && <Info icon={Ticket} label={`${ev.price_from} ${ev.currency}'den başlayan`} />}
          </div>
          {(ev.tags || []).length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-4">
              {ev.tags.map(t => <span key={t} className="text-xs bg-rose-100 text-rose-700 px-2 py-1 rounded-full">{t}</span>)}
            </div>
          )}
          <div className="text-base text-stone-700 leading-relaxed mt-6 whitespace-pre-line">
            {ev.description}
          </div>
          {ev.ticket_url && (
            <a href={ev.ticket_url} target="_blank" rel="noopener noreferrer"
               data-testid="event-ticket-cta"
               className="inline-flex items-center gap-2 mt-8 px-6 py-3 bg-rose-600 text-white rounded-lg text-base font-medium hover:bg-rose-700">
              Bilet Al <ArrowRight size={16} weight="bold" />
            </a>
          )}
          <div className="text-xs text-stone-400 mt-12 pt-6 border-t border-stone-200">
            {ev.property_name} tarafından düzenlenmektedir.
          </div>
        </div>
      </div>
    </div>
  );
}

function Info({ icon: Icon, label }) {
  return (
    <div className="inline-flex items-center gap-1.5">
      <Icon size={16} weight="fill" className="text-rose-600" />
      <span>{label}</span>
    </div>
  );
}
