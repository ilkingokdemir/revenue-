import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Lightning, Plus, X, Play, ToggleLeft, ToggleRight, ClockClockwise, CheckCircle, XCircle, Trash } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/automation/v2`;

export default function AutomationRulesPanel({ propertyId = "all", user }) {
  const [rules, setRules] = useState([]);
  const [catalog, setCatalog] = useState({ triggers: [], actions: [], operators: [] });
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [runsForRule, setRunsForRule] = useState(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [r, c] = await Promise.all([
        axios.get(`${API}/rules`, { withCredentials: true }),
        axios.get(`${API}/catalog`, { withCredentials: true }),
      ]);
      setRules(r.data.rules || []);
      setCatalog(c.data);
    } catch (e) {
      toast.error("Otomasyon kuralları yüklenemedi");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { reload(); }, [reload]);

  async function toggle(rule) {
    try {
      await axios.patch(`${API}/rules/${rule.id}`, { enabled: !rule.enabled }, { withCredentials: true });
      reload();
    } catch { toast.error("Güncellenemedi"); }
  }
  async function remove(id) {
    if (!confirm("Bu kuralı silmek istediğinden emin misin?")) return;
    try {
      await axios.delete(`${API}/rules/${id}`, { withCredentials: true });
      toast.success("Silindi");
      reload();
    } catch { toast.error("Silinemedi"); }
  }
  async function loadRuns(rule) {
    try {
      const r = await axios.get(`${API}/runs?rule_id=${rule.id}&limit=20`, { withCredentials: true });
      setRunsForRule({ rule, runs: r.data.runs });
    } catch { toast.error("Geçmiş yüklenemedi"); }
  }

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="automation-rules-panel">
      <div className="mb-5 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <Lightning size={12} weight="fill" className="text-yellow-500" />
            <span>Automation Suite</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">Otomasyon Kuralları</h1>
          <p className="text-sm text-stone-500 mt-1 max-w-2xl">
            Olay tabanlı iş akışları — örn: <em>"check_in olduğunda + tag 'honeymoon' içeriyorsa → HK'ye amenity siparişi aç"</em>. Tek seferde kur, sonsuza dek çalışsın.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={async () => {
              try {
                const r = await axios.get(`${API}/suggest`, { withCredentials: true });
                if (r.data.error) {
                  toast.error(r.data.error);
                  return;
                }
                const sugs = r.data.suggestions || [];
                if (sugs.length === 0) {
                  toast.info("AI önerisi bulunamadı");
                  return;
                }
                if (confirm(`AI ${sugs.length} kural önerdi:\n\n${sugs.map(s => "• " + s.name).join("\n")}\n\nHepsini taslak olarak ekle?`)) {
                  for (const s of sugs) {
                    await axios.post(`${API}/rules`, { ...s, enabled: false }, { withCredentials: true });
                  }
                  toast.success(`${sugs.length} kural taslak olarak eklendi (devre dışı — incele ve aktifleştir)`);
                  reload();
                }
              } catch (e) { toast.error("AI öneri alınamadı"); }
            }}
            className="px-3 py-1.5 text-xs font-medium text-stone-700 bg-white border border-stone-300 rounded-lg hover:bg-stone-50 inline-flex items-center gap-1.5"
            data-testid="automation-suggest-btn"
          >
            ✨ AI Önerileri Al
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="px-3 py-1.5 text-xs font-medium text-white bg-stone-900 rounded-lg hover:bg-stone-800 inline-flex items-center gap-1.5"
            data-testid="automation-create-btn"
          >
            <Plus size={14} /> Yeni Kural
          </button>
        </div>
      </div>

      {/* NL Builder — Mews Automations paritesi */}
      <NlRuleBuilder onCreated={reload} />

      {loading ? (
        <div className="py-12 text-center text-stone-400">Yükleniyor…</div>
      ) : rules.length === 0 ? (
        <div className="py-12 text-center text-stone-400 bg-white border border-stone-200 rounded-xl" data-testid="automation-empty">
          Henüz kural yok. İlk kuralını oluştur — Flexkeeping'de hoteller bunu kullanarak 13.000+ task otomatize ediyor.
        </div>
      ) : (
        <div className="space-y-2">
          {rules.map(rule => (
            <div key={rule.id} className="bg-white border border-stone-200 rounded-xl p-4" data-testid={`automation-rule-${rule.id}`}>
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="text-[10px] px-1.5 py-0.5 bg-yellow-50 text-yellow-800 rounded font-mono">{rule.trigger}</span>
                    {!rule.enabled && <span className="text-[10px] px-1.5 py-0.5 bg-stone-200 text-stone-600 rounded">Devre dışı</span>}
                    <span className="text-[10px] text-stone-400">{rule.run_count || 0} çalıştırma</span>
                    {rule.last_run_at && (
                      <span className="text-[10px] text-stone-400 inline-flex items-center gap-0.5">
                        {rule.last_run_ok === true ? <CheckCircle size={10} className="text-emerald-500" /> :
                         rule.last_run_ok === false ? <XCircle size={10} className="text-rose-500" /> : null}
                        son: {new Date(rule.last_run_at).toLocaleString("tr-TR")}
                      </span>
                    )}
                  </div>
                  <h3 className="text-sm font-semibold text-stone-900">{rule.name}</h3>
                  {rule.description && <p className="text-xs text-stone-500 mt-0.5">{rule.description}</p>}
                  <div className="flex gap-4 mt-2 flex-wrap">
                    <div className="text-[11px] text-stone-500">
                      <span className="font-medium">Koşullar:</span> {(rule.conditions || []).length === 0 ? "yok (her zaman)" :
                        (rule.conditions || []).map((c, i) => (
                          <span key={i} className="ml-1 px-1.5 py-0.5 bg-stone-50 rounded font-mono text-[10px]">
                            {c.field} {c.op} {JSON.stringify(c.value)}
                          </span>
                        ))}
                    </div>
                    <div className="text-[11px] text-stone-500">
                      <span className="font-medium">Aksiyonlar:</span> {(rule.actions || []).map((a, i) => (
                        <span key={i} className="ml-1 px-1.5 py-0.5 bg-stone-900 text-white rounded text-[10px]">
                          {a.type}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <button onClick={() => loadRuns(rule)} className="p-1.5 text-stone-500 hover:text-stone-900" title="Geçmiş" data-testid={`automation-runs-${rule.id}`}>
                    <ClockClockwise size={16} />
                  </button>
                  <button onClick={() => toggle(rule)} className="p-1.5" title={rule.enabled ? "Devre dışı bırak" : "Etkinleştir"} data-testid={`automation-toggle-${rule.id}`}>
                    {rule.enabled ? <ToggleRight size={22} weight="fill" className="text-emerald-500" /> : <ToggleLeft size={22} className="text-stone-400" />}
                  </button>
                  <button onClick={() => remove(rule.id)} className="p-1.5 text-stone-400 hover:text-rose-600" title="Sil" data-testid={`automation-delete-${rule.id}`}>
                    <Trash size={14} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <CreateRuleModal catalog={catalog} onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); reload(); }} />
      )}
      {runsForRule && (
        <RunsModal {...runsForRule} onClose={() => setRunsForRule(null)} />
      )}
    </div>
  );
}

function NlRuleBuilder({ onCreated }) {
  const [text, setText] = useState("");
  const [parsing, setParsing] = useState(false);
  const [preview, setPreview] = useState(null);
  const [saving, setSaving] = useState(false);

  async function parse() {
    if (text.trim().length < 8) { toast.error("En az 8 karakterlik bir cümle yazın"); return; }
    setParsing(true);
    setPreview(null);
    try {
      const r = await axios.post(`${API}/nl-parse`, { text: text.trim() }, { withCredentials: true });
      setPreview(r.data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Çevrilemedi"); }
    finally { setParsing(false); }
  }

  async function save(enabled) {
    if (!preview?.rule) return;
    setSaving(true);
    try {
      await axios.post(`${API}/rules`, { ...preview.rule, enabled }, { withCredentials: true });
      toast.success(enabled ? "Kural oluşturuldu ve aktif" : "Kural taslak olarak kaydedildi");
      setPreview(null);
      setText("");
      onCreated();
    } catch (e) { toast.error("Kaydedilemedi: " + (e?.response?.data?.detail || e.message)); }
    finally { setSaving(false); }
  }

  return (
    <div className="mb-5 bg-gradient-to-br from-stone-900 via-indigo-950 to-violet-950 rounded-2xl p-5 text-white" data-testid="nl-rule-builder">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-violet-300 mb-2">
        <Lightning size={12} weight="fill" /> Doğal Dilde Kural Yaz (AI)
      </div>
      <p className="text-xs text-stone-300 mb-3">
        Cümleyle anlat, çalışan kurala çevrilsin — örn: <em>"Balayı etiketli misafir check-in olduğunda odaya şampanya gönder ve resepsiyona bildirim at"</em>
      </p>
      <div className="flex gap-2">
        <input value={text} onChange={e => setText(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") parse(); }}
          placeholder="Otomasyon kuralını cümleyle yaz…"
          className="flex-1 px-3 py-2.5 text-sm rounded-lg bg-white/10 border border-white/20 placeholder-stone-400 text-white focus:outline-none focus:border-violet-400"
          data-testid="nl-input" />
        <button onClick={parse} disabled={parsing} data-testid="nl-parse-btn"
          className="px-4 py-2 text-sm font-bold bg-violet-500 hover:bg-violet-400 rounded-lg disabled:opacity-60 shrink-0">
          {parsing ? "Çevriliyor…" : "✨ Kurala Çevir"}
        </button>
      </div>
      {preview && (
        <div className="mt-4 bg-white/10 rounded-xl p-4" data-testid="nl-preview">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className="text-sm font-semibold">{preview.rule.name}</span>
            <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${preview.source === "llm" ? "bg-violet-400/30 text-violet-200" : "bg-amber-400/30 text-amber-200"}`}>
              {preview.source === "llm" ? `AI · güven %${preview.confidence}` : "sezgisel çeviri"}
            </span>
          </div>
          <div className="flex flex-wrap gap-1.5 items-center text-[11px]">
            <span className="px-2 py-1 bg-yellow-400/20 text-yellow-200 rounded font-mono">⚡ {preview.trigger_label}</span>
            {(preview.rule.conditions || []).map((c, i) => (
              <span key={i} className="px-2 py-1 bg-white/10 rounded font-mono">🔍 {c.field} {c.op} {JSON.stringify(c.value)}</span>
            ))}
            {(preview.action_labels || []).map((a, i) => (
              <span key={i} className="px-2 py-1 bg-emerald-400/20 text-emerald-200 rounded">🎯 {a}</span>
            ))}
          </div>
          <div className="flex gap-2 mt-3">
            <button onClick={() => save(true)} disabled={saving} data-testid="nl-save-active-btn"
              className="px-3 py-1.5 text-xs font-bold bg-emerald-500 hover:bg-emerald-400 text-stone-900 rounded-lg disabled:opacity-60">
              Kaydet & Aktifleştir
            </button>
            <button onClick={() => save(false)} disabled={saving} data-testid="nl-save-draft-btn"
              className="px-3 py-1.5 text-xs font-medium bg-white/10 hover:bg-white/20 rounded-lg disabled:opacity-60">
              Taslak olarak kaydet
            </button>
            <button onClick={() => setPreview(null)} className="px-3 py-1.5 text-xs text-stone-400 hover:text-white">Vazgeç</button>
          </div>
        </div>
      )}
    </div>
  );
}

function CreateRuleModal({ catalog, onClose, onCreated }) {
  const [form, setForm] = useState({
    name: "", description: "",
    trigger: catalog.triggers?.[0]?.key || "booking_created",
    conditions: [],
    actions: [{ type: catalog.actions?.[0]?.key || "create_task", params: {} }],
    enabled: true,
  });
  const [saving, setSaving] = useState(false);

  function setCond(i, key, val) {
    const next = [...form.conditions];
    next[i] = { ...next[i], [key]: val };
    setForm(f => ({ ...f, conditions: next }));
  }
  function setActParam(i, key, val) {
    const next = [...form.actions];
    next[i] = { ...next[i], params: { ...next[i].params, [key]: val } };
    setForm(f => ({ ...f, actions: next }));
  }
  function setActType(i, t) {
    const next = [...form.actions];
    next[i] = { type: t, params: {} };
    setForm(f => ({ ...f, actions: next }));
  }
  function addCond() {
    setForm(f => ({ ...f, conditions: [...f.conditions, { field: "tags", op: "contains", value: "" }] }));
  }
  function delCond(i) { setForm(f => ({ ...f, conditions: f.conditions.filter((_, idx) => idx !== i) })); }
  function addAct() {
    setForm(f => ({ ...f, actions: [...f.actions, { type: "create_task", params: {} }] }));
  }
  function delAct(i) { setForm(f => ({ ...f, actions: f.actions.filter((_, idx) => idx !== i) })); }

  async function submit() {
    if (!form.name) { toast.error("Kural adı gerekli"); return; }
    if (form.actions.length === 0) { toast.error("En az 1 aksiyon ekle"); return; }
    // Parse condition values: try JSON, fallback to string
    const conditions = form.conditions.map(c => {
      let v = c.value;
      if (typeof v === "string") {
        try { v = JSON.parse(v); } catch { /* leave as string */ }
      }
      return { ...c, value: v };
    });
    setSaving(true);
    try {
      await axios.post(`${API}/rules`, { ...form, conditions }, { withCredentials: true });
      toast.success("Kural oluşturuldu");
      onCreated();
    } catch (e) {
      toast.error("Oluşturulamadı: " + (e?.response?.data?.detail || e.message));
    } finally { setSaving(false); }
  }

  const actionFields = {
    create_task: ["title", "department", "priority", "description"],
    create_glitch: ["title", "severity", "department", "shift", "description"],
    amenity_request: ["amenity", "qty", "notes"],
    notify_role: ["role", "title", "body"],
    set_room_status: ["status"],
    tag_booking: ["tag"],
    push_to_ota: ["adapters", "job_type"],
    post_to_chat: ["channel", "body"],
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl max-w-2xl w-full p-5 max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()} data-testid="automation-create-modal">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Yeni Otomasyon Kuralı</h2>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-900"><X size={20} /></button>
        </div>
        <div className="space-y-3">
          <input placeholder="Kural adı (örn: Honeymoon Amenity Auto)" value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            className="w-full px-3 py-2 text-sm border border-stone-300 rounded" autoFocus data-testid="auto-input-name" />
          <textarea placeholder="Açıklama (isteğe bağlı)" value={form.description}
            onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
            rows={2} className="w-full px-3 py-2 text-sm border border-stone-300 rounded resize-none" />

          {/* Trigger */}
          <div>
            <div className="text-[11px] uppercase tracking-wider text-stone-500 mb-1.5">⚡ TETİKLEYİCİ</div>
            <select value={form.trigger} onChange={e => setForm(f => ({ ...f, trigger: e.target.value }))}
              className="w-full px-2 py-2 text-xs border border-stone-300 rounded bg-yellow-50" data-testid="auto-input-trigger">
              {catalog.triggers.map(t => <option key={t.key} value={t.key}>{t.label} ({t.key})</option>)}
            </select>
          </div>

          {/* Conditions */}
          <div>
            <div className="text-[11px] uppercase tracking-wider text-stone-500 mb-1.5 flex items-center justify-between">
              <span>🔍 KOŞULLAR (AND)</span>
              <button onClick={addCond} className="text-stone-600 hover:text-stone-900 text-[11px] inline-flex items-center gap-0.5"><Plus size={11} /> Koşul</button>
            </div>
            {form.conditions.length === 0 && (
              <p className="text-[11px] text-stone-400 italic">Koşul yok → her olayda çalışır.</p>
            )}
            {form.conditions.map((c, i) => (
              <div key={i} className="grid grid-cols-12 gap-1.5 mb-1.5" data-testid={`auto-cond-${i}`}>
                <input placeholder="alan (örn: tags, nights)" value={c.field}
                  onChange={e => setCond(i, "field", e.target.value)}
                  className="col-span-4 px-2 py-1.5 text-xs border border-stone-300 rounded" />
                <select value={c.op} onChange={e => setCond(i, "op", e.target.value)}
                  className="col-span-3 px-1 py-1.5 text-xs border border-stone-300 rounded">
                  {catalog.operators.map(o => <option key={o} value={o}>{o}</option>)}
                </select>
                <input placeholder='değer ("honeymoon", 3, true)' value={typeof c.value === "string" ? c.value : JSON.stringify(c.value)}
                  onChange={e => setCond(i, "value", e.target.value)}
                  className="col-span-4 px-2 py-1.5 text-xs border border-stone-300 rounded" />
                <button onClick={() => delCond(i)} className="col-span-1 text-rose-500 hover:text-rose-700"><X size={14} /></button>
              </div>
            ))}
          </div>

          {/* Actions */}
          <div>
            <div className="text-[11px] uppercase tracking-wider text-stone-500 mb-1.5 flex items-center justify-between">
              <span>🎯 AKSİYONLAR</span>
              <button onClick={addAct} className="text-stone-600 hover:text-stone-900 text-[11px] inline-flex items-center gap-0.5"><Plus size={11} /> Aksiyon</button>
            </div>
            {form.actions.map((a, i) => (
              <div key={i} className="border border-stone-200 rounded p-2 mb-1.5 bg-stone-50" data-testid={`auto-act-${i}`}>
                <div className="flex items-center gap-1.5 mb-1.5">
                  <select value={a.type} onChange={e => setActType(i, e.target.value)}
                    className="flex-1 px-2 py-1 text-xs border border-stone-300 rounded">
                    {catalog.actions.map(o => <option key={o.key} value={o.key}>{o.label}</option>)}
                  </select>
                  <button onClick={() => delAct(i)} className="text-rose-500 hover:text-rose-700"><X size={14} /></button>
                </div>
                <div className="grid grid-cols-2 gap-1.5">
                  {(actionFields[a.type] || []).map(field => (
                    <input key={field} placeholder={`${field} (kullanılabilir: {guest_name}, {room_number}, {booking_ref})`}
                      value={a.params?.[field] || ""}
                      onChange={e => setActParam(i, field, e.target.value)}
                      className="px-2 py-1 text-xs border border-stone-300 rounded bg-white" />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-4 pt-3 border-t border-stone-100">
          <button onClick={onClose} className="px-3 py-1.5 text-xs text-stone-600">İptal</button>
          <button onClick={submit} disabled={saving} className="px-3 py-1.5 text-xs font-medium text-white bg-stone-900 rounded hover:bg-stone-800 disabled:opacity-50" data-testid="auto-create-submit">
            {saving ? "Kaydediliyor…" : "Kuralı Oluştur"}
          </button>
        </div>
      </div>
    </div>
  );
}

function RunsModal({ rule, runs, onClose }) {
  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl max-w-2xl w-full p-5 max-h-[85vh] overflow-y-auto" onClick={e => e.stopPropagation()} data-testid="automation-runs-modal">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-stone-500">Çalıştırma Geçmişi</div>
            <h2 className="text-lg font-semibold">{rule.name}</h2>
          </div>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-900"><X size={20} /></button>
        </div>
        {runs.length === 0 ? (
          <div className="text-center py-8 text-stone-400 text-sm">Bu kural henüz hiç tetiklenmedi.</div>
        ) : (
          <div className="space-y-2">
            {runs.map(r => (
              <div key={r.id} className="border border-stone-200 rounded p-3 text-xs">
                <div className="flex items-center gap-2 mb-1">
                  {r.ok ? <CheckCircle size={14} className="text-emerald-500" /> : <XCircle size={14} className="text-rose-500" />}
                  <span className="font-mono text-[10px] text-stone-500">{new Date(r.created_at).toLocaleString("tr-TR")}</span>
                  <span className="text-[10px] px-1.5 py-0.5 bg-stone-100 text-stone-700 rounded">{r.event}</span>
                  {r.dry_run && <span className="text-[10px] px-1.5 py-0.5 bg-amber-50 text-amber-700 rounded">dry-run</span>}
                </div>
                <div className="text-stone-700">
                  {r.actions.map((a, i) => (
                    <div key={i} className="ml-5 mt-1">
                      {a.ok ? "✓" : "✗"} <strong>{a.action}</strong>: {a.detail}
                    </div>
                  ))}
                </div>
                {r.payload_snapshot && Object.values(r.payload_snapshot).some(v => v) && (
                  <pre className="text-[9px] text-stone-400 mt-1.5 font-mono">{JSON.stringify(r.payload_snapshot)}</pre>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
