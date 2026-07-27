import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ShieldCheck, Clock, Trash, FloppyDisk, CalendarBlank } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/min-rates`;

function RuleRow({ rt, rule, pid, onSaved, onDeleted }) {
  const [std, setStd] = useState(rule?.standard_min_rate ?? "");
  const [near, setNear] = useState(rule?.near_term_min_rate ?? "");
  const [window_, setWindow] = useState(rule?.near_term_window_days ?? 7);
  const [enabled, setEnabled] = useState(rule?.enabled ?? true);
  const [preview, setPreview] = useState(null);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/${pid}/${rt.id}`, {
        standard_min_rate: std ? parseFloat(std) : null,
        near_term_min_rate: near ? parseFloat(near) : null,
        near_term_window_days: parseInt(window_) || 7,
        enabled,
      });
      toast.success(`${rt.name}: minimum fiyat kuralı kaydedildi`);
      onSaved();
      loadPreview();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Kaydedilemedi");
    } finally { setSaving(false); }
  };

  const del = async () => {
    try {
      await axios.delete(`${API}/${pid}/${rt.id}`);
      toast.success("Kural silindi");
      setStd(""); setNear(""); setWindow(7); setPreview(null);
      onDeleted();
    } catch (e) { toast.error(e?.response?.data?.detail || "Silinemedi"); }
  };

  const loadPreview = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/${pid}/preview/${rt.id}?days=14`);
      setPreview(data.days);
    } catch { /* preview optional */ }
  }, [pid, rt.id]);

  useEffect(() => { if (rule) loadPreview(); }, [rule, loadPreview]);

  const inputCls = "w-24 rounded-lg border border-stone-200 px-2.5 py-1.5 text-sm text-right tabular-nums focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/40";

  return (
    <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid={`minrate-rule-${rt.id}`}>
      <div className="flex flex-wrap items-center gap-4">
        <div className="min-w-[140px]">
          <div className="font-bold text-sm text-stone-800">{rt.name}</div>
          <div className="text-[10px] text-stone-400">baz fiyat £{rt.base_rate ?? "—"}</div>
        </div>
        <div>
          <label className="block text-[10px] uppercase tracking-widest text-stone-400 font-bold mb-1">Standart min (£)</label>
          <input type="number" min="1" value={std} onChange={(e) => setStd(e.target.value)}
            placeholder="örn. 120" className={inputCls} data-testid={`minrate-std-${rt.id}`} />
        </div>
        <div>
          <label className="block text-[10px] uppercase tracking-widest text-stone-400 font-bold mb-1">Yakın tarih min (£)</label>
          <input type="number" min="1" value={near} onChange={(e) => setNear(e.target.value)}
            placeholder="örn. 80" className={inputCls} data-testid={`minrate-near-${rt.id}`} />
        </div>
        <div>
          <label className="block text-[10px] uppercase tracking-widest text-stone-400 font-bold mb-1">Son kaç gün?</label>
          <input type="number" min="1" max="60" value={window_} onChange={(e) => setWindow(e.target.value)}
            className="w-16 rounded-lg border border-stone-200 px-2.5 py-1.5 text-sm text-right tabular-nums focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/40"
            data-testid={`minrate-window-${rt.id}`} />
        </div>
        <label className="flex items-center gap-2 text-xs text-stone-600 font-bold cursor-pointer mt-4">
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)}
            className="accent-[#1D4ED8] w-4 h-4" data-testid={`minrate-enabled-${rt.id}`} />
          Aktif
        </label>
        <div className="flex items-center gap-2 ml-auto mt-3">
          <button onClick={save} disabled={saving} data-testid={`minrate-save-${rt.id}`}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-gradient-to-r from-[#1D4ED8] to-[#06B6D4] text-white text-xs font-bold hover:from-[#1E40AF] hover:to-[#0891B2] transition-colors disabled:opacity-60">
            <FloppyDisk size={13} weight="bold" /> Kaydet
          </button>
          {rule && (
            <button onClick={del} data-testid={`minrate-delete-${rt.id}`}
              className="p-2 rounded-lg text-stone-400 hover:text-rose-500 hover:bg-rose-50 transition-colors">
              <Trash size={15} />
            </button>
          )}
        </div>
      </div>

      {preview && (
        <div className="mt-4 pt-3 border-t border-stone-100">
          <div className="text-[10px] uppercase tracking-widest text-stone-400 font-bold mb-2 flex items-center gap-1.5">
            <CalendarBlank size={11} /> 14 günlük önizleme — hangi taban aktif?
          </div>
          <div className="flex gap-1 overflow-x-auto pb-1" data-testid={`minrate-preview-${rt.id}`}>
            {preview.map((d) => (
              <div key={d.date} title={d.date}
                className={`shrink-0 w-[68px] rounded-lg border px-1.5 py-1.5 text-center ${
                  d.mode === "near_term" ? "bg-amber-50 border-amber-300"
                  : d.mode === "standard" ? "bg-blue-50 border-blue-200" : "bg-stone-50 border-stone-200"}`}>
                <div className="text-[9px] text-stone-400 font-bold">{d.date.slice(5)}</div>
                <div className={`text-xs font-black tabular-nums ${d.mode === "near_term" ? "text-amber-700" : d.mode === "standard" ? "text-[#1D4ED8]" : "text-stone-300"}`}>
                  {d.floor ? `£${d.floor}` : "—"}
                </div>
                <div className="text-[8px] font-bold uppercase text-stone-400">
                  {d.mode === "near_term" ? "yakın" : d.mode === "standard" ? "standart" : ""}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function MinRateFloorsPanel({ propertyId = "default" }) {
  const pid = propertyId === "all" ? "default" : propertyId;
  const [data, setData] = useState(null);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/${pid}`);
      setData(data);
    } catch { toast.error("Minimum fiyat kuralları yüklenemedi"); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const ruleFor = (rtId) => data?.rules?.find((r) => r.room_type_id === rtId);
  const roomTypes = [{ id: "all", name: "Tüm oda tipleri (varsayılan)", base_rate: null },
    ...(data?.room_types || [])];

  return (
    <div className="space-y-5" data-testid="min-rates-panel">
      <div className="relative bg-[#0A0F1C] rounded-2xl p-6 text-white overflow-hidden">
        <div className="absolute top-[-60px] right-[-40px] w-[240px] h-[240px] rounded-full bg-[#10B981]/20 blur-3xl" aria-hidden="true" />
        <div className="relative">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-emerald-300 mb-1">
            <ShieldCheck size={15} weight="duotone" /> Revenue Management · Fiyat Koruması
          </div>
          <h2 className="text-2xl font-bold">Çift Minimum Fiyat Sistemi</h2>
          <p className="text-sm text-stone-400 mt-1 max-w-2xl">
            Her oda tipi için iki taban fiyat belirleyin: <b className="text-blue-300">standart minimum</b> normal dönemde geçerlidir;
            girişe belirlediğiniz gün sayısı kala (vars. 7) otomatik devre dışı kalır ve
            <b className="text-amber-300"> yakın tarih minimumu</b> devreye girer.
            AI pricing ve Strateji Robotu bu tabanların altına fiyat yazamaz.
          </p>
          <div className="flex items-center gap-2 mt-3 text-xs text-stone-400">
            <Clock size={13} className="text-amber-300" />
            Örnek: Double oda standart min £120 → son 7 gün kala min £80 aktif olur.
          </div>
        </div>
      </div>

      <div className="space-y-3" data-testid="min-rates-list">
        {roomTypes.map((rt) => (
          <RuleRow key={rt.id} rt={rt} rule={ruleFor(rt.id)} pid={pid} onSaved={load} onDeleted={load} />
        ))}
      </div>
    </div>
  );
}
