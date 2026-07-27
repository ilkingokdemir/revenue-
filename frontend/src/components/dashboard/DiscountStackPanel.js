import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Tag, Plus, Trash, Calculator, ArrowRight, Phone, Clock, Star, CheckCircle } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/discount-stack`;

const LAYER_ICONS = { phone: Phone, last: Clock, genius: Star };
const iconFor = (name) => {
  const n = name.toLowerCase();
  if (n.includes("phone") || n.includes("telefon")) return Phone;
  if (n.includes("last") || n.includes("dakika")) return Clock;
  if (n.includes("genius") || n.includes("member") || n.includes("üye")) return Star;
  return Tag;
};

export default function DiscountStackPanel({ propertyId = "default" }) {
  const pid = propertyId === "all" ? "default" : propertyId;
  const [layers, setLayers] = useState([]);
  const [mode, setMode] = useState("multiplicative");
  const [newName, setNewName] = useState("");
  const [newPct, setNewPct] = useState("");
  const [targetNet, setTargetNet] = useState("79");
  const [calc, setCalc] = useState(null);
  const [dateStart, setDateStart] = useState("");
  const [dateEnd, setDateEnd] = useState("");
  const [applying, setApplying] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/${pid}`);
      setLayers(data.layers || []);
      setMode(data.stack_mode);
    } catch { toast.error("İndirim katmanları yüklenemedi"); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const addLayer = async () => {
    if (!newName || !newPct) { toast.error("Ad ve yüzde girin"); return; }
    try {
      await axios.post(`${API}/${pid}/layers`, { name: newName, pct: parseFloat(newPct) });
      setNewName(""); setNewPct("");
      toast.success("İndirim katmanı eklendi");
      load(); setCalc(null);
    } catch (e) { toast.error(e?.response?.data?.detail || "Eklenemedi"); }
  };

  const toggleLayer = async (l) => {
    try {
      await axios.put(`${API}/${pid}/layers/${l.id}`, { active: !l.active });
      load(); setCalc(null);
    } catch { toast.error("Güncellenemedi"); }
  };

  const delLayer = async (l) => {
    try {
      await axios.delete(`${API}/${pid}/layers/${l.id}`);
      toast.success("Silindi");
      load(); setCalc(null);
    } catch { toast.error("Silinemedi"); }
  };

  const setStackMode = async (m) => {
    try {
      await axios.put(`${API}/${pid}/config`, { stack_mode: m });
      setMode(m); setCalc(null);
      toast.success(m === "multiplicative" ? "Kademeli yığınlama (OTA standardı)" : "Toplamsal yığınlama");
    } catch { toast.error("Ayarlanamadı"); }
  };

  const calculate = async () => {
    if (!targetNet) return;
    try {
      const { data } = await axios.post(`${API}/${pid}/calculate`, { target_net: parseFloat(targetNet) });
      setCalc(data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Hesaplanamadı"); }
  };

  const apply = async () => {
    if (!calc || !dateStart) { toast.error("Önce hesaplayın ve başlangıç tarihi seçin"); return; }
    setApplying(true);
    try {
      const { data } = await axios.post(`${API}/${pid}/apply`, {
        target_net: parseFloat(targetNet), date_start: dateStart, date_end: dateEnd || dateStart,
      });
      toast.success(`${data.dates_updated} tarihe PMS Override £${data.gross_pms_override} yazıldı` +
        (data.guard_clamped ? ` · ${data.guard_clamped} tarih fiyat korumasına takıldı` : ""));
    } catch (e) { toast.error(e?.response?.data?.detail || "Uygulanamadı"); }
    finally { setApplying(false); }
  };

  return (
    <div className="space-y-5" data-testid="discount-stack-panel">
      <div className="relative bg-[#0A0F1C] rounded-2xl p-6 text-white overflow-hidden">
        <div className="absolute top-[-60px] right-[-40px] w-[240px] h-[240px] rounded-full bg-[#F97316]/20 blur-3xl" aria-hidden="true" />
        <div className="relative">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-amber-300 mb-1">
            <Tag size={15} weight="duotone" /> Revenue Management · Fiyat Kurgusu
          </div>
          <h2 className="text-2xl font-bold">İndirim Katmanları & Net Fiyat</h2>
          <p className="text-sm text-stone-400 mt-1 max-w-2xl">
            Müşterinin görmesini istediğiniz <b className="text-emerald-300">son satış fiyatını</b> girin;
            sistem aktif indirimleri (phone, last minute, Genius…) geriye doğru hesaplayıp
            <b className="text-blue-300"> PMS Override brüt fiyatını</b> bulur ve gönderir.
            OTA'da müşteri <b className="text-amber-300">"was £96 → £79"</b> görür.
          </p>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-5">
        {/* Katmanlar */}
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="discount-layers-card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-stone-800 flex items-center gap-2">
              <Tag size={16} className="text-[#F97316]" /> Aktif İndirim Katmanları
            </h3>
            <div className="flex gap-1">
              {[["multiplicative", "Kademeli (OTA)"], ["additive", "Toplamsal"]].map(([m, l]) => (
                <button key={m} onClick={() => setStackMode(m)} data-testid={`stack-mode-${m}`}
                  className={`px-2.5 py-1 rounded-lg text-[10px] font-bold border transition-colors ${mode === m ? "bg-stone-800 text-white border-stone-800" : "text-stone-500 border-stone-200 hover:border-stone-400"}`}>
                  {l}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-2 mb-4">
            {layers.length === 0 && (
              <p className="text-xs text-stone-400 py-4 text-center" data-testid="discount-layers-empty">
                Henüz indirim yok — örn. "Phone discount %10" ekleyin.
              </p>
            )}
            {layers.map((l) => {
              const Icon = iconFor(l.name);
              return (
                <div key={l.id} className={`flex items-center gap-3 border rounded-xl px-3 py-2.5 ${l.active ? "border-amber-200 bg-amber-50/50" : "border-stone-100 bg-stone-50 opacity-60"}`}
                  data-testid={`discount-layer-${l.id}`}>
                  <Icon size={16} className="text-[#F97316]" />
                  <span className="flex-1 text-sm font-bold text-stone-800">{l.name}</span>
                  <span className="text-sm font-black text-[#F97316] tabular-nums">-%{l.pct}</span>
                  <label className="flex items-center gap-1 text-[10px] text-stone-500 font-bold cursor-pointer">
                    <input type="checkbox" checked={l.active} onChange={() => toggleLayer(l)}
                      className="accent-[#F97316] w-3.5 h-3.5" data-testid={`discount-toggle-${l.id}`} />
                    aktif
                  </label>
                  <button onClick={() => delLayer(l)} data-testid={`discount-delete-${l.id}`}
                    className="p-1 rounded text-stone-300 hover:text-rose-500 transition-colors"><Trash size={13} /></button>
                </div>
              );
            })}
          </div>
          <div className="flex gap-2 pt-3 border-t border-stone-100">
            <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="örn. Phone discount"
              className="flex-1 rounded-lg border border-stone-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#F97316]/40"
              data-testid="discount-new-name" />
            <input type="number" min="1" max="89" value={newPct} onChange={(e) => setNewPct(e.target.value)} placeholder="%"
              className="w-20 rounded-lg border border-stone-200 px-3 py-2 text-sm text-right tabular-nums focus:outline-none focus:ring-2 focus:ring-[#F97316]/40"
              data-testid="discount-new-pct" />
            <button onClick={addLayer} data-testid="discount-add-btn"
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#F97316] hover:bg-[#EA580C] text-white text-xs font-bold transition-colors">
              <Plus size={13} weight="bold" /> Ekle
            </button>
          </div>
        </div>

        {/* Hesaplayıcı */}
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="discount-calculator-card">
          <h3 className="text-sm font-bold text-stone-800 flex items-center gap-2 mb-4">
            <Calculator size={16} className="text-[#1D4ED8]" /> Net Fiyat Hesaplayıcı
          </h3>
          <div className="flex items-end gap-3 mb-4">
            <div className="flex-1">
              <label className="block text-[10px] uppercase tracking-widest text-stone-400 font-bold mb-1">
                Müşterinin göreceği son fiyat (£)
              </label>
              <input type="number" min="1" value={targetNet} onChange={(e) => setTargetNet(e.target.value)}
                className="w-full rounded-lg border border-stone-200 px-3 py-2.5 text-lg font-black tabular-nums focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/40"
                data-testid="discount-target-net" />
            </div>
            <button onClick={calculate} data-testid="discount-calculate-btn"
              className="px-5 py-3 rounded-lg bg-gradient-to-r from-[#1D4ED8] to-[#06B6D4] text-white text-sm font-bold hover:from-[#1E40AF] hover:to-[#0891B2] transition-colors">
              Hesapla
            </button>
          </div>

          {calc && (
            <div className="space-y-3" data-testid="discount-calc-result">
              <div className="flex items-center justify-between bg-[#0A0F1C] rounded-xl px-4 py-3 text-white">
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">PMS Override (brüt)</div>
                  <div className="text-2xl font-black tabular-nums text-blue-300" data-testid="discount-gross">£{calc.gross_pms_override}</div>
                </div>
                <ArrowRight size={20} className="text-stone-500" />
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">Toplam indirim</div>
                  <div className="text-2xl font-black tabular-nums text-amber-300">-%{calc.total_discount_pct}</div>
                </div>
                <ArrowRight size={20} className="text-stone-500" />
                <div className="text-right">
                  <div className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">Müşteri görür</div>
                  <div className="text-2xl font-black tabular-nums text-emerald-300" data-testid="discount-net">£{calc.net_customer_price}</div>
                </div>
              </div>
              <div className="border border-stone-100 rounded-xl p-3">
                <div className="text-[10px] uppercase tracking-widest text-stone-400 font-bold mb-2">Adım adım indirim akışı</div>
                <div className="space-y-1" data-testid="discount-breakdown">
                  <div className="flex justify-between text-xs text-stone-600"><span>PMS Override</span><b className="tabular-nums">£{calc.gross_pms_override}</b></div>
                  {calc.breakdown.map((s, i) => (
                    <div key={i} className="flex justify-between text-xs text-stone-600">
                      <span>− {s.name} (%{s.pct})</span>
                      <span className="tabular-nums">-£{s.discount_amount} → <b>£{s.price_after}</b></span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 text-sm" data-testid="discount-ota-preview">
                <div className="text-[10px] uppercase tracking-widest text-blue-500 font-bold mb-1">Booking.com'da görünüm</div>
                <span className="line-through text-stone-400 mr-2">£{calc.ota_display.was}</span>
                <span className="font-black text-emerald-600 text-lg">£{calc.ota_display.now}</span>
                <span className="ml-2 text-[10px] font-bold text-rose-500 bg-rose-50 border border-rose-200 rounded px-1.5 py-0.5">-%{calc.total_discount_pct}</span>
              </div>
              <div className="flex items-end gap-2 pt-2 border-t border-stone-100">
                <div>
                  <label className="block text-[10px] uppercase tracking-widest text-stone-400 font-bold mb-1">Başlangıç</label>
                  <input type="date" value={dateStart} onChange={(e) => setDateStart(e.target.value)}
                    className="rounded-lg border border-stone-200 px-2.5 py-2 text-xs" data-testid="discount-date-start" />
                </div>
                <div>
                  <label className="block text-[10px] uppercase tracking-widest text-stone-400 font-bold mb-1">Bitiş</label>
                  <input type="date" value={dateEnd} onChange={(e) => setDateEnd(e.target.value)}
                    className="rounded-lg border border-stone-200 px-2.5 py-2 text-xs" data-testid="discount-date-end" />
                </div>
                <button onClick={apply} disabled={applying} data-testid="discount-apply-btn"
                  className="flex items-center gap-1.5 px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition-colors disabled:opacity-60">
                  <CheckCircle size={14} weight="bold" /> {applying ? "Uygulanıyor…" : "PMS Override olarak uygula"}
                </button>
              </div>
              <p className="text-[10px] text-stone-400">Fiyat koruma sınırları (min/maks) brüt fiyata otomatik uygulanır.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
