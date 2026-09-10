import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const W = { withCredentials: true };

export default function RoomReviewsAdminCard({ propertyId }) {
  const [d, setD] = useState(null);
  const [drafts, setDrafts] = useState([]);
  const [edits, setEdits] = useState({});
  const [busy, setBusy] = useState(false);
  const [acting, setActing] = useState("");
  const load = useCallback(async () => {
    if (!propertyId || propertyId === "all") return;
    try { const r = await axios.get(`${API}/booking/room-reviews/${propertyId}`); setD(r.data); } catch { toast.error("Yorumlar yüklenemedi"); }
    try { const r = await axios.get(`${API}/booking/room-reviews/${propertyId}/drafts`, W); setDrafts(r.data.drafts); } catch { /* ignore */ }
  }, [propertyId]);
  const draftAll = async () => {
    setBusy(true);
    try { const r = await axios.post(`${API}/booking/room-reviews/${propertyId}/draft-replies?limit=20`, {}, W); toast.success(`${r.data.drafted} taslak yanıt üretildi`); load(); }
    catch { toast.error("Taslak üretilemedi"); } finally { setBusy(false); }
  };
  const approve = async (rv) => {
    setActing(rv.id);
    try {
      const text = edits[rv.id] ?? rv.response_text;
      if (text !== rv.response_text) await axios.post(`${API}/reviews/${rv.id}/submit-for-approval`, { response_text: text }, W);
      const notes = rv.risk_level === "high" || rv.risk_level === "critical" ? window.prompt("Yüksek riskli yorum — onay gerekçesi:", "") : undefined;
      if (notes === null) return;
      await axios.post(`${API}/reviews/${rv.id}/approve`, { action: "approve", notes }, W);
      toast.success("Yanıt onaylandı ve yayımlandı"); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Onaylanamadı"); } finally { setActing(""); }
  };
  const reject = async (rv) => {
    setActing(rv.id);
    try { await axios.post(`${API}/reviews/${rv.id}/approve`, { action: "reject", notes: "room-tag draft rejected" }, W); toast.success("Taslak reddedildi"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Reddedilemedi"); } finally { setActing(""); }
  };
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
        <button onClick={draftAll} disabled={busy} className="px-3 py-1.5 rounded-lg border border-stone-300 text-xs font-bold disabled:opacity-50" data-testid="rr-draft-all">✍ Yanıt taslağı üret</button>
      </div>
      {drafts.length > 0 && (
        <div className="mb-4 space-y-2" data-testid="rr-drafts">
          <div className="text-xs font-bold text-stone-700">Onay bekleyen AI yanıt taslakları <span className="px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-800" data-testid="rr-drafts-count">{drafts.length}</span></div>
          {drafts.map((rv) => (
            <div key={rv.id} className="border border-amber-100 bg-amber-50/40 rounded-xl p-3 text-xs" data-testid={`rr-draft-${rv.id}`}>
              <div className="flex flex-wrap items-center gap-2 mb-1"><span className="font-bold text-stone-800">{rv.guest}</span><span className="text-amber-600 font-bold">★ {rv.rating}</span>{rv.draft_room_name && <span className="px-1.5 py-0.5 rounded-full bg-stone-100 text-stone-600">{rv.draft_room_name}</span>}<span className="text-stone-400">{rv.platform || "direct"} · {String(rv.created_at || "").slice(0, 10)}</span>{rv.risk_level !== "low" && <span className="px-1.5 py-0.5 rounded-full bg-rose-100 text-rose-700 font-bold">risk: {rv.risk_level}</span>}</div>
              <div className="text-stone-600 italic mb-2">“{rv.text}”</div>
              <textarea value={edits[rv.id] ?? rv.response_text} onChange={(e) => setEdits({ ...edits, [rv.id]: e.target.value })} rows={3} className="w-full border border-stone-200 rounded-lg px-2 py-1.5 text-xs bg-white" data-testid={`rr-draft-text-${rv.id}`} />
              <div className="flex gap-2 mt-2">
                <button onClick={() => approve(rv)} disabled={acting === rv.id} className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white font-bold disabled:opacity-50" data-testid={`rr-approve-${rv.id}`}>✓ Onayla ve yayımla</button>
                <button onClick={() => reject(rv)} disabled={acting === rv.id} className="px-3 py-1.5 rounded-lg border border-stone-300 text-stone-600 font-bold disabled:opacity-50" data-testid={`rr-reject-${rv.id}`}>Reddet</button>
              </div>
            </div>
          ))}
        </div>
      )}
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
