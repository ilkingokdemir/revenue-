import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Robot, Lightning, TrendUp, TrendDown, LockKey, MagicWand, Eye,
  ArrowsClockwise, CheckCircle, XCircle, Warning, Sparkle, ClockCounterClockwise,
} from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/strategist`;

const ACTION_META = {
  price_increase: { icon: TrendUp, label: "Fiyat artır", cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  price_decrease: { icon: TrendDown, label: "Fiyat düşür", cls: "bg-amber-50 text-amber-700 border-amber-200" },
  restriction: { icon: LockKey, label: "Kısıtlama", cls: "bg-violet-50 text-violet-700 border-violet-200" },
  campaign: { icon: MagicWand, label: "Kampanya", cls: "bg-blue-50 text-blue-700 border-blue-200" },
  monitor: { icon: Eye, label: "İzle", cls: "bg-stone-100 text-stone-600 border-stone-200" },
};
const PRIORITY = {
  high: "bg-rose-500 text-white", medium: "bg-amber-400 text-stone-900", low: "bg-stone-300 text-stone-700",
};
const STATUS_TR = { suggested: null, applied: "Uygulandı", auto_applied: "Otomatik uygulandı", dismissed: "Yoksayıldı" };

function Section({ title, text, icon: Icon, color }) {
  if (!text) return null;
  return (
    <div className="bg-white border border-stone-200 rounded-2xl p-5">
      <h3 className={`text-sm font-bold flex items-center gap-2 mb-2 ${color}`}>
        <Icon size={16} weight="duotone" /> {title}
      </h3>
      <p className="text-sm text-stone-700 leading-relaxed whitespace-pre-line">{text}</p>
    </div>
  );
}

export default function RevenueStrategistPanel({ propertyId = "default" }) {
  const pid = propertyId === "all" ? "default" : propertyId;
  const [cfg, setCfg] = useState(null);
  const [reports, setReports] = useState([]);
  const [report, setReport] = useState(null);
  const [horizon, setHorizon] = useState(90);
  const [language, setLanguage] = useState("tr");
  const [analyzing, setAnalyzing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [c, r] = await Promise.all([
        axios.get(`${API}/${pid}/config`),
        axios.get(`${API}/${pid}/reports`),
      ]);
      setCfg(c.data);
      setHorizon(c.data.horizon_days);
      setLanguage(c.data.language);
      setReports(r.data.items || []);
      if (r.data.items?.length) setReport(r.data.items[0]);
    } catch { toast.error("Strateji robotu verileri yüklenemedi"); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const analyze = async () => {
    setAnalyzing(true);
    toast.info("Robot analiz ediyor — piyasa, geçmiş, rakipler ve doluluk yorumlanıyor…");
    try {
      const { data } = await axios.post(`${API}/${pid}/analyze`, { horizon_days: horizon, language });
      setReport(data);
      setReports((r) => [data, ...r]);
      toast.success(data.auto_applied_count > 0
        ? `Rapor hazır — ${data.auto_applied_count} düşük riskli aksiyon otomatik uygulandı`
        : "Strateji raporu hazır");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Analiz başarısız oldu");
    } finally { setAnalyzing(false); }
  };

  const saveCfg = async (upd) => {
    try {
      const { data } = await axios.put(`${API}/${pid}/config`, upd);
      setCfg(data);
      toast.success("Ayarlar kaydedildi");
    } catch { toast.error("Ayar kaydedilemedi"); }
  };

  const actOn = async (aid, verb) => {
    try {
      const { data } = await axios.post(`${API}/${pid}/reports/${report.id}/actions/${aid}/${verb}`);
      setReport((r) => ({
        ...r,
        recommendations: r.recommendations.map((a) =>
          a.id === aid ? { ...a, status: verb === "apply" ? "applied" : "dismissed" } : a),
      }));
      if (verb === "apply") {
        toast.success(data.dates_updated
          ? `Fiyat uygulandı — ${data.dates_updated} tarih €${data.rate} olarak güncellendi`
          : "Aksiyon kuyruğa alındı");
      } else toast.success("Öneri yoksayıldı");
    } catch (e) { toast.error(e?.response?.data?.detail || "İşlem başarısız"); }
  };

  const k = report?.kpis || {};

  return (
    <div className="space-y-5" data-testid="revenue-strategist-panel">
      {/* Hero */}
      <div className="relative bg-[#0A0F1C] rounded-2xl p-6 text-white overflow-hidden">
        <div className="absolute top-[-60px] right-[-40px] w-[260px] h-[260px] rounded-full bg-[#1D4ED8]/30 blur-3xl" aria-hidden="true" />
        <div className="absolute bottom-[-80px] left-[20%] w-[220px] h-[220px] rounded-full bg-[#06B6D4]/20 blur-3xl" aria-hidden="true" />
        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-cyan-300 mb-1">
              <Robot size={15} weight="duotone" /> ReveniQ · Gelir Strateji Robotu
            </div>
            <h2 className="text-2xl font-bold">AI Revenue Strategist</h2>
            <p className="text-sm text-stone-400 mt-1 max-w-xl">
              Piyasayı, geçmişi, rakipleri, doluluğu ve etkinlikleri tek seferde analiz eder;
              yapılanları değerlendirir, yapılması gerekenleri somut aksiyonlarla önerir.
            </p>
          </div>
          <div className="flex flex-col items-end gap-3">
            <div className="flex items-center gap-2">
              {[30, 90, 365].map((h) => (
                <button key={h} onClick={() => setHorizon(h)} data-testid={`strategist-horizon-${h}`}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-colors ${horizon === h ? "bg-gradient-to-r from-[#1D4ED8] to-[#06B6D4] border-transparent text-white" : "border-white/20 text-stone-300 hover:border-white/50"}`}>
                  {h === 365 ? "12 ay" : `${h} gün`}
                </button>
              ))}
              <div className="w-px h-5 bg-white/20 mx-1" />
              {["tr", "en"].map((l) => (
                <button key={l} onClick={() => setLanguage(l)} data-testid={`strategist-lang-${l}`}
                  className={`px-2.5 py-1.5 rounded-lg text-xs font-bold border uppercase transition-colors ${language === l ? "bg-white text-[#0A0F1C] border-white" : "border-white/20 text-stone-300 hover:border-white/50"}`}>
                  {l}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-xs text-stone-300 cursor-pointer" data-testid="strategist-autoapply-toggle">
                <input type="checkbox" checked={!!cfg?.auto_apply}
                  onChange={(e) => saveCfg({ auto_apply: e.target.checked, horizon_days: horizon, language })}
                  className="accent-cyan-400 w-4 h-4" />
                Düşük riskli aksiyonları otomatik uygula (≤%15)
              </label>
              <button onClick={analyze} disabled={analyzing} data-testid="strategist-analyze-btn"
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-gradient-to-r from-[#1D4ED8] to-[#06B6D4] hover:from-[#1E40AF] hover:to-[#0891B2] text-white text-sm font-bold transition-colors disabled:opacity-60">
                {analyzing ? <ArrowsClockwise size={16} className="animate-spin" /> : <Sparkle size={16} weight="fill" />}
                {analyzing ? "Analiz ediliyor…" : "Şimdi Analiz Et"}
              </button>
            </div>
          </div>
        </div>
      </div>

      {!report ? (
        <div className="bg-white border border-stone-200 rounded-2xl p-12 text-center" data-testid="strategist-empty">
          <Robot size={40} weight="duotone" className="mx-auto text-stone-300 mb-3" />
          <p className="text-sm text-stone-500">Henüz strateji raporu yok. "Şimdi Analiz Et" ile robotu çalıştırın —
            piyasa, geçmiş, rakip ve doluluk verileriniz yorumlanıp strateji önerileri üretilecek.</p>
        </div>
      ) : (
        <>
          {/* KPI strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3" data-testid="strategist-kpis">
            {[
              ["İleri dönem doluluk", `%${k.fwd_occ_pct ?? 0}`, "text-[#1D4ED8]"],
              ["Pazar doluluğu", k.avg_market_occ_pct != null ? `%${k.avg_market_occ_pct}` : "—", "text-violet-600"],
              ["Ort. pazar farkı", k.avg_market_gap_pct != null ? `%${k.avg_market_gap_pct}` : "—", "text-[#F97316]"],
              ["Pazar altı gün", k.underpriced_dates ?? 0, "text-rose-600"],
              ["Etkili etkinlik", k.high_impact_events ?? 0, "text-amber-600"],
              ["Potansiyel ek gelir", `€${(k.potential_extra_revenue ?? 0).toLocaleString()}`, "text-emerald-600"],
              ["Maks. rakip fiyat", `€${k.max_observed_comp_rate ?? 0}`, "text-cyan-600"],
            ].map(([l, v, c]) => (
              <div key={l} className="bg-white border border-stone-200 rounded-xl p-4">
                <div className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">{l}</div>
                <div className={`text-xl font-black tabular-nums ${c}`}>{v}</div>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between text-xs text-stone-400">
            <span data-testid="strategist-report-meta">
              Rapor: {new Date(report.created_at).toLocaleString("tr")} · {report.horizon_days === 365 ? "12 ay" : `${report.horizon_days} gün`} ufuk
              · {report.trigger === "scheduled" ? "otomatik" : "manuel"}
              {report.auto_applied_count > 0 && <span className="ml-2 text-emerald-600 font-bold">⚡ {report.auto_applied_count} otomatik uygulandı</span>}
            </span>
            {reports.length > 1 && (
              <select value={report.id} onChange={(e) => setReport(reports.find((r) => r.id === e.target.value))}
                className="border border-stone-200 rounded-lg px-2 py-1 text-xs bg-white" data-testid="strategist-history-select">
                {reports.map((r) => (
                  <option key={r.id} value={r.id}>
                    <ClockCounterClockwise size={10} /> {new Date(r.created_at).toLocaleString("tr")}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Report sections */}
          <div className="grid lg:grid-cols-2 gap-4">
            <Section title="Mevcut Durum" text={report.situation_report} icon={Robot} color="text-[#1D4ED8]" />
            <Section title="Piyasa & Rakip Analizi + Maksimum Fiyat" text={report.market_analysis} icon={TrendUp} color="text-cyan-600" />
            <Section title="Geçmiş Performans (STLY karşılaştırma)" text={report.past_performance} icon={ClockCounterClockwise} color="text-amber-600" />
            <Section title="Yapılanların Değerlendirmesi" text={report.what_was_done} icon={CheckCircle} color="text-emerald-600" />
          </div>

          {(report.positive_factors?.length > 0 || report.negative_factors?.length > 0) && (
            <div className="grid md:grid-cols-2 gap-4">
              <div className="bg-white border-2 border-emerald-200 rounded-2xl p-5" data-testid="strategist-positive-factors">
                <h3 className="text-sm font-bold text-emerald-700 flex items-center gap-2 mb-3">
                  <TrendUp size={16} weight="duotone" /> Geliri Pozitif Etkileyecek Etkenler
                </h3>
                <ul className="space-y-2">
                  {(report.positive_factors || []).map((f, i) => (
                    <li key={i} className="text-sm text-stone-700 flex gap-2 bg-emerald-50/70 rounded-lg px-3 py-2">
                      <span className="text-emerald-500 font-black">+</span>{f}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="bg-white border-2 border-rose-200 rounded-2xl p-5" data-testid="strategist-negative-factors">
                <h3 className="text-sm font-bold text-rose-700 flex items-center gap-2 mb-3">
                  <TrendDown size={16} weight="duotone" /> Geliri Negatif Etkileyecek Etkenler
                </h3>
                <ul className="space-y-2">
                  {(report.negative_factors || []).map((f, i) => (
                    <li key={i} className="text-sm text-stone-700 flex gap-2 bg-rose-50/70 rounded-lg px-3 py-2">
                      <span className="text-rose-500 font-black">−</span>{f}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {report.events_considered?.length > 0 && (
            <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="strategist-events">
              <h3 className="text-sm font-bold text-amber-600 flex items-center gap-2 mb-3">
                <Lightning size={16} weight="duotone" /> Dikkate Alınan Etkinlikler (Event Robotu)
              </h3>
              <div className="flex flex-wrap gap-2">
                {report.events_considered.map((e, i) => (
                  <span key={i} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-50 border border-amber-200 text-xs font-bold text-amber-800">
                    {e.name} · {e.date}
                    <span className="px-1.5 py-0.5 rounded-full bg-amber-500 text-white text-[9px]">skor {e.score}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {(report.risks?.length > 0 || report.opportunities?.length > 0) && (
            <div className="grid md:grid-cols-2 gap-4">
              <div className="bg-rose-50/60 border border-rose-200 rounded-2xl p-5" data-testid="strategist-risks">
                <h3 className="text-sm font-bold text-rose-700 flex items-center gap-2 mb-2"><Warning size={16} weight="duotone" /> Riskler</h3>
                <ul className="space-y-1.5">
                  {(report.risks || []).map((r, i) => <li key={i} className="text-sm text-stone-700 flex gap-2"><span className="text-rose-400">•</span>{r}</li>)}
                </ul>
              </div>
              <div className="bg-emerald-50/60 border border-emerald-200 rounded-2xl p-5" data-testid="strategist-opportunities">
                <h3 className="text-sm font-bold text-emerald-700 flex items-center gap-2 mb-2"><Lightning size={16} weight="duotone" /> Fırsatlar</h3>
                <ul className="space-y-1.5">
                  {(report.opportunities || []).map((o, i) => <li key={i} className="text-sm text-stone-700 flex gap-2"><span className="text-emerald-400">•</span>{o}</li>)}
                </ul>
              </div>
            </div>
          )}

          {/* Recommendations */}
          <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="strategist-recommendations">
            <h3 className="text-sm font-bold text-stone-800 flex items-center gap-2 mb-4">
              <Sparkle size={16} weight="fill" className="text-[#1D4ED8]" /> Strateji Önerileri — Yapılması Gerekenler
            </h3>
            <div className="space-y-3">
              {(report.recommendations || []).map((a) => {
                const meta = ACTION_META[a.action_type] || ACTION_META.monitor;
                const done = a.status !== "suggested";
                return (
                  <div key={a.id} className={`border rounded-xl p-4 flex flex-wrap items-start gap-3 ${done ? "border-stone-100 bg-stone-50/60 opacity-75" : "border-stone-200"}`}
                    data-testid={`strategist-action-${a.id}`}>
                    <div className="flex-1 min-w-[240px]">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`inline-flex items-center gap-1.5 text-[10px] font-bold px-2 py-1 rounded-lg border ${meta.cls}`}>
                          <meta.icon size={12} weight="bold" /> {meta.label}
                        </span>
                        <span className={`text-[9px] font-black px-2 py-0.5 rounded-full uppercase ${PRIORITY[a.priority] || PRIORITY.low}`}>{a.priority}</span>
                        {a.date_start && <span className="text-[10px] text-stone-400 font-bold">{a.date_start}{a.date_end && a.date_end !== a.date_start ? ` → ${a.date_end}` : ""}</span>}
                        {a.target_rate && <span className="text-[10px] font-black text-[#1D4ED8]">hedef €{a.target_rate}</span>}
                        {STATUS_TR[a.status] && (
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${a.status === "dismissed" ? "bg-stone-200 text-stone-500" : "bg-emerald-100 text-emerald-700"}`}>
                            {STATUS_TR[a.status]}
                          </span>
                        )}
                      </div>
                      <div className="font-bold text-sm text-stone-800 mt-1.5">{a.title}</div>
                      <p className="text-xs text-stone-600 mt-1 leading-relaxed">{a.detail}</p>
                      {a.expected_impact && <p className="text-[11px] text-emerald-600 font-bold mt-1">Beklenen etki: {a.expected_impact}</p>}
                    </div>
                    {!done && (
                      <div className="flex items-center gap-2">
                        <button onClick={() => actOn(a.id, "apply")} data-testid={`strategist-apply-${a.id}`}
                          className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-gradient-to-r from-[#1D4ED8] to-[#06B6D4] text-white text-xs font-bold hover:from-[#1E40AF] hover:to-[#0891B2] transition-colors">
                          <CheckCircle size={13} weight="bold" /> Uygula
                        </button>
                        <button onClick={() => actOn(a.id, "dismiss")} data-testid={`strategist-dismiss-${a.id}`}
                          className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-stone-200 text-stone-500 text-xs font-bold hover:bg-stone-50 transition-colors">
                          <XCircle size={13} /> Yoksay
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
