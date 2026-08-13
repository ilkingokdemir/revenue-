import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Handshake, Plus, Calculator, FilePdf, PaperPlaneTilt, CalendarPlus, UsersThree } from "@phosphor-icons/react";
import { Loader2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const STATUS_TR = { new: "Yeni", quoted: "Teklif verildi", negotiating: "Pazarlık", won: "Kazanıldı", lost: "Kaybedildi" };
const STATUS_COLOR = { new: "bg-stone-100 text-stone-600", quoted: "bg-sky-100 text-sky-700", negotiating: "bg-amber-100 text-amber-700", won: "bg-emerald-100 text-emerald-700", lost: "bg-rose-100 text-rose-700" };
const REC_TR = { accept: "✓ Kabul", negotiate: "⚠ Pazarlık", reject: "✗ Red" };

export default function GroupSalesPanel({ propertyId }) {
  const pid = propertyId && propertyId !== "all" ? propertyId : "default";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [quoting, setQuoting] = useState(null);
  const [alts, setAlts] = useState({});
  const [altLoading, setAltLoading] = useState(null);
  const [emailing, setEmailing] = useState(null);
  const [pickups, setPickups] = useState({});
  const [roomingName, setRoomingName] = useState("");

  const loadPickup = async (rfp) => {
    if (pickups[rfp.id]) { setPickups((p) => ({ ...p, [rfp.id]: null })); return; }
    try {
      const { data: d } = await axios.get(`${API}/group-sales/rfp/${rfp.id}/pickup`);
      setPickups((p) => ({ ...p, [rfp.id]: d }));
    } catch (e) { toast.error(e?.response?.data?.detail || "Pickup alınamadı"); }
  };
  const addRooming = async (rfp) => {
    if (!roomingName.trim()) return toast.error("Misafir adı gerekli");
    try {
      await axios.post(`${API}/group-sales/rfp/${rfp.id}/rooming`, { guest_name: roomingName });
      setRoomingName("");
      const { data: d } = await axios.get(`${API}/group-sales/rfp/${rfp.id}/pickup`);
      setPickups((p) => ({ ...p, [rfp.id]: d }));
    } catch (e) { toast.error(e?.response?.data?.detail || "Eklenemedi"); }
  };
  const releaseRooms = async (rfp) => {
    const pk = pickups[rfp.id];
    const n = Math.max(1, (pk?.block_rooms || 1) - (pk?.picked_rooms || 0) - 1);
    try {
      const { data: r } = await axios.post(`${API}/group-sales/rfp/${rfp.id}/pickup/release`, { rooms: n });
      toast.success(`${r.released} oda satışa geri açıldı (blok: ${r.block_rooms})`);
      const { data: d } = await axios.get(`${API}/group-sales/rfp/${rfp.id}/pickup`);
      setPickups((p) => ({ ...p, [rfp.id]: d }));
    } catch (e) { toast.error(e?.response?.data?.detail || "Serbest bırakılamadı"); }
  };
  const [form, setForm] = useState({ group_name: "", contact_email: "", check_in: "", check_out: "", rooms: 10, offered_rate: 90, wash_pct: 10, comp_rooms: 0 });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data: d } = await axios.get(`${API}/group-sales/${pid}`);
      setData(d);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const createRfp = async () => {
    if (!form.check_in || !form.check_out) return toast.error("Tarihler gerekli");
    try {
      await axios.post(`${API}/group-sales/${pid}/rfp`, form);
      toast.success("RFP oluşturuldu");
      setForm({ ...form, group_name: "", contact_email: "" });
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Oluşturulamadı"); }
  };
  const quote = async (rfp) => {
    setQuoting(rfp.id);
    try {
      const { data: r } = await axios.post(`${API}/group-sales/rfp/${rfp.id}/quote`, {});
      toast.success(`v${r.version.v} teklifi: ${REC_TR[r.version.recommendation] || r.version.recommendation}`);
      if ((r.alternatives || []).length > 0) {
        setAlts((p) => ({ ...p, [rfp.id]: r.alternatives }));
        toast.info(`Teklif RED — ${r.alternatives.length} alternatif tarih önerildi`);
      }
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Fiyatlanamadı"); }
    finally { setQuoting(null); }
  };
  const findAlts = async (rfp) => {
    setAltLoading(rfp.id);
    try {
      const { data: r } = await axios.post(`${API}/group-sales/rfp/${rfp.id}/alternatives`);
      setAlts((p) => ({ ...p, [rfp.id]: r.alternatives }));
      toast[r.alternatives.length ? "success" : "info"](
        r.alternatives.length ? `${r.alternatives.length} daha kârlı tarih bulundu` : "Mevcut tarihlerden daha iyi pencere yok");
    } catch (e) { toast.error(e?.response?.data?.detail || "Aranamadı"); }
    finally { setAltLoading(null); }
  };
  const reschedule = async (rfp, a) => {
    setAltLoading(rfp.id);
    try {
      const { data: r } = await axios.post(`${API}/group-sales/rfp/${rfp.id}/reschedule`, { check_in: a.check_in, check_out: a.check_out });
      toast.success(`RFP ${a.check_in} tarihine taşındı — yeni teklif: ${REC_TR[r.version.recommendation] || r.version.recommendation}`);
      setAlts((p) => ({ ...p, [rfp.id]: [] }));
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Taşınamadı"); }
    finally { setAltLoading(null); }
  };
  const sendEmail = async (rfp) => {
    setEmailing(rfp.id);
    try {
      const { data: r } = await axios.post(`${API}/group-sales/rfp/${rfp.id}/email`, {});
      toast.success(r.note || `Teklif ${r.to} adresine gönderildi`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gönderilemedi"); }
    finally { setEmailing(null); }
  };
  const setStatus = async (rfp, status) => {
    await axios.put(`${API}/group-sales/rfp/${rfp.id}`, { status });
    load();
  };
  const pdf = async (analysisId, name) => {
    try {
      const { data: blob } = await axios.post(`${API}/group-displacement/proposal-pdf/${analysisId}`, {}, { responseType: "blob" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `grup-teklif-${name}.pdf`; a.click();
      URL.revokeObjectURL(url);
    } catch { toast.error("PDF üretilemedi"); }
  };

  if (loading) return <div className="p-10 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-stone-400" /></div>;
  const p = data?.pipeline;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5" data-testid="group-sales-panel">
      <div>
        <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2">
          <Handshake size={22} weight="fill" className="text-teal-600" /> Group Sales OS
        </h1>
        <p className="text-sm text-stone-500 mt-0.5">
          RFP yaşam döngüsü + wash/attrition + comp oda + teklif versiyonlama. Her teklif shoulder-night'lı
          displacement analiziyle fiyatlanır, tek tıkla PDF'e döner.
        </p>
      </div>

      {p && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="p-4 rounded-2xl bg-white border border-stone-200" data-testid="gs-pipeline-card">
            <div className="text-[10px] uppercase font-bold text-stone-400">Pipeline</div>
            <div className="text-lg font-black text-stone-900">{Object.values(p.by_status).reduce((a, b) => a + b, 0)} RFP</div>
          </div>
          <div className="p-4 rounded-2xl bg-sky-50 border border-sky-200" data-testid="gs-potential-card">
            <div className="text-[10px] uppercase font-bold text-sky-600">Potansiyel gelir</div>
            <div className="text-lg font-black text-sky-900">{p.potential_revenue}</div>
          </div>
          <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200" data-testid="gs-won-card">
            <div className="text-[10px] uppercase font-bold text-emerald-600">Kazanılan</div>
            <div className="text-lg font-black text-emerald-900">{p.won_revenue}</div>
          </div>
          <div className="p-4 rounded-2xl bg-white border border-stone-200" data-testid="gs-conversion-card">
            <div className="text-[10px] uppercase font-bold text-stone-400">Dönüşüm</div>
            <div className="text-lg font-black text-stone-900">%{p.conversion_pct}</div>
          </div>
        </div>
      )}

      {/* New RFP */}
      <div className="bg-white border border-stone-200 rounded-2xl p-4 grid grid-cols-2 md:grid-cols-8 gap-3 items-end" data-testid="gs-rfp-form">
        <div className="col-span-2">
          <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Grup adı</label>
          <input value={form.group_name} onChange={(e) => setForm({ ...form, group_name: e.target.value })} data-testid="gs-name-input"
            className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" placeholder="Acme Kongre" />
        </div>
        <div><label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Giriş</label>
          <input type="date" value={form.check_in} onChange={(e) => setForm({ ...form, check_in: e.target.value })} data-testid="gs-checkin-input" className="w-full border border-stone-200 rounded-lg px-2 py-2 text-xs" /></div>
        <div><label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Çıkış</label>
          <input type="date" value={form.check_out} onChange={(e) => setForm({ ...form, check_out: e.target.value })} data-testid="gs-checkout-input" className="w-full border border-stone-200 rounded-lg px-2 py-2 text-xs" /></div>
        <div><label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Oda</label>
          <input type="number" min="1" value={form.rooms} onChange={(e) => setForm({ ...form, rooms: e.target.value })} data-testid="gs-rooms-input" className="w-full border border-stone-200 rounded-lg px-2 py-2 text-sm" /></div>
        <div><label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Fiyat</label>
          <input type="number" min="0" value={form.offered_rate} onChange={(e) => setForm({ ...form, offered_rate: e.target.value })} data-testid="gs-rate-input" className="w-full border border-stone-200 rounded-lg px-2 py-2 text-sm" /></div>
        <div><label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Wash % / Comp</label>
          <div className="flex gap-1">
            <input type="number" min="0" max="60" value={form.wash_pct} onChange={(e) => setForm({ ...form, wash_pct: e.target.value })} data-testid="gs-wash-input" className="w-1/2 border border-stone-200 rounded-lg px-1.5 py-2 text-xs" />
            <input type="number" min="0" value={form.comp_rooms} onChange={(e) => setForm({ ...form, comp_rooms: e.target.value })} data-testid="gs-comp-input" className="w-1/2 border border-stone-200 rounded-lg px-1.5 py-2 text-xs" />
          </div></div>
        <button onClick={createRfp} data-testid="gs-create-btn"
          className="flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-bold">
          <Plus size={14} /> RFP
        </button>
      </div>

      {/* RFP list */}
      <div className="space-y-3" data-testid="gs-rfp-list">
        {(data?.rfps || []).length === 0 && <p className="text-sm text-stone-400 text-center py-6">Henüz RFP yok — ilk grup talebini ekleyin.</p>}
        {(data?.rfps || []).map((r) => {
          const last = (r.versions || [])[r.versions?.length - 1];
          return (
            <div key={r.id} className="bg-white border border-stone-200 rounded-2xl p-4" data-testid={`gs-rfp-${r.id}`}>
              <div className="flex items-center gap-3 flex-wrap">
                <div className="flex-1 min-w-[200px]">
                  <p className="text-sm font-black text-stone-900">{r.group_name}</p>
                  <p className="text-[11px] text-stone-500">{r.check_in} → {r.check_out} · {r.rooms} oda @ {r.offered_rate} · wash %{r.wash_pct} · {r.comp_rooms} comp</p>
                </div>
                <select value={r.status} onChange={(e) => setStatus(r, e.target.value)} data-testid={`gs-status-${r.id}`}
                  className={`text-[11px] font-bold rounded-full px-2.5 py-1.5 border-0 ${STATUS_COLOR[r.status]}`}>
                  {Object.entries(STATUS_TR).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
                <button onClick={() => quote(r)} disabled={quoting === r.id} data-testid={`gs-quote-${r.id}`}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-stone-900 hover:bg-stone-700 text-white text-xs font-bold disabled:opacity-50">
                  {quoting === r.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Calculator size={13} weight="fill" />}
                  Fiyatla (v{(r.versions?.length || 0) + 1})
                </button>
                {(r.versions || []).length > 0 && (
                  <>
                    <button onClick={() => findAlts(r)} disabled={altLoading === r.id} data-testid={`gs-alts-${r.id}`}
                      title="Daha kârlı alternatif tarih ara"
                      className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-stone-300 hover:bg-stone-50 text-stone-700 text-xs font-bold disabled:opacity-50">
                      {altLoading === r.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CalendarPlus size={13} />}
                      Alternatif tarih
                    </button>
                    <button onClick={() => sendEmail(r)} disabled={emailing === r.id} data-testid={`gs-email-${r.id}`}
                      title={r.contact_email ? `${r.contact_email} adresine gönder` : "İletişim e-postası tanımlı değil"}
                      className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-bold disabled:opacity-50">
                      {emailing === r.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <PaperPlaneTilt size={13} weight="fill" />}
                      E-posta
                    </button>
                    {r.status === "won" && r.block_booking_id && (
                      <button onClick={() => loadPickup(r)} data-testid={`gs-pickup-btn-${r.id}`}
                        className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold">
                        <UsersThree size={13} weight="fill" /> Pickup
                      </button>
                    )}
                  </>
                )}
              </div>
              {(alts[r.id] || []).length > 0 && (
                <div className="mt-3 bg-indigo-50 border border-indigo-200 rounded-xl p-3" data-testid={`gs-alt-list-${r.id}`}>
                  <p className="text-[10px] font-black uppercase text-indigo-700 mb-1.5">📅 Daha kârlı alternatif tarihler</p>
                  {alts[r.id].map((a, i) => (
                    <div key={i} className="flex items-center gap-3 text-[11px] py-1 flex-wrap" data-testid={`gs-alt-${r.id}-${i}`}>
                      <span className="font-bold text-stone-800">{a.check_in} → {a.check_out}</span>
                      <span className="text-stone-500">({a.offset_days > 0 ? "+" : ""}{a.offset_days} gün)</span>
                      <span className="text-stone-500">{a.total_displaced_rooms} displacement</span>
                      <span className={`font-bold ${a.recommendation === "accept" ? "text-emerald-600" : "text-amber-600"}`}>{REC_TR[a.recommendation]}</span>
                      <span className="font-black text-indigo-700 ml-auto">net +{a.gain_vs_current} kazanç</span>
                      <button onClick={() => reschedule(r, a)} disabled={altLoading === r.id} data-testid={`gs-reschedule-${r.id}-${i}`}
                        className="px-2.5 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-[10px] font-bold disabled:opacity-50">
                        Bu tarihle fiyatla
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {pickups[r.id] && (() => { const pk = pickups[r.id]; return (
                <div className={`mt-3 rounded-xl border p-3 ${pk.status === "on_track" ? "bg-emerald-50 border-emerald-200" : pk.status === "behind" ? "bg-amber-50 border-amber-200" : "bg-rose-50 border-rose-200"}`} data-testid={`gs-pickup-${r.id}`}>
                  <div className="flex items-center gap-3 flex-wrap mb-2">
                    <p className="text-[10px] font-black uppercase text-stone-600">Blok Pickup Takibi</p>
                    <span className="text-[11px] font-bold text-stone-800">{pk.picked_rooms}/{pk.block_rooms} oda isimli (%{pk.pickup_pct})</span>
                    <span className="text-[10px] text-stone-500">beklenen tempo: %{pk.expected_pct_now}</span>
                    <span className={`text-[10px] font-black px-2 py-0.5 rounded-full ${pk.deviation_pts >= -5 ? "bg-emerald-100 text-emerald-700" : pk.deviation_pts > -20 ? "bg-amber-100 text-amber-700" : "bg-rose-100 text-rose-700"}`} data-testid={`gs-pickup-dev-${r.id}`}>
                      {pk.deviation_pts > 0 ? "+" : ""}{pk.deviation_pts} puan
                    </span>
                    <span className="text-[10px] text-stone-400 ml-auto">rooming son gün: {pk.rooming_deadline} · girişe {pk.days_to_arrival}g</span>
                  </div>
                  <div className="h-2 rounded-full bg-stone-200 overflow-hidden mb-2">
                    <div className={`h-full rounded-full ${pk.status === "on_track" ? "bg-emerald-500" : pk.status === "behind" ? "bg-amber-500" : "bg-rose-500"}`} style={{ width: `${Math.min(pk.pickup_pct, 100)}%` }} />
                  </div>
                  <p className="text-[11px] text-stone-600 mb-2">{pk.suggestion}</p>
                  <div className="flex items-center gap-2 flex-wrap">
                    <input value={roomingName} onChange={(e) => setRoomingName(e.target.value)}
                      placeholder="Misafir adı ekle..." data-testid={`gs-rooming-input-${r.id}`}
                      className="border border-stone-300 rounded-lg px-2.5 py-1.5 text-xs w-48 bg-white" />
                    <button onClick={() => addRooming(r)} data-testid={`gs-rooming-add-${r.id}`}
                      className="px-3 py-1.5 rounded-lg bg-stone-900 hover:bg-stone-700 text-white text-[10px] font-bold">+ İsimli oda</button>
                    {pk.status !== "on_track" && pk.block_rooms - pk.picked_rooms > 1 && (
                      <button onClick={() => releaseRooms(r)} data-testid={`gs-release-${r.id}`}
                        className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-[10px] font-bold">Dolmayanları satışa aç</button>
                    )}
                    {(pk.rooming_list || []).slice(-5).map((e) => (
                      <span key={e.id} className="text-[10px] px-2 py-0.5 rounded-full bg-white border border-stone-200 text-stone-600">{e.guest_name}</span>
                    ))}
                  </div>
                </div>
              ); })()}
              {(r.versions || []).length > 0 && (
                <div className="mt-3 space-y-1.5" data-testid={`gs-versions-${r.id}`}>
                  {r.versions.slice().reverse().map((v) => (
                    <div key={v.v} className="flex items-center gap-3 text-[11px] bg-stone-50 rounded-lg px-3 py-2 flex-wrap">
                      <span className="font-black text-stone-700">v{v.v}</span>
                      <span>{v.offered_rate}/gece · {v.expected_rooms} net oda ({v.nights}g)</span>
                      <span className="text-stone-500">Düz. gelir {v.adj_group_revenue}</span>
                      <span className={`font-bold ${v.recommendation === "accept" ? "text-emerald-600" : v.recommendation === "negotiate" ? "text-amber-600" : "text-rose-600"}`}>
                        {REC_TR[v.recommendation]} · net {v.net_value_after_commission} · min {v.suggested_min_rate_net}
                      </span>
                      <button onClick={() => pdf(v.analysis_id, r.group_name.replace(/\s+/g, "-"))} data-testid={`gs-pdf-${r.id}-${v.v}`}
                        className="ml-auto flex items-center gap-1 text-teal-700 hover:text-teal-500 font-bold">
                        <FilePdf size={13} weight="fill" /> PDF
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
