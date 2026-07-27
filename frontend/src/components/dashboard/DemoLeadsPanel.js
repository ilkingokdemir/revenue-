import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Funnel, EnvelopeSimple, Buildings, Trash, CheckCircle } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/demo-requests`;
const STATUS_TR = { new: "Yeni", contacted: "İletişime geçildi", closed: "Kapatıldı" };
const STATUS_STYLE = {
  new: "bg-blue-50 text-blue-700 border-blue-200",
  contacted: "bg-amber-50 text-amber-700 border-amber-200",
  closed: "bg-stone-100 text-stone-500 border-stone-200",
};

export default function DemoLeadsPanel() {
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}${filter ? `?status=${filter}` : ""}`);
      setData(r.data);
    } catch { toast.error("Demo talepleri yüklenemedi"); }
  }, [filter]);
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
        <p className="text-sm text-stone-400 mt-1">Tanıtım sitesindeki "Request Demo" formundan gelen potansiyel müşteriler.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[["Toplam", s.total, "text-stone-800"], ["Yeni", s.new, "text-blue-600"],
          ["İletişimde", s.contacted, "text-amber-600"], ["Kapatıldı", s.closed, "text-stone-400"]].map(([label, val, c]) => (
          <div key={label} className="bg-white border border-stone-200 rounded-xl p-4" data-testid={`demo-kpi-${label}`}>
            <div className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">{label}</div>
            <div className={`text-2xl font-black tabular-nums ${c}`}>{val ?? 0}</div>
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        {["", "new", "contacted", "closed"].map((f) => (
          <button key={f} onClick={() => setFilter(f)} data-testid={`demo-filter-${f || "all"}`}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-colors ${filter === f ? "bg-stone-800 text-white border-stone-800" : "bg-white text-stone-500 border-stone-200 hover:border-stone-400"}`}>
            {f ? STATUS_TR[f] : "Tümü"}
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
                  <span className={`text-[10px] px-2 py-0.5 rounded-full border font-bold ${it.product === "rms" ? "bg-[#0A0F1C] text-blue-300 border-blue-900" : "bg-emerald-50 text-emerald-700 border-emerald-200"}`} data-testid={`demo-lead-product-${it.id}`}>
                    {it.product === "rms" ? "ReveniQ" : "MyHotelBox"}
                  </span>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full border font-bold ${STATUS_STYLE[it.status]}`}>{STATUS_TR[it.status]}</span>
                </div>
                <div className="text-xs text-stone-500 flex items-center gap-3 mt-1">
                  <span className="flex items-center gap-1"><EnvelopeSimple size={12} />{it.email}</span>
                  <span className="flex items-center gap-1"><Buildings size={12} />{it.hotel_name}{it.room_count ? ` · ${it.room_count} oda` : ""}</span>
                </div>
                {it.message && <p className="text-xs text-stone-500 mt-1.5 italic">"{it.message}"</p>}
                <div className="text-[10px] text-stone-400 mt-1">{new Date(it.created_at).toLocaleString("tr")}</div>
              </div>
              <div className="flex items-center gap-1.5">
                {it.status === "new" && (
                  <button onClick={() => setStatus(it.id, "contacted")} data-testid={`demo-lead-contact-${it.id}`}
                    className="px-2.5 py-1.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-xs font-bold hover:bg-amber-100 transition-colors">
                    İletişime geçildi
                  </button>
                )}
                {it.status !== "closed" && (
                  <button onClick={() => setStatus(it.id, "closed")} data-testid={`demo-lead-close-${it.id}`}
                    className="px-2.5 py-1.5 rounded-lg bg-stone-100 border border-stone-200 text-stone-600 text-xs font-bold hover:bg-stone-200 transition-colors flex items-center gap-1">
                    <CheckCircle size={12} /> Kapat
                  </button>
                )}
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
