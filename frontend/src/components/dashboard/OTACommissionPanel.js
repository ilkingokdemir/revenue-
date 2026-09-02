/**
 * OTACommissionPanel (iter 374) — Net Revenue Dashboard
 *
 * Shows gross vs commission vs net revenue per channel over a date range.
 * Admin can override commission rates per channel/property.
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  TrendingUp, DollarSign, PieChart, RefreshCw, Percent, Settings,
  Save, ArrowDownRight,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function OTACommissionPanel({ activePropertyId }) {
  const [tab, setTab] = useState("summary");
  return (
    <div className="p-6 max-w-[1400px] mx-auto" data-testid="ota-commission-panel">
      <div className="mb-5">
        <div className="text-xs uppercase tracking-widest text-stone-500 mb-1 flex items-center gap-1.5">
          <Percent className="w-3 h-3 text-emerald-500" /> Kanal Karlılığı
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">OTA Commission & Net Revenue</h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Her booking için OTA komisyon oranını otomatik hesapla, net gelirinizi kanal bazında görün.
          Direct kanallar %0 komisyon → maksimum karlılık.
        </p>
      </div>

      <div className="flex gap-2 mb-5 border-b border-stone-200">
        <TabBtn active={tab === "summary"} onClick={() => setTab("summary")} testId="ota-com-tab-summary">
          <DollarSign className="w-4 h-4 inline mr-1.5" /> Özet & Leaderboard
        </TabBtn>
        <TabBtn active={tab === "rates"} onClick={() => setTab("rates")} testId="ota-com-tab-rates">
          <Settings className="w-4 h-4 inline mr-1.5" /> Komisyon Oranları
        </TabBtn>
      </div>

      {tab === "summary" && <SummaryTab activePropertyId={activePropertyId} />}
      {tab === "rates" && <RatesTab activePropertyId={activePropertyId} />}
    </div>
  );
}

const TabBtn = ({ active, onClick, children, testId }) => (
  <button onClick={onClick} data-testid={testId}
    className={`px-4 py-2.5 text-sm font-semibold transition -mb-px border-b-2 ${
      active ? "border-emerald-600 text-emerald-700" : "border-transparent text-stone-500 hover:text-stone-700"
    }`}>{children}</button>
);

/* ═══════════ SUMMARY TAB ═══════════ */
const OtaConversionCard = ({ activePropertyId, days }) => {
  const [d, setD] = useState(null);
  useEffect(() => {
    axios.get(`${API}/booking-widget/ota-conversion/${activePropertyId || "all"}?days=${days}`).then(r => setD(r.data)).catch(() => setD(null));
  }, [activePropertyId, days]);
  if (!d) return null;
  const fmt = (n) => Number(n || 0).toLocaleString("tr-TR", { maximumFractionDigits: 0 });
  return (
    <div className="border border-emerald-200 rounded-lg bg-emerald-50/40 p-4" data-testid="ota-conversion-card">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div className="text-sm font-semibold text-emerald-900">OTA'dan Çevrilen (direkt şerit) — son {d.days} gün</div>
        <div className="text-[11px] text-stone-500">Şerit: "Direkt rezervasyonda %{d.direct_advantage_pct} daha ucuz" · Booking Engine › Theme'den ayarlanır</div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
        <div className="bg-white rounded-lg p-3 border border-stone-100"><div className="text-[11px] text-stone-500">Şerit görüntülenme</div><div className="text-xl font-bold" data-testid="ota-conv-views">{fmt(d.banner_views)}</div></div>
        <div className="bg-white rounded-lg p-3 border border-stone-100"><div className="text-[11px] text-stone-500">Direkt rezervasyon</div><div className="text-xl font-bold text-emerald-700" data-testid="ota-conv-bookings">{fmt(d.bookings)}</div></div>
        <div className="bg-white rounded-lg p-3 border border-stone-100"><div className="text-[11px] text-stone-500">Dönüşüm</div><div className="text-xl font-bold" data-testid="ota-conv-pct">{d.conversion_pct}%</div></div>
        <div className="bg-white rounded-lg p-3 border border-stone-100"><div className="text-[11px] text-stone-500">Gelir</div><div className="text-xl font-bold">£{fmt(d.revenue)}</div></div>
        <div className="bg-white rounded-lg p-3 border border-emerald-200"><div className="text-[11px] text-stone-500">Kurtarılan komisyon (~%15)</div><div className="text-xl font-bold text-emerald-700" data-testid="ota-conv-saved">£{fmt(d.commission_saved)}</div></div>
      </div>
      {d.by_ota?.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
          {d.by_ota.map(x => <span key={x.ota} className="px-2 py-0.5 rounded-full bg-white border border-stone-200 text-stone-600">{x.ota}: {x.bookings}</span>)}
        </div>
      )}
      {d.ab && (
        <div className="mt-3 border border-violet-200 bg-violet-50/50 rounded-lg p-3" data-testid="ota-ab-card">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
            <div className="text-xs font-semibold text-violet-900">A/B Testi — şerit mesajı %{d.direct_advantage_pct} (A) vs %{d.ab.variant_b_pct} (B)
              <span className={`ml-2 px-1.5 py-0.5 rounded-full text-[10px] ${d.ab.enabled ? "bg-violet-600 text-white" : "bg-stone-200 text-stone-600"}`} data-testid="ota-ab-status">{d.ab.enabled ? "AKTİF" : "KAPALI"}</span>
            </div>
            <div className="text-[11px] text-stone-500">{d.ab.winner ? <>Kazanan: <b className="text-violet-800" data-testid="ota-ab-winner">Varyant {d.ab.winner}</b></> : `Kazanan için her varyantta ≥${d.ab.min_views_for_winner} gösterim gerekir`}</div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {d.ab.variants.map(v => (
              <div key={v.variant} className={`bg-white rounded-lg p-3 border ${d.ab.winner === v.variant ? "border-violet-400" : "border-stone-100"}`} data-testid={`ota-ab-variant-${v.variant}`}>
                <div className="text-[11px] text-stone-500">Varyant {v.variant} · %{v.variant === "A" ? d.direct_advantage_pct : d.ab.variant_b_pct}</div>
                <div className="text-sm mt-1"><b>{fmt(v.views)}</b> gösterim · <b className="text-emerald-700">{fmt(v.bookings)}</b> rezervasyon · <b>{v.conversion_pct}%</b> dönüşüm</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

const SummaryTab = ({ activePropertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [days, setDays] = useState(90);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ days: String(days) });
      if (activePropertyId && activePropertyId !== "all") params.set("property_id", activePropertyId);
      const r = await axios.get(`${API}/ota-commission/leaderboard?${params}`);
      setData(r.data);
    } catch (e) {
      toast.error("Yüklenemedi: " + (e.response?.data?.detail || e.message));
    }
    setLoading(false);
  }, [activePropertyId, days]);

  useEffect(() => { load(); }, [load]);

  if (loading && !data) return <div className="text-sm text-stone-400" data-testid="ota-com-loading">Yükleniyor…</div>;
  if (!data) return null;

  const fmt = (n) => (typeof n === "number" ? n.toLocaleString("tr-TR", { maximumFractionDigits: 0 }) : "-");
  const rows = data.leaderboard || [];
  const totals = data.totals || {};
  const maxGross = Math.max(...rows.map(r => r.gross || 0), 1);

  return (
    <div className="space-y-5" data-testid="ota-com-summary">
      {/* Date range chips */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-stone-600">Aralık:</span>
        {[30, 60, 90, 180, 365].map(d => (
          <button key={d} onClick={() => setDays(d)}
            className={`px-3 py-1 text-xs rounded-full border ${
              days === d ? "bg-emerald-600 text-white border-emerald-600" : "bg-white text-stone-600 border-stone-300"
            }`}
            data-testid={`ota-com-days-${d}`}>
            {d} gün
          </button>
        ))}
        <button onClick={load} disabled={loading}
          className="ml-auto px-3 py-1 text-xs rounded-md bg-white border border-stone-300 hover:bg-stone-50 flex items-center gap-1.5">
          <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} /> Yenile
        </button>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="Toplam Gross" value={`£${fmt(totals.gross)}`} icon={DollarSign} color="stone" testId="ota-com-kpi-gross" />
        <Kpi label="Toplam Komisyon" value={`£${fmt(totals.commission)}`} icon={ArrowDownRight} color="rose" testId="ota-com-kpi-commission" />
        <Kpi label="Net Gelir" value={`£${fmt(totals.net)}`} icon={TrendingUp} color="emerald" testId="ota-com-kpi-net" />
        <Kpi label="Blended %" value={`${totals.blended_commission_pct?.toFixed?.(2) ?? "-"}%`} icon={PieChart} color="amber" testId="ota-com-kpi-blended" />
      </div>

      <OtaConversionCard activePropertyId={activePropertyId} days={days} />

      {/* Leaderboard */}
      <div className="border rounded-lg bg-white overflow-hidden" data-testid="ota-com-leaderboard">
        <div className="px-4 py-2.5 bg-stone-50 border-b border-stone-200 text-sm font-semibold text-stone-800">
          🏆 Net Gelir Leaderboard — Son {days} Gün
        </div>
        <table className="w-full text-sm">
          <thead className="bg-stone-50 text-stone-500 uppercase tracking-wider text-[10px]">
            <tr>
              <th className="px-3 py-2 text-left">#</th>
              <th className="px-3 py-2 text-left">Kanal</th>
              <th className="px-3 py-2 text-right">Rezervasyon</th>
              <th className="px-3 py-2 text-right">ADR</th>
              <th className="px-3 py-2 text-right">Komisyon %</th>
              <th className="px-3 py-2 text-right">Gross</th>
              <th className="px-3 py-2 text-right">Komisyon</th>
              <th className="px-3 py-2 text-right">Net</th>
              <th className="px-3 py-2 text-left" style={{ width: "180px" }}>Gross vs Net</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-100">
            {rows.map(r => (
              <tr key={r.channel} data-testid={`ota-com-row-${r.channel}`}>
                <td className="px-3 py-2 font-bold text-stone-800">{r.rank}</td>
                <td className="px-3 py-2 font-medium text-stone-900">{r.label}</td>
                <td className="px-3 py-2 text-right">{fmt(r.bookings)}</td>
                <td className="px-3 py-2 text-right">£{fmt(r.adr)}</td>
                <td className="px-3 py-2 text-right">
                  {r.rate === 0 ? (
                    <span className="text-emerald-600 font-semibold">%0</span>
                  ) : (
                    <span className="text-rose-600">%{(r.rate * 100).toFixed(1)}</span>
                  )}
                </td>
                <td className="px-3 py-2 text-right font-mono">£{fmt(r.gross)}</td>
                <td className="px-3 py-2 text-right font-mono text-rose-700">-£{fmt(r.commission)}</td>
                <td className="px-3 py-2 text-right font-mono font-semibold text-emerald-700">£{fmt(r.net)}</td>
                <td className="px-3 py-2">
                  <div className="relative h-4 bg-stone-100 rounded">
                    <div className="absolute inset-y-0 left-0 bg-emerald-500 rounded" style={{ width: `${(r.net / maxGross) * 100}%` }} title={`Net £${fmt(r.net)}`} />
                    <div className="absolute inset-y-0 bg-rose-400 rounded-r"
                      style={{ left: `${(r.net / maxGross) * 100}%`, width: `${(r.commission / maxGross) * 100}%` }}
                      title={`Komisyon £${fmt(r.commission)}`} />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="px-4 py-2 text-xs text-stone-500 bg-stone-50 border-t flex items-center gap-4">
          <span className="inline-flex items-center gap-1.5"><span className="inline-block w-3 h-3 bg-emerald-500 rounded-sm" /> Net</span>
          <span className="inline-flex items-center gap-1.5"><span className="inline-block w-3 h-3 bg-rose-400 rounded-sm" /> Komisyon</span>
        </div>
      </div>
    </div>
  );
};

const Kpi = ({ label, value, icon: Icon, color, testId }) => {
  const colorMap = {
    stone:   "bg-stone-50 text-stone-900 border-stone-200",
    rose:    "bg-rose-50 text-rose-900 border-rose-200",
    emerald: "bg-emerald-50 text-emerald-900 border-emerald-200",
    amber:   "bg-amber-50 text-amber-900 border-amber-200",
  };
  return (
    <div className={`border rounded-lg p-4 ${colorMap[color] || colorMap.stone}`} data-testid={testId}>
      <div className="text-[10px] uppercase tracking-wider opacity-70 mb-1 flex items-center gap-1">
        <Icon className="w-3 h-3" /> {label}
      </div>
      <div className="text-2xl font-bold">{value}</div>
    </div>
  );
};

/* ═══════════ RATES TAB ═══════════ */
const RatesTab = ({ activePropertyId }) => {
  const [rates, setRates] = useState([]);
  const [editing, setEditing] = useState({});
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (activePropertyId && activePropertyId !== "all") params.set("property_id", activePropertyId);
      const r = await axios.get(`${API}/ota-commission/rates?${params}`);
      setRates(r.data?.items || []);
      setEditing({});
    } catch (e) {
      toast.error("Yüklenemedi");
    }
  }, [activePropertyId]);

  useEffect(() => { load(); }, [load]);

  const save = async (channel) => {
    const val = parseFloat(editing[channel]);
    if (isNaN(val) || val < 0 || val > 0.5) {
      toast.warning("Oran 0-0.5 arasında olmalı (0 = %0, 0.5 = %50)");
      return;
    }
    setSaving(true);
    try {
      await axios.put(`${API}/ota-commission/rates`, {
        channel,
        rate: val,
        property_id: activePropertyId && activePropertyId !== "all" ? activePropertyId : null,
      });
      toast.success(`${channel} oranı %${(val * 100).toFixed(1)} olarak güncellendi`);
      await load();
    } catch (e) {
      toast.error("Kaydedilemedi: " + (e.response?.data?.detail || e.message));
    }
    setSaving(false);
  };

  return (
    <div className="space-y-4" data-testid="ota-com-rates">
      <div className="text-xs text-stone-500 bg-stone-50 border border-stone-200 rounded p-3">
        Her kanal için varsayılan komisyon oranı sektör standartlarıdır. Kendi anlaşmalarınıza göre override edebilirsiniz.
        {activePropertyId && activePropertyId !== "all" && (
          <span className="block mt-1 text-stone-700"><b>Property:</b> {activePropertyId} (property-specific override)</span>
        )}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {rates.map(r => (
          <div key={r.channel} className={`border rounded-lg p-4 bg-white ${r.overridden ? "border-amber-300" : "border-stone-200"}`}
            data-testid={`ota-com-rate-${r.channel}`}>
            <div className="flex justify-between items-start">
              <div>
                <div className="font-semibold text-stone-900">{r.label}</div>
                <div className="text-xs text-stone-500 mt-0.5">Varsayılan: %{(r.default * 100).toFixed(1)}</div>
              </div>
              {r.overridden && (
                <span className="text-[10px] uppercase tracking-wider bg-amber-100 text-amber-800 px-2 py-0.5 rounded font-semibold">Override</span>
              )}
            </div>
            <div className="mt-3 flex items-center gap-2">
              <div className="relative flex-1">
                <input type="number" min="0" max="0.5" step="0.01"
                  value={editing[r.channel] ?? r.rate}
                  onChange={e => setEditing(prev => ({ ...prev, [r.channel]: e.target.value }))}
                  className="w-full pl-3 pr-10 py-1.5 text-sm border border-stone-300 rounded font-mono"
                  data-testid={`ota-com-rate-input-${r.channel}`} />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-stone-500 pointer-events-none">
                  = %{(parseFloat(editing[r.channel] ?? r.rate) * 100).toFixed(1)}
                </span>
              </div>
              <button onClick={() => save(r.channel)} disabled={saving || editing[r.channel] === undefined}
                className="px-3 py-1.5 text-xs rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-40 flex items-center gap-1"
                data-testid={`ota-com-save-${r.channel}`}>
                <Save className="w-3 h-3" /> Kaydet
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
