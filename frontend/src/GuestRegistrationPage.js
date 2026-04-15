import { useState, useEffect, useRef } from "react";
import axios from "axios";
import { motion, AnimatePresence } from "framer-motion";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STEPS = ["details", "document", "terms", "complete"];
const STEP_LABELS = ["Personal Details", "ID Upload", "Terms & Conditions", "Complete"];

export default function GuestRegistrationPage({ token }) {
  const [reg, setReg] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [step, setStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  // Form fields
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [nationality, setNationality] = useState("");
  const [dob, setDob] = useState("");
  const [address, setAddress] = useState("");
  const [passportNumber, setPassportNumber] = useState("");
  const [emergencyContact, setEmergencyContact] = useState("");
  const [specialRequests, setSpecialRequests] = useState("");

  // ID upload
  const [idFile, setIdFile] = useState(null);
  const [idPreview, setIdPreview] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [idUploaded, setIdUploaded] = useState(false);
  const fileRef = useRef(null);

  // Terms
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const [signature, setSignature] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await axios.get(`${API}/guest-journey/registration/${token}`);
        setReg(data);
        if (data.status === "completed") setStep(3);
        if (data.form_data) {
          setFullName(data.form_data.full_name || data.booking?.guest_name || "");
          setEmail(data.form_data.email || data.booking?.guest_email || "");
          setPhone(data.form_data.phone || "");
          setNationality(data.form_data.nationality || "");
          setDob(data.form_data.date_of_birth || "");
          setAddress(data.form_data.address || "");
          setPassportNumber(data.form_data.passport_number || "");
          setEmergencyContact(data.form_data.emergency_contact || "");
          setSpecialRequests(data.form_data.special_requests || "");
        } else {
          setFullName(data.booking?.guest_name || "");
          setEmail(data.booking?.guest_email || "");
        }
        if (data.id_uploaded) setIdUploaded(true);
        if (data.terms_accepted) setTermsAccepted(true);
      } catch {
        setError("Registration link not found or has expired.");
      }
      setLoading(false);
    };
    load();
  }, [token]);

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
      alert("File too large. Maximum 10MB.");
      return;
    }
    setIdFile(file);
    const reader = new FileReader();
    reader.onload = (ev) => setIdPreview(ev.target.result);
    reader.readAsDataURL(file);
  };

  const uploadId = async () => {
    if (!idFile) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", idFile);
      await axios.post(`${API}/guest-journey/upload-id/${token}`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setIdUploaded(true);
    } catch {
      alert("Upload failed. Please try again.");
    }
    setUploading(false);
  };

  const submitForm = async () => {
    setSubmitting(true);
    try {
      await axios.post(`${API}/guest-journey/registration/${token}`, {
        form_data: {
          full_name: fullName,
          email,
          phone,
          nationality,
          date_of_birth: dob,
          address,
          passport_number: passportNumber,
          emergency_contact: emergencyContact,
          special_requests: specialRequests,
        },
        terms_accepted: termsAccepted && privacyAccepted,
        signature,
      });
      setStep(3);
    } catch {
      alert("Submission failed. Please try again.");
    }
    setSubmitting(false);
  };

  const canProceedStep0 = fullName && email && nationality;
  const canProceedStep1 = idUploaded || idFile;
  const canProceedStep2 = termsAccepted && privacyAccepted && signature.trim();

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-stone-50 to-stone-100 flex items-center justify-center">
        <div className="w-8 h-8 border-3 border-stone-300 border-t-stone-700 rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-stone-50 to-stone-100 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-lg p-8 max-w-md w-full text-center" data-testid="registration-error">
          <div className="w-16 h-16 rounded-full bg-red-50 flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" /></svg>
          </div>
          <h2 className="text-lg font-semibold text-stone-800 mb-2">Link Not Found</h2>
          <p className="text-stone-500 text-sm">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-stone-50 to-amber-50/30" data-testid="guest-registration-page">
      {/* Header */}
      <header className="bg-[#1e3a5f] text-white" data-testid="registration-header">
        <div className="max-w-2xl mx-auto px-4 py-6 text-center">
          {reg?.hotel_logo && (
            <img src={reg.hotel_logo} alt="" className="w-12 h-12 rounded-xl mx-auto mb-3 object-cover bg-white/10" />
          )}
          <h1 className="text-xl font-bold tracking-tight" data-testid="hotel-name-header">{reg?.hotel_name || "Hotel"}</h1>
          <p className="text-white/70 text-sm mt-1">Pre-Arrival Registration</p>
        </div>
      </header>

      {/* Progress Bar */}
      <div className="max-w-2xl mx-auto px-4 mt-6" data-testid="registration-progress">
        <div className="flex items-center justify-between mb-2">
          {STEP_LABELS.map((label, i) => (
            <div key={i} className="flex flex-col items-center flex-1">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300 ${
                i < step ? "bg-emerald-500 text-white" : i === step ? "bg-[#1e3a5f] text-white ring-4 ring-[#1e3a5f]/20" : "bg-stone-200 text-stone-400"
              }`} data-testid={`step-indicator-${i}`}>
                {i < step ? (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>
                ) : i + 1}
              </div>
              <span className={`text-[10px] mt-1.5 font-medium ${i <= step ? "text-stone-700" : "text-stone-400"}`}>{label}</span>
            </div>
          ))}
        </div>
        <div className="h-1 bg-stone-200 rounded-full overflow-hidden mt-1">
          <motion.div className="h-full bg-[#1e3a5f] rounded-full" animate={{ width: `${(step / 3) * 100}%` }} transition={{ duration: 0.5 }} />
        </div>
      </div>

      {/* Booking Info */}
      {reg?.booking && step < 3 && (
        <div className="max-w-2xl mx-auto px-4 mt-4">
          <div className="bg-white/80 backdrop-blur rounded-xl border border-stone-200/60 px-4 py-3 flex items-center gap-4 text-xs text-stone-500" data-testid="booking-summary-bar">
            <span className="font-semibold text-stone-700">Ref: {reg.booking.booking_ref || "—"}</span>
            <span className="text-stone-300">|</span>
            <span>Check-in: {reg.booking.check_in || "—"}</span>
            <span className="text-stone-300">|</span>
            <span>Check-out: {reg.booking.check_out || "—"}</span>
          </div>
        </div>
      )}

      {/* Content */}
      <div className="max-w-2xl mx-auto px-4 py-6">
        <AnimatePresence mode="wait">
          {/* STEP 0: Personal Details */}
          {step === 0 && (
            <motion.div key="step0" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="bg-white rounded-2xl shadow-sm border border-stone-200/60 p-6" data-testid="step-personal-details">
              <h2 className="text-lg font-semibold text-stone-800 mb-1">Personal Details</h2>
              <p className="text-sm text-stone-400 mb-5">Please fill in your information for a smooth check-in</p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="sm:col-span-2">
                  <label className="block text-xs font-medium text-stone-600 mb-1.5">Full Name *</label>
                  <input data-testid="input-full-name" type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} className="w-full px-3 py-2.5 rounded-lg border border-stone-200 text-sm focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] outline-none transition" placeholder="As shown on your ID" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-600 mb-1.5">Email *</label>
                  <input data-testid="input-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full px-3 py-2.5 rounded-lg border border-stone-200 text-sm focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] outline-none transition" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-600 mb-1.5">Phone</label>
                  <input data-testid="input-phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} className="w-full px-3 py-2.5 rounded-lg border border-stone-200 text-sm focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] outline-none transition" placeholder="+44 7..." />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-600 mb-1.5">Nationality *</label>
                  <input data-testid="input-nationality" type="text" value={nationality} onChange={(e) => setNationality(e.target.value)} className="w-full px-3 py-2.5 rounded-lg border border-stone-200 text-sm focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] outline-none transition" placeholder="e.g. British" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-600 mb-1.5">Date of Birth</label>
                  <input data-testid="input-dob" type="date" value={dob} onChange={(e) => setDob(e.target.value)} className="w-full px-3 py-2.5 rounded-lg border border-stone-200 text-sm focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] outline-none transition" />
                </div>
                <div className="sm:col-span-2">
                  <label className="block text-xs font-medium text-stone-600 mb-1.5">Address</label>
                  <input data-testid="input-address" type="text" value={address} onChange={(e) => setAddress(e.target.value)} className="w-full px-3 py-2.5 rounded-lg border border-stone-200 text-sm focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] outline-none transition" placeholder="Home address" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-600 mb-1.5">Passport / ID Number</label>
                  <input data-testid="input-passport" type="text" value={passportNumber} onChange={(e) => setPassportNumber(e.target.value)} className="w-full px-3 py-2.5 rounded-lg border border-stone-200 text-sm focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] outline-none transition" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-600 mb-1.5">Emergency Contact</label>
                  <input data-testid="input-emergency" type="text" value={emergencyContact} onChange={(e) => setEmergencyContact(e.target.value)} className="w-full px-3 py-2.5 rounded-lg border border-stone-200 text-sm focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] outline-none transition" placeholder="Name & phone" />
                </div>
                <div className="sm:col-span-2">
                  <label className="block text-xs font-medium text-stone-600 mb-1.5">Special Requests</label>
                  <textarea data-testid="input-special-requests" value={specialRequests} onChange={(e) => setSpecialRequests(e.target.value)} rows={2} className="w-full px-3 py-2.5 rounded-lg border border-stone-200 text-sm focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] outline-none transition resize-none" placeholder="e.g. Early check-in, extra pillows..." />
                </div>
              </div>

              <div className="flex justify-end mt-6">
                <button data-testid="btn-next-step-0" onClick={() => setStep(1)} disabled={!canProceedStep0} className="px-6 py-2.5 bg-[#1e3a5f] text-white text-sm font-semibold rounded-lg hover:bg-[#15304f] disabled:opacity-40 disabled:cursor-not-allowed transition">
                  Continue
                </button>
              </div>
            </motion.div>
          )}

          {/* STEP 1: ID Upload */}
          {step === 1 && (
            <motion.div key="step1" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="bg-white rounded-2xl shadow-sm border border-stone-200/60 p-6" data-testid="step-id-upload">
              <h2 className="text-lg font-semibold text-stone-800 mb-1">Upload ID Document</h2>
              <p className="text-sm text-stone-400 mb-5">Upload a clear photo of your passport or government-issued ID</p>

              {idUploaded && !idFile ? (
                <div className="border-2 border-emerald-200 bg-emerald-50 rounded-xl p-8 text-center" data-testid="id-already-uploaded">
                  <div className="w-14 h-14 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-3">
                    <svg className="w-7 h-7 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                  </div>
                  <p className="font-medium text-emerald-800">ID Document Uploaded</p>
                  <p className="text-emerald-600 text-sm mt-1">Your document has been received</p>
                  <button onClick={() => { setIdUploaded(false); setIdFile(null); setIdPreview(null); }} className="text-xs text-stone-500 underline mt-3">Upload a different document</button>
                </div>
              ) : (
                <div className="border-2 border-dashed border-stone-300 rounded-xl p-8 text-center hover:border-[#1e3a5f]/40 transition-colors cursor-pointer" onClick={() => fileRef.current?.click()} data-testid="id-upload-dropzone">
                  <input ref={fileRef} type="file" accept="image/*,.pdf" onChange={handleFileSelect} className="hidden" data-testid="id-file-input" />
                  {idPreview ? (
                    <div>
                      <img src={idPreview} alt="ID Preview" className="max-h-48 rounded-lg mx-auto mb-3 object-contain" data-testid="id-preview-image" />
                      <p className="text-sm font-medium text-stone-700">{idFile?.name}</p>
                      <p className="text-xs text-stone-400 mt-1">{(idFile?.size / 1024 / 1024).toFixed(1)} MB</p>
                    </div>
                  ) : (
                    <div>
                      <div className="w-14 h-14 bg-stone-100 rounded-full flex items-center justify-center mx-auto mb-3">
                        <svg className="w-7 h-7 text-stone-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                      </div>
                      <p className="font-medium text-stone-600">Tap to upload your ID</p>
                      <p className="text-xs text-stone-400 mt-1">Passport, National ID, or Driving License</p>
                      <p className="text-xs text-stone-300 mt-0.5">JPEG, PNG, or PDF - max 10MB</p>
                    </div>
                  )}
                </div>
              )}

              {idFile && !idUploaded && (
                <button data-testid="btn-upload-id" onClick={uploadId} disabled={uploading} className="mt-4 w-full py-2.5 bg-emerald-600 text-white text-sm font-semibold rounded-lg hover:bg-emerald-700 disabled:opacity-50 transition">
                  {uploading ? "Uploading..." : "Upload Document"}
                </button>
              )}

              <div className="flex justify-between mt-6">
                <button data-testid="btn-back-step-1" onClick={() => setStep(0)} className="px-5 py-2.5 text-stone-500 text-sm font-medium hover:bg-stone-100 rounded-lg transition">
                  Back
                </button>
                <button data-testid="btn-next-step-1" onClick={() => setStep(2)} disabled={!canProceedStep1 && !idUploaded} className="px-6 py-2.5 bg-[#1e3a5f] text-white text-sm font-semibold rounded-lg hover:bg-[#15304f] disabled:opacity-40 disabled:cursor-not-allowed transition">
                  Continue
                </button>
              </div>
            </motion.div>
          )}

          {/* STEP 2: Terms & Conditions */}
          {step === 2 && (
            <motion.div key="step2" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="bg-white rounded-2xl shadow-sm border border-stone-200/60 p-6" data-testid="step-terms">
              <h2 className="text-lg font-semibold text-stone-800 mb-1">Terms & Conditions</h2>
              <p className="text-sm text-stone-400 mb-5">Please review and accept our hotel policies</p>

              {/* Policy Box */}
              <div className="bg-stone-50 rounded-xl border border-stone-200/60 p-5 max-h-56 overflow-y-auto text-xs text-stone-600 leading-relaxed mb-5" data-testid="terms-content">
                <h3 className="font-bold text-stone-800 text-sm mb-2">{reg?.hotel_name} — Guest Terms & Conditions</h3>
                <p className="mb-3"><strong>1. Check-in / Check-out:</strong> Check-in from {reg?.policies?.check_in_time || "15:00"}, Check-out by {reg?.policies?.check_out_time || "11:00"}. Late check-out subject to availability and additional charges.</p>
                <p className="mb-3"><strong>2. Identification:</strong> All guests are required to present valid photo identification upon arrival. The hotel reserves the right to refuse check-in without valid ID.</p>
                <p className="mb-3"><strong>3. Cancellation:</strong> Free cancellation up to {reg?.policies?.cancellation_hours || 24} hours before arrival. Late cancellations and no-shows may be charged the full amount of the first night.</p>
                <p className="mb-3"><strong>4. Payment:</strong> Full payment is required at check-in unless otherwise arranged. We accept major credit cards and bank transfers.</p>
                <p className="mb-3"><strong>5. Property Rules:</strong> Guests are responsible for any damage to hotel property. Smoking is prohibited in all indoor areas. Quiet hours are observed between 22:00 and 07:00.</p>
                <p className="mb-3"><strong>6. Liability:</strong> The hotel is not responsible for loss or damage to personal belongings. Valuables should be stored in the in-room safe or at reception.</p>
                <p><strong>7. Data Protection:</strong> Personal information is collected for registration purposes and processed in accordance with applicable data protection laws. Your data will not be shared with third parties without your consent.</p>
              </div>

              {/* Checkboxes */}
              <div className="space-y-3 mb-5">
                <label className="flex items-start gap-3 cursor-pointer" data-testid="terms-checkbox-label">
                  <input data-testid="terms-checkbox" type="checkbox" checked={termsAccepted} onChange={(e) => setTermsAccepted(e.target.checked)} className="mt-0.5 w-4 h-4 rounded border-stone-300 text-[#1e3a5f] focus:ring-[#1e3a5f]/30" />
                  <span className="text-sm text-stone-700">I have read and accept the <strong>Terms & Conditions</strong></span>
                </label>
                <label className="flex items-start gap-3 cursor-pointer" data-testid="privacy-checkbox-label">
                  <input data-testid="privacy-checkbox" type="checkbox" checked={privacyAccepted} onChange={(e) => setPrivacyAccepted(e.target.checked)} className="mt-0.5 w-4 h-4 rounded border-stone-300 text-[#1e3a5f] focus:ring-[#1e3a5f]/30" />
                  <span className="text-sm text-stone-700">I agree to the <strong>Privacy Policy</strong> and data processing</span>
                </label>
              </div>

              {/* Signature */}
              <div className="mb-5">
                <label className="block text-xs font-medium text-stone-600 mb-1.5">Digital Signature *</label>
                <input data-testid="input-signature" type="text" value={signature} onChange={(e) => setSignature(e.target.value)} className="w-full px-3 py-2.5 rounded-lg border border-stone-200 text-sm italic focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] outline-none transition" placeholder="Type your full name as signature" />
              </div>

              <div className="flex justify-between">
                <button data-testid="btn-back-step-2" onClick={() => setStep(1)} className="px-5 py-2.5 text-stone-500 text-sm font-medium hover:bg-stone-100 rounded-lg transition">
                  Back
                </button>
                <button data-testid="btn-submit-registration" onClick={async () => { if (idFile && !idUploaded) await uploadId(); submitForm(); }} disabled={!canProceedStep2 || submitting} className="px-6 py-2.5 bg-emerald-600 text-white text-sm font-semibold rounded-lg hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed transition">
                  {submitting ? "Submitting..." : "Complete Registration"}
                </button>
              </div>
            </motion.div>
          )}

          {/* STEP 3: Complete */}
          {step === 3 && (
            <motion.div key="step3" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="bg-white rounded-2xl shadow-sm border border-stone-200/60 p-8 text-center" data-testid="step-complete">
              <div className="w-20 h-20 bg-emerald-50 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-10 h-10 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
              </div>
              <h2 className="text-xl font-bold text-stone-800 mb-2">Registration Complete!</h2>
              <p className="text-stone-500 text-sm max-w-sm mx-auto mb-6">
                Thank you for completing your pre-arrival registration. We've sent you a welcome email with hotel information and local area guides.
              </p>

              {reg?.booking && (
                <div className="bg-stone-50 rounded-xl p-5 max-w-sm mx-auto text-left space-y-2" data-testid="completion-booking-summary">
                  <div className="flex justify-between text-sm"><span className="text-stone-500">Hotel</span><span className="font-medium text-stone-800">{reg.hotel_name}</span></div>
                  <div className="flex justify-between text-sm"><span className="text-stone-500">Check-in</span><span className="font-medium text-stone-800">{reg.booking.check_in}</span></div>
                  <div className="flex justify-between text-sm"><span className="text-stone-500">Check-out</span><span className="font-medium text-stone-800">{reg.booking.check_out}</span></div>
                  {reg.policies?.check_in_time && (
                    <div className="flex justify-between text-sm"><span className="text-stone-500">Check-in Time</span><span className="font-medium text-stone-800">From {reg.policies.check_in_time}</span></div>
                  )}
                </div>
              )}

              <p className="text-xs text-stone-400 mt-6">You can close this page. See you soon!</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Footer */}
      <div className="text-center py-4 text-[10px] text-stone-300">
        Powered by My Hotel Box
      </div>
    </div>
  );
}
