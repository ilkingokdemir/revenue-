import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Storefront, PaperPlaneTilt, ArrowsClockwise, CheckCircle } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS = {
  draft: { label: "Taslak", cls: "bg-stone-100 text-stone-600" },
  in_review: { label: "İncelemede", cls: "bg-amber-100 text-amber-700" },
  live: { label: "Canlı", cls: "bg-emerald-100 text-emerald-700" },
};
const STEPS = ["draft", "submitted", "in_review", "live"];
const STEP_LABELS = { draft: "Taslak", submitted: "Gönderildi", in_review: "İncelemede", live: "Canlı" };

export default function ChannelListingPanel({ activePropertyId, properties }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default");
  const [listings, setListings] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [form, setForm] = useState({ channel_id: "booking_com", description: "", address: "", policies: "", checkin_time: "14:00", checkout_time: "11:00" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/cm/listings/${pid}`);
      setListings(data.listings || []);
      setCatalog(data.catalog || []);
    } catch { toast.error("Yüklenemedi"); }
  }, [pid]);

  useEffect(() => { load(); }, [load]);

  const createDraft = async () => {
    if (!form.description.trim()) { toast.error("Tesis açıklaması zorunlu"); return; }
    setBusy(true);
    try {
      const { channel_id, ...content } = form;
      await axios.post(`${API}/cm/listings/${pid}`, { channel_id, content });
      toast.success("Taslak oluşturuldu — şimdi başvuruyu gönderin");
      setForm({ ...form, description: "" });
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Oluşturulamadı"); }
    setBusy(false);
  };

  const submit = async (lid) => {
    try {
      await axios.post(`${API}/cm/listings/${pid}/${lid}/submit`);
      toast.success("Başvuru gönderildi — inceleme ~1 dk sürer (mock)");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Gönderilemedi"); }
  };

  const stepIdx = (l) => {
    const done = new Set((l.timeline || []).map((t) => t.step));
    let idx = 0;
    STEPS.forEach((s, i) => { if (done.has(s)) idx = i; });
    return idx;
  };

  const inputCls = "w-full rounded-lg border border-stone-200 px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-cyan-600";

  return (
    <div className="p-6 max-w-4xl" data-testid="channel-listing-panel">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-stone-800">Kanal Listing Açma</h2>
          <p className="text-xs text-stone-500 mt-1">Express Connect tarzı — OTA listinglerinizi platform içinden açın. Canlı OTA API anahtarı gelene kadar başvuru akışı mock ilerler.</p>
        </div>
        <button onClick={load} data-testid="listings-refresh-btn"
          className="p-2 rounded-lg border border-stone-200 text-stone-500 hover:bg-stone-50"><ArrowsClockwise size={15} /></button>
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-5 shadow-sm mb-5" data-testid="listing-create-card">
        <div className="flex items-center gap-2 mb-3">
          <Storefront size={17} weight="bold" className="text-cyan-700" />
          <h3 className="text-sm font-bold text-stone-800">Yeni listing başvurusu</h3>
        </div>
        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <label className="text-[10px] font-bold uppercase text-stone-500">Kanal</label>
            <select value={form.channel_id} onChange={(e) => setForm({ ...form, channel_id: e.target.value })}
              className={inputCls} data-testid="listing-channel-select">
              {catalog.map((c) => <option key={c.channel_id} value={c.channel_id}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="text-[10px] font-bold uppercase text-stone-500">Adres</label>
            <input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })}
              placeholder="Cadde, şehir, ülke" className={inputCls} data-testid="listing-address-input" />
          </div>
          <div className="sm:col-span-2">
            <label className="text-[10px] font-bold uppercase text-stone-500">Tesis açıklaması *</label>
            <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={2} placeholder="Misafirlere görünecek tanıtım metni..." className={inputCls} data-testid="listing-desc-input" />
          </div>
          <div className="sm:col-span-2">
            <label className="text-[10px] font-bold uppercase text-stone-500">Politikalar</label>
            <input value={form.policies} onChange={(e) => setForm({ ...form, policies: e.target.value })}
              placeholder="İptal, evcil hayvan, sigara politikaları..." className={inputCls} data-testid="listing-policies-input" />
          </div>
          <div>
            <label className="text-[10px] font-bold uppercase text-stone-500">Check-in</label>
            <input value={form.checkin_time} onChange={(e) => setForm({ ...form, checkin_time: e.target.value })} className={inputCls} data-testid="listing-checkin-input" />
          </div>
          <div>
            <label className="text-[10px] font-bold uppercase text-stone-500">Check-out</label>
            <input value={form.checkout_time} onChange={(e) => setForm({ ...form, checkout_time: e.target.value })} className={inputCls} data-testid="listing-checkout-input" />
          </div>
        </div>
        <button onClick={createDraft} disabled={busy} data-testid="listing-create-btn"
          className="mt-3 px-4 py-2 rounded-lg bg-cyan-700 text-white text-xs font-bold hover:bg-cyan-800 disabled:opacity-50">
          Taslak Oluştur
        </button>
      </div>

      <div className="space-y-3" data-testid="listings-list">
        {listings.length === 0 && <p className="text-[11px] text-stone-400">Henüz listing başvurusu yok.</p>}
        {listings.map((l) => {
          const st = STATUS[l.status] || STATUS.draft;
          const idx = stepIdx(l);
          return (
            <div key={l.id} className="bg-white rounded-2xl border border-stone-200 p-4 shadow-sm" data-testid={`listing-card-${l.id}`}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm font-bold text-stone-800">{l.channel_name}</span>
                <span className={`text-[9px] font-black uppercase px-2 py-0.5 rounded-full ${st.cls}`} data-testid={`listing-status-${l.id}`}>{st.label}</span>
                <span className="text-[9px] font-bold text-amber-600 uppercase">Mock</span>
                <span className="flex-1" />
                {l.status === "draft" && (
                  <button onClick={() => submit(l.id)} data-testid={`listing-submit-${l.id}`}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-stone-900 text-white text-[10px] font-bold hover:bg-stone-700">
                    <PaperPlaneTilt size={11} weight="fill" /> Başvuruyu Gönder
                  </button>
                )}
              </div>
              <div className="flex items-center gap-0 mb-2">
                {STEPS.map((s, i) => (
                  <div key={s} className="flex items-center">
                    <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold ${
                      i <= idx ? "bg-cyan-700 text-white" : "bg-stone-100 text-stone-400"}`}>
                      {i <= idx && <CheckCircle size={10} weight="fill" />}{STEP_LABELS[s]}
                    </div>
                    {i < STEPS.length - 1 && <div className={`w-6 h-0.5 ${i < idx ? "bg-cyan-700" : "bg-stone-200"}`} />}
                  </div>
                ))}
              </div>
              <p className="text-[10px] text-stone-500 line-clamp-1">{l.content?.description}</p>
              <p className="text-[9px] text-stone-400 mt-1">{(l.timeline || []).slice(-1)[0]?.note}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
