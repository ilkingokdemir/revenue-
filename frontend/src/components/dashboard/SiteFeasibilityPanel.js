import React, { useEffect, useState, useCallback, useMemo } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Buildings,
  ChartBar,
  ChartLine,
  ChartLineUp,
  Plus,
  Trash,
  Brain,
  ArrowsClockwise,
  CheckCircle,
  XCircle,
  Sparkle,
  Download,
  Money,
  Warning,
  TrendUp,
  TrendDown,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;
const fmt = (n, cur = "") =>
  typeof n === "number"
    ? `${n.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}${cur ? " " + cur : ""}`
    : "—";

const verdictColor = (v) =>
  ({
    fails: "bg-red-100 text-red-800 border-red-200",
    "on-the-line": "bg-amber-100 text-amber-800 border-amber-200",
    "marginal-pass": "bg-yellow-100 text-yellow-800 border-yellow-200",
    "comfortable-pass": "bg-emerald-100 text-emerald-800 border-emerald-200",
    "no-lease": "bg-stone-100 text-stone-700 border-stone-200",
  }[v] || "bg-stone-100 text-stone-700 border-stone-200");

const verdictLabel = (v) =>
  ({
    fails: "Hurdle'i geçmiyor",
    "on-the-line": "Sınırda",
    "marginal-pass": "Marjinal geçer",
    "comfortable-pass": "Rahat geçer",
    "no-lease": "Kira yok",
  }[v] || v);

const blank = {
  project_name: "",
  location: "",
  currency: "GBP",
  rooms: 30,
  target_adr: 88,
  target_occupancy_pct: 75,
  annual_lease_cost: 180000,
  lease_multiple_target: 4,
  ota_commission_pct: 15,
  wholesaler_share_pct: 10,
  wholesaler_haircut_pct: 10,
  ramp_up_months: 15,
  ramp_start_occupancy_pct: 40,
  comp_set: [],
  notes: "",
};

export default function SiteFeasibilityPanel({ propertyId }) {
  const [studies, setStudies] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [active, setActive] = useState(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState(blank);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState("hurdle");

  const reload = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/feasibility/analyses/${propertyId}`, {
        withCredentials: true,
      });
      setStudies(r.data.items || []);
      if ((r.data.items || []).length && !activeId) {
        setActiveId(r.data.items[0].id);
      }
    } catch (e) {
      toast.error("Çalışmalar yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId, activeId]);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => {
    if (!activeId) return;
    (async () => {
      try {
        const r = await axios.get(`${API}/api/feasibility/analysis/${activeId}`, {
          withCredentials: true,
        });
        setActive(r.data);
      } catch (e) {
        toast.error("Detay yüklenemedi");
      }
    })();
  }, [activeId]);

  const submitNew = async () => {
    if (!form.project_name || !form.location) {
      toast.error("Proje adı ve lokasyon gerekli");
      return;
    }
    setBusy(true);
    try {
      const r = await axios.post(
        `${API}/api/feasibility/analysis`,
        { ...form, property_id: propertyId },
        { withCredentials: true }
      );
      toast.success("Fizibilite çalışması oluşturuldu");
      setCreating(false);
      setForm(blank);
      setActiveId(r.data.id);
      reload();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Oluşturulamadı");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Bu çalışma silinsin mi?")) return;
    try {
      await axios.delete(`${API}/api/feasibility/analysis/${id}`, { withCredentials: true });
      toast.success("Silindi");
      if (activeId === id) {
        setActiveId(null);
        setActive(null);
      }
      reload();
    } catch (e) {
      toast.error("Silinemedi");
    }
  };

  const generateVerdict = async () => {
    if (!activeId) return;
    setBusy(true);
    try {
      const r = await axios.post(
        `${API}/api/feasibility/analysis/${activeId}/verdict`,
        {},
        { withCredentials: true }
      );
      if (r.data?.available === false) {
        toast.error(r.data.narrative || "AI verdict başarısız");
      } else {
        toast.success("AI verdict hazırlandı");
      }
      const fresh = await axios.get(`${API}/api/feasibility/analysis/${activeId}`, {
        withCredentials: true,
      });
      setActive(fresh.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Verdict alınamadı");
    } finally {
      setBusy(false);
    }
  };

  const triggerScrape = async () => {
    if (!activeId) return;
    setBusy(true);
    try {
      await axios.post(
        `${API}/api/feasibility/analysis/${activeId}/scrape`,
        {},
        { withCredentials: true }
      );
      const r = await axios.get(`${API}/api/feasibility/analysis/${activeId}`, {
        withCredentials: true,
      });
      setActive(r.data);
      toast.success("Comp-set yenilendi (mock scrape)");
    } catch (e) {
      toast.error("Scrape başarısız");
    } finally {
      setBusy(false);
    }
  };

  const downloadPDF = async () => {
    if (!activeId) return;
    try {
      const r = await axios.get(`${API}/api/feasibility/analysis/${activeId}/pdf`, {
        withCredentials: true,
        responseType: "blob",
      });
      const url = URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `feasibility-${active?.project_name || "study"}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success("PDF indirildi");
    } catch (e) {
      toast.error("PDF üretilemedi");
    }
  };

  const addComp = () =>
    setForm((f) => ({
      ...f,
      comp_set: [...f.comp_set, { name: "", booking_url: "", rooms: 0, adr: 0, occupancy_pct: 0, excluded: false }],
    }));

  const updateComp = (i, k, v) =>
    setForm((f) => ({
      ...f,
      comp_set: f.comp_set.map((c, idx) => (idx === i ? { ...c, [k]: v } : c)),
    }));

  const removeComp = (i) =>
    setForm((f) => ({
      ...f,
      comp_set: f.comp_set.filter((_, idx) => idx !== i),
    }));

  const num = (v) => (v === "" || v === null ? "" : Number(v));

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="feasibility-panel">
      {/* Header */}
      <div className="mb-5 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <ChartLineUp size={12} weight="fill" className="text-indigo-500" />
            <span>Strategy · Investor Analysis</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">Site Feasibility & Investor Analysis</h1>
          <p className="text-sm text-stone-500 mt-1 max-w-2xl">
            Booking.com tarzı comp-set, 4× kira testi, doluluk sensitivity, Y1 rampa,
            wholesaler haircut riski ve AI investor verdict — hepsi tek PDF.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => {
              setCreating(true);
              setForm(blank);
            }}
            className="px-3 py-2 bg-indigo-600 text-white rounded-md text-sm font-medium hover:bg-indigo-700 flex items-center gap-2"
            data-testid="feasibility-new-btn"
          >
            <Plus size={14} weight="bold" /> Yeni çalışma
          </button>
          <button
            onClick={reload}
            className="px-3 py-2 bg-stone-100 text-stone-700 rounded-md text-sm hover:bg-stone-200 flex items-center gap-2"
            data-testid="feasibility-refresh-btn"
          >
            <ArrowsClockwise size={14} /> Yenile
          </button>
        </div>
      </div>

      {/* New form */}
      {creating && (
        <div className="mb-6 border border-stone-200 rounded-lg bg-white p-5" data-testid="feasibility-form">
          <h2 className="text-base font-semibold mb-4 text-stone-800">Yeni Fizibilite Çalışması</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Field label="Proje adı" v={form.project_name} setV={(v) => setForm({ ...form, project_name: v })} testId="field-project" />
            <Field label="Lokasyon" v={form.location} setV={(v) => setForm({ ...form, location: v })} testId="field-location" />
            <Field label="Para birimi" v={form.currency} setV={(v) => setForm({ ...form, currency: v })} testId="field-currency" />
            <Field type="number" label="Oda sayısı" v={form.rooms} setV={(v) => setForm({ ...form, rooms: num(v) })} testId="field-rooms" />
            <Field type="number" label="Hedef ADR" v={form.target_adr} setV={(v) => setForm({ ...form, target_adr: num(v) })} testId="field-adr" />
            <Field type="number" label="Hedef doluluk %" v={form.target_occupancy_pct} setV={(v) => setForm({ ...form, target_occupancy_pct: num(v) })} testId="field-occ" />
            <Field type="number" label="Yıllık kira" v={form.annual_lease_cost} setV={(v) => setForm({ ...form, annual_lease_cost: num(v) })} testId="field-lease" />
            <Field type="number" label="Hurdle çarpanı (×)" v={form.lease_multiple_target} setV={(v) => setForm({ ...form, lease_multiple_target: num(v) })} testId="field-mult" />
            <Field type="number" label="OTA komisyon %" v={form.ota_commission_pct} setV={(v) => setForm({ ...form, ota_commission_pct: num(v) })} testId="field-ota" />
            <Field type="number" label="Wholesaler payı %" v={form.wholesaler_share_pct} setV={(v) => setForm({ ...form, wholesaler_share_pct: num(v) })} testId="field-ws-share" />
            <Field type="number" label="Wholesaler haircut %" v={form.wholesaler_haircut_pct} setV={(v) => setForm({ ...form, wholesaler_haircut_pct: num(v) })} testId="field-ws-cut" />
            <Field type="number" label="Rampa süresi (ay)" v={form.ramp_up_months} setV={(v) => setForm({ ...form, ramp_up_months: num(v) })} testId="field-ramp" />
            <Field type="number" label="Rampa başlangıç doluluk %" v={form.ramp_start_occupancy_pct} setV={(v) => setForm({ ...form, ramp_start_occupancy_pct: num(v) })} testId="field-ramp-start" />
          </div>

          {/* Comp set */}
          <div className="mt-5">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-stone-700">Comp set (rakip oteller)</h3>
              <button
                onClick={addComp}
                className="text-xs text-indigo-600 hover:underline flex items-center gap-1"
                data-testid="feasibility-add-comp"
              >
                <Plus size={12} /> Rakip ekle
              </button>
            </div>
            {form.comp_set.length === 0 && (
              <p className="text-xs text-stone-400 italic">Henüz rakip eklenmedi.</p>
            )}
            {form.comp_set.map((c, i) => (
              <div key={i} className="grid grid-cols-1 md:grid-cols-6 gap-2 items-center mb-2 p-2 bg-stone-50 rounded">
                <input
                  className="text-sm border border-stone-200 rounded px-2 py-1.5 col-span-2"
                  placeholder="Otel adı"
                  value={c.name}
                  onChange={(e) => updateComp(i, "name", e.target.value)}
                  data-testid={`comp-name-${i}`}
                />
                <input
                  type="number"
                  className="text-sm border border-stone-200 rounded px-2 py-1.5"
                  placeholder="Oda"
                  value={c.rooms || ""}
                  onChange={(e) => updateComp(i, "rooms", num(e.target.value))}
                  data-testid={`comp-rooms-${i}`}
                />
                <input
                  type="number"
                  className="text-sm border border-stone-200 rounded px-2 py-1.5"
                  placeholder="ADR"
                  value={c.adr || ""}
                  onChange={(e) => updateComp(i, "adr", num(e.target.value))}
                  data-testid={`comp-adr-${i}`}
                />
                <input
                  type="number"
                  className="text-sm border border-stone-200 rounded px-2 py-1.5"
                  placeholder="Doluluk %"
                  value={c.occupancy_pct || ""}
                  onChange={(e) => updateComp(i, "occupancy_pct", num(e.target.value))}
                  data-testid={`comp-occ-${i}`}
                />
                <button
                  onClick={() => removeComp(i)}
                  className="text-stone-400 hover:text-red-600 self-center"
                  data-testid={`comp-remove-${i}`}
                >
                  <Trash size={16} />
                </button>
              </div>
            ))}
          </div>

          <div className="mt-4">
            <label className="text-xs text-stone-500 mb-1 block">Notlar</label>
            <textarea
              className="w-full text-sm border border-stone-200 rounded px-3 py-2"
              rows={2}
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              data-testid="field-notes"
            />
          </div>

          <div className="mt-5 flex gap-2 justify-end">
            <button
              onClick={() => setCreating(false)}
              className="px-3 py-2 bg-stone-100 text-stone-700 rounded text-sm hover:bg-stone-200"
              data-testid="feasibility-cancel"
            >
              Vazgeç
            </button>
            <button
              onClick={submitNew}
              disabled={busy}
              className="px-4 py-2 bg-indigo-600 text-white rounded text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
              data-testid="feasibility-submit"
            >
              {busy ? "Hesaplanıyor…" : "Çalışmayı oluştur"}
            </button>
          </div>
        </div>
      )}

      {/* List + detail */}
      <div className="grid grid-cols-1 md:grid-cols-[280px_1fr] gap-5">
        {/* List */}
        <aside className="border border-stone-200 rounded-lg bg-white p-3 h-fit">
          <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-2">
            Çalışmalar ({studies.length})
          </h3>
          {loading && <p className="text-xs text-stone-400">Yükleniyor…</p>}
          {!loading && studies.length === 0 && (
            <p className="text-xs text-stone-400 italic">Henüz çalışma yok.</p>
          )}
          <ul className="space-y-1" data-testid="feasibility-list">
            {studies.map((s) => (
              <li key={s.id}>
                <button
                  onClick={() => setActiveId(s.id)}
                  className={`w-full text-left px-3 py-2 rounded text-sm hover:bg-stone-100 transition ${
                    activeId === s.id ? "bg-indigo-50 text-indigo-800 ring-1 ring-indigo-200" : ""
                  }`}
                  data-testid={`feasibility-item-${s.id}`}
                >
                  <div className="font-medium truncate">{s.project_name}</div>
                  <div className="text-[11px] text-stone-500 flex items-center gap-1">
                    <span>{s.location}</span>
                    <span>·</span>
                    <span
                      className={`inline-block px-1.5 py-0 rounded text-[10px] border ${verdictColor(
                        s.hurdle?.verdict
                      )}`}
                    >
                      {verdictLabel(s.hurdle?.verdict)}
                    </span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        {/* Detail */}
        <main className="space-y-4">
          {!active && !loading && (
            <div className="bg-stone-50 border border-dashed border-stone-200 rounded-lg p-12 text-center text-stone-400 text-sm">
              Sol listeden bir çalışma seç veya yeni bir tane oluştur.
            </div>
          )}

          {active && (
            <>
              {/* Top KPI strip */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="feasibility-kpis">
                <Kpi label="Yıllık ciro" value={fmt(active.hurdle?.annual_turnover, active.currency)} icon={Money} />
                <Kpi label={`Hurdle (${active.lease_multiple_target}×)`} value={fmt(active.hurdle?.hurdle_target, active.currency)} icon={ChartBar} />
                <Kpi
                  label="Headroom"
                  value={fmt(active.hurdle?.headroom, active.currency)}
                  icon={active.hurdle?.headroom >= 0 ? TrendUp : TrendDown}
                  tone={active.hurdle?.headroom >= 0 ? "ok" : "bad"}
                />
                <Kpi label="Per-key revenue" value={fmt(active.per_key_revenue, active.currency)} icon={Buildings} />
              </div>

              {/* Verdict */}
              <div className="bg-white border border-stone-200 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Sparkle size={16} className="text-amber-500" weight="fill" />
                    <h2 className="font-semibold text-stone-800 text-sm">AI Investor Verdict</h2>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full border ${verdictColor(
                        active.hurdle?.verdict
                      )}`}
                    >
                      {verdictLabel(active.hurdle?.verdict)}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={generateVerdict}
                      disabled={busy}
                      className="text-xs px-3 py-1.5 bg-violet-600 text-white rounded hover:bg-violet-700 disabled:opacity-50 flex items-center gap-1"
                      data-testid="feasibility-verdict-btn"
                    >
                      <Brain size={12} /> {busy ? "Üretiliyor…" : "AI verdict üret"}
                    </button>
                    <button
                      onClick={downloadPDF}
                      className="text-xs px-3 py-1.5 bg-stone-800 text-white rounded hover:bg-black flex items-center gap-1"
                      data-testid="feasibility-pdf-btn"
                    >
                      <Download size={12} /> Investor PDF
                    </button>
                    <button
                      onClick={() => remove(active.id)}
                      className="text-xs px-3 py-1.5 bg-red-50 text-red-700 rounded hover:bg-red-100"
                      data-testid="feasibility-delete-btn"
                    >
                      Sil
                    </button>
                  </div>
                </div>
                {active.verdict_narrative ? (
                  <p className="text-sm text-stone-700 leading-relaxed bg-amber-50 border border-amber-100 rounded p-3" data-testid="feasibility-verdict-text">
                    {active.verdict_narrative}
                  </p>
                ) : (
                  <p className="text-xs text-stone-400 italic">
                    Henüz AI verdict üretilmedi. "AI verdict üret" butonuna basın.
                  </p>
                )}
              </div>

              {/* Tabs */}
              <div className="bg-white border border-stone-200 rounded-lg">
                <div className="flex border-b border-stone-200 overflow-x-auto">
                  {[
                    ["hurdle", "Hurdle test"],
                    ["sensitivity", "Sensitivity"],
                    ["compset", "Comp set"],
                    ["ota", "OTA / Wholesaler"],
                    ["ramp", "Y1 Rampa"],
                    ["adr", "ADR Curve"],
                  ].map(([k, l]) => (
                    <button
                      key={k}
                      onClick={() => setTab(k)}
                      className={`px-4 py-2 text-sm border-b-2 ${
                        tab === k
                          ? "border-indigo-600 text-indigo-700 font-medium"
                          : "border-transparent text-stone-500 hover:text-stone-800"
                      }`}
                      data-testid={`feasibility-tab-${k}`}
                    >
                      {l}
                    </button>
                  ))}
                </div>
                <div className="p-4">
                  {tab === "hurdle" && <HurdleView a={active} />}
                  {tab === "sensitivity" && <SensitivityView a={active} />}
                  {tab === "compset" && <CompSetView a={active} onRescrape={triggerScrape} busy={busy} />}
                  {tab === "ota" && <OtaView a={active} />}
                  {tab === "ramp" && <RampView a={active} />}
                  {tab === "adr" && <AdrView a={active} />}
                </div>
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}

const Field = ({ label, v, setV, type = "text", testId }) => (
  <div>
    <label className="text-xs text-stone-500 mb-1 block">{label}</label>
    <input
      type={type}
      value={v}
      onChange={(e) => setV(e.target.value)}
      className="w-full text-sm border border-stone-200 rounded px-3 py-1.5"
      data-testid={testId}
    />
  </div>
);

const Kpi = ({ label, value, icon: Icon, tone }) => (
  <div
    className={`bg-white border rounded-lg p-3 ${
      tone === "ok"
        ? "border-emerald-200"
        : tone === "bad"
        ? "border-red-200"
        : "border-stone-200"
    }`}
  >
    <div className="flex items-center justify-between text-stone-500 mb-1">
      <span className="text-[10px] uppercase tracking-wide">{label}</span>
      {Icon && <Icon size={14} />}
    </div>
    <div className="text-lg font-semibold text-stone-900">{value}</div>
  </div>
);

const HurdleView = ({ a }) => {
  const h = a.hurdle || {};
  const pct = h.hurdle_target ? Math.max(0, Math.min(100, (h.annual_turnover / h.hurdle_target) * 100)) : 0;
  return (
    <div data-testid="feasibility-hurdle-view">
      <div className="mb-3">
        <div className="flex justify-between text-xs text-stone-600 mb-1">
          <span>Ciro / Hurdle</span>
          <span className="font-mono">{pct.toFixed(1)}%</span>
        </div>
        <div className="w-full h-3 rounded bg-stone-100 overflow-hidden">
          <div
            className={`h-full ${
              h.verdict === "fails"
                ? "bg-red-500"
                : h.verdict === "on-the-line"
                ? "bg-amber-500"
                : h.verdict === "marginal-pass"
                ? "bg-yellow-500"
                : "bg-emerald-500"
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
      <table className="w-full text-sm">
        <tbody>
          <Row k="Yıllık ciro" v={fmt(h.annual_turnover, a.currency)} />
          <Row k="Yıllık kira" v={fmt(h.lease_cost, a.currency)} />
          <Row k={`Hurdle hedef (${a.lease_multiple_target}×)`} v={fmt(h.hurdle_target, a.currency)} />
          <Row k="Headroom" v={fmt(h.headroom, a.currency)} bold />
          <Row k="Lease multiple" v={h.lease_multiple ? `${h.lease_multiple}×` : "—"} />
          <Row k="Verdict" v={verdictLabel(h.verdict)} />
        </tbody>
      </table>
    </div>
  );
};

const SensitivityView = ({ a }) => (
  <div data-testid="feasibility-sensitivity-view">
    <p className="text-xs text-stone-500 mb-2">
      Hedef doluluk ±5pp aralığı; her senaryo için yıllık ciro ve hurdle headroom.
    </p>
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-xs text-stone-500 border-b border-stone-200">
          <th className="py-1 pr-2">Δ pp</th>
          <th className="py-1 pr-2">Doluluk</th>
          <th className="py-1 pr-2">Yıllık ciro</th>
          <th className="py-1 pr-2">Headroom</th>
          <th className="py-1 pr-2">Geçer mi?</th>
        </tr>
      </thead>
      <tbody>
        {(a.sensitivity || []).map((s, i) => (
          <tr key={i} className={`border-b border-stone-100 ${s.passes ? "" : "bg-red-50"}`}>
            <td className="py-1 pr-2 font-mono text-xs">{s.delta_pp >= 0 ? `+${s.delta_pp}` : s.delta_pp}</td>
            <td className="py-1 pr-2">{s.occupancy_pct}%</td>
            <td className="py-1 pr-2">{fmt(s.annual_turnover, a.currency)}</td>
            <td className="py-1 pr-2">{fmt(s.headroom, a.currency)}</td>
            <td className="py-1 pr-2">
              {s.passes ? (
                <CheckCircle size={14} className="text-emerald-600" weight="fill" />
              ) : (
                <XCircle size={14} className="text-red-600" weight="fill" />
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

const CompSetView = ({ a, onRescrape, busy }) => {
  const cs = a.scrape || {};
  return (
    <div data-testid="feasibility-compset-view">
      <div className="flex justify-between items-center mb-3">
        <p className="text-xs text-stone-500">
          Comp-set scrape window: {cs.scrape_window} · Source: {cs.source}
        </p>
        <button
          onClick={onRescrape}
          disabled={busy}
          className="text-xs px-3 py-1 bg-stone-800 text-white rounded hover:bg-black disabled:opacity-50 flex items-center gap-1"
          data-testid="feasibility-rescrape"
        >
          <ArrowsClockwise size={12} /> {busy ? "Tarıyor…" : "Yeniden tara"}
        </button>
      </div>
      {(!cs.comp_results || cs.comp_results.length === 0) && (
        <p className="text-xs italic text-stone-400">Henüz comp-set yok. Yeni çalışmaya rakip ekleyin.</p>
      )}
      {cs.comp_results && cs.comp_results.length > 0 && (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-stone-500 border-b border-stone-200">
              <th className="py-1 pr-2">Otel</th>
              <th className="py-1 pr-2">Oda</th>
              <th className="py-1 pr-2">Tahmini ADR</th>
              <th className="py-1 pr-2">Tahmini Doluluk</th>
              <th className="py-1 pr-2">RevPAR</th>
            </tr>
          </thead>
          <tbody>
            {cs.comp_results.map((c, i) => (
              <tr key={i} className="border-b border-stone-100">
                <td className="py-1 pr-2 font-medium">{c.name}</td>
                <td className="py-1 pr-2">{c.rooms || "—"}</td>
                <td className="py-1 pr-2">{fmt(c.estimated_adr, a.currency)}</td>
                <td className="py-1 pr-2">{c.estimated_occupancy_pct}% ±{c.confidence_band_pp}pp</td>
                <td className="py-1 pr-2">{fmt(c.revpar, a.currency)}</td>
              </tr>
            ))}
            <tr className="font-semibold bg-stone-50">
              <td className="py-1 pr-2">ORTALAMA</td>
              <td>—</td>
              <td className="py-1 pr-2">{fmt(cs.comp_avg_adr, a.currency)}</td>
              <td className="py-1 pr-2">{cs.comp_avg_occupancy}%</td>
              <td>—</td>
            </tr>
          </tbody>
        </table>
      )}
    </div>
  );
};

const OtaView = ({ a }) => {
  const o = a.ota_risk || {};
  return (
    <div data-testid="feasibility-ota-view">
      <p className="text-xs text-stone-500 mb-3 flex items-center gap-1">
        <Warning size={14} className="text-amber-500" />
        Wholesaler haircut + OTA komisyonu sonrası net ciro ve hurdle durumu.
      </p>
      <table className="w-full text-sm">
        <tbody>
          <Row k="Baz ciro" v={fmt(o.base_turnover, a.currency)} />
          <Row k="Wholesaler payı" v={`${o.wholesaler_share_pct}%`} />
          <Row k="Wholesaler haircut" v={`${o.wholesaler_haircut_pct}%`} />
          <Row k="Wholesaler kaybı" v={fmt(o.revenue_loss_to_wholesaler, a.currency)} />
          <Row k="OTA komisyonu" v={fmt(o.ota_commission_loss, a.currency)} />
          <Row k="Haircut sonrası ciro" v={fmt(o.turnover_after_haircut, a.currency)} bold />
          <Row k="Komisyon sonrası net" v={fmt(o.net_after_commission, a.currency)} />
          <Row k="Haircut sonrası headroom" v={fmt(o.headroom_after_haircut, a.currency)} bold />
          <Row
            k="Hala hurdle'i geçer mi?"
            v={
              o.still_passes ? (
                <span className="text-emerald-600 font-medium">EVET</span>
              ) : (
                <span className="text-red-600 font-medium">HAYIR</span>
              )
            }
          />
        </tbody>
      </table>
    </div>
  );
};

const RampView = ({ a }) => {
  const r = a.ramp_up || {};
  return (
    <div data-testid="feasibility-ramp-view">
      <p className="text-xs text-stone-500 mb-3">{r.explanation}</p>
      <div className="text-sm font-semibold text-amber-700 mb-3">
        Working capital gerekli: {fmt(r.working_capital_required, a.currency)}
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-stone-500 border-b border-stone-200">
            <th className="py-1 pr-2">Ay</th>
            <th className="py-1 pr-2">Doluluk</th>
            <th className="py-1 pr-2">Gelir</th>
            <th className="py-1 pr-2">OPEX</th>
            <th className="py-1 pr-2">Kira</th>
            <th className="py-1 pr-2">Net</th>
          </tr>
        </thead>
        <tbody>
          {(r.schedule || []).map((s) => (
            <tr key={s.month} className={`border-b border-stone-100 ${s.net < 0 ? "bg-red-50" : ""}`}>
              <td className="py-1 pr-2">{s.month}</td>
              <td className="py-1 pr-2">{s.occupancy_pct}%</td>
              <td className="py-1 pr-2">{fmt(s.revenue, a.currency)}</td>
              <td className="py-1 pr-2">{fmt(s.opex, a.currency)}</td>
              <td className="py-1 pr-2">{fmt(s.lease, a.currency)}</td>
              <td className={`py-1 pr-2 font-mono ${s.net < 0 ? "text-red-600" : "text-emerald-700"}`}>
                {fmt(s.net, a.currency)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const AdrView = ({ a }) => {
  const c = a.adr_curve || {};
  const max = useMemo(
    () => {
      const vals = Object.values(c.by_dow || {});
      return vals.length ? Math.max(...vals) : 1;
    },
    [c.by_dow]
  );
  return (
    <div data-testid="feasibility-adr-view">
      <p className="text-xs text-stone-500 mb-3">{c.note}</p>
      <div className="grid grid-cols-7 gap-2 mb-4 items-end h-40">
        {Object.entries(c.by_dow || {}).map(([d, v]) => (
          <div key={d} className="flex flex-col items-center justify-end h-full">
            <div className="text-[10px] font-mono text-stone-500 mb-1">{v}</div>
            <div
              className="w-full bg-indigo-500 rounded-t"
              style={{ height: `${(v / (max || 1)) * 100}%` }}
            />
            <div className="text-[10px] text-stone-600 mt-1">{d}</div>
          </div>
        ))}
      </div>
      <div className="text-xs text-stone-600">
        Haftalık ortalama ADR: <b>{fmt(c.weekly_avg, a.currency)}</b>
      </div>
    </div>
  );
};

const Row = ({ k, v, bold }) => (
  <tr className="border-b border-stone-100 last:border-0">
    <td className="py-1.5 pr-2 text-stone-500 text-xs uppercase tracking-wide">{k}</td>
    <td className={`py-1.5 ${bold ? "font-semibold text-stone-900" : "text-stone-800"}`}>{v}</td>
  </tr>
);
