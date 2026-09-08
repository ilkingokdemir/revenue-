import React, { useEffect, useState } from "react";
import axios from "axios";
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const iso = (d) => d.toISOString().slice(0, 10);
export default function ChainSearchPage() {
  const q = new URLSearchParams(window.location.search);
  const [ci, setCi] = useState(q.get("check_in") || iso(new Date(Date.now() + 7 * 864e5)));
  const [co, setCo] = useState(q.get("check_out") || iso(new Date(Date.now() + 9 * 864e5)));
  const [adults, setAdults] = useState(Number(q.get("adults") || 2));
  const [data, setData] = useState(null); const [busy, setBusy] = useState(false);
  const search = async () => { setBusy(true); try { const r = await axios.get(`${API}/booking/chain-search`, { params: { check_in: ci, check_out: co, adults } }); setData(r.data); } catch { setData({ properties: [] }); } finally { setBusy(false); } };
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
        <div className="mt-4 space-y-3">
          {data?.properties?.map((p) => (
            <div key={p.property_id} className={`bg-white rounded-2xl border p-4 flex gap-4 items-center ${p.available ? "border-stone-200" : "border-stone-100 opacity-60"}`} data-testid={`chain-prop-${p.property_id}`}>
              {p.image_url ? <img src={p.image_url} alt="" className="w-24 h-20 object-cover rounded-xl" /> : <div className="w-24 h-20 rounded-xl bg-stone-100" />}
              <div className="flex-1 min-w-0"><div className="font-bold text-stone-900">{p.name} {p.star_rating ? <span className="text-amber-500 text-xs">{"★".repeat(p.star_rating)}</span> : null}</div>
                <div className="text-xs text-stone-500">{[p.city, p.country].filter(Boolean).join(", ")}</div>
                {p.best ? <div className="text-xs text-stone-600 mt-1">{p.best.room_name} · {p.best.rooms_left} oda kaldı</div> : <div className="text-xs text-rose-600 mt-1">Bu tarihlerde müsait oda yok</div>}</div>
              <div className="text-right">{p.total_from != null && <div className="text-lg font-black text-stone-900" data-testid={`chain-price-${p.property_id}`}>{p.currency} {p.total_from.toFixed(0)}<div className="text-[10px] text-stone-400 font-normal">{p.nights} gece toplam</div></div>}
                <a href={p.available ? p.book_url : undefined} className={`inline-block mt-1 px-3 py-1.5 rounded-lg text-xs font-bold ${p.available ? "bg-emerald-600 text-white" : "bg-stone-100 text-stone-400 pointer-events-none"}`} data-testid={`chain-book-${p.property_id}`}>Rezerve et</a></div>
            </div>
          ))}
          {data && !data.properties?.length && <p className="text-sm text-stone-500">Sonuç yok.</p>}
        </div>
      </div>
    </div>
  );
}
