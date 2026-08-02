import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { X, Copy, CheckCircle, Clock, LinkSimple, ArrowsClockwise, EnvelopeSimple, WhatsappLogo, QrCode } from "@phosphor-icons/react";
import { QRCodeSVG } from "qrcode.react";
import { API } from "./config";

export const StripeLinkModal = ({ booking, onClose }) => {
  const [amount, setAmount] = useState(booking?.total_price || "");
  const [creating, setCreating] = useState(false);
  const [links, setLinks] = useState([]);
  const [newLink, setNewLink] = useState(null);
  const [sending, setSending] = useState(false);
  const [suggestion, setSuggestion] = useState(null);

  useEffect(() => {
    const leadDays = booking.check_in
      ? Math.max(0, Math.round((new Date(booking.check_in) - Date.now()) / 86400000)) : 0;
    axios.post(`${API}/deposit-policies/evaluate`, {
      property_id: booking.property_id, channel: booking.source || "",
      lead_days: leadDays, rooms: booking.rooms || 1,
      total_price: booking.total_price || 0,
    }).then(({ data }) => { if (data.matched) setSuggestion(data); }).catch(() => {});
  }, [booking]);

  const sendEmail = async () => {
    setSending(true);
    try {
      const { data } = await axios.post(`${API}/pay-links/send`, {
        booking_id: booking.id, checkout_url: newLink.checkout_url,
        amount: newLink.amount, currency: (newLink.currency || "gbp").toUpperCase(),
      });
      toast.success(data.status === "mocked"
        ? `E-posta hazırlandı (${data.to}) — demo modunda gerçek gönderim yapılmadı`
        : `Payment link emailed to ${data.to}`);
    } catch (e) { toast.error(e.response?.data?.detail || "Email failed"); }
    setSending(false);
  };

  const openWhatsApp = () => {
    const phone = (booking.guest_phone || "").replace(/[^\d]/g, "");
    const msg = encodeURIComponent(
      `Hello ${booking.guest_name || ""}, please use this secure link to complete your payment of ${(newLink.currency || "gbp").toUpperCase()} ${newLink.amount?.toFixed(2)}: ${newLink.checkout_url}`);
    window.open(phone ? `https://wa.me/${phone}?text=${msg}` : `https://wa.me/?text=${msg}`, "_blank");
  };

  const fetchLinks = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/pay-links/${booking.id}`); setLinks(data); } catch (e) { /* silent */ }
  }, [booking.id]);

  useEffect(() => { fetchLinks(); }, [fetchLinks]);

  const createLink = async () => {
    setCreating(true);
    try {
      const { data } = await axios.post(`${API}/pay-links/create`, {
        booking_id: booking.id,
        amount: amount ? parseFloat(amount) : null,
        origin_url: window.location.origin,
      });
      setNewLink(data);
      try { await navigator.clipboard?.writeText(data.checkout_url); } catch (err) { /* clipboard blocked */ }
      toast.success("Stripe payment link created & copied to clipboard");
      fetchLinks();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to create payment link");
    }
    setCreating(false);
  };

  const checkStatus = async (sessionId) => {
    try {
      const { data } = await axios.get(`${API}/pay-links/status/${sessionId}`);
      if (data.payment_status === "paid") toast.success("Payment received!");
      else toast.info(`Status: ${data.payment_status}`);
      fetchLinks();
    } catch (e) { toast.error("Status check failed"); }
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose} data-testid="stripe-link-modal">
      <div className="bg-white rounded-xl w-full max-w-md shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="px-5 py-4 border-b border-stone-100 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-stone-800 flex items-center gap-1.5">
              <LinkSimple size={15} className="text-indigo-600" weight="bold" /> Stripe Payment Link
            </h3>
            <p className="text-[11px] text-stone-400 mt-0.5">{booking.booking_ref} — {booking.guest_name}</p>
          </div>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-600" data-testid="stripe-modal-close"><X size={16} /></button>
        </div>

        <div className="p-5 space-y-4">
          <div>
            <label className="text-[11px] font-semibold text-stone-500 uppercase">Amount ({booking.currency || "GBP"})</label>
            <div className="flex gap-1.5 mt-1 mb-1.5">
              {[{ label: "Full", pct: 100 }, { label: "50%", pct: 50 }, { label: "30% deposit", pct: 30 }].map(p => (
                <button key={p.pct}
                  onClick={() => setAmount(((booking.total_price || 0) * p.pct / 100).toFixed(2))}
                  className={`text-[10px] px-2 py-1 rounded-full border font-medium transition-colors ${parseFloat(amount) === +((booking.total_price || 0) * p.pct / 100).toFixed(2) ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-stone-600 border-stone-200 hover:border-indigo-300"}`}
                  data-testid={`stripe-preset-${p.pct}`}>
                  {p.label}
                </button>
              ))}
            </div>
            <div className="flex gap-2 mt-1">
              <input type="number" min="0" step="0.01" value={amount} onChange={e => setAmount(e.target.value)}
                className="flex-1 border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid="stripe-amount-input" />
              <button onClick={createLink} disabled={creating}
                className="px-4 py-2 bg-indigo-600 text-white text-xs font-semibold rounded-lg hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-1.5"
                data-testid="stripe-create-link-btn">
                {creating ? <ArrowsClockwise size={13} className="animate-spin" /> : <LinkSimple size={13} weight="bold" />}
                {creating ? "Creating…" : "Create Link"}
              </button>
            </div>
            {suggestion && (
              <button onClick={() => setAmount(suggestion.deposit_required.toFixed(2))}
                className="mt-1.5 w-full text-left text-[11px] px-3 py-2 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 hover:bg-rose-100 transition-colors"
                data-testid="stripe-deposit-suggestion">
                <b>Deposit policy: {suggestion.policy?.name}</b> — suggested £{suggestion.deposit_required.toFixed(2)}
                {suggestion.non_refundable ? " · non-refundable" : ""} · due in {suggestion.due_within_hours}h (click to apply)
              </button>
            )}
          </div>

          {newLink && (
            <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-3" data-testid="stripe-new-link">
              <div className="text-[10px] font-semibold text-indigo-700 uppercase mb-1">Link ready — copied to clipboard</div>
              <div className="flex items-center gap-2">
                <input readOnly value={newLink.checkout_url} className="flex-1 text-[11px] bg-white border border-indigo-200 rounded px-2 py-1.5 text-stone-600 truncate" />
                <button onClick={() => { navigator.clipboard?.writeText(newLink.checkout_url).then(() => toast.success("Copied")).catch(() => toast.error("Copy blocked — select the link manually")); }}
                  className="p-1.5 bg-white border border-indigo-200 rounded hover:bg-indigo-100" data-testid="stripe-copy-link-btn">
                  <Copy size={13} className="text-indigo-600" />
                </button>
              </div>
              <p className="text-[10px] text-indigo-500 mt-1.5">Share via email, WhatsApp or SMS. Guest pays securely on Stripe.</p>
              <div className="mt-2.5 flex items-center gap-3 bg-white border border-indigo-100 rounded-lg p-2.5" data-testid="stripe-qr-block">
                <QRCodeSVG value={newLink.checkout_url} size={88} data-testid="stripe-qr-code" />
                <div className="text-[10px] text-stone-500 leading-relaxed">
                  <b className="text-stone-700 flex items-center gap-1"><QrCode size={12} /> Kiosk / Reception QR</b>
                  Guest scans with their phone camera and pays instantly on Stripe.
                </div>
              </div>
              <div className="flex gap-2 mt-2.5">
                <button onClick={sendEmail} disabled={sending}
                  className="flex-1 px-3 py-1.5 bg-white border border-indigo-300 text-indigo-700 text-[11px] font-semibold rounded-lg hover:bg-indigo-100 disabled:opacity-50 flex items-center justify-center gap-1.5"
                  data-testid="stripe-send-email-btn">
                  {sending ? <ArrowsClockwise size={12} className="animate-spin" /> : <EnvelopeSimple size={12} weight="bold" />}
                  {sending ? "Sending…" : "Send Email"}
                </button>
                <button onClick={openWhatsApp}
                  className="flex-1 px-3 py-1.5 bg-emerald-600 text-white text-[11px] font-semibold rounded-lg hover:bg-emerald-700 flex items-center justify-center gap-1.5"
                  data-testid="stripe-send-whatsapp-btn">
                  <WhatsappLogo size={13} weight="fill" /> WhatsApp
                </button>
              </div>
            </div>
          )}

          {links.length > 0 && (
            <div>
              <div className="text-[11px] font-semibold text-stone-500 uppercase mb-1.5">Link History</div>
              <div className="space-y-1.5 max-h-44 overflow-y-auto" data-testid="stripe-link-history">
                {links.map((l, i) => (
                  <div key={i} className="flex items-center justify-between bg-stone-50 border border-stone-100 rounded-lg px-3 py-2 text-xs">
                    <div className="flex items-center gap-2">
                      {l.payment_status === "paid"
                        ? <CheckCircle size={14} className="text-emerald-500" weight="fill" />
                        : <Clock size={14} className="text-amber-500" />}
                      <div>
                        <span className="font-semibold text-stone-700">£{l.amount?.toFixed(2)}</span>
                        <span className={`ml-2 text-[9px] px-1.5 py-0.5 rounded-full font-medium ${l.payment_status === "paid" ? "bg-emerald-100 text-emerald-700" : l.payment_status === "pending" ? "bg-amber-100 text-amber-700" : "bg-stone-100 text-stone-500"}`}>{l.payment_status}</span>
                        <div className="text-[10px] text-stone-400">{l.created_at?.slice(0, 16).replace("T", " ")}</div>
                      </div>
                    </div>
                    {l.payment_status === "pending" && (
                      <button onClick={() => checkStatus(l.session_id)}
                        className="text-[10px] px-2 py-1 bg-white border border-stone-200 rounded hover:bg-stone-100 text-stone-600"
                        data-testid={`stripe-check-status-${i}`}>
                        Check
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
