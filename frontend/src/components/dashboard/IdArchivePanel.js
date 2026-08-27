import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { IdentificationCard } from "@phosphor-icons/react";

const B = process.env.REACT_APP_BACKEND_URL;
const BADGE = {
  saklamada: "bg-emerald-50 text-emerald-700 border-emerald-200",
  "imha bekliyor": "bg-rose-50 text-rose-700 border-rose-200",
  "imha edildi": "bg-stone-100 text-stone-500 border-stone-200",
};

export default function IdArchivePanel({ propertyId = "all" }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState("");
  const [preview, setPreview] = useState(null);
  const [previewSrc, setPreviewSrc] = useState(null);

  useEffect(() => {
    let revoke = null;
    if (preview?.url) {
      setPreviewSrc(null);
      axios.get(`${B}${preview.url}`, { responseType: "blob" })
        .then((r) => { revoke = URL.createObjectURL(r.data); setPreviewSrc(revoke); })
        .catch(() => toast.error("Belge yüklenemedi"));
    }
    return () => { if (revoke) URL.revokeObjectURL(revoke); };
  }, [preview]);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${B}/api/id-archive?property_id=all`);
      setData(r.data);
    } catch { toast.error("Arşiv yüklenemedi"); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function saveRetention(e) {
    e.preventDefault(); setBusy("cfg");
    try {
      await axios.put(`${B}/api/id-archive/config`, { retention_days: parseInt(e.target.days.value, 10) });
      toast.success("Saklama süresi güncellendi"); load();
    } catch (err) { toast.error(err.response?.data?.detail || "Kaydedilemedi (sadece admin)"); }
    setBusy("");
  }

  async function purge() {
    if (!window.confirm("Saklama süresi dolan tüm kimlik belgeleri KALICI olarak imha edilecek (geri alınamaz). Onaylıyor musunuz?")) return;
    setBusy("purge");
    try {
      const r = await axios.post(`${B}/api/id-archive/purge-expired`);
      toast.success(`${r.data.purged} belge KVKK gereği imha edildi`); load();
    } catch (err) { toast.error(err.response?.data?.detail || "İmha başarısız (sadece admin)"); }
    setBusy("");
  }

  if (!data) return <p className="p-5 text-sm text-stone-400" data-testid="id-archive-loading">Kimlik arşivi yükleniyor…</p>;

  return (
    <div className="p-5 max-w-[1100px] mx-auto space-y-4" data-testid="id-archive-panel">
      <div className="bg-gradient-to-br from-blue-950 via-stone-900 to-stone-950 rounded-2xl p-6 text-white">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <IdentificationCard size={22} className="text-blue-400" /> Misafir Kimlik Arşivi (KVKK)
        </h1>
        <p className="text-sm text-stone-300 mt-1">{data.note}</p>
        <div className="flex gap-6 mt-3 text-sm">
          <span><b className="text-xl">{data.total}</b> belge</span>
          <span data-testid="id-archive-pending"><b className="text-xl text-rose-400">{data.pending_purge}</b> imha bekliyor</span>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-4 flex flex-wrap items-end gap-3" data-testid="id-archive-config">
        <form onSubmit={saveRetention} className="flex items-end gap-2">
          <label className="text-xs text-stone-500">Saklama süresi (gün, çıkıştan itibaren)
            <input name="days" type="number" min="30" max="3650" defaultValue={data.retention_days}
              data-testid="id-retention-input" className="block border rounded-lg px-2 py-1.5 text-sm w-32 mt-1" /></label>
          <button type="submit" disabled={busy === "cfg"} data-testid="id-retention-save-btn"
            className="px-4 py-2 rounded-full bg-stone-900 text-white text-xs font-bold disabled:opacity-50">Kaydet</button>
        </form>
        {data.pending_purge > 0 && (
          <button onClick={purge} disabled={busy === "purge"} data-testid="id-purge-btn"
            className="ml-auto px-4 py-2 rounded-full bg-rose-600 text-white text-xs font-bold disabled:opacity-50">
            🗑️ Süresi Dolanları İmha Et ({data.pending_purge})
          </button>
        )}
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 overflow-x-auto">
        {data.items.length === 0 ? (
          <p className="p-5 text-sm text-stone-400" data-testid="id-archive-empty">Arşivde kimlik belgesi yok.</p>
        ) : (
          <table className="w-full text-sm" data-testid="id-archive-table">
            <thead><tr className="text-left text-[11px] text-stone-400 border-b">
              <th className="p-3">Misafir</th><th className="p-3">Otel</th><th className="p-3">Çıkış</th><th className="p-3">İmha Tarihi</th><th className="p-3">Durum</th><th className="p-3">Belge</th>
            </tr></thead>
            <tbody>
              {data.items.map((it) => (
                <tr key={it.registration_id} className="border-t border-stone-100" data-testid={`id-archive-row-${it.registration_id}`}>
                  <td className="p-3 font-semibold">{it.guest_name || "—"}<div className="text-[10px] text-stone-400">{it.original_filename}</div></td>
                  <td className="p-3 text-xs">{it.property_id}</td>
                  <td className="p-3 font-mono text-xs">{it.check_out || "—"}</td>
                  <td className="p-3 font-mono text-xs">{it.expires_at || "—"}</td>
                  <td className="p-3"><span className={`text-[10px] font-bold border rounded-full px-2 py-0.5 ${BADGE[it.status]}`}>{it.status.toUpperCase()}</span></td>
                  <td className="p-3">
                    {it.url ? (
                      <button onClick={() => setPreview(it)} data-testid={`id-preview-btn-${it.registration_id}`}
                        className="px-2.5 py-1 rounded-full border border-blue-300 text-blue-700 text-[10px] font-bold">Görüntüle 🔒</button>
                    ) : <span className="text-[10px] text-stone-400">imha edildi</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {preview && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-6" onClick={() => setPreview(null)} data-testid="id-preview-modal">
          <div className="bg-white rounded-2xl p-4 max-w-lg w-full" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-2">
              <b className="text-sm">{preview.guest_name} — {preview.original_filename}</b>
              <button onClick={() => setPreview(null)} className="text-stone-400 text-lg" data-testid="id-preview-close">✕</button>
            </div>
            {previewSrc
              ? <img src={previewSrc} alt="Kimlik belgesi" className="w-full rounded-xl border" data-testid="id-preview-img" />
              : <p className="text-xs text-stone-400 py-8 text-center" data-testid="id-preview-loading">Belge buluttan güvenle yükleniyor…</p>}
            <p className="text-[10px] text-stone-400 mt-2">🔒 Bu belge yetkili oturumlarla korunur; erişim {preview.expires_at} tarihinde kapanacak.</p>
          </div>
        </div>
      )}
    </div>
  );
}
