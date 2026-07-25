import { useState, useEffect, useRef } from "react";
import axios from "axios";
import { motion, AnimatePresence } from "framer-motion";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const BASE_URL = process.env.REACT_APP_BACKEND_URL;
const IDLE_TIMEOUT = 60000; // 60s reset

export default function CheckInKioskPage({ propertyId }) {
  const [screen, setScreen] = useState("welcome"); // welcome, search, results, verify, register, done
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [regToken, setRegToken] = useState(null);
  const [hotelName, setHotelName] = useState("Hotel");
  const [completion, setCompletion] = useState(null);    // { guest_name, room_name, qr_url, ... }
  const [pendingBooking, setPendingBooking] = useState(null); // booking being verified
  const [dispatched, setDispatched] = useState(null);   // reception-dispatched reservation
  const [captures, setCaptures] = useState({ id: false, selfie: false });
  const [camError, setCamError] = useState("");
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const idleTimer = useRef(null);
  const pollTimer = useRef(null);

  // Load hotel name
  useEffect(() => {
    axios.get(`${API}/guest-journey/kiosk-info/${propertyId}`).then(r => {
      if (r.data?.hotel_name) setHotelName(r.data.hotel_name);
    }).catch(() => {});
  }, [propertyId]);

  // Poll the inner registration status every 4s while on register screen.
  // When completed → fetch room assignment + QR → jump to 'done' screen.
  useEffect(() => {
    if (screen !== "register" || !regToken) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const { data } = await axios.get(`${API}/guest-journey/kiosk-complete/${regToken}`);
        if (cancelled) return;
        if (data.completed) {
          setCompletion(data);
          setScreen("done");
        }
      } catch { /* keep polling silently */ }
    };
    pollTimer.current = setInterval(poll, 4000);
    return () => { cancelled = true; clearInterval(pollTimer.current); };
  }, [screen, regToken]);

  // Idle reset
  useEffect(() => {
    const reset = () => {
      clearTimeout(idleTimer.current);
      if (screen !== "welcome" && screen !== "done") {
        idleTimer.current = setTimeout(() => {
          setScreen("welcome"); setQuery(""); setResults([]); setRegToken(null); setCompletion(null);
        }, IDLE_TIMEOUT);
      }
      // Done screen has its own shorter 15s idle (show room, then reset)
      if (screen === "done") {
        idleTimer.current = setTimeout(() => {
          setScreen("welcome"); setQuery(""); setResults([]); setRegToken(null); setCompletion(null);
        }, 15000);
      }
    };
    window.addEventListener("touchstart", reset);
    window.addEventListener("click", reset);
    reset();
    return () => { window.removeEventListener("touchstart", reset); window.removeEventListener("click", reset); clearTimeout(idleTimer.current); };
  }, [screen]);

  // Poll the reception dispatch queue while on welcome screen
  useEffect(() => {
    if (screen !== "welcome") { setDispatched(null); return; }
    let cancelled = false;
    const poll = async () => {
      try {
        const { data } = await axios.get(`${API}/guest-journey/kiosk-queue/${propertyId}`);
        if (!cancelled && data.length > 0) setDispatched(data[0]);
      } catch { /* silent */ }
    };
    poll();
    const t = setInterval(poll, 8000);
    return () => { cancelled = true; clearInterval(t); };
  }, [screen, propertyId]);

  const acceptDispatch = async (e) => {
    e.stopPropagation();
    try { await axios.post(`${API}/guest-journey/kiosk-queue/${dispatched.id}/claim`); } catch { }
    const bid = dispatched.booking_id;
    setDispatched(null);
    startRegistration({ booking_id: bid });
  };

  // Camera helpers for ID/selfie verification step
  const startCamera = async () => {
    setCamError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
    } catch {
      setCamError("Kameraya erişilemedi — bu adımı atlayabilirsiniz.");
    }
  };
  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  };
  useEffect(() => {
    if (screen === "verify") startCamera();
    else stopCamera();
    return stopCamera;
  }, [screen]); // eslint-disable-line react-hooks/exhaustive-deps

  const capture = async (kind) => {
    const video = videoRef.current;
    if (!video || !streamRef.current) return;
    const canvas = document.createElement("canvas");
    canvas.width = 640;
    canvas.height = Math.round(640 * (video.videoHeight / (video.videoWidth || 640))) || 480;
    canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
    const b64 = canvas.toDataURL("image/jpeg", 0.6);
    try {
      await axios.post(`${API}/guest-journey/kiosk-id-capture/${pendingBooking.booking_id}`, {
        kind, image_base64: b64,
      });
      setCaptures((c) => ({ ...c, [kind]: true }));
    } catch { setCamError("Görsel kaydedilemedi, tekrar deneyin."); }
  };

  const proceedToRegister = () => {
    stopCamera();
    setScreen("register");
  };

  const search = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const { data } = await axios.get(`${API}/guest-journey/kiosk-lookup/${propertyId}?q=${encodeURIComponent(query.trim())}`);
      setResults(data);
      setScreen("results");
    } catch { setResults([]); }
    setSearching(false);
  };

  const startRegistration = async (booking) => {
    setPendingBooking(booking);
    setCaptures({ id: false, selfie: false });
    if (booking.registration_token) {
      setRegToken(booking.registration_token);
      setScreen("verify");
      return;
    }
    try {
      const { data } = await axios.post(`${API}/guest-journey/kiosk-register/${propertyId}`, { booking_id: booking.booking_id });
      setRegToken(data.token);
      setScreen("verify");
    } catch { }
  };

  // Welcome Screen
  if (screen === "welcome") {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#1e3a5f] via-[#15304f] to-[#0f2440] flex items-center justify-center p-8" data-testid="kiosk-welcome" onClick={() => setScreen("search")}>
        <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="text-center text-white max-w-lg">
          <div className="w-24 h-24 bg-white/10 backdrop-blur rounded-3xl flex items-center justify-center mx-auto mb-8">
            <svg className="w-12 h-12 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" /></svg>
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight mb-3" data-testid="kiosk-hotel-name">{hotelName}</h1>
          <p className="text-xl text-white/60 font-light mb-12">Self Check-In</p>
          <motion.div animate={{ scale: [1, 1.05, 1] }} transition={{ repeat: Infinity, duration: 2 }} className="inline-block">
            <div className="bg-white/15 backdrop-blur px-10 py-5 rounded-2xl border border-white/20">
              <p className="text-lg font-medium">Tap anywhere to begin</p>
            </div>
          </motion.div>
          {dispatched && (
            <motion.button initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
              onClick={acceptDispatch} data-testid="kiosk-dispatch-banner"
              className="mt-8 block mx-auto bg-emerald-500/20 backdrop-blur border-2 border-emerald-400 rounded-2xl px-8 py-4 text-left hover:bg-emerald-500/30 transition">
              <p className="text-emerald-300 text-xs font-bold uppercase tracking-wider">Resepsiyon sizi yönlendirdi</p>
              <p className="text-xl font-bold mt-0.5">👋 Hoş geldiniz, {dispatched.guest_name}</p>
              <p className="text-white/60 text-sm mt-0.5">Check-in'e başlamak için dokunun</p>
            </motion.button>
          )}
          <p className="text-white/30 text-xs mt-12">Powered by MyHotelBox &amp; ReveniQ</p>
        </motion.div>
      </div>
    );
  }

  // Search Screen
  if (screen === "search") {
    return (
      <div className="min-h-screen bg-gradient-to-br from-stone-50 to-slate-100 flex items-center justify-center p-8" data-testid="kiosk-search">
        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} className="max-w-lg w-full">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-stone-800 mb-2">Find Your Booking</h1>
            <p className="text-stone-500">Enter your booking reference or name</p>
          </div>
          <div className="bg-white rounded-2xl shadow-lg p-6 space-y-4">
            <input data-testid="kiosk-search-input" type="text" value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} autoFocus placeholder="Booking reference or last name..." className="w-full px-5 py-4 text-lg rounded-xl border-2 border-stone-200 focus:border-[#1e3a5f] focus:ring-4 focus:ring-[#1e3a5f]/10 outline-none transition" />
            <button data-testid="kiosk-search-btn" onClick={search} disabled={searching || !query.trim()} className="w-full py-4 bg-[#1e3a5f] text-white text-lg font-semibold rounded-xl hover:bg-[#15304f] disabled:opacity-40 transition">
              {searching ? "Searching..." : "Search"}
            </button>
          </div>
          <button onClick={() => { setScreen("welcome"); setQuery(""); }} className="mt-6 text-stone-400 text-sm mx-auto block hover:text-stone-600 transition" data-testid="kiosk-back-welcome">
            Back to welcome screen
          </button>
        </motion.div>
      </div>
    );
  }

  // Results Screen
  if (screen === "results") {
    return (
      <div className="min-h-screen bg-gradient-to-br from-stone-50 to-slate-100 flex items-center justify-center p-8" data-testid="kiosk-results">
        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} className="max-w-lg w-full">
          <div className="text-center mb-6">
            <h1 className="text-2xl font-bold text-stone-800 mb-1">Select Your Booking</h1>
            <p className="text-stone-500 text-sm">Found {results.length} booking{results.length !== 1 ? "s" : ""}</p>
          </div>

          <div className="space-y-3 max-h-[60vh] overflow-y-auto">
            {results.length === 0 ? (
              <div className="bg-white rounded-2xl shadow-sm p-8 text-center" data-testid="kiosk-no-results">
                <p className="text-stone-500 text-lg">No bookings found</p>
                <p className="text-stone-400 text-sm mt-1">Please check your booking reference or ask at reception</p>
              </div>
            ) : (
              results.map((b, i) => (
                <motion.button key={b.booking_id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }} data-testid={`kiosk-booking-${b.booking_id}`} onClick={() => startRegistration(b)} className="w-full bg-white rounded-2xl shadow-sm p-5 text-left hover:shadow-md hover:border-[#1e3a5f]/30 border-2 border-transparent transition">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-lg font-semibold text-stone-800">{b.guest_name}</p>
                      <p className="text-sm text-stone-500 mt-0.5">Ref: {b.booking_ref}</p>
                      {propertyId === "all" && b.property_id && (
                        <p className="text-xs text-[#1e3a5f] font-medium mt-1" data-testid={`kiosk-booking-prop-${b.booking_id}`}>
                          🏨 {b.property_id}
                        </p>
                      )}
                    </div>
                    {b.registration_status === "completed" ? (
                      <span className="px-3 py-1 bg-emerald-50 text-emerald-700 text-xs font-semibold rounded-full">Completed</span>
                    ) : (
                      <svg className="w-6 h-6 text-[#1e3a5f]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
                    )}
                  </div>
                  <div className="flex gap-4 mt-2 text-xs text-stone-400">
                    <span>Check-in: {b.check_in}</span>
                    <span>Check-out: {b.check_out}</span>
                    <span>{b.rooms} room{b.rooms > 1 ? "s" : ""}</span>
                  </div>
                </motion.button>
              ))
            )}
          </div>

          <button onClick={() => { setScreen("search"); setResults([]); }} className="mt-6 text-stone-400 text-sm mx-auto block hover:text-stone-600 transition" data-testid="kiosk-back-search">
            Search again
          </button>
        </motion.div>
      </div>
    );
  }

  // Identity verification (ID + selfie) before registration
  if (screen === "verify") {
    return (
      <div className="min-h-screen bg-gradient-to-br from-stone-50 to-slate-100 flex items-center justify-center p-8" data-testid="kiosk-verify">
        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} className="max-w-lg w-full">
          <div className="text-center mb-6">
            <h1 className="text-2xl font-bold text-stone-800 mb-1">Kimlik Doğrulama</h1>
            <p className="text-stone-500 text-sm">Güvenliğiniz için kimliğinizin fotoğrafını ve bir selfie'nizi çekin</p>
          </div>
          <div className="bg-white rounded-2xl shadow-lg p-5">
            <div className="rounded-xl overflow-hidden bg-stone-900 aspect-video mb-4 relative">
              <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover" data-testid="kiosk-camera" />
              {camError && (
                <div className="absolute inset-0 flex items-center justify-center bg-stone-900/80 text-white text-sm p-4 text-center" data-testid="kiosk-cam-error">{camError}</div>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <button onClick={() => capture("id")} disabled={!!camError} data-testid="kiosk-capture-id"
                className={`py-3.5 rounded-xl text-sm font-semibold border-2 transition ${captures.id ? "bg-emerald-50 border-emerald-400 text-emerald-700" : "border-stone-200 text-stone-700 hover:border-[#1e3a5f] disabled:opacity-40"}`}>
                {captures.id ? "✓ Kimlik alındı" : "📇 Kimlik fotoğrafı çek"}
              </button>
              <button onClick={() => capture("selfie")} disabled={!!camError} data-testid="kiosk-capture-selfie"
                className={`py-3.5 rounded-xl text-sm font-semibold border-2 transition ${captures.selfie ? "bg-emerald-50 border-emerald-400 text-emerald-700" : "border-stone-200 text-stone-700 hover:border-[#1e3a5f] disabled:opacity-40"}`}>
                {captures.selfie ? "✓ Selfie alındı" : "🤳 Selfie çek"}
              </button>
            </div>
            <button onClick={proceedToRegister} data-testid="kiosk-verify-continue"
              className={`w-full mt-4 py-4 text-lg font-semibold rounded-xl transition ${captures.id && captures.selfie ? "bg-emerald-600 text-white hover:bg-emerald-700" : "bg-[#1e3a5f] text-white hover:bg-[#15304f]"}`}>
              {captures.id && captures.selfie ? "Devam et →" : camError ? "Bu adımı atla →" : "Atla ve devam et →"}
            </button>
          </div>
          <button onClick={() => { stopCamera(); setScreen("results"); }} className="mt-6 text-stone-400 text-sm mx-auto block hover:text-stone-600 transition" data-testid="kiosk-verify-back">
            Geri dön
          </button>
        </motion.div>
      </div>
    );
  }

  // Registration (embedded iframe-like approach using the existing registration page)
  if (screen === "register" && regToken) {
    return (
      <div className="min-h-screen bg-stone-50" data-testid="kiosk-register">
        <div className="max-w-2xl mx-auto py-4 px-4">
          <button onClick={() => { setScreen("search"); setRegToken(null); setQuery(""); setResults([]); }} className="mb-2 text-stone-400 text-sm hover:text-stone-600 transition flex items-center gap-1" data-testid="kiosk-back-to-search">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
            Back to search
          </button>
        </div>
        <iframe src={`${BASE_URL}/register/${regToken}`} className="w-full border-0" style={{ height: "calc(100vh - 50px)" }} title="Guest Registration" data-testid="kiosk-registration-iframe" />
      </div>
    );
  }

  // Done — Welcome screen with room number + QR
  if (screen === "done" && completion) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#0f2440] via-[#15304f] to-[#1e3a5f] flex items-center justify-center p-8" data-testid="kiosk-done">
        <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="text-center text-white max-w-xl">
          <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 200, delay: 0.2 }}
            className="w-24 h-24 bg-emerald-500/20 backdrop-blur rounded-full flex items-center justify-center mx-auto mb-6 border-2 border-emerald-400">
            <svg className="w-14 h-14 text-emerald-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </motion.div>
          <h1 className="text-3xl font-bold mb-2">Welcome, {completion.guest_name.split(" ")[0] || "guest"}!</h1>
          <p className="text-white/60 mb-8">Your check-in is complete. Enjoy your stay.</p>
          <div className="bg-white/10 backdrop-blur rounded-2xl p-6 mb-6 border border-white/10">
            <p className="text-xs uppercase text-amber-300 font-bold tracking-wider mb-1">Your Room</p>
            <p className="text-4xl font-black mb-1" data-testid="kiosk-room-name">{completion.room_name}</p>
            <p className="text-sm text-white/60">{completion.room_type}</p>
            <div className="h-px bg-white/10 my-4" />
            <p className="text-xs uppercase text-white/40 mb-1">Stay</p>
            <p className="text-sm">{completion.check_in} → {completion.check_out}</p>
          </div>
          {completion.qr_url && (
            <div className="bg-white rounded-2xl p-4 inline-block mb-6" data-testid="kiosk-qr">
              <img src={completion.qr_url} alt="Room access QR" className="w-[220px] h-[220px]" />
              <p className="text-[10px] text-stone-500 mt-2">Scan at your room door · or show at reception</p>
            </div>
          )}
          <p className="text-white/30 text-xs">Returning to welcome screen in 15 seconds...</p>
        </motion.div>
      </div>
    );
  }

  return null;
}
