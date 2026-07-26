import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Users, Star, Crown, Tag, ArrowsClockwise, MagnifyingGlass,
  Envelope, Phone, CaretRight, CurrencyGbp, Bed, Eye, Plus, Note, ChatText, X, Copy,
} from "@phosphor-icons/react";
import { CreditCard, Calendar, TrendingUp, Heart, Coffee, Sparkles, Globe, MessageSquare, FileText } from "lucide-react";
import { SmartTipsCard } from "./SmartTipsCard";
import { DuplicateGuestsPanel } from "./DuplicateGuestsPanel";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TIER_CONFIG = {
  standard: { color: "bg-stone-100 text-stone-600 border-stone-200", icon: "🏨", next: "silver", required: 3 },
  silver: { color: "bg-slate-100 text-slate-700 border-slate-300", icon: "🥈", next: "gold", required: 7 },
  gold: { color: "bg-amber-50 text-amber-700 border-amber-300", icon: "🥇", next: "platinum", required: 15 },
  platinum: { color: "bg-purple-50 text-purple-700 border-purple-300", icon: "💎", next: null, required: null },
};

const PREF_OPTIONS = [
  { id: "high_floor", label: "High Floor", icon: "🏢" },
  { id: "quiet_room", label: "Quiet Room", icon: "🤫" },
  { id: "extra_pillows", label: "Extra Pillows", icon: "🛏" },
  { id: "late_checkout", label: "Late Checkout", icon: "🕐" },
  { id: "early_checkin", label: "Early Check-in", icon: "🌅" },
  { id: "vegan", label: "Vegan Diet", icon: "🥗" },
  { id: "halal", label: "Halal Food", icon: "🍖" },
  { id: "no_smoking", label: "Non-Smoking", icon: "🚭" },
  { id: "pet_friendly", label: "Pet-Friendly", icon: "🐕" },
  { id: "accessible", label: "Accessible Room", icon: "♿" },
  { id: "minibar_empty", label: "Empty Minibar", icon: "🧊" },
  { id: "newspaper", label: "Daily Newspaper", icon: "📰" },
];

const SEV_CLS = { high: "bg-rose-50 text-rose-700 border-rose-200", medium: "bg-amber-50 text-amber-700 border-amber-200", low: "bg-stone-50 text-stone-600 border-stone-200" };

function GuestIncidentsCard({ guestEmail, guestName }) {
  const [ctx, setCtx] = useState(null);
  const [form, setForm] = useState({ text: "", severity: "medium", handover: true });
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    if (!guestEmail) return;
    try {
      const r = await axios.get(`${API}/guest-incidents/by-guest/${encodeURIComponent(guestEmail)}`);
      setCtx(r.data);
    } catch { /* silent */ }
  }, [guestEmail]);
  useEffect(() => { load(); }, [load]);

  const add = async () => {
    if (form.text.trim().length < 3) { toast.error("Not en az 3 karakter olmalı"); return; }
    setAdding(true);
    try {
      await axios.post(`${API}/guest-incidents`, { guest_email: guestEmail, guest_name: guestName, ...form, text: form.text.trim() });
      toast.success(form.handover ? "Olay kaydedildi + vardiya devir defterine düştü" : "Olay kaydedildi");
      setForm({ text: "", severity: "medium", handover: true });
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Kaydedilemedi"); }
    setAdding(false);
  };

  const resolve = async (id) => {
    try { await axios.put(`${API}/guest-incidents/${id}/resolve`); toast.success("Olay çözüldü ✓"); load(); }
    catch { toast.error("Güncellenemedi"); }
  };

  if (!ctx) return null;
  return (
    <div className="bg-white rounded-2xl border border-stone-200 p-4 shadow-sm" data-testid="guest-incidents-card">
      <h4 className="text-xs font-bold text-stone-800 flex items-center gap-1.5 mb-3">
        <Note size={13} className="text-orange-500" weight="fill" /> Olay Kayıtları & Vardiya Notları
        {ctx.open_incidents > 0 && <Badge className="text-[9px] bg-rose-100 text-rose-700">{ctx.open_incidents} açık</Badge>}
      </h4>
      <div className="space-y-1.5 mb-3">
        {(ctx.incidents || []).slice(0, 6).map(i => (
          <div key={i.id} className={`rounded-lg border px-3 py-2 ${SEV_CLS[i.severity]}`} data-testid={`incident-${i.id}`}>
            <div className="flex items-center gap-2 text-[11px]">
              <span className="font-bold uppercase text-[9px]">{i.severity}</span>
              {i.handover && <span className="text-[9px] px-1.5 py-0.5 bg-white/70 rounded-full font-semibold">📋 devir</span>}
              <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-bold ${i.status === "open" ? "bg-rose-600 text-white" : "bg-emerald-100 text-emerald-700"}`}>
                {i.status === "open" ? "açık" : "çözüldü"}
              </span>
              <span className="ml-auto text-[9px] opacity-60">{(i.created_at || "").slice(0, 10)}</span>
              {i.status === "open" && (
                <button onClick={() => resolve(i.id)} className="text-[9px] font-bold underline" data-testid={`resolve-incident-${i.id}`}>Çöz ✓</button>
              )}
            </div>
            <p className="text-[11px] mt-1">{i.text}</p>
          </div>
        ))}
        {(ctx.incidents || []).length === 0 && <p className="text-[10px] text-stone-300">Kayıtlı olay yok.</p>}
      </div>
      <div className="border-t border-stone-100 pt-3 space-y-2">
        <Textarea value={form.text} onChange={e => setForm(f => ({ ...f, text: e.target.value }))} rows={2}
          placeholder="Olay / bilgi notu — örn: Klima gürültüsünden şikayet etti, oda değişimi istedi…" data-testid="incident-input" className="text-xs" />
        <div className="flex items-center gap-2 flex-wrap">
          <select value={form.severity} onChange={e => setForm(f => ({ ...f, severity: e.target.value }))}
            className="text-[10px] px-2 py-1.5 border border-stone-200 rounded-lg" data-testid="incident-severity">
            <option value="low">Düşük</option><option value="medium">Orta</option><option value="high">Yüksek</option>
          </select>
          <label className="flex items-center gap-1.5 text-[10px] text-stone-600">
            <input type="checkbox" checked={form.handover} onChange={e => setForm(f => ({ ...f, handover: e.target.checked }))} data-testid="incident-handover" />
            Sonraki vardiyaya devret
          </label>
          <button onClick={add} disabled={adding} data-testid="save-incident-btn"
            className="ml-auto text-[10px] px-3 py-1.5 bg-orange-600 text-white rounded-lg font-bold hover:bg-orange-700 disabled:opacity-50">
            {adding ? "Kaydediliyor…" : "Olay Kaydet"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function GuestProfilesPanel({ properties, activePropertyId }) {
  const [profiles, setProfiles] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedGuest, setSelectedGuest] = useState(null);
  const [guestDetail, setGuestDetail] = useState(null);
  const [sortBy, setSortBy] = useState("last_stay");
  const [showPrefs, setShowPrefs] = useState(false);
  const [showAddNote, setShowAddNote] = useState(false);
  const [showDupes, setShowDupes] = useState(false);
  const [newNote, setNewNote] = useState("");
  const [filterTier, setFilterTier] = useState("all");

  const propertyId = activePropertyId || "all";

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ sort_by: sortBy });
      if (search) params.set("search", search);
      const [profRes, statsRes] = await Promise.all([
        axios.get(`${API}/guests/profiles/${propertyId}?${params}`),
        axios.get(`${API}/guests/profiles/${propertyId}/stats`),
      ]);
      setProfiles(profRes.data);
      setStats(statsRes.data);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, [propertyId, search, sortBy]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const viewGuest = async (guestId) => {
    try {
      const res = await axios.get(`${API}/guests/profiles/detail/${guestId}`);
      setGuestDetail(res.data);
      setSelectedGuest(guestId);
    } catch (err) { console.error(err); }
  };

  const syncProfiles = async () => {
    await axios.post(`${API}/guests/profiles/sync/${propertyId}`);
    toast.success("Profiles synced from bookings");
    fetchData();
  };

  const toggleVip = async (guestId, current) => {
    await axios.put(`${API}/guests/profiles/${guestId}`, { vip: !current });
    fetchData();
    if (guestDetail?.id === guestId) viewGuest(guestId);
  };

  const updatePreferences = async (prefs) => {
    if (!guestDetail) return;
    await axios.put(`${API}/guests/profiles/${guestDetail.id}`, { preferences: prefs });
    toast.success("Preferences updated");
    viewGuest(guestDetail.id);
  };

  const addNote = async () => {
    if (!guestDetail || !newNote) return;
    // Handle both array and string formats for notes
    const existingNotes = Array.isArray(guestDetail.notes) ? guestDetail.notes : [];
    const notes = [...existingNotes, { text: newNote, date: new Date().toISOString(), by: "Staff" }];
    await axios.put(`${API}/guests/profiles/${guestDetail.id}`, { notes });
    toast.success("Note added");
    setNewNote(""); setShowAddNote(false);
    viewGuest(guestDetail.id);
  };

  const addTag = async (tag) => {
    if (!guestDetail) return;
    const tags = [...new Set([...(guestDetail.tags || []), tag])];
    await axios.put(`${API}/guests/profiles/${guestDetail.id}`, { tags });
    viewGuest(guestDetail.id);
  };

  const removeTag = async (tag) => {
    if (!guestDetail) return;
    const tags = (guestDetail.tags || []).filter(t => t !== tag);
    await axios.put(`${API}/guests/profiles/${guestDetail.id}`, { tags });
    viewGuest(guestDetail.id);
  };

  const filteredProfiles = filterTier === "all" ? profiles : profiles.filter(p => p.loyalty_tier === filterTier);
  const g = guestDetail;
  const tier = g ? (TIER_CONFIG[g.loyalty_tier] || TIER_CONFIG.standard) : null;
  const avgSpend = g && g.total_stays > 0 ? Math.round(g.total_spend / g.total_stays) : 0;

  return (
    <div className="h-full flex flex-col" data-testid="guest-profiles-panel">
      {/* Header */}
      <div className="border-b border-stone-200 bg-white px-6 py-4 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-violet-600 flex items-center justify-center"><Users size={18} className="text-white" weight="fill" /></div>
          <div><h2 className="text-lg font-bold text-stone-900" style={{ fontFamily: "Outfit, sans-serif" }}>Guest Profiles</h2><p className="text-[11px] text-stone-500">Unified guest history, preferences & CRM</p></div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowDupes(true)}
            className="text-xs px-3 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-xl font-bold flex items-center gap-1"
            data-testid="open-duplicate-guests"
            title="Aynı misafirin tekrarlı profillerini birleştir"
          >
            <Copy size={12} /> Duplicate Merge
          </button>
          <button onClick={syncProfiles} className="text-xs px-3 py-2 bg-violet-600 text-white rounded-xl font-bold hover:bg-violet-700 flex items-center gap-1" data-testid="sync-profiles-btn">
            <ArrowsClockwise size={12} /> Sync from Bookings
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="bg-white border-b border-stone-200 px-6 py-3 flex items-center gap-3 flex-shrink-0">
        <div className="flex items-center gap-5 flex-1">
          {[
            { label: "Total", value: stats.total || 0, color: "text-stone-800" },
            { label: "VIP", value: stats.vip || 0, color: "text-amber-600" },
            { label: "Gold", value: stats.tiers?.gold || 0, color: "text-amber-700" },
            { label: "Platinum", value: stats.tiers?.platinum || 0, color: "text-purple-600" },
          ].map((s, i) => (
            <div key={i} className="text-center">
              <div className={`text-lg font-black ${s.color}`}>{s.value}</div>
              <div className="text-[9px] text-stone-400 font-semibold">{s.label}</div>
            </div>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <Select value={filterTier} onValueChange={setFilterTier}>
            <SelectTrigger className="h-8 w-28 text-xs"><SelectValue placeholder="All Tiers" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Tiers</SelectItem>
              <SelectItem value="standard">Standard</SelectItem>
              <SelectItem value="silver">Silver</SelectItem>
              <SelectItem value="gold">Gold</SelectItem>
              <SelectItem value="platinum">Platinum</SelectItem>
            </SelectContent>
          </Select>
          <div className="relative">
            <MagnifyingGlass size={13} className="absolute left-2.5 top-2 text-stone-400" />
            <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search..." className="h-8 w-40 text-xs pl-8" data-testid="search-guests" />
          </div>
          <Select value={sortBy} onValueChange={setSortBy}>
            <SelectTrigger className="h-8 w-32 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="last_stay">Last Stay</SelectItem>
              <SelectItem value="total_spend">Top Spenders</SelectItem>
              <SelectItem value="total_stays">Most Stays</SelectItem>
              <SelectItem value="name">Name A-Z</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Guest List */}
        <ScrollArea className="w-[380px] border-r border-stone-200 bg-white flex-shrink-0">
          <div className="p-2 space-y-1" data-testid="guest-list">
            {loading ? (
              <div className="flex justify-center py-16"><ArrowsClockwise size={20} className="animate-spin text-stone-300" /></div>
            ) : filteredProfiles.length === 0 ? (
              <div className="text-center py-12 text-stone-400 text-xs">No guest profiles. Click "Sync from Bookings" to import.</div>
            ) : filteredProfiles.map(guest => (
              <button key={guest.id} onClick={() => viewGuest(guest.id)}
                className={`w-full p-3 rounded-xl flex items-center gap-3 text-left transition-all ${selectedGuest === guest.id ? "bg-violet-50 border border-violet-200" : "hover:bg-stone-50 border border-transparent"}`}
                data-testid={`guest-${guest.id}`}>
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-400 to-purple-600 flex items-center justify-center flex-shrink-0">
                  <span className="text-sm font-bold text-white">{guest.name?.[0]?.toUpperCase() || "?"}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-bold text-stone-800 truncate">{guest.name}</span>
                    {guest.vip && <Crown size={11} className="text-amber-500 flex-shrink-0" weight="fill" />}
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 text-[10px] text-stone-400">
                    <Badge className={`text-[8px] px-1 py-0 ${TIER_CONFIG[guest.loyalty_tier]?.color || "bg-stone-100 text-stone-500"}`}>{guest.loyalty_tier}</Badge>
                    <span>{guest.total_stays || 0} stays</span>
                    {guest.total_spend > 0 && <span className="font-semibold text-stone-600">£{Math.round(guest.total_spend)}</span>}
                  </div>
                </div>
                <CaretRight size={10} className="text-stone-300 flex-shrink-0" />
              </button>
            ))}
          </div>
        </ScrollArea>

        {/* Detail Panel */}
        <div className="flex-1 overflow-y-auto bg-stone-50 p-5">
          {g ? (
            <div className="max-w-2xl mx-auto space-y-4" data-testid="guest-detail">
              {/* Profile Header */}
              <div className="bg-white rounded-2xl border border-stone-200 p-5 shadow-sm">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-400 to-purple-700 flex items-center justify-center shadow-md">
                      <span className="text-2xl font-black text-white">{g.name?.[0]?.toUpperCase()}</span>
                    </div>
                    <div>
                      <div className="text-lg font-bold text-stone-900 flex items-center gap-2">
                        {g.name} {g.vip && <Crown size={16} className="text-amber-500" weight="fill" />}
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge className={`text-[10px] font-bold border ${tier.color}`}>{tier.icon} {g.loyalty_tier?.toUpperCase()}</Badge>
                        {tier.next && <span className="text-[9px] text-stone-400">{tier.required - (g.total_stays || 0)} stays to {tier.next}</span>}
                      </div>
                      <div className="flex items-center gap-3 mt-2 text-xs text-stone-500">
                        {g.email && <span className="flex items-center gap-1"><Envelope size={12} /> {g.email}</span>}
                        {g.phone && <span className="flex items-center gap-1"><Phone size={12} /> {g.phone}</span>}
                        {g.nationality && <span className="flex items-center gap-1"><Globe size={12} /> {g.nationality}</span>}
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-1.5">
                    <button onClick={() => toggleVip(g.id, g.vip)}
                      className={`text-[10px] px-3 py-1.5 rounded-lg font-bold ${g.vip ? "bg-amber-100 text-amber-700" : "bg-stone-100 text-stone-500"}`} data-testid="toggle-vip">
                      <Crown size={11} className="inline mr-0.5" weight="fill" /> {g.vip ? "VIP" : "Set VIP"}
                    </button>
                    <button onClick={() => setShowAddNote(true)} className="text-[10px] px-3 py-1.5 bg-violet-50 text-violet-700 rounded-lg font-bold" data-testid="add-note-btn">
                      <Note size={11} className="inline mr-0.5" /> Add Note
                    </button>
                  </div>
                </div>
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-4 gap-3">
                {[
                  { label: "Total Stays", value: g.total_stays || 0, icon: Bed, color: "text-violet-600", bg: "bg-violet-50" },
                  { label: "Total Spent", value: `£${Math.round(g.total_spend || 0)}`, icon: CreditCard, color: "text-emerald-600", bg: "bg-emerald-50" },
                  { label: "Avg per Stay", value: `£${avgSpend}`, icon: TrendingUp, color: "text-blue-600", bg: "bg-blue-50" },
                  { label: "Last Visit", value: g.last_stay?.slice(0, 10) || "—", icon: Calendar, color: "text-stone-600", bg: "bg-stone-50" },
                ].map((s, i) => (
                  <div key={i} className={`${s.bg} rounded-xl p-3 border border-stone-100`}>
                    <s.icon size={14} className={`${s.color} mb-1.5`} />
                    <div className={`text-sm font-black ${s.color}`}>{s.value}</div>
                    <div className="text-[9px] text-stone-400 font-medium">{s.label}</div>
                  </div>
                ))}
              </div>

              {/* AI Smart Tips (Mews-parity iter 356) */}
              <SmartTipsCard guestId={g.id} />

              {/* Olay kayıtları & vardiya devri (Mews guest notes parity) */}
              <GuestIncidentsCard guestEmail={g.email} guestName={g.name} />

              <div className="grid grid-cols-2 gap-4">
                <div className="bg-white rounded-2xl border border-stone-200 p-4 shadow-sm">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-xs font-bold text-stone-800 flex items-center gap-1.5"><Heart size={13} className="text-pink-500" /> Preferences</h4>
                    <button onClick={() => setShowPrefs(true)} className="text-[9px] text-violet-600 font-bold" data-testid="edit-prefs-btn">Edit</button>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {(() => {
                      const prefs = Array.isArray(g.preferences) ? g.preferences : [];
                      return prefs.length > 0 ? prefs.map(p => {
                        const opt = PREF_OPTIONS.find(o => o.id === p) || { label: p, icon: "✓" };
                        return <Badge key={p} className="text-[9px] bg-pink-50 text-pink-700 border border-pink-200">{opt.icon} {opt.label}</Badge>;
                      }) : <span className="text-[10px] text-stone-300">No preferences set</span>;
                    })()}
                  </div>
                </div>

                {/* Tags */}
                <div className="bg-white rounded-2xl border border-stone-200 p-4 shadow-sm">
                  <h4 className="text-xs font-bold text-stone-800 flex items-center gap-1.5 mb-3"><Tag size={13} className="text-blue-500" weight="fill" /> Tags</h4>
                  <div className="flex flex-wrap gap-1.5">
                    {(g.tags || []).map(t => (
                      <Badge key={t} className="text-[9px] bg-blue-50 text-blue-700 border border-blue-200 flex items-center gap-1">
                        {t} <button onClick={() => removeTag(t)} className="hover:text-red-500"><X size={8} /></button>
                      </Badge>
                    ))}
                    <button onClick={() => { const t = prompt("Add tag:"); if (t) addTag(t); }}
                      className="text-[9px] px-2 py-0.5 border border-dashed border-stone-300 rounded-full text-stone-400 hover:text-stone-600 hover:border-stone-400">
                      <Plus size={8} className="inline" /> Add
                    </button>
                  </div>
                </div>
              </div>

              {/* Booking History */}
              {g.bookings?.length > 0 && (
                <div className="bg-white rounded-2xl border border-stone-200 p-4 shadow-sm">
                  <h4 className="text-xs font-bold text-stone-800 flex items-center gap-1.5 mb-3"><Bed size={13} className="text-indigo-500" weight="fill" /> Stay History ({g.bookings.length})</h4>
                  <div className="space-y-1.5">
                    {g.bookings.slice(0, 10).map((b, i) => (
                      <div key={i} className="flex items-center justify-between text-xs bg-stone-50 rounded-lg px-3 py-2.5 border border-stone-100">
                        <div className="flex items-center gap-2">
                          <span className="text-[9px] font-mono text-stone-400">{b.booking_ref || `#${i + 1}`}</span>
                          <span className="text-stone-700 font-medium">{b.check_in} → {b.check_out}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          {b.room_type && <span className="text-[10px] text-stone-400">{b.room_type}</span>}
                          <span className="font-bold text-emerald-600">£{b.total_price || 0}</span>
                          <Badge className={`text-[8px] ${b.payment_status === "paid" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>{b.payment_status || "pending"}</Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Staff Notes */}
              <div className="bg-white rounded-2xl border border-stone-200 p-4 shadow-sm">
                <h4 className="text-xs font-bold text-stone-800 flex items-center gap-1.5 mb-3"><FileText size={13} className="text-amber-500" /> Staff Notes</h4>
                {(() => {
                  const notes = Array.isArray(g.notes) ? g.notes : (typeof g.notes === 'string' && g.notes ? [{ text: g.notes, date: '', by: 'Staff' }] : []);
                  return notes.length > 0 ? (
                    <div className="space-y-2">
                      {notes.map((n, i) => (
                        <div key={i} className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                          <div className="text-xs text-stone-700">{n.text}</div>
                          <div className="text-[9px] text-stone-400 mt-1">{n.by} · {n.date?.slice(0, 10)}</div>
                        </div>
                      ))}
                    </div>
                  ) : <span className="text-[10px] text-stone-300">No notes yet</span>;
                })()}
              </div>

              {/* Communication */}
              {g.messages?.length > 0 && (
                <div className="bg-white rounded-2xl border border-stone-200 p-4 shadow-sm">
                  <h4 className="text-xs font-bold text-stone-800 flex items-center gap-1.5 mb-3"><MessageSquare size={13} className="text-sky-500" /> Communications ({g.messages.length})</h4>
                  <div className="space-y-1.5 max-h-40 overflow-y-auto">
                    {g.messages.slice(0, 10).map((m, i) => (
                      <div key={i} className="text-[10px] bg-sky-50 border border-sky-100 rounded-lg px-3 py-2 flex items-start gap-2">
                        <Badge className="text-[8px] bg-sky-100 text-sky-700 flex-shrink-0">{m.channel}</Badge>
                        <span className="text-stone-600 flex-1">{m.content?.slice(0, 100)}</span>
                        <span className="text-stone-400 text-[9px] flex-shrink-0">{m.created_at?.slice(0, 10)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-full">
              <div className="text-center"><Eye size={40} className="text-stone-200 mx-auto mb-3" /><p className="text-sm text-stone-400">Select a guest to view their profile</p></div>
            </div>
          )}
        </div>
      </div>

      {/* Preferences Dialog */}
      <Dialog open={showPrefs} onOpenChange={setShowPrefs}>
        <DialogContent className="max-w-md" data-testid="prefs-dialog">
          <DialogHeader><DialogTitle>Guest Preferences</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-2">
            {PREF_OPTIONS.map(opt => {
              // Handle both array and object formats for preferences
              const prefs = Array.isArray(g?.preferences) ? g.preferences : [];
              const active = prefs.includes(opt.id);
              return (
                <button key={opt.id} onClick={() => {
                  const newPrefs = active ? prefs.filter(p => p !== opt.id) : [...prefs, opt.id];
                  updatePreferences(newPrefs);
                }}
                  className={`flex items-center gap-2 p-2.5 rounded-xl text-xs font-medium border-2 transition-all ${active ? "bg-pink-50 border-pink-300 text-pink-700" : "bg-white border-stone-200 text-stone-500 hover:border-stone-300"}`}>
                  <span>{opt.icon}</span> {opt.label}
                </button>
              );
            })}
          </div>
        </DialogContent>
      </Dialog>

      {/* Add Note Dialog */}
      <Dialog open={showAddNote} onOpenChange={setShowAddNote}>
        <DialogContent className="max-w-sm" data-testid="add-note-dialog">
          <DialogHeader><DialogTitle>Add Staff Note</DialogTitle></DialogHeader>
          <Textarea value={newNote} onChange={e => setNewNote(e.target.value)} placeholder="Note about this guest..." rows={3} data-testid="note-input" />
          <button onClick={addNote} className="w-full bg-violet-600 text-white py-2.5 rounded-xl text-sm font-bold" data-testid="save-note-btn">Save Note</button>
        </DialogContent>
      </Dialog>

      {/* Duplicate Guests Auto-Merge Dialog */}
      <Dialog open={showDupes} onOpenChange={setShowDupes}>
        <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto" data-testid="duplicate-guests-dialog">
          <DialogHeader><DialogTitle>Duplicate Guest Auto-Merge</DialogTitle></DialogHeader>
          <DuplicateGuestsPanel />
        </DialogContent>
      </Dialog>
    </div>
  );
}
