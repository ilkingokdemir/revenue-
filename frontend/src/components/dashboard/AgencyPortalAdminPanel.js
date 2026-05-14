/**
 * AgencyPortalAdminPanel — admin/manager UI for managing TÜRSAB agencies
 * and their contract rates.
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Briefcase, Plus, Key, Trash, Receipt, X } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function AgencyPortalAdminPanel() {
  const [tab, setTab] = useState("agencies");
  const [agencies, setAgencies] = useState([]);
  const [contracts, setContracts] = useState([]);
  const [properties, setProperties] = useState([]);
  const [roomTypes, setRoomTypes] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [showContract, setShowContract] = useState(false);
  const [form, setForm] = useState({ default_commission_percent: 10, payment_terms: "Net 30", country: "TR" });
  const [cForm, setCForm] = useState({ contract_rate: 0, currency: "TRY", commission_percent: 10, min_stay: 1, max_stay: 30 });
  const [promoType, setPromoType] = useState("");

  const reload = useCallback(async () => {
    try {
      const [a, c, p, rt] = await Promise.all([
        axios.get(`${API}/agencies`, { withCredentials: true }),
        axios.get(`${API}/agency-contracts`, { withCredentials: true }),
        axios.get(`${API}/properties`, { withCredentials: true }),
        axios.get(`${API}/room-types`, { withCredentials: true }),
      ]);
      setAgencies(a.data.items || []);
      setContracts(c.data.items || []);
      setProperties(p.data.properties || p.data.items || p.data || []);
      setRoomTypes(rt.data.room_types || rt.data.items || rt.data || []);
    } catch (e) { toast.error("Yüklenemedi"); }
  }, []);

  useEffect(() => { reload(); }, [reload]);

  const propName = (id) => properties.find(p => p.id === id)?.name || id;
  const rtName = (id) => id ? (roomTypes.find(r => r.id === id)?.name || id) : "Tüm odalar";
  const agName = (id) => agencies.find(a => a.id === id)?.name || id;

  async function create() {
    if (!form.name || !form.email) { toast.error("Ad ve e-posta gerekli"); return; }
    try {
      await axios.post(`${API}/agencies`, form, { withCredentials: true });
      toast.success("Acenta eklendi");
      setShowCreate(false); setForm({ default_commission_percent: 10, payment_terms: "Net 30", country: "TR" });
      reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Eklenemedi"); }
  }

  async function resetPin(id) {
    if (!window.confirm("Bu acenta için yeni PIN oluşturulsun mu?")) return;
    try {
      const r = await axios.post(`${API}/agencies/${id}/set-credentials`, { generate: true }, { withCredentials: true });
      window.prompt("✅ PIN oluşturuldu. Acentaya güvenli kanal üzerinden iletin:", r.data.pin);
    } catch (e) { toast.error(e?.response?.data?.detail || "PIN oluşturulamadı"); }
  }

  async function saveContract() {
    if (!cForm.agency_id || !cForm.property_id || !cForm.contract_rate) {
      toast.error("Acenta, mülk ve fiyat gerekli"); return;
    }
    const payload = {...cForm};
    if (promoType === "stay_pay") {
      payload.promotion = { type: "stay_pay", stay: parseInt(cForm.promo_stay)||7, pay: parseInt(cForm.promo_pay)||6 };
    } else if (promoType === "early_bird") {
      payload.promotion = { type: "early_bird", days_ahead: parseInt(cForm.promo_days)||30, discount_percent: parseFloat(cForm.promo_disc)||10 };
    }
    try {
      await axios.post(`${API}/agency-contracts`, payload, { withCredentials: true });
      toast.success("Kontrat eklendi");
      setShowContract(false);
      setCForm({ contract_rate: 0, currency: "TRY", commission_percent: 10, min_stay: 1, max_stay: 30 });
      setPromoType("");
      reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Eklenemedi"); }
  }

  async function deleteContract(id) {
    if (!window.confirm("Bu kontrat silinsin mi?")) return;
    try {
      await axios.delete(`${API}/agency-contracts/${id}`, { withCredentials: true });
      toast.success("Silindi"); reload();
    } catch (e) { toast.error("Silinemedi"); }
  }

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="agency-portal-admin-panel">
      <div className="flex items-start justify-between gap-4 mb-5 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">TÜRSAB Distribution</div>
          <h2 className="text-2xl font-semibold text-stone-900 inline-flex items-center gap-2">
            <Briefcase size={22} weight="fill" className="text-sky-600" /> Acenta Portalı Yönetimi
          </h2>
          <p className="text-sm text-stone-500 mt-1">
            TÜRSAB üye acentaları, kontrat tarifeleri ve komisyon yönetimi · Acenta portalı: <code className="bg-stone-100 px-1.5 py-0.5 rounded">/agency</code>
          </p>
        </div>
        <div className="flex gap-2">
          {tab === "agencies" && (
            <button onClick={() => setShowCreate(true)} data-testid="agency-add-btn"
                    className="text-sm px-3 py-1.5 bg-stone-900 text-white rounded-lg inline-flex items-center gap-1.5 hover:bg-stone-800">
              <Plus size={13} weight="bold" /> Acenta Ekle
            </button>
          )}
          {tab === "contracts" && (
            <button onClick={() => setShowContract(true)} data-testid="contract-add-btn"
                    className="text-sm px-3 py-1.5 bg-stone-900 text-white rounded-lg inline-flex items-center gap-1.5 hover:bg-stone-800">
              <Plus size={13} weight="bold" /> Kontrat Ekle
            </button>
          )}
        </div>
      </div>

      <div className="flex gap-1 border-b border-stone-200 mb-4">
        {[{k:"agencies",label:"Acentalar"},{k:"contracts",label:"Kontratlar"}].map(t => (
          <button key={t.k} onClick={() => setTab(t.k)} data-testid={`agency-admin-tab-${t.k}`}
                  className={`px-3 py-2 text-xs font-medium border-b-2 ${tab===t.k ? "border-sky-600 text-sky-700" : "border-transparent text-stone-500"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "agencies" && (
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
              <tr>
                <th className="px-4 py-2 text-left">Acenta</th>
                <th className="px-4 py-2 text-left">TÜRSAB No</th>
                <th className="px-4 py-2 text-left">E-posta</th>
                <th className="px-4 py-2 text-left">Şehir</th>
                <th className="px-4 py-2 text-right">Komisyon</th>
                <th className="px-4 py-2 text-center">Login</th>
                <th className="px-4 py-2 text-right">PIN</th>
              </tr>
            </thead>
            <tbody>
              {agencies.map(a => (
                <tr key={a.id} className="border-t border-stone-100" data-testid={`agency-row-${a.id}`}>
                  <td className="px-4 py-2 font-medium">{a.name}</td>
                  <td className="px-4 py-2 font-mono text-xs">{a.tursab_no || "-"}</td>
                  <td className="px-4 py-2 text-xs">{a.email}</td>
                  <td className="px-4 py-2 text-xs">{a.city || "-"}</td>
                  <td className="px-4 py-2 text-right">%{a.default_commission_percent}</td>
                  <td className="px-4 py-2 text-center">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full ${a.login_enabled ? "bg-emerald-100 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>
                      {a.login_enabled ? "AKTİF" : "PASİF"}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button onClick={() => resetPin(a.id)} data-testid={`agency-pin-${a.id}`}
                            className="text-xs px-2 py-0.5 bg-amber-50 border border-amber-200 text-amber-700 rounded inline-flex items-center gap-1 hover:bg-amber-100">
                      <Key size={11} /> PIN
                    </button>
                  </td>
                </tr>
              ))}
              {agencies.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-stone-400 text-xs">Henüz acenta eklenmedi</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === "contracts" && (
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
              <tr>
                <th className="px-4 py-2 text-left">Acenta</th>
                <th className="px-4 py-2 text-left">Mülk / Oda</th>
                <th className="px-4 py-2 text-right">Fiyat</th>
                <th className="px-4 py-2 text-right">Komisyon</th>
                <th className="px-4 py-2 text-left">Geçerlilik</th>
                <th className="px-4 py-2 text-left">Promosyon</th>
                <th className="px-4 py-2 text-right">İşlem</th>
              </tr>
            </thead>
            <tbody>
              {contracts.map(c => (
                <tr key={c.id} className="border-t border-stone-100" data-testid={`contract-row-${c.id}`}>
                  <td className="px-4 py-2">{agName(c.agency_id)}</td>
                  <td className="px-4 py-2 text-xs">{propName(c.property_id)} · <span className="text-stone-500">{rtName(c.room_type_id)}</span></td>
                  <td className="px-4 py-2 text-right font-semibold">{c.contract_rate} {c.currency}</td>
                  <td className="px-4 py-2 text-right">%{c.commission_percent}</td>
                  <td className="px-4 py-2 text-xs">{c.valid_from || "-"} → {c.valid_to || "-"}</td>
                  <td className="px-4 py-2 text-xs">
                    {c.promotion?.type === "stay_pay" ? `${c.promotion.stay} yat ${c.promotion.pay} öde`
                      : c.promotion?.type === "early_bird" ? `${c.promotion.days_ahead}+gün -%${c.promotion.discount_percent}`
                      : "-"}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button onClick={() => deleteContract(c.id)} data-testid={`contract-delete-${c.id}`}
                            className="text-xs p-1 text-rose-600 hover:bg-rose-50 rounded">
                      <Trash size={13} />
                    </button>
                  </td>
                </tr>
              ))}
              {contracts.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-stone-400 text-xs">Henüz kontrat yok</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && (
        <Modal onClose={() => setShowCreate(false)} title="Yeni Acenta">
          <div className="space-y-2">
            <Inp label="Ad" v={form.name} onChange={v => setForm({...form, name:v})} testId="agency-form-name" />
            <Inp label="E-posta" v={form.email} onChange={v => setForm({...form, email:v})} testId="agency-form-email" />
            <Inp label="TÜRSAB No" v={form.tursab_no} onChange={v => setForm({...form, tursab_no:v})} />
            <Inp label="Telefon" v={form.phone} onChange={v => setForm({...form, phone:v})} />
            <Inp label="Şehir" v={form.city} onChange={v => setForm({...form, city:v})} />
            <Inp label="Varsayılan Komisyon %" v={form.default_commission_percent} type="number" onChange={v => setForm({...form, default_commission_percent:parseFloat(v)||10})} />
          </div>
          <div className="mt-4 flex gap-2 justify-end">
            <button onClick={() => setShowCreate(false)} className="text-xs px-3 py-1.5 border border-stone-300 rounded-lg">İptal</button>
            <button onClick={create} data-testid="agency-form-save" className="text-xs px-3 py-1.5 bg-stone-900 text-white rounded-lg">Kaydet</button>
          </div>
        </Modal>
      )}

      {showContract && (
        <Modal onClose={() => setShowContract(false)} title="Yeni Kontrat">
          <div className="space-y-2">
            <label className="block">
              <span className="text-xs text-stone-700">Acenta</span>
              <select value={cForm.agency_id||""} onChange={e => setCForm({...cForm, agency_id:e.target.value})}
                      className="w-full px-3 py-1.5 text-sm border border-stone-300 rounded-lg mt-1"
                      data-testid="contract-form-agency">
                <option value="">Seçin</option>
                {agencies.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-stone-700">Mülk</span>
              <select value={cForm.property_id||""} onChange={e => setCForm({...cForm, property_id:e.target.value})}
                      className="w-full px-3 py-1.5 text-sm border border-stone-300 rounded-lg mt-1"
                      data-testid="contract-form-property">
                <option value="">Seçin</option>
                {properties.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-stone-700">Oda Tipi (opsiyonel — boşsa tüm odalar)</span>
              <select value={cForm.room_type_id||""} onChange={e => setCForm({...cForm, room_type_id:e.target.value||null})}
                      className="w-full px-3 py-1.5 text-sm border border-stone-300 rounded-lg mt-1">
                <option value="">Tüm odalar</option>
                {roomTypes.filter(r => !cForm.property_id || r.property_id === cForm.property_id).map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </label>
            <div className="grid grid-cols-2 gap-2">
              <Inp label="Fiyat (gece)" v={cForm.contract_rate} type="number" onChange={v => setCForm({...cForm, contract_rate:parseFloat(v)||0})} testId="contract-form-rate" />
              <Inp label="Para Birimi" v={cForm.currency} onChange={v => setCForm({...cForm, currency:v})} />
              <Inp label="Komisyon %" v={cForm.commission_percent} type="number" onChange={v => setCForm({...cForm, commission_percent:parseFloat(v)||10})} />
              <Inp label="Min Gece" v={cForm.min_stay} type="number" onChange={v => setCForm({...cForm, min_stay:parseInt(v)||1})} />
              <Inp label="Maks Gece" v={cForm.max_stay} type="number" onChange={v => setCForm({...cForm, max_stay:parseInt(v)||30})} />
              <Inp label="Geçerli Başlangıç" v={cForm.valid_from} type="date" onChange={v => setCForm({...cForm, valid_from:v})} />
              <Inp label="Geçerli Bitiş" v={cForm.valid_to} type="date" onChange={v => setCForm({...cForm, valid_to:v})} />
            </div>
            <label className="block">
              <span className="text-xs text-stone-700">Promosyon Tipi</span>
              <select value={promoType} onChange={e => setPromoType(e.target.value)}
                      className="w-full px-3 py-1.5 text-sm border border-stone-300 rounded-lg mt-1">
                <option value="">Yok</option>
                <option value="stay_pay">N yat M öde (örn. 7 yat 6 öde)</option>
                <option value="early_bird">Erken Rezervasyon İndirimi</option>
              </select>
            </label>
            {promoType === "stay_pay" && (
              <div className="grid grid-cols-2 gap-2">
                <Inp label="Yat (N)" v={cForm.promo_stay||7} type="number" onChange={v => setCForm({...cForm, promo_stay:v})} />
                <Inp label="Öde (M)" v={cForm.promo_pay||6} type="number" onChange={v => setCForm({...cForm, promo_pay:v})} />
              </div>
            )}
            {promoType === "early_bird" && (
              <div className="grid grid-cols-2 gap-2">
                <Inp label="Min Gün Önce" v={cForm.promo_days||30} type="number" onChange={v => setCForm({...cForm, promo_days:v})} />
                <Inp label="İndirim %" v={cForm.promo_disc||10} type="number" onChange={v => setCForm({...cForm, promo_disc:v})} />
              </div>
            )}
          </div>
          <div className="mt-4 flex gap-2 justify-end">
            <button onClick={() => setShowContract(false)} className="text-xs px-3 py-1.5 border border-stone-300 rounded-lg">İptal</button>
            <button onClick={saveContract} data-testid="contract-form-save" className="text-xs px-3 py-1.5 bg-stone-900 text-white rounded-lg">Kaydet</button>
          </div>
        </Modal>
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

function Modal({ title, children, onClose }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-xl">
        <div className="flex items-center justify-between p-4 border-b border-stone-200">
          <h3 className="text-base font-semibold">{title}</h3>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-700"><X size={18} /></button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}
