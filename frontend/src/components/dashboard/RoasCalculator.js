/**
 * ROAS Calculator
 * ---------------
 * Uploads Google Ads campaign cost CSV, joins with tracked booking revenue
 * per utm_campaign, and displays profit margins + ROAS per campaign.
 *
 * Renders inside AttributionPanel as a collapsible section — one glance
 * and the manager knows which campaigns to scale vs kill.
 */
import { useEffect, useState, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Calculator, UploadCloud, FileDown, Loader2, RefreshCw, Trash2, TrendingUp,
  TrendingDown, Sparkles, ArrowUp, ArrowDown, Minus,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_META = {
  green:   { label: "Ölçekle",     dot: "bg-emerald-500",  text: "text-emerald-300", ring: "ring-emerald-500/30" },
  yellow:  { label: "İzle",         dot: "bg-amber-500",    text: "text-amber-300",   ring: "ring-amber-500/30" },
  red:     { label: "Durdur",      dot: "bg-rose-500",     text: "text-rose-300",    ring: "ring-rose-500/30" },
  no_cost: { label: "Cost yok",     dot: "bg-sky-500",      text: "text-sky-300",     ring: "ring-sky-500/30" },
  no_data: { label: "Veri yok",     dot: "bg-stone-500",    text: "text-stone-300",   ring: "ring-stone-500/20" },
};

const ACTION_META = {
  cut:      { icon: TrendingDown, cls: "bg-rose-500/10 border-rose-500/30 text-rose-200",       arrowIcon: ArrowDown },
  hold:     { icon: Minus,         cls: "bg-stone-700/40 border-stone-600 text-stone-200",        arrowIcon: Minus },
  increase: { icon: TrendingUp,    cls: "bg-emerald-500/10 border-emerald-500/30 text-emerald-200", arrowIcon: ArrowUp },
  double:   { icon: Sparkles,      cls: "bg-fuchsia-500/10 border-fuchsia-500/30 text-fuchsia-200", arrowIcon: ArrowUp },
  info:     { icon: Sparkles,      cls: "bg-sky-500/10 border-sky-500/30 text-sky-200",           arrowIcon: Minus },
  skip:     { icon: Minus,         cls: "bg-stone-800 border-stone-700 text-stone-500",           arrowIcon: Minus },
};

export default function RoasCalculator({ propertyId, currency = "GBP" }) {
  const [data, setData] = useState(null);
  const [days, setDays] = useState(30);
  const [marginPct, setMarginPct] = useState(60);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const r = await axios.get(
        `${API}/attribution/${propertyId}/roas?days=${days}&margin_pct=${marginPct}`,
      );
      setData(r.data);
    } catch {
      toast.error("ROAS verisi alınamadı");
    }
    setLoading(false);
  }, [propertyId, days, marginPct]);

  useEffect(() => { load(); }, [load]);

  const downloadTemplate = async () => {
    try {
      const r = await axios.get(`${API}/attribution/roas/template.csv`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url; a.download = "google_ads_cost_template.csv"; a.click();
      URL.revokeObjectURL(url);
      toast.success("Şablon indirildi");
    } catch {
      toast.error("Şablon indirilemedi");
    }
  };

  const onUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) {
      toast.error("Sadece .csv kabul edilir");
      e.target.value = "";
      return;
    }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await axios.post(`${API}/attribution/${propertyId}/roas/cost`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const { inserted_or_updated, skipped, errors } = r.data;
      toast.success(`${inserted_or_updated} kampanya güncellendi${skipped ? ` · ${skipped} satır atlandı` : ""}`);
      if (errors?.length) toast.warning(errors.join(" · "));
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Yükleme başarısız");
    }
    setUploading(false);
    e.target.value = "";
  };

  const deleteCampaign = async (camp) => {
    if (!window.confirm(`"${camp}" için yüklü cost verisini silinsin mi?`)) return;
    try {
      await axios.delete(`${API}/attribution/${propertyId}/roas/cost/${encodeURIComponent(camp)}`);
      toast.success("Silindi");
      load();
    } catch {
      toast.error("Silinemedi");
    }
  };

  const fmt = (n) => `${currency === "GBP" ? "£" : currency === "EUR" ? "€" : "$"}${(n || 0).toFixed(2)}`;
  const totals = data?.totals || {};
  const rows = data?.campaigns || [];

  return (
    <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-5 space-y-4" data-testid="roas-calculator">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Calculator className="w-5 h-5 text-emerald-400" />
          <div>
            <h3 className="text-lg font-semibold text-stone-100">ROAS Calculator</h3>
            <p className="text-xs text-stone-500">Google Ads maliyetlerini yükleyin — otomatik kampanya bazlı kâr &amp; ROAS.</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <label className="text-xs text-stone-400">Marj %</label>
          <input
            data-testid="roas-margin"
            type="number"
            min={0}
            max={100}
            value={marginPct}
            onChange={(e) => setMarginPct(Math.max(0, Math.min(100, parseFloat(e.target.value) || 0)))}
            className="w-16 px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm"
          />
          <select
            data-testid="roas-days"
            value={days}
            onChange={(e) => setDays(parseInt(e.target.value, 10))}
            className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm"
          >
            {[7, 14, 30, 60, 90].map((d) => <option key={d} value={d}>{`${d}g`}</option>)}
          </select>
          <button
            data-testid="roas-refresh"
            onClick={load}
            className="p-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-200"
            title="Yenile"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            data-testid="roas-template-btn"
            onClick={downloadTemplate}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-200 text-xs font-semibold"
          >
            <FileDown className="w-4 h-4" /> Şablon
          </button>
          <input
            ref={fileRef}
            data-testid="roas-file-input"
            type="file"
            accept=".csv,text/csv"
            onChange={onUpload}
            className="hidden"
          />
          <button
            data-testid="roas-upload-btn"
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold disabled:opacity-60"
          >
            {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <UploadCloud className="w-4 h-4" />}
            CSV Yükle
          </button>
        </div>
      </div>

      {/* Totals */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2" data-testid="roas-totals">
        <TotalCard label="Toplam Cost" value={fmt(totals.cost)} />
        <TotalCard label="Toplam Gelir" value={fmt(totals.revenue)} highlight />
        <TotalCard label="Net Kâr" value={fmt(totals.profit)} highlight={totals.profit > 0} negative={totals.profit < 0} />
        <TotalCard label="Rezervasyon" value={totals.bookings ?? 0} />
        <TotalCard label="Ortalama ROAS" value={totals.roas ? `${totals.roas}x` : "—"} highlight={(totals.roas || 0) >= 3} />
      </div>

      {/* Action summary — auto budget hint */}
      {data?.action_summary && rows.length > 0 && (
        <ActionSummary summary={data.action_summary} fmt={fmt} />
      )}

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center py-8 text-stone-500">
          <Loader2 className="w-5 h-5 animate-spin" />
        </div>
      ) : rows.length === 0 ? (
        <EmptyState onUploadClick={() => fileRef.current?.click()} onTemplateClick={downloadTemplate} />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-stone-800">
          <table className="w-full text-sm">
            <thead className="bg-stone-800/60">
              <tr className="text-stone-400 text-xs uppercase tracking-wider">
                <th className="text-left px-3 py-2">Kampanya</th>
                <th className="text-right px-3 py-2">Cost</th>
                <th className="text-right px-3 py-2">Gelir</th>
                <th className="text-right px-3 py-2">Rez.</th>
                <th className="text-right px-3 py-2">CPA</th>
                <th className="text-right px-3 py-2">ROAS</th>
                <th className="text-right px-3 py-2">Net Kâr</th>
                <th className="text-center px-3 py-2">Durum</th>
                <th className="text-left px-3 py-2">Öneri</th>
                <th className="px-2 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const meta = STATUS_META[r.status] || STATUS_META.no_data;
                const hasCost = r.cost > 0;
                const sug = r.suggestion;
                const sMeta = (sug && ACTION_META[sug.action]) || ACTION_META.skip;
                const SArrow = sMeta.arrowIcon;
                return (
                  <tr key={r.campaign} className="border-t border-stone-800 hover:bg-stone-800/30" data-testid="roas-row">
                    <td className="px-3 py-2 text-stone-100 font-medium">{r.campaign}</td>
                    <td className="px-3 py-2 text-right text-stone-300">{fmt(r.cost)}</td>
                    <td className="px-3 py-2 text-right text-emerald-300 font-semibold">{fmt(r.revenue)}</td>
                    <td className="px-3 py-2 text-right text-stone-300">{r.bookings}</td>
                    <td className="px-3 py-2 text-right text-stone-400">{r.cpa != null ? fmt(r.cpa) : "—"}</td>
                    <td className="px-3 py-2 text-right font-bold">
                      <span className={meta.text}>{r.roas != null ? `${r.roas}x` : "—"}</span>
                    </td>
                    <td className={`px-3 py-2 text-right font-semibold ${r.profit >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                      {fmt(r.profit)}
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ring-1 ${meta.ring} ${meta.text}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                        {meta.label}
                      </span>
                    </td>
                    <td className="px-3 py-2" data-testid="roas-suggestion">
                      {sug && (
                        <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md border text-[11px] max-w-[200px] ${sMeta.cls}`} title={sug.reason}>
                          <SArrow className="w-3 h-3 flex-shrink-0" />
                          <span className="font-semibold truncate">
                            {sug.delta_pct !== 0 ? `${sug.delta_pct > 0 ? "+" : ""}${sug.delta_pct}% · ` : ""}{sug.headline}
                          </span>
                        </div>
                      )}
                    </td>
                    <td className="px-2 py-2 text-right">
                      {hasCost && (
                        <button
                          onClick={() => deleteCampaign(r.campaign)}
                          className="p-1 text-stone-500 hover:text-rose-400"
                          title="Cost sil"
                          data-testid={`roas-del-${r.campaign}`}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {rows.length > 0 && (
        <div className="text-xs text-stone-500 flex items-center gap-1.5">
          <TrendingUp className="w-3.5 h-3.5" />
          ROAS = Gelir ÷ Cost · Net Kâr = (Gelir × Marj%) − Cost · Yeşil ≥ 3x, Sarı 1-3x, Kırmızı &lt; 1x
        </div>
      )}
    </div>
  );
}

function TotalCard({ label, value, highlight = false, negative = false }) {
  const cls = negative
    ? "bg-rose-500/10 border-rose-500/30 text-rose-200"
    : highlight
      ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-200"
      : "bg-stone-800/60 border-stone-800 text-stone-100";
  return (
    <div className={`p-2.5 rounded-lg border ${cls}`}>
      <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-0.5">{label}</div>
      <div className="text-base font-bold">{value}</div>
    </div>
  );
}

function ActionSummary({ summary, fmt }) {
  const rows = [
    { key: "double",   label: "2× Ölçekle",   count: summary.double,   cls: "text-fuchsia-300 bg-fuchsia-500/10 border-fuchsia-500/30" },
    { key: "increase", label: "Artır",         count: summary.increase, cls: "text-emerald-300 bg-emerald-500/10 border-emerald-500/30" },
    { key: "hold",     label: "Sabit",         count: summary.hold,     cls: "text-stone-200 bg-stone-700/40 border-stone-600" },
    { key: "cut",      label: "Azalt",          count: summary.cut,      cls: "text-rose-300 bg-rose-500/10 border-rose-500/30" },
    { key: "info",     label: "Cost eksik",    count: summary.info,     cls: "text-sky-300 bg-sky-500/10 border-sky-500/30" },
  ].filter((r) => r.count > 0);

  const hasIncrease = summary.potential_increase > 0;
  const hasSavings = summary.potential_savings > 0;
  if (!rows.length && !hasIncrease && !hasSavings) return null;

  return (
    <div className="rounded-lg border border-indigo-500/30 bg-gradient-to-r from-indigo-500/10 via-fuchsia-500/5 to-transparent p-3" data-testid="roas-action-summary">
      <div className="flex items-center gap-2 mb-2">
        <Sparkles className="w-4 h-4 text-fuchsia-300" />
        <h4 className="text-sm font-bold text-stone-100">Otomatik Bütçe Önerisi</h4>
        <span className="text-[10px] text-stone-500">Marj-adjust · rule-based</span>
      </div>
      <div className="flex flex-wrap gap-2 items-center">
        {rows.map((r) => (
          <div key={r.key} className={`px-2 py-1 rounded-full text-xs border ${r.cls}`}>
            <b>{r.count}</b> · {r.label}
          </div>
        ))}
        {hasIncrease && (
          <div className="ml-auto flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/40 text-emerald-200 font-semibold" data-testid="roas-potential-increase">
            <ArrowUp className="w-3 h-3" /> +{fmt(summary.potential_increase)} önerilen artış
          </div>
        )}
        {hasSavings && (
          <div className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-rose-500/15 border border-rose-500/40 text-rose-200 font-semibold" data-testid="roas-potential-savings">
            <ArrowDown className="w-3 h-3" /> −{fmt(summary.potential_savings)} tasarruf
          </div>
        )}
      </div>
    </div>
  );
}

function EmptyState({ onUploadClick, onTemplateClick }) {
  return (
    <div className="text-center py-8 border border-dashed border-stone-700 rounded-lg" data-testid="roas-empty">
      <UploadCloud className="w-10 h-10 text-stone-600 mx-auto mb-2" />
      <p className="text-sm text-stone-300 font-medium mb-1">Henüz kampanya cost verisi yüklenmemiş</p>
      <p className="text-xs text-stone-500 mb-4">
        Google Ads → Rapor → CSV Dışa Aktar. Kolonlar: Campaign, Cost, Currency, Clicks, Impressions
      </p>
      <div className="flex items-center justify-center gap-2">
        <button
          onClick={onTemplateClick}
          className="px-3 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-200 text-xs font-semibold"
        >
          Şablon İndir
        </button>
        <button
          onClick={onUploadClick}
          className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold"
        >
          CSV Yükle
        </button>
      </div>
    </div>
  );
}
