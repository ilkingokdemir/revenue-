import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Baby, Trash2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cfg = { withCredentials: true };
const gbp = (n) => `£${Number(n || 0).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const inputCls = "w-full border border-stone-300 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500";

export const ParentalLeaveCard = ({ pid, employees }) => {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ staff_id: "", type: "maternity", start_date: "", awe: "", weeks: 2 });
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/uk-payroll/parental-leave/${pid}`, cfg);
      setItems(data);
    } catch { /* ignore */ }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const submit = async () => {
    if (!f.staff_id || !f.start_date) { toast.error("Personel ve başlangıç tarihi zorunlu"); return; }
    try {
      await axios.post(`${API}/uk-payroll/employees/${f.staff_id}/parental-leave`,
        { type: f.type, start_date: f.start_date, awe: parseFloat(f.awe) || 0, weeks: parseInt(f.weeks) || 2 }, cfg);
      toast.success(f.type === "maternity" ? "Annelik izni (SMP) kaydedildi — bordroya otomatik yansır" : "Babalık izni (SPP) kaydedildi — bordroya otomatik yansır");
      setOpen(false);
      setF({ staff_id: "", type: "maternity", start_date: "", awe: "", weeks: 2 });
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Kaydedilemedi"); }
  };

  const end = async (pl) => {
    if (!window.confirm(`${pl.staff_name} doğum izni sonlandırılsın mı? Sonraki bordrolara yansımaz.`)) return;
    try {
      await axios.delete(`${API}/uk-payroll/parental-leave/${pl.id}`, cfg);
      toast.success("Doğum izni sonlandırıldı");
      load();
    } catch { toast.error("İşlem başarısız"); }
  };

  const active = items.filter((i) => i.status === "active");
  return (
    <div className="bg-white border border-pink-200 rounded-2xl p-4" data-testid="ukp-parental-card">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2 font-semibold text-sm text-pink-800">
          <Baby size={16} /> Doğum İzni — SMP / SPP ({active.length} aktif)
          <span className="text-xs text-stone-400 font-normal">· 2026/27: £194.32/hafta, LEL £129</span>
        </div>
        <button onClick={() => setOpen(!open)} className="text-xs px-3 py-1.5 rounded-lg bg-pink-600 text-white hover:bg-pink-700" data-testid="ukp-parental-add-btn">
          {open ? "Vazgeç" : "+ Doğum İzni Ekle"}
        </button>
      </div>
      {open && (
        <div className="bg-pink-50/50 border border-pink-100 rounded-xl p-3 mb-3 grid grid-cols-2 md:grid-cols-6 gap-3 items-end" data-testid="ukp-parental-form">
          <label className="block text-xs"><span className="text-stone-500 font-medium">Personel</span>
            <select className={inputCls + " mt-1"} value={f.staff_id} onChange={(e) => set("staff_id", e.target.value)} data-testid="ukp-parental-staff">
              <option value="">Seçin</option>
              {employees.filter((e) => e.employment_status !== "leaver").map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
            </select></label>
          <label className="block text-xs"><span className="text-stone-500 font-medium">Tür</span>
            <select className={inputCls + " mt-1"} value={f.type} onChange={(e) => set("type", e.target.value)} data-testid="ukp-parental-type">
              <option value="maternity">Annelik (SMP · 39 hafta)</option>
              <option value="paternity">Babalık (SPP · 1-2 hafta)</option>
            </select></label>
          <label className="block text-xs"><span className="text-stone-500 font-medium">Başlangıç</span>
            <input type="date" className={inputCls + " mt-1"} value={f.start_date} onChange={(e) => set("start_date", e.target.value)} data-testid="ukp-parental-start" /></label>
          <label className="block text-xs"><span className="text-stone-500 font-medium">AWE £/hafta</span>
            <input type="number" step="0.01" placeholder="boş = bordrodan" className={inputCls + " mt-1"} value={f.awe} onChange={(e) => set("awe", e.target.value)} data-testid="ukp-parental-awe" /></label>
          {f.type === "paternity" && (
            <label className="block text-xs"><span className="text-stone-500 font-medium">Hafta</span>
              <select className={inputCls + " mt-1"} value={f.weeks} onChange={(e) => set("weeks", e.target.value)} data-testid="ukp-parental-weeks">
                <option value={1}>1</option><option value={2}>2</option>
              </select></label>
          )}
          <button onClick={submit} className="px-4 py-2 text-sm rounded-lg bg-pink-600 text-white hover:bg-pink-700 h-fit" data-testid="ukp-parental-submit">Kaydet</button>
        </div>
      )}
      <div className="space-y-1.5">
        {items.map((pl) => (
          <div key={pl.id} className={`flex flex-wrap items-center justify-between gap-2 text-sm border rounded-xl px-3 py-2 ${pl.status === "active" ? "border-pink-100" : "border-stone-100 opacity-50"}`} data-testid={`ukp-parental-row-${pl.id}`}>
            <div>
              <b>{pl.staff_name}</b> · {pl.type === "maternity" ? "SMP Annelik" : "SPP Babalık"} · {pl.start_date} → {pl.end_date} ({pl.total_weeks} hafta)
              <span className="text-stone-500"> · AWE {gbp(pl.awe)} · ilk hafta {gbp(pl.weekly_first)}{pl.type === "maternity" && <> · 7. haftadan {gbp(pl.weekly_standard)}</>} · toplam <b>{gbp(pl.total_pay)}</b></span>
            </div>
            {pl.status === "active"
              ? <button onClick={() => end(pl)} className="p-1.5 rounded-lg border border-stone-200 hover:bg-red-50 text-red-500" title="Sonlandır" data-testid={`ukp-parental-end-${pl.id}`}><Trash2 size={14} /></button>
              : <span className="text-xs text-stone-400">Sonlandı</span>}
          </div>
        ))}
        {items.length === 0 && <div className="text-xs text-stone-400">Kayıtlı doğum izni yok.</div>}
      </div>
    </div>
  );
};
