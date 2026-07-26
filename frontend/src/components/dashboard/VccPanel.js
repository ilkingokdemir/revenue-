import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { CreditCard, RefreshCw, Zap, AlertTriangle, CheckCircle2, Clock } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const fmt = (n, c = "GBP") => `${c === "GBP" ? "£" : c + " "}${Number(n || 0).toFixed(2)}`;

const STATUS_STYLE = {
  pending: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  charged: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  failed: "bg-rose-500/15 text-rose-300 border-rose-500/30",
  expired: "bg-stone-500/15 text-stone-400 border-stone-500/30",
};
const STATUS_TR = { pending: "Bekliyor", charged: "Tahsil edildi", failed: "Başarısız", expired: "Süresi doldu" };

export default function VccPanel({ propertyId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/vcc/${propertyId || "all"}`);
      setData(r.data);
    } catch { toast.error("VCC verisi yüklenemedi"); }
    finally { setLoading(false); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  const act = async (label, fn) => {
    setBusy(label);
    try { const r = await fn(); toast.success(r); await load(); }
    catch (e) { toast.error(e.response?.data?.detail || "İşlem başarısız"); }
    finally { setBusy(""); }
  };

  const scan = () => act("scan", async () => {
    const r = await axios.post(`${API}/vcc/scan`, { property_id: propertyId || "all" });
    return `${r.data.created} yeni OTA sanal kartı tespit edildi`;
  });
  const runAll = () => act("run", async () => {
    const r = await axios.post(`${API}/vcc/run`);
    return `Tahsilat çalıştı: ${r.data.charged} başarılı, ${r.data.failed} başarısız`;
  });
  const chargeOne = (id) => act(id, async () => {
    await axios.post(`${API}/vcc/${id}/charge`);
    return "Tahsilat başarılı ✓";
  });

  if (loading) return <div className="p-8 text-stone-400 text-sm" data-testid="vcc-loading">Yükleniyor…</div>;
  const s = data?.summary || {};

  return (
    <div className="space-y-5" data-testid="vcc-panel">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <CreditCard className="w-5 h-5 text-indigo-400" />
            <h2 className="text-2xl font-semibold text-stone-100">OTA Sanal Kart (VCC) Otomasyonu</h2>
          </div>
          <p className="text-sm text-stone-400 mt-1">Booking.com / Expedia sanal kartları aktivasyon gününde otomatik tahsil edilir. Her gece 06:00'da çalışır.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={scan} disabled={!!busy} data-testid="vcc-scan-btn"
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-sm text-stone-100 border border-stone-700 disabled:opacity-50">
            <RefreshCw className={`w-4 h-4 ${busy === "scan" ? "animate-spin" : ""}`} /> OTA taraması
          </button>
          <button onClick={runAll} disabled={!!busy} data-testid="vcc-run-btn"
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-indigo-500/20 hover:bg-indigo-500/30 border border-indigo-500/40 text-indigo-200 text-sm disabled:opacity-50">
            <Zap className="w-4 h-4" /> Vadesi gelenleri tahsil et
          </button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3">
        <div className="bg-stone-900 border border-stone-700 rounded-xl p-4" data-testid="vcc-kpi-pending">
          <div className="text-2xl font-bold text-amber-300">{fmt(s.pending_amount)}</div>
          <div className="text-[11px] text-stone-400 mt-1">Bekleyen tahsilat ({s.pending_count} kart)</div>
        </div>
        <div className="bg-stone-900 border border-stone-700 rounded-xl p-4" data-testid="vcc-kpi-due">
          <div className="text-2xl font-bold text-indigo-300">{fmt(s.due_today_amount)}</div>
          <div className="text-[11px] text-stone-400 mt-1">Bugün vadesi gelen ({s.due_today_count} kart)</div>
        </div>
        <div className="bg-stone-900 border border-stone-700 rounded-xl p-4" data-testid="vcc-kpi-charged">
          <div className="text-2xl font-bold text-emerald-300">{fmt(s.charged_30d_amount)}</div>
          <div className="text-[11px] text-stone-400 mt-1">Tahsil edilen (30 gün)</div>
        </div>
        <div className="bg-stone-900 border border-stone-700 rounded-xl p-4" data-testid="vcc-kpi-failed">
          <div className={`text-2xl font-bold ${s.failed_count > 0 ? "text-rose-400" : "text-stone-200"}`}>{s.failed_count || 0}</div>
          <div className="text-[11px] text-stone-400 mt-1">Başarısız tahsilat</div>
        </div>
      </div>

      <div className="bg-stone-900 border border-stone-700 rounded-xl overflow-hidden" data-testid="vcc-table">
        {(data?.cards || []).length === 0 ? (
          <div className="p-8 text-center text-sm text-stone-500">
            Henüz VCC kaydı yok — "OTA taraması" ile OTA rezervasyonlarındaki sanal kartları tespit edin.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] uppercase tracking-wide text-stone-500 border-b border-stone-800">
                <th className="text-left px-4 py-2.5 font-medium">Misafir</th>
                <th className="text-left px-2 py-2.5 font-medium">Kanal</th>
                <th className="text-left px-2 py-2.5 font-medium">Kart</th>
                <th className="text-right px-2 py-2.5 font-medium">Tutar</th>
                <th className="text-left px-2 py-2.5 font-medium">Aktivasyon</th>
                <th className="text-left px-2 py-2.5 font-medium">Durum</th>
                <th className="text-right px-4 py-2.5 font-medium">Aksiyon</th>
              </tr>
            </thead>
            <tbody>
              {data.cards.map((c) => (
                <tr key={c.id} className="border-b border-stone-800/60 last:border-0" data-testid={`vcc-row-${c.id}`}>
                  <td className="px-4 py-2.5 text-xs font-medium text-stone-200">{c.guest_name}</td>
                  <td className="px-2 py-2.5 text-xs text-stone-400">{c.channel}</td>
                  <td className="px-2 py-2.5 text-xs text-stone-400 font-mono">•••• {c.last4}</td>
                  <td className="px-2 py-2.5 text-right text-xs font-bold text-stone-100">{fmt(c.amount, c.currency)}</td>
                  <td className="px-2 py-2.5 text-xs text-stone-400">{c.activation_date}</td>
                  <td className="px-2 py-2.5">
                    <span className={`inline-flex items-center gap-1 text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full border ${STATUS_STYLE[c.status]}`}>
                      {c.status === "charged" ? <CheckCircle2 className="w-3 h-3" /> : c.status === "failed" ? <AlertTriangle className="w-3 h-3" /> : <Clock className="w-3 h-3" />}
                      {STATUS_TR[c.status] || c.status}
                    </span>
                    {c.attempts > 1 && <span className="text-[10px] text-stone-500 ml-1">×{c.attempts}</span>}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {(c.status === "pending" || c.status === "failed") && (
                      <button onClick={() => chargeOne(c.id)} disabled={!!busy} data-testid={`vcc-charge-${c.id}`}
                        className="text-[11px] font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg px-2.5 py-1.5 disabled:opacity-50">
                        Şimdi tahsil et
                      </button>
                    )}
                    {c.status === "charged" && <span className="text-[10px] text-stone-500 font-mono">{c.transaction_id?.slice(0, 14)}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <VccRecoverySection propertyId={propertyId} onCharged={load} chargeOne={chargeOne} busy={busy} />
    </div>
  );
}

const REC_TYPE_CLS = {
  missed_charge: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  expired: "bg-rose-500/15 text-rose-300 border-rose-500/30",
  underfunded: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  cancel_fee: "bg-violet-500/15 text-violet-300 border-violet-500/30",
};

function VccRecoverySection({ propertyId, onCharged, chargeOne, busy }) {
  const [scan, setScan] = useState(null);
  const [disputes, setDisputes] = useState(null);
  const [working, setWorking] = useState("");

  const load = useCallback(async () => {
    try {
      const [s, d] = await Promise.all([
        axios.get(`${API}/vcc-recovery/${propertyId || "all"}/scan`),
        axios.get(`${API}/vcc-recovery/${propertyId || "all"}/disputes`),
      ]);
      setScan(s.data);
      setDisputes(d.data);
    } catch { /* silent */ }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  const openDispute = async (item) => {
    setWorking(item.vcc_id);
    try {
      await axios.post(`${API}/vcc-recovery/dispute/${item.vcc_id}`, {
        type: item.type, amount: item.recoverable, reason: item.detail,
      });
      toast.success("OTA itirazı açıldı — takip 'Açık itirazlar' bölümünde");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "İtiraz açılamadı"); }
    setWorking("");
  };

  const resolve = async (id, outcome) => {
    setWorking(id);
    try {
      const r = await axios.post(`${API}/vcc-recovery/dispute/${id}/resolve`, { outcome });
      toast.success(outcome === "recovered" ? `✓ ${fmt(r.data.recovered_amount)} kurtarıldı!` : "İtiraz kapatıldı (tahsil edilemedi)");
      load();
    } catch { toast.error("Güncellenemedi"); }
    setWorking("");
  };

  if (!scan) return null;

  return (
    <div className="space-y-4" data-testid="vcc-recovery-section">
      <div className="bg-gradient-to-br from-emerald-950 via-stone-900 to-stone-900 border border-emerald-800/50 rounded-xl p-5">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-emerald-400 font-semibold">💸 Gelir Kurtarma — VCC Mutabakatı</div>
            <p className="text-xs text-stone-400 mt-1">Unutulmuş çekimler, süresi dolan kartlar, eksik yüklemeler ve tahsil edilmemiş iptal ücretleri.</p>
          </div>
          <div className="flex items-center gap-5 text-right">
            <div>
              <div className="text-2xl font-black text-emerald-300" data-testid="vcc-recoverable-total">{fmt(scan.total_recoverable)}</div>
              <div className="text-[10px] text-stone-400">kurtarılabilir gelir</div>
            </div>
            <div className="border-l border-stone-700 pl-5">
              <div className="text-2xl font-black text-teal-300" data-testid="vcc-recovered-total">{fmt(scan.recovered_to_date)}</div>
              <div className="text-[10px] text-stone-400">bugüne dek kurtarılan</div>
            </div>
          </div>
        </div>
        {(scan.by_type || []).length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-3">
            {scan.by_type.map(b => (
              <span key={b.type} className={`text-[10px] px-2 py-1 rounded-full border font-semibold ${REC_TYPE_CLS[b.type]}`}>
                {b.label}: {b.count} · {fmt(b.recoverable)}
              </span>
            ))}
          </div>
        )}
      </div>

      {(scan.items || []).length > 0 && (
        <div className="bg-stone-900 border border-stone-700 rounded-xl overflow-hidden" data-testid="vcc-recovery-table">
          <table className="w-full text-sm">
            <thead><tr className="text-[11px] uppercase text-stone-500 border-b border-stone-800">
              <th className="text-left px-4 py-2.5">Misafir</th><th className="text-left px-2 py-2.5">Kanal</th>
              <th className="text-left px-2 py-2.5">Tutarsızlık</th><th className="text-right px-2 py-2.5">Kurtarılabilir</th>
              <th className="text-right px-4 py-2.5">Aksiyon</th>
            </tr></thead>
            <tbody>
              {scan.items.map(i => (
                <tr key={i.vcc_id + i.type} className="border-b border-stone-800/60 last:border-0" data-testid={`vcc-rec-${i.vcc_id}`}>
                  <td className="px-4 py-2.5 text-xs font-medium text-stone-200">{i.guest_name}</td>
                  <td className="px-2 py-2.5 text-xs text-stone-400">{i.channel}</td>
                  <td className="px-2 py-2.5">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full border font-semibold ${REC_TYPE_CLS[i.type]}`}>{i.type_label}</span>
                    <div className="text-[10px] text-stone-500 mt-0.5 max-w-md">{i.detail}</div>
                  </td>
                  <td className="px-2 py-2.5 text-right text-xs font-bold text-emerald-300">{fmt(i.recoverable, i.currency)}</td>
                  <td className="px-4 py-2.5 text-right">
                    {i.action === "charge_now" ? (
                      <button onClick={() => { chargeOne(i.vcc_id); setTimeout(load, 1200); }} disabled={!!busy || !!working}
                        data-testid={`vcc-rec-charge-${i.vcc_id}`}
                        className="text-[11px] font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg px-2.5 py-1.5 disabled:opacity-50">
                        Şimdi çek
                      </button>
                    ) : (
                      <button onClick={() => openDispute(i)} disabled={!!working} data-testid={`vcc-rec-dispute-${i.vcc_id}`}
                        className="text-[11px] font-semibold text-white bg-sky-600 hover:bg-sky-700 rounded-lg px-2.5 py-1.5 disabled:opacity-50">
                        OTA'ya itiraz aç
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {(scan.items || []).length === 0 && (
        <div className="bg-stone-900 border border-stone-700 rounded-xl p-5 text-center text-sm text-emerald-400" data-testid="vcc-recovery-clean">
          ✓ Tutarsızlık yok — tüm VCC'ler mutabık.
        </div>
      )}

      {(disputes?.disputes || []).length > 0 && (
        <div className="bg-stone-900 border border-stone-700 rounded-xl p-4" data-testid="vcc-disputes-card">
          <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-2">
            OTA itirazları — açık: {fmt(disputes.open_total)} · kurtarılan: {fmt(disputes.recovered_total)}
          </div>
          {disputes.disputes.slice(0, 12).map(d => (
            <div key={d.id} className="flex items-center gap-2 py-1.5 border-b border-stone-800/60 last:border-0 text-xs">
              <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${
                d.status === "open" ? "bg-amber-500/15 text-amber-300" :
                d.status === "recovered" ? "bg-emerald-500/15 text-emerald-300" : "bg-stone-700 text-stone-400"}`}>
                {d.status === "open" ? "açık" : d.status === "recovered" ? "kurtarıldı" : "kapatıldı"}
              </span>
              <span className="text-stone-300 font-medium">{d.guest_name}</span>
              <span className="text-stone-500">{d.channel}</span>
              <span className="font-mono font-bold text-stone-200">{fmt(d.claim_amount, d.currency)}</span>
              <span className="text-stone-500 truncate max-w-xs">{d.reason}</span>
              {d.status === "open" && (
                <span className="ml-auto flex gap-1.5">
                  <button onClick={() => resolve(d.id, "recovered")} disabled={!!working} data-testid={`vcc-dispute-recover-${d.id}`}
                    className="text-[10px] font-semibold text-emerald-300 border border-emerald-700 rounded px-2 py-0.5 hover:bg-emerald-900/40">Kurtarıldı ✓</button>
                  <button onClick={() => resolve(d.id, "written_off")} disabled={!!working} data-testid={`vcc-dispute-writeoff-${d.id}`}
                    className="text-[10px] text-stone-400 border border-stone-700 rounded px-2 py-0.5 hover:bg-stone-800">Vazgeç</button>
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
