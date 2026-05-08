import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Calculator,
  Lightning,
  Plus,
  Trash,
  Play,
  ArrowsClockwise,
  Calculator as CalcIcon,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

const CHANNEL_LABELS = {
  "direct": "Direkt Web",
  "booking.com": "Booking.com",
  "expedia": "Expedia",
  "airbnb": "Airbnb",
  "corporate": "Kurumsal",
  "agent": "Travel Agent",
};

export default function ChannelRevenuePanel({ propertyId, hotelName }) {
  const [tab, setTab] = useState("pricing");

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="channel-revenue-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Lightning size={12} weight="fill" className="text-amber-500" />
          <span>Açık Fiyatlama & Yield</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">
          Kanal Geliri Motoru · {hotelName || "Property"}
        </h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Her kanala farklı fiyat + if-then yield kuralları. Duetto/IDeaS seviyesi ama basitleştirilmiş.
        </p>
      </div>

      <div className="flex gap-2 mb-5 border-b border-stone-200">
        <TabBtn active={tab === "pricing"} onClick={() => setTab("pricing")} testId="cr-tab-pricing">
          <Calculator size={14} className="inline mr-1.5" />
          Açık Fiyatlama
        </TabBtn>
        <TabBtn active={tab === "rules"} onClick={() => setTab("rules")} testId="cr-tab-rules">
          <Lightning size={14} className="inline mr-1.5" />
          Yield Kuralları
        </TabBtn>
      </div>

      {tab === "pricing" && <PricingTab propertyId={propertyId} />}
      {tab === "rules" && <RulesTab propertyId={propertyId} />}
    </div>
  );
}

function TabBtn({ active, onClick, children, testId }) {
  return (
    <button
      onClick={onClick}
      data-testid={testId}
      className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition ${
        active
          ? "border-amber-500 text-amber-600"
          : "border-transparent text-stone-500 hover:text-stone-700"
      }`}
    >
      {children}
    </button>
  );
}

function PricingTab({ propertyId }) {
  const [channels, setChannels] = useState([]);
  const [quote, setQuote] = useState(null);
  const [busy, setBusy] = useState(false);
  const [quoteForm, setQuoteForm] = useState({
    channel: "booking.com",
    check_in: new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10),
    nights: 1,
  });

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/api/channel-revenue/channels/${propertyId}`);
      setChannels(data.channels || []);
    } catch (_) { /* silent */ }
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const updateCh = async (ch, patch) => {
    try {
      await axios.put(`${API}/api/channel-revenue/channels/${propertyId}/${encodeURIComponent(ch)}`, {
        property_id: propertyId, channel: ch, ...patch,
      });
      toast.success(`${CHANNEL_LABELS[ch] || ch} güncellendi`);
      load();
    } catch (_) { toast.error("Güncelleme başarısız"); }
  };

  const runQuote = async () => {
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/api/channel-revenue/quote`, {
        property_id: propertyId, ...quoteForm,
      });
      setQuote(data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Quote başarısız");
    }
    setBusy(false);
  };

  return (
    <div className="space-y-5" data-testid="channel-pricing-tab">
      {/* Channels grid */}
      <div>
        <h3 className="text-sm font-semibold text-stone-900 mb-3">Kanal Fiyat Çarpanları</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {channels.map((c) => (
            <div key={c.channel} className="p-4 rounded-xl bg-white border border-stone-200"
              data-testid={`channel-${c.channel}`}>
              <div className="flex items-center justify-between mb-3">
                <div className="font-semibold text-stone-900">{CHANNEL_LABELS[c.channel] || c.channel}</div>
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-mono ${
                  c.base_multiplier > 1 ? "bg-amber-100 text-amber-700" :
                  c.base_multiplier < 1 ? "bg-sky-100 text-sky-700" :
                  "bg-stone-100 text-stone-700"
                }`}>
                  ×{c.base_multiplier?.toFixed(2)}
                </span>
              </div>
              <div className="space-y-2 text-xs">
                <NumRow
                  label="Çarpan"
                  value={c.base_multiplier}
                  step={0.05}
                  min={0.5}
                  max={2}
                  onSave={(v) => updateCh(c.channel, { base_multiplier: v })}
                />
                <NumRow
                  label="Min taban %"
                  value={c.min_floor_pct}
                  step={5}
                  min={50}
                  max={100}
                  suffix="%"
                  onSave={(v) => updateCh(c.channel, { min_floor_pct: v })}
                />
                <NumRow
                  label="Max tavan %"
                  value={c.max_ceiling_pct}
                  step={5}
                  min={100}
                  max={200}
                  suffix="%"
                  onSave={(v) => updateCh(c.channel, { max_ceiling_pct: v })}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quote playground */}
      <div className="p-4 rounded-xl bg-white border border-stone-200">
        <h3 className="text-sm font-semibold text-stone-900 mb-3 flex items-center gap-2">
          <CalcIcon size={16} />
          Quote Oyun Alanı
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
          <div>
            <label className="text-xs text-stone-500">Kanal</label>
            <select value={quoteForm.channel}
              onChange={(e) => setQuoteForm(q => ({ ...q, channel: e.target.value }))}
              className="w-full px-3 py-2 rounded-lg border border-stone-300 text-sm bg-white"
              data-testid="quote-channel"
            >
              {Object.entries(CHANNEL_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-stone-500">Check-in</label>
            <input type="date" value={quoteForm.check_in}
              onChange={(e) => setQuoteForm(q => ({ ...q, check_in: e.target.value }))}
              className="w-full px-3 py-2 rounded-lg border border-stone-300 text-sm"
              data-testid="quote-checkin"
            />
          </div>
          <div>
            <label className="text-xs text-stone-500">Gece</label>
            <input type="number" value={quoteForm.nights} min={1}
              onChange={(e) => setQuoteForm(q => ({ ...q, nights: Number(e.target.value) }))}
              className="w-full px-3 py-2 rounded-lg border border-stone-300 text-sm"
            />
          </div>
          <button onClick={runQuote} disabled={busy}
            className="px-4 py-2 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-700 disabled:opacity-50 flex items-center justify-center gap-2"
            data-testid="quote-run"
          >
            <Play size={14} />
            {busy ? "Hesaplanıyor…" : "Quote Al"}
          </button>
        </div>

        {quote && (
          <div className="mt-4 p-4 rounded-xl bg-gradient-to-br from-amber-50 to-amber-50/30 border border-amber-200" data-testid="quote-result">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <Kpi label="BAR" value={`£${quote.bar}`} />
              <Kpi label="Çarpan" value={`×${quote.multiplier_used}`} />
              <Kpi label="Gece fiyat" value={`£${quote.per_night_rate}`} accent="amber" />
              <Kpi label="Toplam" value={`£${quote.total}`} accent="emerald" />
              <Kpi label="Doluluk" value={`${quote.occupancy_pct}%`} />
            </div>
            {quote.rules_applied?.length > 0 && (
              <div className="mt-4">
                <div className="text-xs text-stone-600 font-medium mb-2">Uygulanan kurallar ({quote.rules_applied.length}):</div>
                {quote.rules_applied.map((r, i) => (
                  <div key={i} className="text-xs p-2 rounded bg-white/70 border border-amber-100 flex items-center gap-2">
                    <span className="font-medium text-stone-900">{r.rule_name}</span>
                    <span className="text-stone-500">£{r.rate_before} → £{r.rate_after}</span>
                  </div>
                ))}
              </div>
            )}
            {quote.clamped && (
              <div className="mt-3 text-xs text-amber-800 bg-amber-100 p-2 rounded">
                ⚠ Min/max clamp uygulandı · taban £{quote.floor} · tavan £{quote.ceiling}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function NumRow({ label, value, step, min, max, suffix, onSave }) {
  const [v, setV] = useState(value);
  useEffect(() => { setV(value); }, [value]);
  const changed = Math.abs(v - value) > 1e-6;
  return (
    <div className="flex items-center gap-2">
      <span className="text-stone-500 flex-1">{label}</span>
      <input type="number" value={v} step={step} min={min} max={max}
        onChange={(e) => setV(Number(e.target.value))}
        className="w-20 px-2 py-1 rounded border border-stone-300 text-sm text-right" />
      {suffix && <span className="text-stone-400 text-[10px]">{suffix}</span>}
      {changed && (
        <button onClick={() => onSave(v)} className="text-[10px] px-2 py-0.5 rounded bg-amber-600 text-white hover:bg-amber-700">
          Kaydet
        </button>
      )}
    </div>
  );
}

function Kpi({ label, value, accent }) {
  const m = { emerald: "text-emerald-700", amber: "text-amber-700" };
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-stone-500">{label}</div>
      <div className={`text-xl font-bold ${accent ? m[accent] : "text-stone-900"}`}>{value}</div>
    </div>
  );
}

function RulesTab({ propertyId }) {
  const [rules, setRules] = useState([]);
  const [editing, setEditing] = useState(null);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/api/channel-revenue/rules/${propertyId}`);
      setRules(data.rules || []);
    } catch (_) { /* silent */ }
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const seedDefaults = async () => {
    try {
      const { data } = await axios.post(`${API}/api/channel-revenue/rules/${propertyId}/seed-defaults`);
      if (data.seeded === 0) toast.info(data.note || "Zaten kural var");
      else toast.success(`${data.seeded} varsayılan kural eklendi`);
      load();
    } catch (_) { toast.error("Seed başarısız"); }
  };

  const toggle = async (r) => {
    try {
      await axios.put(`${API}/api/channel-revenue/rules/${r.id}`, { ...r, enabled: !r.enabled });
      load();
    } catch (_) { toast.error("Güncelleme başarısız"); }
  };

  const del = async (id) => {
    if (!window.confirm("Bu kuralı sil?")) return;
    try {
      await axios.delete(`${API}/api/channel-revenue/rules/${id}`);
      toast.success("Kural silindi");
      load();
    } catch (_) { toast.error("Silme başarısız"); }
  };

  return (
    <div className="space-y-4" data-testid="yield-rules-tab">
      <div className="flex items-center gap-2">
        <button
          onClick={() => setEditing({})}
          className="px-3 py-1.5 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-700 flex items-center gap-1.5"
          data-testid="rule-new"
        >
          <Plus size={14} /> Yeni Kural
        </button>
        {rules.length === 0 && (
          <button onClick={seedDefaults}
            className="px-3 py-1.5 bg-stone-100 text-stone-700 rounded-lg text-sm hover:bg-stone-200"
            data-testid="rule-seed-defaults"
          >
            Varsayılanları Yükle (4 kural)
          </button>
        )}
        <button onClick={load} className="ml-auto p-2 text-stone-500 hover:text-stone-800">
          <ArrowsClockwise size={14} />
        </button>
      </div>

      <div className="rounded-xl bg-white border border-stone-200 overflow-hidden">
        {rules.length === 0 && (
          <div className="text-xs text-stone-500 py-8 text-center">Henüz kural yok. "Varsayılanları Yükle" ile başlayın.</div>
        )}
        <div className="divide-y divide-stone-100">
          {rules.map((r) => (
            <div key={r.id} className="p-3 flex items-center gap-3" data-testid={`rule-row-${r.id}`}>
              <button onClick={() => toggle(r)}
                className={`w-10 h-6 rounded-full flex items-center ${r.enabled ? "bg-emerald-500" : "bg-stone-300"} px-0.5`}
                title="Aktif/Pasif"
              >
                <div className={`w-5 h-5 rounded-full bg-white transition-transform ${r.enabled ? "translate-x-4" : ""}`} />
              </button>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-stone-900 truncate">{r.name}</div>
                <div className="text-xs text-stone-500 mt-0.5 truncate">
                  <RuleSummary triggers={r.triggers} actions={r.actions} />
                </div>
              </div>
              <span className="text-[10px] text-stone-500 font-mono">P{r.priority}</span>
              <button onClick={() => setEditing(r)} className="text-xs px-2 py-1 rounded bg-stone-100 hover:bg-stone-200">
                Düzenle
              </button>
              <button onClick={() => del(r.id)} className="p-1.5 text-stone-400 hover:text-rose-600">
                <Trash size={14} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {editing !== null && (
        <RuleEditor
          propertyId={propertyId}
          rule={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load(); }}
        />
      )}
    </div>
  );
}

function RuleSummary({ triggers = {}, actions = {} }) {
  const parts = [];
  if (triggers.occupancy_gte) parts.push(`Doluluk ≥${triggers.occupancy_gte}%`);
  if (triggers.occupancy_lte) parts.push(`Doluluk ≤${triggers.occupancy_lte}%`);
  if (triggers.days_to_arrival_lte) parts.push(`Varış ≤${triggers.days_to_arrival_lte}g`);
  if (triggers.days_to_arrival_gte) parts.push(`Varış ≥${triggers.days_to_arrival_gte}g`);
  if (triggers.dow_in?.length) parts.push(`Günler: ${triggers.dow_in.join("/")}`);
  if (triggers.channel_in?.length) parts.push(`Kanallar: ${triggers.channel_in.length}`);
  const triggerStr = parts.length ? parts.join(" · ") : "Her zaman";
  const act = actions.rate_delta_pct != null
    ? `Fiyat ${actions.rate_delta_pct > 0 ? "+" : ""}${actions.rate_delta_pct}%`
    : "—";
  return <span>{triggerStr} → {act}</span>;
}

function RuleEditor({ propertyId, rule, onClose, onSaved }) {
  const [form, setForm] = useState(rule.id ? {
    ...rule,
    occupancy_gte: rule.triggers?.occupancy_gte || "",
    occupancy_lte: rule.triggers?.occupancy_lte || "",
    days_to_arrival_lte: rule.triggers?.days_to_arrival_lte || "",
    dow_in: rule.triggers?.dow_in || [],
    rate_delta_pct: rule.actions?.rate_delta_pct || 0,
  } : {
    name: "",
    enabled: true,
    priority: 5,
    occupancy_gte: "",
    occupancy_lte: "",
    days_to_arrival_lte: "",
    dow_in: [],
    rate_delta_pct: 0,
  });

  const toggleDow = (d) => {
    const cur = form.dow_in || [];
    setForm({
      ...form,
      dow_in: cur.includes(d) ? cur.filter((x) => x !== d) : [...cur, d],
    });
  };

  const save = async () => {
    const triggers = {};
    if (form.occupancy_gte !== "") triggers.occupancy_gte = Number(form.occupancy_gte);
    if (form.occupancy_lte !== "") triggers.occupancy_lte = Number(form.occupancy_lte);
    if (form.days_to_arrival_lte !== "") triggers.days_to_arrival_lte = Number(form.days_to_arrival_lte);
    if (form.dow_in?.length) triggers.dow_in = form.dow_in;
    const actions = {
      rate_delta_pct: Number(form.rate_delta_pct),
    };
    const body = {
      property_id: propertyId,
      name: form.name,
      enabled: form.enabled,
      priority: Number(form.priority),
      triggers, actions,
    };
    try {
      if (rule.id) {
        await axios.put(`${API}/api/channel-revenue/rules/${rule.id}`, body);
      } else {
        await axios.post(`${API}/api/channel-revenue/rules`, body);
      }
      toast.success("Kural kaydedildi");
      onSaved();
    } catch (_) { toast.error("Kaydetme başarısız"); }
  };

  return (
    <div className="fixed inset-0 bg-black/30 z-40 flex items-center justify-center p-4"
      onClick={onClose} data-testid="rule-editor">
      <div className="bg-white rounded-2xl max-w-lg w-full p-5" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-bold text-stone-900 mb-4">
          {rule.id ? "Kuralı Düzenle" : "Yeni Kural"}
        </h3>
        <div className="space-y-3 text-sm">
          <div>
            <label className="text-xs text-stone-500">Ad</label>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-stone-300" placeholder="Örn: Hafta sonu primi"
              data-testid="rule-name" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs text-stone-500">Öncelik</label>
              <input type="number" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-stone-300" />
            </div>
            <div>
              <label className="text-xs text-stone-500">Fiyat değişim %</label>
              <input type="number" value={form.rate_delta_pct} onChange={(e) => setForm({ ...form, rate_delta_pct: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-stone-300" placeholder="±%" />
            </div>
          </div>
          <div className="border-t border-stone-100 pt-3">
            <div className="text-xs text-stone-500 font-medium mb-2">Tetikleyiciler (hepsi eşleşmeli)</div>
            <div className="grid grid-cols-2 gap-2 mb-2">
              <input type="number" placeholder="Doluluk ≥%"
                value={form.occupancy_gte} onChange={(e) => setForm({ ...form, occupancy_gte: e.target.value })}
                className="px-3 py-2 rounded-lg border border-stone-300" />
              <input type="number" placeholder="Doluluk ≤%"
                value={form.occupancy_lte} onChange={(e) => setForm({ ...form, occupancy_lte: e.target.value })}
                className="px-3 py-2 rounded-lg border border-stone-300" />
            </div>
            <input type="number" placeholder="Varışa ≤ N gün"
              value={form.days_to_arrival_lte} onChange={(e) => setForm({ ...form, days_to_arrival_lte: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-stone-300" />
            <div className="mt-2">
              <div className="text-xs text-stone-500 mb-1">Haftanın günleri</div>
              <div className="flex gap-1">
                {["mon", "tue", "wed", "thu", "fri", "sat", "sun"].map((d) => (
                  <button key={d} onClick={() => toggleDow(d)}
                    className={`px-2 py-1 text-xs rounded ${
                      (form.dow_in || []).includes(d)
                        ? "bg-amber-500 text-white"
                        : "bg-stone-100 text-stone-600"
                    }`}>
                    {d.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
        <div className="flex gap-2 mt-5">
          <button onClick={save}
            className="flex-1 px-3 py-2 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-700"
            data-testid="rule-save">
            Kaydet
          </button>
          <button onClick={onClose} className="px-3 py-2 bg-stone-100 text-stone-700 rounded-lg text-sm hover:bg-stone-200">
            İptal
          </button>
        </div>
      </div>
    </div>
  );
}
