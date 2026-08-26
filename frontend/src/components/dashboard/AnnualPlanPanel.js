import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { CalendarBlank, Archive, UploadSimple, Sparkle } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/annual-plan`;
const MONTHS_TR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];

export default function AnnualPlanPanel({ propertyId = "default" }) {
  const [versions, setVersions] = useState([]);
  const [plan, setPlan] = useState(null);
  const [busy, setBusy] = useState("");
  const [anchor, setAnchor] = useState("");
  const [failMsg, setFailMsg] = useState("");
  const [hist, setHist] = useState(null);
  const pid = propertyId === "all" ? "default" : propertyId;

  const load = useCallback(async () => {
    try {
      const [v, l, h] = await Promise.all([
        axios.get(`${API}/${pid}/versions`),
        axios.get(`${API}/${pid}/latest`),
        axios.get(`${process.env.REACT_APP_BACKEND_URL}/api/history-import/${pid}/status`),
      ]);
      setVersions(v.data.versions || []);
      setPlan(l.data.latest || null);
      setHist(h.data);
    } catch { toast.error("Yıllık plan verisi yüklenemedi"); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  async function startImport() {
    setBusy("imp");
    try {
      const r = await axios.post(`${process.env.REACT_APP_BACKEND_URL}/api/history-import/${pid}/start`);
      if (r.data.skipped) toast.info("Geçmiş zaten içe aktarılmış");
      else toast.success(`İçe aktarıldı: ${r.data.job.imported_bookings} rezervasyon, ${r.data.job.nights_covered} gece`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "İçe aktarım başarısız"); }
    setBusy("");
  }

  async function undoImport() {
    if (!window.confirm("İçe aktarılan tüm geçmiş rezervasyonlar silinsin mi?")) return;
    setBusy("undo");
    try {
      const r = await axios.delete(`${process.env.REACT_APP_BACKEND_URL}/api/history-import/${pid}`);
      toast.success(`${r.data.deleted_bookings} içe aktarılmış kayıt silindi`);
      load();
    } catch { toast.error("Silinemedi"); }
    setBusy("");
  }

  async function generate() {
    setBusy("gen"); setFailMsg("");
    try {
      const body = anchor ? { anchor_level: parseFloat(anchor) } : {};
      const r = await axios.post(`${API}/${pid}/generate`, body);
      toast.success(`Plan v${r.data.version} oluşturuldu (${r.data.days.length} gün)`);
      load();
    } catch (e) {
      const det = e.response?.data?.detail;
      if (det?.fail_closed) { setFailMsg(det.reason); toast.error("Fail-closed: plan üretilmedi"); }
      else toast.error("Plan oluşturulamadı");
    }
    setBusy("");
  }

  async function openVersion(id) {
    try {
      const r = await axios.get(`${API}/${pid}/versions/${id}`);
      setPlan(r.data);
    } catch { toast.error("Sürüm açılamadı"); }
  }

  async function publish() {
    if (!plan) return;
    if (!window.confirm(`Plan v${plan.version} yayınlansın mı? ${plan.days.length} güne fiyat yazılacak (D90+). Yayın plandan ayrı, açık bir operatör eylemidir.`)) return;
    setBusy("pub");
    try {
      const r = await axios.post(`${API}/${pid}/versions/${plan.id}/publish`);
      if (r.data.rejected_count > 0) {
        toast.warning(`Kısmi telafi: ${r.data.applied_days} gün yayınlandı, ${r.data.rejected_count} hücre tekil reddedildi (${r.data.rejected[0]?.reason})`);
      } else {
        toast.success(`Yayınlandı: ${r.data.applied_days} gün (${r.data.actor})`);
      }
      load();
    } catch { toast.error("Yayın başarısız"); }
    setBusy("");
  }

  const monthly = {};
  (plan?.days || []).forEach((d) => {
    const m = d.date.slice(0, 7);
    if (!monthly[m]) monthly[m] = { sum: 0, n: 0 };
    monthly[m].sum += d.price; monthly[m].n += 1;
  });
  const monthRows = Object.entries(monthly).map(([m, v]) => ({
    month: m, avg: Math.round(v.sum / v.n), days: v.n,
  }));
  const maxAvg = Math.max(...monthRows.map((r) => r.avg), 1);

  return (
    <div className="p-5 max-w-[1150px] mx-auto space-y-4" data-testid="annual-plan-panel">
      <div className="bg-gradient-to-br from-stone-900 via-violet-950 to-indigo-950 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-violet-300">
              <CalendarBlank size={14} /> Annual Plan D90–365
            </div>
            <h1 className="text-2xl font-bold mt-1">Yıllık Plan & Sürüm Arşivi</h1>
            <p className="text-sm text-stone-300 mt-1">
              Şekil × seviye ayrımı: mevsim/haftagünü şekli 730 günlük geçmişten, seviye yakın 30 günün
              medyanından. Her plan sürümlenir; yayın ayrı ve açık bir operatör eylemidir. Fail-closed: veri yetmezse plan üretilmez.
            </p>
          </div>
          <div className="flex gap-2 items-end flex-wrap">
            <label className="text-xs text-stone-300">Çapa seviye (ops.)
              <input value={anchor} onChange={(e) => setAnchor(e.target.value)} type="number" placeholder="örn. 120"
                className="mt-1 block w-28 rounded-lg px-2 py-1.5 text-sm text-stone-900" data-testid="annual-anchor-input" />
            </label>
            <button onClick={generate} disabled={busy === "gen"} data-testid="annual-generate-btn"
              className="px-4 py-2 rounded-full bg-violet-500 hover:bg-violet-400 text-white text-sm font-semibold flex items-center gap-2 disabled:opacity-50">
              <Sparkle size={16} /> {busy === "gen" ? "Üretiliyor…" : "Yeni Plan Üret"}
            </button>
          </div>
        </div>
        {failMsg && (
          <div className="mt-4 bg-amber-500/20 border border-amber-400/40 rounded-xl p-3 text-sm text-amber-200" data-testid="annual-fail-closed-msg">
            ⛔ Fail-closed: {failMsg}
          </div>
        )}
        {plan && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5">
            <div className="bg-white/10 rounded-xl p-3" data-testid="annual-stat-version">
              <div className="text-2xl font-bold">v{plan.version}</div>
              <div className="text-xs text-stone-300">Görüntülenen sürüm {plan.published_at ? "· YAYINDA" : ""}</div>
            </div>
            <div className="bg-white/10 rounded-xl p-3"><div className="text-2xl font-bold">{plan.level}</div>
              <div className="text-xs text-stone-300">Seviye ({plan.level_source === "operator_anchor" ? "operatör çapası" : "yakın pencere medyanı"})</div></div>
            <div className="bg-white/10 rounded-xl p-3"><div className="text-2xl font-bold">{plan.shape_sample_nights}</div>
              <div className="text-xs text-stone-300">Şekil örneklemi — {plan.shape_source === "sibling" ? "🏨 kardeş otel ödünçü" : plan.shape_source === "neutral" ? "nötr şekil" : "kendi geçmişi"}</div></div>
            <div className="bg-white/10 rounded-xl p-3"><div className="text-2xl font-bold">{plan.days?.length}</div>
              <div className="text-xs text-stone-300">Planlanan gün (D90–365)</div></div>
          </div>
        )}
      </div>

      {hist && (
        <div className="bg-white rounded-2xl border border-stone-200 p-5" data-testid="history-import-card">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <div className="text-xs uppercase tracking-wider text-stone-400 mb-1">📥 2 Yıl Geçmiş İçe Aktarımı</div>
              <p className="text-sm text-stone-600">
                Şekil örneklemi: <b data-testid="history-shape-nights">{hist.shape_nights}</b> gece —{" "}
                {hist.shape_ready
                  ? <span className="text-emerald-600 font-semibold">✓ şekil öğrenimi hazır</span>
                  : <span className="text-amber-600 font-semibold">⚠ 60 gece altı (kardeş ödünçü/çapa devrede)</span>}
                {" · "}PMS bağlanır bağlanmaz otomatik tetiklenir (D-731→D-31, son 30 gün raporları kirletmemek için hariç).
              </p>
              {hist.job && <p className="text-xs text-stone-400 mt-1">Son iş: {hist.job.imported_bookings} rezervasyon, {hist.job.nights_covered} gece ({hist.job.range})</p>}
            </div>
            <div className="flex gap-2">
              {hist.imported_bookings > 0 ? (
                <button onClick={undoImport} disabled={busy === "undo"} data-testid="history-undo-btn"
                  className="px-3 py-2 rounded-full border border-rose-300 text-rose-600 text-xs font-semibold hover:bg-rose-50 disabled:opacity-50">
                  İçe aktarımı geri al ({hist.imported_bookings})
                </button>
              ) : (
                <button onClick={startImport} disabled={busy === "imp"} data-testid="history-start-btn"
                  className="px-4 py-2 rounded-full bg-stone-900 text-white text-sm font-semibold disabled:opacity-50">
                  {busy === "imp" ? "Aktarılıyor…" : "Şimdi İçe Aktar (PMS mock)"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {plan && (
        <>
          <div className="bg-white rounded-2xl border border-stone-200 p-5" data-testid="annual-comp-headline">
            <div className="text-xs uppercase tracking-wider text-stone-400 mb-1">Rakip Sapma Manşeti</div>
            <p className="text-base font-semibold text-stone-800">📰 {plan.comp_deviation?.headline}</p>
            {plan.publish_report?.rejected_count > 0 && (
              <div className="mt-3 bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm" data-testid="annual-publish-report">
                🛡️ <b>Kısmi yayın telafisi:</b> {plan.publish_report.applied} gün yayınlandı,{" "}
                {plan.publish_report.rejected_count} hücre tekil reddedildi/geri alındı:{" "}
                {plan.publish_report.rejected.slice(0, 5).map((r) => `${r.date} (${r.reason})`).join(", ")}
                {plan.publish_report.rejected_count > 5 && " …"}
              </div>
            )}
          </div>

          <div className="bg-white rounded-2xl border border-stone-200 p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Aylık Ortalama Plan Fiyatı</h2>
              <button onClick={publish} disabled={busy === "pub" || !!plan.published_at} data-testid="annual-publish-btn"
                className="px-4 py-2 rounded-full bg-stone-900 text-white text-sm font-semibold flex items-center gap-2 disabled:opacity-40">
                <UploadSimple size={16} /> {plan.published_at ? `Yayınlandı (${plan.published_days} gün)` : "Planı Yayınla (D90+)"}
              </button>
            </div>
            <div className="space-y-1.5" data-testid="annual-month-bars">
              {monthRows.map((r) => (
                <div key={r.month} className="flex items-center gap-3">
                  <div className="w-20 text-xs text-stone-500">{MONTHS_TR[parseInt(r.month.slice(5), 10) - 1]} {r.month.slice(0, 4)}</div>
                  <div className="flex-1 bg-stone-100 rounded-full h-5 overflow-hidden">
                    <div className="h-5 bg-gradient-to-r from-violet-500 to-indigo-500 rounded-full flex items-center justify-end pr-2"
                      style={{ width: `${(r.avg / maxAvg) * 100}%` }}>
                      <span className="text-[10px] text-white font-semibold">{r.avg}</span>
                    </div>
                  </div>
                  <div className="w-14 text-xs text-stone-400">{r.days} gün</div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      <div className="bg-white rounded-2xl border border-stone-200 p-5">
        <h2 className="text-lg font-semibold mb-3 flex items-center gap-2"><Archive size={18} /> Sürüm Arşivi</h2>
        {versions.length === 0 ? (
          <p className="text-sm text-stone-400" data-testid="annual-empty-versions">Henüz plan sürümü yok — "Yeni Plan Üret" ile başlayın.</p>
        ) : (
          <table className="w-full text-sm" data-testid="annual-versions-table">
            <thead><tr className="text-left text-xs text-stone-500 border-b">
              <th className="py-2">Sürüm</th><th>Oluşturma</th><th>Oluşturan</th><th>Seviye</th><th>Rakip sapma</th><th>Yayın</th><th></th>
            </tr></thead>
            <tbody>
              {versions.map((v) => (
                <tr key={v.id} className={`border-b border-stone-100 ${plan?.id === v.id ? "bg-violet-50" : ""}`}>
                  <td className="py-2 font-semibold">v{v.version}</td>
                  <td className="text-xs text-stone-400">{v.created_at?.slice(0, 16).replace("T", " ")}</td>
                  <td className="text-xs">{v.created_by}</td>
                  <td>{v.level} <span className="text-[10px] text-stone-400">({v.level_source === "operator_anchor" ? "çapa" : "yakın"})</span></td>
                  <td className="text-xs">{v.comp_deviation?.avg_dev_pct != null ? `%${v.comp_deviation.avg_dev_pct}` : "—"}</td>
                  <td>{v.published_at ? <span className="text-emerald-600 text-xs font-semibold">✓ {v.published_days} gün</span> : <span className="text-stone-400 text-xs">taslak</span>}</td>
                  <td><button onClick={() => openVersion(v.id)} data-testid={`annual-open-version-${v.version}`}
                    className="text-xs px-2 py-1 rounded-full border border-stone-300 hover:bg-stone-50">Aç</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
