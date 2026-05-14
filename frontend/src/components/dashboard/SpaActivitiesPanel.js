import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { SpinnerGap, Plus, X, Calendar, Clock } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/spa`;

const TABS = [
  { id: "schedule", label: "Bugünkü Program" },
  { id: "services", label: "Hizmetler" },
  { id: "providers", label: "Personel" },
];

export default function SpaActivitiesPanel({ propertyId = "all" }) {
  const [tab, setTab] = useState("schedule");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [form, setForm] = useState({});

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      let url;
      if (tab === "schedule") url = `${API}/schedule?date=${date}`;
      else if (tab === "services") url = `${API}/services?property_id=${propertyId}`;
      else url = `${API}/providers?property_id=${propertyId}`;
      const r = await axios.get(url, { withCredentials: true });
      setData(r.data);
    } catch (e) { toast.error("Yüklenemedi"); }
    finally { setLoading(false); }
  }, [tab, propertyId, date]);

  useEffect(() => { reload(); }, [reload]);

  async function create() {
    try {
      if (tab === "services") {
        await axios.post(`${API}/services`, {
          name: form.name, category: form.category || "spa",
          duration_minutes: Number(form.duration_minutes || 60),
          price: Number(form.price || 0),
          property_id: propertyId,
        }, { withCredentials: true });
      } else if (tab === "providers") {
        await axios.post(`${API}/providers`, {
          name: form.name, role: form.role || "therapist",
          property_id: propertyId,
        }, { withCredentials: true });
      }
      toast.success("Eklendi");
      setShowCreate(false); setForm({}); reload();
    } catch (e) { toast.error("Eklenemedi"); }
  }

  const items = tab === "services" ? (data?.services || []) : tab === "providers" ? (data?.providers || []) : (data?.bookings || []);

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="spa-panel">
      <div className="mb-4">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <SpinnerGap size={12} weight="fill" className="text-pink-500" />
          <span>Wellness & Activities</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">Spa & Aktivite Rezervasyonu</h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Hizmet kataloğu, terapist çizelgesi ve otomatik zaman dilimi tahsisi — günlük çakışmalar otomatik engellenir.
        </p>
      </div>

      <div className="flex gap-1 mb-4 border-b border-stone-200 items-end">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} data-testid={`spa-tab-${t.id}`}
                  className={`px-4 py-2 text-xs font-medium border-b-2 ${tab === t.id ? "border-stone-900 text-stone-900" : "border-transparent text-stone-500"}`}>
            {t.label}
          </button>
        ))}
        {tab === "schedule" && (
          <input type="date" value={date} onChange={e => setDate(e.target.value)}
                 className="ml-auto text-xs px-2 py-1 border border-stone-300 rounded mb-1" data-testid="spa-date" />
        )}
        {tab !== "schedule" && (
          <button onClick={() => setShowCreate(true)} data-testid="spa-create-btn"
                  className="ml-auto px-3 py-1.5 text-xs text-white bg-stone-900 rounded-lg inline-flex items-center gap-1.5 mb-1">
            <Plus size={13} /> Ekle
          </button>
        )}
      </div>

      {loading && <div className="text-center py-12 text-stone-400 text-sm">Yükleniyor…</div>}

      {!loading && tab === "schedule" && (
        <div className="bg-white border border-stone-200 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm text-stone-600 inline-flex items-center gap-1.5">
              <Calendar size={14} /> {date} programı · {items.length} rezervasyon
            </div>
            <div className="text-sm font-semibold">£{(data?.total_revenue || 0).toFixed(2)} ciro</div>
          </div>
          {items.length === 0 ? (
            <div className="text-center py-8 text-stone-400 text-xs" data-testid="spa-empty">Bu gün için rezervasyon yok.</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="text-[11px] uppercase tracking-wider text-stone-500">
                <tr><th className="px-3 py-2 text-left">Saat</th><th className="px-3 py-2 text-left">Misafir</th><th className="px-3 py-2 text-left">Hizmet</th><th className="px-3 py-2 text-left">Süre</th><th className="px-3 py-2 text-left">Fiyat</th></tr>
              </thead>
              <tbody>
                {items.map(b => (
                  <tr key={b.id} className="border-t border-stone-100" data-testid={`spa-booking-${b.id}`}>
                    <td className="px-3 py-2 inline-flex items-center gap-1"><Clock size={12} className="text-stone-400" />{new Date(b.start_at).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}</td>
                    <td className="px-3 py-2">{b.guest_name}</td>
                    <td className="px-3 py-2 text-xs text-stone-600">{b.service_name}</td>
                    <td className="px-3 py-2 text-xs">{b.duration_minutes} dk</td>
                    <td className="px-3 py-2">£{Number(b.price || 0).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {!loading && tab !== "schedule" && (
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
          {items.length === 0 ? (
            <div className="text-center py-12 text-stone-400 text-sm" data-testid="spa-empty">Henüz kayıt yok.</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
                <tr>{tab === "services"
                  ? (<><th className="px-4 py-2 text-left">Ad</th><th className="px-4 py-2 text-left">Kategori</th><th className="px-4 py-2 text-left">Süre</th><th className="px-4 py-2 text-left">Fiyat</th></>)
                  : (<><th className="px-4 py-2 text-left">Ad</th><th className="px-4 py-2 text-left">Rol</th><th className="px-4 py-2 text-left">Durum</th></>)}
                </tr>
              </thead>
              <tbody>
                {items.map(it => (
                  <tr key={it.id} className="border-t border-stone-100" data-testid={`spa-item-${it.id}`}>
                    <td className="px-4 py-2 font-medium">{it.name}</td>
                    {tab === "services" ? (
                      <>
                        <td className="px-4 py-2 text-xs">{it.category}</td>
                        <td className="px-4 py-2 text-xs">{it.duration_minutes} dk</td>
                        <td className="px-4 py-2">£{Number(it.price || 0).toFixed(2)}</td>
                      </>
                    ) : (
                      <>
                        <td className="px-4 py-2 text-xs">{it.role}</td>
                        <td className="px-4 py-2 text-xs">{it.active ? <span className="text-emerald-600">Aktif</span> : "Pasif"}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {showCreate && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setShowCreate(false)}>
          <div className="bg-white rounded-xl w-full max-w-md p-5" onClick={e => e.stopPropagation()} data-testid="spa-create-modal">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold">{tab === "services" ? "Yeni Hizmet" : "Yeni Personel"}</h3>
              <button onClick={() => setShowCreate(false)}><X size={16} /></button>
            </div>
            <div className="space-y-3">
              <input placeholder="Ad" value={form.name || ""} onChange={e => setForm({ ...form, name: e.target.value })}
                     className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" data-testid="spa-form-name" />
              {tab === "services" && (<>
                <select value={form.category || "spa"} onChange={e => setForm({ ...form, category: e.target.value })}
                        className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg">
                  <option value="spa">Spa</option><option value="activity">Aktivite</option>
                  <option value="fitness">Fitness</option><option value="tour">Tur</option>
                </select>
                <input type="number" placeholder="Süre (dakika)" value={form.duration_minutes || ""} onChange={e => setForm({ ...form, duration_minutes: e.target.value })}
                       className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" />
                <input type="number" placeholder="Fiyat" value={form.price || ""} onChange={e => setForm({ ...form, price: e.target.value })}
                       className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" />
              </>)}
              {tab === "providers" && (
                <input placeholder="Rol (örn. terapist)" value={form.role || ""} onChange={e => setForm({ ...form, role: e.target.value })}
                       className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" />
              )}
              <button onClick={create} disabled={!form.name} data-testid="spa-form-save"
                      className="w-full py-2 text-sm text-white bg-stone-900 rounded-lg disabled:opacity-50">
                Kaydet
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
