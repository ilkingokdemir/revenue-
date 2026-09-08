import React, { useEffect, useState } from "react";
import axios from "axios";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const iso = (d) => d.toISOString().slice(0, 10);
export default function ChainSearchPage() {
  const q = new URLSearchParams(window.location.search);
  const [ci, setCi] = useState(q.get("check_in") || iso(new Date(Date.now() + 7 * 864e5)));
  const [co, setCo] = useState(q.get("check_out") || iso(new Date(Date.now() + 9 * 864e5)));
  const [adults, setAdults] = useState(Number(q.get("adults") || 2));
  const [data, setData] = useState(null); const [busy, setBusy] = useState(false);
  const [maxPrice, setMaxPrice] = useState(null); const [stars, setStars] = useState([]); const [onlyAvail, setOnlyAvail] = useState(false);
  const all = data?.properties || [];
  const priceCap = Math.max(0, ...all.map((p) => p.total_from || 0));
  const shown = all.filter((p) => (maxPrice == null || p.total_from == null || p.total_from <= maxPrice) && (!stars.length || stars.includes(Number(p.star_rating) || 0)) && (!onlyAvail || p.available));
  const search = async () => { setBusy(true); try { const r = await axios.get(`${API}/booking/chain-search`, { params: { check_in: ci, check_out: co, adults } }); setData(r.data); setMaxPrice(null); } catch { setData({ properties: [] }); } finally { setBusy(false); } };
  useEffect(() => { search(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  return (
    <div className="min-h-screen bg-stone-50 p-6" data-testid="chain-search-page">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-black text-stone-900 mb-1">Tüm tesislerde ara</h1>
        <p className="text-sm text-stone-500 mb-4">Tek aramada tüm şubeler — en uygun oda ve fiyatı karşılaştırın.</p>
        <div className="bg-white rounded-2xl border border-stone-200 p-4 flex flex-wrap gap-2 items-end">
          <label className="text-xs text-stone-500">Giriş<input type="date" value={ci} onChange={(e) => setCi(e.target.value)} className="block border rounded-lg px-2 py-1.5 text-sm" data-testid="chain-checkin" /></label>
          <label className="text-xs text-stone-500">Çıkış<input type="date" value={co} onChange={(e) => setCo(e.target.value)} className="block border rounded-lg px-2 py-1.5 text-sm" data-testid="chain-checkout" /></label>
          <label className="text-xs text-stone-500">Kişi<input type="number" min="1" value={adults} onChange={(e) => setAdults(Number(e.target.value))} className="block border rounded-lg px-2 py-1.5 text-sm w-20" data-testid="chain-adults" /></label>
          <button onClick={search} disabled={busy} className="px-5 py-2 rounded-lg bg-stone-900 text-white text-sm font-bold disabled:opacity-50" data-testid="chain-search-btn">{busy ? "…" : "Ara"}</button>
        </div>
        {all.length > 0 && <FilterBar priceCap={priceCap} maxPrice={maxPrice} setMaxPrice={setMaxPrice} stars={stars} setStars={setStars} onlyAvail={onlyAvail} setOnlyAvail={setOnlyAvail} shown={shown.length} total={all.length} currency={all[0]?.currency} />}
        <ChainMap items={shown} />
        <div className="mt-4 space-y-3">
          {shown.map((p) => (
            <div key={p.property_id} className={`bg-white rounded-2xl border p-4 flex gap-4 items-center ${p.available ? "border-stone-200" : "border-stone-100 opacity-60"}`} data-testid={`chain-prop-${p.property_id}`}>
              {p.image_url ? <img src={p.image_url} alt="" className="w-24 h-20 object-cover rounded-xl" /> : <div className="w-24 h-20 rounded-xl bg-stone-100" />}
              <div className="flex-1 min-w-0"><div className="font-bold text-stone-900">{p.name} {p.star_rating ? <span className="text-amber-500 text-xs">{"★".repeat(p.star_rating)}</span> : null}</div>
                <div className="text-xs text-stone-500">{[p.city, p.country].filter(Boolean).join(", ")}</div>
                {p.best ? <div className="text-xs text-stone-600 mt-1">{p.best.room_name} · {p.best.rooms_left} oda kaldı</div> : <div className="text-xs text-rose-600 mt-1">Bu tarihlerde müsait oda yok</div>}</div>
              <div className="text-right">{p.total_from != null && <div className="text-lg font-black text-stone-900" data-testid={`chain-price-${p.property_id}`}>{p.currency} {p.total_from.toFixed(0)}<div className="text-[10px] text-stone-400 font-normal">{p.nights} gece toplam</div></div>}
                <a href={p.available ? p.book_url : undefined} className={`inline-block mt-1 px-3 py-1.5 rounded-lg text-xs font-bold ${p.available ? "bg-emerald-600 text-white" : "bg-stone-100 text-stone-400 pointer-events-none"}`} data-testid={`chain-book-${p.property_id}`}>Rezerve et</a></div>
            </div>
          ))}
          {data && !shown.length && <p className="text-sm text-stone-500" data-testid="chain-no-results">{all.length ? "Filtrelere uyan tesis yok." : "Sonuç yok."}</p>}
        </div>
      </div>
    </div>
  );
}

function FilterBar({ priceCap, maxPrice, setMaxPrice, stars, setStars, onlyAvail, setOnlyAvail, shown, total, currency }) {
  const cur = maxPrice == null ? priceCap : maxPrice;
  const toggleStar = (n) => setStars(stars.includes(n) ? stars.filter((x) => x !== n) : [...stars, n]);
  return (
    <div className="mt-3 bg-white rounded-2xl border border-stone-200 p-3 flex flex-wrap gap-4 items-center" data-testid="chain-filters">
      <label className="text-xs text-stone-600 flex items-center gap-2">Maks. fiyat
        <input type="range" min={0} max={priceCap || 1} step={1} value={cur} onChange={(e) => setMaxPrice(Number(e.target.value))} className="w-40 accent-teal-700" data-testid="chain-filter-price" />
        <b className="text-stone-900" data-testid="chain-filter-price-value">{currency} {Math.round(cur)}</b>
      </label>
      <div className="flex items-center gap-1 text-xs text-stone-600">Yıldız
        {[5, 4, 3].map((n) => <button key={n} onClick={() => toggleStar(n)} className={`px-2 py-1 rounded-full border text-[11px] font-bold ${stars.includes(n) ? "bg-amber-400 border-amber-400 text-stone-900" : "border-stone-300 text-stone-600"}`} data-testid={`chain-filter-star-${n}`}>{n}★</button>)}
      </div>
      <label className="text-xs text-stone-600 flex items-center gap-1.5"><input type="checkbox" checked={onlyAvail} onChange={(e) => setOnlyAvail(e.target.checked)} data-testid="chain-filter-avail" />Sadece müsait</label>
      <span className="ml-auto text-[11px] text-stone-500" data-testid="chain-filter-count">{shown}/{total} tesis</span>
      {(maxPrice != null || stars.length || onlyAvail) ? <button onClick={() => { setMaxPrice(null); setStars([]); setOnlyAvail(false); }} className="text-[11px] underline text-stone-500" data-testid="chain-filter-reset">Sıfırla</button> : null}
    </div>
  );
}

function ChainMap({ items }) {
  const ref = React.useRef(null); const mapRef = React.useRef(null);
  const pts = items.filter((p) => p.geo?.lat);
  useEffect(() => {
    if (!pts.length || !ref.current) { if (mapRef.current) { mapRef.current.remove(); mapRef.current = null; } return; }
    {
      if (!mapRef.current) { mapRef.current = L.map(ref.current, { scrollWheelZoom: false }); L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap" }).addTo(mapRef.current); }
      const m = mapRef.current; m.eachLayer((l) => { if (l instanceof L.Marker) m.removeLayer(l); });
      const b = [];
      const groups = {};
      pts.forEach((p) => { const k = `${p.geo.lat.toFixed(4)},${p.geo.lng.toFixed(4)}`; (groups[k] = groups[k] || []).push(p); });
      const lbl = (p) => (p.total_from != null ? `${p.currency} ${Math.round(p.total_from)}` : "Dolu");
      Object.values(groups).forEach((g) => {
        const avail = g.filter((x) => x.available && x.total_from != null).sort((a, c) => a.total_from - c.total_from);
        const p = avail[0] || g[0];
        const label = g.length > 1 ? `${g.length} tesis · ${avail.length ? lbl(avail[0]) + "'dan" : "Dolu"}` : lbl(p);
        const icon = L.divIcon({ className: "", html: `<div data-testid="map-pin-${p.property_id}" style="background:${avail.length ? "#0f766e" : "#9ca3af"};color:#fff;font:700 11px system-ui;padding:4px 8px;border-radius:999px;white-space:nowrap;box-shadow:0 2px 6px rgba(0,0,0,.3)">${label}</div>`, iconSize: null, iconAnchor: [30, 14] });
        const popup = g.map((x) => `<div style="margin:4px 0"><b>${x.name}</b> · ${x.best ? x.best.room_name + " · " + lbl(x) : "Müsait değil"}${x.available ? ` <a href="${x.book_url}">Rezerve et →</a>` : ""}</div>`).join("");
        L.marker([p.geo.lat, p.geo.lng], { icon }).addTo(m).bindPopup(`<div style="font-size:12px">${p.city ? `<div style="color:#666">${p.city}</div>` : ""}${popup}</div>`, { maxWidth: 320 });
        b.push([p.geo.lat, p.geo.lng]);
      });
      m.fitBounds(b, { padding: [30, 30], maxZoom: 12 });
    }
  }, [pts]);
  if (!pts.length) return null;
  return <div ref={ref} className="mt-4 h-72 rounded-2xl border border-stone-200 overflow-hidden" data-testid="chain-map" />;
}
