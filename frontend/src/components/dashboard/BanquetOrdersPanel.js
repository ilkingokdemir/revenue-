import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Calendar,
  ArrowsClockwise,
  FilePdf,
  Plus,
  PencilSimple,
  Trash,
  Users,
  Clock,
  MapPin,
  ForkKnife,
  Wine,
  Television,
  CheckCircle,
  X,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

const STATUS_COLORS = {
  draft: "bg-stone-100 text-stone-700 border-stone-200",
  confirmed: "bg-emerald-100 text-emerald-700 border-emerald-200",
  completed: "bg-cyan-100 text-cyan-700 border-cyan-200",
  cancelled: "bg-rose-100 text-rose-700 border-rose-200",
};
const SETUP_STYLES = ["theatre", "classroom", "u-shape", "boardroom", "banquet", "cabaret", "cocktail", "hollow-square", "custom"];

export default function BanquetOrdersPanel({ propertyId }) {
  const [items, setItems] = useState([]);
  const [stats, setStats] = useState(null);
  const [editing, setEditing] = useState(null); // null | object
  const [filterStatus, setFilterStatus] = useState("");
  const [loading, setLoading] = useState(false);

  const reload = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const q = filterStatus ? `?status=${filterStatus}` : "";
      const [l, d] = await Promise.all([
        axios.get(`${API}/api/banquet-orders/${propertyId}${q}`, { withCredentials: true }),
        axios.get(`${API}/api/banquet-orders/dashboard/${propertyId}`, { withCredentials: true }),
      ]);
      setItems(l.data.items || []);
      setStats(d.data);
    } catch (e) {
      toast.error("Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId, filterStatus]);

  useEffect(() => { reload(); }, [reload]);

  const downloadPdf = async (id, ref) => {
    try {
      const r = await axios.get(`${API}/api/banquet-orders/${id}/pdf`, {
        responseType: "blob", withCredentials: true,
      });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${ref || id.slice(0, 8)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("PDF indirildi");
    } catch (e) {
      toast.error("PDF üretilemedi");
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Bu BEO'yu sil?")) return;
    try {
      await axios.delete(`${API}/api/banquet-orders/${id}`, { withCredentials: true });
      toast.success("Silindi");
      reload();
    } catch (e) {
      toast.error("Hata");
    }
  };

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="beo-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Calendar size={12} weight="fill" className="text-pink-500" />
          <span>Conference S&C · Banquet Operations</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">Banquet Event Orders</h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Etkinlik gününde F&B, banquet, AV ve resepsiyon ekiplerinin baktığı resmi belge. <b>Tek tıkla PDF</b>, son dakika değişiklikte tekrar üretilir — Word doc drift olmaz.
        </p>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5" data-testid="beo-stats">
          <Kpi label="Toplam BEO" value={stats.total} color="stone" />
          <Kpi label="Onaylı" value={stats.by_status?.confirmed || 0} color="emerald" />
          <Kpi label="Önümüzdeki 7g" value={stats.upcoming_7d_count} color="pink" />
          <Kpi label="7g Misafir" value={stats.upcoming_7d_guests} color="cyan" />
        </div>
      )}

      <div className="flex items-center gap-2 mb-3">
        <button
          onClick={() => setEditing({})}
          data-testid="beo-create-btn"
          className="px-3 py-1.5 text-xs rounded-md bg-pink-600 text-white font-semibold hover:bg-pink-700 inline-flex items-center gap-1.5"
        >
          <Plus size={12} weight="bold" /> Yeni BEO
        </button>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          data-testid="beo-filter-status"
          className="px-2 py-1.5 text-xs border border-stone-200 rounded"
        >
          <option value="">Tüm durumlar</option>
          <option value="draft">Taslak</option>
          <option value="confirmed">Onaylı</option>
          <option value="completed">Tamamlandı</option>
          <option value="cancelled">İptal</option>
        </select>
        <button onClick={reload} className="ml-auto px-3 py-1.5 text-xs rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50 inline-flex items-center gap-1.5">
          <ArrowsClockwise size={12} /> Yenile
        </button>
      </div>

      {loading && <div className="text-sm text-stone-400">Yükleniyor…</div>}

      {!loading && items.length === 0 && (
        <div className="text-center py-12 text-stone-400 text-sm" data-testid="beo-empty">
          Henüz BEO yok. "Yeni BEO" ile başlayın.
        </div>
      )}

      <div className="space-y-2" data-testid="beo-list">
        {items.map((b) => (
          <div key={b.id} className="bg-white border border-stone-200 rounded-lg p-3 flex items-center gap-3" data-testid={`beo-row-${b.id}`}>
            <div className="w-12 h-12 rounded-lg bg-pink-50 inline-flex items-center justify-center">
              <Calendar size={18} weight="fill" className="text-pink-500" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-stone-900 truncate">{b.event_name}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded border ${STATUS_COLORS[b.status]}`}>{b.status?.toUpperCase()}</span>
              </div>
              <div className="text-xs text-stone-500 flex items-center gap-3 mt-0.5">
                <span><Clock size={10} weight="fill" className="inline mr-0.5" /> {b.event_date} · {b.start_time}-{b.end_time}</span>
                <span><MapPin size={10} weight="fill" className="inline mr-0.5" /> {b.venue_room}</span>
                <span><Users size={10} weight="fill" className="inline mr-0.5" /> {b.guest_count}</span>
                <span className="text-stone-400 font-mono">{b.ref}</span>
              </div>
            </div>
            <button onClick={() => downloadPdf(b.id, b.ref)} data-testid={`beo-pdf-${b.id}`} className="px-2 py-1 text-xs rounded bg-pink-100 text-pink-700 hover:bg-pink-200 inline-flex items-center gap-1">
              <FilePdf size={12} weight="fill" /> PDF
            </button>
            <button onClick={() => setEditing(b)} data-testid={`beo-edit-${b.id}`} className="w-7 h-7 rounded bg-stone-100 hover:bg-stone-200 inline-flex items-center justify-center">
              <PencilSimple size={12} />
            </button>
            <button onClick={() => remove(b.id)} className="w-7 h-7 rounded bg-rose-50 text-rose-500 hover:bg-rose-100 inline-flex items-center justify-center">
              <Trash size={12} />
            </button>
          </div>
        ))}
      </div>

      {editing !== null && (
        <BeoEditor
          propertyId={propertyId}
          initial={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); reload(); }}
        />
      )}
    </div>
  );
}

function Kpi({ label, value, color }) {
  const cls = {
    stone: "bg-stone-100 text-stone-700",
    emerald: "bg-emerald-50 text-emerald-700",
    pink: "bg-pink-50 text-pink-700",
    cyan: "bg-cyan-50 text-cyan-700",
  }[color];
  return (
    <div className={`${cls} border border-stone-100 rounded-lg p-3`}>
      <div className="text-[10px] uppercase tracking-wider opacity-70">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
    </div>
  );
}

function BeoEditor({ propertyId, initial, onClose, onSaved }) {
  const isEdit = !!initial?.id;
  const [form, setForm] = useState(() => ({
    event_name: initial?.event_name || "",
    event_date: initial?.event_date || new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10),
    start_time: initial?.start_time || "18:00",
    end_time: initial?.end_time || "23:00",
    venue_room: initial?.venue_room || "",
    guest_count: initial?.guest_count || 50,
    setup_style: initial?.setup_style || "banquet",
    decoration: initial?.decoration || "",
    special_requests: initial?.special_requests || "",
    billing_instructions: initial?.billing_instructions || "",
    notes: initial?.notes || "",
    status: initial?.status || "draft",
  }));
  const [menu, setMenu] = useState(initial?.menu || [{ name: "Starter", items: [], notes: "" }]);
  const [bev, setBev] = useState(initial?.beverages || []);
  const [av, setAv] = useState(initial?.av || []);
  const [contacts, setContacts] = useState(initial?.contacts || []);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (!form.event_name || !form.venue_room) {
      toast.error("Etkinlik adı ve salon zorunlu");
      return;
    }
    setBusy(true);
    try {
      const payload = {
        property_id: propertyId,
        ...form,
        guest_count: parseInt(form.guest_count) || 0,
        menu: menu.map((c) => ({
          name: c.name || "",
          items: typeof c.items === "string" ? c.items.split(",").map((s) => s.trim()).filter(Boolean) : c.items || [],
          notes: c.notes || null,
        })),
        beverages: bev.filter((b) => b.name),
        av: av.filter((a) => a.name).map((a) => ({ ...a, qty: parseInt(a.qty) || 1 })),
        contacts: contacts.filter((c) => c.name),
      };
      if (isEdit) {
        await axios.put(`${API}/api/banquet-orders/${initial.id}`, payload, { withCredentials: true });
        toast.success("Güncellendi");
      } else {
        await axios.post(`${API}/api/banquet-orders`, payload, { withCredentials: true });
        toast.success("Oluşturuldu");
      }
      onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Hata");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-stone-900/50 backdrop-blur-sm z-[9999] flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid="beo-editor">
        <div className="sticky top-0 bg-white border-b border-stone-100 p-4 flex items-center justify-between">
          <div className="text-lg font-bold text-stone-900">{isEdit ? "BEO Düzenle" : "Yeni BEO"}</div>
          <button onClick={onClose} className="w-8 h-8 rounded-full bg-stone-100 hover:bg-stone-200 inline-flex items-center justify-center">
            <X size={14} />
          </button>
        </div>
        <div className="p-5 space-y-4">
          {/* Event basics */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <Field label="Etkinlik Adı *">
              <input value={form.event_name} onChange={(e) => setForm({ ...form, event_name: e.target.value })} data-testid="beo-event-name" className="w-full px-2 py-1.5 text-sm border border-stone-200 rounded" />
            </Field>
            <Field label="Salon *">
              <input value={form.venue_room} onChange={(e) => setForm({ ...form, venue_room: e.target.value })} data-testid="beo-venue-room" className="w-full px-2 py-1.5 text-sm border border-stone-200 rounded" />
            </Field>
            <Field label="Misafir Sayısı">
              <input type="number" value={form.guest_count} onChange={(e) => setForm({ ...form, guest_count: e.target.value })} data-testid="beo-guest-count" className="w-full px-2 py-1.5 text-sm border border-stone-200 rounded" />
            </Field>
            <Field label="Tarih">
              <input type="date" value={form.event_date} onChange={(e) => setForm({ ...form, event_date: e.target.value })} data-testid="beo-event-date" className="w-full px-2 py-1.5 text-sm border border-stone-200 rounded" />
            </Field>
            <Field label="Başlangıç">
              <input type="time" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} data-testid="beo-start-time" className="w-full px-2 py-1.5 text-sm border border-stone-200 rounded" />
            </Field>
            <Field label="Bitiş">
              <input type="time" value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })} data-testid="beo-end-time" className="w-full px-2 py-1.5 text-sm border border-stone-200 rounded" />
            </Field>
            <Field label="Düzen">
              <select value={form.setup_style} onChange={(e) => setForm({ ...form, setup_style: e.target.value })} data-testid="beo-setup-style" className="w-full px-2 py-1.5 text-sm border border-stone-200 rounded">
                {SETUP_STYLES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </Field>
            <Field label="Durum">
              <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} data-testid="beo-status" className="w-full px-2 py-1.5 text-sm border border-stone-200 rounded">
                <option value="draft">Taslak</option>
                <option value="confirmed">Onaylı</option>
                <option value="completed">Tamamlandı</option>
                <option value="cancelled">İptal</option>
              </select>
            </Field>
          </div>

          <Section icon={ForkKnife} title="F&B Menü" testId="beo-menu-section">
            {menu.map((c, i) => (
              <div key={i} className="grid grid-cols-12 gap-2 mb-2" data-testid={`beo-menu-row-${i}`}>
                <input value={c.name} onChange={(e) => setMenu(menu.map((m, idx) => idx === i ? { ...m, name: e.target.value } : m))} placeholder="Course" className="col-span-3 px-2 py-1 text-sm border border-stone-200 rounded" />
                <input value={Array.isArray(c.items) ? c.items.join(", ") : c.items} onChange={(e) => setMenu(menu.map((m, idx) => idx === i ? { ...m, items: e.target.value } : m))} placeholder="Yemekler (virgülle)" className="col-span-7 px-2 py-1 text-sm border border-stone-200 rounded" />
                <input value={c.notes || ""} onChange={(e) => setMenu(menu.map((m, idx) => idx === i ? { ...m, notes: e.target.value } : m))} placeholder="Not" className="col-span-2 px-2 py-1 text-sm border border-stone-200 rounded" />
              </div>
            ))}
            <button onClick={() => setMenu([...menu, { name: "", items: [], notes: "" }])} className="text-xs text-pink-600 hover:underline">+ course ekle</button>
          </Section>

          <Section icon={Wine} title="İçecekler" testId="beo-bev-section">
            {bev.map((b, i) => (
              <div key={i} className="grid grid-cols-12 gap-2 mb-2">
                <input value={b.name} onChange={(e) => setBev(bev.map((x, idx) => idx === i ? { ...x, name: e.target.value } : x))} placeholder="İçecek" className="col-span-5 px-2 py-1 text-sm border border-stone-200 rounded" />
                <input value={b.qty || ""} onChange={(e) => setBev(bev.map((x, idx) => idx === i ? { ...x, qty: e.target.value } : x))} placeholder="Miktar / saat" className="col-span-4 px-2 py-1 text-sm border border-stone-200 rounded" />
                <input value={b.notes || ""} onChange={(e) => setBev(bev.map((x, idx) => idx === i ? { ...x, notes: e.target.value } : x))} placeholder="Not" className="col-span-3 px-2 py-1 text-sm border border-stone-200 rounded" />
              </div>
            ))}
            <button onClick={() => setBev([...bev, { name: "", qty: "", notes: "" }])} className="text-xs text-pink-600 hover:underline">+ içecek ekle</button>
          </Section>

          <Section icon={Television} title="AV / Ekipman" testId="beo-av-section">
            {av.map((a, i) => (
              <div key={i} className="grid grid-cols-12 gap-2 mb-2">
                <input value={a.name} onChange={(e) => setAv(av.map((x, idx) => idx === i ? { ...x, name: e.target.value } : x))} placeholder="Ekipman" className="col-span-7 px-2 py-1 text-sm border border-stone-200 rounded" />
                <input type="number" value={a.qty || 1} onChange={(e) => setAv(av.map((x, idx) => idx === i ? { ...x, qty: e.target.value } : x))} placeholder="Adet" className="col-span-2 px-2 py-1 text-sm border border-stone-200 rounded" />
                <input value={a.notes || ""} onChange={(e) => setAv(av.map((x, idx) => idx === i ? { ...x, notes: e.target.value } : x))} placeholder="Not" className="col-span-3 px-2 py-1 text-sm border border-stone-200 rounded" />
              </div>
            ))}
            <button onClick={() => setAv([...av, { name: "", qty: 1, notes: "" }])} className="text-xs text-pink-600 hover:underline">+ ekipman ekle</button>
          </Section>

          <Field label="Dekorasyon">
            <input value={form.decoration} onChange={(e) => setForm({ ...form, decoration: e.target.value })} data-testid="beo-decoration" className="w-full px-2 py-1.5 text-sm border border-stone-200 rounded" />
          </Field>
          <Field label="Özel İstekler">
            <textarea value={form.special_requests} onChange={(e) => setForm({ ...form, special_requests: e.target.value })} rows={2} data-testid="beo-special" className="w-full px-2 py-1.5 text-sm border border-stone-200 rounded" />
          </Field>
          <Field label="Faturalama">
            <input value={form.billing_instructions} onChange={(e) => setForm({ ...form, billing_instructions: e.target.value })} data-testid="beo-billing" className="w-full px-2 py-1.5 text-sm border border-stone-200 rounded" />
          </Field>

          <Section icon={Users} title="Kontaklar" testId="beo-contacts-section">
            {contacts.map((c, i) => (
              <div key={i} className="grid grid-cols-12 gap-2 mb-2">
                <input value={c.name} onChange={(e) => setContacts(contacts.map((x, idx) => idx === i ? { ...x, name: e.target.value } : x))} placeholder="Ad" className="col-span-3 px-2 py-1 text-sm border border-stone-200 rounded" />
                <input value={c.role || ""} onChange={(e) => setContacts(contacts.map((x, idx) => idx === i ? { ...x, role: e.target.value } : x))} placeholder="Rol" className="col-span-3 px-2 py-1 text-sm border border-stone-200 rounded" />
                <input value={c.phone || ""} onChange={(e) => setContacts(contacts.map((x, idx) => idx === i ? { ...x, phone: e.target.value } : x))} placeholder="Telefon" className="col-span-3 px-2 py-1 text-sm border border-stone-200 rounded" />
                <input value={c.email || ""} onChange={(e) => setContacts(contacts.map((x, idx) => idx === i ? { ...x, email: e.target.value } : x))} placeholder="Email" className="col-span-3 px-2 py-1 text-sm border border-stone-200 rounded" />
              </div>
            ))}
            <button onClick={() => setContacts([...contacts, { name: "", role: "", phone: "", email: "" }])} className="text-xs text-pink-600 hover:underline">+ kontak ekle</button>
          </Section>

          <Field label="Ops Notları">
            <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} rows={2} data-testid="beo-notes" className="w-full px-2 py-1.5 text-sm border border-stone-200 rounded" />
          </Field>

          <button onClick={save} disabled={busy} data-testid="beo-save" className="w-full py-2.5 rounded-md bg-pink-600 text-white text-sm font-semibold hover:bg-pink-700 disabled:opacity-50 inline-flex items-center justify-center gap-2">
            <CheckCircle size={14} weight="fill" /> {busy ? "Kaydediliyor…" : (isEdit ? "Güncelle" : "Oluştur")}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block">
      <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-1">{label}</div>
      {children}
    </label>
  );
}

function Section({ icon: Icon, title, testId, children }) {
  return (
    <div className="bg-stone-50 border border-stone-100 rounded-lg p-3" data-testid={testId}>
      <div className="flex items-center gap-2 mb-2 text-xs font-semibold text-stone-700">
        <Icon size={14} weight="fill" /> {title}
      </div>
      {children}
    </div>
  );
}
