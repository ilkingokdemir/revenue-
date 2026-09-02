import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Lock, LockOpen } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cfg = { withCredentials: true };
const MONTHS_TR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];
const STATUS_TR = { pending: ["Onay bekliyor", "bg-amber-50 text-amber-700"], approved: ["Onaylandı · kilit açık", "bg-emerald-50 text-emerald-700"],
  rejected: ["Reddedildi", "bg-red-50 text-red-600"], applied: ["Uygulandı · yeniden çalıştırıldı", "bg-sky-50 text-sky-700"] };

export const PayrollCorrectionsCard = ({ pid, isAdmin, refreshKey, onChanged }) => {
  const [items, setItems] = useState([]);
  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/uk-payroll/corrections/${pid}`, cfg);
      setItems(data);
    } catch { /* ignore */ }
  }, [pid]);
  useEffect(() => { load(); }, [load, refreshKey]);

  const decide = async (c, decision) => {
    try {
      await axios.post(`${API}/uk-payroll/corrections/${c.id}/decide`, { decision }, cfg);
      toast.success(decision === "approve" ? "Düzeltme onaylandı — bordro kilidi açıldı" : "Düzeltme talebi reddedildi");
      load();
      onChanged?.();
    } catch (e) { toast.error(e.response?.data?.detail || "İşlem başarısız"); }
  };

  const pending = items.filter((c) => c.status === "pending");
  return (
    <div className="bg-white border border-stone-200 rounded-2xl p-4" data-testid="ukp-corrections-card">
      <div className="flex items-center gap-2 font-semibold text-sm mb-3">
        <Lock size={16} className="text-amber-600" /> Bordro Kilidi & Düzeltme Geçmişi
        {pending.length > 0 && <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-800" data-testid="ukp-corrections-pending-badge">{pending.length} bekliyor</span>}
      </div>
      <p className="text-xs text-stone-500 mb-3">Çalıştırılan bordrolar otomatik kilitlenir. Değişiklik için düzeltme talebi açılır; admin onaylayınca kilit açılır ve dönem yeniden çalıştırılabilir. Admin doğrudan da kilidi açabilir — her adım burada loglanır.</p>
      <div className="space-y-1.5 max-h-64 overflow-y-auto">
        {items.map((c) => {
          const [label, cls] = STATUS_TR[c.status] || [c.status, "bg-stone-100 text-stone-600"];
          return (
            <div key={c.id} className="flex flex-wrap items-center justify-between gap-2 text-sm border border-stone-100 rounded-xl px-3 py-2" data-testid={`ukp-correction-${c.id}`}>
              <div>
                <b>{MONTHS_TR[c.month - 1]} {c.year}</b> · {c.requested_by} · <span className="text-stone-500">{c.reason}</span>
                {c.direct && <span className="ml-1 text-xs text-violet-600">(admin doğrudan açtı)</span>}
                {c.decided_by && !c.direct && <span className="text-xs text-stone-400"> — karar: {c.decided_by}</span>}
              </div>
              <div className="flex items-center gap-1.5">
                <span className={`text-xs px-2 py-0.5 rounded-full ${cls}`}>{label}</span>
                {c.status === "pending" && isAdmin && (
                  <>
                    <button onClick={() => decide(c, "approve")} className="px-2.5 py-1 text-xs rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 inline-flex items-center gap-1" data-testid={`ukp-correction-approve-${c.id}`}><LockOpen size={12} /> Onayla</button>
                    <button onClick={() => decide(c, "reject")} className="px-2.5 py-1 text-xs rounded-lg bg-red-100 text-red-600 hover:bg-red-200" data-testid={`ukp-correction-reject-${c.id}`}>Reddet</button>
                  </>
                )}
              </div>
            </div>
          );
        })}
        {items.length === 0 && <div className="text-xs text-stone-400">Henüz düzeltme talebi yok.</div>}
      </div>
    </div>
  );
};
