/**
 * ExternalLoyaltyPanel (iter 373) — Link guests to major hotel-chain loyalty
 * programs (Marriott Bonvoy, Hilton Honors, IHG, Accor, Hyatt, Wyndham, BW).
 *
 * Two views:
 *   1) Program directory + Link form
 *   2) Elite Arrivals (next N days) — front-desk action list
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import {
  Trophy, Sparkles, Link2, RefreshCw, X, Users, Crown, Award,
  AlertCircle, ChevronRight, Search,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ExternalLoyaltyPanel({ activePropertyId }) {
  const [tab, setTab] = useState("directory");
  return (
    <div className="p-6 max-w-[1400px] mx-auto" data-testid="external-loyalty-panel">
      <div className="mb-5">
        <div className="text-xs uppercase tracking-widest text-stone-500 mb-1 flex items-center gap-1.5">
          <Crown className="w-3 h-3 text-amber-500" /> Chain Loyalty Integration
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">Harici Loyalty Programları</h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Marriott Bonvoy, Hilton Honors, IHG, Accor ALL, Hyatt, Wyndham, Best Western — misafirlerinizi
          zincir loyalty programlarına bağlayın. Elite tier&apos;lar otomatik oda-atama skorunda öncelik alır.
        </p>
      </div>

      <div className="flex gap-2 mb-5 border-b border-stone-200">
        <TabBtn active={tab === "directory"} onClick={() => setTab("directory")} testId="ext-loy-tab-directory">
          <Users className="w-4 h-4 inline mr-1.5" /> Bağlantılar
        </TabBtn>
        <TabBtn active={tab === "elite"} onClick={() => setTab("elite")} testId="ext-loy-tab-elite">
          <Sparkles className="w-4 h-4 inline mr-1.5" /> Elite Gelişleri
        </TabBtn>
        <TabBtn active={tab === "programs"} onClick={() => setTab("programs")} testId="ext-loy-tab-programs">
          <Trophy className="w-4 h-4 inline mr-1.5" /> Program Rehberi
        </TabBtn>
      </div>

      {tab === "directory" && <LinkDirectory />}
      {tab === "elite" && <EliteArrivalsTab activePropertyId={activePropertyId} />}
      {tab === "programs" && <ProgramsTab />}
    </div>
  );
}

const TabBtn = ({ active, onClick, children, testId }) => (
  <button onClick={onClick} data-testid={testId}
    className={`px-4 py-2.5 text-sm font-semibold transition -mb-px border-b-2 ${
      active ? "border-amber-600 text-amber-700" : "border-transparent text-stone-500 hover:text-stone-700"
    }`}>
    {children}
  </button>
);

/* ═══════════ 1) LINK DIRECTORY ═══════════ */
const LinkDirectory = () => {
  const [guestId, setGuestId] = useState("");
  const [links, setLinks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [programs, setPrograms] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [formProgram, setFormProgram] = useState("");
  const [formMemberId, setFormMemberId] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    axios.get(`${API}/external-loyalty/programs`).then(r => setPrograms(r.data || []));
  }, []);

  const loadLinks = useCallback(async () => {
    const gid = guestId.trim();
    if (!gid) { setLinks([]); return; }
    setLoading(true);
    try {
      const r = await axios.get(`${API}/external-loyalty/guest/${encodeURIComponent(gid)}`);
      setLinks(r.data?.items || []);
    } catch (e) {
      toast.error("Yüklenemedi: " + (e.response?.data?.detail || e.message));
    }
    setLoading(false);
  }, [guestId]);

  const doLink = async () => {
    if (!guestId.trim() || !formProgram || !formMemberId.trim()) {
      toast.warning("Guest ID, program ve üye numarası zorunlu");
      return;
    }
    setSaving(true);
    try {
      const r = await axios.post(`${API}/external-loyalty/link`, {
        guest_id: guestId.trim(),
        program: formProgram,
        member_id: formMemberId.trim(),
        verify_now: true,
      });
      if (r.data?.verified) {
        toast.success(`Bağlandı! Tier: ${r.data.tier}${r.data.is_elite ? " (ELITE)" : ""}`);
      } else {
        toast.warning("Bağlandı ama doğrulanamadı");
      }
      setShowForm(false); setFormMemberId(""); setFormProgram("");
      await loadLinks();
    } catch (e) {
      toast.error("Hata: " + (e.response?.data?.detail || e.message));
    }
    setSaving(false);
  };

  const doSync = async (linkId) => {
    try {
      const r = await axios.post(`${API}/external-loyalty/sync/${linkId}`);
      toast.success(`Senkronize edildi · Tier: ${r.data.tier} · Puan: ${r.data.points?.toLocaleString?.() ?? r.data.points}`);
      await loadLinks();
    } catch (e) {
      toast.error("Sync hatası: " + (e.response?.data?.detail || e.message));
    }
  };

  const doUnlink = async (linkId, label) => {
    if (!window.confirm(`${label} bağlantısını sil?`)) return;
    try {
      await axios.delete(`${API}/external-loyalty/link/${linkId}`);
      toast.success("Bağlantı silindi");
      await loadLinks();
    } catch (e) {
      toast.error("Silme hatası");
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex gap-2 items-center">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
          <input value={guestId} onChange={e => setGuestId(e.target.value)}
            onKeyDown={e => e.key === "Enter" && loadLinks()}
            placeholder="Guest ID veya email"
            className="w-full pl-9 pr-3 py-2 text-sm border border-stone-300 rounded-md focus:ring-2 focus:ring-amber-500 focus:outline-none"
            data-testid="ext-loy-guest-input" />
        </div>
        <button onClick={loadLinks} disabled={loading || !guestId.trim()}
          className="px-4 py-2 text-sm rounded-md bg-stone-800 text-white hover:bg-stone-900 disabled:opacity-50"
          data-testid="ext-loy-search-btn">
          Ara
        </button>
        {guestId.trim() && (
          <button onClick={() => setShowForm(true)}
            className="px-4 py-2 text-sm rounded-md bg-amber-600 text-white hover:bg-amber-700 flex items-center gap-1.5"
            data-testid="ext-loy-add-btn">
            <Link2 className="w-4 h-4" /> Yeni Bağlantı
          </button>
        )}
      </div>

      {!guestId.trim() && (
        <div className="p-10 text-center border border-dashed border-stone-300 rounded-lg bg-stone-50">
          <Users className="w-10 h-10 mx-auto text-stone-400 mb-2" />
          <div className="text-stone-600">Bir misafirin loyalty bağlantılarını görmek için Guest ID veya email girin</div>
        </div>
      )}

      {guestId.trim() && !loading && links.length === 0 && (
        <div className="p-8 text-center border border-dashed rounded-lg bg-amber-50/40" data-testid="ext-loy-empty">
          <AlertCircle className="w-8 h-8 mx-auto text-amber-500 mb-2" />
          <div className="text-stone-700">Bu misafirin harici loyalty bağlantısı yok</div>
          <div className="text-xs text-stone-500 mt-1">&quot;Yeni Bağlantı&quot; ile ekleyebilirsiniz.</div>
        </div>
      )}

      {links.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {links.map(l => (
            <div key={l.id} className="border border-stone-200 rounded-lg p-4 bg-white relative"
              data-testid={`ext-loy-link-${l.id}`}>
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold text-sm"
                  style={{ backgroundColor: l.program_color || "#78716c" }}>
                  {(l.program_label || "?").split(" ").map(w => w[0]).slice(0, 2).join("")}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-stone-900">{l.program_label}</div>
                  <div className="font-mono text-xs text-stone-500 truncate">#{l.member_id}</div>
                </div>
                {l.is_elite && (
                  <Badge className="bg-amber-100 text-amber-800 border-amber-200"><Crown className="w-3 h-3 mr-1" /> ELITE</Badge>
                )}
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                <div>
                  <div className="text-stone-400 uppercase tracking-wider text-[10px]">Tier</div>
                  <div className="font-semibold text-stone-800">{l.tier || "—"}</div>
                </div>
                <div>
                  <div className="text-stone-400 uppercase tracking-wider text-[10px]">Puan</div>
                  <div className="font-semibold text-stone-800">{l.points?.toLocaleString?.() ?? "—"}</div>
                </div>
                <div>
                  <div className="text-stone-400 uppercase tracking-wider text-[10px]">Geceler</div>
                  <div className="font-semibold text-stone-800">{l.nights_ytd ?? "—"}</div>
                </div>
              </div>
              <div className="mt-3 flex gap-2">
                <button onClick={() => doSync(l.id)}
                  className="text-xs px-3 py-1 rounded border border-stone-300 hover:bg-stone-50 flex items-center gap-1"
                  data-testid={`ext-loy-sync-${l.id}`}>
                  <RefreshCw className="w-3 h-3" /> Sync
                </button>
                <button onClick={() => doUnlink(l.id, l.program_label)}
                  className="text-xs px-3 py-1 rounded border border-rose-200 text-rose-700 hover:bg-rose-50 flex items-center gap-1 ml-auto"
                  data-testid={`ext-loy-unlink-${l.id}`}>
                  <X className="w-3 h-3" /> Sil
                </button>
              </div>
              {l.last_sync_at && (
                <div className="text-[10px] text-stone-400 mt-2">
                  Son sync: {new Date(l.last_sync_at).toLocaleString("tr-TR")}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setShowForm(false)}>
          <div className="bg-white rounded-lg p-6 max-w-md w-full" onClick={e => e.stopPropagation()}
            data-testid="ext-loy-form-modal">
            <div className="flex justify-between items-start mb-4">
              <div>
                <div className="font-semibold text-lg text-stone-900">Yeni Loyalty Bağlantısı</div>
                <div className="text-xs text-stone-500 mt-1">Guest ID: <span className="font-mono">{guestId}</span></div>
              </div>
              <button onClick={() => setShowForm(false)}><X className="w-5 h-5 text-stone-400" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-stone-600 uppercase tracking-wider">Program</label>
                <select value={formProgram} onChange={e => setFormProgram(e.target.value)}
                  className="w-full mt-1 px-3 py-2 text-sm border border-stone-300 rounded-md"
                  data-testid="ext-loy-form-program">
                  <option value="">Seç…</option>
                  {programs.map(p => <option key={p.key} value={p.key}>{p.label}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-semibold text-stone-600 uppercase tracking-wider">Üye Numarası</label>
                <input value={formMemberId} onChange={e => setFormMemberId(e.target.value)}
                  placeholder={programs.find(p => p.key === formProgram)?.member_format || "Örn: 123456789012"}
                  className="w-full mt-1 px-3 py-2 text-sm border border-stone-300 rounded-md font-mono"
                  data-testid="ext-loy-form-member-id" />
              </div>
              <button onClick={doLink} disabled={saving}
                className="w-full py-2.5 rounded-md bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50 text-sm font-semibold"
                data-testid="ext-loy-form-submit">
                {saving ? "Doğrulanıyor…" : "Bağla ve Doğrula"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

/* ═══════════ 2) ELITE ARRIVALS ═══════════ */
const EliteArrivalsTab = ({ activePropertyId }) => {
  const [items, setItems] = useState([]);
  const [days, setDays] = useState(7);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ days: String(days) });
      if (activePropertyId) params.set("property_id", activePropertyId);
      const r = await axios.get(`${API}/external-loyalty/elite-arrivals?${params}`);
      setItems(r.data?.items || []);
    } catch (e) {
      toast.error("Yüklenemedi: " + (e.response?.data?.detail || e.message));
    }
    setLoading(false);
  }, [days, activePropertyId]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4" data-testid="ext-loy-elite-tab">
      <div className="flex items-center gap-2">
        <span className="text-xs text-stone-600">Sonraki:</span>
        {[7, 14, 30].map(d => (
          <button key={d} onClick={() => setDays(d)}
            className={`px-3 py-1 text-xs rounded-full border ${
              days === d ? "bg-amber-600 text-white border-amber-600" : "bg-white text-stone-600 border-stone-300"
            }`}
            data-testid={`ext-loy-elite-days-${d}`}>
            {d} gün
          </button>
        ))}
        <button onClick={load} disabled={loading}
          className="ml-auto px-3 py-1 text-xs rounded-md bg-white border border-stone-300 hover:bg-stone-50 flex items-center gap-1.5">
          <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} /> Yenile
        </button>
      </div>

      {!loading && items.length === 0 && (
        <div className="p-10 text-center border border-dashed rounded-lg bg-stone-50" data-testid="ext-loy-elite-empty">
          <Sparkles className="w-10 h-10 mx-auto text-stone-400 mb-2" />
          <div className="text-stone-700 font-semibold">Yaklaşan elite misafir yok</div>
          <div className="text-xs text-stone-500 mt-1">Önümüzdeki {days} gün içinde harici elite loyalty tier&apos;ına sahip misafir bulunamadı.</div>
        </div>
      )}

      {items.length > 0 && (
        <div className="border rounded-lg bg-white overflow-hidden" data-testid="ext-loy-elite-list">
          {items.map((it, i) => (
            <div key={`${it.booking_id}-${it.program}`}
              className={`p-4 flex items-center gap-4 ${i > 0 ? "border-t border-stone-100" : ""}`}>
              <div className="w-11 h-11 rounded-lg flex items-center justify-center text-white font-bold text-sm shrink-0"
                style={{ backgroundColor: it.brand_color || "#78716c" }}>
                {(it.program_label || "?").split(" ").map(w => w[0]).slice(0, 2).join("")}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-stone-900">{it.guest_name || "-"}</span>
                  <Badge className="bg-amber-100 text-amber-800 border-amber-200">
                    <Crown className="w-3 h-3 mr-1" />{it.tier}
                  </Badge>
                </div>
                <div className="text-xs text-stone-500 mt-0.5">
                  {it.program_label} · Check-in <b>{it.check_in}</b> · Oda {it.room_number || "atanmamış"}
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-[10px] text-stone-400 uppercase tracking-wider">Puan</div>
                <div className="font-semibold text-stone-800">{it.points?.toLocaleString?.() ?? "—"}</div>
              </div>
              <ChevronRight className="w-4 h-4 text-stone-300" />
            </div>
          ))}
        </div>
      )}

      <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-900 flex items-start gap-2">
        <Award className="w-4 h-4 mt-0.5 shrink-0" />
        <div>
          <b>Öneri:</b> Elite misafirleri karşılamada VIP amenity (şampanya/meyve tabağı), erken check-in, ücretsiz upgrade veya
          welcome note ile karşılayın. Auto-Assign sistemi de bu tier&apos;a göre otomatik olarak üst kategoriye upgrade sunar.
        </div>
      </div>
    </div>
  );
};

/* ═══════════ 3) PROGRAMS DIRECTORY ═══════════ */
const ProgramsTab = () => {
  const [programs, setPrograms] = useState([]);
  useEffect(() => {
    axios.get(`${API}/external-loyalty/programs`).then(r => setPrograms(r.data || []));
  }, []);
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="ext-loy-programs-grid">
      {programs.map(p => (
        <div key={p.key} className="border border-stone-200 rounded-lg p-4 bg-white">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-12 h-12 rounded-lg flex items-center justify-center text-white font-bold"
              style={{ backgroundColor: p.brand_color }}>
              {p.label.split(" ").map(w => w[0]).slice(0, 2).join("")}
            </div>
            <div>
              <div className="font-semibold text-stone-900">{p.label}</div>
              <div className="text-[10px] text-stone-500 uppercase tracking-wider">
                {p.live ? <span className="text-emerald-600">● LIVE</span> : <span className="text-stone-400">◌ MOCK</span>}
              </div>
            </div>
          </div>
          <div className="text-xs text-stone-600">
            <div className="mb-1"><b>Tier&apos;lar:</b> {p.tiers.join(" → ")}</div>
            <div><b>Elite:</b> <span className="text-amber-700 font-semibold">{p.elite_tiers.join(", ")}</span></div>
            <div className="mt-1 font-mono text-[10px] text-stone-400">Format: {p.member_format}</div>
          </div>
        </div>
      ))}
    </div>
  );
};
