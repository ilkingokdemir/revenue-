import { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const COLS = [
  { id: "ai_status", label: "AI Status", type: "badge" },
  { id: "adr", label: "ADR", type: "money" },
  { id: "occupancy_pct", label: "Occupancy", type: "occ" },
  { id: "pickup", label: "Pickup", type: "num" },
  { id: "min_rate", label: "Min Rate", type: "edit" },
  { id: "floor_rate", label: "Floor (LMF)", type: "edit" },
  { id: "live_pms_rate", label: "Live PMS Rate", type: "money" },
  { id: "current_sell_rate", label: "Current Sell Rate", type: "money" },
  { id: "compset_avg", label: "Compset Avg", type: "money" },
  { id: "ai_rate", label: "Sentinel AI Rate", type: "ai" },
  { id: "target_sell_rate", label: "Target Sell Rate", type: "edit" },
  { id: "pms_override", label: "PMS Override", type: "edit" },
];

const todayISO = () => new Date().toISOString().slice(0, 10);
const fmtMoney = (v) => v == null || v === "" ? "—" : `£${Number(v).toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;
const fmtMoneyDec = (v) => v == null || v === "" ? "—" : `£${Number(v).toFixed(2)}`;

function occColor(pct) {
  if (pct == null) return "text-stone-500";
  if (pct >= 80) return "text-emerald-400";
  if (pct >= 50) return "text-emerald-300";
  if (pct >= 30) return "text-amber-400";
  return "text-red-400";
}

export const MyRatesPanel = ({ properties, activePropertyId }) => {
  const [propertyId, setPropertyId] = useState(activePropertyId || "all");
  const [startDate, setStartDate] = useState(todayISO());
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  // Pending edits keyed by `${date}::${field}` -> value
  const [pending, setPending] = useState({});
  const [visibleRows, setVisibleRows] = useState(() => COLS.filter(c => c.id !== "occupancy_pct").map(c => c.id));
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (activePropertyId && activePropertyId !== propertyId) setPropertyId(activePropertyId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activePropertyId]);

  const reload = useCallback(async () => {
    setLoading(true);
    setPending({});
    try {
      const r = await axios.get(`${API}/rates/grid/${propertyId}`, {
        params: { start_date: startDate, days },
        withCredentials: true,
      });
      setData(r.data);
    } catch (e) {
      console.error(e);
      toast.error("Rate grid yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId, startDate, days]);

  useEffect(() => { reload(); }, [reload]);

  const pendingCount = Object.keys(pending).length;
  const editPending = (date, field, value) => {
    const key = `${date}::${field}`;
    setPending(p => {
      const next = { ...p };
      if (value === "" || value == null) delete next[key];
      else next[key] = value;
      return next;
    });
  };

  async function submitChanges() {
    if (pendingCount === 0) return;
    setSubmitting(true);
    try {
      const byDate = {};
      Object.entries(pending).forEach(([k, v]) => {
        const [d, f] = k.split("::");
        byDate[d] = { ...(byDate[d] || {}), date: d, [f]: v };
      });
      const changes = Object.values(byDate);
      const r = await axios.post(`${API}/rates/grid/override`,
        { property_id: propertyId, changes }, { withCredentials: true });
      toast.success(`${r.data.saved} değişiklik kaydedildi`);
      // Push to PMS sync queue
      const dates = Object.keys(byDate);
      await axios.post(`${API}/rates/grid/submit-to-pms`,
        { property_id: propertyId, dates }, { withCredentials: true });
      toast.success(`${dates.length} gün PMS+OTA kuyruğuna gönderildi`);
      setPending({});
      reload();
    } catch (e) {
      toast.error("Gönderim başarısız: " + (e?.response?.data?.detail || e.message));
    } finally {
      setSubmitting(false);
    }
  }

  const visibleCols = useMemo(() => COLS.filter(c => visibleRows.includes(c.id)), [visibleRows]);
  const rows = data?.rows || [];

  return (
    <div className="bg-stone-950 text-stone-100 min-h-screen -m-6 p-6" data-testid="my-rates-panel">
      {/* Top filter bar */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6 pb-4 border-b border-stone-800">
        <Field label="HOTEL">
          <select
            value={propertyId}
            onChange={e => setPropertyId(e.target.value)}
            className="w-full bg-stone-900 border border-stone-700 rounded px-3 py-2 text-sm"
            data-testid="rates-property-select"
          >
            <option value="all">Tüm oteller</option>
            {(properties || []).map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </Field>
        <Field label="START DATE">
          <input
            type="date"
            value={startDate}
            onChange={e => setStartDate(e.target.value)}
            className="w-full bg-stone-900 border border-stone-700 rounded px-3 py-2 text-sm"
            data-testid="rates-start-date"
          />
        </Field>
        <Field label="NIGHTS">
          <select
            value={days}
            onChange={e => setDays(Number(e.target.value))}
            className="w-full bg-stone-900 border border-stone-700 rounded px-3 py-2 text-sm"
            data-testid="rates-nights"
          >
            <option value={14}>14 Gece</option>
            <option value={30}>30 Gece</option>
            <option value={60}>60 Gece</option>
            <option value={90}>90 Gece</option>
            <option value={180}>180 Gece</option>
            <option value={365}>365 Gece</option>
          </select>
        </Field>
        <div className="flex items-end gap-2">
          <button
            onClick={reload}
            disabled={loading}
            className="px-4 py-2 rounded bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium disabled:opacity-50"
            data-testid="rates-load-btn"
          >
            {loading ? "Yükleniyor…" : "Load Rates"}
          </button>
        </div>
        <div className="flex items-end justify-end">
          <button
            onClick={submitChanges}
            disabled={pendingCount === 0 || submitting}
            className={`px-5 py-2 rounded text-sm font-semibold transition ${
              pendingCount > 0
                ? "bg-amber-500 text-stone-900 hover:bg-amber-400"
                : "bg-stone-800 text-stone-500 cursor-not-allowed"
            }`}
            data-testid="rates-submit-btn"
          >
            {submitting ? "Gönderiliyor…" : pendingCount > 0
              ? `🔒 Submit ${pendingCount} Change(s)`
              : "🔒 Submit 0 Change(s)"}
          </button>
        </div>
      </div>

      {/* Stats strip */}
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
          <Stat label="Avg occupancy" value={`${data.stats.avg_occupancy_pct}%`}
            color={data.stats.avg_occupancy_pct < 30 ? "text-red-400" : "text-emerald-400"} />
          <Stat label="Min rate days"
            value={data.stats.min_rate_days}
            color={data.stats.min_rate_days > 5 ? "text-red-400" : "text-emerald-400"}
            testId="rates-min-rate-days" />
          <Stat label="Pickup (24h)" value={`+${data.stats.total_pickup}`} color="text-cyan-400" />
          <Stat label="Default rate" value={fmtMoney(data.default_rate)} color="text-stone-300" />
        </div>
      )}

      {/* Row visibility toggles */}
      <div className="flex items-center gap-2 mb-4 flex-wrap text-xs">
        <span className="text-stone-500 font-medium uppercase tracking-wider">Row visibility:</span>
        {COLS.map(c => {
          const on = visibleRows.includes(c.id);
          return (
            <button
              key={c.id}
              onClick={() => setVisibleRows(rs => on ? rs.filter(x => x !== c.id) : [...rs, c.id])}
              className={`px-2.5 py-1 rounded-full border text-xs transition ${
                on ? "bg-emerald-500/20 border-emerald-500/60 text-emerald-300"
                   : "bg-stone-900 border-stone-700 text-stone-500"
              }`}
              data-testid={`row-toggle-${c.id}`}
            >
              {c.label}
            </button>
          );
        })}
      </div>

      {/* Grid */}
      <div className="overflow-x-auto rounded-lg border border-stone-800 bg-stone-900/50">
        <table className="text-xs">
          <thead className="bg-stone-900 sticky top-0">
            <tr className="text-stone-400">
              <th className="text-left px-3 py-2 sticky left-0 bg-stone-900 z-10 min-w-[170px]">METRIC</th>
              {rows.map(r => {
                const dt = new Date(r.date);
                const isWeekend = ["Sat", "Sun"].includes(r.dow);
                return (
                  <th key={r.date} className={`px-2 py-2 min-w-[78px] text-center ${isWeekend ? "text-emerald-400" : ""}`}>
                    <div className="text-[10px] uppercase">{dt.toLocaleDateString("en-GB", { month: "short" })}</div>
                    <div className="text-[10px] uppercase opacity-70">{r.dow}</div>
                    <div className="font-bold text-base mt-0.5">{dt.getDate()}</div>
                    <div className={`text-[10px] font-semibold mt-0.5 ${occColor(r.occupancy_pct)}`} data-testid={`header-occ-${r.date}`}>
                      {r.occupancy_pct != null ? `${Math.round(r.occupancy_pct)}%` : "—"}
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {visibleCols.map(col => (
              <tr key={col.id} className="border-t border-stone-800/60 hover:bg-stone-900/40">
                <td className="px-3 py-2.5 sticky left-0 bg-stone-950 text-stone-300 font-medium">{col.label}</td>
                {rows.map(r => (
                  <td key={r.date} className="px-1 py-1 text-center">
                    <Cell row={r} col={col} pending={pending} editPending={editPending} />
                  </td>
                ))}
              </tr>
            ))}
            {rows.length === 0 && !loading && (
              <tr>
                <td colSpan={1 + rows.length} className="text-center py-12 text-stone-500">
                  Veri yok. "Load Rates" butonuna tıklayın.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <p className="text-stone-500 text-xs mt-4 text-center">
        ⓘ 'PMS Override' veya 'Target Sell Rate' alanlarına tıklayıp manuel fiyat girebilirsiniz · Renkli alanlar pending değişiklik ·
        Submit ile PMS+OTA kuyruğuna gönderilir · Live PMS sync active
      </p>
    </div>
  );
};

function Cell({ row, col, pending, editPending }) {
  const key = `${row.date}::${col.id}`;
  const pendingVal = pending[key];
  const value = pendingVal !== undefined ? pendingVal : row[col.id];
  const isPending = pendingVal !== undefined;

  if (col.type === "badge") {
    return (
      <span className={`inline-block px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase tracking-wider ${
        value === "sentinel" ? "text-emerald-400" : "text-amber-400"
      }`}>
        {value || "—"}
      </span>
    );
  }
  if (col.type === "occ") {
    return <span className={`font-semibold ${occColor(value)}`}>{value != null ? `${value}%` : "—"}</span>;
  }
  if (col.type === "money") {
    return <span className="text-stone-300">{fmtMoney(value)}</span>;
  }
  if (col.type === "num") {
    const n = Number(value || 0);
    return <span className={n > 0 ? "text-cyan-400 font-semibold" : "text-stone-600"}>{n > 0 ? `+${n}` : "—"}</span>;
  }
  if (col.type === "ai") {
    return <span className="text-emerald-400 font-semibold">{fmtMoney(value)}</span>;
  }
  if (col.type === "edit") {
    return (
      <input
        type="number"
        value={value ?? ""}
        onChange={e => editPending(row.date, col.id, e.target.value)}
        placeholder="—"
        className={`w-full px-1 py-0.5 rounded bg-transparent text-center text-stone-300 placeholder-stone-700 outline-none ${
          isPending ? "ring-2 ring-amber-500 bg-amber-500/10 text-amber-200" : "hover:bg-stone-800"
        }`}
        data-testid={`cell-${col.id}-${row.date}`}
      />
    );
  }
  return <span>{value ?? "—"}</span>;
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-[10px] uppercase tracking-wider text-stone-500 mb-1.5">{label}</label>
      {children}
    </div>
  );
}

function Stat({ label, value, color, testId }) {
  return (
    <div className="rounded-lg bg-stone-900/60 border border-stone-800 px-4 py-3" data-testid={testId}>
      <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-1">{label}</div>
      <div className={`text-xl font-semibold ${color || "text-stone-200"}`}>{value}</div>
    </div>
  );
}

export default MyRatesPanel;
