import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Waveform,
  TrendDown,
  TrendUp,
  Warning,
  Sparkle,
  ArrowsClockwise,
  Lightbulb,
} from "@phosphor-icons/react";
import CopilotButton from "../CopilotButton";

const API = process.env.REACT_APP_BACKEND_URL;

const METRIC_LABELS = {
  revenue: "Gelir",
  bookings: "Yeni Rezervasyon",
  occupancy: "Doluluk",
  adr: "ADR",
  cancellations: "İptal",
};

const SEVERITY_COLORS = {
  severe: "bg-rose-500 text-white border-rose-600",
  moderate: "bg-amber-400 text-stone-900 border-amber-500",
};

export default function AnomalyPanel({ propertyId }) {
  const [tab, setTab] = useState("feed");

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="anomaly-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Waveform size={12} weight="fill" className="text-fuchsia-500" />
          <span>AI · Anomali Dedektörü</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">
          Gelir & Doluluk Anomali Radarı
        </h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          İstatistiksel z-skor analizi + GPT-5.2 kök-neden hipotezi.
          Tepe noktaları ve düşüşleri erken yakala, zaman kaybetme.
        </p>
      </div>

      <div className="flex gap-2 mb-5 border-b border-stone-200">
        <TabBtn active={tab === "feed"} onClick={() => setTab("feed")} testId="anom-tab-feed">
          <Warning size={14} className="inline mr-1.5" />
          Anomali Akışı
        </TabBtn>
        <TabBtn active={tab === "series"} onClick={() => setTab("series")} testId="anom-tab-series">
          <Waveform size={14} className="inline mr-1.5" />
          Zaman Serisi
        </TabBtn>
      </div>

      {tab === "feed" && <FeedTab propertyId={propertyId} />}
      {tab === "series" && <SeriesTab propertyId={propertyId} />}
    </div>
  );
}

function TabBtn({ active, onClick, children, testId }) {
  return (
    <button
      onClick={onClick}
      data-testid={testId}
      className={`px-3.5 py-2 text-sm font-medium transition-all border-b-2 -mb-px ${
        active
          ? "border-fuchsia-500 text-fuchsia-700"
          : "border-transparent text-stone-500 hover:text-stone-800"
      }`}
    >
      {children}
    </button>
  );
}

/* ==================== FEED ==================== */
function FeedTab({ propertyId }) {
  const [days, setDays] = useState(60);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState("all");

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/anomaly/scan/${propertyId}?days=${days}`, { withCredentials: true });
      setData(r.data);
    } catch (e) {
      toast.error("Anomali tarama başarısız");
    } finally {
      setLoading(false);
    }
  }, [propertyId, days]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="text-sm text-stone-400">Taranıyor…</div>;
  if (!data) return null;

  const rows = filter === "all" ? data.anomalies : data.anomalies.filter((a) => a.metric === filter);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="Toplam Anomali" value={data.total} color="fuchsia" testId="anom-kpi-total" />
        <Kpi label="Ciddi" value={data.by_severity.severe || 0} color="rose" testId="anom-kpi-severe" />
        <Kpi label="Orta" value={data.by_severity.moderate || 0} color="amber" testId="anom-kpi-moderate" />
        <Kpi label="Taranan Gün" value={data.days} color="sky" testId="anom-kpi-days" />
      </div>

      <div className="flex justify-end">
        <CopilotButton
          contextType="anomaly"
          data={{ total: data.total, by_severity: data.by_severity, by_metric: data.by_metric, top_anomalies: (data.anomalies || []).slice(0, 5) }}
          label="AI Özet: Anomali Paterni"
          testId="anom-copilot-btn"
          propertyId={propertyId}
        />
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex gap-1">
          {[30, 60, 90, 180].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              data-testid={`anom-days-${d}`}
              className={`px-2.5 py-1 text-xs rounded-full border transition-all ${
                days === d ? "bg-fuchsia-500 text-white border-fuchsia-500" : "bg-white text-stone-600 border-stone-200 hover:border-stone-400"
              }`}
            >
              {d} gün
            </button>
          ))}
        </div>
        <div className="ml-auto flex gap-1">
          {["all", ...Object.keys(METRIC_LABELS)].map((m) => (
            <button
              key={m}
              onClick={() => setFilter(m)}
              data-testid={`anom-filter-${m}`}
              className={`px-2 py-1 text-[11px] rounded border transition-all ${
                filter === m ? "bg-stone-900 text-white border-stone-900" : "bg-white text-stone-600 border-stone-200 hover:border-stone-400"
              }`}
            >
              {m === "all" ? "Tümü" : METRIC_LABELS[m]}
              {m !== "all" && data.by_metric[m] ? <span className="ml-1 opacity-70">({data.by_metric[m]})</span> : null}
            </button>
          ))}
        </div>
        <button onClick={load} data-testid="anom-refresh" className="px-3 py-1 text-xs rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50 inline-flex items-center gap-1.5">
          <ArrowsClockwise size={12} /> Yenile
        </button>
      </div>

      {rows.length === 0 && (
        <div className="text-center py-12 text-stone-400 text-sm border border-dashed border-stone-200 rounded-lg">
          <Sparkle size={24} className="mx-auto mb-2 opacity-40" />
          {data.total === 0 ? "Bu aralıkta anomali tespit edilmedi. Her şey normal." : "Bu filtrede sonuç yok."}
        </div>
      )}

      <div className="space-y-2" data-testid="anom-feed-list">
        {rows.map((a, i) => (
          <AnomalyRow key={`${a.date}-${a.metric}-${i}`} anomaly={a} propertyId={propertyId} />
        ))}
      </div>
    </div>
  );
}

function Kpi({ label, value, color, testId }) {
  const bg = {
    fuchsia: "bg-fuchsia-50 text-fuchsia-700",
    rose: "bg-rose-50 text-rose-700",
    amber: "bg-amber-50 text-amber-700",
    sky: "bg-sky-50 text-sky-700",
    emerald: "bg-emerald-50 text-emerald-700",
  }[color];
  return (
    <div className={`${bg} border border-stone-100 rounded-lg p-3.5`} data-testid={testId}>
      <div className="text-[10px] uppercase tracking-wider opacity-70">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
    </div>
  );
}

function AnomalyRow({ anomaly, propertyId }) {
  const [expl, setExpl] = useState(null);
  const [busy, setBusy] = useState(false);
  const dir = anomaly.direction;
  const Icon = dir === "spike" ? TrendUp : TrendDown;
  const colorCls = SEVERITY_COLORS[anomaly.severity] || "bg-stone-100 text-stone-700";

  const explain = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/anomaly/explain`, {
        property_id: propertyId,
        date: anomaly.date,
        metric: anomaly.metric,
        value: anomaly.value,
        z: anomaly.z,
      }, { withCredentials: true });
      setExpl(r.data);
    } catch (e) {
      toast.error("Açıklama başarısız");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-white border border-stone-200 rounded-lg p-3.5" data-testid={`anom-row-${anomaly.date}-${anomaly.metric}`}>
      <div className="flex items-start gap-3">
        <div className={`w-9 h-9 rounded-md inline-flex items-center justify-center flex-shrink-0 ${
          dir === "spike" ? "bg-emerald-50 text-emerald-600" : "bg-rose-50 text-rose-600"
        }`}>
          <Icon size={16} weight="bold" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className={`px-1.5 py-0.5 text-[10px] rounded border font-medium uppercase ${colorCls}`}>
              {anomaly.severity}
            </span>
            <span className="text-[11px] font-semibold text-stone-700">{METRIC_LABELS[anomaly.metric] || anomaly.metric}</span>
            <span className="text-[11px] text-stone-400">· {anomaly.date}</span>
            <span className="text-[11px] text-stone-500">z = {anomaly.z}</span>
          </div>
          <div className="text-sm text-stone-800">
            Değer <b>{anomaly.value}</b> · beklenen ~<span className="text-stone-500">{anomaly.mean}</span> (±{anomaly.std})
            · yön <b className={dir === "spike" ? "text-emerald-600" : "text-rose-600"}>{dir === "spike" ? "↑ tepe" : "↓ düşüş"}</b>
          </div>
          {expl && (
            <div className="mt-2 bg-violet-50 border border-violet-100 rounded-md p-2.5" data-testid={`anom-expl-${anomaly.date}-${anomaly.metric}`}>
              <div className="text-[10px] uppercase tracking-wider text-violet-600 mb-1 flex items-center gap-1">
                <Lightbulb size={11} weight="fill" />
                {expl.source === "llm" ? "AI Kök-neden (GPT-5.2)" : "Sezgisel hipotez"}
              </div>
              <div className="text-xs text-stone-700 leading-relaxed">{expl.hypothesis}</div>
              {expl.actions?.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {expl.actions.map((a, i) => (
                    <span key={i} className="px-1.5 py-0.5 text-[10px] bg-white border border-violet-200 rounded text-violet-700">{a}</span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
        {!expl && (
          <button
            onClick={explain}
            disabled={busy}
            data-testid={`anom-explain-${anomaly.date}-${anomaly.metric}`}
            className="px-2.5 py-1.5 text-[11px] rounded-md bg-violet-500 text-white hover:bg-violet-600 inline-flex items-center gap-1 disabled:opacity-50 flex-shrink-0"
          >
            <Sparkle size={11} weight="fill" />
            {busy ? "…" : "Açıkla"}
          </button>
        )}
      </div>
    </div>
  );
}

/* ==================== TIME SERIES ==================== */
function SeriesTab({ propertyId }) {
  const [metric, setMetric] = useState("revenue");
  const [days, setDays] = useState(90);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/anomaly/timeseries/${propertyId}?metric=${metric}&days=${days}`, { withCredentials: true });
      setData(r.data);
    } catch (e) {
      toast.error("Zaman serisi yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId, metric, days]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex gap-1">
          {Object.entries(METRIC_LABELS).map(([k, l]) => (
            <button
              key={k}
              onClick={() => setMetric(k)}
              data-testid={`anom-series-metric-${k}`}
              className={`px-2.5 py-1 text-xs rounded-full border transition-all ${
                metric === k ? "bg-fuchsia-500 text-white border-fuchsia-500" : "bg-white text-stone-600 border-stone-200 hover:border-stone-400"
              }`}
            >
              {l}
            </button>
          ))}
        </div>
        <div className="flex gap-1 ml-auto">
          {[30, 60, 90, 180].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              data-testid={`anom-series-days-${d}`}
              className={`px-2.5 py-1 text-xs rounded-full border transition-all ${
                days === d ? "bg-stone-900 text-white border-stone-900" : "bg-white text-stone-600 border-stone-200 hover:border-stone-400"
              }`}
            >
              {d} gün
            </button>
          ))}
        </div>
      </div>

      {loading && <div className="text-sm text-stone-400">Yükleniyor…</div>}

      {data && (
        <>
          <div className="grid grid-cols-3 gap-3">
            <Kpi label={`Ort. ${METRIC_LABELS[metric]}`} value={data.mean} color="sky" testId="anom-series-kpi-mean" />
            <Kpi label="Std Sapma" value={data.std} color="amber" testId="anom-series-kpi-std" />
            <Kpi label="Anomali Sayısı" value={data.anomaly_count} color="rose" testId="anom-series-kpi-count" />
          </div>

          <TimeSeriesChart points={data.points} mean={data.mean} std={data.std} metric={metric} />
        </>
      )}
    </div>
  );
}

function TimeSeriesChart({ points, mean, std, metric }) {
  const width = 900;
  const height = 220;
  const pad = 30;

  const vals = points.map((p) => p.value);
  const maxV = Math.max(...vals, mean + 2 * std, 1);
  const minV = Math.min(...vals, mean - 2 * std, 0);
  const range = Math.max(maxV - minV, 1);
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;

  const xOf = (i) => pad + (i / Math.max(points.length - 1, 1)) * innerW;
  const yOf = (v) => pad + innerH - ((v - minV) / range) * innerH;

  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"} ${xOf(i)},${yOf(p.value)}`).join(" ");
  const meanY = yOf(mean);
  const upperY = yOf(mean + 2 * std);
  const lowerY = yOf(mean - 2 * std);

  return (
    <div className="bg-white border border-stone-200 rounded-lg p-4" data-testid="anom-timeseries-chart">
      <div className="text-xs text-stone-500 mb-2">
        Mor bant: ±2σ normal aralık. Noktalar bant dışına çıkınca anomali.
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full">
        {/* Normal band */}
        <rect x={pad} y={upperY} width={innerW} height={lowerY - upperY} fill="#f5f3ff" />
        {/* Mean line */}
        <line x1={pad} y1={meanY} x2={width - pad} y2={meanY} stroke="#a78bfa" strokeDasharray="3 3" strokeWidth="1" />
        {/* Series path */}
        <path d={linePath} fill="none" stroke="#7c3aed" strokeWidth="1.5" opacity="0.7" />
        {/* Points */}
        {points.map((p, i) => {
          if (p.is_anomaly) {
            const color = p.severity === "severe" ? "#e11d48" : "#f59e0b";
            return (
              <g key={p.date}>
                <circle cx={xOf(i)} cy={yOf(p.value)} r="5" fill={color} stroke="white" strokeWidth="1.5" />
                <title>{p.date} · {p.value} · z={p.z} · {p.severity}</title>
              </g>
            );
          }
          return <circle key={p.date} cx={xOf(i)} cy={yOf(p.value)} r="2" fill="#7c3aed" opacity="0.5" />;
        })}
        {/* Axes labels */}
        <text x={pad} y={pad - 8} fontSize="9" fill="#78716c">{Math.round(maxV)}</text>
        <text x={pad} y={height - 5} fontSize="9" fill="#78716c">{Math.round(minV)}</text>
        <text x={pad} y={meanY - 3} fontSize="9" fill="#7c3aed">μ={mean}</text>
      </svg>
      <div className="flex items-center gap-4 text-xs text-stone-600 mt-2">
        <span className="inline-flex items-center gap-1.5"><span className="inline-block w-2 h-2 rounded-full bg-violet-500 opacity-50" /> Normal</span>
        <span className="inline-flex items-center gap-1.5"><span className="inline-block w-2 h-2 rounded-full bg-amber-500" /> Orta anomali</span>
        <span className="inline-flex items-center gap-1.5"><span className="inline-block w-2 h-2 rounded-full bg-rose-600" /> Ciddi anomali</span>
      </div>
    </div>
  );
}
