/**
 * RoomKeyPage (iter 371) — Digital Keys guest view
 * -------------------------------------------------
 * Guest opens `/room-key?token=xxx` on their phone; page shows a rotating
 * QR (30-sec) + backup 4-digit PIN. Door lock scans QR or accepts PIN.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { Loader2, Lock, RefreshCw, KeyRound, Clock, Sparkles } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function RoomKeyPage() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token") || "";
  const [key, setKey] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!token) { setError("Token eksik"); setLoading(false); return; }
    try {
      const r = await axios.get(`${API}/digital-keys/token/${token}`);
      setKey(r.data);
      setError(null);
    } catch (e) {
      setError(e?.response?.data?.detail || "Anahtar yüklenemedi");
    }
    setLoading(false);
  }, [token]);

  useEffect(() => {
    load();
    const t = setInterval(load, 30_000);   // rotate every 30s
    return () => clearInterval(t);
  }, [load]);

  if (loading) {
    return (
      <div className="min-h-screen bg-stone-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-amber-400" />
      </div>
    );
  }
  if (error || !key) {
    return (
      <div className="min-h-screen bg-stone-950 flex items-center justify-center p-6">
        <div className="text-center max-w-md space-y-3">
          <Lock className="w-14 h-14 text-stone-700 mx-auto" />
          <h1 className="text-xl font-bold text-stone-100">{error || "Anahtar bulunamadı"}</h1>
          <p className="text-sm text-stone-500">Resepsiyona başvurun veya yeni link isteyin.</p>
        </div>
      </div>
    );
  }

  // Encode QR string as a data URL using a public QR API (no external lib bundle)
  const qrImgUrl = `https://api.qrserver.com/v1/create-qr-code/?size=280x280&bgcolor=0-0-0&color=255-255-255&margin=0&data=${encodeURIComponent(key.qr_string)}`;

  const expiresIn = Math.round((new Date(key.expires_at).getTime() - Date.now()) / 60_000);

  return (
    <div className="min-h-screen bg-gradient-to-br from-stone-950 via-indigo-950 to-stone-950 text-stone-100 p-4">
      <div className="max-w-md mx-auto py-6 space-y-5">
        <header className="text-center">
          <img src="/logos/myhotelbox_horizontal.png" alt="MyHotelBox" className="h-10 mx-auto object-contain filter invert opacity-90" />
          <p className="text-xs uppercase tracking-[0.3em] text-stone-500 mt-3">Dijital Oda Anahtarı</p>
        </header>

        <div className="rounded-2xl bg-stone-900/60 border border-amber-500/30 p-5 text-center">
          <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-1">Misafir</div>
          <div className="text-lg font-bold" data-testid="rk-guest-name">{key.guest_name || "—"}</div>
          <div className="text-[10px] uppercase tracking-wider text-stone-500 mt-3 mb-1">Oda</div>
          <div className="text-4xl font-black text-amber-300" data-testid="rk-room">{key.room_number || "—"}</div>
        </div>

        <div className="rounded-2xl bg-white p-4 relative">
          <img src={qrImgUrl} alt="QR" className="w-full h-auto rounded" data-testid="rk-qr-img" />
          <div className="absolute top-2 right-2 flex items-center gap-1 text-[10px] font-bold text-stone-700 bg-white/80 px-2 py-0.5 rounded-full">
            <Clock className="w-3 h-3" /> {key.refresh_in}s
          </div>
        </div>

        <div className="rounded-2xl bg-stone-900/60 border border-stone-800 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <KeyRound className="w-5 h-5 text-fuchsia-400" />
              <div>
                <div className="text-[10px] uppercase tracking-wider text-stone-500">Backup PIN</div>
                <div className="text-2xl font-black tracking-[0.35em] font-mono" data-testid="rk-pin">{key.backup_pin}</div>
              </div>
            </div>
            <button
              onClick={load}
              className="p-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-200"
              data-testid="rk-refresh"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
          <p className="text-[11px] text-stone-500 mt-3">
            QR'ı kapı okuyucusuna tutun. Çalışmazsa PIN'i tuşlayın.
          </p>
        </div>

        <div className="text-center text-xs text-stone-500 flex items-center justify-center gap-1">
          <Sparkles className="w-3 h-3" /> QR her 30 sn otomatik yenilenir · Süre: {expiresIn > 0 ? `${expiresIn}dk` : "bitti"}
        </div>

        <footer className="text-center text-[10px] text-stone-600 pt-4">
          Powered by MyHotelBox &amp; ReveniQ
        </footer>
      </div>
    </div>
  );
}
