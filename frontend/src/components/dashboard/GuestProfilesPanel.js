import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  Users, Star, Crown, Tag, ArrowsClockwise, MagnifyingGlass,
  Envelope, Phone, CaretRight, CalendarBlank, CurrencyGbp,
  ChatText, Bed, Eye, X, Plus,
} from "@phosphor-icons/react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TIER_COLORS = {
  standard: "bg-stone-100 text-stone-600",
  silver: "bg-slate-100 text-slate-600",
  gold: "bg-amber-100 text-amber-700",
  platinum: "bg-purple-100 text-purple-700",
};

export function GuestProfilesPanel({ properties, activePropertyId }) {
  const [profiles, setProfiles] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedGuest, setSelectedGuest] = useState(null);
  const [guestDetail, setGuestDetail] = useState(null);
  const [sortBy, setSortBy] = useState("last_stay");

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
    fetchData();
  };

  const toggleVip = async (guestId, current) => {
    await axios.put(`${API}/guests/profiles/${guestId}`, { vip: !current });
    fetchData();
    if (guestDetail?.id === guestId) viewGuest(guestId);
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5" data-testid="guest-profiles-panel">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2" data-testid="profiles-title">
            <Users size={22} className="text-violet-500" weight="fill" />
            Guest Profiles
          </h1>
          <p className="text-sm text-stone-500 mt-0.5">Unified guest history & CRM</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={syncProfiles} className="text-xs px-3 py-1.5 bg-violet-50 text-violet-700 rounded-lg hover:bg-violet-100 font-medium" data-testid="sync-profiles-btn">
            <ArrowsClockwise size={12} className="inline mr-1" /> Sync from Bookings
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-xl font-bold text-stone-800">{stats.total || 0}</div>
          <div className="text-[10px] text-stone-500 uppercase">Total Guests</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-xl font-bold text-amber-600">{stats.vip || 0}</div>
          <div className="text-[10px] text-stone-500 uppercase">VIP Guests</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-xl font-bold text-stone-800">{stats.tiers?.gold || 0}</div>
          <div className="text-[10px] text-stone-500 uppercase">Gold Tier</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-xl font-bold text-purple-600">{stats.tiers?.platinum || 0}</div>
          <div className="text-[10px] text-stone-500 uppercase">Platinum</div>
        </div>
      </div>

      {/* Search & Sort */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <MagnifyingGlass size={14} className="absolute left-3 top-2.5 text-stone-400" />
          <Input placeholder="Search guests..." value={search} onChange={e => setSearch(e.target.value)}
            className="pl-9 h-9 text-sm" data-testid="search-guests" />
        </div>
        <Select value={sortBy} onValueChange={setSortBy}>
          <SelectTrigger className="w-40 h-9 text-xs" data-testid="sort-guests">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="last_stay">Last Stay</SelectItem>
            <SelectItem value="total_spend">Total Spend</SelectItem>
            <SelectItem value="total_stays">Total Stays</SelectItem>
            <SelectItem value="name">Name</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Guest List */}
        <div className="lg:col-span-2 space-y-1.5" data-testid="guest-list">
          {loading ? (
            <div className="flex justify-center py-16"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div>
          ) : profiles.length === 0 ? (
            <div className="text-center py-12 text-stone-400 text-sm">No guest profiles. Click "Sync from Bookings" to import.</div>
          ) : profiles.map(g => (
            <button key={g.id} onClick={() => viewGuest(g.id)}
              className={`w-full bg-white border rounded-xl p-3 flex items-center gap-3 text-left transition-all hover:border-stone-300 ${selectedGuest === g.id ? "border-violet-300 ring-1 ring-violet-200" : "border-stone-200"}`}
              data-testid={`guest-${g.id}`}>
              <div className="w-9 h-9 rounded-full bg-violet-50 flex items-center justify-center flex-shrink-0">
                <span className="text-sm font-bold text-violet-600">{g.name?.[0] || "?"}</span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-semibold text-stone-800 truncate">{g.name}</span>
                  {g.vip && <Crown size={12} className="text-amber-500" weight="fill" />}
                  <Badge className={`text-[9px] px-1.5 py-0 ${TIER_COLORS[g.loyalty_tier] || TIER_COLORS.standard}`}>{g.loyalty_tier}</Badge>
                </div>
                <div className="flex items-center gap-2 mt-0.5 text-[10px] text-stone-400">
                  {g.email && <span className="flex items-center gap-0.5"><Envelope size={10} /> {g.email}</span>}
                  {g.total_stays > 0 && <span>{g.total_stays} stays</span>}
                  {g.total_spend > 0 && <span>£{Math.round(g.total_spend)}</span>}
                </div>
              </div>
              <CaretRight size={12} className="text-stone-300" />
            </button>
          ))}
        </div>

        {/* Detail Panel */}
        <div>
          {guestDetail ? (
            <div className="bg-white border border-stone-200 rounded-xl p-4 space-y-4 sticky top-6" data-testid="guest-detail">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-10 h-10 rounded-full bg-violet-100 flex items-center justify-center">
                    <span className="text-lg font-bold text-violet-600">{guestDetail.name?.[0]}</span>
                  </div>
                  <div>
                    <div className="text-sm font-bold text-stone-800">{guestDetail.name}</div>
                    <Badge className={`text-[9px] ${TIER_COLORS[guestDetail.loyalty_tier] || TIER_COLORS.standard}`}>{guestDetail.loyalty_tier}</Badge>
                  </div>
                </div>
                <button onClick={() => toggleVip(guestDetail.id, guestDetail.vip)}
                  className={`text-[10px] px-2 py-1 rounded-lg font-medium ${guestDetail.vip ? "bg-amber-100 text-amber-700" : "bg-stone-100 text-stone-500"}`}>
                  <Crown size={11} className="inline mr-0.5" weight="fill" /> {guestDetail.vip ? "VIP" : "Set VIP"}
                </button>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="bg-stone-50 rounded-lg p-2"><div className="font-bold text-stone-800">{guestDetail.total_stays}</div><div className="text-[10px] text-stone-400">Stays</div></div>
                <div className="bg-stone-50 rounded-lg p-2"><div className="font-bold text-stone-800">£{Math.round(guestDetail.total_spend || 0)}</div><div className="text-[10px] text-stone-400">Total Spend</div></div>
                <div className="bg-stone-50 rounded-lg p-2"><div className="font-bold text-stone-800">{guestDetail.first_stay || "—"}</div><div className="text-[10px] text-stone-400">First Stay</div></div>
                <div className="bg-stone-50 rounded-lg p-2"><div className="font-bold text-stone-800">{guestDetail.last_stay || "—"}</div><div className="text-[10px] text-stone-400">Last Stay</div></div>
              </div>

              {guestDetail.email && <div className="text-xs text-stone-500 flex items-center gap-1"><Envelope size={12} /> {guestDetail.email}</div>}
              {guestDetail.phone && <div className="text-xs text-stone-500 flex items-center gap-1"><Phone size={12} /> {guestDetail.phone}</div>}

              {/* Booking History */}
              {guestDetail.bookings?.length > 0 && (
                <div>
                  <div className="text-[11px] font-semibold text-stone-600 mb-1.5 flex items-center gap-1"><Bed size={12} /> Booking History</div>
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {guestDetail.bookings.slice(0, 5).map((b, i) => (
                      <div key={i} className="text-[10px] bg-stone-50 rounded p-1.5 flex justify-between">
                        <span>{b.check_in} — {b.check_out}</span>
                        <span className="text-emerald-600 font-medium">£{b.total_price}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Tags */}
              <div>
                <div className="text-[11px] font-semibold text-stone-600 mb-1.5 flex items-center gap-1"><Tag size={12} /> Tags</div>
                <div className="flex flex-wrap gap-1">
                  {(guestDetail.tags || []).map(t => (
                    <Badge key={t} variant="outline" className="text-[10px]">{t}</Badge>
                  ))}
                  {(!guestDetail.tags || guestDetail.tags.length === 0) && <span className="text-[10px] text-stone-300">No tags</span>}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white border border-stone-200 rounded-xl p-8 text-center">
              <Eye size={28} className="text-stone-300 mx-auto mb-2" />
              <p className="text-sm text-stone-500">Select a guest to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
