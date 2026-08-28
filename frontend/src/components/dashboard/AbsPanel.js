import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Bed, Plus, Trash, Sparkle } from "@phosphor-icons/react";
import { Loader2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function AbsPanel({ propertyId }) {
  const pid = propertyId && propertyId !== "all" ? propertyId : "default";
  const [attrs, setAttrs] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ name: "", price: "", description: "", image_url: "" });
  const [matrix, setMatrix] = useState(null); // { rooms, attributes }
  const [suggestions, setSuggestions] = useState(null);

  const loadSuggestions = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/abs/${pid}/price-suggestions`);
      setSuggestions(data);
    } catch { /* sessiz */ }
  }, [pid]);
  useEffect(() => { loadSuggestions(); }, [loadSuggestions]);

  const toggleAutoPricing = async () => {
    const next = !suggestions?.auto_pricing;
    try {
      await axios.put(`${API}/abs/${pid}/auto-pricing`, { enabled: next });
      toast.success(next ? "Otomatik fiyat modu AÇIK — robot 24 saatte bir uygulayacak" : "Otomatik fiyat modu kapatıldı");
      loadSuggestions();
    } catch { toast.error("Ayar kaydedilemedi"); }
  };

  const runAutoNow = async () => {
    try {
      const { data } = await axios.post(`${API}/abs/${pid}/auto-pricing/run`);
      toast.success(data.applied_count > 0 ? `${data.applied_count} fiyat güncellendi: ${data.applied.slice(0, 2).join(" · ")}` : "Değişiklik gerekmedi — fiyatlar doğru bantta");
      load();
      loadSuggestions();
    } catch { toast.error("Çalıştırılamadı"); }
  };

  const applySuggestion = async (s) => {
    try {
      const attr = attrs.find((a) => a.id === s.id);
      await axios.post(`${API}/abs/${pid}`, { ...attr, price: s.suggested_price });
      toast.success(`${s.name}: fiyat £${s.suggested_price} olarak güncellendi`);
      load();
      loadSuggestions();
    } catch { toast.error("Uygulanamadı"); }
  };

  const loadMatrix = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/abs/${pid}/room-matrix`);
      setMatrix(data);
    } catch { /* sessiz */ }
  }, [pid]);
  useEffect(() => { loadMatrix(); }, [loadMatrix]);

  const toggleRoomAttr = async (room, attrId) => {
    const cur = room.abs_attrs || [];
    const next = cur.includes(attrId) ? cur.filter((x) => x !== attrId) : [...cur, attrId];
    try {
      await axios.put(`${API}/abs/${pid}/room-attrs/${room.id}`, { attr_ids: next });
      setMatrix((m) => ({ ...m, rooms: m.rooms.map((r) => (r.id === room.id ? { ...r, abs_attrs: next } : r)) }));
    } catch { toast.error("Kaydedilemedi"); }
  };

  const autoSeedMatrix = async () => {
    try {
      const { data } = await axios.post(`${API}/abs/${pid}/room-attrs/auto-seed`);
      toast.success(`${data.rooms_mapped} odaya özellik dağıtıldı`);
      loadMatrix();
    } catch (e) { toast.error(e?.response?.data?.detail || "Dağıtım başarısız"); }
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/abs/${pid}`);
      setAttrs(data.attributes || []);
      setStats(data.stats || null);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const add = async () => {
    if (!form.name.trim()) return toast.error("Özellik adı gerekli");
    try {
      await axios.post(`${API}/abs/${pid}`, { ...form, price: parseFloat(form.price) || 0 });
      setForm({ name: "", price: "", description: "", image_url: "" });
      toast.success("Özellik eklendi");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Eklenemedi"); }
  };
  const toggle = async (a) => {
    await axios.post(`${API}/abs/${pid}`, { ...a, active: !a.active });
    load();
  };
  const remove = async (a) => {
    await axios.delete(`${API}/abs/${pid}/${a.id}`);
    toast.success("Pasifleştirildi");
    load();
  };
  const seed = async () => {
    try {
      await axios.post(`${API}/abs/${pid}/seed`);
      toast.success("Başlangıç seti yüklendi");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Seed başarısız"); }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5" data-testid="abs-panel">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2">
            <Bed size={22} weight="fill" className="text-sky-600" /> Özellik Bazlı Satış (ABS)
          </h1>
          <p className="text-sm text-stone-500 mt-0.5">
            Deniz manzarası, yüksek kat, balkon gibi oda özelliklerini gecelik ek ücretle satın.
            Misafir booking widget'ta seçer, tutar rezervasyona otomatik eklenir.
          </p>
        </div>
        {attrs.length === 0 && !loading && (
          <button onClick={seed} data-testid="abs-seed-btn"
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold">
            <Sparkle size={14} /> Başlangıç seti yükle
          </button>
        )}
      </div>

      {stats && (
        <div className="grid grid-cols-3 gap-3">
          <div className="p-4 rounded-2xl bg-sky-50 border border-sky-200" data-testid="abs-revenue-card">
            <div className="text-[10px] uppercase font-bold text-sky-600">ABS geliri (90g)</div>
            <div className="text-lg font-black text-sky-900">{stats.revenue_90d}</div>
          </div>
          <div className="p-4 rounded-2xl bg-white border border-stone-200" data-testid="abs-count-card">
            <div className="text-[10px] uppercase font-bold text-stone-400">Özellikli rezervasyon</div>
            <div className="text-lg font-black text-stone-900">{stats.bookings_with_abs}</div>
          </div>
          <div className="p-4 rounded-2xl bg-white border border-stone-200" data-testid="abs-top-card">
            <div className="text-[10px] uppercase font-bold text-stone-400">En popüler</div>
            <div className="text-lg font-black text-stone-900">{stats.top_attribute || "—"}</div>
          </div>
        </div>
      )}

      {/* Add form */}
      <div className="bg-white border border-stone-200 rounded-2xl p-4 grid grid-cols-2 md:grid-cols-6 gap-3 items-end">
        <div className="col-span-2">
          <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Özellik adı</label>
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="ör. Köşe oda" data-testid="abs-name-input"
            className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" />
        </div>
        <div>
          <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Fiyat / gece</label>
          <input type="number" min="0" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })}
            data-testid="abs-price-input" className="w-full border border-stone-200 rounded-lg px-2 py-2 text-sm" />
        </div>
        <div>
          <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Açıklama</label>
          <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
            data-testid="abs-desc-input" className="w-full border border-stone-200 rounded-lg px-2 py-2 text-sm" />
        </div>
        <div>
          <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Görsel URL</label>
          <input value={form.image_url} onChange={(e) => setForm({ ...form, image_url: e.target.value })}
            placeholder="https://..." data-testid="abs-image-input" className="w-full border border-stone-200 rounded-lg px-2 py-2 text-sm" />
        </div>
        <button onClick={add} data-testid="abs-add-btn"
          className="flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-xl bg-stone-900 hover:bg-stone-700 text-white text-xs font-bold">
          <Plus size={14} /> Ekle
        </button>
      </div>

      {/* List */}
      {loading ? (
        <div className="p-8 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-stone-400" /></div>
      ) : (
        <div className="bg-white border border-stone-200 rounded-2xl divide-y divide-stone-100" data-testid="abs-list">
          {attrs.length === 0 && <p className="p-6 text-sm text-stone-400 text-center">Henüz özellik yok — başlangıç setini yükleyin.</p>}
          {attrs.map((a) => (
            <div key={a.id} className="flex items-center gap-3 px-4 py-3" data-testid={`abs-row-${a.id}`}>
              {a.image_url ? (
                <img src={a.image_url} alt={a.name} className="w-12 h-12 rounded-lg object-cover flex-shrink-0" data-testid={`abs-img-${a.id}`} />
              ) : (
                <div className="w-12 h-12 rounded-lg bg-stone-100 flex items-center justify-center text-stone-300 flex-shrink-0"><Bed size={18} /></div>
              )}
              <div className="flex-1">
                <p className={`text-sm font-bold ${a.active ? "text-stone-900" : "text-stone-400 line-through"}`}>{a.name}</p>
                {a.description && <p className="text-[11px] text-stone-400">{a.description}</p>}
              </div>
              {stats?.attribute_counts?.[a.name] > 0 && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-sky-50 text-sky-700 font-bold">{stats.attribute_counts[a.name]} satış</span>
              )}
              <span className="text-sm font-black text-sky-700">+{a.price}/gece</span>
              <button onClick={() => toggle(a)} data-testid={`abs-toggle-${a.id}`}
                className={`px-2.5 py-1 rounded-full text-[10px] font-bold ${a.active ? "bg-emerald-100 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>
                {a.active ? "Aktif" : "Pasif"}
              </button>
              <button onClick={() => remove(a)} data-testid={`abs-delete-${a.id}`}
                className="text-stone-300 hover:text-rose-500"><Trash size={15} /></button>
            </div>
          ))}
        </div>
      )}

      {/* Robot Fiyat Önerileri */}
      {suggestions && suggestions.suggestions.length > 0 && (
        <div className="bg-white border border-stone-200 rounded-2xl p-4" data-testid="abs-price-suggestions">
          <div className="flex items-start justify-between gap-3 mb-1">
            <h2 className="text-sm font-black text-stone-800">🤖 Robot Fiyat Önerileri</h2>
            <div className="flex items-center gap-2">
              <button onClick={runAutoNow} data-testid="abs-auto-run-btn"
                className="text-[10px] font-bold text-stone-700 bg-white border border-stone-200 rounded-lg px-2.5 py-1.5 hover:bg-stone-50">Şimdi çalıştır</button>
              <button onClick={toggleAutoPricing} data-testid="abs-auto-toggle"
                className={`flex items-center gap-1.5 text-[10px] font-bold rounded-lg px-2.5 py-1.5 border transition-colors ${suggestions.auto_pricing ? "text-emerald-700 bg-emerald-50 border-emerald-300" : "text-stone-500 bg-white border-stone-200 hover:bg-stone-50"}`}>
                <span className={`w-2 h-2 rounded-full ${suggestions.auto_pricing ? "bg-emerald-500 animate-pulse" : "bg-stone-300"}`} />
                Otomatik mod {suggestions.auto_pricing ? "AÇIK" : "KAPALI"}
              </button>
            </div>
          </div>
          <p className="text-[11px] text-stone-500 mb-3">
            Son 90 gün · {suggestions.total_bookings_90d} rezervasyon · ADR £{suggestions.blended_adr_90d} · özellik tavanı £{suggestions.price_cap} (ADR'nin %15'i)
            {suggestions.last_auto_run && <span className="ml-2 text-emerald-600 font-semibold">Son otomatik koşu: {new Date(suggestions.last_auto_run).toLocaleString("tr-TR")}</span>}
          </p>
          <div className="space-y-2">
            {suggestions.suggestions.map((s) => (
              <div key={s.id} className="flex items-center gap-3 border border-stone-100 rounded-xl px-3 py-2" data-testid={`abs-suggestion-${s.id}`}>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-bold text-stone-800">{s.name}
                    <span className="ml-2 text-[10px] font-semibold text-stone-400">%{s.attach_rate_pct} dönüşüm · {s.sold_90d} satış</span>
                  </div>
                  <div className="text-[10px] text-stone-500">{s.reason_tr}</div>
                </div>
                <div className="text-xs font-black whitespace-nowrap">
                  £{s.current_price} →{" "}
                  <span className={s.action === "raise" ? "text-emerald-600" : s.action === "lower" ? "text-rose-600" : "text-stone-500"}>£{s.suggested_price}</span>
                </div>
                {s.action !== "keep" && (
                  <button onClick={() => applySuggestion(s)} data-testid={`abs-apply-suggestion-${s.id}`}
                    className="text-[10px] font-bold text-white bg-sky-600 hover:bg-sky-500 rounded-lg px-2.5 py-1.5">Uygula</button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Oda–Özellik Matrisi — ABS çekirdek: hangi oda hangi özelliğe sahip */}
      {matrix && matrix.attributes.length > 0 && (
        <div className="bg-white border border-stone-200 rounded-2xl p-4" data-testid="abs-room-matrix">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-sm font-black text-stone-800">Oda–Özellik Matrisi</h2>
              <p className="text-[11px] text-stone-500">Misafir bir özellik seçtiğinde sistem o özelliğe sahip <b>müsait</b> odayı otomatik atar ve garanti eder. Uygun oda kalmazsa satış engellenir.</p>
            </div>
            <button onClick={autoSeedMatrix} data-testid="abs-matrix-autoseed-btn"
              className="text-[10px] font-bold text-sky-700 bg-sky-50 border border-sky-200 rounded-lg px-2.5 py-1.5 hover:bg-sky-100">Otomatik dağıt (demo)</button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[10px] uppercase text-stone-400 border-b border-stone-100">
                  <th className="py-1.5 pr-2">Oda</th>
                  {matrix.attributes.map((a) => <th key={a.id} className="py-1.5 px-2 whitespace-nowrap">{a.name}</th>)}
                </tr>
              </thead>
              <tbody>
                {matrix.rooms.map((r) => (
                  <tr key={r.id} className="border-b border-stone-50" data-testid={`abs-matrix-row-${r.id}`}>
                    <td className="py-1.5 pr-2 font-semibold text-stone-800 whitespace-nowrap">{r.name}</td>
                    {matrix.attributes.map((a) => {
                      const on = (r.abs_attrs || []).includes(a.id);
                      return (
                        <td key={a.id} className="py-1.5 px-2">
                          <button onClick={() => toggleRoomAttr(r, a.id)} data-testid={`abs-matrix-${r.id}-${a.id}`}
                            className={`w-6 h-6 rounded-md border text-[11px] font-black transition-colors ${on ? "bg-sky-600 border-sky-600 text-white" : "bg-white border-stone-200 text-transparent hover:border-sky-300"}`}>
                            ✓
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
