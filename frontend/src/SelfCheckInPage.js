import { useState, useEffect } from "react";
import { CheckCircle, IdentificationCard, ShieldCheck, Notepad, Buildings, ArrowRight } from "@phosphor-icons/react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function SelfCheckInPage() {
  const params = new URLSearchParams(window.location.search);
  const bookingRef = params.get("ref") || "";

  const [checkin, setCheckin] = useState(null);
  const [booking, setBooking] = useState(null);
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [step, setStep] = useState(0); // 0=welcome, 1=id, 2=terms, 3=notes, 4=done
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [specialNotes, setSpecialNotes] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!bookingRef) { setLoading(false); return; }
    const load = async () => {
      try {
        // Start/get check-in
        const ciRes = await fetch(`${API}/checkin/start/${bookingRef}`, { method: "POST" });
        const ciData = await ciRes.json();
        setCheckin(ciData);
        if (ciData.status === "completed") setStep(4);
        // Get booking details
        const bRes = await fetch(`${API}/booking/reservation/${bookingRef}`);
        if (bRes.ok) setBooking(await bRes.json());
        // Get settings
        if (ciData.property_id) {
          const sRes = await fetch(`${API}/checkin/settings/${ciData.property_id}`, {
            headers: { "Authorization": "Bearer skip" }
          }).catch(() => null);
        }
      } catch (e) { setError("Unable to load check-in"); }
      finally { setLoading(false); }
    };
    load();
  }, [bookingRef]);

  const completeCheckIn = async () => {
    try {
      const res = await fetch(
        `${API}/checkin/complete/${bookingRef}?terms_accepted=${termsAccepted}&special_notes=${encodeURIComponent(specialNotes)}`,
        { method: "POST" }
      );
      if (!res.ok) { const d = await res.json(); setError(d.detail); return; }
      const data = await res.json();
      setCheckin(data);
      setStep(4);
    } catch { setError("Failed to complete check-in"); }
  };

  if (loading) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  if (!bookingRef) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-lg p-8 text-center max-w-md">
        <Buildings size={48} className="mx-auto text-slate-300 mb-4" />
        <h1 className="text-xl font-bold text-slate-800">Geçersiz check-in bağlantısı</h1>
        <p className="text-slate-500 mt-2">Lütfen rezervasyon onay e-postanızdaki bağlantıyı kullanın.</p>
      </div>
    </div>
  );

  // Completed
  if (step === 4) return (
    <div className="min-h-screen bg-gradient-to-br from-emerald-50 to-teal-50 flex items-center justify-center p-4" data-testid="checkin-complete">
      <div className="bg-white rounded-2xl shadow-xl p-8 text-center max-w-md w-full">
        <div className="w-20 h-20 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-5">
          <CheckCircle size={44} weight="fill" className="text-emerald-600" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900 mb-2">You're All Checked In!</h1>
        <p className="text-slate-500 mb-6">Skip the front desk and head straight to your room when you arrive.</p>
        {checkin?.room_assignment && (
          <div className="bg-slate-50 rounded-xl p-4 mb-4">
            <span className="text-xs text-slate-500 block">Your Room</span>
            <span className="text-3xl font-bold text-slate-900">{checkin.room_assignment}</span>
          </div>
        )}
        <div className="bg-slate-50 rounded-xl p-4 text-left space-y-2 text-sm">
          <div className="flex justify-between"><span className="text-slate-500">Guest</span><span className="font-medium">{checkin?.guest_name}</span></div>
          <div className="flex justify-between"><span className="text-slate-500">Booking Ref</span><span className="font-mono font-medium">{bookingRef}</span></div>
          {booking && <>
            <div className="flex justify-between"><span className="text-slate-500">Check-in</span><span className="font-medium">{new Date(booking.check_in).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Check-out</span><span className="font-medium">{new Date(booking.check_out).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })}</span></div>
          </>}
        </div>
      </div>
    </div>
  );

  const steps = [
    { icon: Buildings, label: "Welcome", color: "bg-blue-100 text-blue-600" },
    { icon: IdentificationCard, label: "ID Verification", color: "bg-purple-100 text-purple-600" },
    { icon: ShieldCheck, label: "Terms", color: "bg-emerald-100 text-emerald-600" },
    { icon: Notepad, label: "Final Details", color: "bg-amber-100 text-amber-600" },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-indigo-50 flex items-center justify-center p-4" data-testid="checkin-page">
      <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full overflow-hidden">
        {/* Progress */}
        <div className="bg-slate-900 px-6 py-4">
          <div className="flex items-center justify-between mb-3">
            {steps.map((s, i) => (
              <div key={i} className="flex items-center gap-1">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${i <= step ? "bg-white text-slate-900" : "bg-slate-700 text-slate-400"}`}>
                  {i < step ? <CheckCircle size={16} weight="fill" /> : i + 1}
                </div>
                {i < 3 && <div className={`w-8 h-0.5 ${i < step ? "bg-white" : "bg-slate-700"}`} />}
              </div>
            ))}
          </div>
          <h2 className="text-white font-semibold text-sm">{steps[step]?.label}</h2>
        </div>

        <div className="p-6">
          {/* Step 0: Welcome */}
          {step === 0 && (
            <div className="text-center" data-testid="checkin-welcome">
              <Buildings size={48} className="mx-auto text-slate-300 mb-4" />
              <h2 className="text-xl font-bold text-slate-900 mb-2">Welcome, {checkin?.guest_name}!</h2>
              <p className="text-slate-500 text-sm mb-6">Complete your online check-in to skip the front desk queue.</p>
              {booking && (
                <div className="bg-slate-50 rounded-xl p-4 text-left text-sm space-y-1.5 mb-6">
                  <div className="flex justify-between"><span className="text-slate-500">Booking</span><span className="font-mono font-medium">{bookingRef}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Check-in</span><span>{new Date(booking.check_in).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Guests</span><span>{booking.adults} adults{booking.children > 0 ? `, ${booking.children} children` : ""}</span></div>
                </div>
              )}
              <button onClick={() => setStep(1)} className="w-full bg-slate-900 text-white py-3.5 rounded-xl font-semibold flex items-center justify-center gap-2 hover:bg-slate-800 transition-colors" data-testid="start-checkin-btn">
                Start Check-in <ArrowRight size={18} />
              </button>
            </div>
          )}

          {/* Step 1: ID Verification */}
          {step === 1 && (
            <div data-testid="checkin-id-step">
              <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center mx-auto mb-4">
                <IdentificationCard size={28} className="text-purple-600" />
              </div>
              <h3 className="text-lg font-bold text-center text-slate-900 mb-2">ID Verification</h3>
              <p className="text-sm text-slate-500 text-center mb-6">For security, we need to verify your identity. You can present your ID at arrival.</p>
              <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-800 mb-6">
                <p className="font-medium mb-1">Accepted documents:</p>
                <ul className="list-disc list-inside text-blue-600 space-y-0.5">
                  <li>Passport</li>
                  <li>National ID Card</li>
                  <li>Driving Licence</li>
                </ul>
              </div>
              <button onClick={() => setStep(2)} className="w-full bg-slate-900 text-white py-3.5 rounded-xl font-semibold flex items-center justify-center gap-2 hover:bg-slate-800 transition-colors" data-testid="id-continue-btn">
                Continue <ArrowRight size={18} />
              </button>
            </div>
          )}

          {/* Step 2: Terms */}
          {step === 2 && (
            <div data-testid="checkin-terms-step">
              <div className="w-12 h-12 bg-emerald-100 rounded-xl flex items-center justify-center mx-auto mb-4">
                <ShieldCheck size={28} className="text-emerald-600" />
              </div>
              <h3 className="text-lg font-bold text-center text-slate-900 mb-2">Terms & Conditions</h3>
              <div className="bg-slate-50 rounded-xl p-4 text-sm text-slate-600 mb-4 max-h-40 overflow-y-auto">
                <p className="mb-2">By completing this online check-in, you agree to:</p>
                <ul className="list-disc list-inside space-y-1">
                  <li>Abide by the hotel's house rules</li>
                  <li>Pay for any damages during your stay</li>
                  <li>Check-out by the designated time</li>
                  <li>Present valid ID upon arrival if requested</li>
                </ul>
              </div>
              <label className="flex items-start gap-3 mb-6 cursor-pointer" data-testid="terms-checkbox">
                <input type="checkbox" checked={termsAccepted} onChange={e => setTermsAccepted(e.target.checked)}
                  className="mt-0.5 w-5 h-5 rounded border-gray-300 text-emerald-600 focus:ring-emerald-500" />
                <span className="text-sm text-slate-700">I agree to the hotel's terms and conditions</span>
              </label>
              <button onClick={() => setStep(3)} disabled={!termsAccepted}
                className="w-full bg-slate-900 text-white py-3.5 rounded-xl font-semibold flex items-center justify-center gap-2 hover:bg-slate-800 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                data-testid="terms-continue-btn">
                Continue <ArrowRight size={18} />
              </button>
            </div>
          )}

          {/* Step 3: Final Details */}
          {step === 3 && (
            <div data-testid="checkin-final-step">
              <div className="w-12 h-12 bg-amber-100 rounded-xl flex items-center justify-center mx-auto mb-4">
                <Notepad size={28} className="text-amber-600" />
              </div>
              <h3 className="text-lg font-bold text-center text-slate-900 mb-2">Almost Done!</h3>
              <p className="text-sm text-slate-500 text-center mb-4">Any special requests or notes for the hotel?</p>
              <textarea value={specialNotes} onChange={e => setSpecialNotes(e.target.value)}
                placeholder="e.g., Late arrival, extra pillows, quiet room..."
                rows={3} className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm resize-none mb-4 focus:ring-2 focus:ring-blue-500"
                data-testid="checkin-notes-input" />
              {error && <p className="text-red-500 text-sm mb-3">{error}</p>}
              <button onClick={completeCheckIn}
                className="w-full bg-emerald-600 text-white py-3.5 rounded-xl font-semibold flex items-center justify-center gap-2 hover:bg-emerald-700 transition-colors"
                data-testid="complete-checkin-btn">
                <CheckCircle size={18} weight="bold" /> Complete Check-in
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
