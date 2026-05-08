import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  Plugs, CheckCircle, WarningCircle, CaretRight, CaretDown,
  ArrowsClockwise, Trash, Eye, X, Gear,
  Globe, ChatText, Envelope,
} from "@phosphor-icons/react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PLATFORM_ICONS = {
  google: "G",
  booking: "B",
  tripadvisor: "T",
  whatsapp: "W",
  telegram: "T",
};

const CATEGORY_COLORS = {
  reviews: "text-amber-600 bg-amber-50",
  messaging: "text-purple-600 bg-purple-50",
};

export function SetupWizardPanel({ properties, activePropertyId }) {
  const [platforms, setPlatforms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedPlatform, setExpandedPlatform] = useState(null);
  const [guide, setGuide] = useState(null);
  const [formData, setFormData] = useState({});

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/setup-wizard/platforms`);
      setPlatforms(res.data);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const loadGuide = async (platformId) => {
    if (expandedPlatform === platformId) {
      setExpandedPlatform(null);
      setGuide(null);
      return;
    }
    const res = await axios.get(`${API}/setup-wizard/guide/${platformId}`);
    setGuide(res.data);
    setExpandedPlatform(platformId);
    setFormData({});
  };

  const saveCredentials = async (platformId) => {
    await axios.put(`${API}/setup-wizard/credentials/${platformId}`, formData);
    fetchData();
    const res = await axios.get(`${API}/setup-wizard/guide/${platformId}`);
    setGuide(res.data);
  };

  const testCredentials = async (platformId) => {
    const res = await axios.post(`${API}/setup-wizard/test/${platformId}`);
    alert(res.data.message);
    fetchData();
  };

  const removeCredentials = async (platformId) => {
    await axios.delete(`${API}/setup-wizard/credentials/${platformId}`);
    fetchData();
    setExpandedPlatform(null);
    setGuide(null);
  };

  const configuredCount = platforms.filter(p => p.configured).length;

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-5" data-testid="setup-wizard-panel">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2" data-testid="setup-wizard-title">
            <Plugs size={22} className="text-indigo-500" weight="fill" />
            Platform Setup Wizard
          </h1>
          <p className="text-sm text-stone-500 mt-0.5">Connect review platforms & messaging channels — step by step</p>
        </div>
        <Badge className="bg-indigo-100 text-indigo-700 text-xs">{configuredCount}/{platforms.length} connected</Badge>
      </div>

      {loading ? (
        <div className="flex justify-center py-16"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div>
      ) : (
        <div className="space-y-2" data-testid="platform-list">
          {platforms.map(p => {
            const isExpanded = expandedPlatform === p.id;
            const catColor = CATEGORY_COLORS[p.category] || "text-stone-500 bg-stone-50";
            return (
              <div key={p.id} className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid={`platform-${p.id}`}>
                <button onClick={() => loadGuide(p.id)}
                  className="w-full flex items-center gap-3 p-4 text-left hover:bg-stone-50 transition-colors">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-sm font-bold ${catColor}`}>
                    {PLATFORM_ICONS[p.icon] || p.name[0]}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-stone-800">{p.name}</span>
                      <Badge className={`text-[9px] ${p.configured ? "bg-emerald-100 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>
                        {p.configured ? "Connected" : "Not configured"}
                      </Badge>
                    </div>
                    <div className="text-[11px] text-stone-400 mt-0.5">{p.description}</div>
                  </div>
                  {isExpanded ? <CaretDown size={14} className="text-stone-400" /> : <CaretRight size={14} className="text-stone-400" />}
                </button>

                {isExpanded && guide && (
                  <div className="px-4 pb-4 border-t border-stone-100 pt-3 space-y-4">
                    {/* Steps */}
                    <div className="space-y-2">
                      {guide.steps.map(step => (
                        <div key={step.step} className="flex gap-3">
                          <div className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-[11px] font-bold flex-shrink-0 mt-0.5">
                            {step.step}
                          </div>
                          <div>
                            <div className="text-xs font-semibold text-stone-700">{step.title}</div>
                            <div className="text-[11px] text-stone-500">{step.instruction}</div>
                            {step.url && (
                              <a href={step.url} target="_blank" rel="noopener noreferrer"
                                className="text-[11px] text-indigo-600 underline mt-0.5 inline-block">
                                Open link
                              </a>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Credential Fields */}
                    <div className="bg-stone-50 rounded-lg p-3 space-y-2">
                      <div className="text-[11px] font-semibold text-stone-600">Enter Credentials</div>
                      {guide.fields.map(field => (
                        <div key={field.key}>
                          <label className="text-[10px] text-stone-500 block mb-0.5">{field.label}</label>
                          <Input
                            type={field.type === "password" ? "password" : "text"}
                            placeholder={field.placeholder || ""}
                            value={formData[field.key] || ""}
                            onChange={e => setFormData(p => ({...p, [field.key]: e.target.value}))}
                            className="h-8 text-xs"
                            data-testid={`field-${field.key}`}
                          />
                        </div>
                      ))}
                      <div className="flex gap-2 pt-1">
                        <button onClick={() => saveCredentials(p.id)}
                          className="text-xs px-3 py-1.5 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600 font-medium"
                          data-testid={`save-${p.id}`}>
                          Save Credentials
                        </button>
                        {guide.is_configured && (
                          <>
                            <button onClick={() => testCredentials(p.id)}
                              className="text-xs px-3 py-1.5 bg-emerald-50 text-emerald-700 rounded-lg hover:bg-emerald-100 font-medium"
                              data-testid={`test-${p.id}`}>
                              Test Connection
                            </button>
                            <button onClick={() => removeCredentials(p.id)}
                              className="text-xs px-3 py-1.5 text-red-500 hover:bg-red-50 rounded-lg">
                              Remove
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
