import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { UserCircle, Star, SignOut } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const TIER = { bronze: "Bronz", silver: "Gümüş", gold: "Altın", platinum: "Platin" };

export function GuestAccountBox({ propertyId, guestForm, setGuestForm, accent }) {
  const [profile, setProfile] = useState(null);
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(null);
  const [busy, setBusy] = useState(false);

  const apply = (p) => {
    setProfile(p);
    setGuestForm((f) => ({ ...f, guest_name: f.guest_name || p.name || "", guest_email: f.guest_email || p.email || "", guest_phone: f.guest_phone || p.phone || "" }));
  };
  useEffect(() => {
    const q = new URLSearchParams(window.location.search); const glt = q.get("glt");
    if (glt) {
      axios.get(`${API}/booking/guest-account/session/${glt}`).then(({ data }) => { localStorage.setItem("mhb_guest_session", data.session); apply(data.profile); toast.success(`Hoş geldiniz${data.profile.name ? ", " + data.profile.name : ""}!`); q.delete("glt"); window.history.replaceState({}, "", `${window.location.pathname}?${q}`); }).catch(() => toast.error("Giriş bağlantısı geçersiz veya süresi dolmuş"));
      return;
    }
    const s = localStorage.getItem("mhb_guest_session");
    if (s) axios.get(`${API}/booking/guest-account/me?session=${s}&property_id=${propertyId}`).then(({ data }) => apply(data.profile)).catch(() => localStorage.removeItem("mhb_guest_session"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [propertyId]);

  const send = async () => {
    const e = (email || guestForm.guest_email || "").trim(); if (!e.includes("@")) return toast.error("Geçerli e-posta girin");
    setBusy(true);
    try { const { data } = await axios.post(`${API}/booking/guest-account/magic-link`, { email: e, property_id: propertyId, return_path: window.location.pathname }); setSent(data); toast.success("Giriş bağlantısı e-postanıza gönderildi"); }
    catch { toast.error("Gönderilemedi"); } finally { setBusy(false); }
  };
  const logout = async () => { const s = localStorage.getItem("mhb_guest_session"); localStorage.removeItem("mhb_guest_session"); setProfile(null); if (s) axios.post(`${API}/booking/guest-account/logout`, { session: s }).catch(() => {}); };

  if (profile) {
    const lo = profile.loyalty || {};
    return (
      <div className="rounded-lg border p-4 mb-4 bg-emerald-50/50" style={{ borderColor: accent }} data-testid="guest-account-box">
        <div className="flex items-center gap-2 flex-wrap">
          <UserCircle size={22} weight="fill" style={{ color: accent }} />
          <div className="font-semibold text-slate-900" data-testid="guest-account-name">Hoş geldiniz{profile.name ? `, ${profile.name}` : ""}</div>
          <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-bold flex items-center gap-1" data-testid="guest-account-tier"><Star size={12} weight="fill" />{TIER[lo.tier] || lo.tier} üye{lo.points ? ` · ${lo.points.toLocaleString()} puan` : ""}</span>
          <span className="text-xs text-slate-500">{profile.stays} geçmiş konaklama</span>
          <button type="button" onClick={logout} className="ml-auto text-xs text-slate-500 underline flex items-center gap-1" data-testid="guest-account-logout"><SignOut size={12} />Çıkış</button>
        </div>
        <p className="text-xs text-slate-600 mt-1">Bilgileriniz otomatik dolduruldu. {lo.points > 0 && "Puanlarınız konaklama sonrası hesabınıza işlenir."}</p>
        {profile.past?.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2" data-testid="guest-account-past">
            {profile.past.slice(0, 3).map((b) => (
              <a key={b.booking_ref} href={b.rebook_url} className="text-xs bg-white border border-slate-200 rounded-lg px-2 py-1 hover:border-slate-400" data-testid={`guest-rebook-${b.booking_ref}`}>↻ {b.room_name || "Oda"} · {b.check_in} — tekrar rezerve et</a>
            ))}
          </div>
        )}
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-dashed border-slate-300 p-3 mb-4 text-sm" data-testid="guest-login-box">
      <div className="font-semibold text-slate-800">Daha önce bizde kaldınız mı?</div>
      <p className="text-xs text-slate-500 mb-2">E-postanıza tek kullanımlık giriş bağlantısı gönderelim — bilgileriniz otomatik dolsun, geçmiş konaklamalarınızı ve puanlarınızı görün.</p>
      <div className="flex gap-2">
        <input type="email" value={email || guestForm.guest_email || ""} onChange={(e) => setEmail(e.target.value)} placeholder="ornek@eposta.com" className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm" data-testid="guest-login-email" />
        <button type="button" onClick={send} disabled={busy} className="px-3 py-2 rounded-lg text-white text-sm font-semibold disabled:opacity-50" style={{ background: accent }} data-testid="guest-login-send">Bağlantı gönder</button>
      </div>
      {sent && <div className="text-xs text-emerald-700 mt-2" data-testid="guest-login-sent">Bağlantı gönderildi ({sent.expires_in_min} dk geçerli).{sent.dev_link && <> <a className="underline" href={sent.dev_link} data-testid="guest-login-dev-link">Test: bağlantıyı aç</a></>}</div>}
    </div>
  );
}
