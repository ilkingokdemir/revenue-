import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  SignIn,
  CheckCircle,
  Clock,
  Copy,
  PaperPlaneTilt,
  ArrowsClockwise,
  Link as LinkIcon,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

/**
 * SelfCheckInPipelinePanel — Admin dashboard of upcoming arrivals and their
 * self-checkin completion status. One-click "issue link" per booking.
 */
export default function SelfCheckInPipelinePanel({ propertyId, hotelName }) {
  const [days, setDays] = useState(14);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(
        `${API}/api/self-checkin-v2/pipeline/${propertyId}?days_ahead=${days}`
      );
      setData(data);
    } catch (_) { toast.error("Pipeline yüklenemedi"); }
    setLoading(false);
  }, [propertyId, days]);

  useEffect(() => { load(); }, [load]);

  const issueToken = async (bookingId) => {
    try {
      const { data } = await axios.post(
        `${API}/api/self-checkin-v2/token/${bookingId}?expiry_hours=72`
      );
      navigator.clipboard.writeText(`${window.location.origin}${data.link}`);
      toast.success(`Link panoya kopyalandı · ${data.expires_at?.slice(0, 10)} sonuna kadar geçerli`);
      load();
    } catch (_) { toast.error("Token oluşturulamadı"); }
  };

  const copyLink = (token) => {
    navigator.clipboard.writeText(`${window.location.origin}/selfcheckin-v2/${token}`);
    toast.success("Link kopyalandı");
  };

  const rows = data?.rows || [];

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="self-checkin-v2-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <SignIn size={12} weight="fill" className="text-sky-500" />
          <span>Pre-arrival Self Check-in</span>
        </div>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-stone-900">
              Dijital Check-in Pipeline · {hotelName || "Property"}
            </h1>
            <p className="text-sm text-stone-500 mt-1 max-w-2xl">
              Varış öncesi reg-card + ID + imza + slot seçimi. Misafir bitirdiğinde fast-track olur.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select value={days} onChange={(e) => setDays(Number(e.target.value))}
              className="px-2 py-1.5 rounded border border-stone-300 text-sm"
              data-testid="pipeline-days">
              <option value={7}>7 gün</option>
              <option value={14}>14 gün</option>
              <option value={30}>30 gün</option>
            </select>
            <button onClick={load} disabled={loading}
              className="p-2 text-stone-500 hover:text-stone-800">
              <ArrowsClockwise size={14} className={loading ? "animate-spin" : ""} />
            </button>
          </div>
        </div>
      </div>

      {/* KPI */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        <Kpi label="Toplam varış" value={data?.count || 0} />
        <Kpi label="Link gönderildi" value={data?.issued || 0} accent="sky" />
        <Kpi label="Reg-card dolduruldu" value={data?.reg_card_filled || 0} accent="amber" />
        <Kpi label="Tamamlandı" value={data?.completed || 0} accent="emerald"
          subtitle={`%${data?.completion_pct || 0} tamamlanma`} />
      </div>

      {/* Pipeline rows */}
      <div className="rounded-xl bg-white border border-stone-200 overflow-hidden">
        {rows.length === 0 && (
          <div className="py-8 text-center text-sm text-stone-500">
            {loading ? "Yükleniyor…" : "Bu aralıkta varış yok."}
          </div>
        )}
        <div className="divide-y divide-stone-100">
          {rows.map((r) => (
            <div key={r.booking_id} className="p-3 flex items-center gap-3 text-sm"
              data-testid={`pipeline-row-${r.booking_id}`}>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-stone-900 truncate">
                  {r.guest_name || "—"}
                </div>
                <div className="text-xs text-stone-500 mt-0.5">
                  {r.check_in} · {r.room_type_name || "—"} · {r.guest_email || "email yok"}
                </div>
              </div>
              <StepDot label="Link" done={r.token_issued} />
              <StepDot label="Form" done={r.reg_card_filled} />
              <StepDot label="İmza" done={r.has_signature} />
              <StepDot label="ID" done={r.has_id_photo} />
              <StepDot label="Slot" done={r.slot_booked} />
              {r.fast_track && (
                <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-[10px] font-bold">
                  FAST
                </span>
              )}
              {r.arrival_slot && (
                <span className="text-xs text-stone-600 font-mono" title="Seçilen varış saati">
                  <Clock size={10} className="inline mr-1" />
                  {r.arrival_slot}
                </span>
              )}
              <div className="flex items-center gap-1 ml-2">
                {r.token_issued ? (
                  <button onClick={() => copyLink(r.token)}
                    className="p-1.5 text-stone-500 hover:text-sky-600"
                    title="Linki kopyala"
                    data-testid={`pipeline-copy-${r.booking_id}`}>
                    <Copy size={14} />
                  </button>
                ) : (
                  <button onClick={() => issueToken(r.booking_id)}
                    className="px-2.5 py-1 text-xs bg-sky-600 text-white rounded-md hover:bg-sky-700 flex items-center gap-1"
                    data-testid={`pipeline-issue-${r.booking_id}`}>
                    <PaperPlaneTilt size={12} />
                    Link Gönder
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StepDot({ label, done }) {
  return (
    <div className={`flex flex-col items-center gap-0.5 w-10`}>
      <div className={`w-5 h-5 rounded-full flex items-center justify-center ${
        done ? "bg-emerald-100 text-emerald-600" : "bg-stone-100 text-stone-400"
      }`}>
        {done ? <CheckCircle size={12} weight="fill" /> : null}
      </div>
      <div className={`text-[9px] uppercase ${done ? "text-emerald-600" : "text-stone-400"}`}>
        {label}
      </div>
    </div>
  );
}

function Kpi({ label, value, subtitle, accent }) {
  const m = {
    emerald: "text-emerald-700",
    sky: "text-sky-700",
    amber: "text-amber-600",
  };
  return (
    <div className="p-3 rounded-xl bg-white border border-stone-200">
      <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-1">{label}</div>
      <div className={`text-2xl font-bold ${accent ? m[accent] : "text-stone-900"}`}>{value}</div>
      {subtitle && <div className="text-[10px] text-stone-500 mt-0.5">{subtitle}</div>}
    </div>
  );
}
