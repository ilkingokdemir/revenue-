import React, { useEffect, useState } from "react";
import axios from "axios";
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
export default function WishlistPage() {
  const code = window.location.pathname.split("/wishlist/")[1]?.split("/")[0] || "";
  const [w, setW] = useState(null); const [err, setErr] = useState("");
  useEffect(() => { axios.get(`${API}/booking/wishlist/${code}`).then((r) => setW(r.data)).catch(() => setErr("Liste bulunamadı")); }, [code]);
  if (err) return <div className="min-h-screen flex items-center justify-center text-slate-600" data-testid="wishlist-error">{err}</div>;
  if (!w) return <div className="min-h-screen flex items-center justify-center text-slate-400">Yükleniyor…</div>;
  return (
    <div className="min-h-screen bg-stone-50 p-6" data-testid="wishlist-page">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-2xl font-black text-stone-900">❤ Wishlist <span className="font-mono text-base text-stone-400">{w.code}</span></h1>
        <p className="text-sm text-stone-500 mb-5">{w.check_in} → {w.check_out} · {w.adults} kişi · {w.views} görüntülenme</p>
        <div className="grid sm:grid-cols-2 gap-4">
          {w.rooms.map((r) => (
            <a key={r.id} href={r.book_url} className="bg-white rounded-2xl border border-stone-200 overflow-hidden hover:shadow-md transition-shadow" data-testid={`wishlist-room-${r.id}`}>
              {r.image_url && <img src={r.image_url} alt={r.name} className="w-full h-36 object-cover" />}
              <div className="p-4"><div className="font-bold text-stone-900">{r.name}</div><div className="text-xs text-stone-500">{r.property_name}{r.city ? ` · ${r.city}` : ""}{r.max_occupancy ? ` · ${r.max_occupancy} kişi` : ""}</div>
                <div className="mt-2 text-sm font-black" style={{ color: "#0f766e" }}>{r.currency} {Number(r.base_price || 0).toFixed(0)} / gece →</div></div>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
