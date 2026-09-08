import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const STATUS = { pending: "Bekliyor", approved: "Onaylandı", rejected: "Reddedildi" };
const COLOR = { pending: "bg-amber-100 text-amber-800", approved: "bg-emerald-100 text-emerald-800", rejected: "bg-rose-100 text-rose-700" };

export default function BrgClaimsCard({ propertyId }) {
  const [data, setData] = useState({ items: [], pending: 0 });
  const [busy, setBusy] = useState("");
  const load = useCallback(async () => {
    if (!propertyId || propertyId === "all") return;
    try { const r = await axios.get(`${API}/booking/brg-claims/${propertyId}`, { withCredentials: true }); setData(r.data); } catch { toast.error("Talepler yüklenemedi"); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  const decide = async (c, status) => {
    let matched = c.competitor_price; let note = "";
    if (status === "approved") { const v = window.prompt("Eşlenen fiyat", String(c.competitor_price)); if (v === null) return; matched = Number(v) || c.competitor_price; }
    else { note = window.prompt("Red gerekçesi (opsiyonel)", "") || ""; }
    setBusy(c.id);
    try { await axios.put(`${API}/booking/brg-claims/${c.id}`, { status, matched_price: matched, note }, { withCredentials: true }); toast.success(status === "approved" ? "Talep onaylandı, e-posta gönderildi" : "Talep reddedildi"); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Kaydedilemedi"); }
    finally { setBusy(""); }
  };

  if (!propertyId || propertyId === "all") return <div className="text-sm text-stone-500 py-8 text-center" data-testid="brg-select-property">Talepleri görmek için üstten bir tesis seçin.</div>;
  return (
    <div className="bg-white rounded-2xl border border-stone-200 p-4" data-testid="brg-claims-card">
      <div className="flex items-center justify-between mb-3">
        <div><h3 className="font-semibold text-stone-900">En İyi Fiyat Garantisi Talepleri</h3><p className="text-xs text-stone-500">Misafir rakip sitede daha ucuz fiyat bildirdi — 24 saat içinde karar verin.</p></div>
        <span className="text-xs font-bold px-2 py-1 rounded-full bg-amber-100 text-amber-800" data-testid="brg-pending-count">{data.pending} bekleyen</span>
      </div>
      {!data.items.length && <div className="text-sm text-stone-400 py-6 text-center" data-testid="brg-empty">Henüz talep yok.</div>}
      <div className="space-y-2">
        {data.items.map((c) => (
          <div key={c.id} className="border border-stone-100 rounded-xl p-3 flex flex-wrap gap-3 items-center" data-testid={`brg-claim-${c.id}`}>
            <div className="flex-1 min-w-[220px]">
              <div className="text-sm font-semibold text-stone-900">{c.email} {c.booking_ref && <span className="text-xs text-stone-400 font-normal">· {c.booking_ref}</span>}</div>
              <div className="text-xs text-stone-500">{c.check_in} → {c.check_out} · Bizim: {c.currency} {c.our_price} · Rakip: <b className="text-rose-600">{c.currency} {c.competitor_price}</b></div>
              <a href={c.competitor_url} target="_blank" rel="noreferrer" className="text-xs text-sky-600 underline break-all">{c.competitor_url}</a>
              {c.note && <div className="text-xs text-stone-500 italic mt-1">“{c.note}”</div>}
            </div>
            <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${COLOR[c.status]}`} data-testid={`brg-status-${c.id}`}>{STATUS[c.status]}{c.matched_price ? ` · ${c.currency} ${c.matched_price}` : ""}</span>
            {c.status === "pending" && (
              <div className="flex gap-1">
                <button disabled={busy === c.id} onClick={() => decide(c, "approved")} className="px-3 py-1.5 text-xs font-bold rounded-lg bg-emerald-600 text-white disabled:opacity-50" data-testid={`brg-approve-${c.id}`}>Onayla</button>
                <button disabled={busy === c.id} onClick={() => decide(c, "rejected")} className="px-3 py-1.5 text-xs font-bold rounded-lg bg-stone-100 text-stone-700 disabled:opacity-50" data-testid={`brg-reject-${c.id}`}>Reddet</button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
