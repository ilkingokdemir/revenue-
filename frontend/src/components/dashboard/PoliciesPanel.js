import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Clock, X as XIcon, Plus, FloppyDisk, ArrowsClockwise,
  ShieldCheck, Baby, Dog, Cigarette, CreditCard, House, Info,
} from "@phosphor-icons/react";
import { Input } from "@/components/ui/input";
import { AmenityPicker } from "./AmenityPicker";
import { API } from "./config";

const PoliciesPanel = ({ properties }) => {
  const [selectedProperty, setSelectedProperty] = useState(properties?.filter(p => p.id !== "default")[0]?.id || "");
  const [policies, setPolicies] = useState(null);
  const [facilities, setFacilities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState("times");
  const [ruleInput, setRuleInput] = useState("");

  const fetchData = useCallback(async () => {
    if (!selectedProperty) return;
    setLoading(true);
    try {
      const [polRes, facRes] = await Promise.all([
        axios.get(`${API}/hotel-policies/${selectedProperty}`),
        axios.get(`${API}/property-facilities/${selectedProperty}`),
      ]);
      setPolicies(polRes.data);
      setFacilities(facRes.data.facilities || []);
    } catch (e) { toast.error("Failed to load"); }
    finally { setLoading(false); }
  }, [selectedProperty]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const update = (field, value) => setPolicies(prev => ({ ...prev, [field]: value }));

  const handleSave = async () => {
    setSaving(true);
    try {
      await Promise.all([
        axios.put(`${API}/hotel-policies/${selectedProperty}`, policies),
        axios.put(`${API}/property-facilities/${selectedProperty}`, facilities),
      ]);
      toast.success("Policies & facilities saved");
    } catch (e) { toast.error("Failed to save"); }
    finally { setSaving(false); }
  };

  const addRule = () => {
    if (!ruleInput.trim()) return;
    update("house_rules", [...(policies.house_rules || []), ruleInput.trim()]);
    setRuleInput("");
  };

  const removeRule = (idx) => update("house_rules", (policies.house_rules || []).filter((_, i) => i !== idx));

  const tabs = [
    { id: "times", icon: Clock, label: "Check-in / Check-out" },
    { id: "cancellation", icon: ShieldCheck, label: "Cancellation" },
    { id: "rules", icon: House, label: "House Rules" },
    { id: "payment", icon: CreditCard, label: "Payment" },
    { id: "facilities", icon: Info, label: "Property Facilities" },
  ];

  if (loading || !policies) {
    return (
      <div className="p-5"><div className="flex justify-center py-20"><ArrowsClockwise size={24} className="animate-spin text-stone-400" /></div></div>
    );
  }

  return (
    <div className="p-5" data-testid="policies-panel">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-stone-800">Policies & Facilities</h2>
          <p className="text-sm text-stone-500 mt-0.5">Manage hotel policies and property facilities displayed on your booking page</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={selectedProperty} onChange={e => setSelectedProperty(e.target.value)}
            className="text-xs border border-stone-200 rounded-lg px-2.5 py-1.5 bg-white text-stone-700 font-medium"
            data-testid="policies-property-select">
            {properties?.filter(p => p.id !== "default").map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          <button onClick={handleSave} disabled={saving}
            className="flex items-center gap-1.5 px-3 py-2 bg-emerald-700 text-white text-xs font-medium rounded-lg hover:bg-emerald-800 disabled:opacity-50"
            data-testid="save-policies-btn">
            {saving ? <ArrowsClockwise size={13} className="animate-spin" /> : <FloppyDisk size={13} />}
            {saving ? "Saving..." : "Save All"}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-stone-100 rounded-lg p-1 mb-5">
        {tabs.map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-md transition-colors flex-1 justify-center ${
              activeTab === tab.id ? "bg-white text-stone-800 shadow-sm" : "text-stone-500 hover:text-stone-700"
            }`}
            data-testid={`policy-tab-${tab.id}`}>
            <tab.icon size={13} />
            <span className="hidden sm:inline">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Check-in / Check-out */}
      {activeTab === "times" && (
        <div className="bg-white border border-stone-200 rounded-lg p-5 space-y-4" data-testid="policy-times">
          <h3 className="text-sm font-semibold text-stone-800">Check-in & Check-out Times</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block">Check-in From</label>
              <Input type="time" value={policies.check_in_from} onChange={e => update("check_in_from", e.target.value)} data-testid="check-in-from" />
            </div>
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block">Check-in Until</label>
              <Input type="time" value={policies.check_in_until} onChange={e => update("check_in_until", e.target.value)} data-testid="check-in-until" />
            </div>
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block">Check-out From</label>
              <Input type="time" value={policies.check_out_from} onChange={e => update("check_out_from", e.target.value)} data-testid="check-out-from" />
            </div>
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block">Check-out Until</label>
              <Input type="time" value={policies.check_out_until} onChange={e => update("check_out_until", e.target.value)} data-testid="check-out-until" />
            </div>
          </div>
        </div>
      )}

      {/* Cancellation */}
      {activeTab === "cancellation" && (
        <div className="bg-white border border-stone-200 rounded-lg p-5 space-y-4" data-testid="policy-cancellation">
          <h3 className="text-sm font-semibold text-stone-800">Cancellation Policy</h3>
          <div>
            <label className="text-xs font-medium text-stone-600 mb-1 block">Policy Type</label>
            <select value={policies.cancellation_policy} onChange={e => update("cancellation_policy", e.target.value)}
              className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid="cancellation-type">
              <option value="free">Free Cancellation</option>
              <option value="moderate">Moderate (free up to X hours before)</option>
              <option value="strict">Strict (non-refundable)</option>
              <option value="custom">Custom</option>
            </select>
          </div>
          {policies.cancellation_policy === "moderate" && (
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block">Free cancellation up to (hours before check-in)</label>
              <Input type="number" min={0} value={policies.cancellation_hours} onChange={e => update("cancellation_hours", parseInt(e.target.value) || 24)} data-testid="cancellation-hours" />
            </div>
          )}
          <div>
            <label className="text-xs font-medium text-stone-600 mb-1 block">Custom Cancellation Text (shown to guests)</label>
            <textarea value={policies.cancellation_text || ""} onChange={e => update("cancellation_text", e.target.value)}
              placeholder="e.g. Free cancellation until 24 hours before check-in. Late cancellations incur a one-night charge."
              rows={3} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm resize-none" data-testid="cancellation-text" />
          </div>
        </div>
      )}

      {/* House Rules */}
      {activeTab === "rules" && (
        <div className="bg-white border border-stone-200 rounded-lg p-5 space-y-4" data-testid="policy-rules">
          <h3 className="text-sm font-semibold text-stone-800">House Rules & Policies</h3>
          <div className="grid grid-cols-1 gap-3">
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block"><Baby size={12} className="inline mr-1" />Children Policy</label>
              <textarea value={policies.children_policy || ""} onChange={e => update("children_policy", e.target.value)} rows={2}
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm resize-none" data-testid="children-policy" />
            </div>
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block"><Dog size={12} className="inline mr-1" />Pet Policy</label>
              <textarea value={policies.pet_policy || ""} onChange={e => update("pet_policy", e.target.value)} rows={2}
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm resize-none" data-testid="pet-policy" />
            </div>
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block"><Cigarette size={12} className="inline mr-1" />Smoking Policy</label>
              <textarea value={policies.smoking_policy || ""} onChange={e => update("smoking_policy", e.target.value)} rows={2}
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm resize-none" data-testid="smoking-policy" />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-stone-600 mb-1 block">House Rules</label>
            <div className="flex gap-2 mb-2">
              <Input value={ruleInput} onChange={e => setRuleInput(e.target.value)} placeholder="e.g. Quiet hours: 10pm - 7am"
                onKeyDown={e => e.key === "Enter" && addRule()} data-testid="house-rule-input" />
              <button onClick={addRule} className="px-3 py-2 bg-stone-800 text-white rounded-lg text-xs font-medium flex items-center gap-1" data-testid="add-rule-btn"><Plus size={12} /> Add</button>
            </div>
            {(policies.house_rules || []).map((rule, idx) => (
              <div key={idx} className="flex items-center gap-2 py-1.5 text-sm text-stone-700">
                <span className="text-stone-400">{idx + 1}.</span>
                <span className="flex-1">{rule}</span>
                <button onClick={() => removeRule(idx)} className="text-stone-400 hover:text-red-500" data-testid={`remove-rule-${idx}`}><XIcon size={14} /></button>
              </div>
            ))}
          </div>
          <div>
            <label className="text-xs font-medium text-stone-600 mb-1 block">Additional Info</label>
            <textarea value={policies.extra_info || ""} onChange={e => update("extra_info", e.target.value)}
              placeholder="Any additional information guests should know..." rows={2}
              className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm resize-none" data-testid="extra-info" />
          </div>
        </div>
      )}

      {/* Payment */}
      {activeTab === "payment" && (
        <div className="bg-white border border-stone-200 rounded-lg p-5 space-y-4" data-testid="policy-payment">
          <h3 className="text-sm font-semibold text-stone-800">Payment Settings</h3>
          <div>
            <label className="text-xs font-medium text-stone-600 mb-1 block">Accepted Payment Methods</label>
            <div className="flex flex-wrap gap-2">
              {["Visa", "Mastercard", "American Express", "Apple Pay", "Google Pay", "PayPal", "Bank Transfer", "Cash"].map(method => (
                <label key={method} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs cursor-pointer transition-colors ${
                  (policies.payment_methods || []).includes(method) ? "bg-emerald-50 border-emerald-300 text-emerald-800" : "border-stone-200 text-stone-500 hover:border-stone-300"
                }`} data-testid={`payment-method-${method}`}>
                  <input type="checkbox" className="sr-only" checked={(policies.payment_methods || []).includes(method)}
                    onChange={e => {
                      const methods = policies.payment_methods || [];
                      update("payment_methods", e.target.checked ? [...methods, method] : methods.filter(m => m !== method));
                    }} />
                  {method}
                </label>
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-stone-600 mb-1 block">Damage Deposit (£0 = none)</label>
            <Input type="number" min={0} value={policies.damage_deposit || 0} onChange={e => update("damage_deposit", parseFloat(e.target.value) || 0)} data-testid="damage-deposit" />
          </div>
        </div>
      )}

      {/* Property Facilities */}
      {activeTab === "facilities" && (
        <div className="bg-white border border-stone-200 rounded-lg p-5" data-testid="policy-facilities">
          <h3 className="text-sm font-semibold text-stone-800 mb-1">Property Facilities</h3>
          <p className="text-xs text-stone-500 mb-4">Select all facilities available at your property. These are displayed on your booking page.</p>
          <AmenityPicker selected={facilities} onChange={setFacilities} mode="facility" />
        </div>
      )}
    </div>
  );
};

export { PoliciesPanel };
