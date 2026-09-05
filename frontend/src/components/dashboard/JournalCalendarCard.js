import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { CaretLeft, CaretRight, ArrowsClockwise, CalendarBlank } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const COLOR = { pushed: "bg-emerald-500", mock: "bg-amber-400", failed: "bg-rose-500", missing: "bg-stone-300", future: "bg-transparent border border-dashed border-stone-200" };
const LABEL = { pushed: "Gönderildi", mock: "Outbox (MOCK)", failed: "Başarısız", missing: "Eksik", future: "Gelecek" };
const addM = (ym, n) => { const [y, m] = ym.split("-").map(Number); const d = new Date(Date.UTC(y, m - 1 + n, 1)); return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`; };

export default function JournalCalendarCard({ propertyId }) {
  const pid = propertyId && propertyId !== "all" ? propertyId : "default";
  const [ym, setYm] = useState(() => new Date().toISOString().slice(0, 7));
  const [data, setData] = useState(null);
  const [sel, setSel] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    axios.get(`${API}/accounting/journal/calendar/${pid}?month=${ym}`).then(({ data: d }) => setData(d)).catch(() => toast.error("Takvim yüklenemedi"));
  }, [pid, ym]);
  useEffect(() => { load(); }, [load]);

  const resend = async (dates) => {
    if (!dates.length) return;
    setBusy(true);
    try {
      const { data: r } = await axios.post(`${API}/accounting/journal/resend/${pid}`, { dates });
      toast.success(`${r.items.length} gün yeniden gönderildi`); load(); setSel(null);
    } catch (e) { toast.error(e.response?.data?.detail || "Gönderilemedi"); } finally { setBusy(false); }
  };

  if (!data) return null;
  const [y, m] = ym.split("-").map(Number);
  const lead = (new Date(Date.UTC(y, m - 1, 1)).getUTCDay() + 6) % 7;
  const label = new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString("tr-TR", { month: "long", year: "numeric", timeZone: "UTC" });
  const day = sel ? data.days.find((d) => d.date === sel) : null;

  return (
    <div className="bg-white border border-stone-200 rounded-2xl p-5 space-y-3" data-testid="journal-calendar-card">
      <div className="flex items-center gap-3 flex-wrap">
        <CalendarBlank size={18} weight="fill" className="text-indigo-600" />
        <h3 className="text-sm font-semibold text-stone-900">Yevmiye Takvimi</h3>
        <span className="text-xs text-stone-500">{data.providers.join(" · ").toUpperCase()}</span>
        <div className="ml-auto flex items-center gap-1">
          <button onClick={() => setYm(addM(ym, -1))} className="w-7 h-7 rounded-full border border-stone-200 flex items-center justify-center hover:bg-stone-50" data-testid="jc-prev"><CaretLeft size={12} /></button>
          <span className="text-xs font-semibold capitalize w-32 text-center" data-testid="jc-month">{label}</span>
          <button onClick={() => setYm(addM(ym, 1))} className="w-7 h-7 rounded-full border border-stone-200 flex items-center justify-center hover:bg-stone-50" data-testid="jc-next"><CaretRight size={12} /></button>
        </div>
      </div>
      <div className="flex flex-wrap gap-3 text-[11px]">
        {Object.entries(LABEL).filter(([k]) => k !== "future").map(([k, v]) => <span key={k} className="inline-flex items-center gap-1.5"><span className={`w-2.5 h-2.5 rounded-sm ${COLOR[k]}`} /> {v}: <b data-testid={`jc-count-${k}`}>{data.counts[k]}</b></span>)}
        {data.resend_candidates.length > 0 && (
          <button onClick={() => resend(data.resend_candidates)} disabled={busy} className="ml-auto px-3 py-1 rounded-lg bg-stone-900 text-white text-[11px] font-bold inline-flex items-center gap-1 disabled:opacity-50" data-testid="jc-resend-all">
            <ArrowsClockwise size={12} /> Eksik/başarısız {data.resend_candidates.length} günü gönder
          </button>
        )}
      </div>
      <div className="grid grid-cols-7 gap-1 text-[10px] text-stone-400 font-bold uppercase">{["Pt", "Sa", "Ça", "Pe", "Cu", "Ct", "Pz"].map((d) => <div key={d} className="text-center">{d}</div>)}</div>
      <div className="grid grid-cols-7 gap-1">
        {Array.from({ length: lead }).map((_, i) => <div key={`e${i}`} />)}
        {data.days.map((d) => (
          <button key={d.date} onClick={() => d.status !== "future" && setSel(d.date === sel ? null : d.date)} disabled={d.status === "future"}
            className={`h-12 rounded-lg flex flex-col items-center justify-center text-[11px] transition-all ${sel === d.date ? "ring-2 ring-indigo-500" : ""} ${d.status === "future" ? "text-stone-300" : "text-white hover:opacity-90"} ${COLOR[d.status]}`}
            title={LABEL[d.status]} data-testid={`jc-day-${d.date}`} data-status={d.status}>
            <span className="font-bold">{Number(d.date.slice(-2))}</span>
            {d.status !== "future" && d.status !== "missing" && <span className="text-[9px] opacity-90">{Object.values(d.providers).map((p) => p.total != null ? `£${Math.round(p.total)}` : "").filter(Boolean)[0] || ""}</span>}
          </button>
        ))}
      </div>
      {day && (
        <div className="border border-stone-200 rounded-xl p-3 text-xs space-y-2" data-testid="jc-day-detail">
          <div className="flex items-center justify-between">
            <b>{new Date(day.date).toLocaleDateString("tr-TR", { day: "numeric", month: "long", weekday: "long" })}</b>
            {(day.status === "failed" || day.status === "missing" || day.status === "mock") && (
              <button onClick={() => resend([day.date])} disabled={busy} className="px-2.5 py-1 rounded-lg bg-indigo-600 text-white text-[11px] font-bold inline-flex items-center gap-1 disabled:opacity-50" data-testid="jc-resend-day"><ArrowsClockwise size={11} /> Yeniden gönder</button>
            )}
          </div>
          {Object.entries(day.providers).map(([p, v]) => (
            <div key={p} className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${COLOR[v.status]}`} /><span className="uppercase font-semibold w-10">{p}</span>
              <span>{LABEL[v.status]}</span>{v.total != null && <span className="text-stone-500">· £{Number(v.total).toFixed(2)}</span>}
              {v.at && <span className="text-stone-400">· {new Date(v.at).toLocaleString("tr-TR")}</span>}
              {v.error && <span className="text-rose-600 truncate">· {v.error}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
