import { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import { QRCodeSVG } from "qrcode.react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import {
  Search, RefreshCw, X, QrCode, Key, CheckCircle2, Circle, Send,
  UserCheck, CreditCard, ShieldCheck, Sparkles, Calendar, Clock,
  Copy, Mail, MessageSquare, BedDouble, AlertTriangle, Ban, Monitor, Lightbulb,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const WINDOWS = [
  { id: "today", label: "Today" },
  { id: "7d",    label: "Next 7 days" },
  { id: "30d",   label: "Next 30 days" },
  { id: "all",   label: "All upcoming" },
];

const STEPS = [
  { key: "link_sent",   short: "Link",  icon: Send,         label: "Link Sent" },
  { key: "registered",  short: "Reg",   icon: UserCheck,    label: "Registered" },
  { key: "id_verified", short: "ID",    icon: ShieldCheck,  label: "ID Verified" },
  { key: "paid",        short: "Paid",  icon: CreditCard,   label: "Paid" },
  { key: "key_issued",  short: "Key",   icon: Key,          label: "Key Issued" },
];

const ReturningGuestStrip = ({ pid }) => {
  const [data, setData] = useState(null);
  useEffect(() => {
    axios.get(`${API}/guest-incidents/returning/${pid}`).then(r => setData(r.data)).catch(() => {});
  }, [pid]);
  if (!data || data.count === 0) return null;
  return (
    <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4" data-testid="returning-guest-strip">
      <div className="flex items-center gap-2 mb-2">
        <Sparkles className="w-4 h-4 text-amber-600" />
        <span className="text-xs font-black text-amber-800 uppercase tracking-wider">🔁 Dönen misafirler — 48 saat içinde varış ({data.count})</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
        {data.guests.slice(0, 6).map(g => (
          <div key={g.id} className="bg-white border border-amber-100 rounded-xl px-3 py-2.5" data-testid={`returning-guest-${g.id}`}>
            <div className="flex items-center gap-1.5 text-xs font-bold text-stone-800">
              {g.vip && <span title="VIP">👑</span>}
              {g.guest_name}
              <span className="ml-auto text-[10px] font-mono text-stone-400">{g.check_in}{g.room_number ? ` · Oda ${g.room_number}` : ""}</span>
            </div>
            <div className="flex flex-wrap gap-1 mt-1.5">
              {(g.prefs || []).slice(0, 4).map((p, i) => (
                <span key={i} className="text-[9px] px-1.5 py-0.5 bg-emerald-50 text-emerald-700 rounded-full border border-emerald-100">{p}</span>
              ))}
              {g.open_incidents > 0 && (
                <span className="text-[9px] px-1.5 py-0.5 bg-rose-100 text-rose-700 rounded-full font-bold">⚠ {g.open_incidents} açık olay</span>
              )}
            </div>
            {(g.incidents || []).slice(0, 1).map(i => (
              <p key={i.id} className="text-[10px] text-rose-600 mt-1 line-clamp-2">⚠ {i.text}</p>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
};

export const ArrivalsCockpit = ({ propertyId, user }) => {
  const [data, setData] = useState({ counters: { total: 0, registered: 0, id_verified: 0, paid: 0, key_issued: 0 }, arrivals: [] });
  const [timeWindow, setTimeWindow] = useState("7d");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [qrFor, setQrFor] = useState(null);
  const [keyFor, setKeyFor] = useState(null);
  const [busy, setBusy] = useState(null); // booking id being mutated
  const [tips, setTips] = useState(null); // { guest, loading, items, model }
  const [dwCfg, setDwCfg] = useState(null);

  const pid = propertyId || "all";
  const canAct = user?.role === "admin" || user?.role === "manager" || user?.role === "receptionist";

  useEffect(() => {
    if (!pid || pid === "all") { setDwCfg(null); return; }
    axios.get(`${API}/booking/damage-waiver/${pid}`)
      .then(r => setDwCfg(r.data?.enabled ? r.data : null))
      .catch(() => setDwCfg(null));
  }, [pid]);

  const addWaiver = async (a) => {
    setBusy(a.booking_id);
    try {
      const { data } = await axios.post(`${API}/damage-protection/attach/${a.booking_id}`);
      toast.success(`Hasar koruması eklendi — +${data.fee} ${data.currency} (${data.nights} gece)`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Eklenemedi"); }
    finally { setBusy(null); }
  };

  const verifyId = (a) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/jpeg,image/png,image/webp";
    input.onchange = () => {
      const file = input.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = async () => {
        setBusy(a.booking_id);
        toast.info("Kimlik AI ile okunuyor…");
        try {
          const { data } = await axios.post(`${API}/id-verification/verify`, {
            booking_id: a.booking_id, image_base64: reader.result,
          });
          if (data.status === "verified") toast.success(`Kimlik doğrulandı ✓ ${data.extracted?.full_name || ""} (eşleşme %${Math.round(data.name_match * 100)})`);
          else if (data.status === "mismatch") toast.warning(`İsim eşleşmedi: belgede "${data.extracted?.full_name}", rezervasyonda "${a.guest_name}"`);
          else toast.error("Belge okunamadı — daha net bir fotoğraf deneyin");
          load();
        } catch (e) { toast.error(e?.response?.data?.detail || "Doğrulama başarısız"); }
        finally { setBusy(null); }
      };
      reader.readAsDataURL(file);
    };
    input.click();
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ window: timeWindow });
      if (q) params.set("q", q);
      const { data: d } = await axios.get(`${API}/arrivals/${pid}?${params}`);
      setData(d);
    } catch { /* silent */ }
    setLoading(false);
  }, [pid, timeWindow, q]);

  useEffect(() => {
    const t = setTimeout(load, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [load]);

  const sendToKiosk = async (a) => {
    setBusy(a.booking_id);
    try {
      await axios.post(`${API}/guest-journey/kiosk-dispatch`, { booking_id: a.booking_id });
      toast.success(`${a.guest_name} kiosk'a gönderildi — misafir kioskta adıyla karşılanacak`);
    } catch (e) { toast.error(e.response?.data?.detail || "Kiosk'a gönderilemedi"); }
    finally { setBusy(""); }
  };

  const loadSmartTips = async (a) => {
    setTips({ guest: a.guest_name, loading: true, items: [] });
    try {
      const names = (a.guest_name || "").split(" ");
      const r = await axios.post(`${API}/mews-ai/smart-tips`, {
        profile: {
          first_name: names[0] || "", last_name: names.slice(1).join(" "),
          notes: `Kanal: ${a.source || "-"} · ${a.nights || 1} gece · Oda: ${a.room_number || "atanmadı"} · Check-in: ${a.check_in || ""} · ETA: ${a.eta || "-"}`,
        },
      });
      setTips({ guest: a.guest_name, loading: false, items: r.data.tips || [], model: r.data.model });
    } catch {
      toast.error("Smart Tips alınamadı");
      setTips(null);
    }
  };

  const sendRegistration = async (bookingId) => {
    setBusy(bookingId);
    try {
      await axios.post(`${API}/guest-journey/send-registration/${bookingId}`);
      toast.success("Registration link sent");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed");
    }
    setBusy(null);
  };
  const markPaid = async (bookingId) => {
    setBusy(bookingId);
    try {
      await axios.post(`${API}/arrivals/${bookingId}/mark-paid`);
      toast.success("Marked as paid");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setBusy(null);
  };
  const issueKey = async (bookingId) => {
    setBusy(bookingId);
    try {
      const { data } = await axios.post(`${API}/arrivals/${bookingId}/issue-key`);
      toast.success(`Digital key issued: ${data.code}`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Key requires paid status"); }
    setBusy(null);
  };
  const revokeKey = async (bookingId) => {
    if (!window.confirm?.("Revoke this digital key?")) return;
    setBusy(bookingId);
    try {
      await axios.post(`${API}/arrivals/${bookingId}/revoke-key`);
      toast.success("Key revoked");
      load();
    } catch (e) { toast.error("Failed"); }
    setBusy(null);
  };

  const kpi = data.counters || {};
  const coverage = kpi.total ? Math.round((kpi.key_issued / kpi.total) * 100) : 0;
  const baseUrl = process.env.REACT_APP_BACKEND_URL || "";
  const regLink = (token) => `${baseUrl}/register/${token}`;

  const ProgressDots = ({ progress, stage }) => (
    <div className="flex items-center gap-0.5">
      {STEPS.map((s, i) => {
        const done = progress?.[s.key];
        const current = !done && (stage === i);
        const Icon = s.icon;
        return (
          <div key={s.key} className="flex items-center">
            <div
              title={s.label}
              className={`w-6 h-6 rounded-full flex items-center justify-center transition
                ${done ? "bg-emerald-500 text-white"
                       : current ? "bg-amber-400 text-white ring-2 ring-amber-200"
                                 : "bg-stone-100 text-stone-400"}`}
            >
              <Icon className="w-3 h-3" />
            </div>
            {i < STEPS.length - 1 && (
              <div className={`w-2.5 h-0.5 ${done ? "bg-emerald-500" : "bg-stone-200"}`} />
            )}
          </div>
        );
      })}
    </div>
  );

  const KpiCard = ({ label, value, total, color, icon: Icon, testId }) => {
    const pct = total ? Math.round((value / total) * 100) : 0;
    return (
      <div className="bg-white rounded-xl border border-stone-200 p-3" data-testid={testId}>
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] uppercase tracking-wider text-stone-500 font-semibold">{label}</span>
          <Icon className="w-3.5 h-3.5" style={{ color }} />
        </div>
        <div className="flex items-baseline gap-1">
          <span className="text-2xl font-black text-stone-800">{value}</span>
          {total > 0 && <span className="text-xs text-stone-400">/{total}</span>}
        </div>
        <div className="h-1 bg-stone-100 rounded-full mt-1.5 overflow-hidden">
          <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-5" data-testid="arrivals-cockpit">
      <ReturningGuestStrip pid={pid} />
      {/* Hero */}
      <div className="bg-gradient-to-br from-emerald-600 via-teal-600 to-cyan-700 rounded-2xl p-6 text-white shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-72 h-72 bg-white/10 rounded-full -translate-y-24 translate-x-24 blur-3xl" />
        <div className="relative flex items-start justify-between gap-6 flex-wrap">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <BedDouble className="w-5 h-5" />
              <span className="text-[11px] font-bold uppercase tracking-widest opacity-90">Arrivals Cockpit</span>
            </div>
            <h2 className="text-3xl font-black mb-1" data-testid="cockpit-title">Contactless check-in, one pane.</h2>
            <p className="text-sm opacity-90">
              Track every guest from link sent → registered → ID verified → paid → digital key issued.
            </p>
          </div>
          <div className="flex items-center gap-5">
            <div>
              <p className="text-3xl font-black" data-testid="total-arrivals">{kpi.total || 0}</p>
              <p className="text-[10px] opacity-80 uppercase tracking-wider">Arrivals</p>
            </div>
            <div className="h-10 w-px bg-white/30" />
            <div>
              <p className="text-3xl font-black text-emerald-200">{coverage}%</p>
              <p className="text-[10px] opacity-80 uppercase tracking-wider">Keys Ready</p>
            </div>
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <KpiCard label="Arrivals" value={kpi.total || 0} total={0} color="#0EA5A3" icon={Calendar} testId="kpi-arrivals" />
        <KpiCard label="Registered" value={kpi.registered || 0} total={kpi.total} color="#6366F1" icon={UserCheck} testId="kpi-registered" />
        <KpiCard label="ID Verified" value={kpi.id_verified || 0} total={kpi.total} color="#A855F7" icon={ShieldCheck} testId="kpi-id-verified" />
        <KpiCard label="Paid" value={kpi.paid || 0} total={kpi.total} color="#10B981" icon={CreditCard} testId="kpi-paid" />
        <KpiCard label="Keys Issued" value={kpi.key_issued || 0} total={kpi.total} color="#F59E0B" icon={Key} testId="kpi-keys" />
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-1 bg-stone-100 rounded-lg p-0.5">
          {WINDOWS.map(w => (
            <button key={w.id} onClick={() => setTimeWindow(w.id)} data-testid={`win-${w.id}`}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition ${timeWindow === w.id ? "bg-white text-stone-800 shadow-sm" : "text-stone-500 hover:text-stone-700"}`}>
              {w.label}
            </button>
          ))}
        </div>
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <Input value={q} onChange={e => setQ(e.target.value)} placeholder="Search by guest, ref, email..." className="pl-9 h-9" data-testid="arrivals-search" />
          {q && <button onClick={() => setQ("")} className="absolute right-2 top-1/2 -translate-y-1/2 p-1 hover:bg-stone-100 rounded"><X className="w-3 h-3" /></button>}
        </div>
        <Button size="sm" variant="outline" onClick={load} data-testid="refresh-arrivals"><RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /></Button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-stone-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm" data-testid="arrivals-table">
            <thead className="bg-stone-50 text-[10px] uppercase tracking-wider text-stone-500">
              <tr>
                <th className="px-4 py-3 text-left font-semibold">Guest</th>
                <th className="px-4 py-3 text-left font-semibold">Check-in</th>
                <th className="px-4 py-3 text-left font-semibold">Room</th>
                <th className="px-4 py-3 text-left font-semibold">Progress</th>
                <th className="px-4 py-3 text-right font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {loading && data.arrivals.length === 0 && (
                <tr><td colSpan={5} className="py-12 text-center text-stone-400"><RefreshCw className="w-5 h-5 animate-spin inline mr-2" />Loading...</td></tr>
              )}
              {!loading && data.arrivals.length === 0 && (
                <tr><td colSpan={5} className="py-16 text-center text-stone-400" data-testid="empty-arrivals">
                  <BedDouble className="w-10 h-10 mx-auto mb-2 opacity-40" />
                  <p>No arrivals in this window.</p>
                </td></tr>
              )}
              {data.arrivals.map(a => (
                <tr key={a.booking_id} className="hover:bg-stone-50 transition" data-testid={`arrival-${a.booking_id}`}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-400 to-purple-500 text-white flex items-center justify-center text-[11px] font-bold flex-shrink-0">
                        {(a.guest_name || "?").slice(0, 2).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <p className="font-semibold text-stone-800 truncate">
                          {a.guest_name || "Walk-in"}
                          {a.noshow_secured && <span className="ml-1" title="Depozito alındı — no-show'a karşı güvenceli" data-testid={`secured-badge-${a.booking_id}`}>🛡️</span>}
                        </p>
                        <p className="text-[10px] text-stone-500 truncate">{a.booking_ref} · {a.source}{a.nights > 1 ? ` · ${a.nights}n` : ""}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-stone-700">
                    <div className="flex items-center gap-1">
                      <Calendar className="w-3 h-3 text-stone-400" />
                      <span className="font-medium">{a.check_in}</span>
                    </div>
                    {a.eta && <div className="text-[10px] text-stone-400 flex items-center gap-0.5"><Clock className="w-2.5 h-2.5" />ETA {a.eta}</div>}
                  </td>
                  <td className="px-4 py-3 text-stone-700">
                    {a.room_number ? (
                      <Badge className="bg-stone-100 text-stone-700 font-bold">#{a.room_number}</Badge>
                    ) : <span className="text-xs text-stone-400">Unassigned</span>}
                  </td>
                  <td className="px-4 py-3">
                    <ProgressDots progress={a.progress} stage={a.stage} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      {a.id_verification === "verified" ? (
                        <span className="p-1.5 text-sky-500" title="Kimlik doğrulandı ✓" data-testid={`idv-verified-${a.booking_id}`}>
                          <UserCheck className="w-4 h-4" />
                        </span>
                      ) : (
                        <button onClick={() => verifyId(a)} disabled={!canAct || busy === a.booking_id}
                          className={`p-1.5 rounded-lg border border-transparent disabled:opacity-40 ${
                            a.id_verification === "mismatch"
                              ? "text-rose-500 hover:bg-rose-50 hover:border-rose-200"
                              : "text-sky-600 hover:bg-sky-50 hover:border-sky-200"}`}
                          title={a.id_verification === "mismatch" ? "İsim eşleşmedi — tekrar dene" : "Kimlik doğrula (AI)"}
                          data-testid={`idv-btn-${a.booking_id}`}>
                          <CreditCard className="w-4 h-4" />
                        </button>
                      )}
                      {dwCfg && !a.damage_waiver ? (
                        <button onClick={() => addWaiver(a)} disabled={!canAct || busy === a.booking_id}
                          className="p-1.5 hover:bg-emerald-50 rounded-lg text-emerald-600 border border-transparent hover:border-emerald-200 disabled:opacity-40"
                          title={`Hasar koruması ekle (+${dwCfg.fee_per_night}/gece)`} data-testid={`add-waiver-${a.booking_id}`}>
                          <ShieldCheck className="w-4 h-4" />
                        </button>
                      ) : a.damage_waiver ? (
                        <span className="p-1.5 text-emerald-500" title="Hasar koruması aktif" data-testid={`waiver-active-${a.booking_id}`}>
                          <ShieldCheck className="w-4 h-4 fill-emerald-100" />
                        </span>
                      ) : null}
                      <button onClick={() => loadSmartTips(a)} disabled={busy === a.booking_id}
                        className="p-1.5 hover:bg-amber-50 rounded-lg text-amber-500 border border-transparent hover:border-amber-200"
                        title="AI Smart Tips" data-testid={`smart-tips-${a.booking_id}`}>
                        <Lightbulb className="w-4 h-4" />
                      </button>
                      <button onClick={() => sendToKiosk(a)} disabled={busy === a.booking_id}
                        className="p-1.5 hover:bg-indigo-50 rounded-lg text-indigo-600 border border-transparent hover:border-indigo-200"
                        title="Kiosk'a gönder" data-testid={`kiosk-send-${a.booking_id}`}>
                        <Monitor className="w-4 h-4" />
                      </button>
                      {!a.progress.link_sent ? (
                        <Button size="sm" variant="outline" disabled={!canAct || busy === a.booking_id} onClick={() => sendRegistration(a.booking_id)} data-testid={`send-${a.booking_id}`}>
                          <Send className="w-3 h-3 mr-1" />Send Link
                        </Button>
                      ) : (
                        <button onClick={() => setQrFor(a)} className="p-1.5 hover:bg-stone-100 rounded-lg text-stone-600" title="Show QR" data-testid={`qr-${a.booking_id}`}>
                          <QrCode className="w-4 h-4" />
                        </button>
                      )}
                      {!a.progress.paid && (
                        <Button size="sm" variant="outline" disabled={!canAct || busy === a.booking_id} onClick={() => markPaid(a.booking_id)} data-testid={`pay-${a.booking_id}`}>
                          <CreditCard className="w-3 h-3 mr-1" />Mark Paid
                        </Button>
                      )}
                      {a.progress.paid && !a.progress.key_issued && (
                        <Button size="sm" disabled={!canAct || busy === a.booking_id} onClick={() => issueKey(a.booking_id)}
                          className="bg-amber-500 hover:bg-amber-600 text-white" data-testid={`issue-${a.booking_id}`}>
                          <Key className="w-3 h-3 mr-1" />Issue Key
                        </Button>
                      )}
                      {a.progress.key_issued && (
                        <button onClick={() => setKeyFor(a)} className="flex items-center gap-1 px-2 py-1 bg-amber-50 border border-amber-200 rounded-lg hover:bg-amber-100 transition" data-testid={`key-${a.booking_id}`}>
                          <Key className="w-3 h-3 text-amber-600" />
                          <span className="font-mono text-[11px] font-bold text-amber-800">{a.digital_key_code}</span>
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* QR Modal */}
      {qrFor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={() => setQrFor(null)}>
          <div onClick={e => e.stopPropagation()} className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl" data-testid="qr-modal">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-black text-stone-800">{qrFor.guest_name}</h3>
                <p className="text-[11px] text-stone-500">{qrFor.booking_ref} · Check-in {qrFor.check_in}</p>
              </div>
              <button onClick={() => setQrFor(null)} className="p-1 hover:bg-stone-100 rounded"><X className="w-4 h-4" /></button>
            </div>
            <div className="flex flex-col items-center bg-stone-50 rounded-xl p-5 mb-4">
              {qrFor.registration_token ? (
                <QRCodeSVG value={regLink(qrFor.registration_token)} size={180} level="M" includeMargin />
              ) : (
                <div className="text-stone-400 text-sm p-10 text-center">No registration link. Send one first.</div>
              )}
              <p className="text-[10px] text-stone-400 mt-3">Scan to open pre-arrival registration</p>
            </div>
            {qrFor.registration_token && (
              <div className="flex items-center gap-2 bg-stone-100 rounded-lg p-2">
                <code className="flex-1 text-[11px] text-stone-700 truncate">{regLink(qrFor.registration_token)}</code>
                <button onClick={() => { navigator.clipboard.writeText(regLink(qrFor.registration_token)); toast.success("Link copied"); }}
                  className="p-1.5 hover:bg-white rounded" data-testid="copy-link"><Copy className="w-3.5 h-3.5" /></button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Key Modal */}
      {keyFor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={() => setKeyFor(null)}>
          <div onClick={e => e.stopPropagation()} className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl" data-testid="key-modal">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-black text-stone-800">Digital Key Issued</h3>
                <p className="text-[11px] text-stone-500">{keyFor.guest_name} · Room {keyFor.room_number || "—"}</p>
              </div>
              <button onClick={() => setKeyFor(null)} className="p-1 hover:bg-stone-100 rounded"><X className="w-4 h-4" /></button>
            </div>
            <div className="bg-gradient-to-br from-amber-50 to-yellow-50 border border-amber-200 rounded-xl p-6 text-center mb-4">
              <Key className="w-8 h-8 text-amber-600 mx-auto mb-2" />
              <p className="text-[10px] uppercase tracking-wider text-amber-700 font-bold mb-1">Unlock Code</p>
              <p className="font-mono text-3xl font-black text-amber-900 tracking-[0.3em]">{keyFor.digital_key_code}</p>
              <p className="text-[10px] text-amber-700 mt-2">Expires {keyFor.digital_key_expires ? String(keyFor.digital_key_expires).slice(0, 16).replace("T", " ") : "—"}</p>
            </div>
            <div className="flex items-center gap-2">
              <Button size="sm" variant="outline" onClick={() => { navigator.clipboard.writeText(keyFor.digital_key_code); toast.success("Code copied"); }}>
                <Copy className="w-3 h-3 mr-1" />Copy Code
              </Button>
              <Button size="sm" variant="outline" onClick={() => { revokeKey(keyFor.booking_id); setKeyFor(null); }}
                className="text-red-600 hover:bg-red-50 ml-auto" data-testid="revoke-key">
                <Ban className="w-3 h-3 mr-1" />Revoke
              </Button>
            </div>
          </div>
        </div>
      )}
      {tips && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={() => setTips(null)} data-testid="smart-tips-modal">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Lightbulb className="w-4 h-4 text-amber-500" />
                <h3 className="text-sm font-bold text-stone-900">Smart Tips — {tips.guest}</h3>
              </div>
              <button onClick={() => setTips(null)} className="p-1 hover:bg-stone-100 rounded-lg" data-testid="smart-tips-close"><X className="w-4 h-4" /></button>
            </div>
            {tips.loading ? (
              <div className="py-8 text-center text-sm text-stone-400" data-testid="smart-tips-loading">AI önerileri hazırlanıyor…</div>
            ) : (
              <div className="space-y-2.5">
                {tips.items.map((t, i) => (
                  <div key={i} className="flex gap-3 bg-amber-50/60 border border-amber-100 rounded-xl p-3" data-testid={`smart-tip-${i}`}>
                    <div className="w-7 h-7 rounded-lg bg-amber-100 flex items-center justify-center text-sm shrink-0">
                      {{ star: "⭐", gift: "🎁", leaf: "🌿", alert: "⚠️", moon: "🌙", briefcase: "💼", heart: "💛", coffee: "☕", wine: "🍷", utensils: "🍽️" }[t.icon] || "💡"}
                    </div>
                    <div>
                      <div className="text-xs font-bold text-stone-800">{t.title}</div>
                      <div className="text-[11px] text-stone-600 mt-0.5">{t.action}</div>
                    </div>
                  </div>
                ))}
                <p className="text-[10px] text-stone-400 text-right">{tips.model === "fallback" ? "kural tabanlı" : `AI · ${tips.model}`}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
