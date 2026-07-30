import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ShieldCheck, Loader2, Plus, PiggyBank, FileWarning, CheckCircle2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_META = {
  open: { label: "Açık", cls: "bg-amber-100 text-amber-800 border-amber-300" },
  under_review: { label: "İncelemede", cls: "bg-sky-100 text-sky-800 border-sky-300" },
  approved: { label: "Onaylandı", cls: "bg-emerald-100 text-emerald-800 border-emerald-300" },
  denied: { label: "Reddedildi", cls: "bg-rose-100 text-rose-800 border-rose-300" },
  settled: { label: "Ödendi", cls: "bg-violet-100 text-violet-800 border-violet-300" },
};

export function DamageProtectionPanel({ activePropertyId }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : "default";
  const [cfg, setCfg] = useState(null);
  const [stats, setStats] = useState(null);
  const [claims, setClaims] = useState([]);
  const [saving, setSaving] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ guest_name: "", booking_id: "", description: "", amount: "" });

  const load = useCallback(async () => {
    try {
      const [c, s, cl] = await Promise.all([
        axios.get(`${API}/damage-protection/config/${pid}`),
        axios.get(`${API}/damage-protection/stats/${pid}`),
        axios.get(`${API}/damage-protection/claims/${pid}`),
      ]);
      setCfg(c.data); setStats(s.data); setClaims(cl.data || []);
    } catch { toast.error("Yüklenemedi"); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const saveConfig = async (patch) => {
    setSaving(true);
    try {
      const next = { enabled: cfg.enabled, fee_per_night: parseFloat(cfg.fee_per_night) || 0,
        coverage_limit: parseFloat(cfg.coverage_limit) || 0, currency: cfg.currency || "GBP", ...patch };
      await axios.put(`${API}/damage-protection/config/${pid}`, next);
      toast.success("Kaydedildi");
      load();
    } catch { toast.error("Kaydedilemedi"); }
    finally { setSaving(false); }
  };

  const createClaim = async () => {
    if (!form.guest_name || !form.description || !parseFloat(form.amount)) {
      toast.error("Misafir adı, açıklama ve tutar zorunlu"); return;
    }
    try {
      await axios.post(`${API}/damage-protection/claims`, {
        property_id: pid, ...form, amount: parseFloat(form.amount),
      });
      toast.success("Hasar talebi oluşturuldu");
      setShowForm(false); setForm({ guest_name: "", booking_id: "", description: "", amount: "" });
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Oluşturulamadı"); }
  };

  const updateStatus = async (id, status) => {
    try {
      await axios.put(`${API}/damage-protection/claims/${id}`, { status });
      toast.success(`Durum: ${STATUS_META[status].label}`);
      load();
    } catch { toast.error("Güncellenemedi"); }
  };

  if (!cfg || !stats) return <div className="p-10 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-stone-400" /></div>;
  const cur = stats.currency || "GBP";

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5" data-testid="damage-protection-panel">
      <div>
        <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2">
          <ShieldCheck size={22} className="text-emerald-600" />
          Hasar Koruması (Damage Waiver)
        </h1>
        <p className="text-sm text-stone-500 mt-0.5">
          Depozito yerine gecelik küçük ücretle hasar teminatı — fon havuzu ve talep yönetimi (Guesty Shield paritesi).
        </p>
      </div>

      {/* Config */}
      <div className="bg-white border border-stone-200 rounded-2xl p-5 flex flex-wrap items-end gap-4">
        <div>
          <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Durum</label>
          <button onClick={() => saveConfig({ enabled: !cfg.enabled })} disabled={saving}
            data-testid="dp-toggle"
            className={`px-4 py-2 rounded-xl text-xs font-bold ${cfg.enabled ? "bg-emerald-600 text-white" : "bg-stone-200 text-stone-600"}`}>
            {cfg.enabled ? "AKTİF" : "PASİF"}
          </button>
        </div>
        <div>
          <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Gecelik ücret ({cur})</label>
          <input type="number" step="0.5" value={cfg.fee_per_night}
            onChange={e => setCfg({ ...cfg, fee_per_night: e.target.value })}
            onBlur={() => saveConfig({})} data-testid="dp-fee"
            className="w-28 border border-stone-200 rounded-lg px-3 py-2 text-sm" />
        </div>
        <div>
          <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Teminat limiti ({cur})</label>
          <input type="number" step="100" value={cfg.coverage_limit}
            onChange={e => setCfg({ ...cfg, coverage_limit: e.target.value })}
            onBlur={() => saveConfig({})} data-testid="dp-limit"
            className="w-32 border border-stone-200 rounded-lg px-3 py-2 text-sm" />
        </div>
        <p className="text-[11px] text-stone-400 flex-1 min-w-[200px]">
          Ücret rezervasyon başına gece × oda olarak tahsil edilir; havuz onaylanan hasar taleplerini karşılar.
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="dp-stats">
        <Kpi icon={PiggyBank} label="Tahmini prim (90g)" value={`${stats.estimated_collected_90d.toLocaleString()}`} />
        <Kpi label="Kapsanan gece (90g)" value={stats.covered_nights_90d} />
        <Kpi icon={FileWarning} label="Açık talep" value={stats.claims_open} warn={stats.claims_open > 0} />
        <Kpi label="Ödenen hasar" value={`${stats.claims_paid_amount.toLocaleString()}`} />
        <Kpi icon={CheckCircle2} label="Net havuz (90g)" value={`${stats.net_pool_90d.toLocaleString()}`} highlight />
      </div>

      {/* Claims */}
      <div className="bg-white border border-stone-200 rounded-2xl p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-black text-stone-900">Hasar Talepleri ({claims.length})</h2>
          <button onClick={() => setShowForm(!showForm)} data-testid="dp-new-claim-btn"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-stone-900 hover:bg-stone-700 text-white text-xs font-bold">
            <Plus className="w-3.5 h-3.5" /> Yeni Talep
          </button>
        </div>

        {showForm && (
          <div className="mb-4 p-4 rounded-xl bg-stone-50 border border-stone-200 grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="dp-claim-form">
            <input placeholder="Misafir adı *" value={form.guest_name}
              onChange={e => setForm({ ...form, guest_name: e.target.value })}
              data-testid="dp-claim-guest" className="border border-stone-200 rounded-lg px-3 py-2 text-sm" />
            <input placeholder="Rezervasyon ID (ops.)" value={form.booking_id}
              onChange={e => setForm({ ...form, booking_id: e.target.value })}
              className="border border-stone-200 rounded-lg px-3 py-2 text-sm" />
            <input placeholder="Tutar *" type="number" value={form.amount}
              onChange={e => setForm({ ...form, amount: e.target.value })}
              data-testid="dp-claim-amount" className="border border-stone-200 rounded-lg px-3 py-2 text-sm" />
            <button onClick={createClaim} data-testid="dp-claim-submit"
              className="px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold">Oluştur</button>
            <textarea placeholder="Hasar açıklaması *" rows={2} value={form.description}
              onChange={e => setForm({ ...form, description: e.target.value })}
              data-testid="dp-claim-desc" className="col-span-2 md:col-span-4 border border-stone-200 rounded-lg px-3 py-2 text-sm resize-none" />
          </div>
        )}

        <div className="space-y-2" data-testid="dp-claims-list">
          {claims.length === 0 && <p className="text-xs text-stone-400 py-4 text-center">Henüz hasar talebi yok.</p>}
          {claims.map(c => {
            const m = STATUS_META[c.status] || STATUS_META.open;
            return (
              <div key={c.id} className="flex flex-wrap items-center gap-3 p-3 rounded-xl border border-stone-100 bg-stone-50" data-testid={`dp-claim-${c.id}`}>
                <span className={`text-[9px] uppercase font-black px-2 py-0.5 rounded-full border ${m.cls}`}>{m.label}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-bold text-stone-900">{c.guest_name} · {Number(c.amount).toLocaleString()} {cur}</p>
                  <p className="text-[11px] text-stone-500 truncate">{c.description}</p>
                </div>
                {c.status !== "settled" && c.status !== "denied" && (
                  <div className="flex gap-1.5">
                    {c.status === "open" && (
                      <MiniBtn onClick={() => updateStatus(c.id, "under_review")} testId={`dp-review-${c.id}`}>İncele</MiniBtn>
                    )}
                    {(c.status === "open" || c.status === "under_review") && (
                      <>
                        <MiniBtn onClick={() => updateStatus(c.id, "approved")} green testId={`dp-approve-${c.id}`}>Onayla</MiniBtn>
                        <MiniBtn onClick={() => updateStatus(c.id, "denied")} red testId={`dp-deny-${c.id}`}>Reddet</MiniBtn>
                      </>
                    )}
                    {c.status === "approved" && (
                      <MiniBtn onClick={() => updateStatus(c.id, "settled")} violet testId={`dp-settle-${c.id}`}>Öde & Kapat</MiniBtn>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

const Kpi = ({ icon: Icon, label, value, highlight, warn }) => (
  <div className={`p-3 rounded-xl border ${highlight ? "bg-emerald-50 border-emerald-200" : warn ? "bg-amber-50 border-amber-200" : "bg-white border-stone-200"}`}>
    <div className="text-[9px] uppercase font-bold text-stone-400 flex items-center gap-1">
      {Icon && <Icon className="w-3 h-3" />}{label}
    </div>
    <div className={`text-lg font-black ${highlight ? "text-emerald-800" : warn ? "text-amber-800" : "text-stone-900"}`}>{value}</div>
  </div>
);

const MiniBtn = ({ children, onClick, green, red, violet, testId }) => (
  <button onClick={onClick} data-testid={testId}
    className={`px-2.5 py-1 rounded-lg text-[10px] font-bold text-white ${
      green ? "bg-emerald-600 hover:bg-emerald-500" : red ? "bg-rose-600 hover:bg-rose-500"
      : violet ? "bg-violet-600 hover:bg-violet-500" : "bg-stone-600 hover:bg-stone-500"}`}>
    {children}
  </button>
);
