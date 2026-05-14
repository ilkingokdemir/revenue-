import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Medal, FloppyDisk, Plus, Trash } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/loyalty-tiers`;

const TIER_BADGE = {
  Silver: "bg-stone-200 text-stone-700",
  Gold: "bg-amber-100 text-amber-700",
  Platinum: "bg-violet-100 text-violet-700",
};

export default function LoyaltyTiersPanel() {
  const [config, setConfig] = useState({ tiers: [] });
  const [members, setMembers] = useState({ members: [], by_tier: {}, count: 0 });
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState("config");

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [c, m] = await Promise.all([
        axios.get(`${API}/config`, { withCredentials: true }),
        axios.get(`${API}/members`, { withCredentials: true }),
      ]);
      setConfig({ tiers: c.data?.tiers || [] });
      setMembers(m.data || { members: [], by_tier: {}, count: 0 });
    } catch (e) { toast.error("Yüklenemedi"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { reload(); }, [reload]);

  async function saveConfig() {
    try {
      await axios.put(`${API}/config`, { tiers: config.tiers }, { withCredentials: true });
      toast.success("Eşik değerleri güncellendi");
      reload();
    } catch (e) { toast.error("Kaydedilemedi"); }
  }

  function updateTier(idx, field, value) {
    const next = [...config.tiers];
    next[idx] = { ...next[idx], [field]: field.includes("min_") ? Number(value) : value };
    setConfig({ tiers: next });
  }
  function updateBenefits(idx, text) {
    const next = [...config.tiers];
    next[idx] = { ...next[idx], benefits: text.split("\n").map(s => s.trim()).filter(Boolean) };
    setConfig({ tiers: next });
  }
  function addTier() {
    setConfig({ tiers: [...config.tiers, { name: "New Tier", min_stays: 0, min_spend: 0, benefits: [] }] });
  }
  function removeTier(idx) {
    setConfig({ tiers: config.tiers.filter((_, i) => i !== idx) });
  }

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="loyalty-tiers-panel">
      <div className="mb-4">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Medal size={12} weight="fill" className="text-amber-500" />
          <span>Loyalty Engine</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">Sadakat Seviyeleri (Silver / Gold / Platinum)</h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Otomatik konaklama/harcama bazlı tier yükseltme — VIP misafirleri tanıyın, doğru avantajları otomatik tahsis edin.
        </p>
      </div>

      <div className="flex gap-1 mb-4 border-b border-stone-200">
        <button onClick={() => setTab("config")} data-testid="lt-tab-config"
                className={`px-4 py-2 text-xs font-medium border-b-2 ${tab === "config" ? "border-stone-900 text-stone-900" : "border-transparent text-stone-500"}`}>
          Yapılandırma
        </button>
        <button onClick={() => setTab("members")} data-testid="lt-tab-members"
                className={`px-4 py-2 text-xs font-medium border-b-2 ${tab === "members" ? "border-stone-900 text-stone-900" : "border-transparent text-stone-500"}`}>
          Üyeler ({members.count})
        </button>
      </div>

      {loading && <div className="text-center py-12 text-stone-400 text-sm">Yükleniyor…</div>}

      {!loading && tab === "config" && (
        <div className="space-y-3">
          {config.tiers.map((t, i) => (
            <div key={i} className="bg-white border border-stone-200 rounded-xl p-4" data-testid={`lt-tier-${i}`}>
              <div className="flex items-start gap-3">
                <input value={t.name} onChange={e => updateTier(i, "name", e.target.value)}
                       className="font-semibold text-base px-2 py-1 border border-stone-300 rounded w-40" />
                <button onClick={() => removeTier(i)} className="ml-auto text-stone-400 hover:text-rose-500">
                  <Trash size={14} />
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3">
                <label className="text-xs text-stone-600">Min Konaklama
                  <input type="number" value={t.min_stays} onChange={e => updateTier(i, "min_stays", e.target.value)}
                         className="w-full mt-1 px-2 py-1 text-sm border border-stone-300 rounded" />
                </label>
                <label className="text-xs text-stone-600">Min Harcama
                  <input type="number" value={t.min_spend} onChange={e => updateTier(i, "min_spend", e.target.value)}
                         className="w-full mt-1 px-2 py-1 text-sm border border-stone-300 rounded" />
                </label>
                <label className="text-xs text-stone-600 md:col-span-3">Avantajlar (her satır bir avantaj)
                  <textarea value={(t.benefits || []).join("\n")} onChange={e => updateBenefits(i, e.target.value)}
                            rows={3} className="w-full mt-1 px-2 py-1 text-sm border border-stone-300 rounded" />
                </label>
              </div>
            </div>
          ))}
          <div className="flex gap-2">
            <button onClick={addTier} className="px-3 py-1.5 text-xs text-stone-700 bg-white border border-stone-300 rounded-lg inline-flex items-center gap-1.5" data-testid="lt-add-tier">
              <Plus size={13} /> Seviye Ekle
            </button>
            <button onClick={saveConfig} className="px-3 py-1.5 text-xs text-white bg-stone-900 rounded-lg inline-flex items-center gap-1.5" data-testid="lt-save">
              <FloppyDisk size={13} /> Kaydet
            </button>
          </div>
        </div>
      )}

      {!loading && tab === "members" && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            {["Silver", "Gold", "Platinum", "None"].map(t => (
              <div key={t} className="bg-white border border-stone-200 rounded-xl p-3">
                <div className="text-[10px] uppercase tracking-wider text-stone-500">{t === "None" ? "Tier Yok" : t}</div>
                <div className="text-xl font-semibold mt-0.5">{members.by_tier?.[t] || 0}</div>
              </div>
            ))}
          </div>
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
                <tr><th className="px-4 py-2 text-left">E-posta</th><th className="px-4 py-2 text-left">Seviye</th><th className="px-4 py-2 text-left">Konaklama</th><th className="px-4 py-2 text-left">Harcama</th></tr>
              </thead>
              <tbody>
                {members.members.length === 0 && (
                  <tr><td colSpan={4} className="text-center py-8 text-stone-400 text-xs" data-testid="lt-members-empty">Henüz üye yok.</td></tr>
                )}
                {members.members.map(m => (
                  <tr key={m.guest_email} className="border-t border-stone-100" data-testid={`lt-member-${m.guest_email}`}>
                    <td className="px-4 py-2 text-xs">{m.guest_email}</td>
                    <td className="px-4 py-2">
                      {m.tier ? <span className={`px-2 py-0.5 text-[10px] rounded ${TIER_BADGE[m.tier] || "bg-stone-100"}`}>{m.tier}</span> : <span className="text-stone-400 text-xs">—</span>}
                    </td>
                    <td className="px-4 py-2">{m.total_stays}</td>
                    <td className="px-4 py-2">£{m.total_spend.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
