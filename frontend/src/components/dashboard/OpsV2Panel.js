import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Wrench,
  Sparkle,
  ClipboardText,
  Warning,
  CheckCircle,
  Plus,
  ArrowsClockwise,
  Camera,
  PlayCircle,
  PauseCircle,
  SealCheck,
  Drop,
  Broom,
  Headset,
} from "@phosphor-icons/react";
import { MaintenancePanel } from "./MaintenancePanel";

const API = process.env.REACT_APP_BACKEND_URL;

const LINEN_LABELS = {
  bed_sheet: "Çarşaf",
  towel_bath: "Banyo Havlusu",
  towel_face: "Yüz Havlusu",
  pillowcase: "Yastık Kılıfı",
  duvet: "Yorgan",
  tablecloth: "Masa Örtüsü",
};

const PRIORITY_COLORS = {
  critical: "bg-rose-100 text-rose-700 border-rose-200",
  high: "bg-amber-100 text-amber-700 border-amber-200",
  normal: "bg-sky-100 text-sky-700 border-sky-200",
  low: "bg-stone-100 text-stone-600 border-stone-200",
};

const STATUS_LABELS = {
  reported: "Rapor Edildi",
  assigned: "Atandı",
  in_progress: "Devam Ediyor",
  paused: "Duraklatıldı",
  completed: "Tamamlandı",
  verified: "Doğrulandı",
};

const STATUS_COLORS = {
  reported: "bg-stone-50 text-stone-700 border-stone-200",
  assigned: "bg-indigo-50 text-indigo-700 border-indigo-200",
  in_progress: "bg-sky-50 text-sky-700 border-sky-200",
  paused: "bg-amber-50 text-amber-700 border-amber-200",
  completed: "bg-emerald-50 text-emerald-700 border-emerald-200",
  verified: "bg-emerald-600 text-white border-emerald-700",
};

export default function OpsV2Panel({ propertyId, hotelName, properties }) {
  const [tab, setTab] = useState("requests");

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="ops-v2-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Wrench size={12} weight="fill" className="text-orange-500" />
          <span>Operasyon</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">
          Operasyon Merkezi
        </h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Misafir talepleri, bakım iş emirleri, çamaşır PAR ve HK denetimi — tek ekranda.
        </p>
      </div>

      <div className="flex gap-2 mb-5 border-b border-stone-200 overflow-x-auto">
        <TabBtn active={tab === "requests"} onClick={() => setTab("requests")} testId="ops-tab-requests">
          <Headset size={14} className="inline mr-1.5" />
          Misafir Talepleri
        </TabBtn>
        <TabBtn active={tab === "maintenance"} onClick={() => setTab("maintenance")} testId="ops-tab-maintenance">
          <Wrench size={14} className="inline mr-1.5" />
          Bakım İş Emirleri
        </TabBtn>
        <TabBtn active={tab === "linen"} onClick={() => setTab("linen")} testId="ops-tab-linen">
          <Drop size={14} className="inline mr-1.5" />
          Çamaşır PAR
        </TabBtn>
        <TabBtn active={tab === "inspection"} onClick={() => setTab("inspection")} testId="ops-tab-inspection">
          <ClipboardText size={14} className="inline mr-1.5" />
          HK Denetim
        </TabBtn>
      </div>

      {tab === "requests" && (
        <div className="-mx-5">
          <MaintenancePanel properties={properties} activePropertyId={propertyId} />
        </div>
      )}
      {tab === "maintenance" && <MaintenanceTab propertyId={propertyId} />}
      {tab === "linen" && <LinenTab propertyId={propertyId} />}
      {tab === "inspection" && <InspectionTab propertyId={propertyId} />}
    </div>
  );
}

function TabBtn({ active, onClick, children, testId }) {
  return (
    <button
      onClick={onClick}
      data-testid={testId}
      className={`px-3.5 py-2 text-sm font-medium transition-all border-b-2 -mb-px ${
        active
          ? "border-orange-500 text-orange-700"
          : "border-transparent text-stone-500 hover:text-stone-800"
      }`}
    >
      {children}
    </button>
  );
}

/* ==================== MAINTENANCE ==================== */
function MaintenanceTab({ propertyId }) {
  const [data, setData] = useState({ rows: [], counters: {}, critical_open: 0 });
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState("");
  const [showNew, setShowNew] = useState(false);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const url = filter
        ? `${API}/api/ops-v2/workorders/${propertyId}?status=${filter}`
        : `${API}/api/ops-v2/workorders/${propertyId}`;
      const r = await axios.get(url, { withCredentials: true });
      setData(r.data || { rows: [], counters: {}, critical_open: 0 });
    } catch (e) {
      toast.error("İş emirleri yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId, filter]);

  useEffect(() => { load(); }, [load]);

  const counters = data.counters || {};
  const totalOpen = (counters.reported || 0) + (counters.assigned || 0) + (counters.in_progress || 0);

  return (
    <div className="space-y-4">
      {/* KPI tiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi icon={Warning} color="rose" label="Kritik Açık" value={data.critical_open || 0} testId="ops-kpi-critical" />
        <Kpi icon={Wrench} color="orange" label="Açık Toplam" value={totalOpen} testId="ops-kpi-open" />
        <Kpi icon={CheckCircle} color="emerald" label="Tamamlandı" value={counters.completed || 0} testId="ops-kpi-completed" />
        <Kpi icon={SealCheck} color="indigo" label="Doğrulandı" value={counters.verified || 0} testId="ops-kpi-verified" />
      </div>

      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex gap-1.5 flex-wrap" data-testid="ops-status-filter">
          {["", "reported", "assigned", "in_progress", "completed", "verified"].map((s) => (
            <button
              key={s || "all"}
              onClick={() => setFilter(s)}
              data-testid={`ops-filter-${s || "all"}`}
              className={`px-2.5 py-1 text-xs rounded-full border transition-all ${
                filter === s
                  ? "bg-stone-900 text-white border-stone-900"
                  : "bg-white text-stone-600 border-stone-200 hover:border-stone-400"
              }`}
            >
              {s ? STATUS_LABELS[s] : "Tümü"}
            </button>
          ))}
        </div>
        <div className="flex gap-1.5">
          <button
            onClick={load}
            data-testid="ops-refresh-btn"
            className="px-3 py-1.5 text-xs rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50 inline-flex items-center gap-1.5"
          >
            <ArrowsClockwise size={13} />
            Yenile
          </button>
          <button
            onClick={() => setShowNew(true)}
            data-testid="ops-new-wo-btn"
            className="px-3 py-1.5 text-xs rounded-md bg-orange-500 text-white hover:bg-orange-600 inline-flex items-center gap-1.5"
          >
            <Plus size={13} weight="bold" />
            Yeni İş Emri
          </button>
        </div>
      </div>

      {showNew && (
        <NewWorkOrderForm
          propertyId={propertyId}
          onClose={() => setShowNew(false)}
          onSaved={() => { setShowNew(false); load(); }}
        />
      )}

      {loading && <div className="text-sm text-stone-400">Yükleniyor…</div>}

      {!loading && data.rows.length === 0 && (
        <div className="text-center py-10 text-stone-400 text-sm border border-dashed border-stone-200 rounded-lg">
          Bu filtrede iş emri yok.
        </div>
      )}

      <div className="space-y-2" data-testid="ops-wo-list">
        {data.rows.map((wo) => (
          <WorkOrderRow key={wo.id} wo={wo} onChanged={load} />
        ))}
      </div>
    </div>
  );
}

function Kpi({ icon: Icon, color, label, value, testId }) {
  const bg = {
    rose: "bg-rose-50 text-rose-600",
    orange: "bg-orange-50 text-orange-600",
    emerald: "bg-emerald-50 text-emerald-600",
    indigo: "bg-indigo-50 text-indigo-600",
    sky: "bg-sky-50 text-sky-600",
    amber: "bg-amber-50 text-amber-600",
    violet: "bg-violet-50 text-violet-600",
  }[color];
  return (
    <div className="bg-white border border-stone-200 rounded-lg p-3.5" data-testid={testId}>
      <div className="flex items-center gap-2 mb-1.5">
        <div className={`w-7 h-7 rounded-md inline-flex items-center justify-center ${bg}`}>
          <Icon size={14} weight="fill" />
        </div>
        <div className="text-[10px] uppercase tracking-wider text-stone-500">{label}</div>
      </div>
      <div className="text-2xl font-semibold text-stone-900">{value}</div>
    </div>
  );
}

function WorkOrderRow({ wo, onChanged }) {
  const [busy, setBusy] = useState(false);
  const act = async (action, extra = {}) => {
    setBusy(true);
    try {
      await axios.post(`${API}/api/ops-v2/workorders/${wo.id}/action`, { action, ...extra }, { withCredentials: true });
      toast.success(`İş emri: ${action}`);
      onChanged();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Hata");
    } finally {
      setBusy(false);
    }
  };

  const next = {
    reported: { label: "Ata (Bana)", action: "assign", icon: PlayCircle, color: "indigo" },
    assigned: { label: "Başla", action: "start", icon: PlayCircle, color: "sky" },
    in_progress: { label: "Tamamla", action: "complete", icon: CheckCircle, color: "emerald" },
    paused: { label: "Devam Et", action: "resume", icon: PlayCircle, color: "sky" },
    completed: { label: "Doğrula", action: "verify", icon: SealCheck, color: "emerald" },
  }[wo.status];

  return (
    <div className="bg-white border border-stone-200 rounded-lg p-3 hover:border-stone-300 transition-all" data-testid={`ops-wo-${wo.id}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className={`px-1.5 py-0.5 text-[10px] rounded border font-medium ${PRIORITY_COLORS[wo.priority] || PRIORITY_COLORS.normal}`}>
              {wo.priority?.toUpperCase()}
            </span>
            <span className={`px-1.5 py-0.5 text-[10px] rounded border font-medium ${STATUS_COLORS[wo.status] || STATUS_COLORS.reported}`}>
              {STATUS_LABELS[wo.status] || wo.status}
            </span>
            <span className="text-[10px] text-stone-400">{wo.category}</span>
            {wo.room_id && <span className="text-[10px] text-stone-500">· Oda {wo.room_id}</span>}
          </div>
          <div className="text-sm font-medium text-stone-900 truncate">{wo.title}</div>
          {wo.description && <div className="text-xs text-stone-500 mt-0.5 line-clamp-2">{wo.description}</div>}
          <div className="text-[10px] text-stone-400 mt-1">
            {wo.reported_by} · {wo.reported_at?.slice(0, 16).replace("T", " ")}
            {wo.assigned_to && ` → ${wo.assigned_to}`}
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          {next && (
            <button
              disabled={busy}
              onClick={() => act(next.action, next.action === "assign" ? { assigned_to: "me" } : {})}
              data-testid={`ops-wo-action-${wo.id}`}
              className={`px-2.5 py-1.5 text-[11px] rounded-md inline-flex items-center gap-1 font-medium transition-all disabled:opacity-50 ${
                next.color === "emerald" ? "bg-emerald-500 text-white hover:bg-emerald-600" :
                next.color === "sky" ? "bg-sky-500 text-white hover:bg-sky-600" :
                "bg-indigo-500 text-white hover:bg-indigo-600"
              }`}
            >
              <next.icon size={12} weight="bold" />
              {next.label}
            </button>
          )}
          {wo.status === "in_progress" && (
            <button
              disabled={busy}
              onClick={() => act("pause")}
              className="px-2.5 py-1.5 text-[11px] rounded-md inline-flex items-center gap-1 border border-stone-200 text-stone-600 hover:bg-stone-50 disabled:opacity-50"
            >
              <PauseCircle size={12} />
              Durdur
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function NewWorkOrderForm({ propertyId, onClose, onSaved }) {
  const [form, setForm] = useState({
    title: "",
    description: "",
    priority: "normal",
    category: "general",
    location: "",
    room_id: "",
  });
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!form.title.trim()) { toast.error("Başlık zorunlu"); return; }
    setBusy(true);
    try {
      await axios.post(`${API}/api/ops-v2/workorders`, { ...form, property_id: propertyId }, { withCredentials: true });
      toast.success("İş emri oluşturuldu");
      onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Kaydedilemedi");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-stone-50 border border-stone-200 rounded-lg p-4" data-testid="ops-new-wo-form">
      <div className="text-sm font-semibold text-stone-800 mb-3">Yeni İş Emri</div>
      <div className="grid md:grid-cols-2 gap-3">
        <Input label="Başlık" value={form.title} onChange={(v) => setForm({ ...form, title: v })} testId="ops-wo-title" />
        <Input label="Konum / Oda" value={form.location} onChange={(v) => setForm({ ...form, location: v })} testId="ops-wo-location" />
        <Select label="Öncelik" value={form.priority} onChange={(v) => setForm({ ...form, priority: v })}
          options={[["low", "Düşük"], ["normal", "Normal"], ["high", "Yüksek"], ["critical", "Kritik"]]}
          testId="ops-wo-priority"
        />
        <Select label="Kategori" value={form.category} onChange={(v) => setForm({ ...form, category: v })}
          options={[["general", "Genel"], ["plumbing", "Tesisat"], ["electrical", "Elektrik"], ["hvac", "HVAC"], ["it", "IT"], ["safety", "Güvenlik"], ["housekeeping", "Kat Hizmetleri"]]}
          testId="ops-wo-category"
        />
      </div>
      <div className="mt-3">
        <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">Açıklama</label>
        <textarea
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
          rows={2}
          data-testid="ops-wo-description"
          className="w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md focus:outline-none focus:border-stone-400"
        />
      </div>
      <div className="flex gap-2 mt-3 justify-end">
        <button onClick={onClose} className="px-3 py-1.5 text-xs rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50">İptal</button>
        <button
          onClick={submit}
          disabled={busy}
          data-testid="ops-wo-submit"
          className="px-3 py-1.5 text-xs rounded-md bg-orange-500 text-white hover:bg-orange-600 disabled:opacity-50"
        >
          {busy ? "Kaydediliyor…" : "Oluştur"}
        </button>
      </div>
    </div>
  );
}

function Input({ label, value, onChange, testId }) {
  return (
    <div>
      <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">{label}</label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        data-testid={testId}
        className="w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md focus:outline-none focus:border-stone-400"
      />
    </div>
  );
}

function Select({ label, value, onChange, options, testId }) {
  return (
    <div>
      <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        data-testid={testId}
        className="w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md focus:outline-none focus:border-stone-400 bg-white"
      >
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </div>
  );
}

/* ==================== LINEN ==================== */
function LinenTab({ propertyId }) {
  const [data, setData] = useState({ items: [], low_par_count: 0, low_par: [] });
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/ops-v2/linen/${propertyId}`, { withCredentials: true });
      setData(r.data || { items: [], low_par_count: 0, low_par: [] });
    } catch (e) {
      toast.error("Çamaşır verisi yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId]);

  const seed = async () => {
    try {
      const r = await axios.post(`${API}/api/ops-v2/linen/${propertyId}/seed-defaults`, {}, { withCredentials: true });
      toast.success(r.data.seeded ? `${r.data.seeded} varsayılan eklendi` : r.data.note);
      load();
    } catch (e) {
      toast.error("Seed başarısız");
    }
  };

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          {data.low_par_count > 0 && (
            <span className="px-2 py-1 text-xs rounded-full bg-rose-50 text-rose-700 border border-rose-200 inline-flex items-center gap-1" data-testid="linen-low-par-badge">
              <Warning size={12} />
              {data.low_par_count} kalem PAR altı
            </span>
          )}
          {data.items.length === 0 && !loading && (
            <span className="text-xs text-stone-400">Henüz yapılandırılmamış.</span>
          )}
        </div>
        <div className="flex gap-1.5">
          <button onClick={load} data-testid="linen-refresh-btn" className="px-3 py-1.5 text-xs rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50 inline-flex items-center gap-1.5">
            <ArrowsClockwise size={13} />
            Yenile
          </button>
          {data.items.length === 0 && (
            <button onClick={seed} data-testid="linen-seed-btn" className="px-3 py-1.5 text-xs rounded-md bg-sky-500 text-white hover:bg-sky-600 inline-flex items-center gap-1.5">
              <Sparkle size={13} />
              Varsayılan Yükle
            </button>
          )}
        </div>
      </div>

      {loading && <div className="text-sm text-stone-400">Yükleniyor…</div>}

      <div className="grid md:grid-cols-2 gap-3" data-testid="linen-items-list">
        {data.items.map((it) => (
          <LinenCard key={it.item_type} it={it} propertyId={propertyId} onChanged={load} />
        ))}
      </div>
    </div>
  );
}

function LinenCard({ it, propertyId, onChanged }) {
  const [busy, setBusy] = useState(false);
  const [showCycle, setShowCycle] = useState(false);
  const cycle = async (movement, qty) => {
    setBusy(true);
    try {
      await axios.post(`${API}/api/ops-v2/linen/cycle`, {
        property_id: propertyId,
        item_type: it.item_type,
        movement,
        qty,
      }, { withCredentials: true });
      toast.success(`${qty} ${movement}`);
      onChanged();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Hata");
    } finally {
      setBusy(false);
      setShowCycle(false);
    }
  };

  const total = it.total || 0;
  const cleanPct = total ? Math.round((it.clean / total) * 100) : 0;

  return (
    <div className={`bg-white border rounded-lg p-4 transition-all ${it.below_par ? "border-rose-300 shadow-sm shadow-rose-50" : "border-stone-200"}`} data-testid={`linen-card-${it.item_type}`}>
      <div className="flex items-start justify-between gap-2 mb-3">
        <div>
          <div className="text-sm font-semibold text-stone-900">{LINEN_LABELS[it.item_type] || it.item_type}</div>
          <div className="text-[10px] text-stone-500 mt-0.5">
            PAR {it.par_level} · Alt limit {it.reorder_threshold}
          </div>
        </div>
        {it.below_par && (
          <span className="px-1.5 py-0.5 text-[10px] rounded bg-rose-100 text-rose-700 border border-rose-200 font-medium">
            PAR ALTI
          </span>
        )}
      </div>

      <div className="grid grid-cols-4 gap-1.5 mb-3">
        <StateBox label="Temiz" value={it.clean} color="emerald" />
        <StateBox label="Kullanımda" value={it.in_use} color="sky" />
        <StateBox label="Kirli" value={it.dirty} color="amber" />
        <StateBox label="Yıkanıyor" value={it.washing} color="indigo" />
      </div>

      <div className="w-full bg-stone-100 rounded-full h-1.5 mb-1">
        <div className="bg-emerald-500 h-1.5 rounded-full transition-all" style={{ width: `${cleanPct}%` }} />
      </div>
      <div className="text-[10px] text-stone-500 mb-3">%{cleanPct} temiz oranı · toplam {total}</div>

      {!showCycle ? (
        <button
          onClick={() => setShowCycle(true)}
          data-testid={`linen-cycle-${it.item_type}`}
          className="w-full px-3 py-1.5 text-xs rounded-md border border-stone-200 text-stone-700 hover:bg-stone-50 inline-flex items-center justify-center gap-1.5"
        >
          <ArrowsClockwise size={12} />
          Döngü Hareketi
        </button>
      ) : (
        <CycleActions busy={busy} onCycle={cycle} onCancel={() => setShowCycle(false)} itemType={it.item_type} />
      )}
    </div>
  );
}

function StateBox({ label, value, color }) {
  const bg = {
    emerald: "bg-emerald-50 text-emerald-700",
    sky: "bg-sky-50 text-sky-700",
    amber: "bg-amber-50 text-amber-700",
    indigo: "bg-indigo-50 text-indigo-700",
  }[color];
  return (
    <div className={`${bg} rounded-md p-1.5 text-center`}>
      <div className="text-sm font-semibold">{value}</div>
      <div className="text-[9px] uppercase tracking-wider opacity-70">{label}</div>
    </div>
  );
}

function CycleActions({ busy, onCycle, onCancel, itemType }) {
  const [qty, setQty] = useState(5);
  const moves = [
    ["clean_to_in_use", "Temiz → Kullanım", "sky"],
    ["checkout_to_dirty", "Kullanım → Kirli", "amber"],
    ["dirty_to_washing", "Kirli → Yıkama", "indigo"],
    ["washing_to_clean", "Yıkama → Temiz", "emerald"],
    ["lost_or_damaged", "Kayıp/Hasar", "rose"],
  ];
  return (
    <div className="space-y-2 border-t border-stone-100 pt-2">
      <div className="flex items-center gap-2">
        <label className="text-[10px] uppercase tracking-wider text-stone-500">Adet</label>
        <input
          type="number"
          value={qty}
          onChange={(e) => setQty(parseInt(e.target.value) || 0)}
          data-testid={`linen-qty-${itemType}`}
          className="w-16 px-1.5 py-1 text-xs border border-stone-200 rounded-md focus:outline-none focus:border-stone-400"
        />
        <button onClick={onCancel} className="ml-auto text-[11px] text-stone-500 hover:text-stone-800">Kapat</button>
      </div>
      <div className="grid grid-cols-1 gap-1">
        {moves.map(([m, label, c]) => (
          <button
            key={m}
            disabled={busy || qty <= 0}
            onClick={() => onCycle(m, qty)}
            data-testid={`linen-move-${itemType}-${m}`}
            className={`px-2 py-1 text-[11px] rounded-md text-left transition-all disabled:opacity-40 ${
              c === "emerald" ? "bg-emerald-50 text-emerald-700 hover:bg-emerald-100" :
              c === "sky" ? "bg-sky-50 text-sky-700 hover:bg-sky-100" :
              c === "amber" ? "bg-amber-50 text-amber-700 hover:bg-amber-100" :
              c === "indigo" ? "bg-indigo-50 text-indigo-700 hover:bg-indigo-100" :
              "bg-rose-50 text-rose-700 hover:bg-rose-100"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

/* ==================== INSPECTION ==================== */
function InspectionTab({ propertyId }) {
  const [template, setTemplate] = useState([]);
  const [list, setList] = useState({ rows: [], total: 0, failed: 0, pass_rate: 0 });
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [t, l] = await Promise.all([
        axios.get(`${API}/api/ops-v2/inspection/template`, { withCredentials: true }),
        axios.get(`${API}/api/ops-v2/inspections/${propertyId}`, { withCredentials: true }),
      ]);
      setTemplate(t.data.default_checks || []);
      setList(l.data || { rows: [], total: 0, failed: 0, pass_rate: 0 });
    } catch (e) {
      toast.error("Denetim verisi yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <Kpi icon={ClipboardText} color="indigo" label="Toplam Denetim" value={list.total} testId="insp-kpi-total" />
        <Kpi icon={CheckCircle} color="emerald" label="Geçme Oranı" value={`%${list.pass_rate}`} testId="insp-kpi-pass" />
        <Kpi icon={Warning} color="rose" label="Başarısız" value={list.failed} testId="insp-kpi-failed" />
      </div>

      <div className="flex items-center justify-between">
        <div className="text-xs text-stone-500">Oda bazlı HK süpervizör denetimi.</div>
        <button
          onClick={() => setShowForm((v) => !v)}
          data-testid="insp-new-btn"
          className="px-3 py-1.5 text-xs rounded-md bg-orange-500 text-white hover:bg-orange-600 inline-flex items-center gap-1.5"
        >
          <Broom size={13} />
          {showForm ? "Kapat" : "Yeni Denetim"}
        </button>
      </div>

      {showForm && (
        <NewInspectionForm
          propertyId={propertyId}
          template={template}
          onSaved={() => { setShowForm(false); load(); }}
        />
      )}

      {loading && <div className="text-sm text-stone-400">Yükleniyor…</div>}

      <div className="space-y-2" data-testid="insp-history">
        {list.rows.length === 0 && !loading && (
          <div className="text-center py-10 text-stone-400 text-sm border border-dashed border-stone-200 rounded-lg">
            Henüz denetim kaydı yok.
          </div>
        )}
        {list.rows.map((r) => (
          <div key={r.id} className="bg-white border border-stone-200 rounded-lg p-3 flex items-center gap-3" data-testid={`insp-row-${r.id}`}>
            <div className={`w-9 h-9 rounded-md inline-flex items-center justify-center ${r.overall_pass ? "bg-emerald-50 text-emerald-600" : "bg-rose-50 text-rose-600"}`}>
              {r.overall_pass ? <CheckCircle size={16} weight="fill" /> : <Warning size={16} weight="fill" />}
            </div>
            <div className="flex-1">
              <div className="text-sm font-medium text-stone-900">Oda {r.room_id}</div>
              <div className="text-[11px] text-stone-500">
                {r.passed_count} geçti · {r.failed_count} başarısız · {r.inspected_by}
              </div>
            </div>
            <div className="text-[11px] text-stone-400">{r.inspected_at?.slice(0, 16).replace("T", " ")}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function NewInspectionForm({ propertyId, template, onSaved }) {
  const [roomId, setRoomId] = useState("");
  const [checks, setChecks] = useState(() => template.map((n) => ({ name: n, pass: true, notes: "" })));
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (template.length && checks.length === 0) {
      setChecks(template.map((n) => ({ name: n, pass: true, notes: "" })));
    }
    // eslint-disable-next-line
  }, [template]);

  const toggle = (i) => setChecks(checks.map((c, idx) => idx === i ? { ...c, pass: !c.pass } : c));
  const setNote = (i, v) => setChecks(checks.map((c, idx) => idx === i ? { ...c, notes: v } : c));

  const submit = async () => {
    if (!roomId.trim()) { toast.error("Oda numarası zorunlu"); return; }
    const failed = checks.filter((c) => !c.pass).length;
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/ops-v2/inspection`, {
        property_id: propertyId,
        room_id: roomId,
        checks,
        overall_pass: failed === 0,
      }, { withCredentials: true });
      toast.success(`Denetim kaydedildi (${r.data.passed_count} ✓ · ${r.data.failed_count} ✗)`);
      if (r.data.workorders_created?.length) {
        toast.info(`${r.data.workorders_created.length} otomatik iş emri açıldı`);
      }
      onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Kaydedilemedi");
    } finally {
      setBusy(false);
    }
  };

  const failedCount = checks.filter((c) => !c.pass).length;

  return (
    <div className="bg-stone-50 border border-stone-200 rounded-lg p-4" data-testid="insp-form">
      <div className="flex items-center gap-3 mb-3">
        <div className="flex-1">
          <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">Oda No / ID</label>
          <input
            value={roomId}
            onChange={(e) => setRoomId(e.target.value)}
            data-testid="insp-room-id"
            className="w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md focus:outline-none focus:border-stone-400"
            placeholder="Örn: 204"
          />
        </div>
        <div className="text-center">
          <div className={`text-2xl font-semibold ${failedCount === 0 ? "text-emerald-600" : "text-rose-600"}`}>
            {failedCount === 0 ? "✓" : failedCount}
          </div>
          <div className="text-[10px] uppercase tracking-wider text-stone-500">
            {failedCount === 0 ? "Tümü OK" : "Başarısız"}
          </div>
        </div>
      </div>

      <div className="space-y-1.5 mb-3" data-testid="insp-checks">
        {checks.map((c, i) => (
          <div key={i} className="bg-white border border-stone-200 rounded-md p-2.5 flex items-start gap-2">
            <button
              onClick={() => toggle(i)}
              data-testid={`insp-check-${i}`}
              className={`mt-0.5 w-5 h-5 rounded flex items-center justify-center border transition-all flex-shrink-0 ${
                c.pass
                  ? "bg-emerald-500 border-emerald-500 text-white"
                  : "bg-rose-500 border-rose-500 text-white"
              }`}
            >
              {c.pass ? "✓" : "✗"}
            </button>
            <div className="flex-1 min-w-0">
              <div className="text-sm text-stone-800">{c.name}</div>
              {!c.pass && (
                <input
                  value={c.notes}
                  onChange={(e) => setNote(i, e.target.value)}
                  placeholder="Neden başarısız? (otomatik iş emri açılır)"
                  data-testid={`insp-notes-${i}`}
                  className="w-full mt-1 px-2 py-1 text-xs border border-rose-200 rounded focus:outline-none focus:border-rose-400"
                />
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-end">
        <button
          onClick={submit}
          disabled={busy}
          data-testid="insp-submit"
          className="px-3 py-1.5 text-xs rounded-md bg-orange-500 text-white hover:bg-orange-600 disabled:opacity-50 inline-flex items-center gap-1.5"
        >
          <Camera size={13} />
          {busy ? "Kaydediliyor…" : "Denetimi Kaydet"}
        </button>
      </div>
    </div>
  );
}
