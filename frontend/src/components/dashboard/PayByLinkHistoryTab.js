import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { CheckCircle, Clock, WarningCircle, BellRinging, EnvelopeSimple, FileText, Sparkle, ArrowsClockwise, PaperPlaneTilt } from "@phosphor-icons/react";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_STYLE = {
  paid: "bg-emerald-100 text-emerald-700",
  pending: "bg-amber-100 text-amber-700",
  failed: "bg-red-100 text-red-600",
  expired: "bg-stone-100 text-stone-500",
};

export const PayByLinkHistoryTab = ({ propertyId }) => {
  const [links, setLinks] = useState([]);
  const [reports, setReports] = useState([]);
  const [stats, setStats] = useState(null);
  const [insights, setInsights] = useState(null);
  const [tipsLoading, setTipsLoading] = useState(false);

  const loadInsights = useCallback(async (refresh = 0) => {
    setTipsLoading(true);
    try {
      const { data } = await axios.get(`${API}/pay-links/insights`, {
        params: { property_id: propertyId || "", refresh },
      });
      setInsights(data);
    } catch (e) { /* silent */ }
    setTipsLoading(false);
  }, [propertyId]);

  const [bulkSending, setBulkSending] = useState(false);

  const bulkSend = async () => {
    if (!window.confirm("Ödenmemiş rezervasyonlara (en fazla 20) toplu Stripe ödeme linki gönderilecek. Devam?")) return;
    setBulkSending(true);
    try {
      const { data } = await axios.post(`${API}/pay-links/bulk-send`, {
        property_id: propertyId || "", language: "en",
      });
      toast.success(`${data.sent} link gönderildi, ${data.skipped} atlandı (zaten aktif link var)`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Toplu gönderim başarısız"); }
    setBulkSending(false);
  };

  const applyTip = async (tip) => {
    try {
      await axios.post(`${API}/pay-links/insights/apply`, {
        property_id: propertyId || "all", tip,
      });
      loadInsights();
    } catch (e) { /* silent */ }
  };

  useEffect(() => { loadInsights(); }, [loadInsights]);

  const load = useCallback(async () => {
    axios.get(`${API}/pay-links/history`, { params: { property_id: propertyId || "" } })
      .then(r => setLinks(r.data)).catch(() => {});
    axios.get(`${API}/pay-links/stats`, { params: { property_id: propertyId || "" } })
      .then(r => setStats(r.data)).catch(() => {});
    axios.get(`${API}/pulse/weekly-reports`, { params: { property_id: "all" } })
      .then(r => setReports(r.data)).catch(() => {});
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6" data-testid="pay-by-link-tab">
      {/* Conversion analytics */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3" data-testid="pay-link-stats">
          <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
            <div className="text-lg font-bold text-stone-800">{stats.total_links}</div>
            <div className="text-[9px] text-stone-400 uppercase font-semibold">Links Sent</div>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
            <div className="text-lg font-bold text-emerald-600">{stats.paid_links}</div>
            <div className="text-[9px] text-stone-400 uppercase font-semibold">Paid</div>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
            <div className={`text-lg font-bold ${stats.conversion_pct >= 50 ? "text-emerald-600" : "text-amber-600"}`} data-testid="pay-link-conversion">{stats.conversion_pct}%</div>
            <div className="text-[9px] text-stone-400 uppercase font-semibold">Conversion</div>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
            <div className="text-lg font-bold text-emerald-700">£{stats.total_collected?.toLocaleString()}</div>
            <div className="text-[9px] text-stone-400 uppercase font-semibold">Collected</div>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
            <div className="text-lg font-bold text-indigo-600">{stats.avg_hours_to_pay != null ? (stats.avg_hours_to_pay < 1 ? "<1h" : `${stats.avg_hours_to_pay}h`) : "—"}</div>
            <div className="text-[9px] text-stone-400 uppercase font-semibold">Avg Time to Pay</div>
          </div>
        </div>
      )}

      {/* AI conversion tips */}
      {insights?.tips?.length > 0 && (
        <div className="bg-gradient-to-br from-indigo-50 to-white border border-indigo-100 rounded-xl p-4" data-testid="pay-link-ai-tips">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xs font-semibold text-indigo-800 flex items-center gap-1.5">
              <Sparkle size={14} weight="fill" className="text-indigo-500" /> AI Dönüşüm İpuçları
            </h3>
            <button onClick={() => loadInsights(1)} disabled={tipsLoading}
              className="text-[10px] text-indigo-500 hover:text-indigo-700 flex items-center gap-1 disabled:opacity-50"
              data-testid="pay-link-tips-refresh">
              <ArrowsClockwise size={11} className={tipsLoading ? "animate-spin" : ""} /> Yenile
            </button>
          </div>
          <ul className="space-y-1.5">
            {insights.tips.map((t, i) => {
              const applied = (insights.applied || []).find(a => a.tip === t);
              return (
                <li key={i} className="text-[11px] text-stone-600 flex gap-2 items-start">
                  <span className="text-indigo-400 font-bold shrink-0">{i + 1}.</span>
                  <span className="flex-1">{t}</span>
                  {applied ? (
                    <span className="shrink-0 text-[9px] px-1.5 py-0.5 bg-emerald-100 text-emerald-700 rounded-full font-semibold"
                      title={`Baseline: %${applied.baseline_conversion}`} data-testid={`tip-applied-${i}`}>
                      ✓ Uygulandı{applied.impact_pts != null ? ` · ${applied.impact_pts >= 0 ? "+" : ""}${applied.impact_pts} puan` : ""}
                    </span>
                  ) : (
                    <button onClick={() => applyTip(t)}
                      className="shrink-0 text-[9px] px-2 py-0.5 bg-white border border-indigo-200 text-indigo-600 rounded-full font-semibold hover:bg-indigo-50"
                      data-testid={`tip-apply-${i}`}>
                      Uygulandı işaretle
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
          {(insights.applied || []).some(a => a.impact_pts != null) && (
            <div className="mt-2 text-[10px] text-stone-400">
              Etki, ipucu uygulandıktan 7 gün sonra dönüşüm oranı farkı olarak ölçülür.
            </div>
          )}
        </div>
      )}

      {/* Link & reminder history */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-stone-800 flex items-center gap-1.5">
            <BellRinging size={15} className="text-indigo-600" /> Stripe Link & Reminder History
          </h3>
          <button onClick={bulkSend} disabled={bulkSending}
            className="text-[11px] px-3 py-1.5 bg-indigo-600 text-white rounded-lg font-semibold hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-1.5"
            data-testid="bulk-send-links-btn">
            {bulkSending ? <ArrowsClockwise size={12} className="animate-spin" /> : <PaperPlaneTilt size={12} weight="bold" />}
            {bulkSending ? "Gönderiliyor…" : "Toplu Link Gönder"}
          </button>
        </div>
        {links.length === 0 ? (
          <div className="bg-white rounded-xl border border-stone-200 p-8 text-center text-sm text-stone-400">
            No Stripe payment links yet
          </div>
        ) : (
          <div className="space-y-1.5" data-testid="pay-link-history-list">
            {links.map((l, i) => (
              <div key={i} className="bg-white border border-stone-200 rounded-xl px-4 py-2.5 flex items-center justify-between text-xs">
                <div className="flex items-center gap-3 min-w-0">
                  {l.payment_status === "paid"
                    ? <CheckCircle size={16} className="text-emerald-500 shrink-0" weight="fill" />
                    : l.payment_status === "pending"
                      ? <Clock size={16} className="text-amber-500 shrink-0" />
                      : <WarningCircle size={16} className="text-stone-400 shrink-0" />}
                  <div className="min-w-0">
                    <div className="font-semibold text-stone-800 truncate">
                      {l.guest_name || "Guest"} {l.booking_ref && <span className="font-mono text-stone-400">· {l.booking_ref}</span>}
                    </div>
                    <div className="text-[10px] text-stone-400 truncate">
                      {l.created_at?.slice(0, 16).replace("T", " ")}
                      {l.emailed_to && <span> · <EnvelopeSimple size={9} className="inline" /> {l.emailed_to}{l.email_mocked ? " (demo)" : ""}</span>}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {l.created_by === "auto_reminder" && (
                    <span className="text-[9px] px-1.5 py-0.5 bg-indigo-50 text-indigo-600 rounded-full font-semibold">REMINDER</span>
                  )}
                  {l.superseded_by && (
                    <span className="text-[9px] px-1.5 py-0.5 bg-stone-100 text-stone-500 rounded-full">superseded</span>
                  )}
                  <span className="font-bold text-stone-800">£{Number(l.amount || 0).toFixed(2)}</span>
                  <span className={`text-[9px] px-2 py-0.5 rounded-full font-semibold ${STATUS_STYLE[l.payment_status] || "bg-stone-100 text-stone-500"}`}>
                    {l.payment_status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Weekly report archive */}
      <div>
        <h3 className="text-sm font-semibold text-stone-800 mb-2 flex items-center gap-1.5">
          <FileText size={15} className="text-rose-500" /> Weekly Pickup Report Archive
        </h3>
        {reports.length === 0 ? (
          <div className="bg-white rounded-xl border border-stone-200 p-8 text-center text-sm text-stone-400">
            No weekly reports yet — sent automatically every Monday 07:00 UTC
          </div>
        ) : (
          <div className="space-y-1.5" data-testid="weekly-report-archive">
            {reports.map((r, i) => (
              <div key={i} className="bg-white border border-stone-200 rounded-xl px-4 py-2.5 flex items-center justify-between text-xs">
                <div>
                  <div className="font-semibold text-stone-800">{r.week_start} → {r.week_end}</div>
                  <div className="text-[10px] text-stone-400">
                    {(r.emailed_to || []).length} recipients{r.email_mocked ? " (demo mode)" : ""} · {r.created_at?.slice(0, 16).replace("T", " ")}
                  </div>
                </div>
                <div className="flex items-center gap-3 text-stone-700">
                  <span><b>{r.rooms}</b> rooms</span>
                  <span><b>{r.room_nights}</b> nights</span>
                  <span className="font-bold text-emerald-700">£{Number(r.revenue || 0).toLocaleString()}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
