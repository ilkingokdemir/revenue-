import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const GenericSettings = ({ endpoint, title, subtitle, columns, formFields, testPrefix }) => {
  const [items, setItems] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({});

  const load = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/settings/${endpoint}`); setItems(data); } catch { /* silent */ }
  }, [endpoint]);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    try { await axios.post(`${API}/settings/${endpoint}`, form); toast.success("Created"); setShowCreate(false); setForm({}); load(); } catch { toast.error("Failed"); }
  };

  const del = async (id) => { try { await axios.delete(`${API}/settings/${endpoint}/${id}`); toast.success("Deleted"); load(); } catch { toast.error("Failed"); } };

  return (
    <div data-testid={`settings-${testPrefix}`}>
      <div className="flex items-center justify-between mb-5">
        <div><h3 className="text-base font-bold text-stone-800">{title}</h3><p className="text-xs text-stone-500">{subtitle}</p></div>
        <button onClick={() => { setForm({}); setShowCreate(true); }} className="px-3 py-1.5 bg-emerald-600 text-white rounded-lg text-xs font-medium" data-testid={`new-${testPrefix}-btn`}>+ Add</button>
      </div>
      {items.length === 0 ? <div className="text-center py-8 text-stone-400 text-sm">No items</div> : (
        <div className="border border-stone-200 rounded-xl overflow-hidden mb-6">
          <table className="w-full text-sm">
            <thead><tr className="bg-stone-50 border-b">
              {columns.map(c => <th key={c.key} className="px-4 py-2 text-left text-xs font-semibold text-stone-500 uppercase">{c.label}</th>)}
              <th className="px-4 py-2 text-right text-xs font-semibold text-stone-500 uppercase">Actions</th>
            </tr></thead>
            <tbody>{items.map(item => (
              <tr key={item.id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`${testPrefix}-row-${item.id}`}>
                {columns.map(c => <td key={c.key} className="px-4 py-2.5 text-stone-700">{c.render ? c.render(item[c.key], item) : (item[c.key] ?? "—")}</td>)}
                <td className="px-4 py-2.5 text-right"><button onClick={() => del(item.id)} className="text-xs text-red-500 hover:underline">Delete</button></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-sm" data-testid={`${testPrefix}-dialog`}><DialogHeader><DialogTitle>Add {title}</DialogTitle></DialogHeader>
          <div className="space-y-3 mt-2">
            {formFields.map(f => <div key={f.key}><label className="text-xs text-stone-500 mb-1 block">{f.label}</label>
              <Input type={f.type || "text"} value={form[f.key] || ""} onChange={e => setForm({...form, [f.key]: f.type === "number" ? parseFloat(e.target.value) || 0 : e.target.value})} placeholder={f.placeholder || f.label} data-testid={`${testPrefix}-${f.key}`} /></div>)}
            <button onClick={create} className="w-full py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid={`${testPrefix}-save`}>Create</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const badgeRender = (val) => val ? <Badge className="text-[10px] bg-emerald-50 text-emerald-600">{val}</Badge> : "—";

const DataCleanupSettings = () => {
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);

  const scan = async () => {
    try { const r = await axios.get(`${API}/data-cleanup/room-types/all`); setReport(r.data); }
    catch { toast.error("Tarama başarısız"); }
  };
  useEffect(() => { scan(); }, []);

  const merge = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/data-cleanup/room-types/all/merge`);
      toast.success(`${r.data.merged} mükerrer kayıt birleştirildi, ${r.data.references_remapped} referans taşındı`);
      scan();
    } catch { toast.error("Birleştirme başarısız"); } finally { setBusy(false); }
  };

  return (
    <div data-testid="settings-data-cleanup">
      <div className="mb-5"><h3 className="text-base font-bold text-stone-800">Veri Temizliği — Oda Tipleri</h3>
        <p className="text-xs text-stone-500">Aynı tesiste aynı isimli mükerrer oda tipi kayıtlarını güvenli birleştirir: en çok rezervasyon referanslı kayıt korunur, tüm referanslar (rezervasyon/oda/fiyat override/PMS eşleme) ona taşınır, işlem denetim loguna yazılır.</p></div>
      {!report ? <p className="text-sm text-stone-400">Taranıyor…</p> : report.clean ? (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-sm text-emerald-700 font-bold" data-testid="cleanup-clean-badge">
          ✓ Temiz — {report.total_room_types} oda tipi kaydında mükerrer bulunamadı
        </div>
      ) : (
        <div className="space-y-3">
          {report.duplicate_groups.map((g, i) => (
            <div key={i} className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs" data-testid={`cleanup-group-${i}`}>
              <b>{g.name}</b> ({g.property_id}) — korunacak: {g.keeper.id.slice(0, 8)} ({g.keeper.booking_refs} rezervasyon) · silinecek: {g.duplicates.length}
            </div>
          ))}
          <button onClick={merge} disabled={busy} className="px-4 py-2 bg-amber-600 text-white rounded-lg text-sm font-bold disabled:opacity-50" data-testid="cleanup-merge-btn">
            🧹 Güvenli Birleştir ({report.duplicate_groups.length} grup)
          </button>
        </div>
      )}
    </div>
  );
};

const BrandingSettings = () => {
  const [props, setProps] = useState([]);
  const [pid, setPid] = useState("");
  const [ver, setVer] = useState(0);
  const [hasLogo, setHasLogo] = useState(false);

  useEffect(() => {
    axios.get(`${API}/properties`).then(r => {
      const list = Array.isArray(r.data) ? r.data : r.data.properties || [];
      setProps(list);
      if (list[0]) setPid(list[0].id);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!pid) return;
    axios.get(`${API}/branding/logo/${pid}`, { responseType: "blob" })
      .then(() => setHasLogo(true)).catch(() => setHasLogo(false));
  }, [pid, ver]);

  const upload = (file) => {
    if (!file) return;
    if (file.size > 500 * 1024) { toast.error("Logo en fazla 500KB olabilir"); return; }
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const r = await axios.post(`${API}/branding/logo/${pid}`, { logo_b64: reader.result });
        toast.success(`Logo yüklendi (${r.data.size_kb}KB) — tüm PDF raporlarında kullanılacak`);
        setVer(v => v + 1);
      } catch (e) { toast.error(e.response?.data?.detail || "Yüklenemedi"); }
    };
    reader.readAsDataURL(file);
  };

  const removeLogo = async () => {
    try { await axios.delete(`${API}/branding/logo/${pid}`); toast.success("Logo kaldırıldı"); setVer(v => v + 1); }
    catch { toast.error("Kaldırılamadı"); }
  };

  return (
    <div data-testid="settings-branding">
      <div className="mb-5"><h3 className="text-base font-bold text-stone-800">Otel Logosu</h3>
        <p className="text-xs text-stone-500">Yüklenen logo tüm PDF raporlarında (yönetici özeti, haftalık rapor, tatbikat, gap analizi) otomatik kullanılır. PNG/JPEG/WebP, max 500KB.</p></div>
      <div className="flex flex-wrap items-center gap-4">
        <select value={pid} onChange={e => setPid(e.target.value)} data-testid="branding-property-select"
          className="border border-stone-300 rounded-lg px-3 py-2 text-sm">
          {props.map(p => <option key={p.id} value={p.id}>{p.name || p.id}</option>)}
        </select>
        <div className="w-28 h-28 border-2 border-dashed border-stone-300 rounded-xl flex items-center justify-center bg-stone-50 overflow-hidden" data-testid="branding-logo-preview">
          {hasLogo ? <img src={`${API}/branding/logo/${pid}?v=${ver}`} alt="logo" className="max-w-full max-h-full object-contain" />
            : <span className="text-[10px] text-stone-400 text-center px-2">Logo yüklenmedi</span>}
        </div>
        <div className="flex flex-col gap-2">
          <label className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium cursor-pointer text-center" data-testid="branding-upload-btn">
            {hasLogo ? "Logoyu Değiştir" : "Logo Yükle"}
            <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" data-testid="branding-file-input"
              onChange={e => { upload(e.target.files?.[0]); e.target.value = ""; }} />
          </label>
          {hasLogo && <button onClick={removeLogo} className="px-4 py-2 border border-rose-300 text-rose-600 rounded-lg text-sm font-medium" data-testid="branding-delete-btn">Kaldır</button>}
        </div>
      </div>
    </div>
  );
};

const settingsSections = [
  { id: "currencies", title: "Currencies", subtitle: "Manage supported currencies", endpoint: "currencies", testPrefix: "currency",
    columns: [{ key: "code", label: "Code" }, { key: "name", label: "Name" }, { key: "symbol", label: "Symbol" }, { key: "is_default", label: "Default", render: v => v ? <Badge className="text-[10px] bg-emerald-50 text-emerald-600">Default</Badge> : "" }],
    fields: [{ key: "code", label: "Code", placeholder: "GBP" }, { key: "name", label: "Name", placeholder: "British Pound" }, { key: "symbol", label: "Symbol", placeholder: "£" }] },
  { id: "room-categories", title: "Room Categories", subtitle: "Define room types", endpoint: "room-categories", testPrefix: "roomcat",
    columns: [{ key: "code", label: "Code" }, { key: "name", label: "Name" }, { key: "description", label: "Description" }],
    fields: [{ key: "code", label: "Code", placeholder: "STD" }, { key: "name", label: "Name", placeholder: "Standard" }, { key: "description", label: "Description" }] },
  { id: "booking-sources", title: "Booking Sources", subtitle: "Channel commission rates", endpoint: "booking-sources", testPrefix: "bksource",
    columns: [{ key: "code", label: "Code" }, { key: "name", label: "Name" }, { key: "commission_rate", label: "Commission %", render: v => `${v || 0}%` }, { key: "status", label: "Status", render: badgeRender }],
    fields: [{ key: "code", label: "Code", placeholder: "booking_com" }, { key: "name", label: "Name", placeholder: "Booking.com" }, { key: "commission_rate", label: "Commission %", type: "number" }] },
  { id: "expense-categories", title: "Expense Categories", subtitle: "Define expense classifications", endpoint: "expense-categories", testPrefix: "expcat",
    columns: [{ key: "code", label: "Code" }, { key: "name", label: "Name" }],
    fields: [{ key: "code", label: "Code", placeholder: "rent" }, { key: "name", label: "Name", placeholder: "Rent" }] },
  { id: "laundry-providers", title: "Laundry Providers", subtitle: "External laundry services", endpoint: "laundry-providers", testPrefix: "laundryprov",
    columns: [{ key: "name", label: "Name" }, { key: "contact", label: "Contact" }, { key: "phone", label: "Phone" }],
    fields: [{ key: "name", label: "Name" }, { key: "contact", label: "Contact Person" }, { key: "phone", label: "Phone" }, { key: "email", label: "Email" }] },
  { id: "document-types", title: "Booking Document Types", subtitle: "ID and document types for guests", endpoint: "document-types", testPrefix: "doctype",
    columns: [{ key: "name", label: "Name" }, { key: "code", label: "Code" }],
    fields: [{ key: "code", label: "Code", placeholder: "passport" }, { key: "name", label: "Name", placeholder: "Passport" }] },
];

export const SettingsHubPanel = () => {
  const [activeSection, setActiveSection] = useState("currencies");
  const [seeded, setSeeded] = useState(false);

  useEffect(() => {
    if (!seeded) { axios.get(`${API}/settings/seed-defaults`).catch(() => {}); setSeeded(true); }
  }, [seeded]);

  const section = settingsSections.find(s => s.id === activeSection);

  return (
    <div className="p-5" data-testid="settings-hub-panel">
      <div className="mb-6"><h2 className="text-lg font-bold text-stone-800">Settings</h2><p className="text-sm text-stone-500">System configuration and master data</p></div>
      <div className="flex gap-6">
        {/* Settings Sidebar */}
        <div className="w-48 flex-shrink-0">
          <nav className="space-y-1">
            {settingsSections.map(s => (
              <button key={s.id} onClick={() => setActiveSection(s.id)}
                className={`w-full text-left px-3 py-2 text-sm rounded-lg transition-colors ${activeSection === s.id ? "bg-emerald-50 text-emerald-700 font-medium" : "text-stone-500 hover:bg-stone-100"}`} data-testid={`settings-nav-${s.id}`}>
                {s.title}
              </button>
            ))}
            <button onClick={() => setActiveSection("branding")}
              className={`w-full text-left px-3 py-2 text-sm rounded-lg transition-colors ${activeSection === "branding" ? "bg-emerald-50 text-emerald-700 font-medium" : "text-stone-500 hover:bg-stone-100"}`} data-testid="settings-nav-branding">
              Hotel Logo (PDF)
            </button>
            <button onClick={() => setActiveSection("cleanup")}
              className={`w-full text-left px-3 py-2 text-sm rounded-lg transition-colors ${activeSection === "cleanup" ? "bg-emerald-50 text-emerald-700 font-medium" : "text-stone-500 hover:bg-stone-100"}`} data-testid="settings-nav-cleanup">
              Veri Temizliği
            </button>
          </nav>
        </div>
        {/* Settings Content */}
        <div className="flex-1">
          <AnimatePresence mode="wait">
            <motion.div key={activeSection} initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}>
              {activeSection === "branding" ? <BrandingSettings /> :
                activeSection === "cleanup" ? <DataCleanupSettings /> :
                section && <GenericSettings endpoint={section.endpoint} title={section.title} subtitle={section.subtitle} columns={section.columns} formFields={section.fields} testPrefix={section.testPrefix} />}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
};
