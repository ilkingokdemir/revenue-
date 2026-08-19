import { useState, useEffect } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const THEMES = {
  classic: { bg: "bg-[#faf6f0]", text: "text-stone-800", accent: "bg-amber-700 hover:bg-amber-800", card: "bg-white border border-amber-100", hero: "bg-gradient-to-br from-amber-800 to-amber-600" },
  modern: { bg: "bg-stone-950", text: "text-stone-100", accent: "bg-cyan-500 hover:bg-cyan-400 text-stone-950", card: "bg-stone-900 border border-stone-800", hero: "bg-gradient-to-br from-stone-900 to-cyan-950" },
  boutique: { bg: "bg-white", text: "text-stone-900", accent: "bg-stone-900 hover:bg-stone-700", card: "bg-stone-50 border border-stone-200", hero: "bg-gradient-to-br from-rose-100 to-stone-100" },
};

export function CustomDomainSite({ fallback }) {
  const [pid, setPid] = useState(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    axios.get(`${API}/site-builder/public/resolve-domain`, { params: { host: window.location.host } })
      .then(({ data }) => setPid(data.property_id))
      .catch(() => {})
      .finally(() => setChecked(true));
  }, []);

  if (!checked) return <div className="min-h-screen flex items-center justify-center text-stone-400 text-sm">Yükleniyor…</div>;
  if (pid) return <HotelSitePage propertyId={pid} />;
  return fallback || null;
}

export default function HotelSitePage({ propertyId }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    axios.get(`${API}/site-builder/public/site/${propertyId}`)
      .then(({ data: d }) => setData(d))
      .catch(() => setErr(true));
  }, [propertyId]);

  if (err) return <div className="min-h-screen flex items-center justify-center text-stone-500 text-sm" data-testid="site-not-found">Bu site yayında değil.</div>;
  if (!data) return <div className="min-h-screen flex items-center justify-center text-stone-400 text-sm">Yükleniyor…</div>;

  const t = THEMES[data.site.template] || THEMES.classic;
  const c = data.site.content || {};
  const name = data.property?.name || propertyId;
  const rawAm = c.amenities;
  const amenities = Array.isArray(rawAm)
    ? rawAm.map((x) => String(x).trim()).filter(Boolean)
    : String(rawAm || "").split(",").map((x) => x.trim()).filter(Boolean);
  const heroDark = data.site.template !== "boutique";
  const cover = (data.photos || []).find((p) => p.kind === "cover");
  const gallery = (data.photos || []).filter((p) => p.kind === "gallery");
  const apiBase = process.env.REACT_APP_BACKEND_URL;

  return (
    <div className={`min-h-screen ${t.bg} ${t.text}`} data-testid="hotel-site-page">
      <div className={`${t.hero} px-6 py-24 text-center relative overflow-hidden`}
        style={cover ? { backgroundImage: `linear-gradient(rgba(0,0,0,.45), rgba(0,0,0,.55)), url(${apiBase}${cover.url})`, backgroundSize: "cover", backgroundPosition: "center" } : undefined}>
        <h1 className={`relative text-4xl sm:text-5xl lg:text-6xl font-black ${heroDark || cover ? "text-white" : "text-stone-900"}`} data-testid="site-hero-title">{name}</h1>
        {c.headline && <p className={`relative mt-4 text-base md:text-lg ${heroDark || cover ? "text-white/80" : "text-stone-600"}`}>{c.headline}</p>}
        <a href={`/book/${propertyId}`} data-testid="site-book-cta"
          className={`relative inline-block mt-8 px-8 py-3 rounded-full text-sm font-black text-white ${t.accent} transition-colors`}>
          Rezervasyon Yap
        </a>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-14 space-y-12">
        {c.about && (
          <section>
            <h2 className="text-lg font-bold mb-3">Hakkımızda</h2>
            <p className="text-sm opacity-80 leading-relaxed" data-testid="site-about-text">{c.about}</p>
          </section>
        )}
        {amenities.length > 0 && (
          <section>
            <h2 className="text-lg font-bold mb-3">Olanaklar</h2>
            <div className="flex flex-wrap gap-2">
              {amenities.map((a) => (
                <span key={a} className={`text-xs px-3 py-1.5 rounded-full ${t.card}`}>{a}</span>
              ))}
            </div>
          </section>
        )}
        {gallery.length > 0 && (
          <section data-testid="site-gallery">
            <h2 className="text-lg font-bold mb-3">Galeri</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {gallery.map((p) => (
                <img key={p.id} src={`${apiBase}${p.url}`} alt="galeri" className="w-full h-40 object-cover rounded-xl" loading="lazy" />
              ))}
            </div>
          </section>
        )}
        {data.room_types?.length > 0 && (
          <section>
            <h2 className="text-lg font-bold mb-3">Odalarımız</h2>
            <div className="grid sm:grid-cols-2 gap-3">
              {data.room_types.map((r) => (
                <div key={r.id} className={`rounded-xl p-4 ${t.card}`} data-testid={`site-room-${r.id}`}>
                  <div className="text-sm font-bold">{r.name}</div>
                  <div className="text-xs opacity-70 mt-1">£{r.base_rate || r.base_price || "-"} / gece'den itibaren</div>
                  <a href={`/book/${propertyId}`} className="inline-block mt-3 text-xs font-bold underline">Müsaitliğe bak →</a>
                </div>
              ))}
            </div>
          </section>
        )}
        <section className={`rounded-xl p-5 ${t.card} text-xs space-y-1`}>
          <h2 className="text-sm font-bold mb-2">İletişim</h2>
          {c.phone && <div data-testid="site-phone">📞 {c.phone}</div>}
          {c.email && <div>✉️ {c.email}</div>}
          {c.address && <div>📍 {c.address}</div>}
        </section>
      </div>
      <footer className="text-center text-[10px] opacity-50 pb-6">Powered by MyHotelBox</footer>
    </div>
  );
}
