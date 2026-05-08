import React, { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { HandCoins, Heart, CheckCircle, XCircle } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

/**
 * Public guest-facing tipping page. No auth.
 * Routes:
 *   /tip/{property_id}
 *   /tip/{property_id}/{staff_id}
 *   /tip/success?session_id=...
 *   /tip/cancel
 */
export default function TipPage() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  // /tip/success or /tip/cancel
  if (parts[1] === "success") return <TipSuccess />;
  if (parts[1] === "cancel") return <TipCancel />;

  const propertyId = parts[1];
  const staffId = parts[2] || null;
  return <TipForm propertyId={propertyId} staffId={staffId} />;
}

function TipForm({ propertyId, staffId }) {
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [amount, setAmount] = useState(10);
  const [customAmount, setCustomAmount] = useState("");
  const [guestName, setGuestName] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const q = staffId ? `?staff_id=${staffId}` : "";
        const r = await axios.get(`${API}/api/tipping/landing/${propertyId}${q}`);
        setInfo(r.data);
      } catch (e) {
        toast.error("Link geçerli değil");
      } finally {
        setLoading(false);
      }
    })();
  }, [propertyId, staffId]);

  const submit = async () => {
    const final = parseFloat(customAmount) || amount;
    if (!final || final < 0.5) {
      toast.error("Minimum bahşiş tutarı £0.50");
      return;
    }
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/tipping/session`, {
        property_id: propertyId,
        amount: final,
        currency: info?.currency || "gbp",
        staff_id: staffId,
        staff_role: info?.staff?.role || "other",
        guest_name: guestName || null,
        message: message || null,
        origin_url: window.location.origin,
      });
      window.location.href = r.data.checkout_url;
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Ödeme başlatılamadı");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-teal-50 via-white to-amber-50 flex items-center justify-center p-6">
        <div className="text-sm text-stone-500">Yükleniyor…</div>
      </div>
    );
  }

  const primary = info?.branding?.primary_color || "#0d9488";
  const logo = info?.branding?.logo_url;

  return (
    <div className="min-h-screen bg-gradient-to-br from-teal-50 via-white to-amber-50 flex items-center justify-center p-4" data-testid="tip-page">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl overflow-hidden border border-stone-200">
        {/* Hero */}
        <div className="p-6 text-center" style={{ backgroundColor: primary, color: "white" }}>
          {logo ? (
            <img src={logo} alt="" className="h-12 mx-auto mb-3" />
          ) : (
            <HandCoins size={48} weight="fill" className="mx-auto mb-3 opacity-90" />
          )}
          <div className="text-[11px] uppercase tracking-[0.2em] opacity-80 mb-1">Teşekkürler!</div>
          <div className="text-xl font-semibold">{info?.property?.name}</div>
          {info?.staff && (
            <div className="mt-3 inline-flex items-center gap-2 bg-white/15 backdrop-blur px-3 py-1.5 rounded-full text-sm">
              {info.staff.avatar_url && <img src={info.staff.avatar_url} alt="" className="w-5 h-5 rounded-full" />}
              <span>{info.staff.name}</span>
              <span className="opacity-70">·</span>
              <span className="opacity-80">{info.staff.role}</span>
            </div>
          )}
        </div>

        {/* Form */}
        <div className="p-6 space-y-4">
          <div>
            <div className="text-[11px] uppercase tracking-wider text-stone-500 mb-2">Önerilen Tutarlar</div>
            <div className="grid grid-cols-5 gap-2" data-testid="tip-amount-grid">
              {info?.suggested_amounts?.map((a) => (
                <button
                  key={a}
                  onClick={() => { setAmount(a); setCustomAmount(""); }}
                  data-testid={`tip-amount-${a}`}
                  className={`py-2.5 rounded-lg text-sm font-semibold border-2 transition-all ${
                    amount === a && !customAmount
                      ? "border-teal-500 bg-teal-50 text-teal-700"
                      : "border-stone-200 text-stone-600 hover:border-stone-400"
                  }`}
                >
                  £{a}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">Veya özel tutar</label>
            <div className="flex items-center gap-2 border border-stone-200 rounded-md px-3 py-2 focus-within:border-teal-400">
              <span className="text-stone-400">£</span>
              <input
                type="number"
                value={customAmount}
                onChange={(e) => setCustomAmount(e.target.value)}
                data-testid="tip-custom-amount"
                placeholder="0.00"
                step="0.50"
                className="flex-1 outline-none text-sm"
              />
            </div>
          </div>

          <div>
            <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">İsminiz (opsiyonel)</label>
            <input
              value={guestName}
              onChange={(e) => setGuestName(e.target.value)}
              data-testid="tip-guest-name"
              placeholder="Örn: John Smith"
              className="w-full px-3 py-2 text-sm border border-stone-200 rounded-md focus:outline-none focus:border-teal-400"
            />
          </div>

          <div>
            <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">Mesaj (opsiyonel)</label>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              data-testid="tip-message"
              rows={2}
              placeholder="Harika hizmet için teşekkürler!"
              maxLength={200}
              className="w-full px-3 py-2 text-sm border border-stone-200 rounded-md focus:outline-none focus:border-teal-400 resize-none"
            />
          </div>

          <button
            onClick={submit}
            disabled={busy}
            data-testid="tip-submit"
            className="w-full py-3 text-white rounded-lg font-semibold hover:opacity-90 transition-all disabled:opacity-50 inline-flex items-center justify-center gap-2"
            style={{ backgroundColor: primary }}
          >
            <Heart size={16} weight="fill" />
            {busy ? "Yönlendiriliyor…" : `£${(parseFloat(customAmount) || amount).toFixed(2)} bahşiş ver`}
          </button>
          <div className="text-center text-[10px] text-stone-400">
            Ödeme Stripe ile güvenli. Kredi kartı bilgileriniz asla saklanmaz.
          </div>
        </div>
      </div>
    </div>
  );
}

function TipSuccess() {
  const [status, setStatus] = useState("checking");
  const [data, setData] = useState(null);
  const sessionId = new URLSearchParams(window.location.search).get("session_id");

  useEffect(() => {
    if (!sessionId) { setStatus("error"); return; }
    let attempts = 0;
    const poll = async () => {
      attempts += 1;
      try {
        const r = await axios.get(`${API}/api/tipping/status/${sessionId}`);
        setData(r.data);
        if (r.data.status === "paid") {
          setStatus("paid");
        } else if (attempts < 12) {
          setTimeout(poll, 2000);
        } else {
          setStatus("timeout");
        }
      } catch (e) {
        setStatus("error");
      }
    };
    poll();
  }, [sessionId]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-emerald-50 to-teal-50 flex items-center justify-center p-4" data-testid="tip-success">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-8 text-center">
        {status === "paid" ? (
          <>
            <CheckCircle size={64} weight="fill" className="mx-auto text-emerald-500 mb-4" />
            <h1 className="text-2xl font-semibold text-stone-900 mb-2">Teşekkürler! 🎉</h1>
            <p className="text-stone-600 mb-4">Bahşişiniz başarıyla gönderildi.</p>
            {data && (
              <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 mb-4">
                <div className="text-3xl font-bold text-emerald-700">£{data.amount}</div>
                {data.staff_name && <div className="text-xs text-stone-500 mt-1">→ {data.staff_name}</div>}
              </div>
            )}
            <p className="text-xs text-stone-400">Bu pencereyi kapatabilirsiniz.</p>
          </>
        ) : status === "checking" ? (
          <>
            <div className="w-12 h-12 border-4 border-teal-200 border-t-teal-500 rounded-full animate-spin mx-auto mb-4" />
            <h1 className="text-lg font-semibold text-stone-900">Ödeme onaylanıyor…</h1>
          </>
        ) : (
          <>
            <XCircle size={48} weight="fill" className="mx-auto text-amber-500 mb-4" />
            <h1 className="text-lg font-semibold text-stone-900 mb-2">Ödemeyi henüz doğrulayamadık</h1>
            <p className="text-sm text-stone-500">Ödeme gerçekleştiyse birkaç dakika içinde işlenecektir.</p>
          </>
        )}
      </div>
    </div>
  );
}

function TipCancel() {
  return (
    <div className="min-h-screen bg-stone-50 flex items-center justify-center p-4" data-testid="tip-cancel">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-sm p-8 text-center border border-stone-200">
        <XCircle size={48} weight="fill" className="mx-auto text-stone-400 mb-3" />
        <h1 className="text-lg font-semibold text-stone-900 mb-2">Ödeme iptal edildi</h1>
        <p className="text-sm text-stone-500 mb-4">Bahşiş gönderilmedi. Fikir değiştirdiyseniz geri dönüp tekrar deneyebilirsiniz.</p>
        <button
          onClick={() => window.history.back()}
          className="px-4 py-2 text-sm bg-teal-500 text-white rounded-lg hover:bg-teal-600"
        >
          Geri Dön
        </button>
      </div>
    </div>
  );
}
