import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { DownloadSimple, ClockCounterClockwise, Check, FilePdf } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const SHORT = { view: "G", create: "O", edit: "D", delete: "S", export: "E", manage_settings: "A", generate: "Ü", approve: "On", publish: "Y" };
const ROLE_COLOR = { admin: "bg-rose-100 text-rose-700", manager: "bg-indigo-100 text-indigo-700", receptionist: "bg-emerald-100 text-emerald-700", viewer: "bg-stone-100 text-stone-600", custom: "bg-amber-100 text-amber-700" };

export default function PermissionMatrixCard() {
  const [data, setData] = useState(null);
  const [pid, setPid] = useState("all");
  const [changes, setChanges] = useState([]);
  const [showHist, setShowHist] = useState(false);
  const [q, setQ] = useState("");
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));

  const load = useCallback(async () => {
    try {
      const { data: d } = await axios.get(`${API}/admin/permission-matrix?property_id=${pid}`);
      setData(d);
    } catch { toast.error("Matris yüklenemedi"); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { axios.get(`${API}/admin/permission-changes?limit=50`).then(({ data: d }) => setChanges(d.items || [])).catch(() => {}); }, [data]);

  const download = async () => {
    try {
      const r = await axios.get(`${API}/admin/permission-matrix.csv?property_id=${pid}`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data); const a = document.createElement("a"); a.href = url; a.download = `yetki-matrisi-${pid}.csv`; a.click(); URL.revokeObjectURL(url);
    } catch { toast.error("İndirilemedi"); }
  };

  const downloadPdf = async () => {
    try {
      const r = await axios.get(`${API}/admin/permission-changes/report.pdf?month=${month}&property_id=${pid}`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data); const a = document.createElement("a"); a.href = url; a.download = `yetki-denetim-${month}.pdf`; a.click(); URL.revokeObjectURL(url);
      toast.success("Denetim raporu indirildi");
    } catch { toast.error("PDF oluşturulamadı"); }
  };

  if (!data) return <div className="text-sm text-stone-400 p-6">Yükleniyor…</div>;
  const rows = data.rows.filter((r) => !q || r.name.toLowerCase().includes(q.toLowerCase()) || r.email.toLowerCase().includes(q.toLowerCase()));
  const props = data.properties;

  return (
    <div className="space-y-4" data-testid="permission-matrix-card">
      <div className="flex flex-wrap items-center gap-2">
        <select value={pid} onChange={(e) => setPid(e.target.value)} className="border border-stone-200 rounded-lg px-2.5 py-1.5 text-xs" data-testid="pm-property-select">
          <option value="all">Tüm tesisler</option>
          {props.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Kullanıcı ara…" className="border border-stone-200 rounded-lg px-2.5 py-1.5 text-xs w-48" data-testid="pm-search" />
        <span className="text-xs text-stone-500">{rows.length} kullanıcı · {props.length} tesis</span>
        <div className="ml-auto flex gap-2">
          <button onClick={() => setShowHist(!showHist)} className="px-3 py-1.5 text-xs rounded-lg border border-stone-200 inline-flex items-center gap-1.5 hover:bg-stone-50" data-testid="pm-history-btn"><ClockCounterClockwise size={13} /> Değişiklikler ({changes.length})</button>
          <button onClick={download} className="px-3 py-1.5 text-xs rounded-lg bg-stone-900 text-white inline-flex items-center gap-1.5" data-testid="pm-download-btn"><DownloadSimple size={13} /> CSV indir</button>
          <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="border border-stone-200 rounded-lg px-2 py-1 text-xs" data-testid="pm-audit-month" />
          <button onClick={downloadPdf} className="px-3 py-1.5 text-xs rounded-lg bg-rose-600 text-white inline-flex items-center gap-1.5" data-testid="pm-audit-pdf-btn"><FilePdf size={13} /> Denetim PDF</button>
        </div>
      </div>

      {showHist && (
        <div className="border border-stone-200 rounded-xl p-3 max-h-64 overflow-y-auto" data-testid="pm-history">
          {changes.length === 0 && <p className="text-xs text-stone-400">Henüz kayıtlı değişiklik yok — rol / tesis rolü / özel izin değiştirildiğinde burada listelenir.</p>}
          {changes.map((c) => (
            <div key={c.id} className="text-xs py-1.5 border-b border-stone-100 last:border-0 flex gap-2" data-testid={`pm-change-${c.id}`}>
              <span className="text-stone-400 w-32 flex-shrink-0">{new Date(c.created_at).toLocaleString("tr-TR")}</span>
              <span><b>{c.actor_name}</b> → <b>{c.target_name}</b> · {c.field}: <code className="bg-stone-100 px-1 rounded">{JSON.stringify(c.before)}</code> → <code className="bg-emerald-50 px-1 rounded">{JSON.stringify(c.after)}</code></span>
            </div>
          ))}
        </div>
      )}

      <div className="text-[10px] text-stone-500 flex flex-wrap gap-3">
        {Object.entries(SHORT).map(([k, v]) => <span key={k}><b>{v}</b> = {k}</span>)}
      </div>

      <div className="overflow-x-auto border border-stone-200 rounded-xl">
        <table className="text-xs min-w-full" data-testid="pm-table">
          <thead className="bg-stone-50 text-stone-500">
            <tr>
              <th className="px-3 py-2 text-left sticky left-0 bg-stone-50 z-10">Kullanıcı</th>
              <th className="px-3 py-2 text-left">Tesis</th>
              <th className="px-3 py-2 text-left">Etkin rol</th>
              {data.modules.map((m) => <th key={m} className="px-2 py-2 text-left whitespace-nowrap">{m}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => props.map((p, i) => {
              const e = r.per_property[p.id] || {};
              return (
                <tr key={`${r.user_id}-${p.id}`} className={`border-t border-stone-100 ${i === 0 ? "" : "text-stone-500"}`} data-testid={`pm-row-${r.user_id}-${p.id}`}>
                  <td className="px-3 py-1.5 sticky left-0 bg-white z-10">{i === 0 && <><div className="font-semibold text-stone-800">{r.name}</div><div className="text-[10px] text-stone-400">{r.email}{r.sso ? ` · SSO:${r.sso}` : ""}</div></>}</td>
                  <td className="px-3 py-1.5 whitespace-nowrap">{p.name}</td>
                  <td className="px-3 py-1.5"><span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${ROLE_COLOR[e.role] || "bg-stone-100 text-stone-600"}`}>{e.no_access ? "erişim yok" : e.role}{r.property_roles?.[p.id] && <span title="tesise özel rol"> *</span>}</span></td>
                  {data.modules.map((m) => {
                    const acts = e.perms?.[m] || [];
                    return <td key={m} className="px-2 py-1.5 whitespace-nowrap font-mono text-[10px]">{acts.length === 0 ? <span className="text-stone-300">—</span> : acts.length >= 6 ? <span className="text-emerald-700 inline-flex items-center gap-0.5"><Check size={10} weight="bold" /> tümü</span> : acts.map((a) => SHORT[a] || a).join(" ")}</td>;
                  })}
                </tr>
              );
            }))}
          </tbody>
        </table>
      </div>
      <p className="text-[10px] text-stone-400">* tesise özel rol atanmış. Etkin izin = özel izinler &gt; tesis rolü &gt; genel rol (runtime ile aynı öncelik).</p>
    </div>
  );
}
