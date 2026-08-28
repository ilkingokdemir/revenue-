import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Calculator, Printer, Sparkles, AlertTriangle, TrendingDown, Target } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const HORIZONS = ["0-30", "31-60", "61-90"];
const gbp = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const gbp0 = (v) => `£${Number(v || 0).toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;

export default function RebaseImpactPanel({ propertyId = "aldgate-flats" }) {
  const pid = propertyId === "all" ? "aldgate-flats" : propertyId;
  const [defaults, setDefaults] = useState(null);
  const [targets, setTargets] = useState({});
  const [commission, setCommission] = useState(15);
  const [varCost, setVarCost] = useState(15);
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [experiments, setExperiments] = useState([]);
  const [emailTo, setEmailTo] = useState("");
  const [showEmail, setShowEmail] = useState(false);

  const sendEmailReport = async () => {
    if (!report || !emailTo.includes("@")) { toast.error("Geçerli bir e-posta girin"); return; }
    try {
      const { data } = await axios.post(`${API}/revenue/rebase-impact/${pid}/email-report`, {
        report_id: report.id, to: emailTo,
      });
      toast.success(`Rapor e-postası gönderildi → ${data.to}`);
      setShowEmail(false);
    } catch (e) { toast.error(e.response?.data?.detail || "Gönderilemedi"); }
  };

  const loadExperiments = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/revenue/rebase-impact/${pid}/experiments`);
      setExperiments(data.experiments || []);
    } catch { /* sessiz */ }
  }, [pid]);
  useEffect(() => { loadExperiments(); }, [loadExperiments]);

  const startExperiment = async () => {
    if (!report) return;
    try {
      await axios.post(`${API}/revenue/rebase-impact/${pid}/experiment/start`, { report_id: report.id });
      toast.success("Deney başlatıldı — pickup artık ölçülüyor");
      loadExperiments();
    } catch (e) { toast.error(e.response?.data?.detail || "Deney başlatılamadı"); }
  };

  const stopExperiment = async (eid) => {
    try {
      await axios.post(`${API}/revenue/rebase-impact/${pid}/experiment/${eid}/stop`);
      toast.success("Deney durduruldu");
      loadExperiments();
    } catch (e) { toast.error(e.response?.data?.detail || "Durdurulamadı"); }
  };

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/revenue/rebase-impact/${pid}/defaults`);
      setDefaults(data);
      const t = {};
      data.grid.forEach((rt) => {
        t[rt.room_type_id] = {};
        HORIZONS.forEach((h) => { t[rt.room_type_id][h] = rt.horizons[h].suggested; });
      });
      setTargets(t);
    } catch { toast.error("Veriler yüklenemedi"); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const analyze = async () => {
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/revenue/rebase-impact/${pid}/analyze`, {
        targets, commission_pct: Number(commission), variable_cost: Number(varCost),
      });
      setReport(data);
      toast.success("Rebase etki analizi hazır");
    } catch (e) { toast.error(e.response?.data?.detail || "Analiz başarısız"); }
    setBusy(false);
  };

  const aiComment = async () => {
    if (!report) return;
    setAiBusy(true);
    try {
      const { data } = await axios.post(`${API}/revenue/rebase-impact/${pid}/ai-comment`, { report_id: report.id });
      setReport((r) => ({ ...r, ai_comment: data.comment }));
    } catch (e) { toast.error(e.response?.data?.detail || "AI yorumu alınamadı"); }
    setAiBusy(false);
  };

  if (!defaults) return <div className="p-8 text-sm text-stone-500">Yükleniyor…</div>;
  const m = report?.multiplier || defaults.multiplier;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5 print:p-2" data-testid="rebase-impact-panel">
      <div className="flex items-start justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-xl font-black text-stone-900 flex items-center gap-2">
            <TrendingDown className="w-5 h-5 text-rose-600" /> Rebase Etki Analizi
          </h1>
          <p className="text-xs text-stone-500 mt-1">Robotun rebase senaryosu: kategori × ufuk fiyat tablosu → misafir-öder çarpanı → katkı kaybı → başabaş doluluk.</p>
        </div>
        <div className="flex gap-2">
          {report && (
            <>
              <button onClick={startExperiment} data-testid="rebase-experiment-start-btn"
                className="flex items-center gap-1.5 px-3 py-2 text-xs font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-xl hover:bg-emerald-100">
                <Target className="w-3.5 h-3.5" /> Deneyi Başlat
              </button>
              <button onClick={aiComment} disabled={aiBusy} data-testid="rebase-ai-btn"
                className="flex items-center gap-1.5 px-3 py-2 text-xs font-bold text-violet-700 bg-violet-50 border border-violet-200 rounded-xl hover:bg-violet-100 disabled:opacity-50">
                <Sparkles className="w-3.5 h-3.5" /> {aiBusy ? "Yorumluyor…" : "AI Yorum"}
              </button>
              <button onClick={() => setShowEmail((v) => !v)} data-testid="rebase-email-btn"
                className="flex items-center gap-1.5 px-3 py-2 text-xs font-bold text-sky-700 bg-sky-50 border border-sky-200 rounded-xl hover:bg-sky-100">
                ✉ E-posta
              </button>
              <button onClick={() => window.print()} data-testid="rebase-print-btn"
                className="flex items-center gap-1.5 px-3 py-2 text-xs font-bold text-stone-700 bg-white border border-stone-200 rounded-xl hover:bg-stone-50">
                <Printer className="w-3.5 h-3.5" /> Yazdır / PDF
              </button>
            </>
          )}
        </div>
      </div>

      {/* E-posta gönderme satırı */}
      {report && showEmail && (
        <div className="flex items-center gap-2 bg-sky-50 border border-sky-200 rounded-xl p-3 print:hidden" data-testid="rebase-email-row">
          <input type="email" value={emailTo} onChange={(e) => setEmailTo(e.target.value)} placeholder="yonetici@otel.com"
            data-testid="rebase-email-input"
            className="flex-1 border border-sky-200 rounded-lg px-3 py-2 text-sm bg-white" />
          <button onClick={sendEmailReport} data-testid="rebase-email-send"
            className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold">Raporu Gönder</button>
        </div>
      )}

      {/* Girdi tablosu */}
      <div className="bg-white border border-stone-200 rounded-2xl p-4 print:hidden" data-testid="rebase-inputs">
        <div className="flex flex-wrap items-end gap-4 mb-4">
          <div>
            <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Komisyon %</label>
            <input type="number" value={commission} onChange={(e) => setCommission(e.target.value)} data-testid="rebase-commission-input"
              className="w-24 border border-stone-200 rounded-lg px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Değişken maliyet / gece (£)</label>
            <input type="number" value={varCost} onChange={(e) => setVarCost(e.target.value)} data-testid="rebase-varcost-input"
              className="w-24 border border-stone-200 rounded-lg px-2 py-1.5 text-sm" />
          </div>
          <div className="text-[11px] text-stone-500">
            Misafir-öder çarpanı: <b>{m.value ?? m.used}</b> {m.reliable ? `(${m.samples} rezervasyon)` : "(güvenilir değil — 1.0)"} · Doluluk (90g): <b>%{defaults.occupancy_90d}</b>
          </div>
          <button onClick={analyze} disabled={busy} data-testid="rebase-analyze-btn"
            className="ml-auto flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-rose-600 to-orange-500 hover:from-rose-700 hover:to-orange-600 text-white text-sm font-bold shadow disabled:opacity-50">
            <Calculator className="w-4 h-4" /> {busy ? "Hesaplanıyor…" : "Analiz Et"}
          </button>
        </div>
        <p className="text-[10px] text-stone-400 mb-2">Hedef fiyatlar son-dakika gerçekleşen seviyeden otomatik önerildi — hücreleri elle düzeltebilirsiniz.</p>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-[10px] uppercase text-stone-400 border-b border-stone-100">
              <th className="py-1.5">Kategori</th>
              {HORIZONS.map((h) => <th key={h} className="py-1.5">{h} gün hedef (£)</th>)}
            </tr>
          </thead>
          <tbody>
            {defaults.grid.map((rt) => (
              <tr key={rt.room_type_id} className="border-b border-stone-50">
                <td className="py-1.5 font-semibold text-stone-800">{rt.name} · {rt.rooms} oda</td>
                {HORIZONS.map((h) => (
                  <td key={h} className="py-1.5">
                    <input type="number" step="0.01"
                      value={targets[rt.room_type_id]?.[h] ?? ""}
                      onChange={(e) => setTargets((t) => ({ ...t, [rt.room_type_id]: { ...t[rt.room_type_id], [h]: e.target.value } }))}
                      data-testid={`rebase-target-${rt.room_type_id}-${h}`}
                      className="w-24 border border-stone-200 rounded-lg px-2 py-1" />
                    <span className="ml-1.5 text-[10px] text-stone-400">bugün {gbp(rt.horizons[h].net_today)}</span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Deney Takibi — tahmin vs gerçek */}
      {experiments.length > 0 && (
        <div className="bg-white border border-stone-200 rounded-2xl p-4" data-testid="rebase-experiments">
          <h2 className="text-sm font-black text-stone-800 mb-3">Deney Takibi — Tahmin vs Gerçek</h2>
          <div className="space-y-3">
            {experiments.map((e) => (
              <div key={e.id} className={`border rounded-xl p-3 ${e.status === "running" ? "border-emerald-200 bg-emerald-50/40" : "border-stone-200"}`} data-testid={`rebase-exp-${e.id}`}>
                <div className="flex items-center justify-between mb-2">
                  <div className="text-xs font-bold text-stone-800">
                    {new Date(e.started_at).toLocaleDateString("tr-TR")} başlangıç · {e.progress.elapsed_days} gün
                    <span className={`ml-2 px-1.5 py-0.5 rounded-full text-[9px] font-black ${e.status === "running" ? "bg-emerald-100 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>
                      {e.status === "running" ? "ÇALIŞIYOR" : "DURDU"}
                    </span>
                  </div>
                  {e.status === "running" && (
                    <button onClick={() => stopExperiment(e.id)} data-testid={`rebase-exp-stop-${e.id}`}
                      className="text-[10px] font-bold text-rose-600 bg-rose-50 border border-rose-200 rounded-lg px-2 py-1 hover:bg-rose-100">Durdur</button>
                  )}
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-[11px]">
                  <div className="bg-white border border-stone-100 rounded-lg p-2">
                    <div className="text-[9px] uppercase font-bold text-stone-400">Pickup (oda-gece)</div>
                    <div className="font-black text-stone-800">{e.progress.pickup_before.room_nights} → {e.progress.pickup_after.room_nights}
                      {e.progress.pickup_change_pct !== null && <span className={`ml-1 ${e.progress.pickup_change_pct >= 0 ? "text-emerald-600" : "text-rose-600"}`}>({e.progress.pickup_change_pct > 0 ? "+" : ""}%{e.progress.pickup_change_pct})</span>}
                    </div>
                  </div>
                  <div className="bg-white border border-stone-100 rounded-lg p-2">
                    <div className="text-[9px] uppercase font-bold text-stone-400">ADR</div>
                    <div className="font-black text-stone-800">{gbp(e.progress.pickup_before.adr)} → {gbp(e.progress.pickup_after.adr)}
                      {e.progress.adr_change_pct !== null && <span className={`ml-1 ${e.progress.adr_change_pct >= 0 ? "text-emerald-600" : "text-rose-600"}`}>({e.progress.adr_change_pct > 0 ? "+" : ""}%{e.progress.adr_change_pct})</span>}
                    </div>
                  </div>
                  <div className="bg-white border border-stone-100 rounded-lg p-2">
                    <div className="text-[9px] uppercase font-bold text-stone-400">Katkı (pencere)</div>
                    <div className="font-black text-stone-800">{gbp0(e.progress.contribution_before)} → {gbp0(e.progress.contribution_after)}</div>
                  </div>
                  <div className="bg-white border border-stone-100 rounded-lg p-2">
                    <div className="text-[9px] uppercase font-bold text-stone-400">Tahmin (başabaş)</div>
                    <div className="font-black text-stone-800">pickup +%{e.predicted.breakeven_rn_increase_pct} gerekli</div>
                  </div>
                </div>
                <p className="text-xs font-semibold text-stone-700 mt-2" data-testid={`rebase-exp-verdict-${e.id}`}>{e.progress.verdict_tr}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {report && (
        <div className="space-y-5" data-testid="rebase-report">
          {/* Kategori × ufuk sonuç tablosu */}
          <div className="bg-white border border-stone-200 rounded-2xl p-4 overflow-x-auto">
            <h2 className="text-sm font-black text-stone-800 mb-2">Kategori bazında öncesi / sonrası</h2>
            <table className="w-full text-xs" data-testid="rebase-result-table">
              <thead>
                <tr className="text-left text-[10px] uppercase text-stone-400 border-b border-stone-100">
                  <th className="py-1.5">Kategori / ufuk</th><th>Net bugün</th><th>Net sonra</th><th>Değişim</th><th>Misafir bugün*</th><th>Misafir sonra</th>
                </tr>
              </thead>
              <tbody>
                {report.rows.map((r, i) => (
                  <tr key={i} className="border-b border-stone-50">
                    <td className="py-1.5 font-semibold text-stone-700">{r.room_type} · {r.horizon} gün</td>
                    <td>{gbp(r.net_today)}</td>
                    <td className="font-bold">{gbp(r.net_after)}</td>
                    <td className={r.change_pct < 0 ? "text-rose-600 font-bold" : "text-emerald-600 font-bold"}>{r.change_pct > 0 ? "+" : "−"}%{Math.abs(r.change_pct)}</td>
                    <td>{gbp(r.guest_today)}</td>
                    <td className="font-bold">{gbp(r.guest_after)}</td>
                  </tr>
                ))}
                <tr className="bg-stone-50 font-bold">
                  <td className="py-1.5">Otel geneli · oda ağırlıklı</td>
                  <td>{gbp(report.weighted.net_today)}</td>
                  <td>{gbp(report.weighted.net_after)}</td>
                  <td className={report.weighted_change_pct < 0 ? "text-rose-600" : "text-emerald-600"}>{report.weighted_change_pct > 0 ? "+" : "−"}%{Math.abs(report.weighted_change_pct)}</td>
                  <td colSpan={2}></td>
                </tr>
              </tbody>
            </table>
            <p className="text-[10px] text-stone-400 mt-2">* Misafir sütunları {report.multiplier.used} çarpanıyla tahmindir{report.multiplier.reliable ? ` (gözlenen ${report.multiplier.range[0]}–${report.multiplier.range[1]} bandı)` : " — güvenilir çarpan bulunamadı"}.</p>
          </div>

          {/* Katkı analizi */}
          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-white border border-stone-200 rounded-2xl p-4" data-testid="rebase-contribution">
              <h2 className="text-sm font-black text-stone-800 mb-2">90 günlük pencerede katkı</h2>
              <table className="w-full text-xs">
                <thead><tr className="text-left text-[10px] uppercase text-stone-400 border-b border-stone-100"><th className="py-1.5"></th><th>Bugün</th><th>Rebase sonrası</th></tr></thead>
                <tbody>
                  <tr className="border-b border-stone-50"><td className="py-1.5">Misafir öder</td><td>{gbp(report.contribution.guest_today)}</td><td>{gbp(report.contribution.guest_after)}</td></tr>
                  <tr className="border-b border-stone-50"><td className="py-1.5">Otelin eline geçen (komisyon −%{report.commission_pct})</td><td>{gbp(report.contribution.net_of_comm_today)}</td><td>{gbp(report.contribution.net_of_comm_after)}</td></tr>
                  <tr className="border-b border-stone-50"><td className="py-1.5">Değişken maliyet sonrası (−£{report.variable_cost})</td><td className="font-bold">{gbp(report.contribution.per_night_today)}</td><td className="font-bold">{gbp(report.contribution.per_night_after)}</td></tr>
                  <tr><td className="py-1.5 font-bold">{report.breakeven.rn_today} oda-gecede toplam katkı</td><td className="font-black">{gbp0(report.contribution.today_total)}</td><td className="font-black">{gbp0(report.contribution.after_total)}</td></tr>
                </tbody>
              </table>
              <p className="text-xs font-bold text-rose-700 mt-3" data-testid="rebase-loss">
                Aynı dolulukta {gbp0(report.contribution.loss)} katkı kaybı — 90 günde.
              </p>
            </div>

            {/* Başabaş */}
            <div className={`border rounded-2xl p-4 ${report.breakeven.feasible ? "bg-amber-50 border-amber-200" : "bg-rose-50 border-rose-300"}`} data-testid="rebase-breakeven">
              <h2 className="text-sm font-black text-stone-800 mb-2 flex items-center gap-2"><Target className="w-4 h-4" /> Başabaş noktası</h2>
              <p className="text-xs text-stone-700 leading-relaxed">
                Katkıyı korumak için oda-gece sayısının <b>%{report.breakeven.rn_increase_pct}</b> artması gerekiyor:{" "}
                <b>{report.breakeven.rn_today} → {report.breakeven.rn_needed}</b>. Müsait olan <b>{report.breakeven.rn_available}</b>.
              </p>
              <p className="text-xs text-stone-700 mt-2">
                Doluluk: <b>%{report.occupancy_90d} → %{report.breakeven.occ_needed_pct}</b>
              </p>
              {!report.breakeven.feasible && (
                <p className="text-xs font-black text-rose-700 mt-3 flex items-center gap-1.5" data-testid="rebase-infeasible">
                  <AlertTriangle className="w-4 h-4" /> İMKÂNSIZ: gereken doluluk mevcut kapasiteyi aşıyor — bu rebase katkıyı geri kazanamaz.
                </p>
              )}
            </div>
          </div>

          {/* Söylemediği 3 şey */}
          <div className="bg-white border border-stone-200 rounded-2xl p-4" data-testid="rebase-caveats">
            <h2 className="text-sm font-black text-stone-800 mb-2">Tablonun söylemediği üç şey</h2>
            <ul className="text-xs text-stone-600 space-y-1.5 list-disc pl-4">
              <li><b>Hacim etkisi yok.</b> {report.caveats.volume_note}</li>
              <li><b>Rezervasyon penceresi.</b> {report.caveats.window_note}</li>
              <li><b>Veri kalitesi.</b> {report.caveats.rate_plan_note}</li>
            </ul>
          </div>

          {/* Deterministik özet + AI yorum */}
          <div className="bg-stone-900 text-stone-100 rounded-2xl p-4" data-testid="rebase-narrative">
            <h2 className="text-sm font-black mb-2">Kısacası</h2>
            <ul className="text-xs space-y-1.5 list-disc pl-4">
              {report.narrative_tr.map((l, i) => <li key={i}>{l}</li>)}
            </ul>
            {report.ai_comment && (
              <div className="mt-3 pt-3 border-t border-stone-700" data-testid="rebase-ai-comment">
                <div className="text-[10px] font-bold uppercase text-violet-300 mb-1 flex items-center gap-1"><Sparkles className="w-3 h-3" /> AI Danışman Yorumu</div>
                <p className="text-xs leading-relaxed whitespace-pre-wrap">{report.ai_comment}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
