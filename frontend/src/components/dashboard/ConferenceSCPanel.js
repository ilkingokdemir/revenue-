import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Briefcase,
  CalendarBlank,
  Users,
  ForkKnife,
  Plus,
  CheckCircle,
  XCircle,
  Trash,
  ArrowsClockwise,
  ChartPie,
  Sparkle,
  PaperPlaneTilt,
  CurrencyCircleDollar,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

const EVENT_TYPES = [
  ["conference", "Konferans"],
  ["wedding", "Düğün"],
  ["banquet", "Banket"],
  ["meeting", "Toplantı"],
  ["gala", "Gala"],
  ["training", "Eğitim"],
];

const STATUS_LABELS = {
  new: "Yeni",
  proposal_ready: "Teklif Hazır",
  sent: "Gönderildi",
  accepted: "Kazanıldı",
  rejected: "Kaybedildi",
  cancelled: "İptal",
};

const STATUS_COLORS = {
  new: "bg-stone-100 text-stone-700",
  proposal_ready: "bg-amber-100 text-amber-700",
  sent: "bg-sky-100 text-sky-700",
  accepted: "bg-emerald-100 text-emerald-700",
  rejected: "bg-rose-100 text-rose-700",
  cancelled: "bg-stone-200 text-stone-500",
};

export default function ConferenceSCPanel({ propertyId }) {
  const [tab, setTab] = useState("dashboard");

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="conference-sc-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Briefcase size={12} weight="fill" className="text-rose-500" />
          <span>MICE · Conference S&C</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">
          Etkinlik Satış & Catering
        </h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Toplantı + düğün + konferans teklifleri: mekan + catering + oda bloku tek ekranda paketleyin.
        </p>
      </div>

      <div className="flex gap-2 mb-5 border-b border-stone-200">
        <TabBtn active={tab === "dashboard"} onClick={() => setTab("dashboard")} testId="sc-tab-dashboard">
          <ChartPie size={14} className="inline mr-1.5" />
          Pipeline
        </TabBtn>
        <TabBtn active={tab === "inquiries"} onClick={() => setTab("inquiries")} testId="sc-tab-inquiries">
          <PaperPlaneTilt size={14} className="inline mr-1.5" />
          Talepler
        </TabBtn>
        <TabBtn active={tab === "setup"} onClick={() => setTab("setup")} testId="sc-tab-setup">
          <ForkKnife size={14} className="inline mr-1.5" />
          Mekan & Catering
        </TabBtn>
      </div>

      {tab === "dashboard" && <DashboardTab propertyId={propertyId} />}
      {tab === "inquiries" && <InquiriesTab propertyId={propertyId} />}
      {tab === "setup" && <SetupTab propertyId={propertyId} />}
    </div>
  );
}

function TabBtn({ active, onClick, children, testId }) {
  return (
    <button
      onClick={onClick}
      data-testid={testId}
      className={`px-3.5 py-2 text-sm font-medium transition-all border-b-2 -mb-px ${
        active ? "border-rose-500 text-rose-700" : "border-transparent text-stone-500 hover:text-stone-800"
      }`}
    >
      {children}
    </button>
  );
}

/* ==================== DASHBOARD ==================== */
function DashboardTab({ propertyId }) {
  const [data, setData] = useState(null);
  const [days, setDays] = useState(90);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/conference/dashboard/${propertyId}?days=${days}`, { withCredentials: true });
      setData(r.data);
    } catch (e) {
      toast.error("Dashboard yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId, days]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="text-sm text-stone-400">Yükleniyor…</div>;
  if (!data) return null;

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2 flex-wrap">
        <label className="text-xs text-stone-600">Aralık:</label>
        {[30, 90, 180, 365].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            data-testid={`sc-dash-days-${d}`}
            className={`px-2.5 py-1 text-xs rounded-full border transition-all ${
              days === d ? "bg-rose-500 text-white border-rose-500" : "bg-white text-stone-600 border-stone-200 hover:border-stone-400"
            }`}
          >
            {d} gün
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="Toplam Talep" value={data.total_inquiries} color="rose" testId="sc-kpi-total" />
        <Kpi label="Pipeline Değeri" value={`£${data.pipeline_value.toLocaleString()}`} color="amber" testId="sc-kpi-pipeline" />
        <Kpi label="Kazanılan" value={`£${data.won_value.toLocaleString()}`} color="emerald" testId="sc-kpi-won" />
        <Kpi label="Dönüşüm" value={`%${data.conversion_rate}`} color="sky" testId="sc-kpi-conversion" />
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-white border border-stone-200 rounded-lg p-5">
          <div className="text-sm font-semibold text-stone-800 mb-3">Ortalama Anlaşma Büyüklüğü</div>
          <div className="text-4xl font-bold text-emerald-600">£{data.avg_deal_size.toLocaleString()}</div>
          <div className="text-xs text-stone-500 mt-2">Kazanılan tekliflerin ortalama toplam tutarı</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-lg p-5">
          <div className="text-sm font-semibold text-stone-800 mb-3">Etkinlik Türü Dağılımı</div>
          <div className="space-y-1.5" data-testid="sc-by-type">
            {Object.entries(data.by_event_type).map(([et, c]) => {
              const total = Object.values(data.by_event_type).reduce((a, b) => a + b, 0);
              const pct = total ? (c / total * 100).toFixed(1) : 0;
              const label = EVENT_TYPES.find(([v]) => v === et)?.[1] || et;
              return (
                <div key={et} className="flex items-center gap-2 text-sm">
                  <div className="w-24 text-stone-600">{label}</div>
                  <div className="flex-1 bg-stone-100 rounded-full h-2">
                    <div className="bg-rose-500 h-2 rounded-full" style={{ width: `${pct}%` }} />
                  </div>
                  <div className="w-10 text-right font-medium text-stone-800">{c}</div>
                </div>
              );
            })}
            {Object.keys(data.by_event_type).length === 0 && (
              <div className="text-sm text-stone-400 text-center py-4">Henüz talep yok.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ==================== INQUIRIES ==================== */
function InquiriesTab({ propertyId }) {
  const [rows, setRows] = useState([]);
  const [byStatus, setByStatus] = useState({});
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [filter, setFilter] = useState("");

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const url = filter
        ? `${API}/api/conference/inquiries/${propertyId}?status=${filter}`
        : `${API}/api/conference/inquiries/${propertyId}`;
      const r = await axios.get(url, { withCredentials: true });
      setRows(r.data.rows || []);
      setByStatus(r.data.by_status || {});
    } catch (e) {
      toast.error("Talepler yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId, filter]);

  useEffect(() => { load(); }, [load]);

  if (selectedId) {
    return <InquiryDetail propertyId={propertyId} inqId={selectedId} onBack={() => { setSelectedId(null); load(); }} />;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex gap-1 flex-wrap">
          <StatusPill active={filter === ""} onClick={() => setFilter("")} label="Tümü" count={rows.length} />
          {Object.entries(STATUS_LABELS).map(([k, l]) => (
            <StatusPill key={k} active={filter === k} onClick={() => setFilter(k)} label={l} count={byStatus[k]?.count || 0} />
          ))}
        </div>
        <div className="ml-auto flex gap-1">
          <button onClick={load} className="px-3 py-1 text-xs rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50 inline-flex items-center gap-1.5">
            <ArrowsClockwise size={12} /> Yenile
          </button>
          <button onClick={() => setShowForm((v) => !v)} data-testid="sc-new-inquiry-btn" className="px-3 py-1 text-xs rounded-md bg-rose-500 text-white hover:bg-rose-600 inline-flex items-center gap-1.5">
            <Plus size={12} weight="bold" />
            {showForm ? "Kapat" : "Yeni Talep"}
          </button>
        </div>
      </div>

      {showForm && (
        <NewInquiryForm propertyId={propertyId} onCreated={(id) => { setShowForm(false); load(); setSelectedId(id); }} onCancel={() => setShowForm(false)} />
      )}

      {loading && <div className="text-sm text-stone-400">Yükleniyor…</div>}

      {rows.length === 0 && !loading && (
        <div className="text-center py-12 text-stone-400 text-sm border border-dashed border-stone-200 rounded-lg">
          Henüz talep yok. "Yeni Talep" ile ilk MICE talebini oluşturun.
        </div>
      )}

      <div className="space-y-2" data-testid="sc-inquiry-list">
        {rows.map((inq) => (
          <div
            key={inq.id}
            onClick={() => setSelectedId(inq.id)}
            data-testid={`sc-inq-row-${inq.id}`}
            className="bg-white border border-stone-200 rounded-lg p-3.5 cursor-pointer hover:border-rose-300 hover:shadow-sm transition-all"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <span className={`px-1.5 py-0.5 text-[10px] rounded font-medium ${STATUS_COLORS[inq.status] || STATUS_COLORS.new}`}>
                    {STATUS_LABELS[inq.status] || inq.status}
                  </span>
                  <span className="font-mono text-[10px] text-stone-400">{inq.ref}</span>
                  <span className="text-[11px] text-stone-500 capitalize">· {EVENT_TYPES.find(([v]) => v === inq.event_type)?.[1] || inq.event_type}</span>
                </div>
                <div className="text-sm font-semibold text-stone-900 truncate">{inq.event_name}</div>
                <div className="text-xs text-stone-500 mt-0.5">
                  {inq.contact_company ? `${inq.contact_company} · ` : ""}{inq.contact_name} · {inq.total_attendees} kişi
                </div>
                <div className="text-[11px] text-stone-400 mt-1">
                  {inq.start_date} → {inq.end_date} ({inq.days} gün)
                </div>
              </div>
              <div className="text-right flex-shrink-0">
                {inq.proposal_total > 0 ? (
                  <>
                    <div className="text-lg font-semibold text-stone-900">£{inq.proposal_total.toLocaleString()}</div>
                    <div className="text-[10px] text-stone-400">Teklif</div>
                  </>
                ) : (
                  <span className="text-[10px] text-stone-400">Teklif yok</span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatusPill({ active, onClick, label, count }) {
  return (
    <button
      onClick={onClick}
      className={`px-2 py-1 text-[11px] rounded-full border transition-all ${
        active ? "bg-stone-900 text-white border-stone-900" : "bg-white text-stone-600 border-stone-200 hover:border-stone-400"
      }`}
    >
      {label}
      {count > 0 && <span className="ml-1 opacity-70">({count})</span>}
    </button>
  );
}

function Kpi({ label, value, color, testId }) {
  const bg = {
    rose: "bg-rose-50 text-rose-700",
    amber: "bg-amber-50 text-amber-700",
    emerald: "bg-emerald-50 text-emerald-700",
    sky: "bg-sky-50 text-sky-700",
  }[color];
  return (
    <div className={`${bg} border border-stone-100 rounded-lg p-3.5`} data-testid={testId}>
      <div className="text-[10px] uppercase tracking-wider opacity-70">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
    </div>
  );
}

function NewInquiryForm({ propertyId, onCreated, onCancel }) {
  const [form, setForm] = useState({
    contact_name: "",
    contact_email: "",
    contact_company: "",
    contact_phone: "",
    event_name: "",
    event_type: "conference",
    start_date: "",
    end_date: "",
    total_attendees: 50,
    budget_estimate: "",
    special_requirements: "",
  });
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!form.contact_name || !form.contact_email || !form.event_name || !form.start_date || !form.end_date) {
      toast.error("Zorunlu alanları doldurun");
      return;
    }
    setBusy(true);
    try {
      const payload = { ...form, property_id: propertyId, budget_estimate: parseFloat(form.budget_estimate) || null };
      const r = await axios.post(`${API}/api/conference/inquiry`, payload, { withCredentials: true });
      toast.success(`Talep oluşturuldu: ${r.data.ref}`);
      onCreated(r.data.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Oluşturulamadı");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-stone-50 border border-stone-200 rounded-lg p-4 space-y-3" data-testid="sc-new-inquiry-form">
      <div className="text-sm font-semibold text-stone-800">Yeni MICE Talebi</div>
      <div className="grid md:grid-cols-2 gap-3">
        <Field label="Kontakt Adı *" value={form.contact_name} onChange={(v) => setForm({ ...form, contact_name: v })} testId="sc-f-name" />
        <Field label="E-posta *" type="email" value={form.contact_email} onChange={(v) => setForm({ ...form, contact_email: v })} testId="sc-f-email" />
        <Field label="Şirket" value={form.contact_company} onChange={(v) => setForm({ ...form, contact_company: v })} testId="sc-f-company" />
        <Field label="Telefon" value={form.contact_phone} onChange={(v) => setForm({ ...form, contact_phone: v })} testId="sc-f-phone" />
        <Field label="Etkinlik Adı *" value={form.event_name} onChange={(v) => setForm({ ...form, event_name: v })} testId="sc-f-event" className="md:col-span-2" />
        <Select label="Tür" value={form.event_type} onChange={(v) => setForm({ ...form, event_type: v })} options={EVENT_TYPES} testId="sc-f-type" />
        <Field label="Toplam Katılımcı *" type="number" value={form.total_attendees} onChange={(v) => setForm({ ...form, total_attendees: parseInt(v) || 1 })} testId="sc-f-attendees" />
        <Field label="Başlangıç *" type="date" value={form.start_date} onChange={(v) => setForm({ ...form, start_date: v })} testId="sc-f-start" />
        <Field label="Bitiş *" type="date" value={form.end_date} onChange={(v) => setForm({ ...form, end_date: v })} testId="sc-f-end" />
        <Field label="Bütçe Tahmini (£)" type="number" value={form.budget_estimate} onChange={(v) => setForm({ ...form, budget_estimate: v })} testId="sc-f-budget" />
      </div>
      <div>
        <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">Özel İstekler</label>
        <textarea
          value={form.special_requirements}
          onChange={(e) => setForm({ ...form, special_requirements: e.target.value })}
          rows={2}
          data-testid="sc-f-requirements"
          className="w-full px-3 py-2 text-sm border border-stone-200 rounded-md focus:outline-none focus:border-rose-400"
        />
      </div>
      <div className="flex gap-2 justify-end">
        <button onClick={onCancel} className="px-4 py-2 text-sm rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50">Vazgeç</button>
        <button onClick={submit} disabled={busy} data-testid="sc-f-submit" className="px-4 py-2 text-sm rounded-md bg-rose-500 text-white hover:bg-rose-600 disabled:opacity-50">
          {busy ? "Kaydediliyor…" : "Talep Oluştur"}
        </button>
      </div>
    </div>
  );
}

function Field({ label, type = "text", value, onChange, testId, className = "" }) {
  return (
    <div className={className}>
      <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        data-testid={testId}
        className="w-full px-3 py-2 text-sm border border-stone-200 rounded-md focus:outline-none focus:border-rose-400"
      />
    </div>
  );
}

function Select({ label, value, onChange, options, testId }) {
  return (
    <div>
      <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)} data-testid={testId} className="w-full px-3 py-2 text-sm border border-stone-200 rounded-md bg-white focus:outline-none focus:border-rose-400">
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </div>
  );
}

/* ==================== INQUIRY DETAIL + PROPOSAL BUILDER ==================== */
function InquiryDetail({ propertyId, inqId, onBack }) {
  const [inq, setInq] = useState(null);
  const [spaces, setSpaces] = useState([]);
  const [catering, setCatering] = useState([]);
  const [lines, setLines] = useState([]);
  const [discountPct, setDiscountPct] = useState(0);
  const [notes, setNotes] = useState("");
  const [validUntil, setValidUntil] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [i, s, c] = await Promise.all([
        axios.get(`${API}/api/conference/inquiry/${inqId}`, { withCredentials: true }),
        axios.get(`${API}/api/conference/event-spaces/${propertyId}`, { withCredentials: true }),
        axios.get(`${API}/api/conference/catering/${propertyId}`, { withCredentials: true }),
      ]);
      setInq(i.data);
      setSpaces(s.data.rows || []);
      setCatering(c.data.rows || []);
      setLines(i.data.proposal_lines || []);
      setDiscountPct(i.data.proposal_discount_pct || 0);
      setNotes(i.data.proposal_notes || "");
      setValidUntil(i.data.proposal_valid_until || "");
    } catch (e) {
      toast.error("Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [inqId, propertyId]);

  useEffect(() => { load(); }, [load]);

  const addSpace = (s) => {
    setLines([...lines, {
      type: "space",
      reference_id: s.id,
      description: `${s.name} (full-day)`,
      qty: inq?.days || 1,
      unit_price: s.full_day_rate,
      currency: "gbp",
    }]);
  };

  const addCatering = (c) => {
    setLines([...lines, {
      type: "catering",
      reference_id: c.id,
      description: `${c.name} (per person)`,
      qty: inq?.total_attendees || 1,
      unit_price: c.per_person_price,
      currency: "gbp",
    }]);
  };

  const addRoomBlock = () => {
    setLines([...lines, {
      type: "room_block",
      description: "Oda bloku (standart oda, gece başına)",
      qty: Math.ceil((inq?.total_attendees || 10) / 2) * (inq?.days || 1),
      unit_price: 110,
      currency: "gbp",
    }]);
  };

  const addCustom = () => {
    setLines([...lines, { type: "custom", description: "Özel kalem", qty: 1, unit_price: 0, currency: "gbp" }]);
  };

  const updateLine = (i, patch) => {
    const n = [...lines];
    n[i] = { ...n[i], ...patch };
    setLines(n);
  };

  const removeLine = (i) => setLines(lines.filter((_, idx) => idx !== i));

  const subtotal = lines.reduce((s, l) => s + (l.qty * l.unit_price), 0);
  const discountAmount = subtotal * discountPct / 100;
  const total = subtotal - discountAmount;
  const perPerson = inq?.total_attendees ? total / inq.total_attendees : 0;

  const saveProposal = async () => {
    if (lines.length === 0) { toast.error("En az bir kalem ekleyin"); return; }
    try {
      await axios.post(`${API}/api/conference/inquiry/${inqId}/proposal`, {
        lines: lines.map((l) => ({ ...l, qty: parseFloat(l.qty) || 0, unit_price: parseFloat(l.unit_price) || 0 })),
        discount_pct: parseFloat(discountPct) || 0,
        notes,
        valid_until: validUntil || null,
      }, { withCredentials: true });
      toast.success("Teklif kaydedildi");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Kaydedilemedi");
    }
  };

  const setStatus = async (newStatus) => {
    try {
      await axios.post(`${API}/api/conference/inquiry/${inqId}/status/${newStatus}`, {}, { withCredentials: true });
      toast.success(`Durum: ${STATUS_LABELS[newStatus]}`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Değiştirilemedi");
    }
  };

  if (loading || !inq) return <div className="text-sm text-stone-400">Yükleniyor…</div>;

  return (
    <div className="space-y-4" data-testid="sc-inquiry-detail">
      <button onClick={onBack} data-testid="sc-back-btn" className="text-xs text-stone-600 hover:text-stone-900 inline-flex items-center gap-1">
        ← Geri
      </button>

      <div className="bg-white border border-stone-200 rounded-lg p-4">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className={`px-1.5 py-0.5 text-[10px] rounded font-medium ${STATUS_COLORS[inq.status]}`}>{STATUS_LABELS[inq.status]}</span>
              <span className="font-mono text-[10px] text-stone-400">{inq.ref}</span>
            </div>
            <div className="text-lg font-semibold text-stone-900">{inq.event_name}</div>
            <div className="text-xs text-stone-600">
              {inq.contact_company && `${inq.contact_company} · `}{inq.contact_name} · {inq.contact_email}
            </div>
            <div className="text-[11px] text-stone-500 mt-1">
              {inq.start_date} → {inq.end_date} ({inq.days} gün) · {inq.total_attendees} kişi
            </div>
          </div>
          <div className="flex gap-1.5 flex-wrap">
            {inq.status !== "sent" && inq.proposal_total > 0 && (
              <button onClick={() => setStatus("sent")} data-testid="sc-set-sent" className="px-2.5 py-1 text-[11px] rounded-md bg-sky-500 text-white hover:bg-sky-600 inline-flex items-center gap-1">
                <PaperPlaneTilt size={11} />
                Gönderildi
              </button>
            )}
            {inq.status !== "accepted" && (
              <button onClick={() => setStatus("accepted")} data-testid="sc-set-accepted" className="px-2.5 py-1 text-[11px] rounded-md bg-emerald-500 text-white hover:bg-emerald-600 inline-flex items-center gap-1">
                <CheckCircle size={11} />
                Kazan
              </button>
            )}
            {inq.status !== "rejected" && (
              <button onClick={() => setStatus("rejected")} data-testid="sc-set-rejected" className="px-2.5 py-1 text-[11px] rounded-md bg-rose-500 text-white hover:bg-rose-600 inline-flex items-center gap-1">
                <XCircle size={11} />
                Kaybet
              </button>
            )}
          </div>
        </div>
        {inq.special_requirements && (
          <div className="text-xs text-stone-600 bg-stone-50 border border-stone-100 rounded p-2">
            <b>Özel İstekler:</b> {inq.special_requirements}
          </div>
        )}
      </div>

      {/* Proposal Builder */}
      <div className="bg-white border border-stone-200 rounded-lg p-4" data-testid="sc-proposal-builder">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-semibold text-stone-800">Teklif Yapıcı</div>
          <button onClick={saveProposal} data-testid="sc-save-proposal" className="px-3 py-1.5 text-xs rounded-md bg-rose-500 text-white hover:bg-rose-600 inline-flex items-center gap-1.5">
            <Sparkle size={12} weight="fill" />
            Teklifi Kaydet
          </button>
        </div>

        {/* Add buttons */}
        <div className="flex gap-2 flex-wrap mb-3">
          {spaces.length > 0 && (
            <select onChange={(e) => { const s = spaces.find((x) => x.id === e.target.value); if (s) addSpace(s); e.target.value = ""; }}
                    data-testid="sc-add-space" className="px-2.5 py-1 text-xs border border-stone-200 rounded-md bg-white">
              <option value="">+ Mekan Ekle…</option>
              {spaces.map((s) => <option key={s.id} value={s.id}>{`${s.name} · £${s.full_day_rate}/gün`}</option>)}
            </select>
          )}
          {catering.length > 0 && (
            <select onChange={(e) => { const c = catering.find((x) => x.id === e.target.value); if (c) addCatering(c); e.target.value = ""; }}
                    data-testid="sc-add-catering" className="px-2.5 py-1 text-xs border border-stone-200 rounded-md bg-white">
              <option value="">+ Catering Ekle…</option>
              {catering.map((c) => <option key={c.id} value={c.id}>{`${c.name} · £${c.per_person_price}/kişi`}</option>)}
            </select>
          )}
          <button onClick={addRoomBlock} data-testid="sc-add-room-block" className="px-2.5 py-1 text-xs border border-stone-200 text-stone-700 rounded-md hover:bg-stone-50">+ Oda Bloku</button>
          <button onClick={addCustom} data-testid="sc-add-custom" className="px-2.5 py-1 text-xs border border-stone-200 text-stone-700 rounded-md hover:bg-stone-50">+ Özel Kalem</button>
        </div>

        {/* Lines */}
        <div className="space-y-1.5 mb-3" data-testid="sc-proposal-lines">
          {lines.map((l, i) => (
            <div key={i} className="grid grid-cols-12 gap-2 items-center bg-stone-50 border border-stone-100 rounded p-2">
              <span className={`col-span-1 px-1 py-0.5 text-[9px] text-center rounded uppercase font-bold ${
                l.type === "space" ? "bg-rose-100 text-rose-700" :
                l.type === "catering" ? "bg-amber-100 text-amber-700" :
                l.type === "room_block" ? "bg-sky-100 text-sky-700" :
                "bg-stone-200 text-stone-700"
              }`}>{l.type.slice(0, 4)}</span>
              <input value={l.description} onChange={(e) => updateLine(i, { description: e.target.value })} className="col-span-5 px-2 py-1 text-xs border border-stone-200 rounded bg-white" />
              <input type="number" value={l.qty} onChange={(e) => updateLine(i, { qty: e.target.value })} className="col-span-2 px-2 py-1 text-xs border border-stone-200 rounded bg-white text-right" />
              <input type="number" step="0.01" value={l.unit_price} onChange={(e) => updateLine(i, { unit_price: e.target.value })} className="col-span-2 px-2 py-1 text-xs border border-stone-200 rounded bg-white text-right" />
              <div className="col-span-1 text-right text-xs font-semibold text-stone-800">£{(l.qty * l.unit_price).toFixed(0)}</div>
              <button onClick={() => removeLine(i)} data-testid={`sc-remove-line-${i}`} className="col-span-1 text-rose-500 hover:text-rose-700"><Trash size={12} /></button>
            </div>
          ))}
          {lines.length === 0 && (
            <div className="text-center py-6 text-stone-400 text-xs border border-dashed border-stone-200 rounded">
              Yukarıdan mekan, catering, oda bloku veya özel kalem ekleyin.
            </div>
          )}
        </div>

        {/* Totals */}
        <div className="border-t border-stone-200 pt-3 space-y-2 text-sm">
          <div className="flex justify-between text-stone-600">
            <span>Ara Toplam</span>
            <span>£{subtotal.toFixed(2)}</span>
          </div>
          <div className="flex justify-between items-center text-stone-600">
            <span className="flex items-center gap-2">
              İndirim %
              <input type="number" min={0} max={50} value={discountPct} onChange={(e) => setDiscountPct(e.target.value)} data-testid="sc-discount-pct" className="w-14 px-1 py-0.5 text-xs border border-stone-200 rounded" />
            </span>
            <span className="text-rose-600">-£{discountAmount.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-lg font-bold text-stone-900 border-t border-stone-100 pt-2">
            <span>Toplam</span>
            <span>£{total.toFixed(2)}</span>
          </div>
          {inq.total_attendees > 0 && (
            <div className="flex justify-between text-xs text-stone-500">
              <span>Kişi Başı</span>
              <span>£{perPerson.toFixed(2)}</span>
            </div>
          )}
        </div>

        <div className="grid md:grid-cols-2 gap-3 mt-3 pt-3 border-t border-stone-100">
          <div>
            <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">Geçerlilik Tarihi</label>
            <input type="date" value={validUntil} onChange={(e) => setValidUntil(e.target.value)} data-testid="sc-valid-until" className="w-full px-2 py-1 text-xs border border-stone-200 rounded-md" />
          </div>
          <div>
            <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">Notlar</label>
            <input value={notes} onChange={(e) => setNotes(e.target.value)} data-testid="sc-notes" placeholder="İç not veya misafire görünür açıklama" className="w-full px-2 py-1 text-xs border border-stone-200 rounded-md" />
          </div>
        </div>
      </div>
    </div>
  );
}

/* ==================== SETUP TAB ==================== */
function SetupTab({ propertyId }) {
  const [spaces, setSpaces] = useState([]);
  const [catering, setCatering] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [s, c] = await Promise.all([
        axios.get(`${API}/api/conference/event-spaces/${propertyId}`, { withCredentials: true }),
        axios.get(`${API}/api/conference/catering/${propertyId}`, { withCredentials: true }),
      ]);
      setSpaces(s.data.rows || []);
      setCatering(c.data.rows || []);
    } catch (e) {
      toast.error("Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId]);

  const seed = async () => {
    try {
      const r = await axios.post(`${API}/api/conference/event-spaces/${propertyId}/seed-defaults`, {}, { withCredentials: true });
      toast.success(`${r.data.seeded_spaces || 0} mekan + ${r.data.seeded_catering || 0} catering eklendi`);
      load();
    } catch (e) {
      toast.error("Seed başarısız");
    }
  };

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-xs text-stone-500">Mekan ve catering paketleri teklif yapıcısında kullanılır.</div>
        {(spaces.length === 0 || catering.length === 0) && (
          <button onClick={seed} data-testid="sc-seed-btn" className="px-3 py-1.5 text-xs rounded-md bg-sky-500 text-white hover:bg-sky-600 inline-flex items-center gap-1.5">
            <Sparkle size={12} />
            Varsayılanları Yükle
          </button>
        )}
      </div>

      {loading && <div className="text-sm text-stone-400">Yükleniyor…</div>}

      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <div className="text-sm font-semibold text-stone-800 mb-2 flex items-center gap-2">
            <CalendarBlank size={14} className="text-rose-500" />
            Mekanlar ({spaces.length})
          </div>
          <div className="space-y-2" data-testid="sc-spaces-list">
            {spaces.map((s) => (
              <div key={s.id} className="bg-white border border-stone-200 rounded-lg p-3">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="text-sm font-medium text-stone-900">{s.name}</div>
                    <div className="text-[11px] text-stone-500">{s.area_sqm} m²</div>
                    <div className="text-[11px] text-stone-600 mt-0.5">
                      {s.capacity_theater > 0 && `Tiyatro: ${s.capacity_theater}`}
                      {s.capacity_banquet > 0 && ` · Banket: ${s.capacity_banquet}`}
                      {s.capacity_boardroom > 0 && ` · Toplantı: ${s.capacity_boardroom}`}
                    </div>
                    {s.features?.length > 0 && (
                      <div className="flex gap-1 flex-wrap mt-1.5">
                        {s.features.map((f, i) => <span key={i} className="px-1.5 py-0.5 text-[9px] bg-rose-50 text-rose-700 rounded">{f}</span>)}
                      </div>
                    )}
                  </div>
                  <div className="text-right text-xs">
                    <div className="font-semibold text-stone-900">£{s.full_day_rate}</div>
                    <div className="text-[10px] text-stone-400">tam gün</div>
                    <div className="text-[10px] text-stone-400">½ gün £{s.half_day_rate}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="text-sm font-semibold text-stone-800 mb-2 flex items-center gap-2">
            <ForkKnife size={14} className="text-amber-500" />
            Catering ({catering.length})
          </div>
          <div className="space-y-2" data-testid="sc-catering-list">
            {catering.map((c) => (
              <div key={c.id} className="bg-white border border-stone-200 rounded-lg p-3">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="text-sm font-medium text-stone-900">{c.name}</div>
                    <div className="text-[11px] text-stone-500 capitalize">{c.category.replace("_", " ")} · min {c.min_persons} kişi</div>
                    {c.includes?.length > 0 && (
                      <div className="flex gap-1 flex-wrap mt-1.5">
                        {c.includes.map((x, i) => <span key={i} className="px-1.5 py-0.5 text-[9px] bg-amber-50 text-amber-700 rounded">{x}</span>)}
                      </div>
                    )}
                  </div>
                  <div className="text-right text-xs">
                    <div className="font-semibold text-stone-900">£{c.per_person_price}</div>
                    <div className="text-[10px] text-stone-400">/ kişi</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
