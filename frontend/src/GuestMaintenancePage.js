import { useState, useEffect, useRef } from "react";
import axios from "axios";
import { motion } from "framer-motion";
import { useTranslation } from "@/i18n";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CATEGORIES = [
  { value: "plumbing", label: "Plumbing / Water" },
  { value: "electrical", label: "Electrical / Lights" },
  { value: "hvac", label: "AC / Heating" },
  { value: "appliance", label: "Appliance / TV" },
  { value: "furniture", label: "Furniture" },
  { value: "cleaning", label: "Cleaning" },
  { value: "it_network", label: "WiFi / Internet" },
  { value: "general", label: "Other" },
];

export default function GuestMaintenancePage({ propertyId, roomId }) {
  const { t } = useTranslation();
  const [hotelName, setHotelName] = useState("Hotel");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("general");
  const [guestName, setGuestName] = useState("");
  const [photo, setPhoto] = useState(null);
  const [preview, setPreview] = useState(null);
  const fileRef = useRef(null);
  const cameraRef = useRef(null);

  useEffect(() => {
    axios.get(`${API}/maintenance/guest-report-info/${propertyId}/${roomId}`).then(r => {
      setHotelName(r.data.hotel_name || "Hotel");
    }).catch(() => {});
  }, [propertyId, roomId]);

  const handlePhoto = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPhoto(file);
    const reader = new FileReader();
    reader.onload = (ev) => setPreview(ev.target.result);
    reader.readAsDataURL(file);
  };

  const submit = async () => {
    if (!title.trim()) return;
    setSubmitting(true);
    try {
      const { data } = await axios.post(`${API}/maintenance/guest-report/${propertyId}/${roomId}`, {
        title, description, category, guest_name: guestName || "Guest",
      });
      if (photo && data.id) {
        const fd = new FormData();
        fd.append("file", photo);
        await axios.post(`${API}/maintenance/guest-upload-photo/${data.id}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      }
      setSubmitted(true);
    } catch {
      alert("Failed to submit. Please try again or contact reception.");
    }
    setSubmitting(false);
  };

  if (submitted) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-emerald-50 to-stone-50 flex items-center justify-center p-4">
        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="bg-white rounded-2xl shadow-lg p-8 max-w-md w-full text-center" data-testid="report-submitted">
          <div className="w-20 h-20 bg-emerald-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-10 h-10 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
          </div>
          <h2 className="text-xl font-bold text-stone-800 mb-2">Report Submitted!</h2>
          <p className="text-stone-500 text-sm">Thank you for letting us know. Our maintenance team has been notified and will address this as soon as possible.</p>
          <p className="text-xs text-stone-400 mt-4">Room {roomId} &middot; {hotelName}</p>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-stone-50 to-orange-50/20" data-testid="guest-maintenance-page">
      {/* Header */}
      <header className="bg-[#b45309] text-white">
        <div className="max-w-lg mx-auto px-4 py-5 text-center relative">
          <div className="absolute right-4 top-3"><LanguageSwitcher compact /></div>
          <h1 className="text-lg font-bold">{hotelName}</h1>
          <p className="text-white/70 text-sm mt-0.5">Room {roomId} — Report a Problem</p>
        </div>
      </header>

      <div className="max-w-lg mx-auto px-4 py-6">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="bg-white rounded-2xl shadow-sm border border-stone-200/60 p-5 space-y-4">
          <div>
            <p className="text-sm text-stone-500 mb-4">Something not working in your room? Let us know and we'll fix it.</p>
          </div>

          {/* Category Quick Select */}
          <div>
            <label className="text-xs font-medium text-stone-600 mb-2 block">What's the issue?</label>
            <div className="grid grid-cols-4 gap-2" data-testid="category-grid">
              {CATEGORIES.map(c => (
                <button key={c.value} onClick={() => setCategory(c.value)} className={`p-2.5 rounded-xl border-2 text-center transition text-xs font-medium ${category === c.value ? "border-[#b45309] bg-orange-50 text-[#b45309]" : "border-stone-200 text-stone-600 hover:border-stone-300"}`} data-testid={`cat-${c.value}`}>
                  {c.label}
                </button>
              ))}
            </div>
          </div>

          {/* Title */}
          <div>
            <label className="text-xs font-medium text-stone-600 mb-1.5 block">Short description *</label>
            <input data-testid="report-title" type="text" value={title} onChange={(e) => setTitle(e.target.value)} className="w-full px-3 py-2.5 rounded-lg border border-stone-200 text-sm focus:ring-2 focus:ring-[#b45309]/20 focus:border-[#b45309] outline-none transition" placeholder="e.g. AC not cooling, tap leaking..." />
          </div>

          {/* Detail */}
          <div>
            <label className="text-xs font-medium text-stone-600 mb-1.5 block">More details (optional)</label>
            <textarea data-testid="report-description" value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className="w-full px-3 py-2.5 rounded-lg border border-stone-200 text-sm focus:ring-2 focus:ring-[#b45309]/20 focus:border-[#b45309] outline-none transition resize-none" placeholder="Describe the problem..." />
          </div>

          {/* Photo */}
          <div>
            <label className="text-xs font-medium text-stone-600 mb-1.5 block">Photo (optional)</label>
            <input ref={cameraRef} type="file" accept="image/*" capture="environment" onChange={handlePhoto} className="hidden" />
            <input ref={fileRef} type="file" accept="image/*" onChange={handlePhoto} className="hidden" />
            {preview ? (
              <div className="relative">
                <img src={preview} alt="" className="w-full h-40 object-cover rounded-lg border border-stone-200" data-testid="report-photo-preview" />
                <button onClick={() => { setPhoto(null); setPreview(null); }} className="absolute top-2 right-2 w-6 h-6 bg-red-500 text-white rounded-full flex items-center justify-center text-xs">X</button>
              </div>
            ) : (
              <div className="flex gap-2">
                <button onClick={() => cameraRef.current?.click()} className="flex-1 py-3 border-2 border-dashed border-stone-300 rounded-lg text-stone-500 text-xs font-medium hover:border-[#b45309] hover:text-[#b45309] transition" data-testid="btn-report-camera">
                  <svg className="w-5 h-5 mx-auto mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                  Take Photo
                </button>
                <button onClick={() => fileRef.current?.click()} className="flex-1 py-3 border-2 border-dashed border-stone-300 rounded-lg text-stone-500 text-xs font-medium hover:border-[#b45309] hover:text-[#b45309] transition" data-testid="btn-report-gallery">
                  <svg className="w-5 h-5 mx-auto mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                  Gallery
                </button>
              </div>
            )}
          </div>

          {/* Guest Name */}
          <div>
            <label className="text-xs font-medium text-stone-600 mb-1.5 block">Your name (optional)</label>
            <input data-testid="report-guest-name" type="text" value={guestName} onChange={(e) => setGuestName(e.target.value)} className="w-full px-3 py-2.5 rounded-lg border border-stone-200 text-sm focus:ring-2 focus:ring-[#b45309]/20 focus:border-[#b45309] outline-none transition" placeholder="Room guest name" />
          </div>

          <button data-testid="btn-submit-report" onClick={submit} disabled={!title.trim() || submitting} className="w-full py-3 bg-[#b45309] text-white text-sm font-bold rounded-xl hover:bg-[#a14708] disabled:opacity-40 transition">
            {submitting ? "Submitting..." : "Report Issue"}
          </button>
        </motion.div>

        <p className="text-center text-[10px] text-stone-300 mt-4">For urgent issues, please call reception directly</p>
      </div>
    </div>
  );
}
