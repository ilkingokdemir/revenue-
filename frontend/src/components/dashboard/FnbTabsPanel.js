import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ForkKnife,
  CoinVertical,
  ArrowsLeftRight,
  Plus,
  Trash,
  ArrowsClockwise,
  XCircle,
  Receipt,
  Door,
  CreditCard,
  Money,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

const OUTLETS = [
  ["bar", "Bar"],
  ["pool_bar", "Havuz Bar"],
  ["restaurant", "Restoran"],
  ["rooftop", "Rooftop"],
  ["spa", "Spa"],
  ["poolside", "Havuz Kenarı"],
  ["lounge", "Lounge"],
  ["in_room", "Oda Servisi"],
];
const OUTLET_LABEL = Object.fromEntries(OUTLETS);

const PAYMENT_METHODS = [
  ["cash", "Nakit", Money],
  ["card", "Kart", CreditCard],
  ["room_folio", "Oda Folyosu", Door],
  ["complimentary", "Komplimanter", null],
  ["voucher", "Voucher", null],
];

export default function FnbTabsPanel({ propertyId }) {
  const [tab, setTab] = useState("active");

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="fnb-tabs-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <ForkKnife size={12} weight="fill" className="text-orange-500" />
          <span>F&B · Outlet Tab Yönetimi</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">
          Tab Transfer & Folyo Aktarımı
        </h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Bar → Restoran → Oda. Outlets arası tab transferi + folyoya tek-tık otomatik fatura.
        </p>
      </div>

      <div className="flex gap-2 mb-5 border-b border-stone-200">
        <TabBtn active={tab === "active"} onClick={() => setTab("active")} testId="fnb-tab-active">
          <Receipt size={14} className="inline mr-1.5" />
          Açık Tab'lar
        </TabBtn>
        <TabBtn active={tab === "transfers"} onClick={() => setTab("transfers")} testId="fnb-tab-transfers">
          <ArrowsLeftRight size={14} className="inline mr-1.5" />
          Transfer Geçmişi
        </TabBtn>
        <TabBtn active={tab === "dashboard"} onClick={() => setTab("dashboard")} testId="fnb-tab-dashboard">
          <CoinVertical size={14} className="inline mr-1.5" />
          Bugün Özet
        </TabBtn>
      </div>

      {tab === "active" && <ActiveTabsView propertyId={propertyId} />}
      {tab === "transfers" && <TransfersView propertyId={propertyId} />}
      {tab === "dashboard" && <DashboardView propertyId={propertyId} />}
    </div>
  );
}

function TabBtn({ active, onClick, children, testId }) {
  return (
    <button onClick={onClick} data-testid={testId}
      className={`px-3.5 py-2 text-sm font-medium transition-all border-b-2 -mb-px ${
        active ? "border-orange-500 text-orange-700" : "border-transparent text-stone-500 hover:text-stone-800"
      }`}>
      {children}
    </button>
  );
}

function ActiveTabsView({ propertyId }) {
  const [rows, setRows] = useState([]);
  const [byOutlet, setByOutlet] = useState({});
  const [loading, setLoading] = useState(false);
  const [showOpen, setShowOpen] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [outletFilter, setOutletFilter] = useState("");

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const url = outletFilter
        ? `${API}/api/fnb/tabs/${propertyId}?outlet=${outletFilter}`
        : `${API}/api/fnb/tabs/${propertyId}`;
      const r = await axios.get(url, { withCredentials: true });
      setRows(r.data.rows || []);
      setByOutlet(r.data.by_outlet || {});
    } catch (e) {
      toast.error("Tab'lar yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId, outletFilter]);

  useEffect(() => { load(); }, [load]);

  if (selectedId) {
    return <TabDetail tabId={selectedId} onBack={() => { setSelectedId(null); load(); }} />;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={() => setOutletFilter("")}
          data-testid="fnb-outlet-all"
          className={`px-2.5 py-1 text-xs rounded-full border transition-all ${
            outletFilter === "" ? "bg-stone-900 text-white border-stone-900" : "bg-white text-stone-600 border-stone-200 hover:border-stone-400"
          }`}
        >
          Tümü ({rows.length})
        </button>
        {OUTLETS.map(([v, l]) => {
          const c = byOutlet[v]?.count || 0;
          if (c === 0 && outletFilter !== v) return null;
          return (
            <button
              key={v}
              onClick={() => setOutletFilter(v)}
              data-testid={`fnb-outlet-${v}`}
              className={`px-2.5 py-1 text-xs rounded-full border transition-all ${
                outletFilter === v ? "bg-orange-500 text-white border-orange-500" : "bg-white text-stone-600 border-stone-200 hover:border-stone-400"
              }`}
            >
              {l} {c > 0 && <span className="opacity-70">({c})</span>}
            </button>
          );
        })}
        <button onClick={load} className="ml-auto px-3 py-1 text-xs rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50 inline-flex items-center gap-1.5">
          <ArrowsClockwise size={12} /> Yenile
        </button>
        <button onClick={() => setShowOpen(true)} data-testid="fnb-open-btn" className="px-3 py-1 text-xs rounded-md bg-orange-500 text-white hover:bg-orange-600 inline-flex items-center gap-1.5">
          <Plus size={12} weight="bold" />
          Yeni Tab
        </button>
      </div>

      {showOpen && <OpenTabForm propertyId={propertyId} onCreated={(id) => { setShowOpen(false); load(); setSelectedId(id); }} onCancel={() => setShowOpen(false)} />}

      {loading && <div className="text-sm text-stone-400">Yükleniyor…</div>}

      {rows.length === 0 && !loading && (
        <div className="text-center py-12 text-stone-400 text-sm border border-dashed border-stone-200 rounded-lg">
          Açık tab yok. "Yeni Tab" ile başlatın.
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-3" data-testid="fnb-tabs-list">
        {rows.map((t) => (
          <div
            key={t.id}
            onClick={() => setSelectedId(t.id)}
            data-testid={`fnb-tab-row-${t.id}`}
            className="bg-white border border-stone-200 rounded-lg p-3.5 cursor-pointer hover:border-orange-300 hover:shadow-sm transition-all"
          >
            <div className="flex items-start justify-between mb-1">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-stone-900">{t.guest_name || "Walk-in"}</span>
                  <span className="px-1.5 py-0.5 text-[10px] rounded bg-orange-50 text-orange-700">
                    {OUTLET_LABEL[t.outlet] || t.outlet}
                  </span>
                  {t.transfer_history?.length > 1 && (
                    <span className="px-1.5 py-0.5 text-[10px] rounded bg-violet-50 text-violet-700 inline-flex items-center gap-0.5">
                      <ArrowsLeftRight size={9} />
                      {t.transfer_history.length - 1}
                    </span>
                  )}
                </div>
                <div className="text-[10px] text-stone-400 mt-0.5">
                  {t.ref} {t.table_number && `· Masa ${t.table_number}`} · {t.party_size} kişi
                </div>
              </div>
              <div className="text-right">
                <div className="text-lg font-bold text-stone-900">£{(t.total || 0).toFixed(2)}</div>
                <div className="text-[10px] text-stone-400">{t.items?.length || 0} kalem</div>
              </div>
            </div>
            {t.booking_id && (
              <div className="text-[10px] text-emerald-600 mt-1 inline-flex items-center gap-0.5">
                <Door size={10} weight="fill" /> Folyoya bağlanabilir
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function OpenTabForm({ propertyId, onCreated, onCancel }) {
  const [form, setForm] = useState({
    outlet: "bar",
    guest_name: "",
    booking_id: "",
    table_number: "",
    party_size: 2,
  });
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/fnb/tabs`, {
        ...form,
        property_id: propertyId,
        booking_id: form.booking_id || null,
        guest_name: form.guest_name || null,
      }, { withCredentials: true });
      toast.success(`Tab açıldı: ${r.data.ref}`);
      onCreated(r.data.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Açılamadı");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-stone-50 border border-stone-200 rounded-lg p-4 space-y-3" data-testid="fnb-open-form">
      <div className="text-sm font-semibold text-stone-800">Yeni Tab</div>
      <div className="grid md:grid-cols-2 gap-3">
        <div>
          <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">Outlet</label>
          <select value={form.outlet} onChange={(e) => setForm({ ...form, outlet: e.target.value })} data-testid="fnb-form-outlet" className="w-full px-3 py-2 text-sm border border-stone-200 rounded-md bg-white">
            {OUTLETS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <Input label="Misafir Adı" value={form.guest_name} onChange={(v) => setForm({ ...form, guest_name: v })} testId="fnb-form-guest" />
        <Input label="Masa No" value={form.table_number} onChange={(v) => setForm({ ...form, table_number: v })} testId="fnb-form-table" />
        <Input label="Kişi Sayısı" type="number" value={form.party_size} onChange={(v) => setForm({ ...form, party_size: parseInt(v) || 1 })} testId="fnb-form-party" />
        <Input label="Booking ID (opsiyonel — folyoya yazmak için)" value={form.booking_id} onChange={(v) => setForm({ ...form, booking_id: v })} testId="fnb-form-booking" className="md:col-span-2" />
      </div>
      <div className="flex gap-2 justify-end">
        <button onClick={onCancel} className="px-4 py-2 text-sm rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50">Vazgeç</button>
        <button onClick={submit} disabled={busy} data-testid="fnb-form-submit" className="px-4 py-2 text-sm rounded-md bg-orange-500 text-white hover:bg-orange-600 disabled:opacity-50">
          {busy ? "Açılıyor…" : "Tab Aç"}
        </button>
      </div>
    </div>
  );
}

function Input({ label, type = "text", value, onChange, testId, className = "" }) {
  return (
    <div className={className}>
      <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        data-testid={testId}
        className="w-full px-3 py-2 text-sm border border-stone-200 rounded-md focus:outline-none focus:border-orange-400"
      />
    </div>
  );
}

function TabDetail({ tabId, onBack }) {
  const [tab, setTab] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [showTransfer, setShowTransfer] = useState(false);
  const [showClose, setShowClose] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/fnb/tabs/detail/${tabId}`, { withCredentials: true });
      setTab(r.data);
    } catch (e) {
      toast.error("Tab yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [tabId]);

  useEffect(() => { load(); }, [load]);

  const removeItem = async (itemId) => {
    try {
      await axios.delete(`${API}/api/fnb/tabs/${tabId}/items/${itemId}`, { withCredentials: true });
      toast.success("Kaldırıldı");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Hata");
    }
  };

  if (loading || !tab) return <div className="text-sm text-stone-400">Yükleniyor…</div>;

  const isOpen = tab.status === "open";

  return (
    <div className="space-y-4" data-testid="fnb-tab-detail">
      <button onClick={onBack} data-testid="fnb-back-btn" className="text-xs text-stone-600 hover:text-stone-900">← Geri</button>

      <div className="bg-white border border-stone-200 rounded-lg p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className={`px-2 py-0.5 text-xs rounded font-medium ${
                tab.status === "open" ? "bg-emerald-100 text-emerald-700" :
                tab.status === "closed" ? "bg-stone-200 text-stone-600" :
                "bg-stone-100 text-stone-500"
              }`}>
                {tab.status === "open" ? "AÇIK" : "KAPALI"}
              </span>
              <span className="font-mono text-[10px] text-stone-400">{tab.ref}</span>
            </div>
            <div className="text-lg font-semibold text-stone-900">{tab.guest_name || "Walk-in"}</div>
            <div className="text-xs text-stone-600">
              {OUTLET_LABEL[tab.outlet]} {tab.table_number && `· Masa ${tab.table_number}`} · {tab.party_size} kişi
            </div>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold text-stone-900">£{(tab.total || 0).toFixed(2)}</div>
            <div className="text-[10px] text-stone-400">{tab.items?.length || 0} kalem</div>
          </div>
        </div>

        {isOpen && (
          <div className="flex gap-2 mt-3 pt-3 border-t border-stone-100 flex-wrap">
            <button onClick={() => setShowAdd(true)} data-testid="fnb-add-item-btn" className="px-3 py-1.5 text-xs rounded-md bg-orange-500 text-white hover:bg-orange-600 inline-flex items-center gap-1">
              <Plus size={12} weight="bold" /> Kalem Ekle
            </button>
            <button onClick={() => setShowTransfer(true)} data-testid="fnb-transfer-btn" className="px-3 py-1.5 text-xs rounded-md bg-violet-500 text-white hover:bg-violet-600 inline-flex items-center gap-1">
              <ArrowsLeftRight size={12} /> Outlet Transferi
            </button>
            <button onClick={() => setShowClose(true)} data-testid="fnb-close-btn" className="ml-auto px-3 py-1.5 text-xs rounded-md bg-stone-900 text-white hover:bg-stone-800 inline-flex items-center gap-1">
              <Receipt size={12} /> Kapat & Tahsil
            </button>
          </div>
        )}
      </div>

      {showAdd && <AddItemForm tabId={tabId} onAdded={() => { setShowAdd(false); load(); }} onCancel={() => setShowAdd(false)} />}
      {showTransfer && <TransferForm tabId={tabId} currentOutlet={tab.outlet} onTransferred={() => { setShowTransfer(false); load(); }} onCancel={() => setShowTransfer(false)} />}
      {showClose && <CloseForm tabId={tabId} hasBooking={!!tab.booking_id} subtotal={tab.subtotal} onClosed={() => { setShowClose(false); load(); }} onCancel={() => setShowClose(false)} />}

      {/* Items */}
      <div className="bg-white border border-stone-200 rounded-lg overflow-hidden" data-testid="fnb-items-list">
        <div className="bg-stone-50 px-3 py-2 text-[10px] uppercase tracking-wider text-stone-500 font-semibold">Kalemler</div>
        {tab.items?.length === 0 ? (
          <div className="p-8 text-center text-stone-400 text-sm">Henüz kalem yok.</div>
        ) : (
          tab.items.map((it) => (
            <div key={it.id} className="px-3 py-2 border-t border-stone-100 flex items-center gap-2">
              <span className="px-1 py-0.5 text-[9px] uppercase rounded bg-stone-100 text-stone-600 font-medium">{OUTLET_LABEL[it.outlet]?.slice(0, 4) || it.outlet?.slice(0, 4)}</span>
              <div className="flex-1 min-w-0">
                <div className="text-sm text-stone-900">{it.name} {it.qty > 1 && <span className="text-stone-400">x{it.qty}</span>}</div>
                {it.note && <div className="text-[11px] text-stone-500 italic">{it.note}</div>}
              </div>
              <div className="text-sm font-semibold text-stone-900">£{(it.line_total || 0).toFixed(2)}</div>
              {isOpen && (
                <button onClick={() => removeItem(it.id)} data-testid={`fnb-remove-${it.id}`} className="text-rose-400 hover:text-rose-600">
                  <Trash size={12} />
                </button>
              )}
            </div>
          ))
        )}
        {tab.items?.length > 0 && (
          <div className="px-3 py-2 border-t-2 border-stone-200 flex justify-between text-sm font-semibold bg-stone-50">
            <span>Ara Toplam</span>
            <span>£{(tab.subtotal || 0).toFixed(2)}</span>
          </div>
        )}
      </div>

      {/* Transfer history */}
      {tab.transfer_history?.length > 1 && (
        <div className="bg-violet-50 border border-violet-100 rounded-lg p-3" data-testid="fnb-transfer-history">
          <div className="text-[10px] uppercase tracking-wider text-violet-700 mb-2 font-semibold">Outlet Transfer Geçmişi</div>
          <div className="flex items-center gap-2 flex-wrap text-xs">
            {tab.transfer_history.map((h, i) => (
              <React.Fragment key={i}>
                {i > 0 && <ArrowsLeftRight size={10} className="text-violet-400" />}
                <span className="px-2 py-0.5 bg-white border border-violet-200 rounded text-violet-700">
                  {OUTLET_LABEL[h.outlet]}
                  <span className="text-violet-400 ml-1 text-[10px]">{h.at?.slice(11, 16)}</span>
                </span>
              </React.Fragment>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function AddItemForm({ tabId, onAdded, onCancel }) {
  const [item, setItem] = useState({ name: "", qty: 1, unit_price: 0, category: "beverage", note: "" });
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (!item.name.trim()) { toast.error("Ürün adı"); return; }
    setBusy(true);
    try {
      await axios.post(`${API}/api/fnb/tabs/${tabId}/items`, item, { withCredentials: true });
      toast.success("Eklendi");
      onAdded();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Hata");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="bg-stone-50 border border-stone-200 rounded-lg p-4 space-y-2" data-testid="fnb-add-form">
      <div className="text-sm font-semibold text-stone-800">Kalem Ekle</div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <Input label="Ürün" value={item.name} onChange={(v) => setItem({ ...item, name: v })} testId="fnb-add-name" className="col-span-2" />
        <Input label="Adet" type="number" value={item.qty} onChange={(v) => setItem({ ...item, qty: parseFloat(v) || 1 })} testId="fnb-add-qty" />
        <Input label="Fiyat (£)" type="number" value={item.unit_price} onChange={(v) => setItem({ ...item, unit_price: parseFloat(v) || 0 })} testId="fnb-add-price" />
        <div className="col-span-2 md:col-span-3">
          <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">Not</label>
          <input value={item.note} onChange={(e) => setItem({ ...item, note: e.target.value })} data-testid="fnb-add-note" className="w-full px-3 py-2 text-sm border border-stone-200 rounded-md" />
        </div>
        <div>
          <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">Kategori</label>
          <select value={item.category} onChange={(e) => setItem({ ...item, category: e.target.value })} className="w-full px-3 py-2 text-sm border border-stone-200 rounded-md bg-white">
            <option value="beverage">İçecek</option>
            <option value="food">Yemek</option>
            <option value="dessert">Tatlı</option>
            <option value="other">Diğer</option>
          </select>
        </div>
      </div>
      <div className="flex gap-2 justify-end">
        <button onClick={onCancel} className="px-3 py-1.5 text-xs rounded-md border border-stone-200 text-stone-600">Vazgeç</button>
        <button onClick={submit} disabled={busy} data-testid="fnb-add-submit" className="px-3 py-1.5 text-xs rounded-md bg-orange-500 text-white hover:bg-orange-600 disabled:opacity-50">
          {busy ? "…" : "Ekle"}
        </button>
      </div>
    </div>
  );
}

function TransferForm({ tabId, currentOutlet, onTransferred, onCancel }) {
  const [newOutlet, setNewOutlet] = useState("");
  const [tableNo, setTableNo] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (!newOutlet) { toast.error("Hedef outlet seç"); return; }
    setBusy(true);
    try {
      await axios.post(`${API}/api/fnb/tabs/${tabId}/transfer`, { new_outlet: newOutlet, new_table_number: tableNo || null }, { withCredentials: true });
      toast.success("Transfer edildi");
      onTransferred();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Hata");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="bg-violet-50 border border-violet-200 rounded-lg p-4 space-y-3" data-testid="fnb-transfer-form">
      <div className="text-sm font-semibold text-violet-800">Outlet Transferi</div>
      <div className="text-xs text-violet-700">Mevcut: <b>{OUTLET_LABEL[currentOutlet]}</b></div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">Yeni Outlet</label>
          <select value={newOutlet} onChange={(e) => setNewOutlet(e.target.value)} data-testid="fnb-transfer-outlet" className="w-full px-3 py-2 text-sm border border-stone-200 rounded-md bg-white">
            <option value="">— Seç —</option>
            {OUTLETS.filter(([v]) => v !== currentOutlet).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <Input label="Yeni Masa No" value={tableNo} onChange={setTableNo} testId="fnb-transfer-table" />
      </div>
      <div className="flex gap-2 justify-end">
        <button onClick={onCancel} className="px-3 py-1.5 text-xs rounded-md border border-stone-200 text-stone-600">Vazgeç</button>
        <button onClick={submit} disabled={busy || !newOutlet} data-testid="fnb-transfer-submit" className="px-3 py-1.5 text-xs rounded-md bg-violet-500 text-white hover:bg-violet-600 disabled:opacity-50">
          {busy ? "…" : "Transfer Et"}
        </button>
      </div>
    </div>
  );
}

function CloseForm({ tabId, hasBooking, subtotal, onClosed, onCancel }) {
  const [paymentMethod, setPaymentMethod] = useState("card");
  const [tipAmount, setTipAmount] = useState(0);
  const [discountPct, setDiscountPct] = useState(0);
  const [busy, setBusy] = useState(false);
  const [loyalty, setLoyalty] = useState(null);
  const [applyLoyalty, setApplyLoyalty] = useState(false);

  useEffect(() => {
    if (!hasBooking) return;
    axios.get(`${API}/api/fnb/tabs/${tabId}/loyalty-discount`, { withCredentials: true })
      .then((r) => {
        if (r.data.eligible && r.data.discount_pct > 0) {
          setLoyalty(r.data);
          setApplyLoyalty(true);
        }
      })
      .catch(() => {});
  }, [tabId, hasBooking]);

  const effectivePct = Math.max(parseFloat(discountPct) || 0, applyLoyalty && loyalty ? loyalty.discount_pct : 0);
  const total = (subtotal || 0) - ((subtotal || 0) * effectivePct / 100) + (parseFloat(tipAmount) || 0);

  const submit = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/fnb/tabs/${tabId}/close`, {
        payment_method: paymentMethod,
        tip_amount: parseFloat(tipAmount) || 0,
        discount_pct: parseFloat(discountPct) || 0,
        apply_loyalty: applyLoyalty,
      }, { withCredentials: true });
      toast.success(`Tab kapatıldı: £${r.data.total.toFixed(2)}${r.data.charged_to_folio ? " (Folyoya)" : ""}${r.data.loyalty_applied ? ` · ${r.data.loyalty_tier} indirimi %${r.data.effective_discount_pct}` : ""}`);
      onClosed();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Hata");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-stone-100 border border-stone-300 rounded-lg p-4 space-y-3" data-testid="fnb-close-form">
      <div className="text-sm font-semibold text-stone-900">Tab Kapat & Tahsil</div>
      <div>
        <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">Ödeme Yöntemi</label>
        <div className="grid grid-cols-3 gap-2">
          {PAYMENT_METHODS.map(([v, l, Icon]) => {
            const disabled = v === "room_folio" && !hasBooking;
            return (
              <button
                key={v}
                onClick={() => setPaymentMethod(v)}
                disabled={disabled}
                data-testid={`fnb-pay-${v}`}
                className={`py-2 rounded-md border text-xs font-medium transition-all inline-flex items-center justify-center gap-1.5 ${
                  paymentMethod === v ? "bg-stone-900 text-white border-stone-900" :
                  disabled ? "bg-stone-50 text-stone-300 border-stone-200 cursor-not-allowed" :
                  "bg-white text-stone-600 border-stone-200 hover:border-stone-400"
                }`}
              >
                {Icon && <Icon size={12} />}
                {l}
              </button>
            );
          })}
        </div>
        {!hasBooking && <div className="text-[10px] text-stone-500 mt-1">Folyo için booking_id gerekli.</div>}
      </div>
      {loyalty && (
        <label className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-md px-3 py-2 cursor-pointer" data-testid="fnb-loyalty-discount">
          <input type="checkbox" checked={applyLoyalty} onChange={(e) => setApplyLoyalty(e.target.checked)}
            data-testid="fnb-loyalty-toggle" className="accent-amber-600" />
          <span className="text-xs text-amber-800">
            <span className="font-semibold">{loyalty.tier_name}</span> sadakat üyesi ({loyalty.guest_name}) — otomatik <span className="font-semibold">%{loyalty.discount_pct} F&B indirimi</span> uygula
          </span>
        </label>
      )}
      <div className="grid grid-cols-2 gap-2">
        <Input label="Bahşiş (£)" type="number" value={tipAmount} onChange={(v) => setTipAmount(v)} testId="fnb-close-tip" />
        <Input label="İndirim %" type="number" value={discountPct} onChange={(v) => setDiscountPct(v)} testId="fnb-close-discount" />
      </div>
      <div className="flex justify-between text-lg font-bold text-stone-900 border-t border-stone-300 pt-2">
        <span>Toplam</span>
        <span>£{total.toFixed(2)}</span>
      </div>
      <div className="flex gap-2 justify-end">
        <button onClick={onCancel} className="px-3 py-1.5 text-xs rounded-md border border-stone-200 text-stone-600">Vazgeç</button>
        <button onClick={submit} disabled={busy} data-testid="fnb-close-submit" className="px-3 py-1.5 text-xs rounded-md bg-emerald-500 text-white hover:bg-emerald-600 disabled:opacity-50 inline-flex items-center gap-1">
          <Receipt size={12} />
          {busy ? "Kapatılıyor…" : "Kapat & Tahsil"}
        </button>
      </div>
    </div>
  );
}

function TransfersView({ propertyId }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/fnb/tabs/transfers/${propertyId}?limit=200`, { withCredentials: true });
      setRows(r.data.rows || []);
    } catch (e) {
      toast.error("Transfer geçmişi yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  return (
    <div>
      {loading && <div className="text-sm text-stone-400">Yükleniyor…</div>}
      {rows.length === 0 && !loading && (
        <div className="text-center py-12 text-stone-400 text-sm border border-dashed border-stone-200 rounded-lg">Henüz transfer yok.</div>
      )}
      <div className="space-y-2" data-testid="fnb-transfers-list">
        {rows.map((r) => (
          <div key={r.id} className="bg-white border border-stone-200 rounded-lg p-3 flex items-center gap-3">
            <ArrowsLeftRight size={14} className="text-violet-500" />
            <div className="flex-1 text-xs">
              <div className="font-mono text-[10px] text-stone-400">{r.tab_ref}</div>
              <div className="text-stone-800">
                <span className="px-1.5 py-0.5 bg-stone-100 rounded">{OUTLET_LABEL[r.from_outlet]}</span>
                <span className="text-stone-400 mx-1">→</span>
                <span className="px-1.5 py-0.5 bg-violet-100 text-violet-700 rounded">{OUTLET_LABEL[r.to_outlet]}</span>
                <span className="text-[10px] text-stone-400 ml-2">{r.items_count} kalem · £{r.tab_total_at_transfer?.toFixed(2)}</span>
              </div>
            </div>
            <div className="text-[10px] text-stone-400">{r.transferred_at?.slice(0, 16).replace("T", " ")}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DashboardView({ propertyId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/fnb/tabs/dashboard/${propertyId}`, { withCredentials: true });
      setData(r.data);
    } catch (e) {
      toast.error("Dashboard yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="text-sm text-stone-400">Yükleniyor…</div>;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Kpi label="Açık Tab" value={data.open_tabs} color="orange" />
        <Kpi label="Bugün Kapatılan" value={data.closed_today} color="sky" />
        <Kpi label="Bugün Gelir" value={`£${data.revenue_today}`} color="emerald" />
        <Kpi label="Bugün Bahşiş" value={`£${data.tips_today}`} color="amber" />
        <Kpi label="Bugün Transfer" value={data.transfers_today} color="violet" />
      </div>
      <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-white border border-stone-200 rounded-lg p-4">
          <div className="text-sm font-semibold text-stone-800 mb-2">Outlet Bazlı Gelir</div>
          {Object.entries(data.by_outlet_today).length === 0 ? (
            <div className="text-stone-400 text-xs">Henüz kapatılan tab yok.</div>
          ) : (
            <div className="space-y-1.5">
              {Object.entries(data.by_outlet_today).map(([k, v]) => {
                const max = Math.max(...Object.values(data.by_outlet_today), 1);
                return (
                  <div key={k} className="flex items-center gap-2 text-sm">
                    <div className="w-28 text-stone-600">{OUTLET_LABEL[k] || k}</div>
                    <div className="flex-1 bg-stone-100 rounded-full h-2">
                      <div className="bg-orange-500 h-2 rounded-full" style={{ width: `${(v / max) * 100}%` }} />
                    </div>
                    <div className="w-16 text-right font-medium">£{v}</div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
        <div className="bg-white border border-stone-200 rounded-lg p-4">
          <div className="text-sm font-semibold text-stone-800 mb-2">Ödeme Yöntemi</div>
          {Object.entries(data.by_payment_today).length === 0 ? (
            <div className="text-stone-400 text-xs">Henüz kapatılan tab yok.</div>
          ) : (
            <div className="space-y-1.5">
              {Object.entries(data.by_payment_today).map(([k, v]) => {
                const max = Math.max(...Object.values(data.by_payment_today), 1);
                const label = PAYMENT_METHODS.find(([pv]) => pv === k)?.[1] || k;
                return (
                  <div key={k} className="flex items-center gap-2 text-sm">
                    <div className="w-28 text-stone-600">{label}</div>
                    <div className="flex-1 bg-stone-100 rounded-full h-2">
                      <div className="bg-emerald-500 h-2 rounded-full" style={{ width: `${(v / max) * 100}%` }} />
                    </div>
                    <div className="w-16 text-right font-medium">£{v}</div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Kpi({ label, value, color }) {
  const bg = {
    orange: "bg-orange-50 text-orange-700",
    sky: "bg-sky-50 text-sky-700",
    emerald: "bg-emerald-50 text-emerald-700",
    amber: "bg-amber-50 text-amber-700",
    violet: "bg-violet-50 text-violet-700",
  }[color];
  return (
    <div className={`${bg} border border-stone-100 rounded-lg p-3`}>
      <div className="text-[10px] uppercase tracking-wider opacity-70">{label}</div>
      <div className="text-xl font-semibold mt-1">{value}</div>
    </div>
  );
}
