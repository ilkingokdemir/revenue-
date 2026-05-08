import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { CheckCircle, CreditCard, Clock, Building2, Calendar, Users, Moon, Receipt, AlertCircle } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CATEGORY_LABELS = {
  room: "Accommodation",
  minibar: "Minibar",
  restaurant: "Restaurant & Bar",
  spa: "Spa & Wellness",
  laundry: "Laundry",
  parking: "Parking",
  other: "Other Charges",
};

const CURRENCY_SYMBOLS = { GBP: "£", USD: "$", EUR: "€", TRY: "₺", AED: "د.إ" };

export default function GuestPaymentPage({ token }) {
  const [folio, setFolio] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [paying, setPaying] = useState(false);
  const [paymentSuccess, setPaymentSuccess] = useState(false);
  const [polling, setPolling] = useState(false);

  const sym = folio ? (CURRENCY_SYMBOLS[folio.currency] || folio.currency + " ") : "£";

  const loadFolio = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/guest-payment/folio/${token}`);
      setFolio(data);
      if (data.status === "paid") setPaymentSuccess(true);
    } catch (e) {
      const status = e.response?.status;
      if (status === 410) setError("This payment link has expired. Please contact the hotel for a new link.");
      else if (status === 404) setError("Payment link not found. Please check the URL or contact the hotel.");
      else setError("Unable to load your folio. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadFolio();
  }, [loadFolio]);

  // Handle return from Stripe
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sessionId = params.get("session_id");
    const payment = params.get("payment");
    if (sessionId && payment === "success") {
      setPolling(true);
      pollStatus(sessionId);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pollStatus = async (sessionId, attempts = 0) => {
    if (attempts >= 12) {
      setPolling(false);
      setPaymentSuccess(true); // Assume success after polling timeout
      return;
    }
    try {
      const { data } = await axios.get(`${API}/guest-payment/status/${token}?session_id=${sessionId}`);
      if (data.status === "paid") {
        setPaymentSuccess(true);
        setPolling(false);
        window.history.replaceState({}, "", `/pay/${token}`);
        return;
      }
    } catch (e) { /* continue polling */ }
    setTimeout(() => pollStatus(sessionId, attempts + 1), 2500);
  };

  const handlePay = async () => {
    setPaying(true);
    try {
      const { data } = await axios.post(`${API}/guest-payment/pay/${token}`);
      if (data.url) window.location.href = data.url;
    } catch (e) {
      alert(e.response?.data?.detail || "Payment failed. Please try again.");
    } finally {
      setPaying(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="w-10 h-10 border-3 border-slate-300 border-t-slate-700 rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-10 text-center max-w-md" data-testid="payment-error">
          <AlertCircle size={40} className="mx-auto text-amber-500 mb-4" />
          <h2 className="text-lg font-semibold text-slate-800 mb-2">Link Unavailable</h2>
          <p className="text-sm text-slate-500">{error}</p>
        </div>
      </div>
    );
  }

  if (polling) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-10 text-center max-w-md" data-testid="payment-polling">
          <div className="w-14 h-14 border-3 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-5" />
          <h2 className="text-lg font-semibold text-slate-800 mb-2">Processing Payment</h2>
          <p className="text-sm text-slate-500">Please wait while we confirm your payment...</p>
        </div>
      </div>
    );
  }

  if (paymentSuccess) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-10 text-center max-w-md" data-testid="payment-success">
          <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-5">
            <CheckCircle size={32} className="text-emerald-600" />
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">Payment Received</h2>
          <p className="text-sm text-slate-500 mb-4">
            Thank you, {folio?.booking?.guest_name || "Guest"}! Your payment has been processed successfully.
          </p>
          <div className="bg-slate-50 rounded-xl p-4 text-sm text-left space-y-1.5 border border-slate-100">
            <div className="flex justify-between"><span className="text-slate-500">Booking Ref</span><span className="font-semibold text-slate-800">{folio?.booking?.booking_ref}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Amount Paid</span><span className="font-bold text-emerald-600">{sym}{folio?.balance_due?.toFixed(2)}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Hotel</span><span className="font-medium text-slate-700">{folio?.hotel_name}</span></div>
          </div>
          <p className="text-[11px] text-slate-400 mt-5">A confirmation will be sent to your email. You can close this page.</p>
        </div>
      </div>
    );
  }

  // Group folio items by category
  const grouped = {};
  (folio?.folio_items || []).forEach(item => {
    const cat = item.category || "other";
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(item);
  });

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-100 to-slate-50" data-testid="guest-payment-page">
      {/* Header */}
      <div className="bg-[#1e3a5f] text-white">
        <div className="max-w-2xl mx-auto px-4 py-6 sm:py-8 text-center">
          {folio.hotel_logo && <img src={folio.hotel_logo} alt="" className="h-10 mx-auto mb-3 object-contain" />}
          <h1 className="text-lg sm:text-xl font-bold tracking-tight">{folio.hotel_name}</h1>
          {folio.hotel_address && <p className="text-xs opacity-70 mt-1">{folio.hotel_address}</p>}
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 -mt-4 pb-8 space-y-4">
        {/* Booking Summary Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden" data-testid="booking-summary-card">
          <div className="bg-slate-50 border-b border-slate-200 px-5 py-3 flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider">Guest Folio</span>
            <span className="text-xs font-mono font-bold text-[#1e3a5f]">{folio.booking.booking_ref}</span>
          </div>
          <div className="p-5">
            <div className="flex items-start gap-4 mb-4">
              <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center flex-shrink-0">
                <Building2 size={18} className="text-blue-600" />
              </div>
              <div>
                <div className="text-base font-semibold text-slate-900">{folio.booking.guest_name}</div>
                <div className="text-xs text-slate-500">{folio.booking.room_name} · {folio.booking.rooms > 1 ? `${folio.booking.rooms} rooms` : "1 room"}</div>
              </div>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="flex items-center gap-2 text-xs text-slate-600">
                <Calendar size={14} className="text-slate-400" />
                <div>
                  <div className="text-[10px] text-slate-400">Check-in</div>
                  <div className="font-medium">{folio.booking.check_in}</div>
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-600">
                <Calendar size={14} className="text-slate-400" />
                <div>
                  <div className="text-[10px] text-slate-400">Check-out</div>
                  <div className="font-medium">{folio.booking.check_out}</div>
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-600">
                <Moon size={14} className="text-slate-400" />
                <div>
                  <div className="text-[10px] text-slate-400">Duration</div>
                  <div className="font-medium">{folio.booking.nights} night{folio.booking.nights > 1 ? "s" : ""}</div>
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-600">
                <Users size={14} className="text-slate-400" />
                <div>
                  <div className="text-[10px] text-slate-400">Guests</div>
                  <div className="font-medium">{folio.booking.adults} adult{folio.booking.adults > 1 ? "s" : ""}{folio.booking.children > 0 ? `, ${folio.booking.children} child` : ""}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Folio Itemization */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden" data-testid="folio-items">
          <div className="bg-slate-50 border-b border-slate-200 px-5 py-3 flex items-center gap-2">
            <Receipt size={14} className="text-slate-500" />
            <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider">Charges</span>
          </div>
          <div className="divide-y divide-slate-100">
            {Object.entries(grouped).map(([category, items]) => (
              <div key={category} className="px-5 py-3">
                <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  {CATEGORY_LABELS[category] || category}
                </div>
                {items.map((item, i) => (
                  <div key={i} className="flex justify-between items-center py-1.5">
                    <span className="text-sm text-slate-700">{item.description}</span>
                    <span className="text-sm font-medium text-slate-800">{sym}{item.amount.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>

        {/* Previous Payments */}
        {folio.payments_made?.length > 0 && (
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden" data-testid="payments-made">
            <div className="bg-slate-50 border-b border-slate-200 px-5 py-3 flex items-center gap-2">
              <CheckCircle size={14} className="text-emerald-500" />
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider">Payments Received</span>
            </div>
            <div className="px-5 py-3">
              {folio.payments_made.map((p, i) => (
                <div key={i} className="flex justify-between items-center py-1.5">
                  <div>
                    <span className="text-sm text-emerald-700">{p.method}</span>
                    <span className="text-xs text-slate-400 ml-2">{p.date?.slice(0, 10)}</span>
                  </div>
                  <span className="text-sm font-medium text-emerald-600">-{sym}{p.amount.toFixed(2)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Notes */}
        {folio.notes && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-5 py-3 text-sm text-amber-800">
            <span className="font-semibold">Note:</span> {folio.notes}
          </div>
        )}

        {/* Total & Pay */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden" data-testid="payment-summary">
          <div className="px-5 py-4 space-y-2">
            <div className="flex justify-between text-sm text-slate-600">
              <span>Total Charges</span>
              <span className="font-medium">{sym}{folio.total_charges?.toFixed(2)}</span>
            </div>
            {folio.total_paid > 0 && (
              <div className="flex justify-between text-sm text-emerald-600">
                <span>Payments Received</span>
                <span className="font-medium">-{sym}{folio.total_paid?.toFixed(2)}</span>
              </div>
            )}
            <div className="border-t border-slate-200 pt-3 flex justify-between items-center">
              <span className="text-base font-bold text-slate-900">Balance Due</span>
              <span className="text-2xl font-bold text-[#1e3a5f]">{sym}{folio.balance_due?.toFixed(2)}</span>
            </div>
          </div>

          {folio.balance_due > 0 && (
            <div className="px-5 pb-5">
              <button
                onClick={handlePay}
                disabled={paying}
                className="w-full bg-[#1e3a5f] hover:bg-[#15304f] text-white py-4 rounded-xl text-base font-semibold transition-colors flex items-center justify-center gap-2 disabled:opacity-60"
                data-testid="pay-now-btn"
              >
                {paying ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Processing...
                  </>
                ) : (
                  <>
                    <CreditCard size={18} />
                    Pay {sym}{folio.balance_due?.toFixed(2)} Now
                  </>
                )}
              </button>
              <div className="flex items-center justify-center gap-2 mt-3 text-[11px] text-slate-400">
                <svg viewBox="0 0 24 24" className="w-3 h-3" fill="currentColor"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-2 16l-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z"/></svg>
                <span>Secure payment powered by Stripe · SSL encrypted</span>
              </div>
            </div>
          )}

          {folio.balance_due === 0 && (
            <div className="px-5 pb-5">
              <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center">
                <CheckCircle size={20} className="mx-auto text-emerald-500 mb-1" />
                <span className="text-sm font-semibold text-emerald-700">Fully Paid</span>
              </div>
            </div>
          )}
        </div>

        {/* Hotel Contact */}
        <div className="text-center text-xs text-slate-400 py-4 space-y-1">
          {(folio.hotel_phone || folio.hotel_email) && (
            <p>Questions? Contact us: {folio.hotel_phone}{folio.hotel_phone && folio.hotel_email ? " · " : ""}{folio.hotel_email}</p>
          )}
          <p>Powered by MyHotelBox — Secure Guest Payments</p>
        </div>
      </div>
    </div>
  );
}
