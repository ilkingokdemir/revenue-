import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ShieldCheck, ChartLineUp, CloudFog, Gauge } from "@phosphor-icons/react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, LineChart, Line, ReferenceLine } from "recharts";

const API = process.env.REACT_APP_BACKEND_URL;

export default function TrustCenterPanel({ activePropertyId, properties = [] }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : properties[0]?.id || "default";
  const [gr, setGr] = useState(null);
  const [viol, setViol] = useState(null);
  const [acc, setAcc] = useState(null);
  const [netOtb, setNetOtb] = useState(null);
  const [shadow, setShadow] = useState(null);
  const [shReport, setShReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [kill, setKill] = useState(null);
  const [outcomes, setOutcomes] = useState(null);
  const [scraper, setScraper] = useState(null);

  const load = useCallback(async () => {
    try {
      const [g, v, a, n, s, r, k, o, sc] = await Promise.all([
        axios.get(`${API}/api/guardrails/${pid}/config`, { withCredentials: true }),
        axios.get(`${API}/api/guardrails/${pid}/violations?limit=30`, { withCredentials: true }),
        axios.get(`${API}/api/rms-acceptance/${pid}/report?weeks=8`, { withCredentials: true }),
        axios.get(`${API}/api/net-otb/${pid}?days=14`, { withCredentials: true }),
        axios.get(`${API}/api/shadow-mode/${pid}/status`, { withCredentials: true }),
        axios.get(`${API}/api/shadow-mode/${pid}/report`, { withCredentials: true }),
        axios.get(`${API}/api/kill-switch/${pid}`, { withCredentials: true }),
        axios.get(`${API}/api/rms-acceptance/${pid}/outcomes?limit=8`, { withCredentials: true }),
        axios.get(`${API}/api/live-scraper/${pid}/status`, { withCredentials: true }),
      ]);
      setGr(g.data); setViol(v.data); setAcc(a.data); setNetOtb(n.data);
      setShadow(s.data); setShReport(r.data); setKill(k.data); setOutcomes(o.data); setScraper(sc.data);
    } catch { toast.error("Güven merkezi verileri yüklenemedi"); }
  }, [pid]);

  useEffect(() => { load(); }, [load]);

  const saveGr = async () => {
    setBusy(true);
    try {
      await axios.put(`${API}/api/guardrails/${pid}/config`, gr, { withCredentials: true });
      toast.success("Guardrail ayarları kaydedildi");
    } catch { toast.error("Kaydedilemedi"); } finally { setBusy(false); }
  };

  const shadowToggle = async () => {
    setBusy(true);
    try {
      const ep = shadow?.active ? "stop" : "start";
      const r = await axios.post(`${API}/api/shadow-mode/${pid}/${ep}`, {}, { withCredentials: true });
      setShadow((s) => ({ ...s, active: r.data.active }));
      toast.success(r.data.active ? "Shadow mode AÇIK — robot önerir ama push edilmez" : "Shadow mode kapatıldı");
    } catch { toast.error("İşlem başarısız"); } finally { setBusy(false); }
  };

  const shadowSnap = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/shadow-mode/${pid}/snapshot`, {}, { withCredentials: true });
      toast.success(`Snapshot alındı — ${r.data.recorded} öneri kaydedildi (push YOK)`);
      load();
    } catch { toast.error("Snapshot alınamadı"); } finally { setBusy(false); }
  };

  const toggleKill = async () => {
    setBusy(true);
    try {
      const ep = kill?.active ? "deactivate" : "activate";
      await axios.post(`${API}/api/kill-switch/${pid}/${ep}`, {}, { withCredentials: true });
      setKill((k) => ({ ...k, active: !k?.active }));
      toast[kill?.active ? "success" : "warning"](kill?.active ? "Kill switch kapatıldı — robot push'ları tekrar açık" : "🛑 KILL SWITCH AKTİF — tüm robot push'ları durduruldu");
    } catch { toast.error("İşlem başarısız"); } finally { setBusy(false); }
  };

  const runScan = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/live-scraper/${pid}/scan`, {}, { withCredentials: true });
      toast.success(`Tarama tamam — ${r.data.hotel_count} otel, kaynak: ${r.data.source}${r.data.source === "mock_fallback" ? " (bot koruması, mock'a düşüldü)" : ""}`);
      load();
    } catch { toast.error("Tarama başarısız"); } finally { setBusy(false); }
  };

  const setScraperMode = async (mode) => {
    try {
      await axios.put(`${API}/api/live-scraper/${pid}/config`, { mode }, { withCredentials: true });
      setScraper((s) => ({ ...s, mode }));
      toast.success(`Compset kaynağı: ${mode === "scraper" ? "CANLI SCRAPER" : mode}`);
    } catch { toast.error("Mod değiştirilemedi"); }
  };

  return (
    <div className="p-5 max-w-[1250px] mx-auto space-y-7" data-testid="trust-center-panel">
      <div>
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <ShieldCheck size={13} weight="fill" className="text-emerald-500" /><span>Robot Güven Merkezi</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">Guardrail · Kabul Oranı · Net OTB · Shadow Mode</h1>
        <div className="flex flex-wrap items-center gap-2 mt-2">
          {kill && (
            <button onClick={toggleKill} disabled={busy} data-testid="tc-kill-switch-btn"
              className={`px-4 py-2 rounded-lg text-sm font-black disabled:opacity-50 ${kill.active ? "bg-rose-600 text-white animate-pulse" : "border-2 border-rose-300 text-rose-600"}`}>
              {kill.active ? "🛑 KILL SWITCH AKTİF — Kaldır" : "🛑 Kill Switch (acil fren)"}
            </button>
          )}
          {kill?.active && <span className="text-[12px] text-rose-600 font-bold" data-testid="tc-kill-status">Tüm robot push'ları bloklu</span>}
        </div>
        <p className="text-sm text-stone-500 mt-1">Oteli batıran modelin hatası değil, guardrail'siz uygulanmış hatasıdır — robotun tüm emniyet katmanları burada.</p>
      </div>

      {gr && viol && (
        <section data-testid="tc-guardrail-section">
          <div className="flex items-center gap-2 mb-2"><Gauge size={16} className="text-rose-600" /><h2 className="text-base font-bold text-stone-800">Guardrail Sertleştirme</h2></div>
          <div className="grid md:grid-cols-3 gap-3">
            <div className="bg-white border border-stone-200 rounded-xl p-4 space-y-2.5">
              <div className="grid grid-cols-2 gap-2">
                <label className="text-[11px] text-stone-500 font-bold block">Artış limiti (%)
                  <input type="number" min={1} max={50} value={gr.max_up_pct} onChange={(e) => setGr((g) => ({ ...g, max_up_pct: +e.target.value }))} data-testid="tc-up-input" className="block w-full border border-stone-300 rounded-lg px-2 py-2 text-sm mt-0.5" />
                </label>
                <label className="text-[11px] text-stone-500 font-bold block">İndirim limiti (%)
                  <input type="number" min={0} max={50} value={gr.max_down_pct} onChange={(e) => setGr((g) => ({ ...g, max_down_pct: +e.target.value }))} data-testid="tc-down-input" className="block w-full border border-stone-300 rounded-lg px-2 py-2 text-sm mt-0.5" />
                </label>
              </div>
              <label className="text-[11px] text-stone-500 font-bold block">Günlük push limiti
                <input type="number" min={1} max={500} value={gr.daily_push_limit} onChange={(e) => setGr((g) => ({ ...g, daily_push_limit: +e.target.value }))} data-testid="tc-daily-input" className="block w-full border border-stone-300 rounded-lg px-2 py-2 text-sm mt-0.5" />
              </label>
              <label className="flex items-center gap-1.5 text-[12px] font-bold text-stone-600">
                <input type="checkbox" checked={gr.cold_start_mode === "auto"} onChange={(e) => setGr((g) => ({ ...g, cold_start_mode: e.target.checked ? "auto" : "off" }))} data-testid="tc-coldstart-toggle" />
                Cold-start koruması {gr.cold_start_active && <span className="px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[10px]" data-testid="tc-coldstart-badge">AKTİF: indirim %0, artış ≤%10</span>}
              </label>
              <button onClick={saveGr} disabled={busy} data-testid="tc-gr-save-btn" className="px-3 py-2 rounded-lg bg-stone-900 text-white text-sm font-bold disabled:opacity-50">Kaydet</button>
              <p className="text-[11px] text-stone-400">Bugün push: <b data-testid="tc-pushed-today">{viol.pushed_today}</b> / {gr.daily_push_limit}. Limit aşımı = blok, adım aşımı = kırpma + log.</p>
            </div>
            <div className="md:col-span-2 bg-white border border-stone-200 rounded-xl overflow-x-auto">
              <div className="px-3 pt-3 text-xs font-bold text-stone-500">İHLAL LOGU ({viol.violations.length})</div>
              {viol.violations.length === 0 ? <p className="p-3 text-sm text-emerald-600 font-bold" data-testid="tc-viol-empty">✅ İhlal yok</p> : (
                <table className="w-full text-sm" data-testid="tc-viol-table">
                  <thead><tr className="text-left text-[11px] text-stone-400"><th className="p-2">Zaman</th><th className="p-2">Tür</th><th className="p-2">Detay</th></tr></thead>
                  <tbody>
                    {viol.violations.map((v, i) => (
                      <tr key={i} className="border-t border-stone-100">
                        <td className="p-2 text-[12px]">{String(v.created_at).slice(0, 16).replace("T", " ")}</td>
                        <td className="p-2"><span className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${v.blocked ? "bg-rose-100 text-rose-700" : "bg-amber-100 text-amber-700"}`}>{v.type === "daily_limit" ? "GÜNLÜK LİMİT" : v.type === "kill_switch" ? "🛑 KILL SWITCH" : "ADIM LİMİTİ"}</span></td>
                        <td className="p-2 text-[12px] text-stone-600">{v.detail}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </section>
      )}

      {acc && (
        <section data-testid="tc-acceptance-section">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
            <div className="flex items-center gap-2"><ChartLineUp size={16} className="text-emerald-600" /><h2 className="text-base font-bold text-stone-800">Öneri Kabul Oranı (8 hafta)</h2></div>
            {acc.overall_acceptance_pct != null && (
              <span className={`px-2.5 py-1 rounded-full text-[11px] font-black ${acc.overall_acceptance_pct >= acc.target_pct ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`} data-testid="tc-acc-badge">
                Genel: %{acc.overall_acceptance_pct} (hedef ≥%{acc.target_pct})
              </span>
            )}
          </div>
          <div className="grid md:grid-cols-3 gap-3">
            <div className="md:col-span-2 bg-white border border-stone-200 rounded-xl p-3" data-testid="tc-acc-chart">
              {acc.weeks.length === 0 ? <p className="text-sm text-stone-500 p-3">Henüz karar verisi yok — AI Fiyatlama panelinden öneri kabul/reddedin.</p> : (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={acc.weeks} margin={{ top: 5, right: 10, left: -15, bottom: 0 }}>
                    <XAxis dataKey="week" tick={{ fontSize: 10 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip /><Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="accepted" name="Kabul" stackId="a" fill="#059669" />
                    <Bar dataKey="auto_applied" name="Oto-uygulama" stackId="a" fill="#0ea5e9" />
                    <Bar dataKey="rejected" name="Red" stackId="a" fill="#e11d48" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
            <div className="bg-white border border-stone-200 rounded-xl p-3" data-testid="tc-acc-reasons">
              <div className="text-xs font-bold text-stone-500 mb-2">RED NEDENLERİ (etiketli veri)</div>
              {acc.reasons.length === 0 ? <p className="text-[12px] text-stone-400">Henüz red nedeni yok.</p> : acc.reasons.map((r) => (
                <div key={r.reason} className="flex items-center justify-between text-sm mb-1"><span className="text-stone-700 truncate mr-2">{r.reason}</span><span className="px-2 py-0.5 rounded-full bg-rose-100 text-rose-700 text-[11px] font-black">{r.count}</span></div>
              ))}
              <p className="text-[10px] text-stone-400 mt-2">{acc.note}</p>
            </div>
          </div>
        </section>
      )}

      {netOtb && (
        <section data-testid="tc-netotb-section">
          <h2 className="text-base font-bold text-stone-800 mb-2">Beklenen Net OTB (14 gün) — genel iptal oranı %{(netOtb.cancel_stats.global_rate * 100).toFixed(1)} · {netOtb.cancel_stats.sample} rezervasyon örneklemi</h2>
          <div className="bg-white border border-stone-200 rounded-xl p-3" data-testid="tc-netotb-chart">
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={netOtb.rows} margin={{ top: 5, right: 10, left: -15, bottom: 0 }}>
                <XAxis dataKey="date" tick={{ fontSize: 9 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip /><Legend wrapperStyle={{ fontSize: 12 }} />
                <ReferenceLine y={100} stroke="#a8a29e" strokeDasharray="4 4" />
                <Line type="monotone" dataKey="gross_occupancy_pct" name="Brüt Doluluk %" stroke="#a8a29e" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="net_occupancy_pct" name="Net Doluluk % (fiyat motoru bunu kullanır)" stroke="#7c3aed" strokeWidth={2.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[11px] text-stone-400 mt-2">{netOtb.note}</p>
        </section>
      )}

      {outcomes && (
        <section data-testid="tc-outcomes-section">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
            <h2 className="text-base font-bold text-stone-800">Karar → Sonuç Zinciri (outcome ledger)</h2>
            {outcomes.avg_occ_delta != null && <span className={`px-2.5 py-1 rounded-full text-[11px] font-black ${outcomes.avg_occ_delta >= 0 ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`} data-testid="tc-outcome-badge">Ort. doluluk etkisi: {outcomes.avg_occ_delta > 0 ? "+" : ""}{outcomes.avg_occ_delta} puan</span>}
          </div>
          {outcomes.count === 0 ? (
            <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 text-sm text-stone-500" data-testid="tc-outcomes-empty">Henüz sonuçlanmış karar yok — robot her sabah tarihi geçen kararların gerçekleşen sonucunu buraya yazar.</div>
          ) : (
            <div className="bg-white border border-stone-200 rounded-xl overflow-x-auto">
              <table className="w-full text-sm" data-testid="tc-outcomes-table">
                <thead><tr className="text-left text-[11px] text-stone-400 border-b border-stone-100">
                  <th className="p-2">Tarih</th><th className="p-2">Karar Fiyatı</th><th className="p-2">Karar Anı Doluluk</th><th className="p-2">Gerçekleşen Doluluk</th><th className="p-2">Δ</th><th className="p-2">Gerçekleşen ADR</th>
                </tr></thead>
                <tbody>
                  {outcomes.outcomes.map((o, i) => (
                    <tr key={i} className="border-t border-stone-100">
                      <td className="p-2 font-bold">{o.date}</td>
                      <td className="p-2">₺{o.decision_rate}</td>
                      <td className="p-2">%{o.occ_at_decision}</td>
                      <td className="p-2">%{o.realized_occupancy_pct}</td>
                      <td className={`p-2 font-black ${o.occ_delta >= 0 ? "text-emerald-600" : "text-rose-600"}`}>{o.occ_delta > 0 ? "+" : ""}{o.occ_delta}</td>
                      <td className="p-2">₺{o.realized_adr}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="text-[11px] text-stone-400 mt-1">{outcomes.note}</p>
        </section>
      )}

      {scraper && (
        <section data-testid="tc-scraper-section">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
            <h2 className="text-base font-bold text-stone-800">Canlı Compset Kaynağı</h2>
            <div className="flex gap-1.5">
              {scraper.modes.map((m) => (
                <button key={m} onClick={() => setScraperMode(m)} data-testid={`tc-scraper-mode-${m}`}
                  className={`px-2.5 py-1 rounded-full text-[11px] font-black ${scraper.mode === m ? "bg-stone-900 text-white" : "bg-stone-100 text-stone-500"}`}>
                  {m === "scraper" ? "CANLI SCRAPER" : m === "licensed" ? "LİSANSLI" : "MOCK"}
                </button>
              ))}
              <button onClick={runScan} disabled={busy} data-testid="tc-scan-btn" className="px-3 py-1 rounded-lg bg-indigo-600 text-white text-[12px] font-bold disabled:opacity-50">Şimdi Tara</button>
            </div>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl p-3 text-sm text-stone-600" data-testid="tc-scraper-status">
            {scraper.last_scan ? (
              <>Son tarama: {String(scraper.last_scan.at).slice(0, 16).replace("T", " ")} · kaynak: <b className={scraper.last_scan.source === "scraped_live" ? "text-emerald-600" : "text-amber-600"}>{scraper.last_scan.source}</b> · {scraper.last_scan.hotels} otel · toplam {scraper.total_scans} tarama</>
            ) : "Henüz tarama yok — 'Şimdi Tara' ile başlatın."}
            <p className="text-[11px] text-stone-400 mt-1">{scraper.note}</p>
          </div>
        </section>
      )}

      {shadow && shReport && (
        <section data-testid="tc-shadow-section">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
            <div className="flex items-center gap-2"><CloudFog size={16} className="text-sky-600" /><h2 className="text-base font-bold text-stone-800">Shadow Mode — robot vs insan</h2></div>
            <div className="flex gap-2">
              <span className={`px-2.5 py-1 rounded-full text-[11px] font-black ${shadow.active ? "bg-sky-600 text-white" : "bg-stone-200 text-stone-600"}`} data-testid="tc-shadow-badge">{shadow.active ? "AKTİF" : "KAPALI"} · {shadow.snapshot_days} gün</span>
              {shReport.exit_criteria && (
                <span className={`px-2.5 py-1 rounded-full text-[11px] font-black ${shReport.exit_criteria.ready_for_live ? "bg-emerald-600 text-white" : "bg-stone-100 text-stone-500"}`} data-testid="tc-shadow-exit-badge">
                  {shReport.exit_criteria.ready_for_live ? "✅ CANLIYA HAZIR" : `Çıkış: ${shReport.exit_criteria.days_done}/${shReport.exit_criteria.min_days} gün + uyum ≥%${shReport.exit_criteria.min_agreement_pct}`}
                </span>
              )}
              <button onClick={shadowToggle} disabled={busy} data-testid="tc-shadow-toggle-btn" className={`px-3 py-1.5 rounded-lg text-[12px] font-bold disabled:opacity-50 ${shadow.active ? "bg-stone-200 text-stone-700" : "bg-sky-600 text-white"}`}>{shadow.active ? "Durdur" : "Shadow Mode Başlat"}</button>
              <button onClick={shadowSnap} disabled={busy} data-testid="tc-shadow-snap-btn" className="px-3 py-1.5 rounded-lg border border-stone-300 text-stone-700 text-[12px] font-bold disabled:opacity-50">Manuel Snapshot</button>
            </div>
          </div>
          {shReport.samples === 0 ? (
            <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 text-sm text-stone-500" data-testid="tc-shadow-empty">{shReport.note}</div>
          ) : (
            <div className="grid md:grid-cols-4 gap-3" data-testid="tc-shadow-report">
              <div className="bg-white border border-stone-200 rounded-xl p-4">
                <div className="text-[11px] uppercase tracking-wide text-stone-500 font-bold">Uyum Oranı</div>
                <div className={`text-2xl font-black mt-1 ${shReport.agreement_pct >= 60 ? "text-emerald-600" : "text-amber-600"}`} data-testid="tc-shadow-agreement">%{shReport.agreement_pct}</div>
                <div className="text-[11px] text-stone-500">|fark| ≤ %5 olan öneriler</div>
              </div>
              <div className="bg-white border border-stone-200 rounded-xl p-4">
                <div className="text-[11px] uppercase tracking-wide text-stone-500 font-bold">Ort. Fark</div>
                <div className="text-2xl font-black text-stone-900 mt-1">{shReport.avg_diff_pct > 0 ? "+" : ""}{shReport.avg_diff_pct}%</div>
                <div className="text-[11px] text-stone-500">robot ↑%{shReport.robot_higher_pct} · robot ↓%{shReport.robot_lower_pct}</div>
              </div>
              <div className="md:col-span-2 bg-white border border-stone-200 rounded-xl p-3">
                <ResponsiveContainer width="100%" height={110}>
                  <LineChart data={shReport.weeks} margin={{ top: 5, right: 10, left: -15, bottom: 0 }}>
                    <XAxis dataKey="week" tick={{ fontSize: 9 }} /><YAxis tick={{ fontSize: 10 }} /><Tooltip />
                    <Line type="monotone" dataKey="agreement_pct" name="Uyum %" stroke="#0284c7" strokeWidth={2} dot={{ r: 2 }} />
                  </LineChart>
                </ResponsiveContainer>
                <div className="text-[10px] text-stone-400 px-1">{shReport.samples} örnek · {shReport.first_snapshot} → {shReport.last_snapshot}</div>
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
