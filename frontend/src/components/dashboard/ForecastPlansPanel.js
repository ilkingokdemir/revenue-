import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { GitBranch, Plus, Lock, LockOpen, Trash, ChatCircle, CheckCircle, Scales, ArrowLeft, PencilSimple } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/forecast-plans`;
const fmt = (n) => Number(n || 0).toLocaleString("tr-TR");

export default function ForecastPlansPanel({ propertyId = "all" }) {
  const [data, setData] = useState(null);
  const [openId, setOpenId] = useState(null);
  const [compareIds, setCompareIds] = useState([]);
  const [compareData, setCompareData] = useState(null);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/${propertyId}/versions`);
      setData(r.data);
    } catch { toast.error("Forecast sürümleri yüklenemedi"); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  async function createVersion() {
    if (propertyId === "all") { toast.error("Sürüm oluşturmak için bir tesis seçin"); return; }
    setCreating(true);
    try {
      const r = await axios.post(`${API}/${propertyId}/versions`, { months: 12 });
      toast.success("AI forecast anlık görüntüsü oluşturuldu");
      setOpenId(r.data.version.id); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Sürüm oluşturulamadı"); }
    setCreating(false);
  }

  async function remove(v) {
    if (!window.confirm(`"${v.name}" taslağı silinsin mi?`)) return;
    try { await axios.delete(`${API}/versions/${v.id}`); toast.success("Silindi"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Silinemedi"); }
  }

  function toggleCompare(id) {
    setCompareData(null);
    setCompareIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev.slice(-1), id]);
  }

  async function runCompare() {
    try {
      const r = await axios.get(`${API}/${propertyId}/compare?a=${compareIds[0]}&b=${compareIds[1]}`);
      setCompareData(r.data);
    } catch { toast.error("Karşılaştırma başarısız"); }
  }

  if (!data) return <div className="p-8 text-center text-stone-400">Yükleniyor…</div>;
  if (openId) return <VersionDetail versionId={openId} onBack={() => { setOpenId(null); load(); }} />;

  return (
    <div className="p-5 max-w-[1200px] mx-auto space-y-4" data-testid="forecast-plans-panel">
      <div className="bg-gradient-to-br from-stone-900 via-indigo-950 to-blue-900 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-indigo-300">
              <GitBranch size={14} /> Planning Workspace
            </div>
            <h1 className="text-2xl font-bold mt-1">Forecast Planlama</h1>
            <p className="text-sm text-stone-300 mt-1">AI forecast'ı sürümleyin, ekiple düzeltin, yorumlayın, onaylayın ve raporlama için kilitleyin. Kilitli sürüm kurumsal "tek doğru" olur.</p>
          </div>
          <button onClick={createVersion} disabled={creating} data-testid="fp-new-version-btn"
            className="px-4 py-2 bg-indigo-400 hover:bg-indigo-300 text-stone-900 rounded-lg text-sm font-bold inline-flex items-center gap-2 disabled:opacity-60">
            <Plus size={16} /> {creating ? "Oluşturuluyor…" : "AI Snapshot Al"}
          </button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-5">
          <Stat label="Taslak sürüm" value={data.summary.draft} testid="fp-stat-draft" />
          <Stat label="Kilitli sürüm" value={data.summary.locked} testid="fp-stat-locked" />
          <Stat label="Karşılaştırma" value={`${compareIds.length}/2 seçili`} testid="fp-stat-compare" />
        </div>
      </div>

      {compareIds.length === 2 && (
        <div className="flex items-center gap-3 bg-indigo-50 border border-indigo-200 rounded-xl px-4 py-2.5">
          <Scales size={16} className="text-indigo-600" />
          <span className="text-sm text-indigo-800 font-medium">2 sürüm seçildi</span>
          <button onClick={runCompare} data-testid="fp-run-compare-btn"
            className="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-bold">Karşılaştır</button>
          <button onClick={() => { setCompareIds([]); setCompareData(null); }} className="text-xs text-stone-500 hover:text-stone-700">Temizle</button>
        </div>
      )}

      {compareData && <CompareView cmp={compareData} />}

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="text-[11px] uppercase text-stone-400 border-b border-stone-100">
            <th className="px-3 py-2 w-8"></th>
            <th className="text-left px-2 py-2">Sürüm</th><th className="text-left px-2 py-2">Durum</th>
            <th className="text-right px-2 py-2">Gelir</th><th className="text-center px-2 py-2">Düzeltme</th>
            <th className="text-center px-2 py-2">Yorum</th><th className="text-center px-2 py-2">Onay</th>
            <th className="text-left px-2 py-2">Oluşturan</th><th className="px-2 py-2"></th>
          </tr></thead>
          <tbody>
            {data.versions.map(v => (
              <tr key={v.id} className="border-b border-stone-50 hover:bg-stone-50/60" data-testid={`fp-version-${v.id}`}>
                <td className="px-3 py-2">
                  <input type="checkbox" checked={compareIds.includes(v.id)} onChange={() => toggleCompare(v.id)}
                    data-testid={`fp-compare-check-${v.id}`} className="accent-indigo-600" />
                </td>
                <td className="px-2 py-2">
                  <button onClick={() => setOpenId(v.id)} data-testid={`fp-open-${v.id}`}
                    className="font-semibold text-stone-800 hover:text-indigo-600 text-left">{v.name}</button>
                  <div className="text-[10px] text-stone-400">{v.months} ay · {new Date(v.created_at).toLocaleDateString("tr-TR")}</div>
                </td>
                <td className="px-2 py-2">
                  <span className={`inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full font-semibold ${v.status === "locked" ? "bg-stone-900 text-white" : "bg-amber-50 text-amber-700"}`}>
                    {v.status === "locked" ? <Lock size={10} /> : <LockOpen size={10} />}
                    {v.status === "locked" ? "Kilitli" : "Taslak"}
                  </span>
                </td>
                <td className="px-2 py-2 text-right font-mono font-semibold">{fmt(v.total_revenue)}</td>
                <td className="px-2 py-2 text-center text-stone-500">{v.adjustment_count}</td>
                <td className="px-2 py-2 text-center text-stone-500">{v.comment_count}</td>
                <td className="px-2 py-2 text-center">
                  <span className={v.approval_count ? "text-emerald-600 font-semibold" : "text-stone-400"}>{v.approval_count}</span>
                </td>
                <td className="px-2 py-2 text-xs text-stone-500">{v.created_by}</td>
                <td className="px-2 py-2 text-right">
                  {v.status === "draft" && (
                    <button onClick={() => remove(v)} className="p-1 text-stone-300 hover:text-rose-600" data-testid={`fp-delete-${v.id}`}><Trash size={14} /></button>
                  )}
                </td>
              </tr>
            ))}
            {data.versions.length === 0 && (
              <tr><td colSpan={9} className="px-4 py-10 text-center text-stone-400 text-sm">
                Henüz forecast sürümü yok. "AI Snapshot Al" ile 12 aylık AI forecast'ı sürümleyin.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CompareView({ cmp }) {
  return (
    <div className="bg-white border border-indigo-200 rounded-xl p-4" data-testid="fp-compare-view">
      <div className="flex items-center gap-4 flex-wrap text-sm mb-3">
        <div><span className="text-[10px] uppercase text-stone-400">A</span> <span className="font-semibold">{cmp.a.name}</span> <span className="font-mono">{fmt(cmp.a.totals.revenue)}</span></div>
        <div><span className="text-[10px] uppercase text-stone-400">B</span> <span className="font-semibold">{cmp.b.name}</span> <span className="font-mono">{fmt(cmp.b.totals.revenue)}</span></div>
        <div className={`font-bold ${cmp.delta.revenue >= 0 ? "text-emerald-600" : "text-rose-600"}`} data-testid="fp-compare-delta">
          Δ {cmp.delta.revenue >= 0 ? "+" : ""}{fmt(cmp.delta.revenue)} · {cmp.delta.bookings >= 0 ? "+" : ""}{cmp.delta.bookings} rez.
        </div>
      </div>
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5">
        {cmp.rows.map(r => (
          <div key={r.period} className="border border-stone-100 rounded-lg p-2 text-center">
            <div className="text-[10px] text-stone-400 font-mono">{r.period}</div>
            <div className={`text-xs font-bold ${r.delta_revenue >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
              {r.delta_revenue >= 0 ? "+" : ""}{fmt(r.delta_revenue)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function VersionDetail({ versionId, onBack }) {
  const [v, setV] = useState(null);
  const [editRow, setEditRow] = useState(null);
  const [comment, setComment] = useState("");

  const load = useCallback(async () => {
    try { const r = await axios.get(`${API}/versions/${versionId}`); setV(r.data); }
    catch { toast.error("Sürüm yüklenemedi"); }
  }, [versionId]);
  useEffect(() => { load(); }, [load]);

  async function saveRow(e) {
    e.preventDefault();
    const f = e.target;
    try {
      await axios.put(`${API}/versions/${versionId}/rows`, {
        period: editRow, bookings: parseInt(f.bookings.value, 10),
        revenue: parseFloat(f.revenue.value), note: f.note.value,
      });
      toast.success("Dönem güncellendi"); setEditRow(null); load();
    } catch (err) { toast.error(err.response?.data?.detail || "Güncellenemedi"); }
  }

  async function lock() {
    if (!window.confirm("Sürüm kilitlensin mi? Kilitli sürüm artık düzenlenemez ve kurumsal raporlamanın kaynağı olur.")) return;
    try { await axios.post(`${API}/versions/${versionId}/lock`); toast.success("Sürüm kilitlendi 🔒"); load(); }
    catch { toast.error("Kilitlenemedi"); }
  }

  async function approve() {
    try {
      const r = await axios.post(`${API}/versions/${versionId}/approve`);
      toast.success(r.data.already ? "Zaten onaylamıştınız" : "Onayınız kaydedildi ✓"); load();
    } catch { toast.error("Onaylanamadı"); }
  }

  async function sendComment(e) {
    e.preventDefault();
    if (!comment.trim()) return;
    try {
      await axios.post(`${API}/versions/${versionId}/comment`, { text: comment });
      setComment(""); load();
    } catch { toast.error("Yorum gönderilemedi"); }
  }

  if (!v) return <div className="p-8 text-center text-stone-400">Yükleniyor…</div>;
  const locked = v.status === "locked";
  const baseMap = Object.fromEntries((v.baseline_rows || []).map(r => [r.period, r]));

  return (
    <div className="p-5 max-w-[1200px] mx-auto space-y-4" data-testid="fp-version-detail">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <button onClick={onBack} className="inline-flex items-center gap-1.5 text-sm text-stone-500 hover:text-stone-800" data-testid="fp-back-btn">
          <ArrowLeft size={15} /> Sürümlere dön
        </button>
        <div className="flex gap-2">
          <button onClick={approve} data-testid="fp-approve-btn"
            className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold inline-flex items-center gap-1.5">
            <CheckCircle size={14} /> Onayla ({(v.approvals || []).length})
          </button>
          {!locked && (
            <button onClick={lock} data-testid="fp-lock-btn"
              className="px-3 py-1.5 bg-stone-900 hover:bg-stone-700 text-white rounded-lg text-xs font-bold inline-flex items-center gap-1.5">
              <Lock size={14} /> Kilitle & Yayınla
            </button>
          )}
        </div>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl p-4">
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-lg font-bold text-stone-800">{v.name}</h2>
          <span className={`inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full font-semibold ${locked ? "bg-stone-900 text-white" : "bg-amber-50 text-amber-700"}`}>
            {locked ? <Lock size={10} /> : <LockOpen size={10} />}{locked ? `Kilitli · ${v.locked_by}` : "Taslak"}
          </span>
          <span className="text-sm text-stone-500">Toplam: <b className="font-mono">{fmt(v.totals.revenue)}</b>
            {v.totals.revenue !== v.baseline_totals.revenue && (
              <span className="text-xs text-indigo-600 ml-1">(AI bazdan {v.totals.revenue > v.baseline_totals.revenue ? "+" : ""}{fmt(v.totals.revenue - v.baseline_totals.revenue)})</span>
            )}
          </span>
        </div>

        <table className="w-full text-sm mt-3">
          <thead><tr className="text-[11px] uppercase text-stone-400 border-b border-stone-100">
            <th className="text-left px-2 py-1.5">Dönem</th><th className="text-right px-2 py-1.5">Rezervasyon</th>
            <th className="text-right px-2 py-1.5">Gelir</th><th className="text-right px-2 py-1.5">AI baz</th>
            <th className="text-center px-2 py-1.5">Güven</th><th className="px-2 py-1.5"></th>
          </tr></thead>
          <tbody>
            {v.rows.map(r => {
              const base = baseMap[r.period] || {};
              const adjusted = base.revenue !== r.revenue || base.bookings !== r.bookings;
              return (
                <tr key={r.period} className={`border-b border-stone-50 ${adjusted ? "bg-indigo-50/50" : ""}`} data-testid={`fp-row-${r.period}`}>
                  <td className="px-2 py-1.5 font-mono text-xs">{r.label}</td>
                  <td className="px-2 py-1.5 text-right">{fmt(r.bookings)}</td>
                  <td className="px-2 py-1.5 text-right font-semibold font-mono">{fmt(r.revenue)}</td>
                  <td className="px-2 py-1.5 text-right text-xs text-stone-400 font-mono">{adjusted ? fmt(base.revenue) : "—"}</td>
                  <td className="px-2 py-1.5 text-center text-xs text-stone-500">%{r.confidence}</td>
                  <td className="px-2 py-1.5 text-right">
                    {!locked && (
                      <button onClick={() => setEditRow(r.period)} className="p-1 text-stone-300 hover:text-indigo-600" data-testid={`fp-edit-${r.period}`}>
                        <PencilSimple size={14} />
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {editRow && (() => {
          const r = v.rows.find(x => x.period === editRow);
          return (
            <form onSubmit={saveRow} className="mt-3 bg-indigo-50 border border-indigo-200 rounded-xl p-3 flex items-end gap-2 flex-wrap" data-testid="fp-edit-form">
              <div className="text-xs font-semibold text-stone-700">{r.label} düzelt</div>
              <label className="text-[10px] text-stone-400">Rezervasyon
                <input name="bookings" type="number" min="0" defaultValue={r.bookings} data-testid="fp-edit-bookings"
                  className="block w-24 border border-stone-200 rounded-lg px-2 py-1 text-sm" /></label>
              <label className="text-[10px] text-stone-400">Gelir
                <input name="revenue" type="number" step="0.01" min="0" defaultValue={r.revenue} data-testid="fp-edit-revenue"
                  className="block w-32 border border-stone-200 rounded-lg px-2 py-1 text-sm" /></label>
              <label className="text-[10px] text-stone-400">Not
                <input name="note" placeholder="ör: yerel etkinlik etkisi" data-testid="fp-edit-note"
                  className="block w-48 border border-stone-200 rounded-lg px-2 py-1 text-sm" /></label>
              <button type="submit" className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-bold" data-testid="fp-edit-save">Kaydet</button>
              <button type="button" onClick={() => setEditRow(null)} className="text-xs text-stone-500">İptal</button>
            </form>
          );
        })()}
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="fp-comments">
          <div className="flex items-center gap-1.5 text-sm font-bold text-stone-700 mb-2"><ChatCircle size={15} /> Yorumlar</div>
          <div className="space-y-2 max-h-56 overflow-y-auto">
            {(v.comments || []).map(c => (
              <div key={c.id} className="text-sm bg-stone-50 rounded-lg px-3 py-2">
                <span className="font-semibold text-stone-700">{c.by}</span>
                <span className="text-[10px] text-stone-400 ml-2">{new Date(c.at).toLocaleString("tr-TR")}</span>
                <div className="text-stone-600">{c.text}</div>
              </div>
            ))}
            {(v.comments || []).length === 0 && <div className="text-xs text-stone-400">Henüz yorum yok.</div>}
          </div>
          <form onSubmit={sendComment} className="flex gap-2 mt-3">
            <input value={comment} onChange={e => setComment(e.target.value)} placeholder="Karar notu ekle…" data-testid="fp-comment-input"
              className="flex-1 border border-stone-200 rounded-lg px-3 py-1.5 text-sm" />
            <button type="submit" className="px-3 py-1.5 bg-stone-900 text-white rounded-lg text-xs font-bold" data-testid="fp-comment-send">Gönder</button>
          </form>
        </div>

        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="fp-audit">
          <div className="text-sm font-bold text-stone-700 mb-2">Değişiklik & Onay Geçmişi</div>
          <div className="space-y-1.5 max-h-72 overflow-y-auto text-xs">
            {(v.approvals || []).map((a, i) => (
              <div key={`ap-${i}`} className="flex items-center gap-1.5 text-emerald-700">
                <CheckCircle size={12} /> <b>{a.by}</b> onayladı · {new Date(a.at).toLocaleString("tr-TR")}
              </div>
            ))}
            {(v.adjustments || []).slice().reverse().map((a, i) => (
              <div key={`ad-${i}`} className="text-stone-500">
                <b className="text-stone-700">{a.by}</b> — {a.period}:{" "}
                {Object.entries(a.changes).map(([k, c]) => `${k} ${fmt(c.from)}→${fmt(c.to)}`).join(", ")}
                {a.note && <span className="italic"> · "{a.note}"</span>}
              </div>
            ))}
            {(v.adjustments || []).length === 0 && (v.approvals || []).length === 0 && (
              <div className="text-stone-400">Henüz değişiklik yok — AI bazı olduğu gibi duruyor.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, testid }) {
  return (
    <div className="bg-white/10 rounded-xl p-3" data-testid={testid}>
      <div className="text-[10px] uppercase tracking-wider text-stone-300">{label}</div>
      <div className="text-xl font-bold mt-0.5">{value}</div>
    </div>
  );
}
