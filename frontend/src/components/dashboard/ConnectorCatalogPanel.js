import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { PlugsConnected } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;
const CATS = ["Tümü", "PMS", "Channel Manager", "OTA Direct", "Direkt Kanal"];
const API_BADGE = { open: ["Açık API", "bg-emerald-100 text-emerald-700"], partner: ["Partner API", "bg-sky-100 text-sky-700"], closed: ["Kapalı API", "bg-stone-200 text-stone-600"] };
const ST_BADGE = {
  connected: ["🟢 Bağlı", "bg-emerald-600 text-white"],
  ready: ["⚡ Panel Hazır", "bg-indigo-100 text-indigo-700"],
  available: ["Bağlanabilir", "bg-stone-100 text-stone-600"],
  requested: ["⏳ Talep Edildi", "bg-amber-100 text-amber-700"],
  coming_soon: ["🔜 Yakında (Direct)", "bg-violet-100 text-violet-700"],
};

export default function ConnectorCatalogPanel({ activePropertyId, properties = [], onNavigate }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : properties[0]?.id || "default";
  const [data, setData] = useState(null);
  const [cat, setCat] = useState("Tümü");

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/connector-catalog/${pid}`, { withCredentials: true });
      setData(r.data);
    } catch { toast.error("Katalog yüklenemedi"); }
  }, [pid]);

  useEffect(() => { load(); }, [load]);

  const request = async (key) => {
    try {
      const r = await axios.post(`${API}/api/connector-catalog/${pid}/request`, { key }, { withCredentials: true });
      toast.success(r.data.message || "Talep alındı");
      load();
    } catch { toast.error("Talep gönderilemedi"); }
  };

  const list = (data?.connectors || []).filter((c) => cat === "Tümü" || c.category === cat);

  return (
    <div className="p-5 max-w-[1200px] mx-auto" data-testid="connector-catalog-panel">
      <div className="flex flex-wrap items-end justify-between gap-3 mb-5">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <PlugsConnected size={13} weight="fill" className="text-indigo-500" /><span>Dağıtım Ağı</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">Bağlantı Kataloğu</h1>
          <p className="text-sm text-stone-500 mt-1">Sektördeki PMS, Channel Manager ve OTA konnektörleri — seçin ve bağlanın. Fiyatlarınız bağlı sistem üzerinden Booking.com ve tüm kanallara dağıtılır.</p>
        </div>
        {data && (
          <div className="text-xs font-bold text-stone-600 bg-stone-100 rounded-full px-3 py-1.5" data-testid="catalog-counts">
            {data.counts.connected} bağlı · {data.counts.ready} hazır · {data.counts.total} toplam
          </div>
        )}
      </div>

      <div className="flex gap-2 mb-4 flex-wrap">
        {CATS.map((c) => (
          <button key={c} onClick={() => setCat(c)} data-testid={`catalog-cat-${c}`}
            className={`px-3 py-1.5 rounded-full text-xs font-bold ${cat === c ? "bg-stone-900 text-white" : "bg-white border border-stone-300 text-stone-600 hover:border-stone-400"}`}>
            {c}
          </button>
        ))}
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {list.map((c) => {
          const [apiLabel, apiCls] = API_BADGE[c.api_type] || API_BADGE.closed;
          const [stLabel, stCls] = ST_BADGE[c.status] || ST_BADGE.available;
          return (
            <div key={c.key} className="bg-white border border-stone-200 rounded-2xl p-4 flex flex-col gap-2 hover:border-stone-300 transition-colors" data-testid={`connector-card-${c.key}`}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="text-sm font-black text-stone-800">{c.name}</div>
                  <div className="text-[10px] text-stone-400 font-bold uppercase tracking-wide mt-0.5">{c.category}</div>
                </div>
                <span className={`text-[10px] font-black px-2 py-0.5 rounded-full ${stCls}`} data-testid={`connector-status-${c.key}`}>{stLabel}</span>
              </div>
              <div className="flex items-center justify-between mt-auto pt-1">
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${apiCls}`}>{apiLabel}</span>
                {c.panel && c.status !== "coming_soon" ? (
                  <button onClick={() => onNavigate && onNavigate(c.panel)} data-testid={`connector-open-${c.key}`}
                    className="px-3 py-1.5 rounded-lg bg-stone-900 text-white text-[11px] font-bold hover:bg-stone-700">
                    {c.status === "connected" ? "Paneli Aç" : "Bağlan"}
                  </button>
                ) : c.status === "requested" ? (
                  <span className="text-[10px] text-amber-600 font-bold">sıraya alındı</span>
                ) : (
                  <button onClick={() => request(c.key)} data-testid={`connector-request-${c.key}`}
                    className="px-3 py-1.5 rounded-lg border border-stone-300 text-stone-600 text-[11px] font-bold hover:border-stone-500">
                    Talep Et
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
