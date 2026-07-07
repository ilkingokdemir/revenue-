/**
 * SelfCheckoutPage (iter 367)
 * ---------------------------
 * Standalone public page that hotels link from the pre-checkout email
 * or a QR code in-room. The guest picks a check-out time and walks out.
 *
 * URL: /checkout?booking={bookingId}&email={email}
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { Loader2, DoorOpen, Home } from "lucide-react";
import ScheduleCheckoutWidget from "./components/dashboard/ScheduleCheckoutWidget";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function SelfCheckoutPage() {
  const params = new URLSearchParams(window.location.search);
  const bookingId = params.get("booking") || "";
  const guestEmail = params.get("email") || "";
  const [booking, setBooking] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!bookingId) { setLoading(false); setNotFound(true); return; }
    axios.get(`${API}/checkout/booking/${bookingId}/snapshot`)
      .then((r) => setBooking(r.data))
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [bookingId]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-stone-950 to-stone-900 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-amber-400" />
      </div>
    );
  }
  if (notFound || !bookingId) {
    return (
      <div className="min-h-screen bg-stone-950 flex items-center justify-center p-6">
        <div className="max-w-md text-center space-y-4">
          <DoorOpen className="w-16 h-16 text-stone-700 mx-auto" />
          <h1 className="text-2xl font-bold text-stone-100">Rezervasyon bulunamadı</h1>
          <p className="text-stone-400 text-sm">Bağlantı hatalı ya da rezervasyon süresi dolmuş olabilir. Lütfen resepsiyona ulaşın.</p>
          <a href="/" className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-100 text-sm">
            <Home className="w-4 h-4" /> Ana Sayfa
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-stone-950 via-stone-900 to-stone-950 py-8 px-4">
      <div className="max-w-xl mx-auto space-y-6">
        <header className="text-center pt-4">
          <img
            src="/logos/myhotelbox_horizontal.png"
            alt="MyHotelBox"
            className="h-10 mx-auto object-contain filter invert opacity-90"
          />
          <p className="text-xs uppercase tracking-[0.3em] text-stone-500 mt-3">Self Check-out</p>
        </header>

        <div className="rounded-2xl border border-stone-800 bg-stone-900/60 p-5">
          <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-1">Rezervasyon</div>
          <div className="text-stone-100 text-lg font-bold">
            {booking?.guest_name} {booking?.room_number ? `· Oda ${booking.room_number}` : ""}
          </div>
          <div className="text-stone-500 text-xs mt-0.5">
            {booking?.check_in_date} → {booking?.check_out_date}
          </div>
        </div>

        <ScheduleCheckoutWidget
          bookingId={bookingId}
          guestEmail={guestEmail || booking?.guest_email || ""}
        />

        <footer className="text-center pt-6 text-xs text-stone-600">
          Powered by MyHotelBox &amp; ReveniQ
        </footer>
      </div>
    </div>
  );
}
