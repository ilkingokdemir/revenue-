import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ChartLineUp,
  ThumbsUp,
  ThumbsDown,
  ArrowsClockwise,
  Warning,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

/**
 * SentimentHeatmapPanel — Cross-channel sentiment visualization.
 *
 * One-screen: Hero NPS-like + channel bars + topic × sentiment heatmap grid
 * + trend sparkline + Top Complaints/Praises with clickable drilldown.
 */
export default function SentimentHeatmapPanel({ propertyId, hotelName }) {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [drill, setDrill] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(
        `${API}/api/sentiment/heatmap/${propertyId}?days=${days}`
      );
      setData(data);
    } catch (_) { toast.error("Sentiment verisi yüklenemedi"); }
    setLoading(false);
  }, [propertyId, days]);

  useEffect(() => { load(); }, [load]);

  const openDrilldown = async (topic, band) => {
    try {
      const { data } = await axios.get(
        `${API}/api/sentiment/drilldown/${propertyId}?topic=${encodeURIComponent(topic)}&days=${days}${band ? `&band=${band}` : ""}`
      );
      setDrill(data);
    } catch (_) { toast.error("Drilldown yüklenemedi"); }
  };

  const scoreColor = (band) => ({
    positive: "emerald",
    neutral: "stone",
    negative: "rose",
  }[band] || "stone");

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="sentiment-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <ChartLineUp size={12} weight="fill" className="text-pink-500" />
          <span>Cross-Channel Intelligence</span>
        </div>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-stone-900">
              Misafir Sesi Haritası · {hotelName || "Property"}
            </h1>
            <p className="text-sm text-stone-500 mt-1 max-w-2xl">
              Yorumlar + Mesajlar + Anketler — 10 konu × 3 duygu + trend. Tek ekranda ne işe yarıyor, ne iyileşmeli.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="px-2 py-1.5 rounded border border-stone-300 text-sm"
              data-testid="sentiment-days"
            >
              <option value={7}>7 gün</option>
              <option value={30}>30 gün</option>
              <option value={90}>90 gün</option>
            </select>
            <button onClick={load} disabled={loading}
              className="p-2 text-stone-500 hover:text-stone-800"
              data-testid="sentiment-reload">
              <ArrowsClockwise size={14} className={loading ? "animate-spin" : ""} />
            </button>
          </div>
        </div>
      </div>

      {!data && loading && <div className="text-sm text-stone-500">Yükleniyor…</div>}
      {!data && !loading && <div className="text-sm text-stone-500">Veri yok.</div>}

      {data && (
        <>
          {/* HERO — Overall sentiment */}
          <div className={`p-5 rounded-2xl mb-5 bg-gradient-to-br from-${scoreColor(data.overall_band)}-50 to-transparent border border-${scoreColor(data.overall_band)}-200`}>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
              <div>
                <div className="text-[10px] uppercase tracking-wider text-stone-500">Genel skor</div>
                <div className={`text-3xl font-bold text-${scoreColor(data.overall_band)}-700`}>
                  {data.overall_avg > 0 ? "+" : ""}{data.overall_avg}
                </div>
                <div className="text-[10px] text-stone-500 capitalize">{data.overall_band}</div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wider text-stone-500">NPS-benzeri</div>
                <div className={`text-3xl font-bold ${data.nps_like >= 0 ? "text-emerald-700" : "text-rose-700"}`}>
                  {data.nps_like > 0 ? "+" : ""}{data.nps_like}
                </div>
                <div className="text-[10px] text-stone-500">(%pozitif − %negatif)</div>
              </div>
              <Tile label="Pozitif" value={data.positive_count} accent="emerald" />
              <Tile label="Nötr" value={data.neutral_count} />
              <Tile label="Negatif" value={data.negative_count} accent="rose" />
            </div>
            <div className="mt-3 text-xs text-stone-600">
              {data.total_responses} yanıt · son {data.window_days} gün
            </div>
          </div>

          {/* By Channel */}
          <div className="p-4 rounded-xl bg-white border border-stone-200 mb-5">
            <h3 className="text-sm font-semibold text-stone-900 mb-3">Kanal Bazında</h3>
            {Object.keys(data.by_channel).length === 0 ? (
              <div className="text-xs text-stone-500">Veri yok</div>
            ) : (
              <div className="space-y-2">
                {Object.entries(data.by_channel)
                  .sort((a, b) => b[1].count - a[1].count)
                  .map(([ch, d]) => {
                    const bar = (d.pos + d.neu + d.neg) || 1;
                    return (
                      <div key={ch} className="flex items-center gap-3" data-testid={`sentiment-channel-${ch}`}>
                        <div className="w-40 text-xs font-medium text-stone-900 truncate">{ch}</div>
                        <div className="flex-1 h-6 rounded-lg overflow-hidden bg-stone-100 flex">
                          <div className="bg-emerald-400" style={{ width: `${(d.pos / bar) * 100}%` }}
                            title={`${d.pos} pozitif`} />
                          <div className="bg-stone-300" style={{ width: `${(d.neu / bar) * 100}%` }}
                            title={`${d.neu} nötr`} />
                          <div className="bg-rose-400" style={{ width: `${(d.neg / bar) * 100}%` }}
                            title={`${d.neg} negatif`} />
                        </div>
                        <div className="w-14 text-right text-xs text-stone-700 font-mono">
                          {d.avg > 0 ? "+" : ""}{d.avg}
                        </div>
                        <div className="w-10 text-right text-[10px] text-stone-500">{d.count}</div>
                      </div>
                    );
                  })}
              </div>
            )}
          </div>

          {/* Topic Heatmap */}
          <div className="p-4 rounded-xl bg-white border border-stone-200 mb-5">
            <h3 className="text-sm font-semibold text-stone-900 mb-3">Konu × Duygu Isı Haritası</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[10px] uppercase tracking-wider text-stone-500">
                    <th className="text-left pb-2 font-medium">Konu</th>
                    <th className="pb-2 font-medium w-20">Pozitif</th>
                    <th className="pb-2 font-medium w-20">Nötr</th>
                    <th className="pb-2 font-medium w-20">Negatif</th>
                    <th className="pb-2 font-medium w-16">Toplam</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data.topic_matrix).sort((a, b) => b[1].total - a[1].total).map(([topic, cells]) => {
                    const total = cells.total || 1;
                    const pp = Math.round((cells.positive / total) * 100);
                    const nn = Math.round((cells.negative / total) * 100);
                    return (
                      <tr key={topic} className="border-t border-stone-100 hover:bg-stone-50"
                        data-testid={`topic-row-${topic.split(" ")[0]}`}>
                        <td className="py-2 pr-2 text-stone-900">{topic}</td>
                        <td className="py-2">
                          <button onClick={() => openDrilldown(topic, "positive")}
                            className={`w-full py-1 rounded text-xs font-mono ${cells.positive > 0 ? "bg-emerald-100 text-emerald-700 hover:bg-emerald-200" : "bg-stone-50 text-stone-400"}`}>
                            {cells.positive} · {pp}%
                          </button>
                        </td>
                        <td className="py-2">
                          <button onClick={() => openDrilldown(topic, "neutral")}
                            className={`w-full py-1 rounded text-xs font-mono ${cells.neutral > 0 ? "bg-stone-100 text-stone-700 hover:bg-stone-200" : "bg-stone-50 text-stone-400"}`}>
                            {cells.neutral}
                          </button>
                        </td>
                        <td className="py-2">
                          <button onClick={() => openDrilldown(topic, "negative")}
                            className={`w-full py-1 rounded text-xs font-mono ${cells.negative > 0 ? "bg-rose-100 text-rose-700 hover:bg-rose-200" : "bg-stone-50 text-stone-400"}`}>
                            {cells.negative} · {nn}%
                          </button>
                        </td>
                        <td className="py-2 text-right text-stone-700 font-mono">{cells.total}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {Object.keys(data.topic_matrix).length === 0 && (
                <div className="text-xs text-stone-500 text-center py-4">Konu çıkarılamadı</div>
              )}
            </div>
          </div>

          {/* Praises + Complaints */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-5">
            <TopList
              items={data.top_praises}
              icon={ThumbsUp}
              label="Övgü"
              tone="emerald"
              testId="top-praises"
            />
            <TopList
              items={data.top_complaints}
              icon={ThumbsDown}
              label="Şikayet"
              tone="rose"
              testId="top-complaints"
            />
          </div>

          {/* Trend */}
          {data.trend?.length > 0 && (
            <div className="p-4 rounded-xl bg-white border border-stone-200">
              <h3 className="text-sm font-semibold text-stone-900 mb-3">Günlük Trend</h3>
              <div className="flex items-end gap-1 h-24">
                {data.trend.map((d) => {
                  const h = Math.max(8, Math.abs(d.avg) * 12);
                  const color = d.avg >= 0 ? "bg-emerald-400" : "bg-rose-400";
                  return (
                    <div key={d.date} className="flex-1 flex flex-col items-center gap-0.5" title={`${d.date}: ${d.avg} (${d.count})`}>
                      <div className={`w-full ${color} rounded-t`} style={{ height: `${h}px` }} />
                      <div className="text-[8px] text-stone-400">{d.date.slice(5)}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}

      {/* Drilldown modal */}
      {drill && (
        <DrilldownModal drill={drill} onClose={() => setDrill(null)} />
      )}
    </div>
  );
}

function TopList({ items, icon: Icon, label, tone, testId }) {
  return (
    <div className="p-4 rounded-xl bg-white border border-stone-200" data-testid={testId}>
      <h3 className={`text-sm font-semibold text-stone-900 mb-3 flex items-center gap-2`}>
        <Icon size={16} className={`text-${tone}-500`} weight="fill" />
        Top {label}
      </h3>
      {items.length === 0 ? (
        <div className="text-xs text-stone-500 py-4 text-center">Yok.</div>
      ) : (
        <div className="space-y-2">
          {items.slice(0, 5).map((it, i) => (
            <div key={i} className={`p-2 rounded-lg bg-${tone}-50 border border-${tone}-100 text-xs`}>
              <div className="flex items-center gap-2 mb-1">
                <span className={`font-mono font-bold text-${tone}-700`}>
                  {it.score > 0 ? "+" : ""}{it.score}
                </span>
                <span className="text-stone-500">{it.channel}</span>
                {it.author && <span className="text-stone-500">· {it.author}</span>}
              </div>
              <div className="text-stone-800">{it.text}</div>
              {it.topics?.length > 0 && (
                <div className="flex gap-1 mt-1 flex-wrap">
                  {it.topics.map((t, j) => (
                    <span key={j} className={`px-1.5 py-0.5 rounded bg-${tone}-100 text-${tone}-700 text-[10px]`}>
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DrilldownModal({ drill, onClose }) {
  return (
    <div className="fixed inset-0 bg-black/30 z-40 flex items-center justify-center p-4"
      onClick={onClose} data-testid="sentiment-drill">
      <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}>
        <div className="p-5 border-b border-stone-200">
          <h3 className="text-lg font-bold text-stone-900">
            {drill.topic}
            {drill.band_filter && (
              <span className={`ml-2 text-sm px-2 py-0.5 rounded-full ${
                drill.band_filter === "positive" ? "bg-emerald-100 text-emerald-700" :
                drill.band_filter === "negative" ? "bg-rose-100 text-rose-700" :
                "bg-stone-100 text-stone-700"
              }`}>
                {drill.band_filter}
              </span>
            )}
          </h3>
          <div className="text-xs text-stone-500 mt-1">{drill.count} yanıt</div>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {drill.rows.map((r, i) => (
            <div key={i} className={`p-3 rounded-lg border ${
              r.band === "positive" ? "bg-emerald-50 border-emerald-100" :
              r.band === "negative" ? "bg-rose-50 border-rose-100" :
              "bg-stone-50 border-stone-100"
            } text-sm`}>
              <div className="flex items-center gap-2 mb-1 text-xs">
                <span className="font-mono font-bold">{r.score > 0 ? "+" : ""}{r.score}</span>
                <span className="text-stone-500">{r.channel}</span>
                {r.author && <span className="text-stone-500">· {r.author}</span>}
                <span className="text-stone-400 ml-auto">{r.created_at?.slice(0, 10)}</span>
              </div>
              <div className="text-stone-800">{r.text}</div>
            </div>
          ))}
          {drill.rows.length === 0 && <div className="text-xs text-stone-500 text-center py-4">Eşleşme yok.</div>}
        </div>
        <div className="p-3 border-t border-stone-200 flex justify-end">
          <button onClick={onClose} className="px-3 py-1.5 bg-stone-100 text-stone-700 rounded-lg text-sm hover:bg-stone-200">
            Kapat
          </button>
        </div>
      </div>
    </div>
  );
}

function Tile({ label, value, accent }) {
  const m = { emerald: "text-emerald-700", rose: "text-rose-600" };
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-stone-500">{label}</div>
      <div className={`text-2xl font-bold ${accent ? m[accent] : "text-stone-900"}`}>{value}</div>
    </div>
  );
}
