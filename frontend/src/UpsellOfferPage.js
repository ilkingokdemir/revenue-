import { useState, useEffect } from "react";
import axios from "axios";
import { CheckCircle, XCircle, Sparkle, CalendarBlank, Bed, UsersThree } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function UpsellOfferPage({ token }) {
  const [offer, setOffer] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState("");

  useEffect(() => {
    axios.get(`${API}/api/public/upsell-offer/${token}`)
      .then((r) => {
        setOffer(r.data);
        if (r.data.status === "accepted") setDone("accepted");
        if (r.data.status === "declined") setDone("declined");
      })
      .catch(() => setError("Teklif bulunamadı veya süresi dolmuş."));
  }, [token]);

  const act = async (action) => {
    setBusy(true);
    try {
      await axios.post(`${API}/api/public/upsell-offer/${token}/${action}`);
      setDone(action === "accept" ? "accepted" : "declined");
    } catch {
      setError("İşlem başarısız oldu, lütfen tekrar deneyin.");
    } finally { setBusy(false); }
  };

  if (error) return (
    <div className="min-h-screen bg-stone-100 flex items-center justify-center p-6">
      <div className="bg-white rounded-2xl shadow-sm border border-stone-200 p-8 max-w-md text-center" data-testid="offer-error">
        <XCircle size={40} className="text-rose-400 mx-auto mb-3" />
        <p className="text-stone-600 text-sm">{error}</p>
      </div>
    </div>
  );
  if (!offer) return <div className="min-h-screen bg-stone-100 flex items-center justify-center text-stone-400 text-sm">Yükleniyor…</div>;

  return (
    <div className="min-h-screen bg-stone-100 flex items-center justify-center p-6">
      <div className="bg-white rounded-2xl shadow-sm border border-stone-200 p-8 max-w-md w-full" data-testid="upsell-offer-page">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-amber-600 mb-4">
          <Sparkle size={14} weight="fill" />
          <span>{offer.hotel_name || "Otelinizden"} özel teklif</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">{offer.title}</h1>
        <p className="text-sm text-stone-500 mt-2">{offer.pitch}</p>

        <div className="bg-amber-50 border border-amber-100 rounded-xl p-4 mt-5 space-y-2 text-sm">
          <div className="flex items-center gap-2 text-stone-600">
            <CalendarBlank size={16} className="text-amber-600" />
            {offer.check_in} → {offer.check_out}
          </div>
          {offer.room_type && (
            <div className="flex items-center gap-2 text-stone-600">
              <Bed size={16} className="text-amber-600" /> {offer.room_type}
            </div>
          )}
          <div className="text-2xl font-semibold text-stone-900 pt-1" data-testid="offer-price">
            {offer.discount_active ? (
              <>
                <span className="line-through text-stone-400 text-lg mr-2">£{Number(offer.price || 0).toFixed(0)}</span>
                £{Number(offer.final_price || 0).toFixed(0)}
                <span className="ml-2 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-full px-2 py-0.5 align-middle">-%{offer.discount_pct} erken kabul</span>
              </>
            ) : (
              <>£{Number(offer.final_price ?? offer.price ?? 0).toFixed(0)}</>
            )}
          </div>
          {offer.discount_active && offer.expires_at && (
            <div className="text-xs text-amber-700" data-testid="offer-deadline">
              İndirim {new Date(offer.expires_at).toLocaleString("tr-TR", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" })} tarihine kadar geçerli
            </div>
          )}
        </div>

        {offer.social_count > 0 && (
          <div className="mt-3 flex items-center gap-2 text-xs text-stone-500" data-testid="offer-social-proof">
            <UsersThree size={16} className="text-amber-600" />
            Son 30 günde <span className="font-semibold text-stone-700">{offer.social_count} misafir</span> bu teklifi kabul etti
          </div>
        )}

        {done === "accepted" ? (
          <div className="mt-6 flex items-center gap-2 text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-xl p-4 text-sm font-medium" data-testid="offer-accepted">
            <CheckCircle size={20} weight="fill" /> Teklif kabul edildi — folyonuza eklendi. Sizi ağırlamak için sabırsızlanıyoruz!
          </div>
        ) : done === "declined" ? (
          <div className="mt-6 text-stone-500 bg-stone-50 border border-stone-200 rounded-xl p-4 text-sm" data-testid="offer-declined">
            Teklif reddedildi. Fikrinizi değiştirirseniz resepsiyona ulaşabilirsiniz.
          </div>
        ) : (
          <div className="mt-6 flex gap-3">
            <button onClick={() => act("accept")} disabled={busy} data-testid="offer-accept-btn"
              className="flex-1 bg-amber-600 hover:bg-amber-700 disabled:opacity-60 text-white font-semibold rounded-xl py-3 text-sm transition-colors">
              {busy ? "İşleniyor…" : "Kabul Et"}
            </button>
            <button onClick={() => act("decline")} disabled={busy} data-testid="offer-decline-btn"
              className="px-5 border border-stone-200 hover:border-stone-300 text-stone-600 rounded-xl py-3 text-sm transition-colors">
              Hayır, teşekkürler
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
