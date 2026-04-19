import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Percent, Plus, X, Trash2, Calculator } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EMPTY_RULE = { kind: "vat", label: "", basis: "percent", rate: 20, applies_to: ["room"], channels: [], included_in_rate: false };
const EMPTY_PROFILE = { property_id: "default", name: "", rules: [{ ...EMPTY_RULE }], active: true, notes: "" };

export const TaxConfigPanel = ({ propertyId = "" }) => {
  const [profiles, setProfiles] = useState([]);
  const [form, setForm] = useState(null);
  const [calc, setCalc] = useState({ base_amount: 100, nights: 1, guests: 1, channel: "", category: "room" });
  const [calcResult, setCalcResult] = useState(null);

  const load = async () => {
    try {
      const { data } = await axios.get(`${API}/tax-config/profiles${propertyId && propertyId !== "all" ? `?property_id=${propertyId}` : ""}`);
      setProfiles(data || []);
    } catch (e) { toast.error("Failed to load"); }
  };
  useEffect(() => { load(); }, [propertyId]);

  const save = async () => {
    if (!form.name) return toast.error("Name required");
    try {
      if (form.id) await axios.put(`${API}/tax-config/profiles/${form.id}`, form);
      else await axios.post(`${API}/tax-config/profiles`, form);
      toast.success("Saved"); setForm(null); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Save failed"); }
  };
  const del = async (id) => {
    if (!window.confirm("Delete this tax profile?")) return;
    try { await axios.delete(`${API}/tax-config/profiles/${id}`); toast.success("Deleted"); load(); }
    catch { toast.error("Delete failed"); }
  };

  const runCalc = async () => {
    try {
      const { data } = await axios.post(`${API}/tax-config/calculate`, {
        property_id: propertyId || "default", ...calc,
      });
      setCalcResult(data);
    } catch (e) { toast.error("Calc failed"); }
  };

  return (
    <div className="p-6 space-y-6" data-testid="tax-config-panel">
      <div className="bg-gradient-to-br from-indigo-700 via-violet-700 to-purple-800 rounded-2xl p-6 text-white shadow-xl">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-amber-200">
          <Percent className="w-4 h-4" /> Tax Configuration
        </div>
        <h1 className="text-3xl font-black mt-2">VAT · City Tax · Service Charge</h1>
        <p className="text-sm text-violet-100 mt-1">Centralised multi-region tax profiles with per-channel overrides</p>
      </div>

      {/* Profiles list */}
      <div className="flex justify-end">
        <button onClick={() => setForm({ ...EMPTY_PROFILE })} data-testid="tax-new-btn"
          className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold">
          <Plus className="w-4 h-4" /> New Tax Profile
        </button>
      </div>

      <div className="space-y-3">
        {profiles.length === 0 && <div className="bg-white border border-dashed border-stone-300 rounded-xl p-8 text-center text-stone-400">No tax profiles yet. Create one to centralise VAT, city tax and service charges.</div>}
        {profiles.map(p => (
          <div key={p.id} className="bg-white border border-stone-200 rounded-xl p-4" data-testid={`tax-profile-${p.id}`}>
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-bold text-stone-900">{p.name} {!p.active && <span className="text-[10px] text-stone-400 ml-2">INACTIVE</span>}</h3>
                <p className="text-[11px] text-stone-500">{p.rules?.length || 0} rule(s) · Property: {p.property_id}</p>
              </div>
              <div className="flex gap-2">
                <button onClick={() => setForm({ ...p })} className="text-xs text-sky-600 hover:underline">Edit</button>
                <button onClick={() => del(p.id)} className="text-xs text-rose-600 hover:underline">Delete</button>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {(p.rules || []).map((r, i) => (
                <div key={i} className="text-xs px-3 py-1.5 bg-stone-100 rounded-lg">
                  <span className="font-bold text-stone-800">{r.label}</span>
                  <span className="ml-2 text-stone-500">
                    {r.basis === "percent" && `${r.rate}%`}
                    {r.basis === "per_night_per_guest" && `£${r.rate}/night/guest`}
                    {r.basis === "per_night" && `£${r.rate}/night`}
                    {r.basis === "flat" && `£${r.rate} flat`}
                  </span>
                  <span className="ml-2 text-[10px] text-stone-400 uppercase">{(r.applies_to || []).join(", ")}</span>
                  {r.included_in_rate && <span className="ml-2 text-[10px] text-emerald-600 font-bold">INCL</span>}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Calculator */}
      <div className="bg-stone-50 border border-stone-200 rounded-xl p-5">
        <div className="flex items-center gap-2 mb-3">
          <Calculator className="w-4 h-4 text-indigo-600" />
          <h3 className="font-bold text-stone-900 text-sm">Tax Calculator</h3>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Field label="Base £"><input type="number" value={calc.base_amount} onChange={e => setCalc({ ...calc, base_amount: parseFloat(e.target.value) || 0 })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid="tax-calc-base" /></Field>
          <Field label="Nights"><input type="number" value={calc.nights} onChange={e => setCalc({ ...calc, nights: parseInt(e.target.value) || 1 })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></Field>
          <Field label="Guests"><input type="number" value={calc.guests} onChange={e => setCalc({ ...calc, guests: parseInt(e.target.value) || 1 })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></Field>
          <Field label="Channel"><input value={calc.channel} onChange={e => setCalc({ ...calc, channel: e.target.value })} placeholder="e.g. Booking.com" className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></Field>
          <button onClick={runCalc} data-testid="tax-calc-run" className="mt-5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold">Calculate</button>
        </div>
        {calcResult && (
          <div className="mt-4 bg-white border border-stone-200 rounded-lg p-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-stone-500">Base</span><span className="font-mono">£{calcResult.base.toFixed(2)}</span>
            </div>
            {(calcResult.applied || []).map((a, i) => (
              <div key={i} className="flex items-center justify-between text-xs py-1">
                <span className="text-stone-500">+ {a.label} <span className="text-[10px] text-stone-400">({a.basis})</span>{a.included_in_rate && <span className="text-[10px] text-emerald-600 font-bold ml-1">INCL</span>}</span>
                <span className={`font-mono ${a.included_in_rate ? "text-stone-400" : ""}`}>£{a.amount.toFixed(2)}</span>
              </div>
            ))}
            <div className="h-px bg-stone-200 my-2" />
            <div className="flex items-center justify-between font-bold">
              <span>Grand Total</span><span className="font-mono text-lg text-emerald-700">£{calcResult.grand_total.toFixed(2)}</span>
            </div>
            {calcResult.profile && <p className="text-[10px] text-stone-400 mt-1">Profile: {calcResult.profile.name}</p>}
          </div>
        )}
      </div>

      {/* Form Modal */}
      {form && (
        <Modal title={form.id ? "Edit Tax Profile" : "New Tax Profile"} onClose={() => setForm(null)}>
          <div className="grid grid-cols-2 gap-3 mb-4">
            <Field label="Name *"><input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid="tax-form-name" /></Field>
            <Field label="Property ID"><input value={form.property_id} onChange={e => setForm({ ...form, property_id: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></Field>
          </div>
          <div className="space-y-2 mb-4">
            <div className="flex items-center justify-between">
              <p className="text-[10px] font-bold uppercase text-stone-500">Rules</p>
              <button onClick={() => setForm({ ...form, rules: [...(form.rules || []), { ...EMPTY_RULE }] })}
                className="text-xs text-indigo-600 hover:underline">+ Add rule</button>
            </div>
            {(form.rules || []).map((r, i) => (
              <div key={i} className="grid grid-cols-[1fr_1fr_100px_100px_auto_auto] gap-2 items-center p-2 bg-stone-50 rounded-lg">
                <select value={r.kind} onChange={e => {
                  const rules = [...form.rules]; rules[i].kind = e.target.value; setForm({ ...form, rules });
                }} className="border border-stone-200 rounded px-2 py-1.5 text-xs">
                  <option value="vat">VAT</option><option value="city_tax">City Tax</option>
                  <option value="tourist_tax">Tourist Tax</option><option value="service_charge">Service Charge</option>
                  <option value="resort_fee">Resort Fee</option><option value="other">Other</option>
                </select>
                <input value={r.label} onChange={e => { const rules = [...form.rules]; rules[i].label = e.target.value; setForm({ ...form, rules }); }}
                  placeholder="Label (e.g. VAT 20%)" className="border border-stone-200 rounded px-2 py-1.5 text-xs" />
                <select value={r.basis} onChange={e => { const rules = [...form.rules]; rules[i].basis = e.target.value; setForm({ ...form, rules }); }}
                  className="border border-stone-200 rounded px-2 py-1.5 text-xs">
                  <option value="percent">%</option><option value="per_night_per_guest">£/night/guest</option>
                  <option value="per_night">£/night</option><option value="flat">£ flat</option>
                </select>
                <input type="number" step="0.01" value={r.rate} onChange={e => { const rules = [...form.rules]; rules[i].rate = parseFloat(e.target.value) || 0; setForm({ ...form, rules }); }}
                  className="border border-stone-200 rounded px-2 py-1.5 text-xs" />
                <label className="text-[10px] flex items-center gap-1"><input type="checkbox" checked={r.included_in_rate} onChange={e => { const rules = [...form.rules]; rules[i].included_in_rate = e.target.checked; setForm({ ...form, rules }); }} /> incl</label>
                <button onClick={() => setForm({ ...form, rules: form.rules.filter((_, j) => j !== i) })} className="text-rose-500 hover:text-rose-700"><Trash2 className="w-3.5 h-3.5" /></button>
              </div>
            ))}
          </div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.active} onChange={e => setForm({ ...form, active: e.target.checked })} /> Active</label>
          <div className="flex justify-end gap-2 mt-4">
            <button onClick={() => setForm(null)} className="px-4 py-2 text-sm">Cancel</button>
            <button onClick={save} data-testid="tax-save-btn" className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold">Save</button>
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
    <div className="bg-white rounded-2xl p-6 w-full max-w-3xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-stone-900">{title}</h2>
        <button onClick={onClose} className="p-1 hover:bg-stone-100 rounded-lg"><X className="w-4 h-4 text-stone-500" /></button>
      </div>
      {children}
    </div>
  </div>
);

export default TaxConfigPanel;
