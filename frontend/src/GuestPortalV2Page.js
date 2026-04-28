import React, { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Calendar,
  Users,
  Warning,
  CheckCircle,
  XCircle,
  PencilSimple,
  ShieldCheck,
  ClockCounterClockwise,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

/**
 * Public guest self-modify / cancel portal.
 * Route: /portal/{token}
 */
export default function GuestPortalV2Page() {
  const token = window.location.pathname.split("/portal/")[1];
  const [state, setState] = useState("loading");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [mode, setMode] = useState(null); // null | "modify" | "cancel"

  const load = async () => {
    try {
      const r = await axios.get(`${API}/api/guest-portal-v2/verify/${token}`);
      setData(r.data);
      setState("ready");
    } catch (e) {
      setError(e?.response?.data?.detail || "Bağlantı geçersiz");
      setState("error");
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [token]);

  if (state === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-sky-50 to-indigo-50">
        <div className="text-sm text-stone-500">Yükleniyor…</div>
      </div>
    );
  }
  if (state === "error") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-stone-50 p-4">
        <div className="bg-white rounded-2xl shadow-sm border border-stone-200 p-8 max-w-md text-center">
          <XCircle size={48} weight="fill" className="mx-auto text-rose-500 mb-3" />
          <div className="text-lg font-semibold text-stone-900 mb-1">Bağlantı geçersiz</div>
          <div className="text-sm text-stone-500">{error}</div>
        </div>
      </div>
    );
  }

  const primary = data.branding?.primary_color || "#0ea5e9";
  const bk = data.booking;

  return (
    <div className="min-h-screen bg-gradient-to-br from-sky-50 via-white to-indigo-50 p-4" data-testid="portal-page">
      <div className="max-w-2xl mx-auto">
        {/* Hero */}
        <div className="rounded-2xl shadow-xl overflow-hidden border border-stone-200 bg-white">
          <div className="p-6 text-white" style={{ backgroundColor: primary }}>
            {data.branding?.logo_url && <img src={data.branding.logo_url} alt="" className="h-10 mb-3" />}
            <div className="text-[11px] uppercase tracking-[0.2em] opacity-80 mb-1">{data.property.name}</div>
            <div className="text-xl font-semibold">Merhaba {bk.guest_name},</div>
            <div className="text-sm opacity-90 mt-1">Rezervasyonunuzu kendiniz yönetebilirsiniz.</div>
          </div>

          {/* Booking summary */}
          <div className="p-6" data-testid="portal-booking-summary">
            <div className="text-[11px] uppercase tracking-wider text-stone-500 mb-2">Rezervasyon · {bk.booking_ref}</div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <SummaryRow icon={Calendar} label="Giriş" value={bk.check_in} />
              <SummaryRow icon={Calendar} label="Çıkış" value={bk.check_out} />
              <SummaryRow icon={ClockCounterClockwise} label="Gece" value={bk.nights} />
              <SummaryRow icon={Users} label="Misafir" value={`${bk.adults} yetişkin${bk.children ? ` + ${bk.children} çocuk` : ""}`} />
            </div>
            <div className="mt-3 pt-3 border-t border-stone-100 flex items-center justify-between">
              <div className="text-sm text-stone-600">{bk.room_type}</div>
              <div className="text-lg font-semibold text-stone-900">{bk.currency === "GBP" ? "£" : bk.currency} {bk.total_price}</div>
            </div>
            <div className="mt-3 bg-sky-50 border border-sky-100 rounded-md p-2.5 text-xs text-sky-700 flex items-center gap-2">
              <ShieldCheck size={14} weight="fill" />
              <span>{data.policy_label}</span>
            </div>
          </div>

          {/* Actions */}
          {mode === null && (
            <div className="px-6 pb-6 grid grid-cols-2 gap-3" data-testid="portal-actions">
              <button
                onClick={() => setMode("modify")}
                disabled={!data.can_modify}
                data-testid="portal-btn-modify"
                className="py-3 rounded-lg bg-stone-900 text-white hover:bg-stone-800 disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center justify-center gap-2 text-sm font-semibold"
              >
                <PencilSimple size={14} weight="bold" />
                Düzenle
              </button>
              <button
                onClick={() => setMode("cancel")}
                disabled={!data.can_cancel}
                data-testid="portal-btn-cancel"
                className="py-3 rounded-lg border-2 border-rose-300 text-rose-700 hover:bg-rose-50 disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center justify-center gap-2 text-sm font-semibold"
              >
                <XCircle size={14} weight="bold" />
                İptal Et
              </button>
            </div>
          )}

          {mode === "modify" && <ModifyForm data={data} token={token} onDone={() => { setMode(null); load(); }} onCancel={() => setMode(null)} />}
          {mode === "cancel" && <CancelForm data={data} token={token} onDone={() => { setMode(null); load(); }} onCancel={() => setMode(null)} />}
        </div>

        {/* History */}
        {data.modifications?.length > 0 && (
          <div className="mt-4 bg-white rounded-2xl border border-stone-200 p-5" data-testid="portal-history">
            <div className="text-sm font-semibold text-stone-800 mb-2">Değişiklik Geçmişi</div>
            <div className="space-y-1.5 text-xs">
              {data.modifications.map((m, i) => (
                <div key={i} className="flex items-center gap-2 text-stone-600">
                  <div className={`w-2 h-2 rounded-full ${m.type === "guest_cancel" ? "bg-rose-400" : "bg-sky-400"}`} />
                  <span className="font-mono text-[10px] text-stone-400">{m.at?.slice(0, 16).replace("T", " ")}</span>
                  <span>{m.type === "guest_cancel" ? "İptal" : "Düzenleme"}</span>
                  <span className="text-stone-400 ml-auto truncate max-w-xs">{JSON.stringify(m.change)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function SummaryRow({ icon: Icon, label, value }) {
  return (
    <div className="flex items-start gap-2">
      <Icon size={14} className="text-stone-400 mt-0.5 flex-shrink-0" />
      <div>
        <div className="text-[10px] uppercase tracking-wider text-stone-500">{label}</div>
        <div className="text-stone-800 font-medium">{value}</div>
      </div>
    </div>
  );
}

function ModifyForm({ data, token, onDone, onCancel }) {
  const bk = data.booking;
  const [form, setForm] = useState({
    check_in: bk.check_in,
    check_out: bk.check_out,
    adults: bk.adults,
    children: bk.children,
    special_requests: bk.special_requests || "",
  });
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/guest-portal-v2/modify/${token}`, form);
      if (r.data.updated) {
        toast.success("Değişiklikler kaydedildi");
      } else {
        toast.info("Değişiklik yok");
      }
      onDone();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Kaydedilemedi");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="p-6 border-t border-stone-100 space-y-3" data-testid="portal-modify-form">
      <div className="text-sm font-semibold text-stone-800">Rezervasyonu Düzenle</div>
      <div className="grid grid-cols-2 gap-3">
        <InputField label="Giriş Tarihi" type="date" value={form.check_in} onChange={(v) => setForm({ ...form, check_in: v })} testId="portal-mod-checkin" />
        <InputField label="Çıkış Tarihi" type="date" value={form.check_out} onChange={(v) => setForm({ ...form, check_out: v })} testId="portal-mod-checkout" />
        <InputField label="Yetişkin" type="number" min={1} max={10} value={form.adults} onChange={(v) => setForm({ ...form, adults: parseInt(v) || 1 })} testId="portal-mod-adults" />
        <InputField label="Çocuk" type="number" min={0} max={10} value={form.children} onChange={(v) => setForm({ ...form, children: parseInt(v) || 0 })} testId="portal-mod-children" />
      </div>
      <div>
        <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">Özel İstekler</label>
        <textarea
          value={form.special_requests}
          onChange={(e) => setForm({ ...form, special_requests: e.target.value })}
          rows={2}
          maxLength={500}
          data-testid="portal-mod-special"
          className="w-full px-3 py-2 text-sm border border-stone-200 rounded-md focus:outline-none focus:border-sky-400 resize-none"
        />
      </div>
      <div className="flex gap-2 justify-end pt-2">
        <button onClick={onCancel} className="px-4 py-2 text-sm rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50">Vazgeç</button>
        <button
          onClick={submit}
          disabled={busy}
          data-testid="portal-mod-submit"
          className="px-4 py-2 text-sm rounded-md bg-sky-500 text-white hover:bg-sky-600 disabled:opacity-50 inline-flex items-center gap-1.5"
        >
          <CheckCircle size={14} weight="bold" />
          {busy ? "Kaydediliyor…" : "Kaydet"}
        </button>
      </div>
    </div>
  );
}

function CancelForm({ data, token, onDone, onCancel }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);

  const submit = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/guest-portal-v2/cancel/${token}`, { reason });
      setDone(r.data);
      toast.success("Rezervasyon iptal edildi");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "İptal başarısız");
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <div className="p-6 border-t border-stone-100 text-center" data-testid="portal-cancel-done">
        <CheckCircle size={48} weight="fill" className="mx-auto text-emerald-500 mb-3" />
        <div className="text-lg font-semibold text-stone-900 mb-1">Rezervasyon İptal Edildi</div>
        <div className="text-sm text-stone-600">
          İade tutarı: <b>{done.currency === "GBP" ? "£" : done.currency} {done.refund_amount}</b> ({done.refund_percent}%)
        </div>
        <div className="text-xs text-stone-400 mt-2">5 iş günü içinde hesabınıza yansıyacaktır.</div>
      </div>
    );
  }

  return (
    <div className="p-6 border-t border-stone-100 space-y-3" data-testid="portal-cancel-form">
      <div className="bg-rose-50 border border-rose-200 rounded-md p-3 flex items-start gap-2">
        <Warning size={16} weight="fill" className="text-rose-500 mt-0.5 flex-shrink-0" />
        <div className="text-xs text-rose-800">
          Bu rezervasyonu iptal etmek üzeresiniz. Varışa kalan gün: <b>{data.days_to_arrival}</b>.
          Politika gereği iade oranı: <b>%{data.refund_percent_if_cancel}</b>.
        </div>
      </div>
      <div>
        <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">İptal Nedeni (opsiyonel)</label>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          maxLength={500}
          data-testid="portal-cancel-reason"
          className="w-full px-3 py-2 text-sm border border-stone-200 rounded-md focus:outline-none focus:border-rose-400 resize-none"
          placeholder="Örn: Planlarım değişti..."
        />
      </div>
      <div className="flex gap-2 justify-end">
        <button onClick={onCancel} className="px-4 py-2 text-sm rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50">Vazgeç</button>
        <button
          onClick={submit}
          disabled={busy}
          data-testid="portal-cancel-submit"
          className="px-4 py-2 text-sm rounded-md bg-rose-500 text-white hover:bg-rose-600 disabled:opacity-50"
        >
          {busy ? "İptal ediliyor…" : "Rezervasyonu İptal Et"}
        </button>
      </div>
    </div>
  );
}

function InputField({ label, type = "text", value, onChange, min, max, testId }) {
  return (
    <div>
      <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        min={min}
        max={max}
        data-testid={testId}
        className="w-full px-3 py-2 text-sm border border-stone-200 rounded-md focus:outline-none focus:border-sky-400"
      />
    </div>
  );
}
