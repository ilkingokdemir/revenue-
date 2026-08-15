/**
 * PublicEventsPanel — manage public event listings (Tripleseat Social SEO parity).
 *
 * Admin can:
 *  - List drafts + published events
 *  - Create new event from scratch or from a meeting
 *  - Publish / unpublish
 *  - Copy public URL
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Confetti, Plus, Globe, EyeSlash, Copy, Trash, FilmReel } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PublicEventsPanel({ propertyId }) {
  const [events, setEvents] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({
    title: "", date: "", start_time: "19:00", end_time: "23:00",
    description: "", capacity: 50, price_from: 0, tags: [],
    venue_name: "", distance_km: null,
  });
  const [estimating, setEstimating] = useState(false);

  async function estimateDistance() {
    if (!form.venue_name.trim()) { toast.error("Önce mekan adı girin"); return; }
    setEstimating(true);
    try {
      const r = await axios.post(`${API}/public-events/estimate-distance`,
        { venue_name: form.venue_name, property_id: propertyId }, { withCredentials: true });
      if (r.data.ok) {
        setForm((f) => ({ ...f, distance_km: r.data.distance_km }));
        toast.success(r.data.message);
      } else toast.error(r.data.message);
    } catch (e) { toast.error(e.response?.data?.detail || "Mesafe tahmin edilemedi"); } finally { setEstimating(false); }
  }
  const [tagInput, setTagInput] = useState("");

  const reload = useCallback(async () => {
    if (!propertyId) return;
    try {
      const r = await axios.get(`${API}/public-events?property_id=${propertyId}&include_drafts=true`, { withCredentials: true });
      setEvents(r.data.items || []);
    } catch (e) { toast.error("Yüklenemedi"); }
  }, [propertyId]);

  useEffect(() => { reload(); }, [reload]);

  async function create() {
    if (!form.title || !form.date) { toast.error("Başlık ve tarih gerekli"); return; }
    try {
      await axios.post(`${API}/public-events`, { ...form, property_id: propertyId }, { withCredentials: true });
      toast.success("Etkinlik oluşturuldu");
      setShowAdd(false);
      setForm({ title: "", date: "", start_time: "19:00", end_time: "23:00", description: "", capacity: 50, price_from: 0, tags: [], venue_name: "", distance_km: null });
      reload();
    } catch (e) { toast.error("Hata"); }
  }

  async function publish(id) {
    try {
      await axios.post(`${API}/public-events/${id}/publish`, {}, { withCredentials: true });
      toast.success("Yayımlandı 🎉"); reload();
    } catch (e) { toast.error("Yayımlanamadı"); }
  }

  async function unpublish(id) {
    try {
      await axios.post(`${API}/public-events/${id}/unpublish`, {}, { withCredentials: true });
      toast.success("Geri çekildi"); reload();
    } catch (e) { toast.error("Hata"); }
  }

  async function del(id) {
    if (!window.confirm("Sil?")) return;
    try {
      await axios.delete(`${API}/public-events/${id}`, { withCredentials: true });
      reload();
    } catch (e) { toast.error("Silinemedi"); }
  }

  async function generateVideo(id) {
    try {
      await axios.post(`${API}/marketing-videos/from-event/${id}`, {}, { withCredentials: true });
      toast.success("Video kuyruğa alındı 🎬 'Pazarlama Videoları' panelinden takip edin");
    } catch (e) { toast.error(e?.response?.data?.detail || "Video oluşturulamadı"); }
  }

  function copyUrl(slug) {
    const url = `${window.location.origin}/events/${slug}`;
    navigator.clipboard.writeText(url);
    toast.success("URL kopyalandı");
  }

  function addTag() {
    if (tagInput && !form.tags.includes(tagInput)) {
      setForm({...form, tags: [...form.tags, tagInput]});
      setTagInput("");
    }
  }

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="public-events-panel">
      <div className="flex items-start justify-between gap-4 mb-5 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">Tripleseat Social SEO</div>
          <h2 className="text-2xl font-semibold text-stone-900 inline-flex items-center gap-2">
            <Confetti size={22} weight="fill" className="text-rose-500" /> Halka Açık Etkinlikler
          </h2>
          <p className="text-sm text-stone-500 mt-1">
            Yayımlanan etkinlikler Google'a indekslenir (JSON-LD), <code>/events/&#123;slug&#125;</code> üzerinden herkese açık.
          </p>
        </div>
        <button onClick={() => setShowAdd(true)} data-testid="event-add-btn"
                className="text-sm px-3 py-1.5 bg-stone-900 text-white rounded-lg inline-flex items-center gap-1.5">
          <Plus size={13} /> Etkinlik Oluştur
        </button>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
        {events.map(e => (
          <div key={e.id} data-testid={`event-card-${e.id}`}
               className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            {e.hero_image && (
              <img src={e.hero_image} alt={e.title} className="w-full h-32 object-cover" />
            )}
            <div className="p-4">
              <div className="flex items-start justify-between mb-1">
                <h3 className="font-semibold text-stone-900">{e.title}</h3>
                <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                  e.is_public ? "bg-emerald-100 text-emerald-700" : "bg-stone-100 text-stone-500"
                }`}>{e.is_public ? "YAYIMDA" : "TASLAK"}</span>
              </div>
              <div className="text-xs text-stone-500">{e.date} · {e.start_time}-{e.end_time}</div>
              <p className="text-xs text-stone-600 mt-2 line-clamp-2">{e.description}</p>
              <div className="mt-2 flex flex-wrap gap-1">
                {(e.tags||[]).map(t => <span key={t} className="text-[10px] bg-stone-100 px-1.5 py-0.5 rounded">{t}</span>)}
              </div>
              <div className="flex items-center justify-between mt-3 pt-2 border-t border-stone-100">
                <div className="text-xs">
                  <div>{e.capacity} kişi · {e.price_from > 0 ? `${e.price_from} TL'den` : "Ücretsiz"}</div>
                  <div className="text-stone-400 text-[10px] font-mono">/events/{e.slug}</div>
                </div>
                <div className="flex gap-1">
                  {e.is_public ? (
                    <button onClick={() => unpublish(e.id)} data-testid={`event-unpub-${e.id}`}
                            title="Yayımdan Kaldır" className="p-1 text-stone-500 hover:bg-stone-100 rounded">
                      <EyeSlash size={13} />
                    </button>
                  ) : (
                    <button onClick={() => publish(e.id)} data-testid={`event-pub-${e.id}`}
                            title="Yayımla" className="p-1 text-emerald-600 hover:bg-emerald-50 rounded">
                      <Globe size={13} />
                    </button>
                  )}
                  <button onClick={() => generateVideo(e.id)} title="AI Video Üret"
                          data-testid={`event-video-${e.id}`}
                          className="p-1 text-fuchsia-600 hover:bg-fuchsia-50 rounded">
                    <FilmReel size={13} />
                  </button>
                  <button onClick={() => copyUrl(e.slug)} title="URL Kopyala"
                          className="p-1 text-sky-600 hover:bg-sky-50 rounded">
                    <Copy size={13} />
                  </button>
                  <button onClick={() => del(e.id)} title="Sil"
                          className="p-1 text-rose-600 hover:bg-rose-50 rounded">
                    <Trash size={13} />
                  </button>
                </div>
              </div>
            </div>
          </div>
        ))}
        {events.length === 0 && (
          <div className="col-span-full text-center py-12 text-stone-400 text-sm">
            Henüz etkinlik yok. Yeni etkinlik oluşturup yayımlayın — Google'da görünmesi için.
          </div>
        )}
      </div>

      {showAdd && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-xl">
            <div className="flex items-center justify-between p-4 border-b border-stone-200">
              <h3 className="text-base font-semibold">Yeni Etkinlik</h3>
              <button onClick={() => setShowAdd(false)} className="text-stone-400">✕</button>
            </div>
            <div className="p-4 space-y-2">
              <Inp label="Başlık" v={form.title} onChange={v => setForm({...form, title:v})} testId="event-title-input" />
              <div className="grid grid-cols-3 gap-2">
                <Inp label="Tarih" v={form.date} type="date" onChange={v => setForm({...form, date:v})} testId="event-date-input" />
                <Inp label="Başlangıç" v={form.start_time} type="time" onChange={v => setForm({...form, start_time:v})} />
                <Inp label="Bitiş" v={form.end_time} type="time" onChange={v => setForm({...form, end_time:v})} />
              </div>
              <label className="block">
                <span className="text-xs text-stone-700">Açıklama</span>
                <textarea value={form.description} rows={3}
                          onChange={e => setForm({...form, description:e.target.value})}
                          className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg mt-1" />
              </label>
              <Inp label="Görsel URL (Hero)" v={form.hero_image} onChange={v => setForm({...form, hero_image:v})} />
              <div className="grid grid-cols-2 gap-2">
                <Inp label="Kapasite" v={form.capacity} type="number" onChange={v => setForm({...form, capacity:parseInt(v)||50})} />
                <Inp label="Başlangıç Fiyatı (TL)" v={form.price_from} type="number" onChange={v => setForm({...form, price_from:parseFloat(v)||0})} />
              </div>
              <div className="grid grid-cols-[1fr_auto_90px] gap-2 items-end">
                <Inp label="Mekan Adı" v={form.venue_name} testId="event-venue-input" onChange={v => setForm({...form, venue_name:v})} />
                <button onClick={estimateDistance} disabled={estimating} data-testid="event-estimate-distance-btn"
                  className="h-9 px-2.5 rounded-lg bg-indigo-600 text-white text-[11px] font-bold disabled:opacity-50 whitespace-nowrap">
                  {estimating ? "..." : "📍 Mesafeyi Tahmin Et"}
                </button>
                <Inp label="Mesafe (km)" v={form.distance_km ?? ""} type="number" testId="event-distance-km-input" onChange={v => setForm({...form, distance_km: v === "" ? null : parseFloat(v)})} />
              </div>
              <Inp label="Bilet URL" v={form.ticket_url} onChange={v => setForm({...form, ticket_url:v})} />
              <label className="block">
                <span className="text-xs text-stone-700">Etiketler</span>
                <div className="flex gap-1 mt-1 flex-wrap mb-2">
                  {form.tags.map(t => (
                    <span key={t} className="text-[11px] bg-rose-100 text-rose-700 px-2 py-0.5 rounded inline-flex items-center gap-1">
                      {t}
                      <button onClick={() => setForm({...form, tags:form.tags.filter(x=>x!==t)})}>×</button>
                    </span>
                  ))}
                </div>
                <div className="flex gap-1">
                  <input value={tagInput} onChange={e => setTagInput(e.target.value)}
                         onKeyDown={e => e.key==="Enter" && (e.preventDefault(), addTag())}
                         placeholder="Etiket ekle..."
                         className="flex-1 px-2 py-1 text-xs border border-stone-300 rounded" />
                  <button onClick={addTag} className="text-xs px-2 py-1 bg-stone-100 rounded">+</button>
                </div>
              </label>
            </div>
            <div className="p-4 border-t border-stone-200 flex justify-end gap-2">
              <button onClick={() => setShowAdd(false)} className="text-xs px-3 py-1.5 border border-stone-300 rounded-lg">İptal</button>
              <button onClick={create} data-testid="event-save-btn" className="text-xs px-3 py-1.5 bg-stone-900 text-white rounded-lg">Oluştur (taslak)</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Inp({ label, v, onChange, type="text", testId }) {
  return (
    <label className="block">
      <span className="text-xs text-stone-700">{label}</span>
      <input value={v||""} type={type} onChange={e => onChange(e.target.value)}
             data-testid={testId}
             className="w-full px-3 py-1.5 text-sm border border-stone-300 rounded-lg mt-1" />
    </label>
  );
}
