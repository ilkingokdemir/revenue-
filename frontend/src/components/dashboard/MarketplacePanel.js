/**
 * MarketplacePanel — Mews-parity Batch 3 Feature 1 (iter 358).
 *
 * Curated integration hub. Category tabs + app cards with install/uninstall
 * flow. Backed by `GET/POST /api/marketplace/*`.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Store, Loader2, Check, ExternalLink, Sparkles, Search, X,
  ToggleLeft, ToggleRight,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_STYLES = {
  installed:  { badge: "bg-emerald-500 text-white",       label: "Yüklü",     dot: "bg-emerald-400" },
  disabled:   { badge: "bg-stone-400 text-white",         label: "Duraklatıldı", dot: "bg-stone-400" },
  available:  { badge: "bg-sky-500/20 text-sky-700 border border-sky-400/40",  label: "Kur",       dot: "bg-sky-400" },
  coming_soon:{ badge: "bg-amber-500/20 text-amber-700 border border-amber-400/40", label: "Yakında", dot: "bg-amber-400" },
};

export default function MarketplacePanel({ propertyId, hotelName = "" }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [category, setCategory] = useState("all");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);
  const [configDraft, setConfigDraft] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/marketplace/catalog`, {
        params: { property_id: propertyId },
      });
      setData(r.data);
    } catch (e) {
      toast.error("Marketplace yüklenemedi");
    } finally { setLoading(false); }
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const install = async (app, cfg = null) => {
    setBusy(true);
    try {
      await axios.post(`${API}/marketplace/install`, {
        app_id: app.id, property_id: propertyId,
        config: cfg ? tryParseJson(cfg) : {},
      });
      toast.success(`✅ ${app.name} kuruldu`);
      setSelected(null);
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Kurulum başarısız");
    } finally { setBusy(false); }
  };

  const uninstall = async (app) => {
    if (!window.confirm(`${app.name} kaldırılsın mı? Config kaybedilecek.`)) return;
    setBusy(true);
    try {
      await axios.post(`${API}/marketplace/uninstall`, {
        app_id: app.id, property_id: propertyId,
      });
      toast.success(`${app.name} kaldırıldı`);
      setSelected(null);
      await load();
    } catch (e) {
      toast.error("Kaldırma başarısız");
    } finally { setBusy(false); }
  };

  const toggleEnabled = async (app) => {
    const target = app.status !== "disabled";
    try {
      await axios.post(`${API}/marketplace/toggle`, {
        app_id: app.id, property_id: propertyId, enabled: !target,
      });
      toast.success(target ? "Duraklatıldı" : "Aktifleştirildi");
      await load();
    } catch { toast.error("Değiştirilemedi"); }
  };

  const filtered = (data?.items || []).filter(a => {
    if (category !== "all" && a.category !== category) return false;
    if (search && !`${a.name} ${a.provider} ${a.summary}`.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="space-y-5" data-testid="marketplace-panel">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-fuchsia-500 to-indigo-600 flex items-center justify-center shadow-lg">
            <Store className="w-6 h-6 text-white" />
          </div>
          <div>
            <h2 className="text-2xl font-black text-stone-100">Marketplace</h2>
            <p className="text-xs text-stone-400 mt-0.5">
              {hotelName ? `${hotelName} · ` : ""}Otelinizi 3. parti araçlara bağlayın · {data?.total || 0} entegrasyon
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="text-[9px] text-stone-500 uppercase font-bold">Yüklü</p>
            <p className="text-2xl font-black text-emerald-400" data-testid="marketplace-installed-count">{data?.installed_count || 0}</p>
          </div>
        </div>
      </div>

      {/* Search + Category tabs */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-xs">
          <Search className="w-4 h-4 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Ara: Stripe, Twilio, Booking.com..."
            data-testid="marketplace-search"
            className="w-full pl-9 pr-3 py-2 rounded-lg bg-stone-800 border border-stone-700 text-sm text-stone-100 placeholder:text-stone-500 focus:border-fuchsia-500 outline-none"
          />
        </div>
        <div className="flex items-center gap-1.5 flex-wrap" data-testid="marketplace-categories">
          <button
            onClick={() => setCategory("all")}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${category === "all" ? "bg-fuchsia-500 text-white" : "bg-stone-800 text-stone-300 hover:bg-stone-700"}`}
          >
            Tümü
          </button>
          {(data?.categories || []).map(c => (
            <button
              key={c.id}
              onClick={() => setCategory(c.id)}
              data-testid={`marketplace-cat-${c.id}`}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors inline-flex items-center gap-1 ${category === c.id ? "bg-fuchsia-500 text-white" : "bg-stone-800 text-stone-300 hover:bg-stone-700"}`}
            >
              <span>{c.icon}</span> {c.label}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="text-center py-12"><Loader2 className="w-6 h-6 animate-spin text-stone-500 mx-auto" /></div>
      )}

      {/* App grid */}
      {!loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="marketplace-grid">
          {filtered.map(app => {
            const st = STATUS_STYLES[app.status] || STATUS_STYLES.available;
            const isInstalled = app.status === "installed" || app.status === "disabled";
            return (
              <div
                key={app.id}
                data-testid={`marketplace-card-${app.id}`}
                className={`rounded-xl border p-4 transition-all hover:scale-[1.02] ${isInstalled ? "border-emerald-500/40 bg-emerald-950/20" : app.status === "coming_soon" ? "border-amber-500/20 bg-stone-900/40 opacity-70" : "border-stone-700 bg-stone-900/60 hover:border-fuchsia-500/60"}`}
              >
                <div className="flex items-start gap-3">
                  <div className="w-11 h-11 rounded-lg bg-stone-800 flex items-center justify-center text-2xl flex-shrink-0">
                    {app.logo}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <h4 className="text-sm font-bold text-stone-100 truncate">{app.name}</h4>
                      {app.featured && <Sparkles className="w-3 h-3 text-amber-300 flex-shrink-0" />}
                    </div>
                    <p className="text-[10px] text-stone-500 uppercase tracking-wide">{app.provider}</p>
                  </div>
                  <span className={`text-[9px] px-2 py-0.5 rounded-full font-bold whitespace-nowrap ${st.badge}`}>
                    {app.status === "installed" || app.status === "disabled" ? (
                      <><Check className="w-2.5 h-2.5 inline mr-0.5" /> {st.label}</>
                    ) : st.label}
                  </span>
                </div>
                <p className="text-xs text-stone-400 mt-2.5 leading-relaxed line-clamp-2">
                  {app.summary}
                </p>
                <div className="mt-3 flex items-center gap-1.5">
                  <button
                    onClick={() => { setSelected(app); setConfigDraft(""); }}
                    disabled={app.status === "coming_soon"}
                    data-testid={`marketplace-open-${app.id}`}
                    className={`flex-1 text-[11px] px-3 py-1.5 rounded-lg font-bold transition-colors inline-flex items-center justify-center gap-1 ${
                      app.status === "coming_soon"
                        ? "bg-stone-800 text-stone-500 cursor-not-allowed"
                        : isInstalled
                          ? "bg-stone-700 hover:bg-stone-600 text-stone-100"
                          : "bg-fuchsia-500 hover:bg-fuchsia-600 text-white"
                    }`}
                  >
                    {app.status === "coming_soon" ? "Yakında" : isInstalled ? "Yönet" : "Kur"}
                    {!isInstalled && app.status !== "coming_soon" && <ExternalLink className="w-3 h-3" />}
                  </button>
                  {isInstalled && (
                    <button
                      onClick={() => toggleEnabled(app)}
                      title={app.status === "disabled" ? "Aktifleştir" : "Duraklat"}
                      data-testid={`marketplace-toggle-${app.id}`}
                      className="p-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-300"
                    >
                      {app.status === "disabled" ? <ToggleLeft className="w-4 h-4" /> : <ToggleRight className="w-4 h-4 text-emerald-400" />}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
          {filtered.length === 0 && (
            <div className="col-span-full text-center py-16 text-stone-500 text-sm">
              Sonuç yok. Farklı bir kategori veya arama deneyin.
            </div>
          )}
        </div>
      )}

      {/* App Detail Modal */}
      {selected && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-stone-900 border border-stone-700 rounded-2xl shadow-2xl w-full max-w-md" data-testid="marketplace-detail-modal">
            <div className="p-5 border-b border-stone-800 flex items-start gap-3">
              <div className="w-14 h-14 rounded-xl bg-stone-800 flex items-center justify-center text-3xl flex-shrink-0">
                {selected.logo}
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-black text-stone-100">{selected.name}</h3>
                <p className="text-xs text-stone-500">{selected.provider}</p>
              </div>
              <button onClick={() => setSelected(null)} className="p-1 rounded hover:bg-stone-800 text-stone-400">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-3">
              <p className="text-sm text-stone-300 leading-relaxed">{selected.summary}</p>
              {selected.requires_config && (
                <div className="bg-stone-950/60 border border-stone-800 rounded-lg p-3">
                  <p className="text-[10px] text-fuchsia-300/80 uppercase font-bold mb-1.5">
                    Yapılandırma ipucu
                  </p>
                  <p className="text-xs text-stone-300">{selected.config_hint}</p>
                  <textarea
                    value={configDraft}
                    onChange={e => setConfigDraft(e.target.value)}
                    placeholder={`Optional JSON config, örn:\n{"api_key": "sk_test_...", "webhook_url": "..."}`}
                    rows={3}
                    data-testid="marketplace-config-input"
                    className="w-full mt-2 px-2 py-1.5 rounded bg-stone-950 border border-stone-800 text-xs text-stone-100 font-mono focus:border-fuchsia-500 outline-none"
                  />
                </div>
              )}
            </div>
            <div className="p-4 border-t border-stone-800 flex items-center gap-2">
              {selected.status === "installed" || selected.status === "disabled" ? (
                <>
                  <button
                    onClick={() => uninstall(selected)}
                    disabled={busy}
                    data-testid="marketplace-uninstall"
                    className="flex-1 px-3 py-2 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 text-sm font-bold border border-rose-500/40 disabled:opacity-50"
                  >
                    Kaldır
                  </button>
                  <button
                    onClick={() => install(selected, configDraft)}
                    disabled={busy}
                    data-testid="marketplace-update-config"
                    className="flex-1 px-3 py-2 rounded-lg bg-fuchsia-500 hover:bg-fuchsia-600 text-white text-sm font-bold disabled:opacity-50 inline-flex items-center justify-center gap-1"
                  >
                    {busy && <Loader2 className="w-3 h-3 animate-spin" />}
                    Config güncelle
                  </button>
                </>
              ) : (
                <button
                  onClick={() => install(selected, configDraft)}
                  disabled={busy || selected.status === "coming_soon"}
                  data-testid="marketplace-install-confirm"
                  className="flex-1 px-3 py-2 rounded-lg bg-fuchsia-500 hover:bg-fuchsia-600 text-white text-sm font-bold disabled:opacity-50 inline-flex items-center justify-center gap-1"
                >
                  {busy && <Loader2 className="w-3 h-3 animate-spin" />}
                  {selected.status === "coming_soon" ? "Yakında" : "Kur"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function tryParseJson(str) {
  if (!str || !str.trim()) return {};
  try { return JSON.parse(str); } catch { return { raw: str }; }
}
