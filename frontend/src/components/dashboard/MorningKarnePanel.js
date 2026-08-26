import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Sun, PaperPlaneTilt } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/morning-karne`;

export default function MorningKarnePanel({ propertyId = "default" }) {
  const [data, setData] = useState(null);
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);
  const pid = propertyId === "all" ? "default" : propertyId;

  const load = useCallback(async () => {
    try {
      const [l, h] = await Promise.all([
        axios.get(`${API}/${pid}/latest`),
        axios.get(`${API}/${pid}/history`),
      ]);
      setData(l.data);
      setHistory(h.data.history || []);
    } catch { toast.error("Karne verisi yüklenemedi"); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  async function sendNow() {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/${pid}/send-now`);
      toast.success(`Karne gönderildi (not: ${r.data.karne.grade}) → ${r.data.sent_to.length} yönetici`);
      load();
    } catch { toast.error("Gönderilemedi"); }
    setBusy(false);
  }

  async function toggle() {
    try {
      const next = !data.config.enabled;
      await axios.put(`${API}/${pid}/config`, { enabled: next });
      toast.success(next ? "Günlük otomatik karne AÇIK" : "Günlük otomatik karne kapalı");
      load();
    } catch { toast.error("Ayar kaydedilemedi"); }
  }

  if (!data) return <div className="p-8 text-center text-stone-400">Yükleniyor…</div>;
  const k = data.live_preview;
  const gradeColor = { A: "text-emerald-400", B: "text-amber-400", C: "text-rose-400" }[k.grade];

  return (
    <div className="p-5 max-w-[1000px] mx-auto space-y-4" data-testid="morning-karne-panel">
      <div className="bg-gradient-to-br from-stone-900 via-yellow-950 to-amber-950 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-yellow-300">
              <Sun size={14} /> Daily Report Card
            </div>
            <h1 className="text-2xl font-bold mt-1">Sabah Karnesi</h1>
            <p className="text-sm text-stone-300 mt-1">
              Sistem her sabah (~09:00 TR) kendi bekçi-zinciri karnesini yöneticilere e-postayla verir:
              doluluk, merdivenler, ikinci-yazıcı, vitrin ve 5xx sağlığı tek notta.
            </p>
          </div>
          <div className="flex gap-2 items-center">
            <button onClick={toggle} data-testid="karne-toggle-btn"
              className={`px-4 py-2 rounded-full text-sm font-semibold ${data.config.enabled ? "bg-emerald-500 text-stone-900" : "bg-white/15"}`}>
              Otomatik: {data.config.enabled ? "AÇIK" : "KAPALI"}
            </button>
            <button onClick={sendNow} disabled={busy} data-testid="karne-send-now-btn"
              className="px-4 py-2 rounded-full bg-yellow-500 hover:bg-yellow-400 text-stone-900 text-sm font-semibold flex items-center gap-2 disabled:opacity-50">
              <PaperPlaneTilt size={16} /> Şimdi Gönder
            </button>
          </div>
        </div>
        <div className="flex items-center gap-6 mt-5">
          <div>
            <div className={`text-6xl font-black ${gradeColor}`} data-testid="karne-grade">{k.grade}</div>
            <div className="text-xs text-stone-300">Bugünkü not (canlı)</div>
          </div>
          <div className="text-sm text-stone-300">
            {k.date} · Doluluk %{k.occ}
            {data.latest && <div className="text-xs mt-1">Son gönderim: {data.latest.date} → {data.latest.sent_to?.length} yönetici</div>}
          </div>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-5" data-testid="ladder-weekly-card">
        <div className="text-xs uppercase tracking-wider text-stone-400 mb-2">🪜 Merdiven Haftalık Özeti (son 7 gün, tahmini)</div>
        {k.ladder_weekly ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="bg-emerald-50 rounded-xl p-3">
              <div className="text-xl font-bold text-emerald-700">≈{k.ladder_weekly.lastday.recovered_estimate}</div>
              <div className="text-xs text-stone-500">Son-gün merdiveni kurtarılan gelir — {k.ladder_weekly.lastday.sold_after_discount} gece indirimle satıldı ({k.ladder_weekly.lastday.steps} kademe)</div>
            </div>
            <div className="bg-amber-50 rounded-xl p-3">
              <div className="text-xl font-bold text-amber-700">≈{k.ladder_weekly.ramp.uplift_estimate}</div>
              <div className="text-xs text-stone-500">Zam merdiveni ek gelir — {k.ladder_weekly.ramp.guest_approved} misafir-onaylı kademe ({k.ladder_weekly.ramp.steps} zam)</div>
            </div>
            <div className="bg-stone-900 text-white rounded-xl p-3">
              <div className="text-xl font-bold" data-testid="ladder-weekly-total">≈{k.ladder_weekly.total_estimate}</div>
              <div className="text-xs text-stone-300">Toplam merdiven katkısı (7g)</div>
            </div>
          </div>
        ) : <p className="text-sm text-stone-400">Veri yok.</p>}
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-5">
        <h2 className="text-lg font-semibold mb-3">Karne Kalemleri (canlı önizleme)</h2>
        <div className="space-y-2" data-testid="karne-checks">
          {k.checks.map((c, i) => (
            <div key={i} className={`flex items-center justify-between px-3 py-2 rounded-xl ${c.status === "ok" ? "bg-stone-50" : "bg-amber-50 border border-amber-200"}`}>
              <div className="text-sm">{c.status === "ok" ? "✅" : "⚠️"} {c.name}</div>
              <div className="text-sm font-semibold">{c.value}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-5">
        <h2 className="text-lg font-semibold mb-3">Gönderim Geçmişi</h2>
        {history.length === 0 ? (
          <p className="text-sm text-stone-400" data-testid="karne-empty-history">Henüz gönderim yok — "Şimdi Gönder" ile test edin (Resend anahtarı yoksa e-posta MOCK olarak email_outbox'a düşer).</p>
        ) : (
          <table className="w-full text-sm" data-testid="karne-history-table">
            <thead><tr className="text-left text-xs text-stone-500 border-b">
              <th className="py-2">Tarih</th><th>Not</th><th>Doluluk</th><th>Alıcı</th><th>Tür</th>
            </tr></thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.id} className="border-b border-stone-100">
                  <td className="py-2">{h.date}</td>
                  <td className="font-bold">{h.karne?.grade}</td>
                  <td>%{h.karne?.occ}</td>
                  <td className="text-xs text-stone-400">{h.sent_to?.join(", ")}</td>
                  <td className="text-xs">{h.forced ? "manuel" : "otomatik"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
