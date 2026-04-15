import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  Crown, Star, Gift, ArrowsClockwise, Plus, Trophy, CurrencyGbp,
} from "@phosphor-icons/react";
import { Award, TrendingUp, Users, Heart, Coffee, Sparkles, ShoppingBag } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TIER_CONFIG = {
  standard: { color: "bg-stone-100 text-stone-700 border-stone-300", gradient: "from-stone-400 to-stone-500", icon: "🏨" },
  silver: { color: "bg-slate-100 text-slate-700 border-slate-400", gradient: "from-slate-400 to-slate-600", icon: "🥈" },
  gold: { color: "bg-amber-50 text-amber-700 border-amber-400", gradient: "from-amber-400 to-amber-600", icon: "🥇" },
  platinum: { color: "bg-purple-50 text-purple-700 border-purple-400", gradient: "from-purple-500 to-indigo-600", icon: "💎" },
};

const REWARD_ICONS = { stay: "🏨", upgrade: "⬆️", spa: "🧖", dining: "🍽️", service: "🔑", amenity: "🍾" };

export function LoyaltyPanel({ properties, activePropertyId }) {
  const [tab, setTab] = useState("leaderboard");
  const [leaderboard, setLeaderboard] = useState({ members: [], tier_counts: {} });
  const [rewards, setRewards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedMember, setSelectedMember] = useState(null);
  const [showEarnPoints, setShowEarnPoints] = useState(false);
  const [earnData, setEarnData] = useState({ guest_id: "", amount: 0, reason: "stay" });

  const propertyId = (activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "aldgate-flats");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [lb, rw] = await Promise.all([
        axios.get(`${API}/loyalty/leaderboard/${propertyId}`),
        axios.get(`${API}/loyalty/rewards`),
      ]);
      setLeaderboard(lb.data);
      setRewards(rw.data);
    } catch (e) {}
    finally { setLoading(false); }
  }, [propertyId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const viewMember = async (guestId) => {
    try { const { data } = await axios.get(`${API}/loyalty/member/${guestId}`); setSelectedMember(data); }
    catch (e) { toast.error("Failed to load"); }
  };

  const earnPoints = async () => {
    try {
      const { data } = await axios.post(`${API}/loyalty/earn-points`, earnData);
      toast.success(`${data.points_earned} points awarded!${data.tier_upgraded ? " Tier upgraded!" : ""}`);
      setShowEarnPoints(false);
      fetchData();
      if (selectedMember) viewMember(selectedMember.guest_id);
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const redeemReward = async (guestId, rewardId) => {
    try {
      const { data } = await axios.post(`${API}/loyalty/redeem`, { guest_id: guestId, reward_id: rewardId });
      toast.success(`Redeemed: ${data.reward}! New balance: ${data.new_balance} pts`);
      viewMember(guestId);
    } catch (e) { toast.error(e.response?.data?.detail || "Not enough points"); }
  };

  const tabs = [
    { id: "leaderboard", label: "Members", icon: Users },
    { id: "rewards", label: "Rewards", icon: Gift },
  ];

  if (loading) return <div className="flex items-center justify-center h-96"><ArrowsClockwise size={24} className="animate-spin text-amber-300" /></div>;

  return (
    <div className="h-full flex flex-col" data-testid="loyalty-panel">
      <div className="border-b border-stone-200 bg-white px-6 py-4 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center"><Crown size={18} className="text-white" weight="fill" /></div>
          <div><h2 className="text-lg font-bold text-stone-900" style={{ fontFamily: "Outfit, sans-serif" }}>Loyalty Program</h2><p className="text-[11px] text-stone-500">Points, tiers, rewards & guest recognition</p></div>
        </div>
        <button onClick={() => setShowEarnPoints(true)} className="text-xs px-4 py-2 bg-amber-500 text-white rounded-xl font-bold hover:bg-amber-600 flex items-center gap-1" data-testid="earn-points-btn"><Plus size={12} /> Award Points</button>
      </div>

      {/* Tier Summary */}
      <div className="bg-white border-b border-stone-200 px-6 py-3 flex gap-4 flex-shrink-0">
        {Object.entries(leaderboard.tier_counts || {}).map(([tier, count]) => {
          const cfg = TIER_CONFIG[tier] || TIER_CONFIG.standard;
          return (
            <div key={tier} className={`flex items-center gap-2 px-3 py-1.5 rounded-full border ${cfg.color}`}>
              <span>{cfg.icon}</span><span className="text-xs font-bold">{count}</span><span className="text-[10px]">{tier}</span>
            </div>
          );
        })}
        <div className="flex-1" />
        <span className="text-xs text-stone-500">{leaderboard.total_members} total members</span>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-stone-200 px-6 flex gap-1 flex-shrink-0">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold border-b-[3px] transition-all ${tab === t.id ? "border-amber-500 text-amber-600" : "border-transparent text-stone-400"}`} data-testid={`loyalty-tab-${t.id}`}>
            <t.icon size={14} /> {t.label}
          </button>
        ))}
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Members List */}
        {tab === "leaderboard" && (
          <>
            <div className="w-[380px] border-r border-stone-200 bg-white overflow-y-auto flex-shrink-0 p-2 space-y-1" data-testid="members-list">
              {leaderboard.members?.map((m, i) => {
                const cfg = TIER_CONFIG[m.tier] || TIER_CONFIG.standard;
                return (
                  <button key={m.id} onClick={() => viewMember(m.guest_id)}
                    className={`w-full p-3 rounded-xl flex items-center gap-3 text-left transition-all ${selectedMember?.guest_id === m.guest_id ? "bg-amber-50 border border-amber-200" : "hover:bg-stone-50 border border-transparent"}`}
                    data-testid={`member-${m.guest_id}`}>
                    <div className="flex items-center justify-center w-8 text-sm font-black text-stone-300">{i < 3 ? ["🥇","🥈","🥉"][i] : `#${i+1}`}</div>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-bold text-stone-800 truncate">{m.guest_name}</div>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <Badge className={`text-[8px] px-1 py-0 border ${cfg.color}`}>{cfg.icon} {m.tier}</Badge>
                        <span className="text-[10px] text-stone-400">{m.lifetime_points?.toLocaleString()} pts</span>
                      </div>
                    </div>
                    <span className="text-xs font-bold text-amber-600">£{Math.round(m.total_spend || 0)}</span>
                  </button>
                );
              })}
              {leaderboard.members?.length === 0 && <div className="text-center py-12 text-stone-400 text-xs">No members yet. Sync guest profiles first.</div>}
            </div>

            {/* Member Detail */}
            <div className="flex-1 overflow-y-auto bg-stone-50 p-5">
              {selectedMember ? (
                <div className="max-w-xl mx-auto space-y-4" data-testid="member-detail">
                  {/* Profile Card */}
                  <div className={`rounded-2xl p-6 bg-gradient-to-br ${TIER_CONFIG[selectedMember.tier]?.gradient || "from-stone-400 to-stone-500"} text-white shadow-lg`}>
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-[10px] uppercase tracking-widest opacity-70">Loyalty Member</div>
                        <div className="text-xl font-black mt-1">{selectedMember.guest_name}</div>
                        <div className="text-sm opacity-80 mt-0.5">{selectedMember.guest_email}</div>
                      </div>
                      <div className="text-4xl">{TIER_CONFIG[selectedMember.tier]?.icon}</div>
                    </div>
                    <div className="grid grid-cols-3 gap-3 mt-5">
                      <div className="bg-white/20 rounded-xl p-3 text-center backdrop-blur-sm"><div className="text-xl font-black">{selectedMember.points?.toLocaleString()}</div><div className="text-[9px] opacity-70">Points</div></div>
                      <div className="bg-white/20 rounded-xl p-3 text-center backdrop-blur-sm"><div className="text-xl font-black">{selectedMember.total_stays}</div><div className="text-[9px] opacity-70">Stays</div></div>
                      <div className="bg-white/20 rounded-xl p-3 text-center backdrop-blur-sm"><div className="text-xl font-black">£{Math.round(selectedMember.total_spend)}</div><div className="text-[9px] opacity-70">Spent</div></div>
                    </div>
                    {selectedMember.stays_to_next_tier > 0 && selectedMember.next_tier && (
                      <div className="mt-4 bg-white/10 rounded-lg p-2 text-center text-[10px]">
                        {selectedMember.stays_to_next_tier} more stays to {selectedMember.next_tier} tier
                      </div>
                    )}
                  </div>

                  {/* Benefits */}
                  <div className="bg-white rounded-xl border border-stone-200 p-4">
                    <h4 className="text-xs font-bold text-stone-800 mb-2 flex items-center gap-1.5"><Sparkles size={13} className="text-amber-500" /> Tier Benefits</h4>
                    <div className="space-y-1">
                      {(selectedMember.tier_benefits || []).map((b, i) => (
                        <div key={i} className="text-xs text-stone-600 flex items-center gap-2"><Star size={10} className="text-amber-400 flex-shrink-0" weight="fill" /> {b}</div>
                      ))}
                    </div>
                  </div>

                  {/* Redeem Rewards */}
                  <div className="bg-white rounded-xl border border-stone-200 p-4">
                    <h4 className="text-xs font-bold text-stone-800 mb-3 flex items-center gap-1.5"><Gift size={13} className="text-purple-500" weight="fill" /> Redeem Rewards</h4>
                    <div className="grid grid-cols-2 gap-2">
                      {rewards.filter(r => r.points_cost <= (selectedMember.points || 0)).map(r => (
                        <button key={r.id} onClick={() => redeemReward(selectedMember.guest_id, r.id)}
                          className="text-left p-2.5 rounded-xl border border-stone-200 hover:border-amber-300 hover:bg-amber-50 transition-all" data-testid={`redeem-${r.id}`}>
                          <div className="text-sm">{REWARD_ICONS[r.category] || "🎁"}</div>
                          <div className="text-[10px] font-bold text-stone-800 mt-1">{r.name}</div>
                          <div className="text-[9px] text-amber-600 font-bold">{r.points_cost} pts</div>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Points History */}
                  {selectedMember.points_history?.length > 0 && (
                    <div className="bg-white rounded-xl border border-stone-200 p-4">
                      <h4 className="text-xs font-bold text-stone-800 mb-2">Points History</h4>
                      {selectedMember.points_history.slice(-5).reverse().map((h, i) => (
                        <div key={i} className="flex items-center justify-between text-xs py-1.5 border-b border-stone-50 last:border-0">
                          <span className="text-stone-600">{h.reason} · £{h.amount} · {h.multiplier}x</span>
                          <span className="font-bold text-emerald-600">+{h.points} pts</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex items-center justify-center h-full text-center">
                  <div><Crown size={40} className="text-stone-200 mx-auto mb-3" /><p className="text-sm text-stone-400">Select a member to view details</p></div>
                </div>
              )}
            </div>
          </>
        )}

        {/* Rewards Catalog */}
        {tab === "rewards" && (
          <div className="flex-1 overflow-y-auto bg-stone-50 p-6" data-testid="rewards-catalog">
            <div className="max-w-3xl mx-auto grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {rewards.map(r => (
                <motion.div key={r.id} whileHover={{ scale: 1.03 }}
                  className="bg-white rounded-2xl border border-stone-200 p-4 text-center shadow-sm" data-testid={`reward-card-${r.id}`}>
                  <div className="text-3xl mb-2">{REWARD_ICONS[r.category] || "🎁"}</div>
                  <div className="text-sm font-bold text-stone-900">{r.name}</div>
                  <div className="text-[10px] text-stone-500 mt-1">{r.description}</div>
                  <div className="mt-3 bg-amber-50 text-amber-700 rounded-full py-1 text-xs font-black">{r.points_cost?.toLocaleString()} pts</div>
                </motion.div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Earn Points Dialog */}
      <Dialog open={showEarnPoints} onOpenChange={setShowEarnPoints}>
        <DialogContent className="max-w-sm" data-testid="earn-points-dialog">
          <DialogHeader><DialogTitle>Award Points</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-[11px] font-bold text-stone-600 mb-1 block">Guest</label>
              <Select value={earnData.guest_id} onValueChange={v => setEarnData(p => ({...p, guest_id: v}))}>
                <SelectTrigger className="h-9 text-xs"><SelectValue placeholder="Select guest" /></SelectTrigger>
                <SelectContent>
                  {leaderboard.members?.map(m => <SelectItem key={m.guest_id} value={m.guest_id}>{m.guest_name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div><label className="text-[11px] font-bold text-stone-600 mb-1 block">Amount (£)</label>
              <Input type="number" value={earnData.amount} onChange={e => setEarnData(p => ({...p, amount: parseFloat(e.target.value) || 0}))} placeholder="e.g. 250" data-testid="earn-amount" /></div>
            <Select value={earnData.reason} onValueChange={v => setEarnData(p => ({...p, reason: v}))}>
              <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="stay">Room Stay</SelectItem>
                <SelectItem value="dining">Restaurant/Bar</SelectItem>
                <SelectItem value="spa">Spa</SelectItem>
                <SelectItem value="bonus">Bonus Points</SelectItem>
              </SelectContent>
            </Select>
            <button onClick={earnPoints} className="w-full bg-amber-500 text-white py-2.5 rounded-xl text-sm font-bold" data-testid="confirm-earn-btn">Award Points</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
