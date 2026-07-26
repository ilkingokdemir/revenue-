import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Broom, ArrowsClockwise, Lightning, User } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/hk-dispatch`;

const STATUS_CLS = {
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  in_progress: "bg-sky-50 text-sky-700 border-sky-200",
  clean: "bg-emerald-50 text-emerald-700 border-emerald-200",
  done: "bg-emerald-50 text-emerald-700 border-emerald-200",
  completed: "bg-emerald-50 text-emerald-700 border-emerald-200",
  inspected: "bg-teal-50 text-teal-700 border-teal-200",
};

export default function HkDispatchPanel({ propertyId = "all" }) {
  const [board, setBoard] = useState(null);
  const [running, setRunning] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/${propertyId}/board`);
      setBoard(r.data);
    } catch { toast.error("Pano yüklenemedi"); }
  }, [propertyId]);

  useEffect(() => {
    load();
    const iv = setInterval(load, 30000);
    return () => clearInterval(iv);
  }, [load]);

  async function dispatch() {
    setRunning(true);
    try {
      const r = await axios.post(`${API}/${propertyId}/run`);
      toast.success(`${r.data.tasks_created} görev dağıtıldı (${r.data.urgent} öncelikli) · ${r.data.skipped_duplicates} zaten vardı`);
      load();
    } catch { toast.error("Dağıtım çalıştırılamadı"); }
    setRunning(false);
  }

  if (!board) return <div className="p-8 text-center text-stone-400">Yükleniyor…</div>;
  const c = board.counts || {};

  return (
    <div className="p-5 max-w-[1400px] mx-auto space-y-4" data-testid="hk-dispatch-panel">
      <div className="bg-gradient-to-br from-stone-900 via-cyan-950 to-sky-900 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-cyan-300">
              <Broom size={14} /> Auto-Dispatch
            </div>
            <h1 className="text-2xl font-bold mt-1">Housekeeping Görev Dağıtım Panosu</h1>
            <p className="text-sm text-stone-300 mt-1">
              Check-out olan odalar en az yüklü görevliye otomatik atanır; bugün varış olan odalar ⚡ öncelikli işaretlenir. 30 sn'de bir yenilenir.
            </p>
          </div>
          <button onClick={dispatch} disabled={running} data-testid="hk-dispatch-run-btn"
            className="px-4 py-2 bg-cyan-400 hover:bg-cyan-300 text-stone-900 rounded-lg text-sm font-bold inline-flex items-center gap-2 disabled:opacity-60">
            <ArrowsClockwise size={16} className={running ? "animate-spin" : ""} />
            {running ? "Dağıtılıyor…" : "Görevleri Dağıt"}
          </button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5">
          <Stat label="Bugünkü görev" value={board.total} testid="hkd-stat-total" />
          <Stat label="Bekleyen" value={c.pending || 0} testid="hkd-stat-pending" />
          <Stat label="Devam eden" value={c.in_progress || 0} testid="hkd-stat-progress" />
          <Stat label="Öncelikli oda" value={(board.urgent_rooms || []).length} warn={(board.urgent_rooms || []).length > 0} testid="hkd-stat-urgent" />
        </div>
        {(board.urgent_rooms || []).length > 0 && (
          <div className="mt-3 text-xs text-amber-300 flex items-center gap-1.5" data-testid="hkd-urgent-strip">
            <Lightning size={14} weight="fill" /> Erken varış öncelikli odalar: {board.urgent_rooms.join(", ")}
          </div>
        )}
      </div>

      {/* Staff columns */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {(board.columns || []).map(col => (
          <div key={col.id} className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid={`hkd-col-${col.id}`}>
            <div className="px-3 py-2.5 border-b border-stone-100 flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-cyan-100 text-cyan-700 flex items-center justify-center"><User size={14} /></div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-stone-800 truncate">{col.name}</div>
                <div className="text-[10px] text-stone-400">{col.open} açık · {col.done} bitti · ~{col.minutes} dk</div>
              </div>
            </div>
            <div className="p-2 space-y-1.5 max-h-[420px] overflow-y-auto">
              {col.tasks.map(t => (
                <div key={t.id} className={`border rounded-lg px-2.5 py-2 ${STATUS_CLS[t.status] || STATUS_CLS.pending}`}>
                  <div className="flex items-center gap-1.5 text-xs font-semibold">
                    {t.priority === "urgent" && <Lightning size={12} weight="fill" className="text-rose-500" />}
                    Oda {t.room_number}
                    <span className="ml-auto text-[10px] font-normal opacity-70">{t.status}</span>
                  </div>
                  <div className="text-[10px] opacity-80 mt-0.5 line-clamp-2">{typeof t.notes === "string" ? t.notes : ""}</div>
                </div>
              ))}
              {col.tasks.length === 0 && <p className="text-[11px] text-stone-400 text-center py-4">Görev yok</p>}
            </div>
          </div>
        ))}
        {(board.columns || []).length === 0 && (
          <div className="col-span-full bg-white border border-stone-200 rounded-xl p-8 text-center text-stone-400 text-sm">
            Sistemde "housekeeper" rolünde personel bulunamadı. Kullanıcı yönetiminden kat görevlisi ekleyin.
          </div>
        )}
      </div>

      {(board.unassigned || []).length > 0 && (
        <div className="bg-white border border-rose-200 rounded-xl p-4" data-testid="hkd-unassigned">
          <div className="text-[11px] uppercase tracking-wider text-rose-600 mb-2">Atanmamış görevler ({board.unassigned.length})</div>
          <div className="flex flex-wrap gap-1.5">
            {board.unassigned.map(t => (
              <span key={t.id} className="text-xs px-2 py-1 bg-rose-50 text-rose-700 rounded-lg border border-rose-200">Oda {t.room_number}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, warn, testid }) {
  return (
    <div className={`rounded-xl p-3 ${warn ? "bg-amber-400/20" : "bg-white/10"}`} data-testid={testid}>
      <div className="text-[10px] uppercase tracking-wider text-stone-300">{label}</div>
      <div className="text-xl font-bold mt-0.5">{value}</div>
    </div>
  );
}
