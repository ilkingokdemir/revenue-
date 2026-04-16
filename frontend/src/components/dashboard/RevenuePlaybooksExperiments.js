import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus, Trash2, BookOpen, Zap, FlaskConical } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const RevenuePlaybooks = ({ propertyId }) => {
  const [items, setItems] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", trigger_type: "manual", rules: [{ condition: "Occupancy", value: 80, action: "Increase", by: 10 }] });

  const load = () => { axios.get(`${API}/revenue/playbooks/${propertyId}`).then(r => setItems(r.data.items)).catch(() => toast.error("Failed")); };
  useEffect(() => { load(); }, [propertyId]);

  const addRule = () => setForm(p => ({ ...p, rules: [...p.rules, { condition: "Occupancy", value: 0, action: "Increase", by: 0 }] }));
  const removeRule = (i) => setForm(p => ({ ...p, rules: p.rules.filter((_, idx) => idx !== i) }));
  const updateRule = (i, k, v) => setForm(p => ({ ...p, rules: p.rules.map((r, idx) => idx === i ? { ...r, [k]: v } : r) }));

  const save = async () => {
    if (!form.name) { toast.error("Name required"); return; }
    try { await axios.post(`${API}/revenue/playbooks/${propertyId}`, form); toast.success("Playbook saved"); setShowForm(false); setForm({ name: "", description: "", trigger_type: "manual", rules: [{ condition: "Occupancy", value: 80, action: "Increase", by: 10 }] }); load(); } catch { toast.error("Failed"); }
  };

  const remove = async (id) => { try { await axios.delete(`${API}/revenue/playbooks/${id}`); toast.success("Deleted"); load(); } catch { toast.error("Failed"); } };

  return (
    <div className="space-y-6" data-testid="rev-playbooks">
      <div className="flex items-center justify-between">
        <div><h2 className="text-lg font-bold text-stone-800">Playbooks</h2><p className="text-sm text-stone-500">Build automated pricing rules</p></div>
        <button onClick={() => setShowForm(!showForm)} className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white px-4 py-2 rounded-xl text-sm font-medium" data-testid="rev-new-playbook"><Plus className="w-4 h-4" />Create Playbook</button>
      </div>

      {showForm && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="bg-white border border-stone-200 rounded-2xl p-6">
            <h3 className="text-lg font-bold text-stone-800 mb-4">Playbook Details</h3>
            <div className="space-y-4">
              <div><label className="text-sm font-semibold text-stone-700 block mb-1">Name</label><Input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="Weekend Surge Pricing" data-testid="rev-pb-name" /></div>
              <div><label className="text-sm font-semibold text-stone-700 block mb-1">Description</label><textarea value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))} placeholder="What does this playbook do?" className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm h-24 resize-none" /></div>
              <div><label className="text-sm font-semibold text-stone-700 block mb-1">Trigger Type</label>
                <Select value={form.trigger_type} onValueChange={v => setForm(p => ({ ...p, trigger_type: v }))}>
                  <SelectTrigger className="h-10"><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="manual">Manual</SelectItem><SelectItem value="automatic">Automatic</SelectItem><SelectItem value="scheduled">Scheduled</SelectItem></SelectContent>
                </Select>
              </div>
            </div>
          </div>
          <div className="bg-white border border-stone-200 rounded-2xl p-6">
            <div className="flex items-center justify-between mb-4">
              <div><Badge className="bg-stone-100 text-stone-600 text-xs mb-1">Playbook Studio</Badge><h3 className="text-lg font-bold text-stone-800">Rules</h3></div>
              <button onClick={addRule} className="flex items-center gap-1 bg-emerald-500 hover:bg-emerald-600 text-white px-3 py-1.5 rounded-lg text-xs font-medium"><Plus className="w-3 h-3" />Add Rule</button>
            </div>
            <div className="space-y-4">
              {form.rules.map((rule, i) => (
                <div key={i} className="border border-stone-200 rounded-xl p-4">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm font-bold text-stone-700">Rule {i + 1}</span>
                    {form.rules.length > 1 && <button onClick={() => removeRule(i)} className="text-red-400 hover:text-red-600"><Trash2 className="w-4 h-4" /></button>}
                  </div>
                  <div className="grid grid-cols-4 gap-2">
                    <div><label className="text-[10px] text-stone-400 font-medium">IF</label>
                      <Select value={rule.condition} onValueChange={v => updateRule(i, "condition", v)}>
                        <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
                        <SelectContent><SelectItem value="Occupancy">Occupancy</SelectItem><SelectItem value="ADR">ADR</SelectItem><SelectItem value="Lead Time">Lead Time</SelectItem><SelectItem value="Day of Week">Day of Week</SelectItem></SelectContent>
                      </Select>
                    </div>
                    <div><label className="text-[10px] text-stone-400 font-medium">Value</label><Input type="number" value={rule.value} onChange={e => updateRule(i, "value", Number(e.target.value))} className="h-9" /></div>
                    <div><label className="text-[10px] text-stone-400 font-medium">THEN</label>
                      <Select value={rule.action} onValueChange={v => updateRule(i, "action", v)}>
                        <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
                        <SelectContent><SelectItem value="Increase">Increase</SelectItem><SelectItem value="Decrease">Decrease</SelectItem><SelectItem value="Set to">Set to</SelectItem></SelectContent>
                      </Select>
                    </div>
                    <div><label className="text-[10px] text-stone-400 font-medium">By</label><Input type="number" value={rule.by} onChange={e => updateRule(i, "by", Number(e.target.value))} className="h-9" /></div>
                  </div>
                </div>
              ))}
            </div>
            <div className="flex justify-end mt-4">
              <button onClick={save} className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white px-5 py-2.5 rounded-xl text-sm font-semibold" data-testid="rev-pb-save"><BookOpen className="w-4 h-4" />Save Playbook</button>
            </div>
          </div>
        </div>
      )}

      {items.length === 0 && !showForm ? (
        <div className="text-center py-16 bg-white border border-stone-200 rounded-2xl">
          <BookOpen className="w-12 h-12 text-stone-200 mx-auto mb-3" />
          <p className="font-semibold text-stone-600">No playbooks yet</p>
          <p className="text-sm text-stone-400">Create your first automated pricing playbook</p>
        </div>
      ) : items.map(pb => (
        <div key={pb.id} className="bg-white border border-stone-200 rounded-2xl p-5 flex items-center justify-between" data-testid={`rev-pb-${pb.id}`}>
          <div>
            <div className="flex items-center gap-2"><span className="font-bold text-stone-800">{pb.name}</span><Badge className={`text-[10px] ${pb.status === "active" ? "bg-emerald-100 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>{pb.status}</Badge><Badge className="text-[10px] bg-violet-100 text-violet-700">{pb.trigger_type}</Badge></div>
            <p className="text-xs text-stone-400 mt-1">{pb.rules?.length || 0} rules configured</p>
          </div>
          <button onClick={() => remove(pb.id)} className="text-red-400 hover:text-red-600 p-2"><Trash2 className="w-4 h-4" /></button>
        </div>
      ))}
    </div>
  );
};

export const RevenueExperiments = ({ propertyId }) => {
  const [items, setItems] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", target_room_category: "All Categories", target_rate_plan: "All Plans", start_date: new Date().toISOString().split("T")[0], end_date: new Date(Date.now() + 7 * 86400000).toISOString().split("T")[0], treatment_adjustment: 10 });

  const load = () => { axios.get(`${API}/revenue/experiments/${propertyId}`).then(r => setItems(r.data.items)).catch(() => toast.error("Failed")); };
  useEffect(() => { load(); }, [propertyId]);

  const create = async () => {
    if (!form.name) { toast.error("Name required"); return; }
    try { await axios.post(`${API}/revenue/experiments/${propertyId}`, form); toast.success("Experiment created"); setShowForm(false); load(); } catch { toast.error("Failed"); }
  };
  const remove = async (id) => { try { await axios.delete(`${API}/revenue/experiments/${id}`); toast.success("Deleted"); load(); } catch { toast.error("Failed"); } };

  return (
    <div className="space-y-6" data-testid="rev-experiments">
      <div className="flex items-center justify-between">
        <div><h2 className="text-lg font-bold text-stone-800">Experiments</h2><p className="text-sm text-stone-500">Test pricing changes with controlled experiments</p></div>
        <button onClick={() => setShowForm(!showForm)} className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white px-4 py-2 rounded-xl text-sm font-medium" data-testid="rev-new-experiment"><FlaskConical className="w-4 h-4" />Create Experiment</button>
      </div>
      {showForm && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="bg-white border border-stone-200 rounded-2xl p-6 space-y-4">
            <h3 className="text-lg font-bold text-stone-800">Experiment Details</h3>
            <div><label className="text-sm font-semibold text-stone-700 block mb-1">Name *</label><Input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="Weekend Price Test" data-testid="rev-exp-name" /></div>
            <div><label className="text-sm font-semibold text-stone-700 block mb-1">Description</label><textarea value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm h-20 resize-none" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-sm font-semibold text-stone-700 block mb-1">Target Room Category</label>
                <Select value={form.target_room_category} onValueChange={v => setForm(p => ({ ...p, target_room_category: v }))}><SelectTrigger className="h-10"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="All Categories">All Categories</SelectItem></SelectContent></Select></div>
              <div><label className="text-sm font-semibold text-stone-700 block mb-1">Target Rate Plan</label>
                <Select value={form.target_rate_plan} onValueChange={v => setForm(p => ({ ...p, target_rate_plan: v }))}><SelectTrigger className="h-10"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="All Plans">All Plans</SelectItem></SelectContent></Select></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-sm font-semibold text-stone-700 block mb-1">Start Date</label><Input type="date" value={form.start_date} onChange={e => setForm(p => ({ ...p, start_date: e.target.value }))} /></div>
              <div><label className="text-sm font-semibold text-stone-700 block mb-1">End Date</label><Input type="date" value={form.end_date} onChange={e => setForm(p => ({ ...p, end_date: e.target.value }))} /></div>
            </div>
          </div>
          <div className="bg-white border border-stone-200 rounded-2xl p-6 space-y-4">
            <h3 className="text-lg font-bold text-stone-800">Variation Config</h3>
            <div className="bg-stone-50 rounded-xl p-4"><p className="font-bold text-stone-700">Control (A)</p><p className="text-sm text-stone-500">No price changes - baseline</p></div>
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
              <p className="font-bold text-stone-700">Treatment (B)</p>
              <label className="text-sm text-stone-600 block mt-2 mb-1">Price Adjustment (%)</label>
              <Input type="number" value={form.treatment_adjustment} onChange={e => setForm(p => ({ ...p, treatment_adjustment: Number(e.target.value) }))} placeholder="10%" data-testid="rev-exp-adj" />
              <p className="text-xs text-stone-400 mt-1">Positive = increase, Negative = decrease</p>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => setShowForm(false)} className="border border-stone-300 text-stone-600 px-4 py-2 rounded-xl text-sm">Cancel</button>
              <button onClick={create} className="bg-emerald-500 hover:bg-emerald-600 text-white px-5 py-2.5 rounded-xl text-sm font-semibold" data-testid="rev-exp-create">+ Create Experiment</button>
            </div>
          </div>
        </div>
      )}
      {items.length === 0 && !showForm ? (
        <div className="text-center py-16 bg-white border border-stone-200 rounded-2xl"><FlaskConical className="w-12 h-12 text-stone-200 mx-auto mb-3" /><p className="font-semibold text-stone-600">No experiments yet</p></div>
      ) : items.map(exp => (
        <div key={exp.id} className="bg-white border border-stone-200 rounded-2xl p-5 flex items-center justify-between" data-testid={`rev-exp-${exp.id}`}>
          <div><div className="flex items-center gap-2"><span className="font-bold text-stone-800">{exp.name}</span><Badge className="text-[10px] bg-emerald-100 text-emerald-700">{exp.status}</Badge></div><p className="text-xs text-stone-400 mt-1">{exp.start_date} → {exp.end_date} | Treatment: {exp.treatment_adjustment > 0 ? "+" : ""}{exp.treatment_adjustment}%</p></div>
          <button onClick={() => remove(exp.id)} className="text-red-400 hover:text-red-600 p-2"><Trash2 className="w-4 h-4" /></button>
        </div>
      ))}
    </div>
  );
};
