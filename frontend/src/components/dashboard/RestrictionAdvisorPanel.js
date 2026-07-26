import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { LockKey, ArrowsClockwise, Check, X } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/restriction-advisor`;

export default function RestrictionAdvisorPanel({ propertyId = "all" }) {
  const [data, setData] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [filter, setFilter] = useState("pending");

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/${propertyId}`);
      setData(r.data);
    } catch { toast.error("Kısıtlama önerileri yüklenemedi"); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  async function scan() {
    setScanning(true);
    try {
      const r = await axios.post(`${API}/${propertyId}/scan`);
      toast.success(`${r.data.properties_scanned} tesis tarandı · ${r.data.recommendations} öneri üretildi`);
      load();
    } catch { toast.error("Tarama başarısız"); }
    setScanning(false);
  }

  async function act(rec, action) {
    try {
      const r = await axios.post(`${API}/recs/${rec.id}/${action}`);
      toast.success(action === "accept"
        ? `Uygulandı → ${(r.data.applied_channels || []).join(", ")} kanallarına push edildi`
        : "Öneri reddedildi (7 gün tekrar önerilmez)");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "İşlem başarısız"); }
  }

  if (!data) return <div className="p-8 text-center text-stone-400">Yükleniyor…</div>;
  const s = data.summary;
  const rows = data.recommendations.filter(r => !filter || r.status === filter);

  return (
    <div className="p-5 max-w-[1100px] mx-auto space-y-4" data-testid="restriction-advisor-panel">
      <div className="bg-gradient-to-br from-stone-900 via-violet-950 to-fuchsia-900 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-violet-300">
              <LockKey size={14} /> AI Restriction Advisor
            </div>
            <h1 className="text-2xl font-bold mt-1">AI Kısıtlama Önerileri</h1>
            <p className="text-sm text-stone-300 mt-1">Yüksek talepli geceler için MLOS (min konaklama) ve CTA (varışa kapalı) önerileri. Kabul edilen öneri tüm bağlı kanallara yazılır ve OTA'ya push edilir.</p>
          </div>
          <button onClick={scan} disabled={scanning} data-testid="ra-scan-btn"
            className="px-4 py-2 bg-violet-400 hover:bg-violet-300 text-stone-900 rounded-lg text-sm font-bold inline-flex items-center gap-2 disabled:opacity-60">
            <ArrowsClockwise size={16} className={scanning ? "animate-spin" : ""} />
            {scanning ? "Taranıyor…" : "Şimdi Tara"}
          </button>
        </div>
        <div className="grid grid-cols-3 gap-3 mt-5">
          <Stat label="Bekleyen öneri" value={s.pending} testid="ra-stat-pending" />
          <Stat label="Uygulanan" value={s.accepted} testid="ra-stat-accepted" />
          <Stat label="Reddedilen" value={s.rejected} testid="ra-stat-rejected" />
        </div>
      </div>

      <div className="flex gap-1.5">
        {[["pending", "Bekleyen"], ["accepted", "Uygulanan"], ["rejected", "Reddedilen"], ["", "Tümü"]].map(([id, label]) => (
          <button key={id || "all"} onClick={() => setFilter(id)} data-testid={`ra-filter-${id || "all"}`}
            className={`px-3 py-1 text-xs rounded-full border ${filter === id ? "bg-stone-900 text-white border-stone-900" : "bg-white text-stone-600 border-stone-200 hover:bg-stone-50"}`}>
            {label}
          </button>
        ))}
      </div>

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="text-[11px] uppercase text-stone-400 border-b border-stone-100">
            <th className="text-left px-4 py-2">Tarih</th><th className="text-left px-2 py-2">Tesis</th>
            <th className="text-center px-2 py-2">Doluluk</th><th className="text-left px-2 py-2">Öneri</th>
            <th className="text-left px-2 py-2">Gerekçe</th><th className="px-2 py-2"></th>
          </tr></thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.id} className="border-b border-stone-50" data-testid={`ra-rec-${r.id}`}>
                <td className="px-4 py-2 font-mono text-xs">{r.date}</td>
                <td className="px-2 py-2 text-xs text-stone-500">{r.property_id}</td>
                <td className="px-2 py-2 text-center">
                  <span className={`text-[11px] px-2 py-0.5 rounded-full font-bold ${r.occupancy_pct >= 95 ? "bg-rose-50 text-rose-600" : "bg-amber-50 text-amber-700"}`}>%{r.occupancy_pct}</span>
                </td>
                <td className="px-2 py-2">
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${r.rec_type === "cta" ? "bg-rose-100 text-rose-700" : "bg-violet-50 text-violet-700"}`}>
                    {r.rec_type === "cta" ? "Varışa kapat (CTA)" : `Min ${r.min_los} gece (MLOS)`}
                  </span>
                </td>
                <td className="px-2 py-2 text-xs text-stone-500 max-w-[320px]">{r.rationale}</td>
                <td className="px-2 py-2 text-right whitespace-nowrap">
                  {r.status === "pending" ? (
                    <>
                      <button onClick={() => act(r, "accept")} data-testid={`ra-accept-${r.id}`}
                        className="p-1.5 text-emerald-600 hover:bg-emerald-50 rounded-lg" title="Uygula + OTA push"><Check size={16} /></button>
                      <button onClick={() => act(r, "reject")} data-testid={`ra-reject-${r.id}`}
                        className="p-1.5 text-stone-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg" title="Reddet"><X size={16} /></button>
                    </>
                  ) : (
                    <span className={`text-[10px] font-semibold ${r.status === "accepted" ? "text-emerald-600" : "text-stone-400"}`}>
                      {r.status === "accepted" ? `✓ ${r.accepted_by || ""}` : "✕ reddedildi"}
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-10 text-center text-stone-400 text-sm">
                Bu filtrede öneri yok. Motor her sabah 05:15'te tarar; "Şimdi Tara" ile manuel tetikleyebilirsiniz.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value, testid }) {
  return (
    <div className="bg-white/10 rounded-xl p-3" data-testid={testid}>
      <div className="text-[10px] uppercase tracking-wider text-stone-300">{label}</div>
      <div className="text-xl font-bold mt-0.5">{value}</div>
    </div>
  );
}
