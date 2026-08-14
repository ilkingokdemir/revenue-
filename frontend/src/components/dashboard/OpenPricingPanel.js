/**
 * OpenPricingPanel — Duetto-style segment × channel × room-type rate matrix.
 *
 * UI:
 *  - Property + date selector
 *  - Override table (segment / channel / room_type / rate / scope label)
 *  - Add override modal with optional segment/channel/room_type
 *  - Quick lookup: pick scope and see "current applicable rate"
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Stack, Plus, Trash, MagnifyingGlass } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function OpenPricingPanel({ propertyId }) {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [data, setData] = useState(null);
  const [segments, setSegments] = useState([]);
  const [channels, setChannels] = useState([]);
  const [roomTypes, setRoomTypes] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ rate: 0 });
  const [lookup, setLookup] = useState(null);
  const [lookupForm, setLookupForm] = useState({});

  const reload = useCallback(async () => {
    if (!propertyId) return;
    try {
      const m = await axios.get(`${API}/open-pricing/matrix/${propertyId}?date=${date}`, { withCredentials: true });
      setData(m.data);
      setSegments(m.data.segments || []);
      setChannels(m.data.channels || []);
      const rt = await axios.get(`${API}/room-types?property_id=${propertyId}`, { withCredentials: true });
      setRoomTypes(rt.data.room_types || rt.data.items || rt.data || []);
    } catch (e) { toast.error("Yüklenemedi"); }
  }, [propertyId, date]);

  useEffect(() => { reload(); }, [reload]);

  async function add() {
    if (!form.rate) { toast.error("Fiyat gerekli"); return; }
    try {
      await axios.post(`${API}/open-pricing/override`,
        { property_id: propertyId, date, ...form, rate: parseFloat(form.rate) },
        { withCredentials: true });
      toast.success("Override eklendi");
      setShowAdd(false); setForm({ rate: 0 });
      reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Eklenemedi"); }
  }

  async function delOverride(id) {
    if (!window.confirm("Silinsin mi?")) return;
    try {
      await axios.delete(`${API}/open-pricing/override/${id}`, { withCredentials: true });
      reload();
    } catch (e) { toast.error("Silinemedi"); }
  }

  async function doLookup() {
    try {
      const r = await axios.post(`${API}/open-pricing/lookup`,
        { property_id: propertyId, date, ...lookupForm }, { withCredentials: true });
      setLookup(r.data);
    } catch (e) { toast.error("Lookup başarısız"); }
  }

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="open-pricing-panel">
      <div className="flex items-start justify-between gap-4 mb-5 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">Duetto Open Pricing</div>
          <h2 className="text-2xl font-semibold text-stone-900 inline-flex items-center gap-2">
            <Stack size={22} weight="fill" className="text-fuchsia-600" /> Segment × Kanal × Oda Tarife Matrisi
          </h2>
          <p className="text-sm text-stone-500 mt-1">
            Çok boyutlu override: aynı tarihte segmente/kanala/oda tipine özel fiyatlar.
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <button onClick={async () => {
            try {
              const { data: r } = await axios.post(`${API}/open-pricing/optimize`, { property_id: propertyId, days: 14, apply: true }, { withCredentials: true });
              toast.success(`Optimizer: ${r.overrides_written} hücre fiyatı bağımsız üretildi ve uygulandı`);
              reload();
            } catch { toast.error("Optimizer çalıştırılamadı"); }
          }} data-testid="op-optimize-btn"
                  className="text-sm px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg inline-flex items-center gap-1.5">
            ⚡ Optimizer (14g)
          </button>
          <input type="date" value={date} onChange={e => setDate(e.target.value)}
                 data-testid="op-date-select"
                 className="px-3 py-1.5 text-sm border border-stone-300 rounded-lg bg-white" />
          <button onClick={() => setShowAdd(true)} data-testid="op-add-btn"
                  className="text-sm px-3 py-1.5 bg-stone-900 text-white rounded-lg inline-flex items-center gap-1.5">
            <Plus size={13} /> Override Ekle
          </button>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white border border-stone-200 rounded-xl overflow-hidden">
          <div className="px-4 py-2.5 border-b border-stone-200 text-sm font-semibold">
            {date} için aktif override ({data?.count || 0})
          </div>
          <table className="w-full text-sm">
            <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
              <tr>
                <th className="px-4 py-2 text-left">Kapsam</th>
                <th className="px-4 py-2 text-left">Segment</th>
                <th className="px-4 py-2 text-left">Kanal</th>
                <th className="px-4 py-2 text-left">Oda Tipi</th>
                <th className="px-4 py-2 text-right">Fiyat</th>
                <th className="px-4 py-2 text-right">İşlem</th>
              </tr>
            </thead>
            <tbody>
              {(data?.items || []).map(i => (
                <tr key={i.id} className="border-t border-stone-100" data-testid={`op-row-${i.id}`}>
                  <td className="px-4 py-2 text-xs">{i.scope_label}</td>
                  <td className="px-4 py-2 text-xs">{i.segment || "-"}</td>
                  <td className="px-4 py-2 text-xs">{i.channel || "-"}</td>
                  <td className="px-4 py-2 text-xs">{i.room_type_id || "-"}</td>
                  <td className="px-4 py-2 text-right font-semibold">{i.rate} £</td>
                  <td className="px-4 py-2 text-right">
                    <button onClick={() => delOverride(i.id)} data-testid={`op-del-${i.id}`}
                            className="text-xs p-1 text-rose-600 hover:bg-rose-50 rounded">
                      <Trash size={13} />
                    </button>
                  </td>
                </tr>
              ))}
              {(!data?.items || data.items.length === 0) && (
                <tr><td colSpan={6} className="px-4 py-10 text-center text-stone-400 text-xs">Bu tarih için override yok</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="bg-white border border-stone-200 rounded-xl p-4">
          <h3 className="text-sm font-semibold mb-2 inline-flex items-center gap-1.5">
            <MagnifyingGlass size={14} /> Tarife Lookup
          </h3>
          <p className="text-xs text-stone-500 mb-3">Bir kombinasyon için aktif fiyatı kontrol et.</p>
          <div className="space-y-2">
            <Sel label="Segment" v={lookupForm.segment} onChange={v => setLookupForm({...lookupForm, segment:v})} opts={segments} />
            <Sel label="Kanal" v={lookupForm.channel} onChange={v => setLookupForm({...lookupForm, channel:v})} opts={channels} />
            <Sel label="Oda Tipi" v={lookupForm.room_type_id} onChange={v => setLookupForm({...lookupForm, room_type_id:v})} opts={roomTypes.map(r=>({id:r.id, label:r.name}))} />
            <button onClick={doLookup} data-testid="op-lookup-btn"
                    className="w-full text-sm px-3 py-1.5 bg-stone-900 text-white rounded-lg">
              Lookup
            </button>
            {lookup && (
              <div className={`mt-2 p-2 rounded text-xs ${lookup.found ? "bg-emerald-50 text-emerald-800" : "bg-stone-50 text-stone-700"}`}
                   data-testid="op-lookup-result">
                {lookup.found ? <>✓ <b>£{lookup.rate}</b> — {lookup.source}</> : "Override bulunamadı (grid'e fallback)"}
              </div>
            )}
          </div>
        </div>
      </div>

      {showAdd && (
        <Modal title="Yeni Override" onClose={() => setShowAdd(false)}>
          <div className="space-y-2">
            <Sel label="Segment (opsiyonel)" v={form.segment} onChange={v => setForm({...form, segment:v})} opts={segments} />
            <Sel label="Kanal (opsiyonel)" v={form.channel} onChange={v => setForm({...form, channel:v})} opts={channels} />
            <Sel label="Oda Tipi (opsiyonel)" v={form.room_type_id} onChange={v => setForm({...form, room_type_id:v})} opts={roomTypes.map(r=>({id:r.id, label:r.name}))} />
            <label className="block">
              <span className="text-xs text-stone-700">Fiyat (£)</span>
              <input type="number" value={form.rate} data-testid="op-rate-input"
                     onChange={e => setForm({...form, rate:e.target.value})}
                     className="w-full px-3 py-1.5 text-sm border border-stone-300 rounded-lg mt-1" />
            </label>
            <label className="block">
              <span className="text-xs text-stone-700">Neden</span>
              <input value={form.reason||""} onChange={e => setForm({...form, reason:e.target.value})}
                     className="w-full px-3 py-1.5 text-sm border border-stone-300 rounded-lg mt-1" />
            </label>
          </div>
          <div className="mt-4 flex gap-2 justify-end">
            <button onClick={() => setShowAdd(false)} className="text-xs px-3 py-1.5 border border-stone-300 rounded-lg">İptal</button>
            <button onClick={add} data-testid="op-save-override" className="text-xs px-3 py-1.5 bg-stone-900 text-white rounded-lg">Kaydet</button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function Sel({ label, v, onChange, opts }) {
  return (
    <label className="block">
      <span className="text-xs text-stone-700">{label}</span>
      <select value={v||""} onChange={e => onChange(e.target.value||null)}
              className="w-full px-3 py-1.5 text-sm border border-stone-300 rounded-lg mt-1">
        <option value="">Tümü</option>
        {opts.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
      </select>
    </label>
  );
}

function Modal({ title, children, onClose }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl w-full max-w-md shadow-xl">
        <div className="flex items-center justify-between p-4 border-b border-stone-200">
          <h3 className="text-base font-semibold">{title}</h3>
          <button onClick={onClose} className="text-stone-400">✕</button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}
