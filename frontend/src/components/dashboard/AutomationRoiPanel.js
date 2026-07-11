import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Coins, ArrowsClockwise, EnvelopeSimple, ShoppingCartSimple, Lightning, Robot, Storefront, Crosshair, ArrowRight, Wrench, TrendUp, Funnel, BellRinging, Heartbeat, Lifebuoy as LifebuoyIcon, ChartBar } from "@phosphor-icons/react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

const API = process.env.REACT_APP_BACKEND_URL;
const ICONS = { rebook: EnvelopeSimple, comeback: ShoppingCartSimple, direct_conversion: Storefront, upsell: Lightning, ai_pricing: Robot };
const fmt = (v) => `£${Number(v || 0).toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;

function FunnelCard({ title, stages, color, testId }) {
  const max = Math.max(...stages.map((s) => s.value), 1);
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-5" data-testid={testId}>
      <div className="flex items-center gap-2 mb-4">
        <Funnel size={16} weight="fill" className="text-stone-500" />
        <h3 className="text-sm font-semibold text-stone-900">{title}</h3>
      </div>
      <div className="space-y-3">
        {stages.map((s) => (
          <div key={s.label}>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-stone-500">{s.label}</span>
              <span className="font-semibold text-stone-800">
                {s.value}{s.rate !== undefined && <span className="text-stone-400 font-normal ml-1.5">%{s.rate}</span>}
              </span>
            </div>
            <div className="h-2 bg-stone-100 rounded-full overflow-hidden">
              <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.round((s.value / max) * 100)}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function AutomationRoiPanel({ propertyId, onNavigate }) {
  const [data, setData] = useState(null);
  const [opps, setOpps] = useState(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [fixing, setFixing] = useState(false);
  const [trend, setTrend] = useState(null);
  const [funnel, setFunnel] = useState(null);
  const [nudge, setNudge] = useState(null);
  const [nudging, setNudging] = useState(false);
  const [pulse, setPulse] = useState(null);
  const [sendingPulse, setSendingPulse] = useState(false);
  const [health, setHealth] = useState(null);
  const [cancelSave, setCancelSave] = useState(null);
  const [savingRun, setSavingRun] = useState(false);
  const [report, setReport] = useState(null);
  const [sendingReport, setSendingReport] = useState(false);

  const sendReport = async () => {
    setSendingReport(true);
    try {
      const r = await axios.post(`${API}/api/automation/report-card/send`, {
        property_id: propertyId === "all" ? "default" : propertyId, force: true,
      });
      toast.success(`Otomasyon Karnesi ${r.data.sent_to ?? 0} yöneticiye gönderildi (£${r.data.grand_total ?? 0})`);
    } catch { toast.error("Karne gönderilemedi"); }
    finally { setSendingReport(false); }
  };

  const runCancelSave = async () => {
    setSavingRun(true);
    try {
      const r = await axios.post(`${API}/api/ai-predictions/cancel-save/run`, { property_id: propertyId });
      toast.success(`İptal kurtarma: ${r.data.scanned} rezervasyon tarandı, ${r.data.offers_sent} tutundurma kuponu gönderildi`);
      load();
    } catch { toast.error("İptal kurtarma taraması başarısız"); }
    finally { setSavingRun(false); }
  };

  const sendPulse = async () => {
    setSendingPulse(true);
    try {
      const r = await axios.post(`${API}/api/automation/daily-pulse/send`, {
        property_id: propertyId === "all" ? "default" : propertyId, force: true,
      });
      toast.success(`Günlük Nabız ${r.data.sent_to ?? 0} yöneticiye gönderildi`);
    } catch { toast.error("Günlük Nabız gönderilemedi"); }
    finally { setSendingPulse(false); }
  };

  const runNudge = async () => {
    setNudging(true);
    try {
      const r = await axios.post(`${API}/api/automation/nudge/run`, { property_id: propertyId });
      toast.success(`Hatırlatmalar gönderildi: ${r.data.upsell_nudged} upsell, ${r.data.coupon_nudged} kupon`);
      load();
    } catch { toast.error("Hatırlatma gönderimi başarısız"); }
    finally { setNudging(false); }
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [r, o, t, f, n, p, h, cs, rc] = await Promise.all([
        axios.get(`${API}/api/automation/roi/${propertyId}?days=${days}`),
        axios.get(`${API}/api/automation/opportunities/${propertyId}`),
        axios.get(`${API}/api/automation/roi/${propertyId}/trend?weeks=8`),
        axios.get(`${API}/api/automation/funnel/${propertyId}?days=30`),
        axios.get(`${API}/api/automation/nudge/stats/${propertyId}?days=30`),
        axios.get(`${API}/api/automation/daily-pulse/preview/${propertyId === "all" ? "default" : propertyId}`),
        axios.get(`${API}/api/automation/health/${propertyId}`),
        axios.get(`${API}/api/ai-predictions/cancel-save/stats/${propertyId}?days=30`),
        axios.get(`${API}/api/automation/report-card/preview/${propertyId}?days=30`),
      ]);
      setData(r.data);
      setOpps(o.data);
      setTrend(t.data);
      setFunnel(f.data);
      setNudge(n.data);
      setPulse(p.data);
      setHealth(h.data);
      setCancelSave(cs.data);
      setReport(rc.data);
    } catch { toast.error("ROI verisi yüklenemedi"); }
    finally { setLoading(false); }
  }, [propertyId, days]);
  useEffect(() => { load(); }, [load]);

  const autoFix = async () => {
    setFixing(true);
    try {
      const r = await axios.post(`${API}/api/automation/opportunities/${propertyId}/auto-fix`, {});
      const res = r.data.results || {};
      const rb = res.rebook || {};
      const cb = res.comeback || {};
      const up = res.upsell || {};
      toast.success(`Otomatik düzeltme tamam: ${rb.queued ?? 0} rebook kuponu, ${cb.emails_sent ?? 0} sepet kurtarma, ${up.offers_sent ?? 0} upsell teklifi gönderildi`);
      load();
    } catch { toast.error("Otomatik düzeltme başarısız"); }
    finally { setFixing(false); }
  };

  if (loading) return <div className="p-8 text-stone-400 text-sm" data-testid="automation-roi-loading">Hesaplanıyor…</div>;
  if (!data) return <div className="p-8 text-stone-400 text-sm">Veri yok</div>;

  const maxRev = Math.max(...data.rows.map((r) => r.revenue), 1);

  return (
    <div className="space-y-6" data-testid="automation-roi-panel">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <Coins size={12} weight="fill" className="text-amber-500" />
            <span>Otomasyon ROI</span>
          </div>
          <h2 className="text-xl font-semibold text-stone-900">Otomasyonlar ne kazandırdı?</h2>
        </div>
        <div className="flex items-center gap-2">
          {[30, 90, 365].map((d) => (
            <button key={d} onClick={() => setDays(d)} data-testid={`roi-days-${d}`}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${days === d ? "bg-stone-900 text-white border-stone-900" : "bg-white text-stone-600 border-stone-200 hover:border-stone-300"}`}>
              {d === 365 ? "1 yıl" : `${d} gün`}
            </button>
          ))}
          <button onClick={load} data-testid="roi-refresh-btn"
            className="inline-flex items-center gap-1.5 text-xs text-stone-500 hover:text-stone-800 border border-stone-200 rounded-lg px-3 py-1.5 bg-white transition-colors">
            <ArrowsClockwise size={14} /> Yenile
          </button>
        </div>
      </div>

      <div className="bg-stone-900 text-white rounded-2xl p-6 flex flex-wrap items-center gap-8">
        <div>
          <div className="text-3xl font-semibold" data-testid="roi-total">{fmt(data.total_attributed)}</div>
          <div className="text-xs text-stone-400 mt-1">Doğrulanmış atfedilen gelir (son {data.days} gün)</div>
        </div>
        <div>
          <div className="text-xl font-semibold text-amber-400">+{fmt(data.total_estimated)}</div>
          <div className="text-xs text-stone-400 mt-1">AI fiyatlama tahmini katkı</div>
        </div>
        {data.commission_saved > 0 && (
          <div>
            <div className="text-xl font-semibold text-emerald-400">{fmt(data.commission_saved)}</div>
            <div className="text-xs text-stone-400 mt-1">OTA komisyon tasarrufu</div>
          </div>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {data.rows.map((r) => {
          const Icon = ICONS[r.key] || Lightning;
          return (
            <div key={r.key} className="bg-white border border-stone-200 rounded-xl p-5" data-testid={`roi-row-${r.key}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-stone-100 flex items-center justify-center">
                    <Icon size={20} className="text-stone-700" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-stone-900">
                      {r.name}
                      {r.estimated && <span className="ml-2 text-[10px] uppercase text-amber-600 font-medium">tahmini</span>}
                    </div>
                    <div className="text-xs text-stone-500 mt-0.5">{r.desc}</div>
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className={`text-lg font-semibold ${r.estimated ? "text-amber-600" : "text-emerald-700"}`}>{fmt(r.revenue)}</div>
                  <div className="text-[11px] text-stone-400">{r.count} işlem{r.extra ? ` · ${fmt(r.extra)} komisyon` : ""}</div>
                </div>
              </div>
              <div className="h-1.5 bg-stone-100 rounded-full mt-4 overflow-hidden">
                <div className={`h-full rounded-full ${r.estimated ? "bg-amber-400" : "bg-emerald-500"}`}
                  style={{ width: `${Math.round((r.revenue / maxRev) * 100)}%` }} />
              </div>
            </div>
          );
        })}
      </div>

      {trend?.buckets?.length > 0 && (
        <div className="bg-white border border-stone-200 rounded-xl p-5" data-testid="roi-trend-chart">
          <div className="flex items-center gap-2 mb-4">
            <TrendUp size={16} weight="fill" className="text-emerald-600" />
            <h3 className="text-sm font-semibold text-stone-900">Haftalık trend — atfedilen gelir (8 hafta)</h3>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={trend.buckets} barCategoryGap="25%">
              <XAxis dataKey="week" tick={{ fontSize: 11, fill: "#78716c" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#78716c" }} axisLine={false} tickLine={false} tickFormatter={(v) => `£${v}`} width={50} />
              <Tooltip formatter={(v, n) => [fmt(v), n === "coupon" ? "Kupon geliri" : "Upsell geliri"]}
                contentStyle={{ borderRadius: 12, border: "1px solid #e7e5e4", fontSize: 12 }} />
              <Bar dataKey="coupon" stackId="a" fill="#10b981" radius={[0, 0, 0, 0]} />
              <Bar dataKey="upsell" stackId="a" fill="#f59e0b" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <div className="flex items-center gap-4 mt-2 text-[11px] text-stone-500">
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-emerald-500 inline-block" /> Kupon (rebook · sepet · OTA→direkt)</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-amber-500 inline-block" /> Upsell</span>
          </div>
        </div>
      )}

      {funnel && (
        <div className="grid md:grid-cols-2 gap-4" data-testid="roi-funnel">
          <FunnelCard title="Kupon hunisi (30 gün)" testId="funnel-coupon"
            stages={[
              { label: "Gönderilen", value: funnel.coupon.sent },
              { label: "Tıklanan", value: funnel.coupon.clicked, rate: funnel.coupon.click_rate },
              { label: "Kullanılan", value: funnel.coupon.redeemed, rate: funnel.coupon.redeem_rate },
            ]} color="bg-emerald-500" />
          <FunnelCard title="Upsell hunisi (30 gün)" testId="funnel-upsell"
            stages={[
              { label: "Gönderilen", value: funnel.upsell.sent },
              { label: "Görüntülenen", value: funnel.upsell.viewed, rate: funnel.upsell.view_rate },
              { label: "Kabul edilen", value: funnel.upsell.accepted, rate: funnel.upsell.accept_rate },
            ]} color="bg-amber-500" />
        </div>
      )}

      {report && (
        <div className="bg-stone-900 text-white rounded-xl p-5 flex flex-wrap items-center justify-between gap-4" data-testid="report-card">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-stone-800 border border-stone-700 flex items-center justify-center shrink-0">
              <ChartBar size={18} className="text-emerald-400" />
            </div>
            <div>
              <div className="text-sm font-semibold">Otomasyon Karnesi — son {report.days} gün</div>
              <div className="text-2xl font-semibold text-emerald-400 mt-1" data-testid="report-grand-total">
                {fmt(report.grand_total)} <span className="text-xs font-normal text-stone-400">kazandırıldı / kurtarıldı</span>
              </div>
              <div className="flex flex-wrap gap-3 mt-2 text-[11px] text-stone-400" data-testid="report-breakdown">
                <span>Kupon {fmt(report.sections.coupons.revenue)}</span>
                <span>Upsell {fmt(report.sections.upsell.revenue)}</span>
                <span>İptal kurtarma {fmt(report.sections.cancel_save.revenue)}</span>
                <span>No-show {fmt(report.sections.noshow.posted)}</span>
                <span>Sızıntı {fmt(report.sections.leakage.closed)}</span>
              </div>
            </div>
          </div>
          <button onClick={sendReport} disabled={sendingReport} data-testid="report-send-btn"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-stone-900 bg-emerald-400 hover:bg-emerald-300 disabled:opacity-60 rounded-lg px-3 py-1.5 transition-colors">
            <ChartBar size={14} weight="fill" />
            {sendingReport ? "Gönderiliyor…" : "Karneyi Şimdi Gönder"}
          </button>
        </div>
      )}

      {cancelSave && (
        <div className="bg-white border border-stone-200 rounded-xl p-5 flex flex-wrap items-center justify-between gap-4" data-testid="cancel-save-card">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-teal-50 border border-teal-100 flex items-center justify-center shrink-0">
              <LifebuoyIcon size={18} className="text-teal-600" />
            </div>
            <div>
              <div className="text-sm font-semibold text-stone-900">İptal Kurtarma (Cancel-Save)</div>
              <div className="text-xs text-stone-500 mt-0.5">
                Yüksek iptal riskli (skor ≥65) rezervasyonlara otomatik tutundurma kuponu (%10) — günlük 11:00
              </div>
              <div className="flex gap-4 mt-2 text-xs text-stone-600" data-testid="cancel-save-stats">
                <span><b>{cancelSave.offers_sent}</b> kupon gönderildi</span>
                <span className="text-emerald-700"><b>{cancelSave.saved}</b> kurtarıldı ({fmt(cancelSave.saved_revenue)})</span>
                <span className="text-stone-500"><b>{cancelSave.pending}</b> bekliyor</span>
                <span className="text-rose-600"><b>{cancelSave.cancelled_anyway}</b> yine de iptal</span>
                {cancelSave.saved + cancelSave.cancelled_anyway > 0 && <span>kurtarma oranı %{cancelSave.save_rate}</span>}
              </div>
            </div>
          </div>
          <button onClick={runCancelSave} disabled={savingRun} data-testid="cancel-save-run-btn"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-white bg-teal-600 hover:bg-teal-700 disabled:opacity-60 rounded-lg px-3 py-1.5 transition-colors">
            <LifebuoyIcon size={14} weight="fill" />
            {savingRun ? "Taranıyor…" : "Şimdi Tara"}
          </button>
        </div>
      )}

      {nudge && (
        <div className="bg-white border border-stone-200 rounded-xl p-5 flex flex-wrap items-center justify-between gap-4" data-testid="nudge-card">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-cyan-50 border border-cyan-100 flex items-center justify-center shrink-0">
              <BellRinging size={18} className="text-cyan-600" />
            </div>
            <div>
              <div className="text-sm font-semibold text-stone-900">Akıllı Hatırlatma (Nudge)</div>
              <div className="text-xs text-stone-500 mt-0.5">
                Açılmamış tekliflere (24s) ve tıklanmamış kuponlara (72s) farklı konu satırıyla tek hatırlatma
              </div>
              <div className="flex gap-4 mt-2 text-xs text-stone-600" data-testid="nudge-stats">
                <span>Upsell: <b>{nudge.upsell.nudged}</b> gönderildi · <b className="text-emerald-700">{nudge.upsell.recovered}</b> geri kazanıldı (%{nudge.upsell.recovery_rate})</span>
                <span>Kupon: <b>{nudge.coupon.nudged}</b> gönderildi · <b className="text-emerald-700">{nudge.coupon.recovered}</b> geri kazanıldı (%{nudge.coupon.recovery_rate})</span>
              </div>
            </div>
          </div>
          <button onClick={runNudge} disabled={nudging} data-testid="nudge-run-btn"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-white bg-cyan-600 hover:bg-cyan-700 disabled:opacity-60 rounded-lg px-3 py-1.5 transition-colors">
            <BellRinging size={14} weight="fill" />
            {nudging ? "Gönderiliyor…" : "Hatırlatmaları Gönder"}
          </button>
        </div>
      )}

      {health && health.rows.length > 0 && (
        <div className="bg-white border border-stone-200 rounded-xl p-5" data-testid="automation-health-card">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <div className="flex items-center gap-2">
              <Heartbeat size={16} weight="fill" className={health.summary.failing > 0 ? "text-rose-500" : "text-emerald-600"} />
              <h3 className="text-sm font-semibold text-stone-900">Otomasyon sağlığı</h3>
            </div>
            <div className="flex items-center gap-3 text-xs" data-testid="health-summary">
              <span className="text-emerald-700">● {health.summary.healthy} sağlıklı</span>
              {health.summary.stale > 0 && <span className="text-amber-600">● {health.summary.stale} bayat</span>}
              {health.summary.pending > 0 && <span className="text-stone-400">● {health.summary.pending} bekliyor</span>}
              {health.summary.failing > 0 && <span className="text-rose-600 font-semibold">● {health.summary.failing} HATALI</span>}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {(() => {
              const byJob = {};
              const rank = { failing: 3, stale: 2, pending: 1, healthy: 0 };
              for (const r of health.rows) {
                const cur = byJob[r.job];
                if (!cur || rank[r.status] > rank[cur.status]) byJob[r.job] = r;
              }
              const dot = { healthy: "bg-emerald-500", stale: "bg-amber-500", pending: "bg-stone-300", failing: "bg-rose-500" };
              return Object.values(byJob).map((r) => (
                <div key={r.job} className="inline-flex items-center gap-2 border border-stone-200 rounded-full px-3 py-1.5 text-xs text-stone-700"
                  data-testid={`health-${r.job}`}
                  title={r.status === "failing" ? r.last_error : (r.last_run_at ? `Son çalışma: ${r.last_run_at.slice(0, 16).replace("T", " ")}` : "Henüz çalışmadı")}>
                  <span className={`w-2 h-2 rounded-full ${dot[r.status]}`} />
                  {r.label}
                  {r.consecutive_failures > 1 && <span className="text-rose-600 font-semibold">×{r.consecutive_failures}</span>}
                </div>
              ));
            })()}
          </div>
        </div>
      )}


      {pulse && (
        <div className="bg-white border border-stone-200 rounded-xl p-5" data-testid="daily-pulse-card">
          <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center shrink-0">
                <EnvelopeSimple size={18} className="text-indigo-600" />
              </div>
              <div>
                <div className="text-sm font-semibold text-stone-900">Günlük Nabız — GM özet e-postası</div>
                <div className="text-xs text-stone-500 mt-0.5">Her sabah 08:00'de yöneticilere otomatik gönderilir</div>
              </div>
            </div>
            <button onClick={sendPulse} disabled={sendingPulse} data-testid="pulse-send-btn"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 rounded-lg px-3 py-1.5 transition-colors">
              <EnvelopeSimple size={14} weight="fill" />
              {sendingPulse ? "Gönderiliyor…" : "Şimdi Gönder"}
            </button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3 text-center" data-testid="pulse-preview">
            {[
              { label: "Varış", value: pulse.today.arrivals },
              { label: "Çıkış", value: pulse.today.departures },
              { label: "Konaklayan", value: pulse.today.in_house },
              { label: "Doluluk", value: pulse.today.occupancy_pct != null ? `%${pulse.today.occupancy_pct}` : "—" },
              { label: "Dün rezervasyon", value: fmt(pulse.yesterday.booked_revenue) },
              { label: "Dün otomasyon", value: fmt(pulse.yesterday.automation_revenue) },
              ...(pulse.leakage_closed_7d > 0 ? [{ label: "Sızıntı kapatıldı (7g)", value: fmt(pulse.leakage_closed_7d) }] : []),
            ].map((s) => (
              <div key={s.label} className="bg-stone-50 border border-stone-100 rounded-lg p-3">
                <div className="text-base font-semibold text-stone-900">{s.value}</div>
                <div className="text-[11px] text-stone-500 mt-0.5">{s.label}</div>
              </div>
            ))}
          </div>
          {(pulse.risks.open_logbook > 0 || pulse.risks.unanswered_reviews > 0) && (
            <div className="mt-3 text-xs text-rose-600" data-testid="pulse-risks">
              ⚠ {pulse.risks.open_logbook > 0 && `${pulse.risks.open_logbook} açık logbook kaydı`}
              {pulse.risks.open_logbook > 0 && pulse.risks.unanswered_reviews > 0 && " · "}
              {pulse.risks.unanswered_reviews > 0 && `${pulse.risks.unanswered_reviews} yanıtlanmamış yorum`}
            </div>
          )}
        </div>
      )}

      {opps && (
        <div className="space-y-3" data-testid="opportunity-radar">
          <div className="flex items-center justify-between pt-2">
            <div className="flex items-center gap-2">
              <Crosshair size={16} weight="fill" className="text-rose-500" />
              <h3 className="text-sm font-semibold text-stone-900">Fırsat Radarı — masada kalan para</h3>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-sm font-semibold text-rose-600" data-testid="opportunity-total">
                ~{fmt(opps.total_potential)} potansiyel
              </div>
              <button onClick={autoFix} disabled={fixing} data-testid="auto-fix-btn"
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 disabled:opacity-60 rounded-lg px-3 py-1.5 transition-colors">
                <Wrench size={14} weight="fill" />
                {fixing ? "Çalışıyor…" : "Hepsini Düzelt"}
              </button>
            </div>
          </div>
          <div className="grid md:grid-cols-2 gap-3">
            {opps.rows.map((r) => {
              const Icon = ICONS[r.key] || Lightning;
              return (
                <div key={r.key} className="bg-rose-50/50 border border-rose-100 rounded-xl p-4 flex items-start justify-between gap-3"
                  data-testid={`opportunity-${r.key}`}>
                  <div className="flex items-start gap-3 min-w-0">
                    <div className="w-9 h-9 rounded-lg bg-white border border-rose-100 flex items-center justify-center shrink-0">
                      <Icon size={18} className="text-rose-500" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-stone-900">{r.name}</div>
                      <div className="text-xs text-stone-500 mt-0.5">{r.desc}</div>
                      {onNavigate && r.count > 0 && (
                        <button onClick={() => onNavigate(r.view)} data-testid={`opportunity-action-${r.key}`}
                          className="inline-flex items-center gap-1 mt-2 text-xs font-medium text-rose-700 hover:text-rose-900 transition-colors">
                          {r.action} <ArrowRight size={12} />
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-base font-semibold text-rose-600">~{fmt(r.potential)}</div>
                    <div className="text-[11px] text-stone-400">{r.count} fırsat{r.extra ? ` · ${fmt(r.extra)} komisyon riski` : ""}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
