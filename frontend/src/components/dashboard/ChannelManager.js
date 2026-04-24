import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Network, RefreshCw, Send, CheckCircle, XCircle, Settings, Clock, ArrowUpRight, Zap, History, Eye } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

const CH_COLORS = {
  booking_com: "#003580", expedia: "#FFCC00", airbnb: "#FF5A5F", hotels_com: "#D32F2F",
  agoda: "#5C2D91", trip_com: "#287DFA", google_hotels: "#4285F4", trivago: "#E74C3C", direct: "#16A34A",
};

export const ChannelManager = ({ propertyId, hotelName = "" }) => {
  const shortName = hotelName && hotelName.length > 20
    ? (hotelName.split(" ")[0] || "Us")
    : (hotelName || "Us");
  const [data, setData] = useState(null);
  const [pushing, setPushing] = useState(false);
  const [logs, setLogs] = useState([]);
  const [preview, setPreview] = useState(null);
  const [subTab, setSubTab] = useState("channels");

  const load = () => {
    axios.get(`${API}/revenue/channel-manager/${propertyId}`).then(r => setData(r.data)).catch(() => {});
    axios.get(`${API}/revenue/channel-manager/${propertyId}/push-logs`).then(r => setLogs(r.data.logs || [])).catch(() => {});
  };
  useEffect(() => { load(); }, [propertyId]);

  const updateChannel = async (channelId, updates) => {
    try {
      await axios.put(`${API}/revenue/channel-manager/${propertyId}/${channelId}`, updates);
      toast.success("Channel updated");
      load();
    } catch { toast.error("Failed"); }
  };

  const [syncingAvail, setSyncingAvail] = useState(false);

  const pushRates = async () => {
    setPushing(true);
    try {
      const { data: r } = await axios.post(`${API}/revenue/channel-manager/${propertyId}/push-rates`, { days: 90 });
      toast.success(r.message);
      load();
    } catch { toast.error("Push failed"); }
    setPushing(false);
  };

  const loadPreview = async () => {
    try {
      const { data: r } = await axios.get(`${API}/revenue/channel-manager/${propertyId}/rate-preview?days=7`);
      setPreview(r);
    } catch { toast.error("Failed"); }
  };

  const syncAvailability = async () => {
    setSyncingAvail(true);
    try {
      const { data: r } = await axios.post(`${API}/revenue/channel-manager/${propertyId}/sync-availability`, { days: 30 });
      toast.success(r.message);
      load();
    } catch { toast.error("Availability sync failed"); }
    setSyncingAvail(false);
  };

  useEffect(() => { if (subTab === "preview") loadPreview(); }, [subTab]);

  const channels = data?.channels || [];
  const s = data?.summary || {};
  const connected = channels.filter(c => c.connected);
  const disconnected = channels.filter(c => !c.connected);

  return (
    <div className="space-y-6" data-testid="channel-manager">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-900 via-indigo-900 to-violet-900 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-white/10 rounded-xl flex items-center justify-center backdrop-blur-sm">
              <Network className="w-6 h-6 text-blue-300" />
            </div>
            <div>
              <h2 className="text-xl font-bold">Channel Manager</h2>
              <p className="text-sm text-white/60">Distribute rates across OTAs, metasearch & direct channels</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={syncAvailability} disabled={syncingAvail || connected.length === 0}
              className="flex items-center gap-2 bg-white/10 hover:bg-white/20 border border-white/20 text-white px-4 py-2.5 rounded-xl text-sm font-semibold disabled:opacity-50" data-testid="cm-sync-availability">
              {syncingAvail ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
              {syncingAvail ? "Syncing..." : "Sync Availability"}
            </button>
            <button onClick={pushRates} disabled={pushing || connected.length === 0}
              className="flex items-center gap-2 bg-white/10 hover:bg-white/20 border border-white/20 text-white px-5 py-2.5 rounded-xl text-sm font-semibold disabled:opacity-50" data-testid="cm-push-rates">
              {pushing ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              {pushing ? "Pushing Rates..." : "Push Rates to All"}
            </button>
          </div>
        </div>
        {data && (
          <div className="grid grid-cols-4 gap-4 mt-4">
            <div className="bg-white/5 rounded-xl p-3 text-center">
              <p className="text-2xl font-bold">{s.connected}</p>
              <p className="text-[10px] text-white/50">Connected</p>
            </div>
            <div className="bg-white/5 rounded-xl p-3 text-center">
              <p className="text-2xl font-bold">{s.disconnected}</p>
              <p className="text-[10px] text-white/50">Disconnected</p>
            </div>
            <div className="bg-white/5 rounded-xl p-3 text-center">
              <p className="text-2xl font-bold">{s.auto_syncing}</p>
              <p className="text-[10px] text-white/50">Auto-Syncing</p>
            </div>
            <div className="bg-white/5 rounded-xl p-3 text-center">
              <p className="text-2xl font-bold">{s.total_channels}</p>
              <p className="text-[10px] text-white/50">Total Channels</p>
            </div>
          </div>
        )}
      </div>

      {/* Sub-tabs */}
      <div className="flex items-center gap-1 border-b border-stone-200">
        {[{id:"channels",label:"Channels"},{id:"preview",label:"Rate Preview"},{id:"logs",label:"Push Logs"}].map(t => (
          <button key={t.id} onClick={() => setSubTab(t.id)} className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-[1px] transition-all ${subTab === t.id ? "text-indigo-700 border-indigo-500" : "text-stone-400 border-transparent hover:text-stone-600"}`} data-testid={`cm-tab-${t.id}`}>{t.label}</button>
        ))}
      </div>

      {/* Channels Tab */}
      {subTab === "channels" && (
        <div className="space-y-4">
          {/* Connected */}
          {connected.length > 0 && (
            <>
              <h3 className="text-sm font-bold text-stone-500 uppercase tracking-wider">Connected Channels</h3>
              <div className="grid grid-cols-1 gap-3">
                {connected.map(ch => (
                  <div key={ch.channel_id} className="bg-white border border-emerald-200 rounded-2xl p-5" data-testid={`cm-ch-${ch.channel_id}`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold text-sm" style={{ backgroundColor: CH_COLORS[ch.channel_id] || "#666" }}>
                          {ch.logo}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-stone-800">{ch.name}</span>
                            <Badge className="bg-emerald-100 text-emerald-700 text-[9px]">Connected</Badge>
                            <Badge className="bg-stone-100 text-stone-500 text-[9px] capitalize">{ch.type}</Badge>
                            {ch.auto_sync && <Badge className="bg-blue-100 text-blue-700 text-[9px]">Auto-Sync</Badge>}
                          </div>
                          <div className="flex items-center gap-4 mt-1 text-xs text-stone-400">
                            <span>Commission: {ch.commission_pct}%</span>
                            {ch.last_sync && <span className="flex items-center gap-1"><Clock className="w-3 h-3" />Last sync: {new Date(ch.last_sync).toLocaleString("en-GB", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        {/* Rate Rule */}
                        <div className="text-right">
                          <Select value={ch.rate_rule || "same"} onValueChange={v => updateChannel(ch.channel_id, { rate_rule: v })}>
                            <SelectTrigger className="w-32 h-8 text-xs"><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="same">Same Rate</SelectItem>
                              <SelectItem value="markup">Markup</SelectItem>
                              <SelectItem value="undercut">Undercut</SelectItem>
                            </SelectContent>
                          </Select>
                          {ch.rate_rule !== "same" && (
                            <Input type="number" value={ch.rate_markup_pct || 0} onChange={e => updateChannel(ch.channel_id, { rate_markup_pct: Number(e.target.value) })}
                              className="w-20 h-7 text-xs mt-1" placeholder="%" />
                          )}
                        </div>
                        <div className="flex flex-col items-center gap-1">
                          <span className="text-[9px] text-stone-400">Auto-Sync</span>
                          <Switch checked={ch.auto_sync} onCheckedChange={v => updateChannel(ch.channel_id, { auto_sync: v })} />
                        </div>
                        <button onClick={() => updateChannel(ch.channel_id, { connected: false })}
                          className="text-red-400 hover:text-red-600 text-xs font-medium px-3 py-1.5 border border-red-200 rounded-lg hover:bg-red-50">
                          Disconnect
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Disconnected */}
          {disconnected.length > 0 && (
            <>
              <h3 className="text-sm font-bold text-stone-500 uppercase tracking-wider mt-6">Available Channels</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {disconnected.map(ch => (
                  <div key={ch.channel_id} className="bg-white border border-stone-200 rounded-2xl p-5 hover:border-indigo-200 transition-all" data-testid={`cm-ch-${ch.channel_id}`}>
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold text-sm opacity-60" style={{ backgroundColor: CH_COLORS[ch.channel_id] || "#666" }}>
                        {ch.logo}
                      </div>
                      <div>
                        <span className="font-bold text-stone-700">{ch.name}</span>
                        <p className="text-[10px] text-stone-400 capitalize">{ch.type} | {ch.commission_pct}% commission</p>
                      </div>
                    </div>
                    <button onClick={() => updateChannel(ch.channel_id, { connected: true })}
                      className="w-full bg-indigo-600 hover:bg-indigo-700 text-white py-2 rounded-xl text-sm font-semibold transition-all" data-testid={`cm-connect-${ch.channel_id}`}>
                      Connect
                    </button>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* Rate Preview Tab */}
      {subTab === "preview" && preview && (
        <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden" data-testid="cm-rate-preview">
          <div className="px-5 py-3 bg-stone-50 border-b font-bold text-sm text-stone-800 flex items-center gap-2">
            <Eye className="w-4 h-4 text-stone-400" /> Rate Preview (Next 7 Days by Channel)
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="px-3 py-2 text-xs font-semibold text-stone-500 text-left">Date</th>
                  <th className="px-3 py-2 text-xs font-semibold text-stone-500 text-center">{shortName} Rate</th>
                  {preview.channels.filter(c => c.connected).map(ch => (
                    <th key={ch.channel_id} className="px-3 py-2 text-center">
                      <span className="text-[9px] font-bold px-2 py-0.5 rounded text-white" style={{ backgroundColor: CH_COLORS[ch.channel_id] || "#666" }}>{ch.name}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.preview.map(p => (
                  <tr key={p.date} className="border-b border-stone-50">
                    <td className="px-3 py-2 font-medium text-stone-700 text-xs whitespace-nowrap">
                      {new Date(p.date + "T00:00:00").toLocaleDateString("en", { weekday: "short", month: "short", day: "numeric" })}
                    </td>
                    <td className="px-3 py-2 text-center font-bold text-indigo-700">{cur(p.our_rate)}</td>
                    {preview.channels.filter(c => c.connected).map(ch => {
                      const rate = p[ch.channel_id];
                      const diff = rate && p.our_rate ? round(((rate - p.our_rate) / p.our_rate) * 100, 1) : 0;
                      return (
                        <td key={ch.channel_id} className="px-3 py-2 text-center">
                          <div className="font-bold text-stone-800">{cur(rate)}</div>
                          {diff !== 0 && <div className={`text-[10px] font-semibold ${diff > 0 ? "text-emerald-600" : "text-red-500"}`}>{diff > 0 ? "+" : ""}{diff}%</div>}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Push Logs Tab */}
      {subTab === "logs" && (
        <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden" data-testid="cm-push-logs">
          <div className="px-5 py-3 bg-stone-50 border-b font-bold text-sm text-stone-800 flex items-center gap-2">
            <History className="w-4 h-4 text-stone-400" /> Rate Push History
          </div>
          {logs.length === 0 ? (
            <div className="p-12 text-center text-stone-400">
              <Send className="w-10 h-10 mx-auto mb-2 text-stone-200" />
              <p className="font-medium">No rates pushed yet</p>
              <p className="text-sm mt-1">Click "Push Rates to All" to sync your rates across channels.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b bg-stone-50/50">
                  {["Channel", "Rates Pushed", "Rule", "Markup", "Pushed At"].map(h => (
                    <th key={h} className="px-3 py-2 text-xs font-semibold text-stone-500 text-center">{h}</th>
                  ))}
                </tr></thead>
                <tbody>
                  {logs.map(l => (
                    <tr key={l.id} className="border-b border-stone-50">
                      <td className="px-3 py-2">
                        <span className="text-xs font-bold px-2 py-0.5 rounded text-white" style={{ backgroundColor: CH_COLORS[l.channel_id] || "#666" }}>{l.channel_name}</span>
                      </td>
                      <td className="px-3 py-2 text-center font-semibold">{l.rates_pushed}</td>
                      <td className="px-3 py-2 text-center text-stone-500 capitalize text-xs">{l.rule}</td>
                      <td className="px-3 py-2 text-center text-xs">{l.markup_pct ? `${l.markup_pct}%` : "—"}</td>
                      <td className="px-3 py-2 text-center text-xs text-stone-400">{new Date(l.pushed_at).toLocaleString("en-GB")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

function round(v, d = 0) { const m = Math.pow(10, d); return Math.round(v * m) / m; }
