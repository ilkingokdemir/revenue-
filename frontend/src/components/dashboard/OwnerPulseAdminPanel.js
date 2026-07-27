/** Admin — Sahip Portalı (Pulse) modül kontrolü + önizleme */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Gauge, Eye, EyeSlash, FloppyDisk, ArrowSquareOut } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MODULES = [
  { key: "dashboard", label: "Genel Bakış (Pulse Dashboard)", desc: "Aylık gelir kartları + YoY, 90g doluluk & pickup, yıllık tablo" },
  { key: "demand_radar", label: "Talep Radarı", desc: "90 gün pazar zekâsı: talep/fiyat/arz timeline, pickup, fırsat haritası" },
  { key: "compset", label: "Rekabet Analizi (Compset)", desc: "Segment kıyası, sıralamalar, günlük drill-down" },
  { key: "reports", label: "Rapor Merkezi", desc: "Performans, YoY, rezervasyon ve kanal raporları + CSV" },
  { key: "rates", label: "Fiyatlar & İndirimler", desc: "İki yönlü fiyat panosu (mevcut modül)" },
];

export default function OwnerPulseAdminPanel({ propertyId }) {
  const [modules, setModules] = useState(null);
  const [preview, setPreview] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [{ data: cfg }, { data: dash }] = await Promise.all([
        axios.get(`${API}/owner-pulse/${propertyId}/config`),
        axios.get(`${API}/owner-pulse/${propertyId}/dashboard`),
      ]);
      setModules(cfg.modules);
      setPreview(dash);
    } catch { toast.error("Yüklenemedi"); }
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/owner-pulse/${propertyId}/config`, { modules });
      toast.success("Sahip portalı modülleri güncellendi");
    } catch { toast.error("Kaydedilemedi"); }
    setSaving(false);
  };

  if (!modules) return <div className="text-center py-12 text-stone-400 text-sm">Yükleniyor…</div>;
  const pc = preview?.currency || "GBP";
  const c = pc === "GBP" ? "£" : pc === "EUR" ? "€" : pc === "TRY" ? "₺" : pc === "USD" ? "$" : pc + " ";

  return (
    <div className="space-y-6 rounded-2xl bg-stone-950 border border-stone-800 p-6" data-testid="owner-pulse-admin-panel">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-stone-100 flex items-center gap-2"><Gauge size={22} className="text-teal-400" /> Sahip Portalı — Pulse Modülleri</h2>
          <p className="text-sm text-stone-400 mt-1">Otel sahibinin <code className="text-teal-300">/owner</code> portalında hangi analitik ekranları göreceğini buradan yönetin. Kapatılan modül sahip tarafında anında gizlenir (API de 403 döner).</p>
        </div>
        <a href="/owner" target="_blank" rel="noreferrer" data-testid="opa-open-portal"
           className="text-xs px-3 py-2 rounded-lg bg-stone-800 border border-stone-700 text-stone-200 inline-flex items-center gap-1 hover:bg-stone-700"><ArrowSquareOut size={13} /> Sahip Portalını Aç</a>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {MODULES.map((m) => (
          <button key={m.key} onClick={() => setModules({ ...modules, [m.key]: !modules[m.key] })}
            data-testid={`opa-toggle-${m.key}`}
            className={`text-left rounded-xl border p-4 transition-colors ${modules[m.key] ? "bg-teal-500/10 border-teal-500/40" : "bg-stone-900/60 border-stone-800 opacity-70"}`}>
            <div className="flex items-center justify-between">
              <span className={`text-sm font-semibold ${modules[m.key] ? "text-teal-200" : "text-stone-400"}`}>{m.label}</span>
              {modules[m.key] ? <Eye size={16} className="text-teal-300" /> : <EyeSlash size={16} className="text-stone-500" />}
            </div>
            <div className="text-[11px] text-stone-500 mt-1">{m.desc}</div>
            <div className={`text-[10px] font-bold mt-2 ${modules[m.key] ? "text-teal-300" : "text-stone-500"}`}>{modules[m.key] ? "SAHİBE AÇIK" : "GİZLİ"}</div>
          </button>
        ))}
      </div>

      <button onClick={save} disabled={saving} data-testid="opa-save-btn"
        className="px-4 py-2 rounded-lg bg-teal-500/20 border border-teal-500/40 text-teal-200 text-sm font-semibold inline-flex items-center gap-2 hover:bg-teal-500/30 disabled:opacity-50">
        <FloppyDisk size={15} /> {saving ? "Kaydediliyor…" : "Değişiklikleri Kaydet"}
      </button>

      {preview && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4" data-testid="opa-preview">
          <div className="text-xs uppercase tracking-wider text-stone-500 font-semibold mb-3">Sahibin Göreceği Aylık Kartlar (önizleme)</div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {preview.month_cards.map((m) => (
              <div key={m.label} className="rounded-lg border border-stone-800 bg-stone-950/60 p-3">
                <div className="flex items-center justify-between text-[10px] text-stone-500 uppercase"><span>{m.label} · {m.tag}</span>
                  {m.yoy_pct != null && <span className={m.yoy_pct >= 0 ? "text-emerald-400" : "text-rose-400"}>YoY {m.yoy_pct >= 0 ? "+" : ""}{m.yoy_pct}%</span>}
                </div>
                <div className="text-xl font-bold text-stone-100 mt-1">{c}{(m.revenue || 0).toLocaleString()}</div>
                <div className="text-[10px] text-stone-500">Occ {m.occ}% · ADR {c}{Math.round(m.adr)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
