import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Shield, Plus, X, Trash2, Clock, Lock } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EMPTY_POLICY = {
  property_id: "default", name: "",
  trigger: { channels: [], lead_days_lte: null, rate_plan_ids: [] },
  amount_type: "percent", amount_value: 50, due_within_hours: 24,
  non_refundable: false, active: true, priority: 100,
};

export const DepositPolicyPanel = ({ propertyId = "" }) => {
  const [policies, setPolicies] = useState([]);
  const [form, setForm] = useState(null);
  const [eval_, setEval_] = useState({ channel: "Booking.com", lead_days: 3, rate_plan_id: "", total_price: 500 });
  const [evalResult, setEvalResult] = useState(null);

  const load = async () => {
    try {
      const { data } = await axios.get(`${API}/deposit-policies/${propertyId && propertyId !== "all" ? `?property_id=${propertyId}` : ""}`);
      setPolicies(data || []);
    } catch { toast.error("Failed to load"); }
  };
  useEffect(() => { load(); }, [propertyId]);

  const save = async () => {
    if (!form.name) return toast.error("Name required");
    try {
      if (form.id) await axios.put(`${API}/deposit-policies/${form.id}`, form);
      else await axios.post(`${API}/deposit-policies/`, form);
      toast.success("Saved"); setForm(null); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Save failed"); }
  };
  const del = async (id) => {
    if (!window.confirm("Delete this policy?")) return;
    try { await axios.delete(`${API}/deposit-policies/${id}`); toast.success("Deleted"); load(); }
    catch { toast.error("Delete failed"); }
  };
  const evaluate = async () => {
    try {
      const { data } = await axios.post(`${API}/deposit-policies/evaluate`, {
        property_id: propertyId || "default", ...eval_,
      });
      setEvalResult(data);
    } catch { toast.error("Evaluate failed"); }
  };

  return (
    <div className="p-6 space-y-6" data-testid="deposit-policy-panel">
      <div className="bg-gradient-to-br from-rose-700 via-red-700 to-orange-700 rounded-2xl p-6 text-white shadow-xl">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-amber-200">
          <Shield className="w-4 h-4" /> Deposit Policies
        </div>
        <h1 className="text-3xl font-black mt-2">Enforce deposit collection rules</h1>
        <p className="text-sm text-rose-100 mt-1">Per-channel, per-lead-time rules with % or flat amounts and non-refundable flags</p>
      </div>

      <div className="flex justify-end">
        <button onClick={() => setForm({ ...EMPTY_POLICY })} data-testid="dep-new-btn"
          className="flex items-center gap-1.5 px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-sm font-semibold">
          <Plus className="w-4 h-4" /> New Policy
        </button>
      </div>

      {policies.length === 0 ? (
        <div className="bg-white border border-dashed border-stone-300 rounded-xl p-8 text-center text-stone-400">No deposit policies configured yet.</div>
      ) : (
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 text-[10px] uppercase text-stone-500">
              <tr><th className="p-3 text-left">Priority</th><th className="p-3 text-left">Name</th><th className="p-3 text-left">Trigger</th><th className="p-3 text-right">Amount</th><th className="p-3 text-center">Due within</th><th className="p-3 text-center">Non-refund</th><th className="p-3 text-center">Active</th><th></th></tr>
            </thead>
            <tbody>
              {policies.map(p => (
                <tr key={p.id} className="border-t border-stone-100 hover:bg-stone-50" data-testid={`dep-policy-${p.id}`}>
                  <td className="p-3 font-mono text-xs">{p.priority}</td>
                  <td className="p-3 font-semibold text-stone-800">{p.name}</td>
                  <td className="p-3 text-xs text-stone-500">
                    {(p.trigger?.channels?.length || 0) > 0 ? p.trigger.channels.join(", ") : "All channels"}
                    {p.trigger?.lead_days_lte != null && <span className="ml-2">· ≤{p.trigger.lead_days_lte}d lead</span>}
                  </td>
                  <td className="p-3 text-right font-bold">{p.amount_type === "percent" ? `${p.amount_value}%` : `£${p.amount_value}`}</td>
                  <td className="p-3 text-center text-xs"><Clock className="inline w-3 h-3 mr-1" />{p.due_within_hours}h</td>
                  <td className="p-3 text-center">{p.non_refundable && <Lock className="inline w-3.5 h-3.5 text-rose-600" />}</td>
                  <td className="p-3 text-center">{p.active ? "✓" : "—"}</td>
                  <td className="p-3 text-right">
                    <button onClick={() => setForm({ ...p })} className="text-xs text-sky-600 hover:underline mr-2">Edit</button>
                    <button onClick={() => del(p.id)} className="text-xs text-rose-600 hover:underline">Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Evaluator */}
      <div className="bg-stone-50 border border-stone-200 rounded-xl p-5">
        <h3 className="font-bold text-stone-900 text-sm mb-3">Policy Evaluator</h3>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Field label="Channel"><input value={eval_.channel} onChange={e => setEval_({ ...eval_, channel: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid="dep-eval-channel" /></Field>
          <Field label="Lead days"><input type="number" value={eval_.lead_days} onChange={e => setEval_({ ...eval_, lead_days: parseInt(e.target.value) || 0 })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></Field>
          <Field label="Rate plan ID"><input value={eval_.rate_plan_id} onChange={e => setEval_({ ...eval_, rate_plan_id: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></Field>
          <Field label="Total £"><input type="number" value={eval_.total_price} onChange={e => setEval_({ ...eval_, total_price: parseFloat(e.target.value) || 0 })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></Field>
          <button onClick={evaluate} data-testid="dep-eval-run" className="mt-5 px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-sm font-semibold">Evaluate</button>
        </div>
        {evalResult && (
          <div className={`mt-4 p-4 rounded-lg border ${evalResult.matched ? "bg-emerald-50 border-emerald-200" : "bg-stone-100 border-stone-200"}`}>
            {evalResult.matched ? (
              <>
                <p className="text-sm font-bold text-emerald-800">Matched: {evalResult.policy.name}</p>
                <p className="text-sm mt-1">Deposit required: <strong>£{Number(evalResult.deposit_required).toFixed(2)}</strong></p>
                <p className="text-xs text-stone-600">Due within {evalResult.due_within_hours}h · {evalResult.non_refundable ? "NON-refundable" : "Refundable"}</p>
              </>
            ) : (
              <p className="text-sm text-stone-600">No policy matches — no deposit required.</p>
            )}
          </div>
        )}
      </div>

      {form && (
        <Modal title={form.id ? "Edit Policy" : "New Policy"} onClose={() => setForm(null)}>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Name *"><input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid="dep-form-name" /></Field>
            <Field label="Priority (lower = higher)"><input type="number" value={form.priority} onChange={e => setForm({ ...form, priority: parseInt(e.target.value) || 100 })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></Field>
            <Field label="Amount Type"><select value={form.amount_type} onChange={e => setForm({ ...form, amount_type: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm"><option value="percent">Percent %</option><option value="flat">Flat £</option></select></Field>
            <Field label="Amount Value"><input type="number" step="0.01" value={form.amount_value} onChange={e => setForm({ ...form, amount_value: parseFloat(e.target.value) || 0 })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></Field>
            <Field label="Due within (hours)"><input type="number" value={form.due_within_hours} onChange={e => setForm({ ...form, due_within_hours: parseInt(e.target.value) || 24 })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></Field>
            <Field label="Channels (comma-sep, empty = all)">
              <input value={(form.trigger?.channels || []).join(", ")}
                onChange={e => setForm({ ...form, trigger: { ...form.trigger, channels: e.target.value.split(",").map(s => s.trim()).filter(Boolean) } })}
                placeholder="e.g. Booking.com, Airbnb"
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" />
            </Field>
            <Field label="Lead days ≤ (empty = any)">
              <input type="number" value={form.trigger?.lead_days_lte ?? ""}
                onChange={e => setForm({ ...form, trigger: { ...form.trigger, lead_days_lte: e.target.value === "" ? null : parseInt(e.target.value) } })}
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" />
            </Field>
          </div>
          <div className="flex gap-4 mt-3">
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.non_refundable} onChange={e => setForm({ ...form, non_refundable: e.target.checked })} /> Non-refundable</label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.active} onChange={e => setForm({ ...form, active: e.target.checked })} /> Active</label>
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <button onClick={() => setForm(null)} className="px-4 py-2 text-sm">Cancel</button>
            <button onClick={save} data-testid="dep-save-btn" className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-sm font-semibold">Save</button>
          </div>
        </Modal>
      )}
    </div>
  );
};

const Field = ({ label, children }) => (
  <div>
    <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">{label}</label>
    {children}
  </div>
);

const Modal = ({ title, onClose, children }) => (
  <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
    <div className="bg-white rounded-2xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-stone-900">{title}</h2>
        <button onClick={onClose} className="p-1 hover:bg-stone-100 rounded-lg"><X className="w-4 h-4 text-stone-500" /></button>
      </div>
      {children}
    </div>
  </div>
);

export default DepositPolicyPanel;
