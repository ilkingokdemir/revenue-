import React, { useEffect, useState, useRef } from "react";
import axios from "axios";
import { toast, Toaster } from "sonner";
import {
  CheckCircle,
  ArrowRight,
  ArrowLeft,
  PencilSimple,
  IdentificationCard,
  Clock,
  Trash,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function SelfCheckInV2Page() {
  const token = window.location.pathname.split("/selfcheckin-v2/")[1] || "";
  const [data, setData] = useState(null);
  const [step, setStep] = useState(0); // 0=welcome 1=regcard 2=signature 3=slot 4=done
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let stop = false;
    axios.get(`${API}/api/self-checkin-v2/verify/${token}`)
      .then(({ data }) => {
        if (stop) return;
        setData(data);
        if (data.reg_card_filled && data.slot_booked) setStep(4);
        else if (data.reg_card_filled) setStep(3);
      })
      .catch((e) => {
        if (stop) return;
        setError(e?.response?.data?.detail || "Bu bağlantı geçerli değil.");
      })
      .finally(() => !stop && setLoading(false));
    return () => { stop = true; };
  }, [token]);

  if (loading) return <Shell><div className="text-center text-stone-500 py-20">Yükleniyor…</div></Shell>;
  if (error) return <Shell><div className="text-center py-20">
    <div className="text-5xl mb-3">⏳</div>
    <div className="text-stone-900 font-semibold mb-2">{error}</div>
    <div className="text-sm text-stone-500">Lütfen tesis ile iletişime geçin.</div>
  </div></Shell>;
  if (!data) return null;

  return (
    <Shell property={data.property}>
      <Toaster position="top-center" richColors />
      {/* Stepper */}
      <Stepper step={step} />

      <div className="mt-6">
        {step === 0 && <WelcomeStep data={data} onNext={() => setStep(1)} />}
        {step === 1 && <RegCardStep
          token={token}
          booking={data.booking}
          onNext={() => setStep(2)}
          onBack={() => setStep(0)}
        />}
        {step === 2 && <SignatureStep
          token={token}
          onNext={() => setStep(3)}
          onBack={() => setStep(1)}
        />}
        {step === 3 && <SlotStep
          token={token}
          slots={data.default_slots}
          property={data.property}
          onNext={() => setStep(4)}
          onBack={() => setStep(2)}
        />}
        {step === 4 && <DoneStep data={data} />}
      </div>
    </Shell>
  );
}

function Shell({ children, property }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-sky-50 via-white to-emerald-50">
      <div className="max-w-2xl mx-auto px-4 py-8">
        {property && (
          <div className="flex items-center gap-3 mb-6">
            {property.logo_url ? (
              <img src={property.logo_url} alt="" className="w-12 h-12 rounded-lg object-cover" />
            ) : (
              <div className="w-12 h-12 rounded-lg bg-stone-900 text-white flex items-center justify-center text-xl font-bold">
                {(property.name || "H")[0]}
              </div>
            )}
            <div>
              <div className="font-semibold text-stone-900">{property.name || "Welcome"}</div>
              <div className="text-xs text-stone-500">{property.address || ""}</div>
            </div>
          </div>
        )}
        <div className="bg-white rounded-2xl border border-stone-200 shadow-sm p-6" data-testid="selfcheckin-v2-page">
          {children}
        </div>
      </div>
    </div>
  );
}

function Stepper({ step }) {
  const steps = ["Hoş geldin", "Bilgiler", "İmza", "Slot", "Bitti"];
  return (
    <div className="flex items-center gap-1" data-testid="stepper">
      {steps.map((s, i) => (
        <React.Fragment key={i}>
          <div className="flex items-center gap-1.5">
            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
              i < step ? "bg-emerald-500 text-white" :
              i === step ? "bg-sky-500 text-white" :
              "bg-stone-200 text-stone-500"
            }`}>
              {i < step ? <CheckCircle size={14} weight="fill" /> : i + 1}
            </div>
            <div className={`text-[10px] uppercase tracking-wider hidden sm:block ${
              i <= step ? "text-stone-900 font-medium" : "text-stone-400"
            }`}>
              {s}
            </div>
          </div>
          {i < steps.length - 1 && (
            <div className={`flex-1 h-0.5 ${i < step ? "bg-emerald-400" : "bg-stone-200"}`} />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

function WelcomeStep({ data, onNext }) {
  return (
    <div data-testid="welcome-step">
      <h1 className="text-2xl font-bold text-stone-900 mb-2">
        Hoş geldiniz, {data.booking.guest_name}!
      </h1>
      <p className="text-sm text-stone-600 mb-4">
        Varış öncesi hızlı check-in için birkaç adım:
      </p>
      <div className="grid grid-cols-2 gap-2 text-sm mb-5">
        <div className="p-3 rounded-xl bg-stone-50">
          <div className="text-[10px] uppercase text-stone-500">Giriş</div>
          <div className="font-semibold">{data.booking.check_in}</div>
        </div>
        <div className="p-3 rounded-xl bg-stone-50">
          <div className="text-[10px] uppercase text-stone-500">Çıkış</div>
          <div className="font-semibold">{data.booking.check_out}</div>
        </div>
        <div className="p-3 rounded-xl bg-stone-50">
          <div className="text-[10px] uppercase text-stone-500">Oda</div>
          <div className="font-semibold">{data.booking.room_type_name || "—"}</div>
        </div>
        <div className="p-3 rounded-xl bg-stone-50">
          <div className="text-[10px] uppercase text-stone-500">Toplam</div>
          <div className="font-semibold">{data.booking.total_price} {data.booking.currency}</div>
        </div>
      </div>
      <p className="text-xs text-stone-500 mb-5">
        Bu işlem yaklaşık 2 dakika sürer. Bittiğinde resepsiyonda anahtarınız hazır olacak — fast-track ✨
      </p>
      <button onClick={onNext}
        className="w-full px-4 py-3 bg-sky-600 text-white rounded-xl font-medium hover:bg-sky-700 flex items-center justify-center gap-2"
        data-testid="welcome-start">
        Başla <ArrowRight size={16} />
      </button>
    </div>
  );
}

function RegCardStep({ token, booking, onNext, onBack }) {
  const [form, setForm] = useState({
    first_name: (booking.guest_name || "").split(" ")[0] || "",
    last_name: (booking.guest_name || "").split(" ").slice(1).join(" ") || "",
    date_of_birth: "",
    nationality: "",
    id_doc_type: "passport",
    id_doc_no: "",
    address: "",
    phone: "",
    email: "",
    id_doc_image_b64: "",
    marketing_consent: false,
  });
  const [busy, setBusy] = useState(false);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const onFile = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 3 * 1024 * 1024) {
      toast.error("Dosya 3MB'den küçük olmalı");
      return;
    }
    const r = new FileReader();
    r.onload = () => set("id_doc_image_b64", r.result);
    r.readAsDataURL(f);
  };

  const submit = async () => {
    if (!form.first_name || !form.last_name) {
      toast.error("Ad ve Soyad zorunlu");
      return;
    }
    setBusy(true);
    try {
      // store draft in state for signature step (don't send yet - we send after signature)
      window.__checkinFormDraft = form;
      onNext();
    } finally { setBusy(false); }
  };

  return (
    <div data-testid="reg-card-step">
      <h2 className="text-xl font-bold text-stone-900 mb-1 flex items-center gap-2">
        <IdentificationCard size={20} className="text-sky-500" />
        Misafir Bilgileri
      </h2>
      <p className="text-xs text-stone-500 mb-4">Yasal bildirim için gerekli.</p>

      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <Field label="Ad" val={form.first_name} onChange={(v) => set("first_name", v)} testId="regcard-firstname" />
          <Field label="Soyad" val={form.last_name} onChange={(v) => set("last_name", v)} testId="regcard-lastname" />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Doğum tarihi" type="date" val={form.date_of_birth} onChange={(v) => set("date_of_birth", v)} />
          <Field label="Uyruk (ISO-2)" val={form.nationality} onChange={(v) => set("nationality", v.toUpperCase().slice(0, 2))} placeholder="TR" />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <label className="flex flex-col text-xs gap-1">
            <span className="text-stone-500">Belge türü</span>
            <select value={form.id_doc_type} onChange={(e) => set("id_doc_type", e.target.value)}
              className="px-3 py-2 rounded-lg border border-stone-300 text-sm">
              <option value="passport">Pasaport</option>
              <option value="id_card">Kimlik Kartı</option>
              <option value="driving_license">Ehliyet</option>
            </select>
          </label>
          <Field label="Belge No" val={form.id_doc_no} onChange={(v) => set("id_doc_no", v)} testId="regcard-docno" />
        </div>
        <Field label="Adres" val={form.address} onChange={(v) => set("address", v)} />
        <div className="grid grid-cols-2 gap-2">
          <Field label="Telefon" val={form.phone} onChange={(v) => set("phone", v)} />
          <Field label="E-posta" val={form.email} onChange={(v) => set("email", v)} type="email" />
        </div>

        <label className="flex flex-col text-xs gap-1">
          <span className="text-stone-500">Belge fotoğrafı (ops.)</span>
          <input type="file" accept="image/*" capture="environment" onChange={onFile}
            className="text-xs" data-testid="regcard-file" />
          {form.id_doc_image_b64 && (
            <img src={form.id_doc_image_b64} alt="" className="mt-1 max-h-32 rounded-lg border" />
          )}
        </label>

        <label className="flex items-center gap-2 text-xs">
          <input type="checkbox" checked={form.marketing_consent}
            onChange={(e) => set("marketing_consent", e.target.checked)} />
          <span>Kampanya ve haberler için e-posta almak istiyorum (opsiyonel)</span>
        </label>
      </div>

      <div className="flex gap-2 mt-5">
        <button onClick={onBack} className="px-4 py-2.5 bg-stone-100 text-stone-700 rounded-xl text-sm hover:bg-stone-200 flex items-center gap-1">
          <ArrowLeft size={14} /> Geri
        </button>
        <button onClick={submit} disabled={busy}
          className="flex-1 px-4 py-2.5 bg-sky-600 text-white rounded-xl font-medium hover:bg-sky-700 flex items-center justify-center gap-2"
          data-testid="regcard-next">
          İleri <ArrowRight size={14} />
        </button>
      </div>
    </div>
  );
}

function SignatureStep({ token, onNext, onBack }) {
  const canvasRef = useRef(null);
  const [drawing, setDrawing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [empty, setEmpty] = useState(true);

  const getPos = (e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    const evt = e.touches ? e.touches[0] : e;
    return { x: evt.clientX - rect.left, y: evt.clientY - rect.top };
  };

  const start = (e) => {
    e.preventDefault();
    setDrawing(true);
    const ctx = canvasRef.current.getContext("2d");
    const { x, y } = getPos(e);
    ctx.beginPath();
    ctx.moveTo(x, y);
  };
  const move = (e) => {
    if (!drawing) return;
    e.preventDefault();
    const ctx = canvasRef.current.getContext("2d");
    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.strokeStyle = "#0f172a";
    const { x, y } = getPos(e);
    ctx.lineTo(x, y);
    ctx.stroke();
    setEmpty(false);
  };
  const end = () => setDrawing(false);

  const clear = () => {
    const c = canvasRef.current;
    c.getContext("2d").clearRect(0, 0, c.width, c.height);
    setEmpty(true);
  };

  const submit = async () => {
    if (empty) {
      toast.error("Lütfen imza atın");
      return;
    }
    setBusy(true);
    try {
      const signatureB64 = canvasRef.current.toDataURL("image/png");
      const form = window.__checkinFormDraft || {};
      await axios.post(`${API}/api/self-checkin-v2/reg-card/${token}`, {
        ...form,
        signature_svg: signatureB64,
      });
      toast.success("Bilgiler kaydedildi");
      onNext();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Kaydetme başarısız");
    }
    setBusy(false);
  };

  return (
    <div data-testid="signature-step">
      <h2 className="text-xl font-bold text-stone-900 mb-1 flex items-center gap-2">
        <PencilSimple size={20} className="text-sky-500" />
        İmza
      </h2>
      <p className="text-xs text-stone-500 mb-4">Parmağınızla veya fare ile imzalayın.</p>

      <div className="relative">
        <canvas
          ref={canvasRef}
          width={560}
          height={180}
          onMouseDown={start} onMouseMove={move} onMouseUp={end} onMouseLeave={end}
          onTouchStart={start} onTouchMove={move} onTouchEnd={end}
          className="w-full h-44 border-2 border-dashed border-stone-300 rounded-xl bg-stone-50 touch-none"
          data-testid="signature-canvas"
        />
        {empty && (
          <div className="absolute inset-0 flex items-center justify-center text-xs text-stone-400 pointer-events-none">
            İmzanızı buraya atın
          </div>
        )}
      </div>

      <button onClick={clear} className="mt-2 text-xs text-stone-500 hover:text-rose-600 flex items-center gap-1"
        data-testid="signature-clear">
        <Trash size={12} /> Temizle
      </button>

      <div className="flex gap-2 mt-5">
        <button onClick={onBack}
          className="px-4 py-2.5 bg-stone-100 text-stone-700 rounded-xl text-sm hover:bg-stone-200 flex items-center gap-1">
          <ArrowLeft size={14} /> Geri
        </button>
        <button onClick={submit} disabled={busy}
          className="flex-1 px-4 py-2.5 bg-sky-600 text-white rounded-xl font-medium hover:bg-sky-700 flex items-center justify-center gap-2 disabled:opacity-50"
          data-testid="signature-next">
          Kaydet ve devam <ArrowRight size={14} />
        </button>
      </div>
    </div>
  );
}

function SlotStep({ token, slots, property, onNext, onBack }) {
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!selected) { toast.error("Bir zaman dilimi seçin"); return; }
    setBusy(true);
    try {
      await axios.post(`${API}/api/self-checkin-v2/slot/${token}`, {
        arrival_slot: selected,
      });
      toast.success("Varış zamanı kaydedildi");
      onNext();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Başarısız");
    }
    setBusy(false);
  };

  return (
    <div data-testid="slot-step">
      <h2 className="text-xl font-bold text-stone-900 mb-1 flex items-center gap-2">
        <Clock size={20} className="text-sky-500" />
        Varış Saati
      </h2>
      <p className="text-xs text-stone-500 mb-4">
        Otele yaklaşık ne zaman varacaksınız? Resepsiyon buna göre hazırlanır.
      </p>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {slots.map((s) => (
          <button key={s}
            onClick={() => setSelected(s)}
            className={`px-3 py-3 rounded-xl border text-sm transition ${
              selected === s
                ? "border-sky-500 bg-sky-50 text-sky-700 font-semibold"
                : "border-stone-200 hover:border-sky-300"
            }`}
            data-testid={`slot-${s.slice(0,5)}`}>
            {s}
          </button>
        ))}
      </div>

      {property.check_in_time && (
        <p className="text-[10px] text-stone-400 mt-3">
          Standart check-in: {property.check_in_time}
        </p>
      )}

      <div className="flex gap-2 mt-5">
        <button onClick={onBack}
          className="px-4 py-2.5 bg-stone-100 text-stone-700 rounded-xl text-sm hover:bg-stone-200 flex items-center gap-1">
          <ArrowLeft size={14} /> Geri
        </button>
        <button onClick={submit} disabled={busy || !selected}
          className="flex-1 px-4 py-2.5 bg-sky-600 text-white rounded-xl font-medium hover:bg-sky-700 flex items-center justify-center gap-2 disabled:opacity-50"
          data-testid="slot-next">
          Tamamla <ArrowRight size={14} />
        </button>
      </div>
    </div>
  );
}

function DoneStep({ data }) {
  return (
    <div className="text-center py-6" data-testid="done-step">
      <div className="w-16 h-16 mx-auto rounded-full bg-emerald-100 flex items-center justify-center mb-4">
        <CheckCircle size={32} className="text-emerald-600" weight="fill" />
      </div>
      <h2 className="text-2xl font-bold text-stone-900 mb-2">Hepsi bu kadar! ✨</h2>
      <p className="text-sm text-stone-600 mb-5 max-w-md mx-auto">
        Resepsiyonda <strong>{data.booking.guest_name}</strong> olarak karşılanacaksınız. Anahtarınız sizi bekliyor olacak.
      </p>
      <div className="p-4 rounded-xl bg-stone-50 text-xs text-stone-600 inline-block">
        <div className="flex items-center gap-2 justify-center mb-1">
          <Clock size={14} /> Check-in: {data.property.check_in_time || "15:00"}
        </div>
        <div>
          {data.property.name} · {data.property.phone || ""}
        </div>
      </div>
    </div>
  );
}

function Field({ label, val, onChange, type = "text", placeholder, testId }) {
  return (
    <label className="flex flex-col text-xs gap-1">
      <span className="text-stone-500">{label}</span>
      <input type={type} value={val} onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="px-3 py-2 rounded-lg border border-stone-300 text-sm"
        data-testid={testId} />
    </label>
  );
}
