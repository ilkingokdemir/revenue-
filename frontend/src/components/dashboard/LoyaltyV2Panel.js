import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Crown,
  UsersThree,
  Gift,
  Plus,
  Trash,
  CopySimple,
  CheckCircle,
  Sparkle,
  ArrowsClockwise,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

const TIER_META = {
  bronze:   { color: "amber",   label: "Bronze",   icon: "🥉" },
  silver:   { color: "stone",   label: "Silver",   icon: "🥈" },
  gold:     { color: "amber",   label: "Gold",     icon: "🥇" },
  platinum: { color: "violet",  label: "Platinum", icon: "💎" },
};

const PERK_FIELDS = [
  { k: "early_check_in",  label: "Erken giriş (13:00)" },
  { k: "late_check_out",  label: "Geç çıkış (14:00)" },
  { k: "room_upgrade",    label: "Oda upgrade" },
  { k: "free_breakfast",  label: "Ücretsiz kahvaltı" },
  { k: "welcome_amenity", label: "Karşılama amenity" },
  { k: "birthday_gift",   label: "Doğum günü hediyesi" },
];

export default function LoyaltyV2Panel({ propertyId, hotelName }) {
  const [tab, setTab] = useState("tiers");

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="loyalty-v2-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Crown size={12} weight="fill" className="text-violet-500" />
          <span>Loyalty Enterprise</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">
          Sadakat & Paketler · {hotelName || "Property"}
        </h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Tier ayrıcalıkları + Referral programı + Dinamik paketleme.
        </p>
      </div>

      <div className="flex gap-2 mb-5 border-b border-stone-200">
        <TabBtn active={tab === "tiers"} onClick={() => setTab("tiers")} testId="loy-tab-tiers">
          <Crown size={14} className="inline mr-1.5" />
          Tier Ayrıcalıkları
        </TabBtn>
        <TabBtn active={tab === "referrals"} onClick={() => setTab("referrals")} testId="loy-tab-referrals">
          <UsersThree size={14} className="inline mr-1.5" />
          Referral Kodları
        </TabBtn>
        <TabBtn active={tab === "packages"} onClick={() => setTab("packages")} testId="loy-tab-packages">
          <Gift size={14} className="inline mr-1.5" />
          Paketler
        </TabBtn>
      </div>

      {tab === "tiers" && <TiersTab propertyId={propertyId} />}
      {tab === "referrals" && <ReferralsTab propertyId={propertyId} />}
      {tab === "packages" && <PackagesTab propertyId={propertyId} />}
    </div>
  );
}

function TabBtn({ active, onClick, children, testId }) {
  return (
    <button
      onClick={onClick}
      data-testid={testId}
      className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition ${
        active
          ? "border-violet-500 text-violet-600"
          : "border-transparent text-stone-500 hover:text-stone-700"
      }`}
    >
      {children}
    </button>
  );
}

function TiersTab({ propertyId }) {
  const [benefits, setBenefits] = useState([]);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/api/loyalty-v2/benefits/${propertyId}`);
      setBenefits(data.benefits || []);
    } catch (_) { /* silent */ }
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const update = async (tier, patch) => {
    const current = benefits.find((b) => b.tier === tier) || {};
    try {
      await axios.put(`${API}/api/loyalty-v2/benefits/${propertyId}/${tier}`, {
        property_id: propertyId, tier,
        ...current, ...patch,
      });
      load();
    } catch (_) { toast.error("Güncelleme başarısız"); }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3" data-testid="tiers-grid">
      {benefits.map((b) => {
        const meta = TIER_META[b.tier] || TIER_META.bronze;
        return (
          <div key={b.tier} className={`p-5 rounded-xl bg-white border border-stone-200`}
            data-testid={`tier-card-${b.tier}`}>
            <div className="flex items-center gap-2 mb-4">
              <span className="text-2xl">{meta.icon}</span>
              <div>
                <div className="font-bold text-lg text-stone-900 capitalize">{meta.label}</div>
                <div className="text-[10px] uppercase tracking-wider text-stone-500">Tier</div>
              </div>
            </div>
            <div className="space-y-2">
              {PERK_FIELDS.map((p) => (
                <label key={p.k} className="flex items-center justify-between p-2 rounded-lg hover:bg-stone-50 cursor-pointer">
                  <span className="text-sm text-stone-700">{p.label}</span>
                  <input
                    type="checkbox"
                    checked={!!b[p.k]}
                    onChange={(e) => update(b.tier, { [p.k]: e.target.checked })}
                    className="w-4 h-4"
                    data-testid={`tier-${b.tier}-${p.k}`}
                  />
                </label>
              ))}
              <div className="flex items-center justify-between p-2 rounded-lg">
                <span className="text-sm text-stone-700">F&B indirimi %</span>
                <input type="number" value={b.fnb_discount_pct || 0} min={0} max={50}
                  onChange={(e) => update(b.tier, { fnb_discount_pct: Number(e.target.value) })}
                  className="w-16 px-2 py-1 rounded border border-stone-300 text-sm text-right" />
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg">
                <span className="text-sm text-stone-700">Spa indirimi %</span>
                <input type="number" value={b.spa_discount_pct || 0} min={0} max={50}
                  onChange={(e) => update(b.tier, { spa_discount_pct: Number(e.target.value) })}
                  className="w-16 px-2 py-1 rounded border border-stone-300 text-sm text-right" />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ReferralsTab({ propertyId }) {
  const [data, setData] = useState({ rows: [], count: 0 });
  const [creating, setCreating] = useState(false);
  const [guestId, setGuestId] = useState("");
  const [refPct, setRefPct] = useState(10);
  const [refPoints, setRefPoints] = useState(500);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/api/loyalty-v2/referrals/${propertyId}`);
      setData(data);
    } catch (_) { /* silent */ }
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const create = async () => {
    if (!guestId.trim()) {
      toast.error("Referrer guest ID gerekli");
      return;
    }
    setCreating(true);
    try {
      await axios.post(`${API}/api/loyalty-v2/referrals`, {
        property_id: propertyId,
        referrer_guest_id: guestId.trim(),
        benefit_for_referee_pct: refPct,
        benefit_for_referrer_points: refPoints,
      });
      toast.success("Referral kodu oluşturuldu");
      setGuestId("");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Oluşturma başarısız");
    }
    setCreating(false);
  };

  const copy = (code) => {
    navigator.clipboard.writeText(code);
    toast.success(`Kopyalandı: ${code}`);
  };

  return (
    <div className="space-y-4" data-testid="referrals-tab">
      <div className="grid grid-cols-3 gap-3">
        <Kpi label="Toplam kod" value={data.count} accent="stone" />
        <Kpi label="Oluşan rezervasyon" value={data.total_bookings_generated || 0} accent="emerald" />
        <Kpi label="Dağıtılan puan" value={(data.total_earned_points || 0).toLocaleString()} accent="violet" />
      </div>

      {/* Create form */}
      <div className="p-4 rounded-xl bg-white border border-stone-200">
        <h3 className="text-sm font-semibold text-stone-900 mb-3">Yeni Referral Kodu</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
          <div>
            <label className="text-xs text-stone-500">Referrer Guest ID</label>
            <input value={guestId} onChange={(e) => setGuestId(e.target.value)}
              placeholder="UUID" className="w-full px-3 py-2 rounded-lg border border-stone-300 text-sm font-mono"
              data-testid="referral-guest-id" />
          </div>
          <div>
            <label className="text-xs text-stone-500">Misafire indirim %</label>
            <input type="number" value={refPct} min={0} max={50}
              onChange={(e) => setRefPct(Number(e.target.value))}
              className="w-full px-3 py-2 rounded-lg border border-stone-300 text-sm" />
          </div>
          <div>
            <label className="text-xs text-stone-500">Referrer'a puan</label>
            <input type="number" value={refPoints} min={0} step={100}
              onChange={(e) => setRefPoints(Number(e.target.value))}
              className="w-full px-3 py-2 rounded-lg border border-stone-300 text-sm" />
          </div>
          <button onClick={create} disabled={creating}
            className="px-4 py-2 bg-violet-600 text-white rounded-lg text-sm font-medium hover:bg-violet-700 disabled:opacity-50 flex items-center justify-center gap-2"
            data-testid="referral-create">
            <Plus size={14} />
            {creating ? "…" : "Oluştur"}
          </button>
        </div>
      </div>

      {/* List */}
      <div className="rounded-xl bg-white border border-stone-200 overflow-hidden">
        {data.rows.length === 0 && (
          <div className="text-xs text-stone-500 py-8 text-center">Henüz referral kodu yok.</div>
        )}
        <div className="divide-y divide-stone-100">
          {data.rows.map((r) => (
            <div key={r.id} className="flex items-center gap-3 p-3 text-sm" data-testid={`referral-${r.id}`}>
              <div className="font-mono text-sm font-bold text-violet-600 bg-violet-50 px-2 py-1 rounded">
                {r.code}
              </div>
              <button onClick={() => copy(r.code)} className="p-1 text-stone-400 hover:text-stone-700" title="Kopyala">
                <CopySimple size={14} />
              </button>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-stone-900 truncate">
                  {r.referrer_name || r.referrer_guest_id}
                </div>
                <div className="text-xs text-stone-500 mt-0.5">
                  Misafir -{r.benefit_for_referee_pct}% · Referrer +{r.benefit_for_referrer_points} puan
                </div>
              </div>
              <div className="text-right">
                <div className="text-xs font-bold text-emerald-700">{r.times_used || 0} kullanım</div>
                <div className="text-[10px] text-stone-500">{r.total_bookings_generated || 0} booking</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PackagesTab({ propertyId }) {
  const [list, setList] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/api/loyalty-v2/packages/${propertyId}`);
      setList(data.packages || []);
    } catch (_) { /* silent */ }
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const seed = async () => {
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/api/loyalty-v2/packages/${propertyId}/seed-defaults`);
      if (data.seeded === 0) toast.info(data.note);
      else toast.success(`${data.seeded} paket eklendi`);
      load();
    } catch (_) { toast.error("Seed başarısız"); }
    setBusy(false);
  };

  const del = async (id) => {
    if (!window.confirm("Bu paketi sil?")) return;
    try {
      await axios.delete(`${API}/api/loyalty-v2/packages/${id}`);
      toast.success("Silindi");
      load();
    } catch (_) { toast.error("Silme başarısız"); }
  };

  const toggleActive = async (p) => {
    try {
      await axios.put(`${API}/api/loyalty-v2/packages/${p.id}`, { ...p, active: !p.active });
      load();
    } catch (_) { toast.error("Güncelleme başarısız"); }
  };

  return (
    <div className="space-y-4" data-testid="packages-tab">
      <div className="flex items-center gap-2">
        {list.length === 0 && (
          <button onClick={seed} disabled={busy}
            className="px-3 py-1.5 bg-violet-600 text-white rounded-lg text-sm font-medium hover:bg-violet-700 flex items-center gap-1.5"
            data-testid="package-seed">
            <Sparkle size={14} />
            3 varsayılan paket ekle
          </button>
        )}
        <button onClick={load} className="ml-auto p-2 text-stone-500 hover:text-stone-800">
          <ArrowsClockwise size={14} />
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {list.map((p) => (
          <div key={p.id} className={`p-4 rounded-xl bg-white border ${p.active ? "border-violet-200" : "border-stone-200 opacity-60"}`}
            data-testid={`package-${p.id}`}>
            <div className="flex items-start gap-2 mb-2">
              <div className="w-9 h-9 rounded-xl bg-violet-100 text-violet-700 flex items-center justify-center shrink-0">
                <Gift size={18} weight="bold" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-bold text-stone-900 truncate">{p.name}</div>
                {p.description && <div className="text-xs text-stone-500 mt-0.5 line-clamp-2">{p.description}</div>}
              </div>
            </div>

            <div className="space-y-1.5 my-3 pb-3 border-b border-stone-100">
              {(p.components || []).map((c, i) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <span className="text-stone-700 truncate">
                    <span className="text-stone-400 uppercase text-[9px] font-mono mr-1">{c.type}</span>
                    {c.name}
                  </span>
                  <span className="text-stone-500 font-mono ml-2 shrink-0">
                    £{c.alacarte_price}{c.qty > 1 ? ` ×${c.qty}` : ""}
                  </span>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-2 gap-2 text-center">
              <div>
                <div className="text-[10px] uppercase tracking-wider text-stone-500">A la carte</div>
                <div className="text-sm text-stone-400 line-through">£{p.alacarte_total}</div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wider text-violet-600">Paket</div>
                <div className="text-lg font-bold text-violet-700">£{p.package_price}</div>
              </div>
            </div>

            {p.savings > 0 && (
              <div className="mt-3 text-center p-2 rounded-lg bg-emerald-50 border border-emerald-200">
                <div className="text-xs font-bold text-emerald-700">
                  £{p.savings} tasarruf (%{p.savings_pct})
                </div>
              </div>
            )}

            <div className="mt-3 flex gap-2 text-xs">
              <button onClick={() => toggleActive(p)}
                className={`flex-1 px-2 py-1.5 rounded-md ${p.active ? "bg-emerald-100 text-emerald-700" : "bg-stone-100 text-stone-600"}`}>
                {p.active ? "✓ Aktif" : "Pasif"}
              </button>
              <button onClick={() => del(p.id)}
                className="p-1.5 text-stone-400 hover:text-rose-600">
                <Trash size={14} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Kpi({ label, value, accent }) {
  const m = {
    emerald: "text-emerald-700", violet: "text-violet-700",
    stone: "text-stone-900",
  };
  return (
    <div className="p-3 rounded-xl bg-white border border-stone-200">
      <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-1">{label}</div>
      <div className={`text-2xl font-bold ${m[accent] || m.stone}`}>{value}</div>
    </div>
  );
}
