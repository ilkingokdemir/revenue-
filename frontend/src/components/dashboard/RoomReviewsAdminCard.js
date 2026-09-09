import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const W = { withCredentials: true };

export default function RoomReviewsAdminCard({ propertyId }) {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    if (!propertyId || propertyId === "all") return;
    try { const r = await axios.get(`${API}/booking/room-reviews/${propertyId}`); setD(r.data); } catch { toast.error("Yorumlar yüklenemedi"); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);
  const autoTag = async () => {
    setBusy(true);
    try { const r = await axios.post(`${API}/booking/room-reviews/${propertyId}/auto-tag?limit=40`, {}, W); toast.success(`${r.data.processed} yorum işlendi, ${r.data.tagged} tanesi odaya eşlendi (${r.data.source === "ai" ? "AI" : "kelime eşleşmesi"})`); load(); }
    catch { toast.error("Eşleme başarısız"); } finally { setBusy(false); }
  };
  if (!propertyId || propertyId === "all") return <div className="text-sm text-stone-500 py-8 text-center" data-testid="rr-select-property">Üstten bir tesis seçin.</div>;
  if (!d) return null;
  const tagged = d.rooms.reduce((a, r) => a + r.count, 0);
  return (
    <div className="bg-white rounded-2xl border border-stone-200 p-4" data-testid="room-reviews-admin-card">
      <div className="flex flex-wrap items-center gap-3 mb-3">
        <div><h3 className="font-semibold text-stone-900">Oda Bazlı Yorumlar</h3><p className="text-xs text-stone-500">Tesis puanı ★ {d.property_avg ?? "—"} ({d.property_count} yorum) · {tagged} yorum odaya eşlendi. AI, yorum metnindeki ipuçlarından (suite, king, aile, manzara…) oda tipini bulur; ipucu yoksa boş bırakır.</p></div>
        <button onClick={autoTag} disabled={busy} className="ml-auto px-3 py-1.5 rounded-lg bg-stone-900 text-white text-xs font-bold disabled:opacity-50" data-testid="rr-auto-tag">{busy ? "Eşleniyor…" : "✨ AI ile odalara eşle"}</button>
      </div>
      <div className="space-y-1">
        {d.rooms.map((r) => (
          <div key={r.room_type_id} className="flex flex-wrap items-center gap-2 text-xs bg-stone-50 rounded-lg px-2 py-1.5" data-testid={`rr-room-${r.room_type_id}`}>
            <span className="font-bold text-stone-800 w-48 truncate">{r.name}</span>
            <span className="text-amber-600 font-bold">{r.avg ? `★ ${r.avg}` : "—"}</span>
            <span className="text-stone-500">{r.count} yorum · {r.verified} doğrulanmış</span>
            {r.quotes[0] && <span className="text-stone-500 italic truncate flex-1">“{r.quotes[0].text}”</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
