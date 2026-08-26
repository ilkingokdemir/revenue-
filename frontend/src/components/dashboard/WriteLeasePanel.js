import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { LockKey, ArrowsClockwise } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/write-lease`;

export default function WriteLeasePanel({ propertyId = "default" }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState("");
  const pid = propertyId === "all" ? "default" : propertyId;

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/${pid}`);
      setData(r.data);
    } catch { toast.error("Kira listesi yüklenemedi"); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  async function demo() {
    setBusy("demo");
    try {
      const d = new Date(); d.setDate(d.getDate() + 5);
      const day = d.toISOString().slice(0, 10);
      const a = await axios.post(`${API}/${pid}/test-acquire`, { date: day, owner: "writer-A" });
      const b = await axios.post(`${API}/${pid}/test-acquire`, { date: day, owner: "writer-B" });
      toast.success(`Tatbikat: writer-A kira aldı (${a.data.acquired}), writer-B ÇİTE TAKILDI (${b.data.acquired ? "HATA!" : "engellendi ✓"})`);
      load();
    } catch { toast.error("Tatbikat başarısız"); }
    setBusy("");
  }

  async function forceReleaseAll() {
    setBusy("rel");
    try {
      const r = await axios.post(`${API}/${pid}/force-release`, {});
      toast.success(`Operatör egemenliği: ${r.data.released} kira iptal edildi`);
      load();
    } catch { toast.error("İptal başarısız"); }
    setBusy("");
  }

  if (!data) return <div className="p-8 text-center text-stone-400">Yükleniyor…</div>;

  return (
    <div className="p-5 max-w-[1000px] mx-auto space-y-4" data-testid="write-lease-panel">
      <div className="bg-gradient-to-br from-stone-900 via-slate-800 to-zinc-900 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-zinc-300">
              <LockKey size={14} /> Lease &amp; Fence
            </div>
            <h1 className="text-2xl font-bold mt-1">Yazım Kilidi (Kira &amp; Çit)</h1>
            <p className="text-sm text-stone-300 mt-1">
              Aynı fiyat hücresine iki otomatik yazıcı aynı anda giremez: her yazım sahiplik kirası + aktör imzası taşır.
              Son-gün ve zam merdivenleri bu kilitten geçer. Operatör egemendir — manuel yazım robot kiralarını iptal eder.
            </p>
          </div>
          <div className="flex gap-2">
            <button onClick={load} className="px-3 py-2 rounded-full bg-white/15 hover:bg-white/25 text-sm flex items-center gap-2" data-testid="lease-refresh-btn">
              <ArrowsClockwise size={16} /> Yenile
            </button>
            <button onClick={demo} disabled={busy === "demo"} data-testid="lease-demo-btn"
              className="px-4 py-2 rounded-full bg-zinc-400 hover:bg-zinc-300 text-stone-900 text-sm font-semibold disabled:opacity-50">
              Tatbikat: çifte yazım dene
            </button>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 mt-5">
          <div className="bg-white/10 rounded-xl p-3" data-testid="lease-stat-total">
            <div className="text-2xl font-bold">{data.total}</div>
            <div className="text-xs text-stone-300">Aktif kira (sahipli hücre)</div>
          </div>
          <div className="bg-white/10 rounded-xl p-3" data-testid="lease-stat-owners">
            <div className="text-sm font-semibold mt-1">
              {Object.entries(data.owners).map(([o, n]) => `${o}: ${n}`).join(" · ") || "—"}
            </div>
            <div className="text-xs text-stone-300">Sahip dağılımı</div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">Aktif Kiralar</h2>
          {data.total > 0 && (
            <button onClick={forceReleaseAll} disabled={busy === "rel"} data-testid="lease-force-release-btn"
              className="px-4 py-1.5 rounded-full bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold disabled:opacity-50">
              Tümünü iptal et (operatör egemenliği)
            </button>
          )}
        </div>
        {data.leases.length === 0 ? (
          <p className="text-sm text-stone-400" data-testid="lease-empty">
            Aktif kira yok. Merdivenler yazarken hücre kirası alır; süre dolunca hücre serbest kalır.
          </p>
        ) : (
          <table className="w-full text-sm" data-testid="lease-table">
            <thead><tr className="text-left text-xs text-stone-500 border-b">
              <th className="py-2">Gece</th><th>Oda tipi</th><th>Sahip (aktör)</th><th>Alındı</th><th>Bitiş</th>
            </tr></thead>
            <tbody>
              {data.leases.map((l, i) => (
                <tr key={i} className="border-b border-stone-100">
                  <td className="py-2">{l.date}</td>
                  <td className="text-xs text-stone-400">{l.room_type_id || "(varsayılan)"}</td>
                  <td><span className="px-2 py-0.5 rounded-full bg-stone-100 text-xs font-semibold">{l.owner}</span></td>
                  <td className="text-xs text-stone-400">{l.acquired_at?.slice(11, 16)}</td>
                  <td className="text-xs text-stone-400">{l.expires_at?.slice(11, 16)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
