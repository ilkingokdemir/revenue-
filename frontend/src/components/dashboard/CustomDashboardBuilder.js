/**
 * CustomDashboardBuilder (iter 369) — Mews parity
 * ------------------------------------------------
 * Users pick from a widget catalog and assemble their own dashboard.
 * Widgets render live data from `/api/dashboards/widget-data/*`.
 * Layout persists in DB via PUT `/api/dashboards/{id}`.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  LayoutDashboard, Plus, Trash2, Loader2, RefreshCw,
  Percent, DollarSign, TrendingUp, Bell, Zap, Sparkles,
  ArrowUp, ArrowDown, Minus,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function CustomDashboardBuilder({ propertyId }) {
  const [dashboards, setDashboards] = useState([]);
  const [activeDash, setActiveDash] = useState(null);
  const [catalog, setCatalog] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddWidget, setShowAddWidget] = useState(false);

  const loadDashboards = useCallback(async () => {
    setLoading(true);
    try {
      const [d, c] = await Promise.all([
        axios.get(`${API}/dashboards/mine`),
        axios.get(`${API}/dashboards/widget-catalog`),
      ]);
      setDashboards(d.data.items || []);
      setCatalog(c.data.items || []);
      if (!activeDash && (d.data.items || []).length > 0) {
        loadDash(d.data.items[0].id);
      }
    } catch { toast.error("Yüklenemedi"); }
    setLoading(false);
  }, [activeDash]);   // eslint-disable-line react-hooks/exhaustive-deps

  const loadDash = async (id) => {
    try {
      const r = await axios.get(`${API}/dashboards/${id}`);
      setActiveDash(r.data);
    } catch { toast.error("Dashboard açılamadı"); }
  };

  useEffect(() => { loadDashboards(); /* eslint-disable-line */ }, []);

  const createDash = async () => {
    const name = window.prompt("Yeni dashboard adı:", "Benim Dashboardum");
    if (!name) return;
    try {
      const r = await axios.post(`${API}/dashboards`, { name, property_id: propertyId });
      toast.success("Oluşturuldu");
      setDashboards([r.data, ...dashboards]);
      loadDash(r.data.id);
    } catch (e) { toast.error(e?.response?.data?.detail || "Başarısız"); }
  };

  const deleteDash = async (id) => {
    if (!window.confirm("Dashboard silinsin mi?")) return;
    try {
      await axios.delete(`${API}/dashboards/${id}`);
      toast.success("Silindi");
      setActiveDash(null);
      loadDashboards();
    } catch { toast.error("Silinemedi"); }
  };

  const addWidget = async (type) => {
    try {
      await axios.post(`${API}/dashboards/${activeDash.id}/widgets`, { type });
      toast.success("Widget eklendi");
      loadDash(activeDash.id);
      setShowAddWidget(false);
    } catch (e) { toast.error(e?.response?.data?.detail || "Ekleme başarısız"); }
  };

  const removeWidget = async (widgetId) => {
    try {
      await axios.delete(`${API}/dashboards/${activeDash.id}/widgets/${widgetId}`);
      toast.success("Kaldırıldı");
      loadDash(activeDash.id);
    } catch { toast.error("Kaldırılamadı"); }
  };

  return (
    <div className="space-y-4" data-testid="custom-dashboard-builder">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl bg-fuchsia-500/20">
            <LayoutDashboard className="w-6 h-6 text-fuchsia-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-stone-100">Custom Dashboards</h2>
            <p className="text-sm text-stone-400">Kendi widget'larından oluşan panelini kur — istediğini ekle, sil, düzenle.</p>
          </div>
        </div>
        <button
          onClick={createDash}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-fuchsia-600 hover:bg-fuchsia-700 text-white text-sm font-bold"
          data-testid="dash-create-btn"
        >
          <Plus className="w-4 h-4" /> Yeni Dashboard
        </button>
      </div>

      {/* Dashboard tabs */}
      {dashboards.length > 0 && (
        <div className="flex gap-1 flex-wrap" data-testid="dash-tabs">
          {dashboards.map((d) => (
            <button
              key={d.id}
              onClick={() => loadDash(d.id)}
              data-testid={`dash-tab-${d.id}`}
              className={`px-3 py-1.5 rounded-lg text-sm ${
                activeDash?.id === d.id
                  ? "bg-fuchsia-500/20 border border-fuchsia-500/40 text-fuchsia-100"
                  : "bg-stone-800/60 border border-stone-800 text-stone-400 hover:text-stone-200"
              }`}
            >
              {d.name}
              {d.shared && <span className="ml-1 text-[10px] text-emerald-400">·paylaşımlı</span>}
            </button>
          ))}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16 text-stone-500"><Loader2 className="w-6 h-6 animate-spin" /></div>
      ) : !activeDash ? (
        <div className="text-center py-16 border border-dashed border-stone-700 rounded-2xl">
          <LayoutDashboard className="w-14 h-14 text-stone-700 mx-auto mb-3" />
          <p className="text-stone-300 font-medium mb-3">Henüz dashboard yok</p>
          <button
            onClick={createDash}
            className="px-4 py-2 rounded-lg bg-fuchsia-600 hover:bg-fuchsia-700 text-white text-sm font-bold"
            data-testid="dash-empty-create-btn"
          >
            İlk Dashboard'unu Oluştur
          </button>
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between mt-2">
            <div className="text-xs text-stone-500">{activeDash.widgets?.length || 0} widget · son güncelleme {new Date(activeDash.updated_at).toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" })}</div>
            <div className="flex gap-2">
              <button
                onClick={() => setShowAddWidget(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-fuchsia-500/20 hover:bg-fuchsia-500/30 border border-fuchsia-500/40 text-fuchsia-100 text-xs font-bold"
                data-testid="add-widget-btn"
              >
                <Plus className="w-3.5 h-3.5" /> Widget Ekle
              </button>
              <button
                onClick={() => loadDash(activeDash.id)}
                className="p-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-300"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
              <button
                onClick={() => deleteDash(activeDash.id)}
                className="p-1.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-300"
                data-testid="dash-delete-btn"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>

          {showAddWidget && (
            <div className="rounded-xl border border-fuchsia-500/40 bg-fuchsia-500/5 p-4" data-testid="widget-catalog">
              <div className="text-sm font-bold text-fuchsia-200 mb-3">Katalog</div>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
                {catalog.map((c) => (
                  <button
                    key={c.type}
                    onClick={() => addWidget(c.type)}
                    data-testid={`catalog-${c.type}`}
                    className="text-left p-3 rounded-lg bg-stone-900/60 hover:bg-stone-900 border border-stone-700 hover:border-fuchsia-500/40"
                  >
                    <div className="text-[10px] uppercase text-stone-500">{c.category}</div>
                    <div className="text-sm font-semibold text-stone-100">{c.label}</div>
                  </button>
                ))}
              </div>
              <button
                onClick={() => setShowAddWidget(false)}
                className="mt-3 text-xs text-stone-400 hover:text-stone-200"
              >
                × Kapat
              </button>
            </div>
          )}

          {/* Widget grid */}
          {activeDash.widgets?.length === 0 ? (
            <div className="text-center py-16 border border-dashed border-stone-700 rounded-2xl" data-testid="dash-empty-widgets">
              <Sparkles className="w-10 h-10 text-stone-600 mx-auto mb-2" />
              <p className="text-stone-400 text-sm mb-3">Henüz widget eklenmemiş</p>
              <button
                onClick={() => setShowAddWidget(true)}
                className="px-3 py-1.5 rounded-lg bg-fuchsia-600 hover:bg-fuchsia-700 text-white text-xs font-bold"
              >
                İlk Widget'ını Ekle
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-12 gap-3 auto-rows-[70px]" data-testid="dash-widgets">
              {activeDash.widgets.map((w) => (
                <WidgetHost
                  key={w.id}
                  widget={w}
                  propertyId={propertyId}
                  onRemove={() => removeWidget(w.id)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
// Widget host — fetches data and renders appropriate visual
// ────────────────────────────────────────────────────────────────
function WidgetHost({ widget, propertyId, onRemove }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const url = `${API}/dashboards/widget-data/${widget.type}` +
                (propertyId && propertyId !== "all" ? `?property_id=${propertyId}` : "");
    axios.get(url)
      .then((r) => !cancelled && setData(r.data))
      .catch(() => !cancelled && setData({ error: true }))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [widget.type, propertyId]);

  const style = {
    gridColumn:  `span ${Math.min(12, widget.w || 3)} / span ${Math.min(12, widget.w || 3)}`,
    gridRow:     `span ${widget.h || 2} / span ${widget.h || 2}`,
  };

  return (
    <div
      style={style}
      data-testid={`widget-${widget.type}`}
      className="relative rounded-xl border border-stone-800 bg-stone-900/60 p-4 group hover:border-fuchsia-500/40"
    >
      <button
        onClick={onRemove}
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 p-1 rounded bg-stone-800 hover:bg-rose-600 text-stone-400 hover:text-white transition"
        data-testid={`widget-remove-${widget.id}`}
      >
        <Trash2 className="w-3 h-3" />
      </button>
      {loading ? (
        <div className="h-full flex items-center justify-center"><Loader2 className="w-4 h-4 animate-spin text-stone-500" /></div>
      ) : data?.error ? (
        <div className="text-stone-500 text-xs">Veri alınamadı</div>
      ) : (
        <WidgetContent type={widget.type} data={data} />
      )}
    </div>
  );
}

function WidgetContent({ type, data }) {
  if (type.startsWith("kpi_")) return <KpiCard data={data} type={type} />;
  if (type === "spark_revenue") return <SparkRevenue data={data} />;
  if (type === "hk_summary") return <HkSummary data={data} />;
  if (type === "alerts_board") return <AlertsBoard data={data} />;
  if (type === "quick_actions") return <QuickActions data={data} />;
  return <pre className="text-xs text-stone-500">{JSON.stringify(data, null, 2)}</pre>;
}

function KpiCard({ data, type }) {
  const iconMap = {
    kpi_occupancy: Percent, kpi_adr: DollarSign, kpi_revpar: TrendingUp,
    kpi_pace: Zap, kpi_pickup: TrendingUp, kpi_roas: TrendingUp,
  };
  const Icon = iconMap[type] || TrendingUp;
  const delta = data.delta_pct;
  const DeltaIcon = delta == null ? Minus : delta > 0 ? ArrowUp : delta < 0 ? ArrowDown : Minus;
  const deltaColor = delta == null ? "text-stone-500" : delta > 0 ? "text-emerald-400" : delta < 0 ? "text-rose-400" : "text-stone-500";
  const val = data.value ?? "—";
  const fmt = data.unit === "%" ? `${val}%` : data.unit === "x" ? `${val || "—"}x` : data.unit === "GBP" ? `£${val}` : val;
  return (
    <div className="h-full flex flex-col justify-between">
      <div className="flex items-center justify-between">
        <div className="text-[10px] uppercase tracking-wider text-stone-500">{data.label || type}</div>
        <Icon className="w-4 h-4 text-fuchsia-400" />
      </div>
      <div className="text-3xl font-black text-stone-100">{fmt}</div>
      {delta != null && (
        <div className={`text-xs flex items-center gap-1 ${deltaColor}`}>
          <DeltaIcon className="w-3 h-3" /> {Math.abs(delta)}% dün
        </div>
      )}
    </div>
  );
}

function SparkRevenue({ data }) {
  const series = data.series || [];
  const max = Math.max(1, ...series.map((s) => Number(s.revenue) || 0));
  return (
    <div className="h-full flex flex-col">
      <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-1">Son 7 Gün Gelir</div>
      <div className="flex-1 flex items-end gap-1 min-h-[40px]">
        {series.map((s) => (
          <div
            key={s.date}
            className="flex-1 bg-gradient-to-t from-fuchsia-500 to-fuchsia-400 rounded-t"
            style={{ height: `${(Number(s.revenue) || 0) / max * 100}%` }}
            title={`${s.date}: £${Number(s.revenue).toFixed(0)}`}
          />
        ))}
      </div>
      <div className="flex justify-between text-[9px] text-stone-500 mt-1">
        <span>{series[0]?.date?.slice(5)}</span>
        <span>{series[series.length - 1]?.date?.slice(5)}</span>
      </div>
    </div>
  );
}

function HkSummary({ data }) {
  const counts = data.counts || {};
  const total = data.total_rooms || Object.values(counts).reduce((a, b) => a + b, 0);
  const CLS = { clean: "bg-emerald-500", dirty: "bg-amber-500", inspected: "bg-sky-500", oo: "bg-rose-500" };
  return (
    <div className="h-full flex flex-col">
      <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-2">Housekeeping · {total} oda</div>
      <div className="space-y-1.5 text-xs">
        {Object.entries(counts).map(([status, count]) => (
          <div key={status} className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${CLS[status] || "bg-stone-500"}`} />
            <span className="capitalize text-stone-300 flex-1">{status}</span>
            <span className="font-bold text-stone-100">{count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function AlertsBoard({ data }) {
  const items = data.items || [];
  return (
    <div className="h-full flex flex-col">
      <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-2 flex items-center gap-1">
        <Bell className="w-3 h-3" /> Aktif Uyarılar
      </div>
      {items.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-stone-500 text-xs">Uyarı yok ✓</div>
      ) : (
        <div className="space-y-1 flex-1 overflow-y-auto">
          {items.map((a, i) => (
            <div key={i} className="text-xs p-2 rounded bg-rose-500/10 border border-rose-500/30 text-rose-200">
              {a.title || a.message || "Uyarı"}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function QuickActions({ data }) {
  const items = data.items || [];
  return (
    <div className="h-full flex flex-col">
      <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-2 flex items-center gap-1">
        <Zap className="w-3 h-3" /> Hızlı Aksiyonlar
      </div>
      <div className="grid grid-cols-2 gap-1.5 flex-1">
        {items.map((a) => (
          <button
            key={a.key}
            className="p-2 rounded bg-stone-800 hover:bg-stone-700 text-stone-200 text-xs font-medium text-left"
          >
            {a.label}
          </button>
        ))}
      </div>
    </div>
  );
}
