import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Users,
  Link as LinkIcon,
  PencilSimple,
  XCircle,
  CheckCircle,
  Clock,
  Copy,
  ArrowsClockwise,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

const POLICY_OPTIONS = [
  ["flexible", "Esnek (48h tam iade)"],
  ["moderate", "Orta (5g tam / 2-5g %50)"],
  ["strict",   "Sıkı (7g %50)"],
];

export default function GuestPortalV2Panel({ propertyId }) {
  const [data, setData] = useState(null);
  const [days, setDays] = useState(14);
  const [loading, setLoading] = useState(false);
  const [policy, setPolicy] = useState("flexible");

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/guest-portal-v2/pipeline/${propertyId}?days_ahead=${days}`, { withCredentials: true });
      setData(r.data);
    } catch (e) {
      toast.error("Pipeline yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId, days]);

  useEffect(() => { load(); }, [load]);

  const issueToken = async (bookingId) => {
    try {
      const r = await axios.post(`${API}/api/guest-portal-v2/token/${bookingId}`, { expiry_hours: 72, policy }, { withCredentials: true });
      const link = `${window.location.origin}${r.data.link_path}`;
      navigator.clipboard.writeText(link);
      toast.success("Link panoya kopyalandı");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Token oluşturulamadı");
    }
  };

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="portal-v2-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Users size={12} weight="fill" className="text-indigo-500" />
          <span>Misafir · Self-Servis Portalı</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">
          Guest Modify / Cancel Portal
        </h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Misafirler rezervasyonlarını kendileri düzenleyebilir ve iptal edebilir — resepsiyon yükünü azaltın.
        </p>
      </div>

      {loading && <div className="text-sm text-stone-400">Yükleniyor…</div>}

      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <Kpi label="Gelecek Varış" value={data.counts.total} color="indigo" testId="portal-kpi-total" />
            <Kpi label="Link Çıkarılmış" value={data.counts.token_issued} color="sky" testId="portal-kpi-issued" />
            <Kpi label="Self-Düzenleme" value={data.counts.modified} color="emerald" testId="portal-kpi-modified" />
            <Kpi label="Self-İptal" value={data.counts.cancelled} color="rose" testId="portal-kpi-cancelled" />
          </div>

          <div className="flex items-center gap-2 flex-wrap mb-4">
            <label className="text-xs text-stone-600">Gün ufku:</label>
            {[7, 14, 30, 60].map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                data-testid={`portal-days-${d}`}
                className={`px-2.5 py-1 text-xs rounded-full border transition-all ${
                  days === d ? "bg-indigo-500 text-white border-indigo-500" : "bg-white text-stone-600 border-stone-200 hover:border-stone-400"
                }`}
              >
                {d} gün
              </button>
            ))}
            <label className="text-xs text-stone-600 ml-4">Politika:</label>
            <select
              value={policy}
              onChange={(e) => setPolicy(e.target.value)}
              data-testid="portal-policy-select"
              className="px-2.5 py-1 text-xs rounded-md border border-stone-200 bg-white"
            >
              {POLICY_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <button onClick={load} className="ml-auto px-3 py-1 text-xs rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50 inline-flex items-center gap-1.5">
              <ArrowsClockwise size={12} /> Yenile
            </button>
          </div>

          {data.rows.length === 0 ? (
            <div className="text-center py-12 text-stone-400 text-sm border border-dashed border-stone-200 rounded-lg">
              Bu ufukta gelecek varış yok.
            </div>
          ) : (
            <div className="bg-white border border-stone-200 rounded-lg overflow-hidden" data-testid="portal-rows">
              <table className="w-full text-xs">
                <thead className="bg-stone-50 text-stone-500 uppercase tracking-wider text-[10px]">
                  <tr>
                    <th className="text-left px-3 py-2">Rezervasyon</th>
                    <th className="text-left px-3 py-2">Misafir</th>
                    <th className="text-left px-3 py-2">Tarihler</th>
                    <th className="text-left px-3 py-2">Durum</th>
                    <th className="text-left px-3 py-2">Link</th>
                    <th className="text-right px-3 py-2">Eylem</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((r) => (
                    <tr key={r.booking_id} className="border-t border-stone-100 hover:bg-stone-50" data-testid={`portal-row-${r.booking_id}`}>
                      <td className="px-3 py-2 font-mono text-[10px] text-stone-500">{r.booking_ref}</td>
                      <td className="px-3 py-2 text-stone-800">{r.guest_name}</td>
                      <td className="px-3 py-2 text-stone-600">{r.check_in?.slice(5)} → {r.check_out?.slice(5)}</td>
                      <td className="px-3 py-2">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                          r.status === "cancelled" ? "bg-rose-100 text-rose-700" :
                          r.status === "checked_in" ? "bg-emerald-100 text-emerald-700" :
                          "bg-stone-100 text-stone-700"
                        }`}>{r.status}</span>
                      </td>
                      <td className="px-3 py-2">
                        {r.token_issued ? (
                          <span className={`inline-flex items-center gap-1 text-[10px] ${
                            r.token_status === "modified" ? "text-emerald-600" :
                            r.token_status === "cancelled" ? "text-rose-600" :
                            "text-sky-600"
                          }`}>
                            {r.token_status === "modified" ? <PencilSimple size={10} /> :
                             r.token_status === "cancelled" ? <XCircle size={10} /> :
                             <LinkIcon size={10} />}
                            {r.token_status || "issued"}
                          </span>
                        ) : (
                          <span className="text-stone-400 text-[10px]">—</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-right">
                        {!r.token_issued && r.status !== "cancelled" && (
                          <button
                            onClick={() => issueToken(r.booking_id)}
                            data-testid={`portal-issue-${r.booking_id}`}
                            className="px-2 py-1 text-[11px] rounded-md bg-indigo-500 text-white hover:bg-indigo-600 inline-flex items-center gap-1"
                          >
                            <LinkIcon size={10} />
                            Link Gönder
                          </button>
                        )}
                        {r.token_issued && r.token_status !== "cancelled" && (
                          <button
                            onClick={() => issueToken(r.booking_id)}
                            className="px-2 py-1 text-[11px] rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50 inline-flex items-center gap-1"
                          >
                            <Copy size={10} />
                            Kopyala
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Kpi({ label, value, color, testId }) {
  const bg = {
    indigo: "bg-indigo-50 text-indigo-700",
    sky: "bg-sky-50 text-sky-700",
    emerald: "bg-emerald-50 text-emerald-700",
    rose: "bg-rose-50 text-rose-700",
  }[color];
  return (
    <div className={`${bg} border border-stone-100 rounded-lg p-3.5`} data-testid={testId}>
      <div className="text-[10px] uppercase tracking-wider opacity-70">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
    </div>
  );
}
