import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  Key, Lock, Plus, ArrowsClockwise, CheckCircle,
  WarningCircle, CaretRight, Trash, Eye, X,
  Buildings, Gear,
} from "@phosphor-icons/react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function SmartLocksPanel({ properties, activePropertyId }) {
  const [providers, setProviders] = useState({});
  const [config, setConfig] = useState(null);
  const [keys, setKeys] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("config");
  const [showGenerate, setShowGenerate] = useState(false);
  const [genRef, setGenRef] = useState("");
  const [genRoom, setGenRoom] = useState("");

  const propertyId = activePropertyId && activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "city-gate");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [provRes, cfgRes, keysRes, statsRes] = await Promise.all([
        axios.get(`${API}/smart-locks/providers`),
        axios.get(`${API}/smart-locks/config/${propertyId}`),
        axios.get(`${API}/digital-keys/${propertyId}`),
        axios.get(`${API}/digital-keys/${propertyId}/stats`),
      ]);
      setProviders(provRes.data);
      setConfig(cfgRes.data);
      setKeys(keysRes.data);
      setStats(statsRes.data);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, [propertyId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const saveConfig = async (updates) => {
    await axios.put(`${API}/smart-locks/config/${propertyId}`, updates);
    fetchData();
  };

  const testConnection = async () => {
    const res = await axios.post(`${API}/smart-locks/config/${propertyId}/test`);
    alert(res.data.message);
  };

  const generateKey = async () => {
    if (!genRef) return;
    await axios.post(`${API}/digital-keys/generate`, { booking_ref: genRef, room_number: genRoom });
    setShowGenerate(false);
    setGenRef("");
    setGenRoom("");
    fetchData();
  };

  const revokeKey = async (keyId) => {
    await axios.put(`${API}/digital-keys/${keyId}/revoke`);
    fetchData();
  };

  const providerInfo = config?.provider ? providers[config.provider] : null;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5" data-testid="smart-locks-panel">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2" data-testid="smart-locks-title">
            <Key size={22} className="text-cyan-500" weight="fill" />
            Digital Keys & Smart Locks
          </h1>
          <p className="text-sm text-stone-500 mt-0.5">Keyless entry for guests — generate access codes per booking</p>
        </div>
        <button onClick={fetchData} className="h-8 w-8 flex items-center justify-center rounded-lg border border-stone-200 hover:bg-stone-50">
          <ArrowsClockwise size={14} className="text-stone-500" />
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-xl font-bold text-stone-800">{stats.total || 0}</div>
          <div className="text-[10px] text-stone-500 uppercase">Total Keys</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-xl font-bold text-emerald-600">{stats.active || 0}</div>
          <div className="text-[10px] text-stone-500 uppercase">Active</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-xl font-bold text-stone-400">{stats.expired || 0}</div>
          <div className="text-[10px] text-stone-500 uppercase">Expired</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-xl font-bold text-red-500">{stats.revoked || 0}</div>
          <div className="text-[10px] text-stone-500 uppercase">Revoked</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-stone-200">
        {[
          { id: "config", label: "Lock Provider", icon: Gear },
          { id: "keys", label: `Digital Keys (${keys.length})`, icon: Key },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-2.5 text-xs font-medium flex items-center gap-1.5 border-b-2 transition-colors ${
              tab === t.id ? "border-cyan-500 text-cyan-700" : "border-transparent text-stone-400 hover:text-stone-600"
            }`} data-testid={`tab-${t.id}`}>
            <t.icon size={14} /> {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-16"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div>
      ) : (
        <>
          {tab === "config" && config && (
            <div className="space-y-4" data-testid="lock-config">
              {/* Provider Selection */}
              <div className="bg-white border border-stone-200 rounded-xl p-4">
                <div className="text-sm font-semibold text-stone-800 mb-3">Select Lock Provider</div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {Object.entries(providers).map(([id, info]) => (
                    <button key={id}
                      onClick={() => saveConfig({ provider: id })}
                      className={`p-3 rounded-lg border text-left transition-all ${
                        config.provider === id ? "border-cyan-300 bg-cyan-50 ring-1 ring-cyan-200" : "border-stone-200 hover:border-stone-300"
                      }`} data-testid={`provider-${id}`}>
                      <div className="text-xs font-semibold text-stone-800">{info.name}</div>
                      <div className="text-[10px] text-stone-400 mt-0.5 line-clamp-2">{info.description?.slice(0, 80)}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Credentials */}
              {providerInfo && (
                <div className="bg-white border border-stone-200 rounded-xl p-4">
                  <div className="text-sm font-semibold text-stone-800 mb-1">{providerInfo.name} Configuration</div>
                  <p className="text-[11px] text-stone-500 mb-3">{providerInfo.description}</p>
                  {providerInfo.setup_url && (
                    <a href={providerInfo.setup_url} target="_blank" rel="noopener noreferrer"
                      className="text-[11px] text-cyan-600 underline mb-3 block">Open {providerInfo.name} developer portal</a>
                  )}
                  <div className="space-y-2">
                    {providerInfo.fields?.map(field => (
                      <Input key={field} placeholder={field.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
                        type={field.includes("secret") ? "password" : "text"}
                        defaultValue={config[field] || ""}
                        onBlur={e => saveConfig({ [field]: e.target.value })} />
                    ))}
                  </div>
                  <div className="flex gap-2 mt-3">
                    <button onClick={testConnection}
                      className="text-xs px-3 py-1.5 bg-cyan-50 text-cyan-700 rounded-lg hover:bg-cyan-100 font-medium" data-testid="test-lock-btn">
                      Test Connection
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {tab === "keys" && (
            <div className="space-y-3" data-testid="keys-list">
              <div className="flex justify-end">
                <button onClick={() => setShowGenerate(true)}
                  className="text-xs px-3 py-1.5 bg-cyan-500 text-white rounded-lg hover:bg-cyan-600 font-medium flex items-center gap-1"
                  data-testid="generate-key-btn">
                  <Plus size={12} /> Generate Key
                </button>
              </div>
              {keys.length === 0 ? (
                <div className="bg-white border border-stone-200 rounded-xl p-12 text-center">
                  <Key size={32} className="text-stone-300 mx-auto mb-2" />
                  <p className="text-sm text-stone-500">No digital keys generated yet</p>
                </div>
              ) : keys.map(k => (
                <div key={k.id} className="bg-white border border-stone-200 rounded-xl p-4 flex items-center justify-between" data-testid={`key-${k.id}`}>
                  <div className="flex items-center gap-3">
                    <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${k.status === "active" ? "bg-emerald-50" : "bg-stone-100"}`}>
                      <Key size={16} className={k.status === "active" ? "text-emerald-500" : "text-stone-400"} weight="fill" />
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-stone-800">{k.guest_name} — Room {k.room_number || "TBD"}</div>
                      <div className="flex items-center gap-2 text-[10px] text-stone-400">
                        <span>#{k.booking_ref}</span>
                        <span>Code: <span className="font-mono font-bold text-stone-700">{k.access_code}</span></span>
                        <span>{k.valid_from} — {k.valid_until}</span>
                        {k.used_count > 0 && <span>Used {k.used_count}x</span>}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge className={`text-[10px] ${k.status === "active" ? "bg-emerald-100 text-emerald-700" : k.status === "revoked" ? "bg-red-100 text-red-700" : "bg-stone-100 text-stone-500"}`}>
                      {k.status}
                    </Badge>
                    {k.status === "active" && (
                      <button onClick={() => revokeKey(k.id)} className="text-[10px] px-2 py-1 text-red-500 hover:bg-red-50 rounded">Revoke</button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Generate Key Dialog */}
      <Dialog open={showGenerate} onOpenChange={setShowGenerate}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>Generate Digital Key</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Input placeholder="Booking Reference (e.g. MHB-XXXX)" value={genRef}
              onChange={e => setGenRef(e.target.value)} data-testid="gen-key-ref" />
            <Input placeholder="Room Number (optional)" value={genRoom}
              onChange={e => setGenRoom(e.target.value)} data-testid="gen-key-room" />
            <button onClick={generateKey}
              className="w-full text-xs py-2 bg-cyan-500 text-white rounded-lg hover:bg-cyan-600 font-medium" data-testid="gen-key-submit">
              Generate Access Code
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
