import { useState, useEffect } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/digital-auth`;

export default function AuthorizeFormPage({ token }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [form, setForm] = useState({ cardholder_name: "", card_number: "", billing_address: "", signature: "", consent: false });
  const [state, setState] = useState("idle");

  useEffect(() => {
    axios.get(`${API}/public/${token}`)
      .then(r => setData(r.data))
      .catch(e => setErr(e.response?.data?.detail || "Bağlantı geçersiz"));
  }, [token]);

  const brand = (num) => {
    if (/^4/.test(num)) return "visa";
    if (/^5[1-5]/.test(num)) return "mastercard";
    if (/^3[47]/.test(num)) return "amex";
    return "card";
  };

  const submit = async () => {
    const digits = form.card_number.replace(/\D/g, "");
    if (digits.length < 13) { setErr("Geçerli bir kart numarası girin"); return; }
    setErr(""); setState("saving");
    try {
      await axios.post(`${API}/public/${token}/submit`, {
        cardholder_name: form.cardholder_name,
        card_last4: digits.slice(-4),
        card_brand: brand(digits),
        billing_address: form.billing_address,
        signature: form.signature,
        consent: form.consent,
      });
      setState("done");
    } catch (e) {
      setErr(e.response?.data?.detail || "Gönderilemedi");
      setState("idle");
    }
  };

  if (err && !data) return <Shell><p className="text-rose-600 text-sm text-center py-10" data-testid="auth-form-error">{err}</p></Shell>;
  if (!data) return <Shell><p className="text-stone-400 text-sm text-center py-10">Yükleniyor…</p></Shell>;

  if (state === "done" || data.status === "authorized" || data.status === "charged") {
    return (
      <Shell>
        <div className="text-center py-8" data-testid="auth-form-success">
          <div className="text-4xl mb-3">✅</div>
          <h2 className="text-lg font-bold text-stone-800">Yetkilendirme tamamlandı</h2>
          <p className="text-sm text-stone-500 mt-2">{data.property_name} ekibi bilgilendirildi. Bu pencereyi kapatabilirsiniz.</p>
        </div>
      </Shell>
    );
  }
  if (data.status !== "pending") {
    return <Shell><p className="text-amber-600 text-sm text-center py-10" data-testid="auth-form-closed">Bu talep artık aktif değil (durum: {data.status}).</p></Shell>;
  }

  return (
    <Shell>
      <div data-testid="auth-form-page">
        <div className="text-center mb-5">
          <div className="text-2xl mb-1">🔐</div>
          <h1 className="text-lg font-bold text-stone-900">{data.property_name}</h1>
          <p className="text-xs text-stone-500">Güvenli Ödeme Yetkilendirme Formu</p>
        </div>
        <div className="bg-stone-50 border border-stone-200 rounded-xl p-3 mb-4 text-sm">
          <div className="flex justify-between"><span className="text-stone-500">Amaç</span><strong>{data.purpose_label}</strong></div>
          <div className="flex justify-between mt-1"><span className="text-stone-500">Tutar</span><strong className="text-emerald-700">{data.currency} {Number(data.amount).toLocaleString()}</strong></div>
          {data.note && <p className="text-[11px] text-stone-500 mt-2">{data.note}</p>}
        </div>
        <div className="space-y-3">
          <Field label="Kart sahibi adı">
            <input value={form.cardholder_name} onChange={e => setForm(f => ({ ...f, cardholder_name: e.target.value }))}
              className="w-full px-3 py-2.5 text-sm border border-stone-300 rounded-lg" data-testid="auth-holder-input" />
          </Field>
          <Field label="Kart numarası">
            <input value={form.card_number} inputMode="numeric" placeholder="•••• •••• •••• ••••"
              onChange={e => setForm(f => ({ ...f, card_number: e.target.value.replace(/[^\d ]/g, "").slice(0, 19) }))}
              className="w-full px-3 py-2.5 text-sm border border-stone-300 rounded-lg font-mono" data-testid="auth-card-input" />
            <p className="text-[10px] text-stone-400 mt-1">🔒 Tam kart numaranız saklanmaz — sadece son 4 hane kaydedilir (PCI-DSS).</p>
          </Field>
          <Field label="Fatura adresi (opsiyonel)">
            <input value={form.billing_address} onChange={e => setForm(f => ({ ...f, billing_address: e.target.value }))}
              className="w-full px-3 py-2.5 text-sm border border-stone-300 rounded-lg" data-testid="auth-address-input" />
          </Field>
          <label className="flex items-start gap-2 text-[11px] text-stone-600">
            <input type="checkbox" checked={form.consent} onChange={e => setForm(f => ({ ...f, consent: e.target.checked }))}
              className="mt-0.5" data-testid="auth-consent-check" />
            Belirtilen tutarın yukarıdaki amaç doğrultusunda kartımdan tahsil edilmesini onaylıyorum.
          </label>
          <Field label="Dijital imza (ad soyad yazın)">
            <input value={form.signature} onChange={e => setForm(f => ({ ...f, signature: e.target.value }))}
              className="w-full px-3 py-2.5 text-sm border border-stone-300 rounded-lg italic" data-testid="auth-signature-input" />
          </Field>
          {err && <p className="text-xs text-rose-600" data-testid="auth-submit-error">{err}</p>}
          <button onClick={submit} disabled={state === "saving" || !form.consent || form.cardholder_name.length < 3 || form.signature.length < 3}
            className="w-full py-3 bg-stone-900 text-white rounded-xl text-sm font-bold hover:bg-stone-800 disabled:opacity-50"
            data-testid="auth-submit-btn">
            {state === "saving" ? "Gönderiliyor…" : "Yetkilendirmeyi Onayla 🔐"}
          </button>
        </div>
      </div>
    </Shell>
  );
}

function Shell({ children }) {
  return (
    <div className="min-h-screen bg-stone-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-lg border border-stone-200 p-6">{children}</div>
    </div>
  );
}
function Field({ label, children }) {
  return <div><label className="block text-[11px] font-semibold text-stone-600 mb-1">{label}</label>{children}</div>;
}
