import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Crown,
  ArrowsClockwise,
  Star,
  Trophy,
  Plus,
  Trash,
  TrendUp,
  PencilSimple,
  CheckCircle,
  Sparkle,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

const COLOR_BG = {
  stone: "bg-stone-100 text-stone-700 border-stone-200",
  amber: "bg-amber-100 text-amber-800 border-amber-200",
  slate: "bg-slate-200 text-slate-700 border-slate-300",
  yellow: "bg-yellow-100 text-yellow-800 border-yellow-300",
  violet: "bg-violet-100 text-violet-800 border-violet-300",
  emerald: "bg-emerald-100 text-emerald-800 border-emerald-200",
  cyan: "bg-cyan-100 text-cyan-800 border-cyan-200",
  rose: "bg-rose-100 text-rose-800 border-rose-200",
};

export default function LoyaltyTierPanel({ propertyId }) {
  const [config, setConfig] = useState(null);
  const [dash, setDash] = useState(null);
  const [tab, setTab] = useState("overview");
  const [loading, setLoading] = useState(false);

  const reload = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [c, d] = await Promise.all([
        axios.get(`${API}/api/loyalty-tier/config/${propertyId}`, { withCredentials: true }),
        axios.get(`${API}/api/loyalty-tier/dashboard/${propertyId}`, { withCredentials: true }),
      ]);
      setConfig(c.data);
      setDash(d.data);
    } catch (e) {
      toast.error("Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId]);

  useEffect(() => { reload(); }, [reload]);

  const runBatch = async () => {
    setLoading(true);
    try {
      const r = await axios.post(`${API}/api/loyalty-tier/evaluate-batch/${propertyId}`, {}, { withCredentials: true });
      toast.success(`${r.data.evaluated} misafir · ↑${r.data.upgraded} terfi · ↓${r.data.downgraded} düşüş · ${r.data.skipped_manual} elle atlandı`);
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Hata");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-5 max-w-[1500px] mx-auto" data-testid="loyalty-tier-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Crown size={12} weight="fill" className="text-yellow-500" />
          <span>Loyalty · Tier Engine</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">Sadakat Kademeleri</h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Misafirlerin yıllık <b>gece + harcama + puan</b> performansına göre otomatik Bronze/Silver/Gold/Platinum kademelerine yerleşir. Manuel override mümkün, audit trail tutulur.
        </p>
      </div>

      {dash && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5" data-testid="lt-stats">
          <Kpi label="Toplam Üye" value={dash.total_members} color="stone" />
          <Kpi label="Manuel Override" value={dash.manual_overrides} color="violet" />
          <Kpi label="Son 30g Hareket" value={dash.recent_upgrades?.length || 0} color="cyan" />
          <Kpi label="Tier Sayısı" value={dash.tiers?.length || 0} color="yellow" />
        </div>
      )}

      <div className="flex items-center gap-2 mb-4">
        <TabBtn active={tab === "overview"} onClick={() => setTab("overview")} testId="lt-tab-overview">Tier Dağılımı</TabBtn>
        <TabBtn active={tab === "config"} onClick={() => setTab("config")} testId="lt-tab-config">Tier Yapılandırması</TabBtn>
        <TabBtn active={tab === "history"} onClick={() => setTab("history")} testId="lt-tab-history">Son Hareketler</TabBtn>
        <button onClick={runBatch} disabled={loading} data-testid="lt-run-batch" className="ml-auto px-3 py-1.5 text-xs rounded-md bg-yellow-500 text-white font-semibold hover:bg-yellow-600 disabled:opacity-50 inline-flex items-center gap-1.5">
          <Sparkle size={12} weight="fill" /> Tüm Misafirleri Yeniden Değerlendir
        </button>
        <button onClick={reload} className="px-3 py-1.5 text-xs rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50 inline-flex items-center gap-1.5">
          <ArrowsClockwise size={12} /> Yenile
        </button>
      </div>

      {tab === "overview" && config && dash && (
        <TierLadder tiers={config.tiers} distribution={dash.distribution} total={dash.total_members} />
      )}
      {tab === "config" && config && (
        <ConfigEditor propertyId={propertyId} initialTiers={config.tiers} onSaved={reload} />
      )}
      {tab === "history" && (
        <HistoryList entries={dash?.recent_upgrades || []} tiers={config?.tiers || []} />
      )}
    </div>
  );
}

function TabBtn({ active, onClick, testId, children }) {
  return (
    <button
      onClick={onClick}
      data-testid={testId}
      className={`px-3 py-1.5 text-xs rounded-md ${active ? "bg-yellow-500 text-white" : "bg-stone-100 text-stone-600 hover:bg-stone-200"}`}
    >
      {children}
    </button>
  );
}

function Kpi({ label, value, color }) {
  const cls = {
    stone: "bg-stone-100 text-stone-700",
    violet: "bg-violet-50 text-violet-700",
    cyan: "bg-cyan-50 text-cyan-700",
    yellow: "bg-yellow-50 text-yellow-800",
  }[color];
  return (
    <div className={`${cls} border border-stone-100 rounded-lg p-3`}>
      <div className="text-[10px] uppercase tracking-wider opacity-70">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
    </div>
  );
}

function TierLadder({ tiers, distribution, total }) {
  return (
    <div className="space-y-3" data-testid="lt-ladder">
      {tiers.map((t, idx) => {
        const count = distribution?.[t.tier_key] || 0;
        const pct = total ? Math.round(count / total * 100) : 0;
        const colorClass = COLOR_BG[t.color] || COLOR_BG.stone;
        return (
          <div key={t.tier_key} className={`bg-white border-2 rounded-xl p-4 ${colorClass}`} data-testid={`lt-tier-${t.tier_key}`}>
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-full bg-white inline-flex items-center justify-center shadow-sm">
                {idx === 0 ? <Star size={20} weight="fill" /> :
                 idx === tiers.length - 1 ? <Crown size={20} weight="fill" /> :
                 <Trophy size={20} weight="fill" />}
              </div>
              <div className="flex-1">
                <div className="text-lg font-bold">{t.name}</div>
                <div className="text-xs opacity-75">
                  ≥{t.threshold_nights} gece · ≥£{t.threshold_revenue} · ≥{t.threshold_points} puan
                </div>
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold">{count}</div>
                <div className="text-[10px] opacity-70">üye · %{pct}</div>
              </div>
            </div>
            {t.benefits?.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {t.benefits.map((b, i) => (
                  <span key={i} className="text-[10px] bg-white/60 border border-current/10 rounded-full px-2 py-0.5">
                    {b}
                  </span>
                ))}
              </div>
            )}
            <div className="mt-2 h-1.5 bg-white/40 rounded overflow-hidden">
              <div className="h-full bg-current opacity-50" style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ConfigEditor({ propertyId, initialTiers, onSaved }) {
  const [tiers, setTiers] = useState(initialTiers || []);
  const [busy, setBusy] = useState(false);

  const addTier = () => {
    setTiers([...tiers, { tier_key: `tier_${tiers.length}`, name: "Yeni Kademe", color: "stone",
      threshold_nights: 0, threshold_revenue: 0, threshold_points: 0, benefits: [] }]);
  };

  const removeTier = (idx) => setTiers(tiers.filter((_, i) => i !== idx));

  const updateTier = (idx, patch) => {
    setTiers(tiers.map((t, i) => i === idx ? { ...t, ...patch } : t));
  };

  const save = async () => {
    setBusy(true);
    try {
      const payload = { tiers: tiers.map((t) => ({
        tier_key: t.tier_key,
        name: t.name,
        color: t.color || "stone",
        threshold_nights: parseInt(t.threshold_nights) || 0,
        threshold_revenue: parseFloat(t.threshold_revenue) || 0,
        threshold_points: parseInt(t.threshold_points) || 0,
        benefits: Array.isArray(t.benefits) ? t.benefits : (t.benefits || "").split(",").map((s) => s.trim()).filter(Boolean),
      })) };
      await axios.post(`${API}/api/loyalty-tier/config/${propertyId}`, payload, { withCredentials: true });
      toast.success("Yapılandırma kaydedildi");
      onSaved?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Hata");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3" data-testid="lt-config-editor">
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-xs text-yellow-900">
        <b>Tier sırası önemli:</b> En düşük tier (üye) en üste, en yüksek (Platinum) en aşağıya. Bir misafir her 3 eşiği de geçtiğinde o kademeye otomatik terfi eder.
      </div>
      {tiers.map((t, idx) => (
        <div key={idx} className="bg-white border border-stone-200 rounded-lg p-3" data-testid={`lt-tier-edit-${idx}`}>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
            <input value={t.tier_key} onChange={(e) => updateTier(idx, { tier_key: e.target.value })} placeholder="key" data-testid={`lt-tier-key-${idx}`} className="px-2 py-1 text-sm border border-stone-200 rounded font-mono" />
            <input value={t.name} onChange={(e) => updateTier(idx, { name: e.target.value })} placeholder="Ad" data-testid={`lt-tier-name-${idx}`} className="px-2 py-1 text-sm border border-stone-200 rounded font-semibold" />
            <select value={t.color} onChange={(e) => updateTier(idx, { color: e.target.value })} data-testid={`lt-tier-color-${idx}`} className="px-2 py-1 text-sm border border-stone-200 rounded">
              {Object.keys(COLOR_BG).map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <input type="number" value={t.threshold_nights} onChange={(e) => updateTier(idx, { threshold_nights: e.target.value })} placeholder="gece" data-testid={`lt-tier-nights-${idx}`} className="px-2 py-1 text-sm border border-stone-200 rounded" />
            <input type="number" value={t.threshold_revenue} onChange={(e) => updateTier(idx, { threshold_revenue: e.target.value })} placeholder="gelir" data-testid={`lt-tier-revenue-${idx}`} className="px-2 py-1 text-sm border border-stone-200 rounded" />
            <div className="flex items-center gap-1">
              <input type="number" value={t.threshold_points} onChange={(e) => updateTier(idx, { threshold_points: e.target.value })} placeholder="puan" data-testid={`lt-tier-points-${idx}`} className="flex-1 px-2 py-1 text-sm border border-stone-200 rounded" />
              <button onClick={() => removeTier(idx)} data-testid={`lt-tier-remove-${idx}`} disabled={tiers.length <= 1} className="w-7 h-7 rounded bg-rose-50 text-rose-500 inline-flex items-center justify-center disabled:opacity-30">
                <Trash size={12} />
              </button>
            </div>
          </div>
          <div className="mt-2">
            <input
              value={Array.isArray(t.benefits) ? t.benefits.join(", ") : t.benefits}
              onChange={(e) => updateTier(idx, { benefits: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
              placeholder="Avantajlar (virgülle: Late checkout 4pm, Welcome amenity, ...)"
              data-testid={`lt-tier-benefits-${idx}`}
              className="w-full px-2 py-1 text-xs border border-stone-100 rounded bg-stone-50"
            />
          </div>
        </div>
      ))}
      <div className="flex gap-2">
        <button onClick={addTier} data-testid="lt-add-tier" className="px-3 py-2 text-sm rounded-md bg-stone-100 text-stone-700 hover:bg-stone-200 inline-flex items-center gap-1.5">
          <Plus size={14} /> Kademe Ekle
        </button>
        <button onClick={save} disabled={busy} data-testid="lt-save-config" className="ml-auto px-4 py-2 text-sm rounded-md bg-yellow-500 text-white font-semibold hover:bg-yellow-600 disabled:opacity-50 inline-flex items-center gap-1.5">
          <CheckCircle size={14} weight="fill" /> {busy ? "Kaydediliyor…" : "Yapılandırmayı Kaydet"}
        </button>
      </div>
    </div>
  );
}

function HistoryList({ entries, tiers }) {
  const tierName = (k) => tiers.find((t) => t.tier_key === k)?.name || k || "—";
  if (!entries.length) {
    return <div className="text-center py-12 text-stone-400 text-sm" data-testid="lt-history-empty">Son 30 günde tier hareketi yok.</div>;
  }
  return (
    <div className="space-y-2" data-testid="lt-history-list">
      {entries.map((e, i) => {
        const fromIdx = tiers.findIndex((t) => t.tier_key === e.from);
        const toIdx = tiers.findIndex((t) => t.tier_key === e.to);
        const isUp = toIdx > fromIdx;
        return (
          <div key={i} className="bg-white border border-stone-200 rounded-lg p-3 flex items-center gap-3" data-testid={`lt-history-row-${i}`}>
            <div className={`w-8 h-8 rounded-full inline-flex items-center justify-center ${isUp ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
              {isUp ? <TrendUp size={14} weight="bold" /> : <PencilSimple size={14} weight="bold" />}
            </div>
            <div className="flex-1">
              <div className="text-sm text-stone-900">
                Misafir <span className="font-mono text-xs text-stone-500">{e.guest_id?.slice(0, 8)}</span>
                {" · "}
                <b>{tierName(e.from)}</b>
                {" → "}
                <b className={isUp ? "text-emerald-700" : "text-amber-700"}>{tierName(e.to)}</b>
              </div>
              <div className="text-[10px] text-stone-400">
                {e.at?.slice(0, 16).replace("T", " ")} · {e.reason} · {e.by}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
