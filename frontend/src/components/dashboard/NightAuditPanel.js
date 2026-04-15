import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  CheckCircle, WarningCircle, XCircle, ArrowsClockwise, Moon,
  CurrencyGbp, Bed, Receipt, Broom, ChartBar, Clock, Lightning,
} from "@phosphor-icons/react";
import { Play, History, FileText, TrendingUp, Users, CreditCard, ShoppingCart, Wrench, ChevronRight, Check } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_ICON = {
  pass: { icon: CheckCircle, color: "text-emerald-500", bg: "bg-emerald-50 border-emerald-200", label: "Passed" },
  warning: { icon: WarningCircle, color: "text-amber-500", bg: "bg-amber-50 border-amber-200", label: "Warnings" },
  fail: { icon: XCircle, color: "text-red-500", bg: "bg-red-50 border-red-200", label: "Failed" },
};

export function NightAuditPanel({ properties, activePropertyId }) {
  const [audit, setAudit] = useState(null);
  const [history, setHistory] = useState([]);
  const [running, setRunning] = useState(false);
  const [tab, setTab] = useState("wizard");
  const [showComplete, setShowComplete] = useState(false);
  const [completeNotes, setCompleteNotes] = useState("");
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(true);

  const propertyId = (activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "aldgate-flats");

  const fetchHistory = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/night-audit/history/${propertyId}`); setHistory(data); } catch (e) {}
  }, [propertyId]);

  const fetchLatest = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/night-audit/latest/${propertyId}`);
      if (data && data.id && !data.completed) setAudit(data);
    } catch (e) {}
  }, [propertyId]);

  useEffect(() => { setLoading(true); Promise.all([fetchLatest(), fetchHistory()]).then(() => setLoading(false)); }, [fetchLatest, fetchHistory]);

  const runAudit = async () => {
    setRunning(true); setStep(0); setAudit(null);
    try {
      const { data } = await axios.post(`${API}/night-audit/run/${propertyId}`);
      setAudit(data);
      toast.success("Night audit completed!");
      fetchHistory();
    } catch (e) { toast.error("Audit failed"); }
    finally { setRunning(false); }
  };

  const completeAudit = async () => {
    if (!audit) return;
    try {
      await axios.post(`${API}/night-audit/complete/${audit.id}`, { notes: completeNotes });
      toast.success("Night audit finalized. Date rolled forward.");
      setShowComplete(false); setCompleteNotes(""); setAudit(null);
      fetchHistory();
    } catch (e) { toast.error("Failed"); }
  };

  const a = audit;
  const checks = a?.checks || {};
  const checkOrder = [
    { key: "checkins", label: "Check-in Verification", icon: Users, desc: "Verify all expected arrivals" },
    { key: "checkouts", label: "Check-out Verification", icon: Bed, desc: "Verify all departures completed" },
    { key: "payments", label: "Payment Reconciliation", icon: CreditCard, desc: "Balance charges vs collections" },
    { key: "pos", label: "POS Closure", icon: ShoppingCart, desc: "Verify all F&B orders settled" },
    { key: "housekeeping", label: "Housekeeping Status", icon: Wrench, desc: "Check room readiness" },
  ];

  if (loading) return <div className="flex items-center justify-center h-96"><ArrowsClockwise size={24} className="animate-spin text-indigo-300" /></div>;

  return (
    <div className="h-full flex flex-col" data-testid="night-audit-panel">
      {/* Header */}
      <div className="border-b border-stone-200 bg-white px-6 py-4 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center"><Moon size={18} className="text-white" weight="fill" /></div>
          <div><h2 className="text-lg font-bold text-stone-900" style={{ fontFamily: "Outfit, sans-serif" }}>Night Audit</h2><p className="text-[11px] text-stone-500">End-of-day reconciliation & daily close</p></div>
        </div>
        <div className="flex items-center gap-2">
          {!running && !a && (
            <button onClick={runAudit} className="text-xs px-4 py-2.5 bg-indigo-600 text-white rounded-xl font-bold hover:bg-indigo-700 flex items-center gap-1.5 shadow-md" data-testid="run-audit-btn">
              <Play size={14} /> Run Night Audit
            </button>
          )}
          {a && !a.completed && (
            <button onClick={() => setShowComplete(true)} className="text-xs px-4 py-2.5 bg-emerald-600 text-white rounded-xl font-bold hover:bg-emerald-700 flex items-center gap-1.5" data-testid="complete-audit-btn">
              <Check size={14} /> Complete & Close Day
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-stone-200 px-6 flex gap-1 flex-shrink-0">
        {[
          { id: "wizard", label: "Audit Wizard", icon: Moon },
          { id: "history", label: `History (${history.length})`, icon: History },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold border-b-[3px] transition-all ${tab === t.id ? "border-indigo-600 text-indigo-600" : "border-transparent text-stone-400"}`}
            data-testid={`audit-tab-${t.id}`}><t.icon size={14} /> {t.label}</button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto bg-stone-50 p-6">
        {/* Wizard */}
        {tab === "wizard" && (
          <div className="max-w-4xl mx-auto space-y-5" data-testid="audit-wizard">
            {/* Running Animation */}
            {running && (
              <div className="bg-white rounded-2xl border border-indigo-200 p-10 text-center shadow-sm">
                <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-indigo-100 flex items-center justify-center">
                  <ArrowsClockwise size={28} className="text-indigo-600 animate-spin" />
                </div>
                <h3 className="text-lg font-bold text-stone-900">Running Night Audit...</h3>
                <p className="text-sm text-stone-500 mt-1">Verifying check-ins, payments, POS, housekeeping...</p>
              </div>
            )}

            {/* No Audit Yet */}
            {!running && !a && (
              <div className="bg-white rounded-2xl border border-stone-200 p-10 text-center shadow-sm">
                <Moon size={48} className="mx-auto text-indigo-300 mb-4" weight="fill" />
                <h3 className="text-lg font-bold text-stone-900">Ready for Night Audit</h3>
                <p className="text-sm text-stone-500 mt-1 mb-5">Run the audit to verify all operations and close the day</p>
                <button onClick={runAudit} className="px-6 py-3 bg-indigo-600 text-white rounded-xl font-bold text-sm hover:bg-indigo-700 inline-flex items-center gap-2" data-testid="run-audit-btn-center">
                  <Play size={16} /> Start Night Audit
                </button>
              </div>
            )}

            {/* Audit Results */}
            {a && (
              <>
                {/* Overall Status */}
                <div className={`rounded-2xl border-2 p-6 shadow-sm ${a.overall_status === "pass" ? "bg-emerald-50 border-emerald-300" : a.overall_status === "warning" ? "bg-amber-50 border-amber-300" : "bg-red-50 border-red-300"}`} data-testid="audit-overall">
                  <div className="flex items-center gap-4">
                    {a.overall_status === "pass" ? <CheckCircle size={40} className="text-emerald-500" weight="fill" /> :
                     a.overall_status === "warning" ? <WarningCircle size={40} className="text-amber-500" weight="fill" /> :
                     <XCircle size={40} className="text-red-500" weight="fill" />}
                    <div>
                      <h3 className="text-xl font-black text-stone-900">
                        {a.overall_status === "pass" ? "All Checks Passed" : a.overall_status === "warning" ? "Audit Has Warnings" : "Audit Failed"}
                      </h3>
                      <p className="text-sm text-stone-600">{a.pass_count}/{a.total_checks} checks passed · Audit date: {a.audit_date} · Run by: {a.run_by}</p>
                    </div>
                  </div>
                </div>

                {/* Revenue Summary */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {[
                    { label: "Room Revenue", value: `£${a.revenue?.room_revenue?.toLocaleString()}`, bg: "bg-indigo-50", color: "text-indigo-700" },
                    { label: "F&B Revenue", value: `£${a.revenue?.pos_revenue?.toLocaleString()}`, bg: "bg-emerald-50", color: "text-emerald-700" },
                    { label: "Total Revenue", value: `£${a.revenue?.total_revenue?.toLocaleString()}`, bg: "bg-stone-900", color: "text-white" },
                    { label: "Occupancy", value: `${a.occupancy?.occupancy_pct}%`, bg: "bg-amber-50", color: "text-amber-700" },
                  ].map((kpi, i) => (
                    <div key={i} className={`rounded-2xl p-4 text-center ${kpi.bg}`}>
                      <div className={`text-2xl font-black ${kpi.color}`}>{kpi.value}</div>
                      <div className={`text-[10px] font-semibold ${kpi.color} opacity-70`}>{kpi.label}</div>
                    </div>
                  ))}
                </div>

                {/* Occupancy KPIs */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-white rounded-xl border border-stone-200 p-3 text-center">
                    <div className="text-lg font-black text-stone-800">{a.occupancy?.occupied}/{a.occupancy?.total_rooms}</div>
                    <div className="text-[9px] text-stone-400 font-semibold">Occupied / Total</div>
                  </div>
                  <div className="bg-white rounded-xl border border-stone-200 p-3 text-center">
                    <div className="text-lg font-black text-blue-600">£{a.occupancy?.adr}</div>
                    <div className="text-[9px] text-stone-400 font-semibold">ADR</div>
                  </div>
                  <div className="bg-white rounded-xl border border-stone-200 p-3 text-center">
                    <div className="text-lg font-black text-purple-600">£{a.occupancy?.revpar}</div>
                    <div className="text-[9px] text-stone-400 font-semibold">RevPAR</div>
                  </div>
                </div>

                {/* Individual Checks */}
                <div className="space-y-3">
                  {checkOrder.map((check, idx) => {
                    const c = checks[check.key] || {};
                    const si = STATUS_ICON[c.status] || STATUS_ICON.warning;
                    const StatusIcon = si.icon;
                    return (
                      <motion.div key={check.key} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: idx * 0.1 }}
                        className={`bg-white rounded-2xl border-2 overflow-hidden shadow-sm ${si.bg}`} data-testid={`check-${check.key}`}>
                        <div className="px-5 py-4 flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${c.status === "pass" ? "bg-emerald-100" : "bg-amber-100"}`}>
                              <check.icon size={18} className={c.status === "pass" ? "text-emerald-600" : "text-amber-600"} />
                            </div>
                            <div>
                              <div className="text-sm font-bold text-stone-900">{check.label}</div>
                              <div className="text-[11px] text-stone-500">{check.desc}</div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <StatusIcon size={20} className={si.color} weight="fill" />
                            <Badge className={`text-[9px] font-bold ${c.status === "pass" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>{si.label}</Badge>
                          </div>
                        </div>
                        {/* Check Details */}
                        <div className="px-5 pb-4 border-t border-stone-100 pt-3">
                          {check.key === "checkins" && (
                            <div className="grid grid-cols-3 gap-2 text-xs text-center">
                              <div className="bg-stone-50 rounded-lg p-2"><span className="font-bold text-stone-800">{c.expected}</span><div className="text-[9px] text-stone-400">Expected</div></div>
                              <div className="bg-emerald-50 rounded-lg p-2"><span className="font-bold text-emerald-700">{c.actual}</span><div className="text-[9px] text-stone-400">Checked In</div></div>
                              <div className={`rounded-lg p-2 ${c.no_shows > 0 ? "bg-red-50" : "bg-stone-50"}`}><span className={`font-bold ${c.no_shows > 0 ? "text-red-600" : "text-stone-800"}`}>{c.no_shows}</span><div className="text-[9px] text-stone-400">No-Shows</div></div>
                            </div>
                          )}
                          {check.key === "checkouts" && (
                            <div className="grid grid-cols-3 gap-2 text-xs text-center">
                              <div className="bg-stone-50 rounded-lg p-2"><span className="font-bold text-stone-800">{c.expected}</span><div className="text-[9px] text-stone-400">Expected</div></div>
                              <div className="bg-emerald-50 rounded-lg p-2"><span className="font-bold text-emerald-700">{c.actual}</span><div className="text-[9px] text-stone-400">Checked Out</div></div>
                              <div className={`rounded-lg p-2 ${c.overstays > 0 ? "bg-amber-50" : "bg-stone-50"}`}><span className={`font-bold ${c.overstays > 0 ? "text-amber-600" : "text-stone-800"}`}>{c.overstays}</span><div className="text-[9px] text-stone-400">Overstays</div></div>
                            </div>
                          )}
                          {check.key === "payments" && (
                            <div className="grid grid-cols-3 gap-2 text-xs text-center">
                              <div className="bg-emerald-50 rounded-lg p-2"><span className="font-bold text-emerald-700">£{c.total_paid}</span><div className="text-[9px] text-stone-400">Collected ({c.paid_count})</div></div>
                              <div className={`rounded-lg p-2 ${c.total_unpaid > 0 ? "bg-amber-50" : "bg-stone-50"}`}><span className={`font-bold ${c.total_unpaid > 0 ? "text-amber-600" : "text-stone-800"}`}>£{c.total_unpaid}</span><div className="text-[9px] text-stone-400">Unpaid ({c.unpaid_count})</div></div>
                              <div className="bg-indigo-50 rounded-lg p-2"><span className="font-bold text-indigo-700">£{c.total_room_revenue}</span><div className="text-[9px] text-stone-400">Room Revenue</div></div>
                            </div>
                          )}
                          {check.key === "pos" && (
                            <div className="grid grid-cols-4 gap-2 text-xs text-center">
                              <div className="bg-stone-50 rounded-lg p-2"><span className="font-bold">{c.total_orders}</span><div className="text-[9px] text-stone-400">Total</div></div>
                              <div className="bg-emerald-50 rounded-lg p-2"><span className="font-bold text-emerald-700">{c.paid_orders}</span><div className="text-[9px] text-stone-400">Paid</div></div>
                              <div className={`rounded-lg p-2 ${c.unpaid_orders > 0 ? "bg-amber-50" : "bg-stone-50"}`}><span className={`font-bold ${c.unpaid_orders > 0 ? "text-amber-600" : "text-stone-800"}`}>{c.unpaid_orders}</span><div className="text-[9px] text-stone-400">Unpaid</div></div>
                              <div className="bg-indigo-50 rounded-lg p-2"><span className="font-bold text-indigo-700">£{c.revenue}</span><div className="text-[9px] text-stone-400">Revenue</div></div>
                            </div>
                          )}
                          {check.key === "housekeeping" && (
                            <div className="grid grid-cols-4 gap-2 text-xs text-center">
                              <div className={`rounded-lg p-2 ${c.dirty_rooms > 0 ? "bg-red-50" : "bg-emerald-50"}`}><span className={`font-bold ${c.dirty_rooms > 0 ? "text-red-600" : "text-emerald-700"}`}>{c.dirty_rooms}</span><div className="text-[9px] text-stone-400">Dirty</div></div>
                              <div className="bg-stone-50 rounded-lg p-2"><span className="font-bold">{c.out_of_order_rooms}</span><div className="text-[9px] text-stone-400">OOO</div></div>
                              <div className={`rounded-lg p-2 ${c.pending_tasks > 0 ? "bg-amber-50" : "bg-stone-50"}`}><span className={`font-bold ${c.pending_tasks > 0 ? "text-amber-600" : "text-stone-800"}`}>{c.pending_tasks}</span><div className="text-[9px] text-stone-400">Tasks</div></div>
                              <div className="bg-stone-50 rounded-lg p-2"><span className="font-bold">{c.open_maintenance}</span><div className="text-[9px] text-stone-400">Maintenance</div></div>
                            </div>
                          )}
                          {/* Warning Details */}
                          {c.no_show_list?.length > 0 && (
                            <div className="mt-2 space-y-1">{c.no_show_list.map((ns, i) => (
                              <div key={i} className="text-[10px] flex items-center justify-between bg-red-50 rounded-lg px-3 py-1.5">
                                <span className="text-red-700 font-medium">{ns.ref} — {ns.guest}</span><span className="text-red-600 font-bold">£{ns.amount}</span>
                              </div>
                            ))}</div>
                          )}
                          {c.unpaid_list?.length > 0 && (
                            <div className="mt-2 space-y-1">{c.unpaid_list.slice(0, 5).map((u, i) => (
                              <div key={i} className="text-[10px] flex items-center justify-between bg-amber-50 rounded-lg px-3 py-1.5">
                                <span className="text-amber-700 font-medium">{u.ref || u.number} — {u.guest || u.outlet}</span><span className="text-amber-600 font-bold">£{u.amount}</span>
                              </div>
                            ))}</div>
                          )}
                        </div>
                      </motion.div>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        )}

        {/* History */}
        {tab === "history" && (
          <div className="max-w-4xl mx-auto space-y-3" data-testid="audit-history">
            {history.length === 0 ? (
              <div className="bg-white rounded-2xl border border-stone-200 p-10 text-center">
                <History size={32} className="mx-auto text-stone-300 mb-3" />
                <p className="text-sm text-stone-500">No audit history</p>
              </div>
            ) : history.map(h => {
              const si = STATUS_ICON[h.overall_status] || STATUS_ICON.warning;
              const StatusIcon = si.icon;
              return (
                <div key={h.id} className="bg-white rounded-2xl border border-stone-200 p-4 shadow-sm flex items-center justify-between" data-testid={`history-${h.id}`}>
                  <div className="flex items-center gap-3">
                    <StatusIcon size={22} className={si.color} weight="fill" />
                    <div>
                      <div className="text-sm font-bold text-stone-900">{h.audit_date}</div>
                      <div className="text-[11px] text-stone-500">
                        {h.pass_count}/{h.total_checks} passed · Revenue: £{h.revenue?.total_revenue?.toLocaleString()} · Occupancy: {h.occupancy?.occupancy_pct}%
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge className={`text-[9px] font-bold ${si.bg}`}>{si.label}</Badge>
                    {h.completed && <Badge className="text-[9px] bg-emerald-100 text-emerald-700 font-bold">Closed</Badge>}
                    <span className="text-[10px] text-stone-400">{h.run_by?.split("@")[0]}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Complete Audit Dialog */}
      <Dialog open={showComplete} onOpenChange={setShowComplete}>
        <DialogContent className="max-w-sm" data-testid="complete-dialog">
          <DialogHeader><DialogTitle className="flex items-center gap-2"><Moon size={16} className="text-indigo-600" weight="fill" /> Complete Night Audit</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <p className="text-xs text-stone-500">Completing the audit will finalize today's figures and roll the date forward. Add any shift notes below.</p>
            <Textarea value={completeNotes} onChange={e => setCompleteNotes(e.target.value)} placeholder="Shift notes, handover items, issues to follow up..." rows={4} data-testid="audit-notes" />
            <button onClick={completeAudit} className="w-full bg-emerald-600 text-white py-3 rounded-xl text-sm font-bold hover:bg-emerald-700 flex items-center justify-center gap-2" data-testid="confirm-complete-btn">
              <Check size={16} /> Complete & Close Day
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
