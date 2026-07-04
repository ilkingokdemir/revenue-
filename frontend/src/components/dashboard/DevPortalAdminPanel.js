/**
 * DevPortalAdminPanel — Mews Marketplace-style developer oversight.
 *
 * Shows all registered developers + their apps, approve/suspend, view
 * usage stats, and link to public docs.
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Code, CheckCircle, X, Globe, Users } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/dev-portal`;

export default function DevPortalAdminPanel() {
  const [apps, setApps] = useState([]);
  const [info, setInfo] = useState(null);

  const reload = useCallback(async () => {
    try {
      const a = await axios.get(`${API}/admin/apps`, { withCredentials: true });
      setApps(a.data.items || []);
      const i = await axios.get(`${API}/info`);
      setInfo(i.data);
    } catch (e) { toast.error("Yüklenemedi"); }
  }, []);

  useEffect(() => { reload(); }, [reload]);

  async function approve(id) {
    try {
      await axios.post(`${API}/admin/apps/${id}/approve`, {}, { withCredentials: true });
      toast.success("Onaylandı"); reload();
    } catch (e) { toast.error("Hata"); }
  }

  async function suspend(id) {
    const reason = window.prompt("Askıya alma nedeni:");
    if (reason === null) return;
    try {
      await axios.post(`${API}/admin/apps/${id}/suspend`, { reason }, { withCredentials: true });
      toast.success("Askıya alındı"); reload();
    } catch (e) { toast.error("Hata"); }
  }

  const counts = {
    pending: apps.filter(a => a.status === "pending_review").length,
    approved: apps.filter(a => a.status === "approved").length,
    suspended: apps.filter(a => a.status === "suspended").length,
    rev_share: apps.filter(a => a.revenue_share_enrolled).length,
  };

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="dev-portal-admin-panel">
      <div className="mb-5">
        <div className="text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">Developer Platform v2 · MyHotelBox × ReveniQ</div>
        <h2 className="text-2xl font-semibold text-stone-900 inline-flex items-center gap-2">
          <Code size={22} weight="fill" className="text-emerald-600" /> Geliştirici Portalı Yönetimi
        </h2>
        <p className="text-sm text-stone-500 mt-1">
          Üçüncü taraf geliştiriciler için OAuth + API key + revenue share programı.
          Public landing: <code className="bg-stone-100 px-1.5 py-0.5 rounded">/api/dev-portal/info</code>
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-5">
        <KPI label="Toplam App" value={apps.length} />
        <KPI label="Onay Bekleyen" value={counts.pending} color="text-amber-600" />
        <KPI label="Onaylı" value={counts.approved} color="text-emerald-600" />
        <KPI label="Askıdaki" value={counts.suspended} color="text-rose-600" />
        <KPI label="Revenue-Share" value={counts.rev_share} color="text-indigo-600" />
      </div>

      {info && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 mb-4 text-xs text-emerald-900">
          <div className="font-semibold mb-1 inline-flex items-center gap-1.5">
            <Globe size={13} weight="fill" /> Public Portal Bilgisi
          </div>
          <div>Scope sayısı: <b>{info.scopes.length}</b> · Rate limit: <b>{info.rate_limits.default}</b> · Revenue share: <b>%{info.revenue_share_program.default_share_percent}</b> · Sandbox: <b>{info.sandbox.free ? "Ücretsiz" : "Ücretli"}</b></div>
        </div>
      )}

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <div className="px-4 py-2.5 border-b border-stone-200 text-sm font-semibold inline-flex items-center gap-1.5">
          <Users size={14} weight="fill" /> Kayıtlı Geliştirici App'leri
        </div>
        <table className="w-full text-sm">
          <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
            <tr>
              <th className="px-4 py-2 text-left">App</th>
              <th className="px-4 py-2 text-left">Geliştirici</th>
              <th className="px-4 py-2 text-left">Scopes</th>
              <th className="px-4 py-2 text-center">Sandbox</th>
              <th className="px-4 py-2 text-center">Rev-Share</th>
              <th className="px-4 py-2 text-center">Durum</th>
              <th className="px-4 py-2 text-right">İşlem</th>
            </tr>
          </thead>
          <tbody>
            {apps.map(a => (
              <tr key={a.id} className="border-t border-stone-100" data-testid={`dev-app-${a.id}`}>
                <td className="px-4 py-2">
                  <div className="font-medium">{a.name}</div>
                  <div className="text-[10px] text-stone-400 font-mono">{a.client_id}</div>
                </td>
                <td className="px-4 py-2 text-xs">
                  {a.developer_email || a.developer_id}
                  {a.developer_company && <div className="text-stone-500">{a.developer_company}</div>}
                </td>
                <td className="px-4 py-2 text-xs">
                  {(a.scopes || []).slice(0, 3).map(s => <span key={s} className="inline-block bg-stone-100 px-1.5 py-0.5 rounded mr-1 mb-0.5 text-[10px]">{s}</span>)}
                  {a.scopes?.length > 3 && <span className="text-stone-400">+{a.scopes.length-3}</span>}
                </td>
                <td className="px-4 py-2 text-center text-xs">{a.is_sandbox ? "✓" : "—"}</td>
                <td className="px-4 py-2 text-center text-xs">
                  {a.revenue_share_enrolled ? `%${a.revenue_share_percent}` : "—"}
                </td>
                <td className="px-4 py-2 text-center">
                  <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                    a.status==="approved" ? "bg-emerald-100 text-emerald-700" :
                    a.status==="suspended" ? "bg-rose-100 text-rose-700" :
                    "bg-amber-100 text-amber-700"
                  }`}>{a.status}</span>
                </td>
                <td className="px-4 py-2 text-right">
                  <div className="flex gap-1 justify-end">
                    {a.status !== "approved" && (
                      <button onClick={() => approve(a.id)} data-testid={`dev-app-approve-${a.id}`}
                              className="p-1 text-emerald-600 hover:bg-emerald-50 rounded">
                        <CheckCircle size={13} weight="fill" />
                      </button>
                    )}
                    {a.status !== "suspended" && (
                      <button onClick={() => suspend(a.id)} data-testid={`dev-app-suspend-${a.id}`}
                              className="p-1 text-rose-600 hover:bg-rose-50 rounded">
                        <X size={13} weight="bold" />
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {apps.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-10 text-center text-stone-400 text-xs">
                Henüz kayıtlı geliştirici app yok. Geliştiriciler <code>/api/dev-portal/register</code> ile başlayabilir.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function KPI({ label, value, color }) {
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-3">
      <div className="text-[10px] uppercase tracking-wider text-stone-500">{label}</div>
      <div className={`text-xl font-semibold mt-1 ${color || "text-stone-900"}`}>{value}</div>
    </div>
  );
}
