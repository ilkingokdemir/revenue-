import React, { useEffect, useState } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function GuestPassPage() {
  const ref = decodeURIComponent(window.location.pathname.split("/pass/")[1]?.split("/")[0] || "");
  const email = new URLSearchParams(window.location.search).get("email") || "";
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    axios.get(`${API}/guest-pass/${encodeURIComponent(ref)}`, { params: { email } }).then((r) => setData(r.data)).catch((e) => setErr(e.response?.data?.detail || "Geçiş kartı bulunamadı"));
  }, [ref, email]);
  const q = `email=${encodeURIComponent(email)}`;
  const fmt = (d) => (d ? new Date(d).toLocaleDateString("tr-TR", { weekday: "short", day: "2-digit", month: "short", year: "numeric" }) : "—");
  const money = (v) => `${data?.currency ? data.currency.toUpperCase() + " " : ""}${Number(v || 0).toFixed(2)}`;
  if (err) return <div className="min-h-screen bg-stone-950 text-white flex items-center justify-center p-6 text-center" data-testid="guest-pass-error">{err}</div>;
  if (!data) return <div className="min-h-screen bg-stone-950 text-stone-400 flex items-center justify-center">Yükleniyor…</div>;
  const walletBtn = (label, ready, href, tid) => (
    <a href={ready ? href : undefined} onClick={(e) => { if (!ready) { e.preventDefault(); alert("Bu cüzdan bağlantısı için otel yönetimi sertifika/anahtar tanımlamalı."); } }}
      className={`flex-1 text-center rounded-xl py-3 text-sm font-bold ${ready ? "bg-white text-black" : "bg-stone-800 text-stone-500 cursor-not-allowed"}`} data-testid={tid}>{label}{!ready && <span className="block text-[10px] font-normal">yakında</span>}</a>
  );
  return (
    <div className="min-h-screen bg-stone-950 text-white flex items-start justify-center p-4 sm:p-8" data-testid="guest-pass-page">
      <div className="w-full max-w-md">
        <div className="rounded-3xl overflow-hidden bg-gradient-to-b from-stone-800 to-stone-900 border border-stone-700 shadow-2xl">
          <div className="p-5 border-b border-dashed border-stone-600">
            <div className="text-[10px] uppercase tracking-[0.25em] text-stone-400">Guest Pass</div>
            <div className="text-xl font-black mt-1" data-testid="guest-pass-hotel">{data.hotel?.name}</div>
            <div className="text-xs text-stone-400">{data.hotel?.address}</div>
          </div>
          <div className="p-5 grid grid-cols-2 gap-4">
            <div><div className="text-[10px] uppercase text-stone-400">Giriş</div><div className="font-bold" data-testid="guest-pass-checkin">{fmt(data.check_in)}</div><div className="text-xs text-stone-400">{data.hotel?.check_in_time}'dan itibaren</div></div>
            <div><div className="text-[10px] uppercase text-stone-400">Çıkış</div><div className="font-bold">{fmt(data.check_out)}</div><div className="text-xs text-stone-400">{data.hotel?.check_out_time}'a kadar</div></div>
            <div><div className="text-[10px] uppercase text-stone-400">Misafir</div><div className="font-bold">{data.guest_name}</div></div>
            <div><div className="text-[10px] uppercase text-stone-400">Oda</div><div className="font-bold">{data.room_name || "—"}{data.room_number ? ` · ${data.room_number}` : ""}</div></div>
            <div><div className="text-[10px] uppercase text-stone-400">Gece / Kişi</div><div className="font-bold">{data.nights} · {data.adults}{data.children ? `+${data.children}` : ""}</div></div>
            <div><div className="text-[10px] uppercase text-stone-400">Toplam</div><div className="font-bold">{money(data.total_price)}</div>{data.balance_due > 0 && <div className="text-xs text-amber-300">Kalan: {money(data.balance_due)}</div>}</div>
          </div>
          {data.extras?.length > 0 && (
            <div className="px-5 pb-4" data-testid="guest-pass-extras">
              <div className="text-[10px] uppercase text-stone-400 mb-1">Ekstralar</div>
              {data.extras.map((x, i) => <div key={i} className="flex justify-between text-sm py-0.5"><span>{x.name}</span><span className="text-stone-300">{money(x.price)} {x.paid ? "✓" : ""}</span></div>)}
            </div>
          )}
          <div className="bg-white p-5 flex flex-col items-center">
            <img src={`${API}/guest-pass/${encodeURIComponent(ref)}/qr.png?${q}`} alt="QR" className="w-44 h-44" data-testid="guest-pass-qr" />
            <div className="font-mono text-black text-lg font-black tracking-widest mt-2" data-testid="guest-pass-ref">{data.booking_ref}</div>
            <div className="text-[11px] text-stone-500">Resepsiyonda bu kodu gösterin</div>
          </div>
        </div>
        <div className="flex gap-2 mt-4">
          {walletBtn(" Apple Wallet", data.wallet?.apple_ready, `${API}/guest-pass/${encodeURIComponent(ref)}/apple.pkpass?${q}`, "guest-pass-apple")}
          {walletBtn("Google Wallet", data.wallet?.google_ready, `${API}/guest-pass/${encodeURIComponent(ref)}/google?${q}`, "guest-pass-google")}
        </div>
        <a href={`${API}/guest-pass/${encodeURIComponent(ref)}/calendar.ics?${q}`} className="block mt-2 text-center rounded-xl py-3 text-sm font-bold bg-emerald-500 text-black" data-testid="guest-pass-ics">📅 Takvime ekle (.ics)</a>
        <p className="text-center text-[11px] text-stone-500 mt-3">Bu sayfayı telefonunuzun ana ekranına ekleyerek çevrimdışı da kullanabilirsiniz.</p>
      </div>
    </div>
  );
}
