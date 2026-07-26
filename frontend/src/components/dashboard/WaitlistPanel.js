import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { HourglassMedium, ArrowsClockwise, Trash, EnvelopeSimple } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/waitlist`;

const STATUS_META = {
  waiting: { label: "Bekliyor", cls: "bg-amber-50 text-amber-700" },
  offered: { label: "Teklif gönderildi", cls: "bg-sky-50 text-sky-700" },
  converted: { label: "Rezervasyona döndü", cls: "bg-emerald-50 text-emerald-700" },
  expired: { label: "Süresi doldu", cls: "bg-stone-100 text-stone-500" },
};

export default function WaitlistPanel({ propertyId = "all" }) {
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState("");
  const [running, setRunning] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/${propertyId}${filter ? `?status=${filter}` : ""}`);
      setData(r.data);
    } catch { toast.error("Bekleme listesi yüklenemedi"); }
  }, [propertyId, filter]);
  useEffect(() => { load(); }, [load]);

  async function runMatch() {
    setRunning(true);
    try {
      const r = await axios.post(`${API}/${propertyId === "all" ? "all" : propertyId}/match-run`);
      toast.success(`${r.data.offers_sent} teklif gönderildi · ${r.data.waiting_scanned} bekleyen tarandı`);
      load();
    } catch { toast.error("Eşleştirme çalıştırılamadı"); }
    setRunning(false);
  }

  async function remove(id) {
    try {
      await axios.delete(`${API}/${propertyId}/${id}`);
      toast.success("Kayıt silindi");
      load();
    } catch { toast.error("Silinemedi"); }
  }

  if (!data) return <div className="p-8 text-center text-stone-400">Yükleniyor…</div>;
  const s = data.summary || {};

  return (
    <div className="p-5 max-w-[1200px] mx-auto space-y-4" data-testid="waitlist-panel">
      <div className="bg-gradient-to-br from-stone-900 via-amber-950 to-orange-900 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-amber-300">
              <HourglassMedium size={14} /> Waitlist
            </div>
            <h1 className="text-2xl font-bold mt-1">Bekleme Listesi</h1>
            <p className="text-sm text-stone-300 mt-1">Dolu tarihlerde misafirleri listeye alır; iptal ile yer açılınca otomatik teklif e-postası gönderilir (48s geçerli).</p>
          </div>
          <button onClick={runMatch} disabled={running} data-testid="waitlist-match-btn"
            className="px-4 py-2 bg-amber-400 hover:bg-amber-300 text-stone-900 rounded-lg text-sm font-bold inline-flex items-center gap-2 disabled:opacity-60">
            <ArrowsClockwise size={16} className={running ? "animate-spin" : ""} />
            {running ? "Taranıyor…" : "Şimdi Eşleştir"}
          </button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-5">
          <Stat label="Bekliyor" value={s.waiting || 0} testid="wl-stat-waiting" />
          <Stat label="Teklif gönderildi" value={s.offered || 0} testid="wl-stat-offered" />
          <Stat label="Dönüşen" value={s.converted || 0} testid="wl-stat-converted" />
          <Stat label="Süresi dolan" value={s.expired || 0} testid="wl-stat-expired" />
          <Stat label="Dönüşüm oranı" value={`%${data.conversion_rate}`} testid="wl-stat-conversion" />
        </div>
      </div>

      <div className="flex gap-1.5 flex-wrap">
        {["", "waiting", "offered", "converted", "expired"].map(fs => (
          <button key={fs} onClick={() => setFilter(fs)} data-testid={`wl-filter-${fs || "all"}`}
            className={`px-3 py-1 text-xs rounded-full border ${filter === fs ? "bg-stone-900 text-white border-stone-900" : "bg-white text-stone-600 border-stone-200 hover:bg-stone-50"}`}>
            {fs === "" ? "Tümü" : STATUS_META[fs].label}
          </button>
        ))}
      </div>

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="text-[11px] uppercase text-stone-400 border-b border-stone-100">
            <th className="text-left px-4 py-2">Misafir</th><th className="text-left px-2 py-2">Tarihler</th>
            <th className="text-center px-2 py-2">Kişi</th><th className="text-left px-2 py-2">Tesis</th>
            <th className="text-left px-2 py-2">Durum</th><th className="text-left px-2 py-2">Teklif</th>
            <th className="px-2 py-2"></th>
          </tr></thead>
          <tbody>
            {(data.entries || []).map(e => {
              const sm = STATUS_META[e.status] || STATUS_META.waiting;
              return (
                <tr key={e.id} className="border-b border-stone-50" data-testid={`wl-entry-${e.id}`}>
                  <td className="px-4 py-2">
                    <div className="font-medium text-stone-800">{e.guest_name}</div>
                    <div className="text-[11px] text-stone-400">{e.email}</div>
                  </td>
                  <td className="px-2 py-2 font-mono text-xs">{e.check_in} → {e.check_out}</td>
                  <td className="px-2 py-2 text-center">{e.guests}</td>
                  <td className="px-2 py-2 text-xs text-stone-500">{e.property_id}</td>
                  <td className="px-2 py-2"><span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${sm.cls}`}>{sm.label}</span></td>
                  <td className="px-2 py-2 text-[11px] text-stone-500">
                    {e.status === "offered" && (
                      <span className="inline-flex items-center gap-1">
                        <EnvelopeSimple size={12} className="text-sky-500" />
                        {e.email_status === "mock" ? "mock e-posta" : e.email_status} · son: {(e.offer_expires_at || "").slice(0, 10)}
                      </span>
                    )}
                    {e.status === "converted" && e.converted_at && `✓ ${new Date(e.converted_at).toLocaleDateString("tr-TR")}`}
                  </td>
                  <td className="px-2 py-2 text-right">
                    <button onClick={() => remove(e.id)} className="p-1 text-stone-300 hover:text-rose-600" data-testid={`wl-delete-${e.id}`}><Trash size={14} /></button>
                  </td>
                </tr>
              );
            })}
            {(!data.entries || data.entries.length === 0) && (
              <tr><td colSpan={7} className="px-4 py-10 text-center text-stone-400 text-sm">
                Bekleme listesi boş. Misafirler, rezervasyon widget'ında müsaitlik olmadığında kendini listeye ekleyebilir.
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
