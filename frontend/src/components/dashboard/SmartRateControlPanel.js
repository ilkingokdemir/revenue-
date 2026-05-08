/**
 * Smart Rate Control Panel (Iter 165) — bulk editor parity with
 * Mews/Eviivo/Cloudbeds/SiteMinder.
 *
 * Applies: action × target × unit × value × date range → optional
 * rate_plan_ids / room_type_ids scoping.
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Zap, CheckCircle2, Calendar as CalIcon } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TARGETS = [
  { k: "rates",        l: "Rates",        numeric: true  },
  { k: "availability", l: "Availability", numeric: true  },
  { k: "min_los",      l: "Min LOS",      numeric: true  },
  { k: "max_los",      l: "Max LOS",      numeric: true  },
  { k: "cta",          l: "Closed To Arrival",   numeric: false },
  { k: "ctd",          l: "Closed To Departure", numeric: false },
  { k: "stop_sell",    l: "Stop Sell",    numeric: false },
];

const SmartRateControlPanel = ({ activePropertyId }) => {
  const pid = activePropertyId || "aldgate-flats";
  const [action, setAction] = useState("increase");
  const [target, setTarget] = useState("rates");
  const [unit, setUnit] = useState("percent");
  const [value, setValue] = useState(10);
  const [boolValue, setBoolValue] = useState(true);
  const [fromDate, setFromDate] = useState(new Date().toISOString().slice(0, 10));
  const [toDate, setToDate] = useState(new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10));
  const [planIds, setPlanIds] = useState([]);
  const [roomIds, setRoomIds] = useState([]);
  const [lastResult, setLastResult] = useState(null);

  const [plans, setPlans] = useState([]);
  const [rooms, setRooms] = useState([]);

  const load = useCallback(async () => {
    try {
      const [pr, al] = await Promise.all([
        axios.get(`${API}/rate-structure/products?property_id=${pid}`),
        axios.get(`${API}/inventory-allocations/${pid}`),
      ]);
      setPlans(pr.data || []); setRooms(al.data.room_types || []);
    } catch { /* */ }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const targetObj = TARGETS.find(t => t.k === target);
  const isBool = !targetObj?.numeric;

  const apply = async () => {
    const payload = {
      action: isBool ? "set" : action,
      target,
      unit,
      value: isBool ? boolValue : parseFloat(value),
      from_date: fromDate,
      to_date: toDate,
    };
    if (planIds.length) payload.rate_plan_ids = planIds;
    if (roomIds.length) payload.room_type_ids = roomIds;
    try {
      const { data } = await axios.post(`${API}/smart-rate-control/${pid}/apply`, payload);
      toast.success(`Applied to ${data.cells_touched} cells`);
      setLastResult(data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed");
    }
  };

  return (
    <div className="p-6 space-y-5" data-testid="smart-rate-control-panel">
      <div>
        <div className="text-xs text-stone-400">Revenue · Rate Calendar</div>
        <h2 className="text-2xl font-bold flex items-center gap-2"><Zap className="w-6 h-6 text-amber-500" /> Smart Rate Control</h2>
        <p className="text-sm text-stone-500">Rapidly adjust rates, availability and restrictions for a date range.</p>
      </div>

      {/* Builder */}
      <div className="bg-white border border-stone-200 rounded-2xl p-5 shadow-sm">
        <div className="grid grid-cols-[auto,1fr,auto,1fr,auto,1fr,auto,1fr] gap-x-2 gap-y-3 items-center text-sm">
          {!isBool && (<>
            <span className="text-xs text-stone-400 uppercase font-semibold">Type</span>
            <select value={action} onChange={e => setAction(e.target.value)} className="px-3 py-2 border rounded-lg" data-testid="src-action">
              <option value="increase">Increase</option>
              <option value="decrease">Decrease</option>
              <option value="set">Set to</option>
            </select>
          </>)}
          {isBool && <><span></span><span></span></>}

          <span className="text-xs text-stone-400 uppercase font-semibold">to</span>
          <select value={target} onChange={e => setTarget(e.target.value)} className="px-3 py-2 border rounded-lg" data-testid="src-target">
            {TARGETS.map(t => <option key={t.k} value={t.k}>{t.l}</option>)}
          </select>

          {!isBool && (<>
            <span className="text-xs text-stone-400 uppercase font-semibold">by</span>
            <div className="flex items-center gap-2">
              <input type="number" step="0.01" value={value} onChange={e => setValue(e.target.value)} className="w-24 px-3 py-2 border rounded-lg" data-testid="src-value" />
              {target === "rates" && (
                <select value={unit} onChange={e => setUnit(e.target.value)} className="px-3 py-2 border rounded-lg" data-testid="src-unit">
                  <option value="percent">%</option>
                  <option value="flat">£</option>
                </select>
              )}
            </div>
          </>)}
          {isBool && (<>
            <span className="text-xs text-stone-400 uppercase font-semibold">Value</span>
            <select value={String(boolValue)} onChange={e => setBoolValue(e.target.value === "true")} className="px-3 py-2 border rounded-lg" data-testid="src-boolvalue">
              <option value="true">Enable</option>
              <option value="false">Disable</option>
            </select>
          </>)}

          <span className="text-xs text-stone-400 uppercase font-semibold">for</span>
          <div className="flex items-center gap-2">
            <CalIcon className="w-4 h-4 text-stone-400" />
            <input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} className="px-2 py-2 border rounded-lg" data-testid="src-from" />
            <span className="text-xs text-stone-400">→</span>
            <input type="date" value={toDate} onChange={e => setToDate(e.target.value)} className="px-2 py-2 border rounded-lg" data-testid="src-to" />
          </div>
        </div>

        {/* Scoping */}
        <div className="mt-4 pt-4 border-t border-stone-100 grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-semibold text-stone-500 uppercase">Rate Plans (optional — all if empty)</label>
            <select multiple value={planIds} onChange={e => setPlanIds(Array.from(e.target.selectedOptions).map(o => o.value))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm h-24" data-testid="src-plan-ids">
              {plans.map(p => <option key={p.id} value={p.id}>{p.name} · {p.code || p.id.slice(0,6)}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs font-semibold text-stone-500 uppercase">Room Types (optional — all if empty)</label>
            <select multiple value={roomIds} onChange={e => setRoomIds(Array.from(e.target.selectedOptions).map(o => o.value))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm h-24" data-testid="src-room-ids">
              {rooms.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between">
          <div className="text-xs text-stone-400">
            Scope: {roomIds.length ? `${roomIds.length} room type(s)` : "all rooms"} · {planIds.length ? `${planIds.length} plan(s)` : "all plans"} · {fromDate} → {toDate}
          </div>
          <button onClick={apply} className="px-6 py-2.5 bg-emerald-600 text-white rounded-xl text-sm font-semibold flex items-center gap-2 hover:bg-emerald-700" data-testid="src-apply">
            <Zap className="w-4 h-4" /> Apply
          </button>
        </div>
      </div>

      {/* Result */}
      {lastResult && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5 flex items-start gap-3" data-testid="src-result">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 mt-0.5" />
          <div>
            <div className="font-bold text-emerald-900">Bulk update applied</div>
            <div className="text-sm text-emerald-800 mt-1">
              {lastResult.cells_touched} cells updated · {lastResult.dates_in_range} dates in range · {lastResult.rate_plans_in_scope} rate plan(s)
            </div>
            <div className="text-xs text-emerald-700 mt-2">Changes are recorded in the Channel Manager audit log.</div>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm space-y-1">
        <div className="font-semibold text-blue-900">How this works</div>
        <ul className="list-disc list-inside text-blue-800 space-y-0.5 text-xs">
          <li><b>Increase Rates by 10%</b> → raises every cell's rate by 10% of its current value (or base price if empty)</li>
          <li><b>Set Availability to 0</b> → closes inventory on those dates (stop-sell equivalent)</li>
          <li><b>Stop Sell Enable</b> → marks all scoped cells as stop-sold for the date range</li>
          <li>Leave room/plan filters empty to apply to everything under this property</li>
        </ul>
      </div>
    </div>
  );
};

export default SmartRateControlPanel;
