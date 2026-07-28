import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Funnel, EnvelopeSimple, Buildings, Trash, CheckCircle, MagnifyingGlass } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/demo-requests`;
const STATUS_TR = { new: "Yeni", contacted: "İletişimde", demo_scheduled: "Demo Planlandı", won: "Kazanıldı", lost: "Kaybedildi" };
const STATUS_STYLE = {
  new: "bg-blue-50 text-blue-700 border-blue-200",
  contacted: "bg-amber-50 text-amber-700 border-amber-200",
  demo_scheduled: "bg-violet-50 text-violet-700 border-violet-200",
  won: "bg-emerald-50 text-emerald-700 border-emerald-200",
  lost: "bg-stone-100 text-stone-500 border-stone-200",
};
const NEXT_STEPS = {
  new: [["contacted", "İletişime geçildi", "bg-amber-50 border-amber-200 text-amber-700 hover:bg-amber-100"]],
  contacted: [["demo_scheduled", "Demo planlandı", "bg-violet-50 border-violet-200 text-violet-700 hover:bg-violet-100"]],
  demo_scheduled: [
    ["won", "✓ Kazanıldı", "bg-emerald-50 border-emerald-200 text-emerald-700 hover:bg-emerald-100"],
    ["lost", "✕ Kaybedildi", "bg-stone-100 border-stone-200 text-stone-600 hover:bg-stone-200"],
  ],
  won: [], lost: [],
};
const PRODUCT_BADGE = {
  rms: ["ReveniQ", "bg-[#0A0F1C] text-blue-300 border-blue-900"],
  pms: ["MyHotelBox", "bg-emerald-50 text-emerald-700 border-emerald-200"],
  pulse: ["Market Pulse ★", "bg-teal-50 text-teal-700 border-teal-300"],
};

export default function DemoLeadsPanel() {
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState("");
  const [productFilter, setProductFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (filter) params.set("status", filter);
      if (productFilter) params.set("product", productFilter);
      if (sourceFilter) params.set("source", sourceFilter);
      const r = await axios.get(`${API}${params.toString() ? `?${params}` : ""}`);
      setData(r.data);
    } catch { toast.error("Demo talepleri yüklenemedi"); }
  }, [filter, productFilter, sourceFilter]);
  useEffect(() => { load(); }, [load]);

  const setStatus = async (id, status) => {
    try {
      await axios.patch(`${API}/${id}`, { status });
      toast.success(`Durum: ${STATUS_TR[status]}`);
      load();
    } catch { toast.error("Durum güncellenemedi"); }
  };

  const remove = async (id) => {
    try {
      await axios.delete(`${API}/${id}`);
      toast.success("Talep silindi");
      load();
    } catch { toast.error("Silinemedi"); }
  };

  const s = data?.summary || {};
  const items = data?.items || [];

  return (
    <div className="space-y-5" data-testid="demo-leads-panel">
      <div className="bg-[#0A0F1C] rounded-2xl p-6 text-white">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-400 mb-1">
          <Funnel size={14} /> Web Sitesi · Satış Hunisi
        </div>
        <h2 className="text-2xl font-bold">Demo Talepleri</h2>
        <p className="text-sm text-stone-400 mt-1">Tanıtım sitesindeki "Request Demo" formu ve Price Checker aracından gelen potansiyel müşteriler.</p>
        {s.price_checker_queries > 0 && (
          <div className="mt-3 inline-flex items-center gap-2 text-xs bg-white/10 rounded-lg px-3 py-1.5" data-testid="demo-pc-stats">
            <MagnifyingGlass size={13} className="text-amber-300" />
            <span className="text-stone-300">Price Checker: <b className="text-white">{s.price_checker_queries}</b> sorgu → <b className="text-amber-300">{s.price_checker_leads}</b> CRM lead'i</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-3">
        {[["Toplam", s.total, "text-stone-800"], ["Yeni", s.new, "text-blue-600"],
          ["İletişimde", s.contacted, "text-amber-600"], ["Demo Planlandı", s.demo_scheduled, "text-violet-600"],
          ["Kazanıldı", s.won, "text-emerald-600"], ["Kaybedildi", s.lost, "text-stone-400"],
          ["Kazanma Oranı", s.win_rate != null ? `%${s.win_rate}` : "—", "text-teal-600"]].map(([label, val, c]) => (
          <div key={label} className="bg-white border border-stone-200 rounded-xl p-4" data-testid={`demo-kpi-${label}`}>
            <div className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">{label}</div>
            <div className={`text-2xl font-black tabular-nums ${c}`}>{val ?? 0}</div>
          </div>
        ))}
      </div>

      <div className="flex gap-2 flex-wrap items-center">
        {["", "new", "contacted", "demo_scheduled", "won", "lost"].map((f) => (
          <button key={f} onClick={() => setFilter(f)} data-testid={`demo-filter-${f || "all"}`}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-colors ${filter === f ? "bg-stone-800 text-white border-stone-800" : "bg-white text-stone-500 border-stone-200 hover:border-stone-400"}`}>
            {f ? STATUS_TR[f] : "Tümü"}
          </button>
        ))}
        <span className="mx-1 text-stone-300">|</span>
        {[["", "Tüm Ürünler"], ["pms", "MyHotelBox"], ["rms", "ReveniQ"], ["pulse", "Pulse ★"]].map(([p, label]) => (
          <button key={p} onClick={() => setProductFilter(p)} data-testid={`demo-product-filter-${p || "all"}`}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-colors ${productFilter === p ? "bg-teal-600 text-white border-teal-600" : "bg-white text-stone-500 border-stone-200 hover:border-teal-400"}`}>
            {label}
          </button>
        ))}
        <span className="mx-1 text-stone-300">|</span>
        {[["", "Tüm Kaynaklar"], ["landing", "Demo Formu"], ["price-checker", "Price Checker 🔍"]].map(([src, label]) => (
          <button key={src} onClick={() => setSourceFilter(src)} data-testid={`demo-source-filter-${src || "all"}`}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-colors ${sourceFilter === src ? "bg-amber-500 text-white border-amber-500" : "bg-white text-stone-500 border-stone-200 hover:border-amber-400"}`}>
            {label}
          </button>
        ))}
      </div>

      {items.length === 0 ? (
        <div className="bg-white border border-stone-200 rounded-xl p-10 text-center text-sm text-stone-400" data-testid="demo-leads-empty">
          Henüz demo talebi yok. Tanıtım sitesi yayında — talepler burada listelenecek.
        </div>
      ) : (
        <div className="space-y-2" data-testid="demo-leads-list">
          {items.map((it) => (
            <div key={it.id} className="bg-white border border-stone-200 rounded-xl p-4 flex flex-wrap items-center gap-3" data-testid={`demo-lead-${it.id}`}>
              <div className="flex-1 min-w-[220px]">
                <div className="font-bold text-stone-800 text-sm flex items-center gap-2">
                  {it.name}
                  {(() => { const [pl, pc] = PRODUCT_BADGE[it.product] || PRODUCT_BADGE.pms; return (
                    <span className={`text-[10px] px-2 py-0.5 rounded-full border font-bold ${pc}`} data-testid={`demo-lead-product-${it.id}`}>{pl}</span>
                  ); })()}
                  {it.source === "price-checker" && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full border font-bold bg-amber-50 text-amber-700 border-amber-300" data-testid={`demo-lead-source-${it.id}`}>Price Checker 🔍</span>
                  )}
                  <span className={`text-[10px] px-2 py-0.5 rounded-full border font-bold ${STATUS_STYLE[it.status] || STATUS_STYLE.new}`}>{STATUS_TR[it.status] || it.status}</span>
                </div>
                <div className="text-xs text-stone-500 flex items-center gap-3 mt-1">
                  <span className="flex items-center gap-1"><EnvelopeSimple size={12} />{it.email}</span>
                  <span className="flex items-center gap-1"><Buildings size={12} />{it.hotel_name}{it.room_count ? ` · ${it.room_count} oda` : ""}</span>
                </div>
                {it.message && <p className="text-xs text-stone-500 mt-1.5 italic">"{it.message}"</p>}
                <div className="text-[10px] text-stone-400 mt-1">{new Date(it.created_at).toLocaleString("tr")}</div>
              </div>
              <div className="flex items-center gap-1.5">
                {(NEXT_STEPS[it.status] || []).map(([st, label, cls]) => (
                  <button key={st} onClick={() => setStatus(it.id, st)} data-testid={`demo-lead-${st}-${it.id}`}
                    className={`px-2.5 py-1.5 rounded-lg border text-xs font-bold transition-colors ${cls}`}>
                    {label}
                  </button>
                ))}
                <button onClick={() => remove(it.id)} data-testid={`demo-lead-delete-${it.id}`}
                  className="p-1.5 rounded-lg text-stone-400 hover:text-rose-500 hover:bg-rose-50 transition-colors">
                  <Trash size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
