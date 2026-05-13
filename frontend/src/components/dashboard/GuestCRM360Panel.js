import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Users, Heart, Crown, ClockCounterClockwise, EnvelopeSimple } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SEG_META = {
  vip: { color: "bg-purple-100 text-purple-800", icon: Crown, label: "VIP" },
  champion: { color: "bg-amber-100 text-amber-800", icon: Crown, label: "Champion (5+ stays)" },
  advocate: { color: "bg-emerald-100 text-emerald-800", icon: Heart, label: "Advocate (5★)" },
  repeat: { color: "bg-blue-100 text-blue-800", icon: Users, label: "Repeat (2+ stays)" },
  "first-time": { color: "bg-stone-100 text-stone-700", icon: Users, label: "First-time" },
  lapsed: { color: "bg-rose-100 text-rose-700", icon: ClockCounterClockwise, label: "Lapsed (365+ days)" },
  dormant: { color: "bg-orange-100 text-orange-700", icon: ClockCounterClockwise, label: "Dormant (180+ days)" },
  "at-risk": { color: "bg-rose-200 text-rose-900", icon: ClockCounterClockwise, label: "At-Risk (low rating)" },
};

export default function GuestCRM360Panel({ user }) {
  const [segments, setSegments] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeSeg, setActiveSeg] = useState("vip");
  const [winbackCandidates, setWinbackCandidates] = useState([]);
  const [winbackDays, setWinbackDays] = useState(90);
  const [winbackBusy, setWinbackBusy] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/crm/segments`, { withCredentials: true });
      setSegments(r.data);
    } catch (e) { toast.error("Segments yüklenemedi"); }
    finally { setLoading(false); }
  }, []);

  const loadWinback = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/crm/winback/candidates?days_inactive=${winbackDays}`, { withCredentials: true });
      setWinbackCandidates(r.data.candidates || []);
    } catch (e) { toast.error("Win-back listesi alınamadı"); }
  }, [winbackDays]);

  useEffect(() => { reload(); }, [reload]);
  useEffect(() => { loadWinback(); }, [loadWinback]);

  async function queueWinback() {
    if (winbackCandidates.length === 0) return;
    if (!confirm(`${winbackCandidates.length} misafire win-back e-postası kuyrukla?`)) return;
    setWinbackBusy(true);
    try {
      const r = await axios.post(`${API}/crm/winback/queue`, {
        guest_emails: winbackCandidates.map(c => c.guest_email),
        template: "Sizi özledik! Bir sonraki konaklamanız için %10 indirim.",
      }, { withCredentials: true });
      toast.success(`${r.data.queued_count} mail kuyrukta — Resend key gelince gönderilecek`);
    } catch { toast.error("Kuyruklanamadı"); }
    finally { setWinbackBusy(false); }
  }

  const segList = segments?.segments || {};
  const activeMembers = segList[activeSeg]?.members || [];

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="crm-360-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Users size={12} weight="fill" className="text-violet-500" />
          <span>Guest CRM 360</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">Misafir Profilleri & Segmentler</h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Booking + folio + review verisinden otomatik segmentasyon — VIP, Champion, Lapsed... Revinate'in 1/5'i fiyatla.
        </p>
      </div>

      {loading || !segments ? (
        <div className="py-12 text-center text-stone-400">Hesaplanıyor…</div>
      ) : (
        <>
          {/* Segment cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2 mb-6">
            {Object.entries(SEG_META).map(([k, m]) => {
              const count = segList[k]?.count || 0;
              const Icon = m.icon;
              return (
                <button
                  key={k}
                  onClick={() => setActiveSeg(k)}
                  data-testid={`crm-seg-${k}`}
                  className={`p-3 rounded-xl text-left border transition ${
                    activeSeg === k
                      ? "border-stone-900 bg-stone-50"
                      : "border-stone-200 bg-white hover:border-stone-300"
                  }`}
                >
                  <Icon size={14} className="text-stone-500 mb-1" />
                  <div className="text-2xl font-semibold text-stone-900">{count}</div>
                  <div className="text-[10px] uppercase tracking-wider text-stone-500 leading-tight mt-0.5">{m.label}</div>
                </button>
              );
            })}
          </div>

          {/* Active segment members */}
          <div className="bg-white border border-stone-200 rounded-xl mb-6">
            <div className="px-4 py-3 border-b border-stone-200 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-stone-900">{SEG_META[activeSeg]?.label}</h2>
              <span className="text-xs text-stone-400">{activeMembers.length} kayıt gösteriliyor</span>
            </div>
            <div className="divide-y divide-stone-100">
              {activeMembers.length === 0 ? (
                <div className="p-8 text-center text-stone-400 text-sm">Bu segmentte misafir yok.</div>
              ) : (
                activeMembers.map(m => (
                  <div key={m.guest_email} className="px-4 py-2.5 flex items-center gap-3" data-testid={`crm-member-${m.guest_email}`}>
                    <div className="w-8 h-8 rounded-full bg-violet-100 text-violet-700 text-[10px] font-semibold inline-flex items-center justify-center shrink-0">
                      {(m.guest_name || "?").slice(0, 2).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-semibold text-stone-900 truncate">{m.guest_name}</div>
                      <div className="text-[11px] text-stone-500 truncate">{m.guest_email}</div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-sm font-semibold text-stone-800">£{m.lifetime_value.toFixed(2)}</div>
                      <div className="text-[10px] text-stone-400">{m.total_stays || 0} konaklama · son: {m.last_stay || "—"}</div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Win-back panel */}
          <div className="bg-white border border-stone-200 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h2 className="text-sm font-semibold text-stone-900 inline-flex items-center gap-1.5">
                  <EnvelopeSimple size={14} /> Win-Back Kampanya
                </h2>
                <p className="text-xs text-stone-500 mt-0.5">
                  N gündür konaklamamış misafirler — toplu e-posta kuyruğu oluştur.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <select value={winbackDays} onChange={e => setWinbackDays(Number(e.target.value))}
                  className="px-2 py-1 text-xs border border-stone-300 rounded" data-testid="winback-days">
                  <option value={60}>60+ gün</option>
                  <option value={90}>90+ gün</option>
                  <option value={180}>180+ gün</option>
                  <option value={365}>365+ gün</option>
                </select>
                <button onClick={queueWinback} disabled={winbackBusy || !winbackCandidates.length}
                  className="px-3 py-1.5 text-xs font-medium text-white bg-stone-900 rounded hover:bg-stone-800 disabled:opacity-50"
                  data-testid="winback-queue-btn">
                  Tümünü kuyrukla ({winbackCandidates.length})
                </button>
              </div>
            </div>
            <div className="max-h-64 overflow-y-auto">
              {winbackCandidates.slice(0, 30).map(c => (
                <div key={c.guest_email} className="py-1.5 px-2 text-xs flex items-center gap-3 border-b border-stone-100">
                  <span className="flex-1 truncate text-stone-800">{c.guest_name}</span>
                  <span className="text-stone-400 font-mono">{c.days_inactive}d</span>
                  <span className="text-stone-600 font-mono">£{c.lifetime_value.toFixed(0)}</span>
                  <span className="text-[10px] px-1.5 py-0.5 bg-stone-100 text-stone-500 rounded">{c.lifecycle}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
