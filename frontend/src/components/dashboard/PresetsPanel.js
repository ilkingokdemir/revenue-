import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Buildings, CheckCircle } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PresetsPanel({ activePropertyId, properties }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default");
  const [presets, setPresets] = useState([]);
  const [applied, setApplied] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/property-presets`);
      setPresets(data.presets || []);
      const p = (properties || []).find((x) => x.id === pid);
      setApplied(p?.preset || null);
    } catch { toast.error("Yüklenemedi"); }
  }, [pid, properties]);

  useEffect(() => { load(); }, [load]);

  const apply = async (key) => {
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/property-presets/apply/${pid}`, { preset: key });
      setApplied(key);
      toast.success(data.rooms_skipped
        ? "Şablon uygulandı — mevcut odalar korundu, RMS varsayılanları güncellendi"
        : `Şablon uygulandı — ${data.room_types_created} oda tipi oluşturuldu + RMS varsayılanları ayarlandı`);
    } catch (e) { toast.error(e.response?.data?.detail || "Uygulanamadı"); }
    setBusy(false);
  };

  return (
    <div className="p-6 max-w-4xl" data-testid="presets-panel">
      <div className="mb-5">
        <h2 className="text-xl font-bold text-stone-800">Tesis Tipi Şablonları</h2>
        <p className="text-xs text-stone-500 mt-1">Tesisinizin tipini seçin — oda tipleri, baz fiyatlar, guardrail'ler ve fiyatlama modu tek tıkla hazır kurulsun. Mevcut odalarınız varsa korunur.</p>
      </div>
      <div className="grid sm:grid-cols-2 gap-3">
        {presets.map((p) => (
          <div key={p.id} className={`rounded-2xl border-2 p-4 ${applied === p.id ? "border-emerald-500 bg-emerald-50" : "border-stone-200 bg-white"}`} data-testid={`preset-card-${p.id}`}>
            <div className="flex items-center gap-2 mb-1">
              <Buildings size={16} weight="bold" className="text-stone-600" />
              <span className="text-sm font-bold text-stone-800">{p.name}</span>
              {applied === p.id && <CheckCircle size={15} weight="fill" className="text-emerald-500 ml-auto" />}
            </div>
            <p className="text-[11px] text-stone-500 mb-2">{p.desc}</p>
            <div className="text-[10px] text-stone-600 space-y-0.5 mb-3">
              {p.room_types.map((r) => <div key={r.name}>• {r.name} — £{r.base_rate} × {r.total}</div>)}
              <div className="font-semibold">RMS: £{p.rms.min_rate}–£{p.rms.max_rate} · mod: {p.rms.mode}</div>
            </div>
            <button onClick={() => apply(p.id)} disabled={busy} data-testid={`preset-apply-${p.id}`}
              className={`w-full py-2 rounded-lg text-xs font-bold ${applied === p.id
                ? "bg-emerald-600 text-white" : "bg-stone-900 text-white hover:bg-stone-700"} disabled:opacity-50`}>
              {applied === p.id ? "Uygulandı ✓ (Yeniden Uygula)" : "Bu Şablonu Uygula"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
