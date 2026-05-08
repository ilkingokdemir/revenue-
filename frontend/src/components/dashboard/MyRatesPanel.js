import { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const COLS = [
  { id: "ai_status", label: "AI Status", type: "badge" },
  { id: "adr", label: "ADR", type: "money" },
  { id: "occupancy_pct", label: "Occupancy", type: "occ" },
  { id: "free_total", label: "Boş Oda", type: "free" },
  { id: "pickup", label: "Pickup", type: "num" },
  { id: "min_rate", label: "Min Rate", type: "edit" },
  { id: "floor_rate", label: "Floor (LMF)", type: "edit" },
  { id: "live_pms_rate", label: "Live PMS Rate", type: "money" },
  { id: "current_sell_rate", label: "Current Sell Rate", type: "money" },
  { id: "compset_avg", label: "Compset Avg", type: "money" },
  { id: "ai_rate", label: "Sentinel AI Rate", type: "ai" },
  { id: "target_sell_rate", label: "Target Sell Rate", type: "edit" },
  { id: "pms_override", label: "PMS Override", type: "edit" },
  { id: "availability", label: "Oda Tipi Müsaitlik", type: "section" },
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
  const [winloss, setWinloss] = useState(null);
  const [loading, setLoading] = useState(false);
  // Pending edits keyed by `${date}::${field}` -> value
  const [pending, setPending] = useState({});
  const [visibleRows, setVisibleRows] = useState(() => COLS.filter(c => c.id !== "occupancy_pct").map(c => c.id));
  const [submitting, setSubmitting] = useState(false);
  const [drawer, setDrawer] = useState(null); // {date}
  const [winlossOpen, setWinlossOpen] = useState(false);

  useEffect(() => {
    if (activePropertyId && activePropertyId !== propertyId) setPropertyId(activePropertyId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activePropertyId]);

  const reload = useCallback(async () => {
    setLoading(true);
    setPending({});
    try {
      const [r, w] = await Promise.all([
        axios.get(`${API}/rates/grid/${propertyId}`, {
          params: { start_date: startDate, days },
          withCredentials: true,
        }),
        axios.get(`${API}/rates/winloss/${propertyId}`, {
          params: { lookback_days: 60 },
          withCredentials: true,
        }).catch(() => ({ data: null })),
      ]);
      setData(r.data);
      setWinloss(w.data);
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
  const roomTypes = data?.room_types || [];
  const showAvail = visibleRows.includes("availability");

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

      {/* AI vs Owner Win/Loss Scoreboard */}
      {winloss?.summary && winloss.summary.total_overrides > 0 && (
        <button
          onClick={() => setWinlossOpen(true)}
          className="w-full mb-5 rounded-xl bg-gradient-to-r from-violet-900/30 to-emerald-900/30 border border-violet-700/40 p-4 hover:border-violet-500 transition text-left"
          data-testid="winloss-tile"
        >
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <div className="text-[10px] uppercase tracking-wider text-violet-400 mb-1">
                ⚔️ AI vs Sahip Performans (son {winloss.lookback_days} gün)
              </div>
              <div className="flex items-center gap-4 text-sm">
                <span className="text-emerald-400">
                  <strong className="text-2xl">{winloss.summary.wins}</strong> kazanç
                </span>
                <span className="text-red-400">
                  <strong className="text-2xl">{winloss.summary.losses}</strong> kayıp
                </span>
                <span className="text-stone-400">
                  <strong className="text-2xl">{winloss.summary.neutrals}</strong> nötr
                </span>
                <span className="text-violet-300 ml-2">
                  Win-rate: <strong>{winloss.summary.win_rate_pct}%</strong>
                </span>
              </div>
            </div>
            <div className="text-right">
              <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-1">
                Sahip kararı vs AI baseline
              </div>
              <div className={`text-2xl font-bold ${winloss.summary.revenue_lift >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {winloss.summary.revenue_lift >= 0 ? "+" : ""}£{winloss.summary.revenue_lift.toLocaleString()}
              </div>
              <div className="text-[10px] text-stone-500">detay için tıklayın →</div>
            </div>
          </div>
        </button>
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
                  <th
                    key={r.date}
                    onClick={() => setDrawer({ date: r.date, propertyId })}
                    className={`px-2 py-2 min-w-[78px] text-center cursor-pointer hover:bg-stone-800/60 ${isWeekend ? "text-emerald-400" : ""}`}
                    data-testid={`date-header-${r.date}`}
                  >
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
            {visibleCols.filter(c => c.id !== "availability").map(col => (
              <tr key={col.id} className="border-t border-stone-800/60 hover:bg-stone-900/40">
                <td className="px-3 py-2.5 sticky left-0 bg-stone-950 text-stone-300 font-medium">{col.label}</td>
                {rows.map(r => (
                  <td key={r.date} className="px-1 py-1 text-center">
                    <Cell row={r} col={col} pending={pending} editPending={editPending} />
                  </td>
                ))}
              </tr>
            ))}
            {/* Per-room-type availability section */}
            {showAvail && roomTypes.length > 0 && (
              <>
                <tr className="border-t-2 border-emerald-700/40 bg-stone-900/60">
                  <td className="px-3 py-2 sticky left-0 bg-stone-900 text-emerald-400 text-[10px] uppercase tracking-wider font-bold" colSpan={1}>
                    🛏 Oda Tipi · Boş / Toplam
                  </td>
                  {rows.map(r => (
                    <td key={r.date} className="px-1 py-1 text-center text-[9px] text-stone-500">
                      {r.in_house}/{data.total_rooms} dolu
                    </td>
                  ))}
                </tr>
                {roomTypes.map(rt => (
                  <tr key={rt.id} className="border-t border-stone-800/40 hover:bg-stone-900/40 text-[11px]">
                    <td className="px-3 py-1.5 sticky left-0 bg-stone-950 text-stone-400">
                      <span className="text-stone-300">{rt.name}</span>
                      <span className="text-stone-600 ml-1">({rt.total})</span>
                    </td>
                    {rows.map(r => {
                      const a = (r.availability || []).find(x => x.room_type_id === rt.id);
                      const free = a ? a.free : rt.total;
                      const pct = rt.total ? free / rt.total : 1;
                      let cls = "text-emerald-400";
                      if (pct === 0) cls = "text-red-400 font-bold";
                      else if (pct < 0.3) cls = "text-amber-400";
                      else if (pct < 0.7) cls = "text-emerald-300";
                      return (
                        <td key={r.date} className="px-1 py-1 text-center">
                          <span className={cls} data-testid={`avail-${rt.id}-${r.date}`}>
                            {free}
                            <span className="text-stone-600 text-[9px]">/{rt.total}</span>
                          </span>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </>
            )}
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
        Submit ile PMS+OTA kuyruğuna gönderilir · Tarih başlığına tıklayarak <strong className="text-emerald-400">Why this rate?</strong> + geçmiş + AI'a bırak
      </p>

      {drawer && (
        <RateDrawer
          date={drawer.date}
          propertyId={drawer.propertyId}
          onClose={() => setDrawer(null)}
          onChanged={() => { setDrawer(null); reload(); }}
        />
      )}

      {winlossOpen && winloss && (
        <WinLossModal data={winloss} onClose={() => setWinlossOpen(false)} />
      )}
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
  if (col.type === "free") {
    const v = Number(row.free_total || 0);
    const cls = v === 0 ? "text-red-400 font-bold" : v < 5 ? "text-amber-400" : "text-emerald-400";
    return <span className={cls}>{v}</span>;
  }
  if (col.type === "section") {
    return <span className="text-stone-600">—</span>;
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

function RateDrawer({ date, propertyId, onClose, onChanged }) {
  const [explain, setExplain] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [releasing, setReleasing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const [e, h] = await Promise.all([
          axios.get(`${API}/rates/grid/explain/${propertyId}/${date}`, { withCredentials: true }),
          axios.get(`${API}/rates/grid/history/${propertyId}/${date}`, { withCredentials: true }),
        ]);
        if (!cancelled) { setExplain(e.data); setHistory(h.data?.history || []); }
      } catch (err) {
        if (!cancelled) toast.error("Drawer yüklenemedi");
      } finally { if (!cancelled) setLoading(false); }
    })();
    return () => { cancelled = true; };
  }, [date, propertyId]);

  async function release() {
    if (!confirm(`${date} için kilidi kaldır ve Sentinel AI'a bırak?`)) return;
    setReleasing(true);
    try {
      await axios.post(`${API}/rates/grid/release/${propertyId}/${date}`, {}, { withCredentials: true });
      toast.success("AI'a bırakıldı");
      onChanged();
    } catch {
      toast.error("İşlem başarısız");
    } finally { setReleasing(false); }
  }

  const ctx = explain?.context || {};
  const isLocked = ctx.is_locked;
  const dt = new Date(date);

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex justify-end" onClick={onClose} data-testid="rate-drawer">
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md bg-stone-950 border-l border-stone-800 h-full overflow-y-auto p-5 space-y-5"
      >
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-stone-100">
              {dt.toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
            </h2>
            <p className="text-xs text-stone-500">
              Lead {ctx.lead_time_days ?? "—"} gün · {ctx.day_of_week}
              {isLocked && (
                <span className="ml-2 inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 text-[10px]">
                  🔒 OWNER LOCKED
                </span>
              )}
            </p>
          </div>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-200 text-xl" data-testid="drawer-close-btn">×</button>
        </div>

        {loading && <div className="text-stone-500 text-sm">Yükleniyor…</div>}

        {/* AI rate + breakdown */}
        {explain && (
          <section className="space-y-3">
            <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/40 p-4">
              <div className="text-[10px] uppercase tracking-wider text-emerald-400 mb-1">Sentinel AI Rate</div>
              <div className="text-3xl font-bold text-emerald-300">£{explain.ai_rate}</div>
              {ctx.owner_override && (
                <div className="text-[11px] text-amber-400 mt-1">Owner override: £{ctx.owner_override}</div>
              )}
            </div>

            {/* Narrative */}
            {explain.narrative && (
              <div className="rounded-xl bg-stone-900 border border-stone-800 p-4">
                <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-2">Why this rate?</div>
                <div className="text-stone-200 text-sm whitespace-pre-line leading-relaxed" data-testid="rate-narrative">
                  {explain.narrative}
                </div>
              </div>
            )}

            {/* Breakdown */}
            <div className="rounded-xl bg-stone-900 border border-stone-800 p-4 space-y-2">
              <div className="text-[10px] uppercase tracking-wider text-stone-500">Sinyaller</div>
              <Sig label={`Compset (${ctx.compset_count || 0} otel)`}
                value={ctx.compset_avg ? `£${ctx.compset_avg}` : "—"}
                sub={ctx.compset_min ? `min £${ctx.compset_min} · max £${ctx.compset_max}` : null} />
              <Sig label="Doluluk" value={`${ctx.occupancy_pct}% (${ctx.in_house}/${ctx.total_rooms})`} />
              <Sig label="Pickup (24s)" value={`+${ctx.pickup_24h}`} color={ctx.pickup_24h > 0 ? "text-cyan-400" : ""} />
              <Sig label="Gün" value={ctx.day_of_week} />
              <Sig label="Lead time" value={`${ctx.lead_time_days} gün`} />
              {ctx.events?.length > 0 && (
                <Sig label="Etkinlik" value={ctx.events.join(", ")} color="text-amber-400" />
              )}
            </div>

            {isLocked && (
              <button
                onClick={release}
                disabled={releasing}
                className="w-full py-3 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-300 font-medium text-sm disabled:opacity-50"
                data-testid="release-to-ai-btn"
              >
                {releasing ? "Bırakılıyor…" : "🤖 AI'a Bırak (kilidi kaldır)"}
              </button>
            )}
          </section>
        )}

        {/* History */}
        <section>
          <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-2">Geçmiş ({history.length})</div>
          {history.length === 0 ? (
            <div className="text-stone-600 text-xs">Henüz değişiklik yok</div>
          ) : (
            <ul className="space-y-2">
              {history.map(h => (
                <li key={h.id} className="rounded-lg bg-stone-900 border border-stone-800 p-3 text-xs"
                    data-testid={`history-${h.id}`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase ${
                      h.action === "release" ? "bg-amber-500/20 text-amber-400"
                                              : "bg-emerald-500/20 text-emerald-400"
                    }`}>
                      {h.action === "release" ? "AI'a bırakıldı" : "Submit"}
                    </span>
                    <span className="text-stone-500">{new Date(h.created_at).toLocaleString("tr-TR")}</span>
                  </div>
                  {h.action !== "release" && (
                    <div className="text-stone-300">
                      {h.previous_rate != null ? <>£{h.previous_rate}</> : <span className="text-stone-500">—</span>}
                      <span className="mx-2 text-stone-500">→</span>
                      <strong className="text-emerald-300">£{h.new_rate}</strong>
                      {h.delta_pct != null && (
                        <span className={`ml-2 text-[10px] ${h.delta_pct > 0 ? "text-emerald-400" : "text-red-400"}`}>
                          {h.delta_pct > 0 ? "+" : ""}{h.delta_pct}%
                        </span>
                      )}
                    </div>
                  )}
                  {h.action === "release" && h.previous_rate && (
                    <div className="text-stone-400">£{h.previous_rate} kilidi kaldırıldı</div>
                  )}
                  <div className="text-stone-500 text-[10px] mt-0.5">{h.by}</div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

function Sig({ label, value, sub, color }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-stone-400">{label}</span>
      <div className="text-right">
        <div className={`font-semibold ${color || "text-stone-200"}`}>{value}</div>
        {sub && <div className="text-[10px] text-stone-500">{sub}</div>}
      </div>
    </div>
  );
}

function WinLossModal({ data, onClose }) {
  const s = data.summary;
  const VERDICT_BADGE = {
    win: "bg-emerald-500/20 text-emerald-400 border-emerald-500/40",
    loss: "bg-red-500/20 text-red-400 border-red-500/40",
    neutral: "bg-stone-500/20 text-stone-400 border-stone-500/40",
  };
  const VERDICT_LABEL = { win: "KAZANÇ", loss: "KAYIP", neutral: "NÖTR" };

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={onClose} data-testid="winloss-modal">
      <div onClick={(e) => e.stopPropagation()}
           className="bg-stone-950 border border-stone-800 rounded-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto p-6 space-y-5">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-xl font-bold text-stone-100">⚔️ AI vs Sahip Performans Raporu</h2>
            <p className="text-xs text-stone-500 mt-1">
              {data.start_date} — {data.end_date} arası, {s.total_overrides} override karşılaştırması
            </p>
          </div>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-200 text-2xl" data-testid="winloss-close-btn">×</button>
        </div>

        {/* KPI cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <KPI label="Kazanç" value={s.wins} color="text-emerald-400" sub={`%${s.win_rate_pct} win-rate`} />
          <KPI label="Kayıp" value={s.losses} color="text-red-400" />
          <KPI label="Nötr" value={s.neutrals} color="text-stone-400" />
          <KPI label="Net Gelir Etkisi" color={s.revenue_lift >= 0 ? "text-emerald-400" : "text-red-400"}
               value={`${s.revenue_lift >= 0 ? "+" : ""}£${s.revenue_lift.toLocaleString()}`}
               sub={`AI olsaydı: £${s.revenue_ai_counterfactual.toLocaleString()}`} />
        </div>

        {/* Best/worst */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {s.biggest_win && (
            <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/30 p-4">
              <div className="text-[10px] uppercase tracking-wider text-emerald-400 mb-1">🏆 En büyük kazanç</div>
              <div className="text-stone-100 font-semibold">{s.biggest_win.date}</div>
              <div className="text-xs text-stone-400 mt-1">
                Sahip £{s.biggest_win.owner_rate} vs AI £{s.biggest_win.ai_rate} ·
                <strong className="text-emerald-300"> +£{s.biggest_win.revenue_delta}</strong>
                <span className="text-stone-500"> ({s.biggest_win.bookings} rez)</span>
              </div>
            </div>
          )}
          {s.biggest_loss && (
            <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4">
              <div className="text-[10px] uppercase tracking-wider text-red-400 mb-1">⚠️ En büyük kayıp</div>
              <div className="text-stone-100 font-semibold">{s.biggest_loss.date}</div>
              <div className="text-xs text-stone-400 mt-1">
                Sahip £{s.biggest_loss.owner_rate} vs AI £{s.biggest_loss.ai_rate} ·
                <strong className="text-red-300"> £{s.biggest_loss.revenue_delta}</strong>
                <span className="text-stone-500"> ({s.biggest_loss.bookings} rez)</span>
              </div>
            </div>
          )}
        </div>

        {/* Detailed table */}
        <div className="rounded-xl border border-stone-800 overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-stone-900 text-stone-500">
              <tr>
                <th className="text-left px-3 py-2">Tarih</th>
                <th className="text-right px-3 py-2">Sahip £</th>
                <th className="text-right px-3 py-2">AI £</th>
                <th className="text-right px-3 py-2">Δ /gece</th>
                <th className="text-right px-3 py-2">Rez</th>
                <th className="text-right px-3 py-2">Doluluk</th>
                <th className="text-right px-3 py-2">Net Gelir Δ</th>
                <th className="text-center px-3 py-2">Sonuç</th>
              </tr>
            </thead>
            <tbody>
              {data.comparisons.length === 0 && (
                <tr><td colSpan={8} className="text-center py-6 text-stone-600">Henüz karşılaştırılabilir kayıt yok</td></tr>
              )}
              {data.comparisons.slice(0, 30).map((c, i) => (
                <tr key={i} className="border-t border-stone-800/60 hover:bg-stone-900/40"
                    data-testid={`winloss-row-${c.date}`}>
                  <td className="px-3 py-2 text-stone-300">{c.date}</td>
                  <td className="px-3 py-2 text-right text-stone-200">£{c.owner_rate}</td>
                  <td className="px-3 py-2 text-right text-emerald-400">£{c.ai_rate}</td>
                  <td className={`px-3 py-2 text-right ${c.delta_per_night > 0 ? "text-emerald-400" : c.delta_per_night < 0 ? "text-red-400" : "text-stone-500"}`}>
                    {c.delta_per_night > 0 ? "+" : ""}£{c.delta_per_night}
                  </td>
                  <td className="px-3 py-2 text-right text-cyan-400">{c.bookings}</td>
                  <td className={`px-3 py-2 text-right ${occColor(c.occupancy_pct)}`}>{c.occupancy_pct}%</td>
                  <td className={`px-3 py-2 text-right font-semibold ${c.revenue_delta > 0 ? "text-emerald-400" : c.revenue_delta < 0 ? "text-red-400" : "text-stone-500"}`}>
                    {c.revenue_delta > 0 ? "+" : ""}£{c.revenue_delta}
                  </td>
                  <td className="px-3 py-2 text-center">
                    <span className={`px-2 py-0.5 rounded text-[9px] font-bold border ${VERDICT_BADGE[c.verdict]}`}>
                      {VERDICT_LABEL[c.verdict]}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="text-stone-500 text-[10px] text-center">
          ⓘ Naive karşılaştırma: AI fiyatı uygulanmış olsaydı aynı talep koşulunda gelir varsayımıyla. Gerçek elastiklik için A/B testi gerekir.
        </p>
      </div>
    </div>
  );
}

function KPI({ label, value, color, sub }) {
  return (
    <div className="rounded-xl bg-stone-900/60 border border-stone-800 p-4">
      <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-1">{label}</div>
      <div className={`text-2xl font-bold ${color || "text-stone-200"}`}>{value}</div>
      {sub && <div className="text-[10px] text-stone-500 mt-1">{sub}</div>}
    </div>
  );
}

export default MyRatesPanel;
