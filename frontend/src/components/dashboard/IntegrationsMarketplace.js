import { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import {
  Search, Check, Zap, Star, Globe, CreditCard, Route, LineChart,
  MessageCircle, Sparkles, Lock, Wallet, Utensils, BarChart3,
  Megaphone, Cloud, Shield, FileCheck, RefreshCw, Settings2,
  Trash2, TrendingUp, X, CheckCircle2, Plug, Wand2, ArrowRight,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ICON_MAP = {
  globe: Globe, "credit-card": CreditCard, route: Route, "line-chart": LineChart,
  message: MessageCircle, sparkle: Sparkles, sparkles: Sparkles, star: Star,
  lock: Lock, wallet: Wallet, utensils: Utensils, "bar-chart": BarChart3,
  megaphone: Megaphone, cloud: Cloud, shield: Shield, "file-check": FileCheck,
  zap: Zap,
};

export const IntegrationsMarketplace = ({ propertyId, user }) => {
  const [data, setData] = useState({ integrations: [], categories: [], total_available: 0, total_installed: 0, featured: [] });
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState("");
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("all"); // all, installed, featured
  const [selected, setSelected] = useState(null);
  const [rec, setRec] = useState(null);
  const [recLoading, setRecLoading] = useState(false);

  const pid = propertyId || "all";
  const isManager = user?.role === "admin" || user?.role === "manager";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const qs = new URLSearchParams();
      if (category) qs.set("category", category);
      if (q) qs.set("q", q);
      const { data: d } = await axios.get(`${API}/marketplace/catalog/${pid}?${qs}`);
      setData(d);
    } catch { /* silent */ }
    setLoading(false);
  }, [pid, category, q]);

  useEffect(() => {
    const t = setTimeout(load, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [load]);

  // Load cached recommendations on mount / property change
  useEffect(() => {
    (async () => {
      try {
        const { data: d } = await axios.get(`${API}/marketplace/recommendations/${pid}`);
        if (d && d.recommendations) setRec(d);
      } catch { /* silent */ }
    })();
  }, [pid]);

  const generateRecs = async () => {
    setRecLoading(true);
    try {
      const { data: d } = await axios.post(`${API}/marketplace/recommendations/${pid}/generate`);
      setRec(d);
      toast.success("AI recommendations refreshed");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "AI service unavailable");
    }
    setRecLoading(false);
  };

  const filteredIntegrations = useMemo(() => {
    let list = data.integrations || [];
    if (filter === "installed") list = list.filter(i => i.installed || i.enabled);
    if (filter === "featured") list = list.filter(i => i.featured);
    return list;
  }, [data.integrations, filter]);

  const install = async (id) => {
    try {
      await axios.post(`${API}/marketplace/install/${pid}/${id}`, {});
      toast.success("Integration connected");
      load();
    } catch { toast.error("Failed"); }
  };
  const toggle = async (id) => {
    try {
      const { data } = await axios.post(`${API}/marketplace/toggle/${pid}/${id}`);
      toast.success(data.enabled ? "Enabled" : "Paused");
      load();
    } catch { toast.error("Failed"); }
  };
  const uninstall = async (id) => {
    if (!window.confirm("Disconnect this integration?")) return;
    try {
      await axios.delete(`${API}/marketplace/uninstall/${pid}/${id}`);
      toast.success("Disconnected");
      load();
    } catch { toast.error("Failed"); }
  };
  const sync = async (id) => {
    try {
      await axios.post(`${API}/marketplace/sync/${pid}/${id}`);
      toast.success("Synced");
      load();
    } catch { toast.error("Failed"); }
  };

  const Logo = ({ domain, size = 32 }) => (
    <img
      src={`https://www.google.com/s2/favicons?domain=${domain}&sz=128`}
      alt={domain}
      width={size}
      height={size}
      className="rounded-lg bg-white p-0.5 flex-shrink-0"
      style={{ objectFit: "contain" }}
      onError={(e) => { e.currentTarget.style.opacity = 0.3; }}
    />
  );

  const IntegrationCard = ({ item }) => {
    const cat = data.categories.find(c => c.id === item.cat);
    return (
      <div
        onClick={() => setSelected(item)}
        className="group bg-white border border-stone-200 rounded-2xl p-4 hover:border-stone-400 hover:shadow-md transition-all cursor-pointer relative"
        data-testid={`integration-${item.id}`}
      >
        {item.featured && !item.installed && !item.enabled && (
          <Badge className="absolute top-2 right-2 bg-amber-100 text-amber-700 text-[9px] font-bold flex items-center gap-0.5">
            <Star className="w-2.5 h-2.5 fill-current" />FEATURED
          </Badge>
        )}
        {(item.installed || item.enabled) && (
          <Badge className="absolute top-2 right-2 bg-emerald-500 text-white text-[9px] font-bold flex items-center gap-0.5" data-testid={`installed-${item.id}`}>
            <CheckCircle2 className="w-2.5 h-2.5" />CONNECTED
          </Badge>
        )}
        <div className="flex items-start gap-3 mb-2">
          <Logo domain={item.domain} size={40} />
          <div className="flex-1 min-w-0 pr-10">
            <h4 className="text-sm font-bold text-stone-800 truncate">{item.name}</h4>
            {cat && (
              <div className="flex items-center gap-1 mt-0.5">
                <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: cat.color }} />
                <span className="text-[10px] text-stone-500 truncate">{cat.name}</span>
              </div>
            )}
          </div>
        </div>
        <p className="text-[11px] text-stone-600 leading-snug line-clamp-2 mb-3 h-[30px]">{item.desc}</p>
        {item.installed || item.enabled ? (
          <div className="flex items-center gap-1.5">
            <button onClick={(e) => { e.stopPropagation(); toggle(item.id); }} data-testid={`toggle-${item.id}`}
              className={`flex-1 py-1.5 text-[10px] font-bold rounded-lg ${item.enabled ? "bg-emerald-50 text-emerald-700 hover:bg-emerald-100" : "bg-stone-100 text-stone-500"}`}>
              {item.enabled ? "Paused?" : "Resume"}
            </button>
            <button onClick={(e) => { e.stopPropagation(); setSelected(item); }} className="p-1.5 hover:bg-stone-100 rounded-lg"><Settings2 className="w-3.5 h-3.5 text-stone-500" /></button>
          </div>
        ) : (
          <Button
            size="sm"
            onClick={(e) => { e.stopPropagation(); install(item.id); }}
            disabled={!isManager}
            className="w-full h-7 text-[11px] bg-stone-800 hover:bg-stone-700 text-white"
            data-testid={`connect-${item.id}`}
          >
            <Plug className="w-3 h-3 mr-1" />Connect
          </Button>
        )}
      </div>
    );
  };

  const pct = data.total_available ? Math.round((data.total_installed / data.total_available) * 100) : 0;

  return (
    <div className="space-y-5" data-testid="integrations-marketplace">
      {/* Hero Header */}
      <div className="bg-gradient-to-br from-indigo-600 via-violet-600 to-fuchsia-600 rounded-2xl p-6 text-white shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full -translate-y-20 translate-x-20 blur-3xl" />
        <div className="relative">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="w-5 h-5" />
            <span className="text-[11px] font-bold uppercase tracking-wider opacity-90">Integrations Marketplace</span>
          </div>
          <h2 className="text-3xl font-black mb-1" data-testid="marketplace-title">Connect everything. Run anything.</h2>
          <p className="text-sm opacity-90">{data.total_available}+ integrations across {data.categories.length} categories — the deepest ecosystem in hospitality.</p>
          <div className="flex items-center gap-6 mt-4">
            <div><p className="text-3xl font-black" data-testid="total-available">{data.total_available}</p><p className="text-[10px] opacity-80 uppercase tracking-wider">Available</p></div>
            <div className="h-10 w-px bg-white/30" />
            <div><p className="text-3xl font-black text-emerald-200" data-testid="total-installed">{data.total_installed}</p><p className="text-[10px] opacity-80 uppercase tracking-wider">Connected</p></div>
            <div className="h-10 w-px bg-white/30" />
            <div className="flex-1 min-w-[150px] max-w-sm">
              <div className="flex items-center justify-between mb-1 text-[10px] opacity-80"><span>Coverage</span><span>{pct}%</span></div>
              <div className="h-1.5 bg-white/20 rounded-full overflow-hidden">
                <div className="h-full bg-gradient-to-r from-emerald-300 to-cyan-300" style={{ width: `${pct}%` }} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* AI Recommendations Strip */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-2xl p-5 text-white shadow-xl border border-indigo-500/20 relative overflow-hidden" data-testid="ai-rec-strip">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_0%,rgba(139,92,246,0.25),transparent_50%),radial-gradient(circle_at_80%_100%,rgba(236,72,153,0.15),transparent_50%)]" />
        <div className="relative">
          <div className="flex items-start justify-between gap-3 mb-3">
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-400 to-fuchsia-500 flex items-center justify-center shadow-lg flex-shrink-0">
                <Wand2 className="w-4.5 h-4.5 text-white" />
              </div>
              <div>
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-violet-200">AI Picks · GPT-5.2</span>
                  <Badge className="bg-white/10 text-white text-[9px] border-white/20 backdrop-blur-sm">RECOMMENDED FOR YOU</Badge>
                </div>
                <h3 className="text-base font-bold leading-tight" data-testid="ai-rec-headline">
                  {rec?.headline || "Let GPT-5.2 pick the 3 integrations that will lift your RevPAR fastest."}
                </h3>
                {rec?.signal_snapshot && (
                  <p className="text-[11px] text-indigo-200/80 mt-0.5">
                    Analysed {rec.signal_snapshot.bookings} bookings · {rec.signal_snapshot.connected_count} apps connected · top sources: {(rec.signal_snapshot.top_sources || []).join(", ")}
                  </p>
                )}
              </div>
            </div>
            <Button
              size="sm"
              onClick={generateRecs}
              disabled={recLoading || !isManager}
              className="bg-white text-slate-900 hover:bg-violet-50 font-semibold shadow-lg flex-shrink-0"
              data-testid="ai-rec-generate"
            >
              {recLoading ? <><RefreshCw className="w-3.5 h-3.5 mr-1 animate-spin" />Analysing...</>
                          : <><Sparkles className="w-3.5 h-3.5 mr-1" />{rec ? "Refresh Picks" : "Get AI Picks"}</>}
            </Button>
          </div>

          {rec?.recommendations?.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 mt-3" data-testid="ai-rec-list">
              {rec.recommendations.map((r, idx) => (
                <div
                  key={r.id}
                  className="bg-white/[0.07] hover:bg-white/[0.12] backdrop-blur-sm border border-white/10 rounded-xl p-3 transition cursor-pointer group"
                  onClick={() => {
                    const item = (data.integrations || []).find(i => i.id === r.id);
                    if (item) setSelected(item);
                  }}
                  data-testid={`ai-rec-${r.id}`}
                >
                  <div className="flex items-start gap-2.5 mb-2">
                    <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-white flex items-center justify-center shadow">
                      <img
                        src={`https://www.google.com/s2/favicons?domain=${r.domain}&sz=128`}
                        alt={r.domain} className="w-5 h-5" style={{ objectFit: "contain" }}
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[9px] font-bold text-violet-300">#{idx + 1}</span>
                        <h4 className="text-sm font-bold truncate">{r.title}</h4>
                      </div>
                      <div className="flex items-center gap-1 mt-0.5">
                        <Badge className={`text-[9px] font-bold border-0 ${r.priority === "high" ? "bg-rose-500/30 text-rose-100" : "bg-amber-400/25 text-amber-100"}`}>
                          {(r.priority || "medium").toUpperCase()}
                        </Badge>
                        {r.impact && (
                          <span className="text-[10px] font-bold text-emerald-300 flex items-center gap-0.5">
                            <TrendingUp className="w-2.5 h-2.5" />{r.impact}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <p className="text-[11px] text-indigo-100/90 leading-snug line-clamp-2 mb-2 min-h-[28px]">{r.reason}</p>
                  <button
                    onClick={(e) => { e.stopPropagation(); install(r.id); }}
                    className="w-full py-1.5 text-[11px] font-bold rounded-lg bg-white text-slate-900 hover:bg-violet-50 flex items-center justify-center gap-1 transition"
                    data-testid={`ai-rec-connect-${r.id}`}
                  >
                    <Plug className="w-3 h-3" />Connect {r.name} <ArrowRight className="w-3 h-3 opacity-60 group-hover:translate-x-0.5 transition" />
                  </button>
                </div>
              ))}
            </div>
          )}
          {!rec && !recLoading && (
            <p className="text-[11px] text-indigo-200/70 mt-1">
              Tap <span className="font-semibold text-white">Get AI Picks</span> — we'll read your booking mix, payment coverage and category gaps, then surface 3 hand-picked integrations with an expected RevPAR lift.
            </p>
          )}
        </div>
      </div>

      {/* Search + Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <Input value={q} onChange={e => setQ(e.target.value)} placeholder="Search 120+ integrations..." className="pl-9 h-9" data-testid="marketplace-search" />
          {q && <button onClick={() => setQ("")} className="absolute right-2 top-1/2 -translate-y-1/2 p-1 hover:bg-stone-100 rounded"><X className="w-3 h-3" /></button>}
        </div>
        <div className="flex items-center gap-1 bg-stone-100 rounded-lg p-0.5">
          {[["all","All"],["installed","Connected"],["featured","Featured"]].map(([k,l]) => (
            <button key={k} onClick={() => setFilter(k)} data-testid={`filter-${k}`}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md ${filter === k ? "bg-white text-stone-800 shadow-sm" : "text-stone-500"}`}>
              {l}
            </button>
          ))}
        </div>
      </div>

      {/* Categories */}
      <div className="flex items-center gap-2 flex-wrap" data-testid="categories">
        <button onClick={() => setCategory("")} data-testid="cat-all"
          className={`px-3 py-1.5 text-xs font-semibold rounded-full border transition ${!category ? "bg-stone-800 text-white border-stone-800" : "bg-white text-stone-600 border-stone-200 hover:border-stone-400"}`}>
          All Categories ({data.total_available})
        </button>
        {data.categories.map(c => {
          const Icon = ICON_MAP[c.icon] || Zap;
          const sel = category === c.id;
          return (
            <button key={c.id} onClick={() => setCategory(sel ? "" : c.id)} data-testid={`cat-${c.id}`}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-full border transition ${sel ? "text-white border-transparent" : "bg-white border-stone-200 hover:border-stone-400"}`}
              style={sel ? { backgroundColor: c.color } : { color: c.color }}>
              <Icon className="w-3.5 h-3.5" />
              {c.name}
              <span className={`text-[10px] font-bold ${sel ? "bg-white/20" : "bg-stone-100"} px-1.5 rounded-full ${sel ? "text-white" : ""}`}>
                {c.installed > 0 && <span className="text-emerald-600">{c.installed}/</span>}{c.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading marketplace...</div>
      ) : filteredIntegrations.length === 0 ? (
        <div className="text-center py-16 text-stone-400" data-testid="empty-state">
          <Search className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="text-sm">No integrations match your filters.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3" data-testid="integrations-grid">
          {filteredIntegrations.map(item => <IntegrationCard key={item.id} item={item} />)}
        </div>
      )}

      {/* Detail Drawer */}
      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={() => setSelected(null)}>
          <div onClick={e => e.stopPropagation()} className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl" data-testid="integration-detail">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <Logo domain={selected.domain} size={56} />
                <div>
                  <h3 className="text-lg font-black text-stone-800">{selected.name}</h3>
                  <div className="flex items-center gap-1.5">
                    {selected.featured && <Badge className="bg-amber-100 text-amber-700 text-[9px]"><Star className="w-2.5 h-2.5 fill-current mr-0.5" />FEATURED</Badge>}
                    {(selected.installed || selected.enabled) && <Badge className="bg-emerald-500 text-white text-[9px]"><CheckCircle2 className="w-2.5 h-2.5 mr-0.5" />CONNECTED</Badge>}
                  </div>
                </div>
              </div>
              <button onClick={() => setSelected(null)} className="p-1 hover:bg-stone-100 rounded"><X className="w-4 h-4" /></button>
            </div>
            <p className="text-sm text-stone-600 mb-4">{selected.desc}</p>
            {(selected.installed || selected.enabled) && (
              <div className="bg-stone-50 rounded-lg p-3 mb-4 space-y-1 text-xs">
                <div className="flex justify-between"><span className="text-stone-500">Status</span><span className="font-semibold text-emerald-700">{selected.status || "Connected"}</span></div>
                {selected.configured_at && <div className="flex justify-between"><span className="text-stone-500">Connected</span><span>{String(selected.configured_at).slice(0, 16).replace("T", " ")}</span></div>}
                {selected.last_sync && <div className="flex justify-between"><span className="text-stone-500">Last Sync</span><span>{String(selected.last_sync).slice(0, 16).replace("T", " ")}</span></div>}
              </div>
            )}
            <div className="flex items-center gap-2">
              {(selected.installed || selected.enabled) ? (
                <>
                  <Button size="sm" onClick={() => sync(selected.id)} className="bg-blue-600 hover:bg-blue-700 text-white"><RefreshCw className="w-3.5 h-3.5 mr-1" />Sync Now</Button>
                  <Button size="sm" variant="outline" onClick={() => { toggle(selected.id); }}>{selected.enabled ? "Pause" : "Resume"}</Button>
                  <Button size="sm" variant="outline" onClick={() => { uninstall(selected.id); setSelected(null); }} className="text-red-600 hover:bg-red-50 ml-auto" data-testid={`uninstall-btn`}>
                    <Trash2 className="w-3.5 h-3.5 mr-1" />Disconnect
                  </Button>
                </>
              ) : (
                <Button size="sm" onClick={() => { install(selected.id); setSelected(null); }} disabled={!isManager}
                  className="flex-1 bg-stone-800 hover:bg-stone-700 text-white" data-testid="install-btn">
                  <Plug className="w-3.5 h-3.5 mr-1" />Connect {selected.name}
                </Button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
