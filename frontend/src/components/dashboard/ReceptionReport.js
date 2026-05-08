import { useState, useEffect } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { RefreshCw, BookOpen, LogIn, LogOut, XCircle, ClipboardList, Calendar } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const ReceptionReport = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [start, setStart] = useState(() => { const d = new Date(); d.setDate(d.getDate() - 7); return d.toISOString().slice(0, 10); });
  const [end, setEnd] = useState(() => new Date().toISOString().slice(0, 10));
  const pid = propertyId || "all";

  useEffect(() => {
    setLoading(true);
    axios.get(`${API}/operations/reception-report/${pid}?start=${start}&end=${end}`)
      .then(r => { setData(r.data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [pid, start, end]);

  if (loading || !data) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading...</div>;

  const k = data.kpis;

  return (
    <div className="space-y-5" data-testid="reception-report">
      {/* Header + Date Range */}
      <div className="flex items-center justify-between">
        <h2 className="text-base font-bold text-stone-800 flex items-center gap-2" data-testid="reception-title"><ClipboardList className="w-5 h-5 text-stone-500" />Reception Report</h2>
        <div className="flex items-center gap-2">
          <input type="date" value={start} onChange={e => setStart(e.target.value)} className="border border-stone-200 rounded-lg px-2 py-1 text-xs" />
          <span className="text-xs text-stone-400">to</span>
          <input type="date" value={end} onChange={e => setEnd(e.target.value)} className="border border-stone-200 rounded-lg px-2 py-1 text-xs" />
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-5 gap-3" data-testid="reception-kpis">
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center"><BookOpen className="w-5 h-5 mx-auto mb-1 text-blue-600" /><p className="text-2xl font-black text-blue-700">{k.bookings_created}</p><p className="text-[9px] text-blue-500">Bookings Created</p></div>
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center"><LogIn className="w-5 h-5 mx-auto mb-1 text-emerald-600" /><p className="text-2xl font-black text-emerald-700">{k.check_ins}</p><p className="text-[9px] text-emerald-500">Check-ins</p></div>
        <div className="bg-violet-50 border border-violet-200 rounded-xl p-4 text-center"><LogOut className="w-5 h-5 mx-auto mb-1 text-violet-600" /><p className="text-2xl font-black text-violet-700">{k.check_outs}</p><p className="text-[9px] text-violet-500">Check-outs</p></div>
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-center"><XCircle className="w-5 h-5 mx-auto mb-1 text-red-600" /><p className="text-2xl font-black text-red-700">{k.cancellations}</p><p className="text-[9px] text-red-500">Cancellations</p></div>
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-center"><Calendar className="w-5 h-5 mx-auto mb-1 text-amber-600" /><p className="text-2xl font-black text-amber-700">{k.routine_runs}</p><p className="text-[9px] text-amber-500">Routine Runs</p></div>
      </div>

      {/* Detail Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Bookings Created */}
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="bookings-created-table">
          <h3 className="text-sm font-bold text-stone-800 mb-2">Bookings Created</h3>
          {data.bookings_created.length === 0 ? <p className="text-xs text-stone-400 py-4 text-center">None</p> : (
            <div className="space-y-1 max-h-[200px] overflow-y-auto">
              {data.bookings_created.map((b, i) => (
                <div key={i} className="flex items-center justify-between text-xs py-1.5 border-b border-stone-50">
                  <span className="font-medium text-stone-700">{b.guest}</span>
                  <div className="flex items-center gap-2"><Badge className="bg-stone-100 text-stone-500 text-[8px]">{b.source}</Badge><span className="text-stone-400 text-[10px]">{b.created_at?.slice(0, 10)}</span></div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Check-ins */}
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="checkins-table">
          <h3 className="text-sm font-bold text-stone-800 mb-2">Check-ins</h3>
          {data.check_ins.length === 0 ? <p className="text-xs text-stone-400 py-4 text-center">None</p> : (
            <div className="space-y-1 max-h-[200px] overflow-y-auto">
              {data.check_ins.map((b, i) => (
                <div key={i} className="flex items-center justify-between text-xs py-1.5 border-b border-stone-50">
                  <span className="font-medium text-stone-700">{b.guest}</span>
                  <span className="text-stone-400 text-[10px]">{b.date}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Check-outs */}
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="checkouts-table">
          <h3 className="text-sm font-bold text-stone-800 mb-2">Check-outs</h3>
          {data.check_outs.length === 0 ? <p className="text-xs text-stone-400 py-4 text-center">None</p> : (
            <div className="space-y-1 max-h-[200px] overflow-y-auto">
              {data.check_outs.map((b, i) => (
                <div key={i} className="flex items-center justify-between text-xs py-1.5 border-b border-stone-50">
                  <span className="font-medium text-stone-700">{b.guest}</span>
                  <span className="text-stone-400 text-[10px]">{b.date}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Cancellations */}
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="cancellations-table">
          <h3 className="text-sm font-bold text-stone-800 mb-2">Cancellations</h3>
          {data.cancellations.length === 0 ? <p className="text-xs text-stone-400 py-4 text-center">None</p> : (
            <div className="space-y-1 max-h-[200px] overflow-y-auto">
              {data.cancellations.map((b, i) => (
                <div key={i} className="text-xs py-1.5 border-b border-stone-50 font-medium text-stone-700">{b.guest}</div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
