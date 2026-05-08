import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  Notebook, Plus, ArrowsClockwise, CheckCircle, WarningCircle, Clock,
  User, CaretRight, Note,
} from "@phosphor-icons/react";
import { AlertTriangle, Send, Shield, FileText } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TYPE_CONFIG = {
  note: { label: "Note", color: "bg-blue-100 text-blue-700", icon: "📝" },
  incident: { label: "Incident", color: "bg-red-100 text-red-700", icon: "🚨" },
  vip: { label: "VIP", color: "bg-amber-100 text-amber-700", icon: "👑" },
  handover: { label: "Handover", color: "bg-purple-100 text-purple-700", icon: "🔄" },
  complaint: { label: "Complaint", color: "bg-orange-100 text-orange-700", icon: "⚠️" },
  request: { label: "Request", color: "bg-emerald-100 text-emerald-700", icon: "📩" },
};

const SHIFT_CONFIG = {
  morning: { label: "Morning (6AM-2PM)", color: "bg-amber-50 text-amber-700 border-amber-200" },
  afternoon: { label: "Afternoon (2PM-10PM)", color: "bg-blue-50 text-blue-700 border-blue-200" },
  night: { label: "Night (10PM-6AM)", color: "bg-indigo-50 text-indigo-700 border-indigo-200" },
};

export function LogbookPanel({ properties, activePropertyId }) {
  const [entries, setEntries] = useState([]);
  const [handovers, setHandovers] = useState([]);
  const [tab, setTab] = useState("entries");
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);
  const [showHandover, setShowHandover] = useState(false);
  const [filterShift, setFilterShift] = useState("");
  const [filterType, setFilterType] = useState("");
  const [newEntry, setNewEntry] = useState({ type: "note", title: "", content: "", priority: "normal", room_number: "", guest_name: "", follow_up_required: false });
  const [handoverData, setHandoverData] = useState({ summary: "", key_items: "", pending_issues: "", to_shift: "afternoon" });

  const propertyId = (activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "aldgate-flats");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterShift) params.set("shift", filterShift);
      const [ent, ho] = await Promise.all([
        axios.get(`${API}/logbook/entries/${propertyId}?${params}`),
        axios.get(`${API}/logbook/shift-handovers/${propertyId}`),
      ]);
      setEntries(ent.data);
      setHandovers(ho.data);
    } catch (e) {}
    finally { setLoading(false); }
  }, [propertyId, filterShift]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const createEntry = async () => {
    if (!newEntry.title) return toast.error("Title required");
    try {
      await axios.post(`${API}/logbook/entries`, { ...newEntry, property_id: propertyId });
      toast.success("Entry added"); setShowNew(false);
      setNewEntry({ type: "note", title: "", content: "", priority: "normal", room_number: "", guest_name: "", follow_up_required: false });
      fetchData();
    } catch (e) { toast.error("Failed"); }
  };

  const resolveEntry = async (id) => {
    await axios.put(`${API}/logbook/entries/${id}`, { status: "resolved" });
    toast.success("Resolved"); fetchData();
  };

  const createHandover = async () => {
    try {
      await axios.post(`${API}/logbook/shift-handover`, {
        property_id: propertyId, ...handoverData,
        key_items: handoverData.key_items.split("\n").filter(Boolean),
        pending_issues: handoverData.pending_issues.split("\n").filter(Boolean),
      });
      toast.success("Handover created"); setShowHandover(false);
      setHandoverData({ summary: "", key_items: "", pending_issues: "", to_shift: "afternoon" });
      fetchData();
    } catch (e) { toast.error("Failed"); }
  };

  const filteredEntries = filterType ? entries.filter(e => e.type === filterType) : entries;

  return (
    <div className="h-full flex flex-col" data-testid="logbook-panel">
      <div className="border-b border-stone-200 bg-white px-6 py-4 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-teal-600 flex items-center justify-center"><Notebook size={18} className="text-white" weight="fill" /></div>
          <div><h2 className="text-lg font-bold text-stone-900" style={{ fontFamily: "Outfit, sans-serif" }}>Duty Manager Logbook</h2><p className="text-[11px] text-stone-500">Shift notes, incidents, VIP tracking & handovers</p></div>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowNew(true)} className="text-xs px-3 py-2 bg-teal-600 text-white rounded-xl font-bold hover:bg-teal-700 flex items-center gap-1" data-testid="new-entry-btn"><Plus size={12} /> New Entry</button>
          <button onClick={() => setShowHandover(true)} className="text-xs px-3 py-2 bg-purple-600 text-white rounded-xl font-bold hover:bg-purple-700 flex items-center gap-1" data-testid="handover-btn"><Send size={12} /> Shift Handover</button>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white border-b border-stone-200 px-6 py-2.5 flex items-center gap-2 flex-shrink-0">
        <Select value={filterShift || "all"} onValueChange={v => setFilterShift(v === "all" ? "" : v)}>
          <SelectTrigger className="h-8 w-36 text-xs"><SelectValue placeholder="All Shifts" /></SelectTrigger>
          <SelectContent><SelectItem value="all">All Shifts</SelectItem><SelectItem value="morning">Morning</SelectItem><SelectItem value="afternoon">Afternoon</SelectItem><SelectItem value="night">Night</SelectItem></SelectContent>
        </Select>
        <div className="flex gap-1">
          <button onClick={() => setFilterType("")} className={`text-[10px] px-2 py-1 rounded-full font-bold ${!filterType ? "bg-teal-600 text-white" : "bg-stone-100 text-stone-500"}`}>All</button>
          {Object.entries(TYPE_CONFIG).map(([k, v]) => (
            <button key={k} onClick={() => setFilterType(filterType === k ? "" : k)}
              className={`text-[10px] px-2 py-1 rounded-full font-bold ${filterType === k ? v.color : "bg-stone-100 text-stone-500"}`}>{v.icon} {v.label}</button>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-stone-200 px-6 flex gap-1 flex-shrink-0">
        {[
          { id: "entries", label: `Entries (${entries.length})` },
          { id: "handovers", label: `Handovers (${handovers.length})` },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} className={`px-4 py-2.5 text-xs font-semibold border-b-[3px] transition-all ${tab === t.id ? "border-teal-600 text-teal-600" : "border-transparent text-stone-400"}`} data-testid={`log-tab-${t.id}`}>{t.label}</button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto bg-stone-50 p-5">
        {tab === "entries" && (
          <div className="max-w-4xl mx-auto space-y-2" data-testid="entries-list">
            {filteredEntries.length === 0 ? (
              <div className="bg-white rounded-2xl border p-10 text-center"><Notebook size={32} className="mx-auto text-stone-300 mb-3" /><p className="text-sm text-stone-500">No entries</p></div>
            ) : filteredEntries.map(e => {
              const tc = TYPE_CONFIG[e.type] || TYPE_CONFIG.note;
              const sc = SHIFT_CONFIG[e.shift] || {};
              return (
                <div key={e.id} className="bg-white rounded-xl border border-stone-200 p-4 shadow-sm" data-testid={`entry-${e.id}`}>
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3">
                      <div className="text-xl mt-0.5">{tc.icon}</div>
                      <div>
                        <div className="text-sm font-bold text-stone-900">{e.title}</div>
                        <div className="text-xs text-stone-600 mt-0.5">{e.content}</div>
                        <div className="flex items-center gap-2 mt-2 text-[10px] text-stone-400">
                          <Badge className={`text-[8px] ${tc.color}`}>{tc.label}</Badge>
                          <Badge className={`text-[8px] border ${sc.color || ""}`}>{e.shift}</Badge>
                          {e.room_number && <span>Room {e.room_number}</span>}
                          {e.guest_name && <span>{e.guest_name}</span>}
                          <span>{e.created_by}</span>
                          <span>{e.created_at?.slice(11, 16)}</span>
                          {e.follow_up_required && <Badge className="text-[8px] bg-red-100 text-red-700">Follow-up</Badge>}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge className={`text-[9px] font-bold ${e.priority === "urgent" ? "bg-red-100 text-red-700" : e.priority === "high" ? "bg-orange-100 text-orange-700" : "bg-stone-100 text-stone-600"}`}>{e.priority}</Badge>
                      {e.status === "open" && (
                        <button onClick={() => resolveEntry(e.id)} className="text-[10px] px-2 py-1 bg-emerald-50 text-emerald-700 rounded-lg font-bold" data-testid={`resolve-${e.id}`}>Resolve</button>
                      )}
                      {e.status === "resolved" && <Badge className="text-[8px] bg-emerald-100 text-emerald-700">Resolved</Badge>}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {tab === "handovers" && (
          <div className="max-w-4xl mx-auto space-y-3" data-testid="handovers-list">
            {handovers.length === 0 ? (
              <div className="bg-white rounded-2xl border p-10 text-center"><Send size={32} className="mx-auto text-stone-300 mb-3" /><p className="text-sm text-stone-500">No handovers yet</p></div>
            ) : handovers.map(h => (
              <div key={h.id} className="bg-white rounded-xl border border-stone-200 p-5 shadow-sm" data-testid={`handover-${h.id}`}>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Badge className={`text-[9px] border ${SHIFT_CONFIG[h.from_shift]?.color || ""}`}>{h.from_shift}</Badge>
                    <CaretRight size={10} className="text-stone-400" />
                    <Badge className={`text-[9px] border ${SHIFT_CONFIG[h.to_shift]?.color || ""}`}>{h.to_shift}</Badge>
                  </div>
                  <span className="text-[10px] text-stone-400">{h.handover_by} · {h.created_at?.slice(0, 16).replace("T", " ")}</span>
                </div>
                <p className="text-xs text-stone-700 mb-2">{h.summary}</p>
                {h.key_items?.length > 0 && (
                  <div className="mb-2"><span className="text-[10px] font-bold text-stone-500">Key Items:</span>
                    <ul className="ml-4 text-xs text-stone-600 list-disc">{h.key_items.map((item, i) => <li key={i}>{item}</li>)}</ul>
                  </div>
                )}
                {h.pending_issues?.length > 0 && (
                  <div><span className="text-[10px] font-bold text-amber-600">Pending Issues:</span>
                    <ul className="ml-4 text-xs text-amber-700 list-disc">{h.pending_issues.map((item, i) => <li key={i}>{item}</li>)}</ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* New Entry */}
      <Dialog open={showNew} onOpenChange={setShowNew}>
        <DialogContent className="max-w-md" data-testid="new-entry-dialog">
          <DialogHeader><DialogTitle>New Logbook Entry</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="flex gap-1.5 flex-wrap">
              {Object.entries(TYPE_CONFIG).map(([k, v]) => (
                <button key={k} onClick={() => setNewEntry(p => ({...p, type: k}))}
                  className={`text-[10px] px-2.5 py-1.5 rounded-lg font-bold ${newEntry.type === k ? v.color : "bg-stone-100 text-stone-500"}`}>{v.icon} {v.label}</button>
              ))}
            </div>
            <Input value={newEntry.title} onChange={e => setNewEntry(p => ({...p, title: e.target.value}))} placeholder="Title" data-testid="entry-title" />
            <Textarea value={newEntry.content} onChange={e => setNewEntry(p => ({...p, content: e.target.value}))} placeholder="Details..." rows={3} />
            <div className="grid grid-cols-2 gap-2">
              <Input value={newEntry.room_number} onChange={e => setNewEntry(p => ({...p, room_number: e.target.value}))} placeholder="Room #" />
              <Input value={newEntry.guest_name} onChange={e => setNewEntry(p => ({...p, guest_name: e.target.value}))} placeholder="Guest name" />
            </div>
            <Select value={newEntry.priority} onValueChange={v => setNewEntry(p => ({...p, priority: v}))}>
              <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="urgent">Urgent</SelectItem><SelectItem value="high">High</SelectItem><SelectItem value="normal">Normal</SelectItem><SelectItem value="low">Low</SelectItem></SelectContent>
            </Select>
            <button onClick={createEntry} className="w-full bg-teal-600 text-white py-2.5 rounded-xl text-sm font-bold" data-testid="save-entry-btn">Save Entry</button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Shift Handover */}
      <Dialog open={showHandover} onOpenChange={setShowHandover}>
        <DialogContent className="max-w-md" data-testid="handover-dialog">
          <DialogHeader><DialogTitle>Shift Handover</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Select value={handoverData.to_shift} onValueChange={v => setHandoverData(p => ({...p, to_shift: v}))}>
              <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="morning">Morning Shift</SelectItem><SelectItem value="afternoon">Afternoon Shift</SelectItem><SelectItem value="night">Night Shift</SelectItem></SelectContent>
            </Select>
            <Textarea value={handoverData.summary} onChange={e => setHandoverData(p => ({...p, summary: e.target.value}))} placeholder="Shift summary..." rows={3} data-testid="handover-summary" />
            <Textarea value={handoverData.key_items} onChange={e => setHandoverData(p => ({...p, key_items: e.target.value}))} placeholder="Key items (one per line)..." rows={3} />
            <Textarea value={handoverData.pending_issues} onChange={e => setHandoverData(p => ({...p, pending_issues: e.target.value}))} placeholder="Pending issues (one per line)..." rows={2} />
            <button onClick={createHandover} className="w-full bg-purple-600 text-white py-2.5 rounded-xl text-sm font-bold" data-testid="save-handover-btn">Submit Handover</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
