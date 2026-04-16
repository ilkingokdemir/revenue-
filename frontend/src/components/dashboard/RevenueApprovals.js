import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { CheckCircle, XCircle, Eye, Clock } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

export const RevenueApprovals = ({ propertyId }) => {
  const [items, setItems] = useState([]);
  const [counts, setCounts] = useState({});
  const [filter, setFilter] = useState("all");
  const [tab, setTab] = useState("recommendations");

  const load = async () => {
    try {
      const { data } = await axios.get(`${API}/revenue/approvals/${propertyId}?status=${filter}`);
      setItems(data.items);
      setCounts(data.counts);
    } catch { toast.error("Failed"); }
  };
  useEffect(() => { load(); }, [propertyId, filter]);

  const handleAction = async (id, action) => {
    try {
      await axios.put(`${API}/revenue/approvals/${id}/${action}`);
      toast.success(`${action === "accept" ? "Accepted" : "Rejected"}`);
      load();
    } catch { toast.error("Failed"); }
  };

  const tabs = ["Recommendations", "Decisions", "Parity", "Overbooking", "Intents", "Publish Jobs"];

  return (
    <div className="space-y-6" data-testid="rev-approvals">
      <div>
        <h2 className="text-lg font-bold text-stone-800">Approvals & Publish</h2>
        <p className="text-sm text-stone-500">Single hub to Accept → Create Intent → Queue Publish (no silent writes).</p>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-4 text-sm text-emerald-800">
          Recommendations, playbook decisions, parity fixes, overbooking adjustments stay <strong>draft</strong> until accepted here.
        </div>
        <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 text-sm text-blue-800">
          Publish always flows through <strong>intent → job → items</strong> and carries resolver snapshots + applied layers.
        </div>
        <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 text-sm text-stone-700">
          Correlation IDs link every action to audit and delivery logs. Branch scope is enforced.
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-stone-200 overflow-x-auto">
        {tabs.map(t => (
          <button key={t} onClick={() => setTab(t.toLowerCase().replace(/ /g, "-"))}
            className={`px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 -mb-[1px] transition-all ${
              tab === t.toLowerCase().replace(/ /g, "-") ? "text-violet-700 border-violet-500" : "text-stone-400 border-transparent hover:text-stone-600"
            }`}>{t}</button>
        ))}
      </div>

      {/* Status filter */}
      <div className="flex items-center gap-2">
        {["all", "draft", "accepted", "rejected"].map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg capitalize ${filter === f ? "bg-violet-100 text-violet-700" : "text-stone-400 hover:bg-stone-50"}`}>
            {f} {f !== "all" && counts[f] !== undefined ? `(${counts[f]})` : ""}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="border-b bg-stone-50/50">
            <th className="px-4 py-3 text-left text-xs font-semibold text-stone-500">#</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-stone-500">Date</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-stone-500">Room/Rate</th>
            <th className="px-4 py-3 text-center text-xs font-semibold text-stone-500">Current</th>
            <th className="px-4 py-3 text-center text-xs font-semibold text-stone-500">Recommended</th>
            <th className="px-4 py-3 text-center text-xs font-semibold text-stone-500">Status</th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-stone-500">Actions</th>
          </tr></thead>
          <tbody>
            {items.length === 0 ? (
              <tr><td colSpan={7} className="text-center py-12 text-stone-400">
                <Clock className="w-8 h-8 mx-auto mb-2 text-stone-200" />
                <p className="text-sm">No {filter === "all" ? "" : filter} recommendations</p>
                <p className="text-xs text-stone-300 mt-1">Run Smart Pricing to generate recommendations.</p>
              </td></tr>
            ) : items.map(item => (
              <tr key={item.id} className="border-b border-stone-50 hover:bg-stone-50/50">
                <td className="px-4 py-3 text-stone-500 font-mono text-xs">{item.id}</td>
                <td className="px-4 py-3 text-stone-600">{item.date}</td>
                <td className="px-4 py-3 text-stone-700 font-medium">{item.room_type_name}</td>
                <td className="px-4 py-3 text-center text-stone-500">{cur(item.current_rate)}</td>
                <td className="px-4 py-3 text-center font-semibold text-violet-700">{cur(item.recommended_rate)}</td>
                <td className="px-4 py-3 text-center">
                  <Badge className={`text-[10px] ${
                    item.status === "draft" ? "bg-stone-100 text-stone-600" :
                    item.status === "accepted" ? "bg-emerald-100 text-emerald-700" :
                    "bg-red-100 text-red-700"
                  }`}>{item.status}</Badge>
                </td>
                <td className="px-4 py-3 text-right">
                  {item.status === "draft" ? (
                    <div className="flex items-center justify-end gap-1.5">
                      <button onClick={() => handleAction(item.id, "accept")}
                        className="bg-emerald-500 hover:bg-emerald-600 text-white px-3 py-1.5 rounded-lg text-xs font-medium" data-testid={`rev-approve-${item.id}`}>
                        Accept
                      </button>
                      <button onClick={() => handleAction(item.id, "reject")}
                        className="border border-stone-300 text-stone-600 px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-stone-50">
                        Reject
                      </button>
                    </div>
                  ) : (
                    <span className="text-xs text-stone-400">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
