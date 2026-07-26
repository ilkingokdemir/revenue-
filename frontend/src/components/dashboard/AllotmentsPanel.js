import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Buildings, Plus, ArrowsClockwise, Trash, CalendarBlank, X, Prohibit } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/allotments`;

export default function AllotmentsPanel({ propertyId = "all" }) {
  const [data, setData] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [openCal, setOpenCal] = useState(null);
  const [running, setRunning] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/${propertyId}`);
      setData(r.data);
    } catch { toast.error("Kontenjan kontratları yüklenemedi"); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  async function releaseRun() {
    setRunning(true);
    try {
      const r = await axios.post(`${API}/${propertyId}/release-run`);
      toast.success(`${r.data.rooms_released} oda serbest bırakıldı · ${r.data.ota_push_tasks || 0} OTA push kuyruklandı`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Release çalıştırılamadı"); }
    setRunning(false);
  }

  async function remove(c) {
    if (!window.confirm(`${c.operator_name} kontratı silinsin mi? Pickup kayıtları da silinir.`)) return;
    try {
      await axios.delete(`${API}/${c.property_id}/${c.id}`);
      toast.success("Kontrat silindi"); load();
    } catch { toast.error("Silinemedi"); }
  }

  if (!data) return <div className="p-8 text-center text-stone-400">Yükleniyor…</div>;
  const s = data.summary || {};

  return (
    <div className="p-5 max-w-[1200px] mx-auto space-y-4" data-testid="allotments-panel">
      <div className="bg-gradient-to-br from-stone-900 via-teal-950 to-cyan-900 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-teal-300">
              <Buildings size={14} /> Tour Operator Allotments
            </div>
            <h1 className="text-2xl font-bold mt-1">Tur Operatörü Kontenjanları</h1>
            <p className="text-sm text-stone-300 mt-1">Operatör kontratları, günlük kontenjan/pickup takibi, stop-sale ve release penceresinde otomatik serbest bırakma.</p>
          </div>
          <div className="flex gap-2">
            <button onClick={releaseRun} disabled={running} data-testid="allot-release-run-btn"
              className="px-4 py-2 bg-white/10 hover:bg-white/20 border border-white/20 rounded-lg text-sm font-semibold inline-flex items-center gap-2 disabled:opacity-60">
              <ArrowsClockwise size={16} className={running ? "animate-spin" : ""} />
              {running ? "Taranıyor…" : "Release Çalıştır"}
            </button>
            <button onClick={() => setShowForm(v => !v)} data-testid="allot-new-contract-btn"
              className="px-4 py-2 bg-teal-400 hover:bg-teal-300 text-stone-900 rounded-lg text-sm font-bold inline-flex items-center gap-2">
              <Plus size={16} /> Yeni Kontrat
            </button>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5">
          <Stat label="Aktif kontrat" value={s.active_contracts || 0} testid="allot-stat-active" />
          <Stat label="Genel pickup" value={`%${s.overall_pickup_pct || 0}`} testid="allot-stat-pickup" />
          <Stat label="Serbest bırakılan oda" value={s.rooms_released || 0} testid="allot-stat-released" />
          <Stat label="Operatör" value={s.operators || 0} testid="allot-stat-operators" />
        </div>
      </div>

      {showForm && <ContractForm propertyId={propertyId} onDone={() => { setShowForm(false); load(); }} />}

      <div className="space-y-3">
        {(data.contracts || []).map(c => (
          <ContractCard key={c.id} c={c} onDelete={() => remove(c)} onReload={load}
            open={openCal === c.id} onToggleCal={() => setOpenCal(openCal === c.id ? null : c.id)} />
        ))}
        {(!data.contracts || data.contracts.length === 0) && (
          <div className="bg-white border border-stone-200 rounded-xl px-4 py-12 text-center text-stone-400 text-sm">
            Henüz kontenjan kontratı yok. "Yeni Kontrat" ile tur operatörü anlaşması ekleyin.
          </div>
        )}
      </div>
    </div>
  );
}

function ContractCard({ c, onDelete, onReload, open, onToggleCal }) {
  const active = c.status === "active";
  const pct = Math.min(c.pickup_pct || 0, 100);
  return (
    <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid={`allot-contract-${c.id}`}>
      <div className="p-4 flex items-center gap-4 flex-wrap">
        <div className="min-w-[180px]">
          <div className="font-bold text-stone-800">{c.operator_name}</div>
          <div className="text-[11px] text-stone-400">{c.room_type} · {c.property_id}</div>
        </div>
        <div className="text-xs font-mono text-stone-500">{c.start_date} → {c.end_date}</div>
        <div className="text-xs text-stone-600">{c.daily_allotment} oda/gün · release {c.release_days}g</div>
        <div className="text-xs text-stone-600">{c.rate > 0 && `${c.rate} ${c.currency}`}</div>
        <div className="flex-1 min-w-[140px]">
          <div className="flex justify-between text-[10px] text-stone-400 mb-0.5">
            <span>Pickup {c.picked}/{c.total_room_nights}</span><span>%{c.pickup_pct}</span>
          </div>
          <div className="h-2 bg-stone-100 rounded-full overflow-hidden">
            <div className={`h-full rounded-full ${pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-amber-400" : "bg-rose-400"}`}
              style={{ width: `${pct}%` }} />
          </div>
        </div>
        <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${active ? "bg-emerald-50 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>
          {active ? "Aktif" : "Arşiv"}
        </span>
        <div className="flex gap-1">
          <button onClick={onToggleCal} data-testid={`allot-cal-btn-${c.id}`}
            className={`p-1.5 rounded-lg border ${open ? "bg-stone-900 text-white border-stone-900" : "text-stone-500 border-stone-200 hover:bg-stone-50"}`}>
            <CalendarBlank size={15} />
          </button>
          <button onClick={onDelete} className="p-1.5 text-stone-300 hover:text-rose-600" data-testid={`allot-delete-${c.id}`}>
            <Trash size={15} />
          </button>
        </div>
      </div>
      {open && <ContractCalendar c={c} onReload={onReload} />}
    </div>
  );
}

function ContractCalendar({ c, onReload }) {
  const [cal, setCal] = useState(null);
  const [pickup, setPickup] = useState(null);

  const loadCal = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/${c.property_id}/${c.id}/calendar?days=21`);
      setCal(r.data);
    } catch { toast.error("Takvim yüklenemedi"); }
  }, [c.property_id, c.id]);
  useEffect(() => { loadCal(); }, [loadCal]);

  async function toggleStop(ds) {
    try {
      const r = await axios.post(`${API}/${c.property_id}/${c.id}/stop-sale`, { date: ds });
      toast.success(r.data.stop_sale ? `${ds} stop-sale açıldı` : `${ds} stop-sale kaldırıldı`);
      loadCal(); onReload();
    } catch { toast.error("Stop-sale değiştirilemedi"); }
  }

  async function savePickup(e) {
    e.preventDefault();
    const f = e.target;
    try {
      const r = await axios.post(`${API}/${c.property_id}/${c.id}/pickup`, {
        date: pickup, rooms: parseInt(f.rooms.value || "1", 10),
        booking_ref: f.ref.value, guest_name: f.guest.value,
      });
      toast.success(`Pickup kaydedildi · kalan ${r.data.remaining_on_date} oda`);
      setPickup(null); loadCal(); onReload();
    } catch (err) { toast.error(err.response?.data?.detail || "Pickup kaydedilemedi"); }
  }

  if (!cal) return <div className="px-4 pb-4 text-xs text-stone-400">Takvim yükleniyor…</div>;
  return (
    <div className="border-t border-stone-100 p-4 bg-stone-50/60" data-testid={`allot-calendar-${c.id}`}>
      <div className="grid grid-cols-7 gap-1.5">
        {(cal.days || []).map(d => (
          <div key={d.date} data-testid={`allot-day-${c.id}-${d.date}`}
            className={`rounded-lg border p-1.5 text-center ${d.stop_sale ? "bg-rose-50 border-rose-200" : d.remaining === 0 ? "bg-stone-100 border-stone-200" : "bg-white border-stone-200"}`}>
            <div className="text-[10px] text-stone-400 font-mono">{d.date.slice(5)}</div>
            <div className="text-sm font-bold text-stone-800">{d.stop_sale ? "—" : `${d.remaining}`}</div>
            <div className="text-[9px] text-stone-400">P{d.picked}{d.released > 0 && ` R${d.released}`}</div>
            <div className="flex justify-center gap-0.5 mt-1">
              {!d.stop_sale && d.remaining > 0 && (
                <button onClick={() => setPickup(d.date)} title="Pickup ekle" data-testid={`allot-pickup-btn-${c.id}-${d.date}`}
                  className="p-0.5 text-teal-600 hover:bg-teal-50 rounded"><Plus size={11} /></button>
              )}
              <button onClick={() => toggleStop(d.date)} title={d.stop_sale ? "Stop-sale kaldır" : "Stop-sale"}
                data-testid={`allot-stop-btn-${c.id}-${d.date}`}
                className={`p-0.5 rounded ${d.stop_sale ? "text-rose-600 hover:bg-rose-100" : "text-stone-300 hover:text-rose-500 hover:bg-rose-50"}`}>
                <Prohibit size={11} />
              </button>
            </div>
          </div>
        ))}
      </div>
      <div className="text-[10px] text-stone-400 mt-2">Kutulardaki sayı = kalan kontenjan · P=pickup · R=release edilmiş · kırmızı = stop-sale</div>

      {pickup && (
        <form onSubmit={savePickup} className="mt-3 bg-white border border-teal-200 rounded-xl p-3 flex items-end gap-2 flex-wrap" data-testid="allot-pickup-form">
          <div className="text-xs font-semibold text-stone-700">Pickup — {pickup}</div>
          <label className="text-[10px] text-stone-400">Oda
            <input name="rooms" type="number" min="1" defaultValue="1" data-testid="allot-pickup-rooms"
              className="block w-16 border border-stone-200 rounded-lg px-2 py-1 text-sm" />
          </label>
          <label className="text-[10px] text-stone-400">Rezervasyon ref
            <input name="ref" placeholder="TUI-12345" data-testid="allot-pickup-ref"
              className="block w-32 border border-stone-200 rounded-lg px-2 py-1 text-sm" />
          </label>
          <label className="text-[10px] text-stone-400">Misafir
            <input name="guest" placeholder="opsiyonel" data-testid="allot-pickup-guest"
              className="block w-36 border border-stone-200 rounded-lg px-2 py-1 text-sm" />
          </label>
          <button type="submit" data-testid="allot-pickup-save"
            className="px-3 py-1.5 bg-teal-600 hover:bg-teal-500 text-white rounded-lg text-xs font-bold">Kaydet</button>
          <button type="button" onClick={() => setPickup(null)} className="p-1.5 text-stone-400 hover:text-stone-600"><X size={14} /></button>
        </form>
      )}
    </div>
  );
}

function ContractForm({ propertyId, onDone }) {
  const [saving, setSaving] = useState(false);
  async function submit(e) {
    e.preventDefault();
    const f = e.target;
    if (propertyId === "all" && !f.pid.value.trim()) { toast.error("Tesis ID girin"); return; }
    setSaving(true);
    try {
      await axios.post(`${API}/${propertyId === "all" ? f.pid.value.trim() : propertyId}`, {
        operator_name: f.operator.value, room_type: f.room_type.value,
        start_date: f.start.value, end_date: f.end.value,
        daily_allotment: parseInt(f.daily.value || "0", 10),
        release_days: parseInt(f.release.value || "7", 10),
        rate: parseFloat(f.rate.value || "0"), currency: f.currency.value,
        note: f.note.value,
      });
      toast.success("Kontrat oluşturuldu"); onDone();
    } catch (err) { toast.error(err.response?.data?.detail || "Kontrat oluşturulamadı"); }
    setSaving(false);
  }
  const inp = "border border-stone-200 rounded-lg px-2.5 py-1.5 text-sm w-full";
  const lbl = "text-[10px] uppercase tracking-wider text-stone-400";
  return (
    <form onSubmit={submit} className="bg-white border border-teal-200 rounded-xl p-4 grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="allot-contract-form">
      {propertyId === "all" && (
        <div><div className={lbl}>Tesis ID</div><input name="pid" className={inp} placeholder="prop-..." data-testid="allot-form-pid" /></div>
      )}
      <div><div className={lbl}>Operatör</div><input name="operator" required className={inp} placeholder="TUI / ETS / Jolly" data-testid="allot-form-operator" /></div>
      <div><div className={lbl}>Oda tipi</div><input name="room_type" required className={inp} placeholder="Standard Double" data-testid="allot-form-roomtype" /></div>
      <div><div className={lbl}>Başlangıç</div><input name="start" type="date" required className={inp} data-testid="allot-form-start" /></div>
      <div><div className={lbl}>Bitiş</div><input name="end" type="date" required className={inp} data-testid="allot-form-end" /></div>
      <div><div className={lbl}>Günlük kontenjan</div><input name="daily" type="number" min="1" defaultValue="5" required className={inp} data-testid="allot-form-daily" /></div>
      <div><div className={lbl}>Release (gün)</div><input name="release" type="number" min="0" defaultValue="7" className={inp} data-testid="allot-form-release" /></div>
      <div><div className={lbl}>Kontrat fiyatı</div><input name="rate" type="number" step="0.01" min="0" className={inp} placeholder="65.00" data-testid="allot-form-rate" /></div>
      <div><div className={lbl}>Para birimi</div>
        <select name="currency" className={inp} defaultValue="EUR" data-testid="allot-form-currency">
          <option>EUR</option><option>USD</option><option>GBP</option><option>TRY</option>
        </select>
      </div>
      <div className="col-span-2"><div className={lbl}>Not</div><input name="note" className={inp} placeholder="opsiyonel" data-testid="allot-form-note" /></div>
      <div className="flex items-end">
        <button type="submit" disabled={saving} data-testid="allot-form-save"
          className="px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white rounded-lg text-sm font-bold disabled:opacity-60">
          {saving ? "Kaydediliyor…" : "Kontratı Kaydet"}
        </button>
      </div>
    </form>
  );
}

function Stat({ label, value, testid }) {
  return (
    <div className="bg-white/10 rounded-xl p-3" data-testid={testid}>
      <div className="text-[10px] uppercase tracking-wider text-stone-300">{label}</div>
      <div className="text-xl font-bold mt-0.5">{value}</div>
    </div>
  );
}
