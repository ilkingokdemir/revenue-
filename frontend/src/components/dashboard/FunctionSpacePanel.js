import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Buildings, FileText, ChartBar, Trophy } from "@phosphor-icons/react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from "recharts";

const API = process.env.REACT_APP_BACKEND_URL;
const STATUS = { sent: "bg-sky-100 text-sky-700", accepted: "bg-emerald-100 text-emerald-700", rejected: "bg-stone-200 text-stone-500" };
const STATUS_TR = { sent: "Gönderildi", accepted: "Kabul", rejected: "Red" };

export default function FunctionSpacePanel({ activePropertyId, properties = [] }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : properties[0]?.id || "default";
  const [spaces, setSpaces] = useState([]);
  const [revpam, setRevpam] = useState(null);
  const [props, setProps] = useState([]);
  const [form, setForm] = useState({ space_id: "", date: new Date().toISOString().slice(0, 10), start_hour: 9, end_hour: 17, attendees: 10, fnb_package: "lunch", av_needed: true, client_name: "", client_email: "" });
  const [quote, setQuote] = useState(null);
  const [busy, setBusy] = useState(false);
  const [cal, setCal] = useState(null);
  const [weekStart, setWeekStart] = useState("");
  const [winData, setWinData] = useState(null);
  const [rejectingId, setRejectingId] = useState(null);
  const [rejectReason, setRejectReason] = useState("fiyat");

  const load = useCallback(async () => {
    try {
      const [s, r, p, c, w] = await Promise.all([
        axios.get(`${API}/api/spaces/${pid}`, { withCredentials: true }),
        axios.get(`${API}/api/function-space/${pid}/revpam`, { withCredentials: true }),
        axios.get(`${API}/api/function-space/${pid}/proposals`, { withCredentials: true }),
        axios.get(`${API}/api/function-space/${pid}/calendar${weekStart ? `?week_start=${weekStart}` : ""}`, { withCredentials: true }),
        axios.get(`${API}/api/function-space/${pid}/win-analysis?months=6`, { withCredentials: true }),
      ]);
      const meets = (s.data.spaces || s.data || []).filter((x) => x.kind === "meeting_room");
      setSpaces(meets);
      if (meets.length && !form.space_id) setForm((f) => ({ ...f, space_id: meets[0].id }));
      setRevpam(r.data); setProps(p.data.proposals || []); setCal(c.data); setWinData(w.data);
    } catch { toast.error("Fonksiyon alanı verileri yüklenemedi"); }
  }, [pid, weekStart]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { load(); }, [load]);

  const getQuote = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/function-space/${pid}/quote`, form, { withCredentials: true });
      setQuote(r.data);
    } catch (e) { toast.error(e.response?.data?.detail || "Teklif hesaplanamadı"); } finally { setBusy(false); }
  };

  const sendProposal = async () => {
    if (!form.client_name.trim()) { toast.error("Müşteri adı gerekli"); return; }
    const sp = spaces.find((s) => s.id === form.space_id);
    if (sp && sp.capacity && form.attendees > sp.capacity) {
      toast.error(`Kapasite aşımı: ${sp.name} en fazla ${sp.capacity} kişi alır. Katılımcıyı azaltın veya daha büyük salon seçin.`);
      return;
    }
    setBusy(true);
    try {
      await axios.post(`${API}/api/function-space/${pid}/proposals`, form, { withCredentials: true });
      toast.success("Teklif oluşturuldu"); setQuote(null); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Teklif oluşturulamadı"); } finally { setBusy(false); }
  };

  const act = async (id, action) => {
    try {
      await axios.post(`${API}/api/function-space/${pid}/proposals/${id}/${action}`, {}, { withCredentials: true });
      toast.success(action === "accept" ? "Teklif kabul edildi — salon rezerve edildi" : "Teklif reddedildi");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "İşlem başarısız"); }
  };

  const confirmReject = async (id) => {
    try {
      await axios.post(`${API}/api/function-space/${pid}/proposals/${id}/reject`, { reason: rejectReason }, { withCredentials: true });
      toast.success("Teklif reddedildi — neden kaydedildi");
      setRejectingId(null); load();
    } catch (e) { toast.error(e.response?.data?.detail || "İşlem başarısız"); }
  };

  const F = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const emailProposal = async (id) => {
    try {
      const r = await axios.post(`${API}/api/function-space/${pid}/proposals/${id}/email`, {}, { withCredentials: true });
      toast.success(`E-posta kuyruğa alındı: ${r.data.queued_to} (Resend anahtarı girilene kadar MOCK)`);
    } catch (e) { toast.error(e.response?.data?.detail || "E-posta gönderilemedi"); }
  };

  const runReminders = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/function-space/${pid}/reminders/run`, {}, { withCredentials: true });
      toast.success(r.data.reminded > 0 ? `${r.data.reminded} teklif için hatırlatma kuyruğa alındı (MOCK)` : "Hatırlatma gereken teklif yok — hepsi 3 günden yeni veya zaten hatırlatıldı");
      load();
    } catch { toast.error("Hatırlatmalar çalıştırılamadı"); } finally { setBusy(false); }
  };

  const shiftWeek = (n) => {
    const base = new Date((cal?.week_start || new Date().toISOString().slice(0, 10)) + "T00:00:00");
    base.setDate(base.getDate() + n * 7);
    setWeekStart(base.toISOString().slice(0, 10));
  };

  const slotToQuote = (spaceId, date, slot) => {
    setForm((f) => ({ ...f, space_id: spaceId, date, start_hour: slot.start_hour, end_hour: Math.min(slot.start_hour + 2, slot.end_hour) }));
    setQuote(null);
    toast.info("Boş saat forma aktarıldı — Fiyat Hesapla'ya basın");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <div className="p-5 max-w-[1200px] mx-auto space-y-6" data-testid="function-space-panel">
      <div>
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Buildings size={13} weight="fill" className="text-indigo-500" /><span>Fonksiyon Alanı Motoru</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">Toplantı & Balo Salonu Teklifleri</h1>
        <p className="text-sm text-stone-500 mt-1">Teklif oluştur, kabulle otomatik rezervasyona dönüştür; RevPAM ile m² verimini izle.</p>
      </div>

      {revpam && (
        <section data-testid="fs-revpam-section">
          <div className="flex items-center gap-2 mb-2"><ChartBar size={16} className="text-indigo-600" /><h2 className="text-base font-bold text-stone-800">RevPAM — son {revpam.window_days} gün · toplam ₺{revpam.total_revpam}/m²/gün</h2></div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {revpam.spaces.map((s) => (
              <div key={s.space_id} className="bg-white border border-stone-200 rounded-xl p-3" data-testid={`fs-revpam-${s.space_id}`}>
                <div className="text-xs font-bold text-stone-700 truncate">{s.name}</div>
                <div className="text-xl font-black text-indigo-700 mt-1">₺{s.revpam}<span className="text-[10px] text-stone-400 font-normal"> /m²/gün</span></div>
                <div className="text-[11px] text-stone-500 mt-1">{s.sqm} m² · {s.bookings} rezervasyon · ₺{s.revenue.toLocaleString("tr-TR")}</div>
              </div>
            ))}
            {revpam.spaces.length === 0 && <div className="col-span-full bg-stone-50 border border-stone-200 rounded-xl p-4 text-sm text-stone-500">meeting_room türünde salon yok — Spaces panelinden ekleyin/seed edin.</div>}
          </div>
          <p className="text-[11px] text-stone-400 mt-2">{revpam.note}</p>
        </section>
      )}

      <section className="grid md:grid-cols-2 gap-4">
        <div className="bg-white border border-stone-200 rounded-xl p-4 space-y-3" data-testid="fs-quote-form">
          <h2 className="text-base font-bold text-stone-800">Hızlı Teklif</h2>
          <select value={form.space_id} onChange={(e) => { const sp = spaces.find((s) => s.id === e.target.value); setForm((f) => ({ ...f, space_id: e.target.value, attendees: sp?.capacity ? Math.min(f.attendees, sp.capacity) : f.attendees })); }} data-testid="fs-space-select" className="w-full border border-stone-300 rounded-lg px-2.5 py-2 text-sm">
            {spaces.map((s) => <option key={s.id} value={s.id}>{`${s.name} (${s.capacity} kişi)`}</option>)}
          </select>
          <div className="grid grid-cols-3 gap-2">
            <input type="date" value={form.date} onChange={(e) => F("date", e.target.value)} data-testid="fs-date" className="border border-stone-300 rounded-lg px-2 py-2 text-sm" />
            <input type="number" min={0} max={23} value={form.start_hour} onChange={(e) => F("start_hour", +e.target.value)} data-testid="fs-start" className="border border-stone-300 rounded-lg px-2 py-2 text-sm" placeholder="Başlangıç" />
            <input type="number" min={1} max={24} value={form.end_hour} onChange={(e) => F("end_hour", +e.target.value)} data-testid="fs-end" className="border border-stone-300 rounded-lg px-2 py-2 text-sm" placeholder="Bitiş" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <input type="number" min={1} value={form.attendees} onChange={(e) => F("attendees", +e.target.value)} data-testid="fs-attendees" className="border border-stone-300 rounded-lg px-2 py-2 text-sm" placeholder="Katılımcı" />
            <select value={form.fnb_package} onChange={(e) => F("fnb_package", e.target.value)} data-testid="fs-fnb" className="border border-stone-300 rounded-lg px-2 py-2 text-sm">
              <option value="none">F&B yok</option><option value="coffee">Kahve Molası (₺8/kişi)</option>
              <option value="lunch">Öğle Yemeği (₺25/kişi)</option><option value="banquet">Banket/Gala (₺55/kişi)</option>
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-stone-600">
            <input type="checkbox" checked={form.av_needed} onChange={(e) => F("av_needed", e.target.checked)} data-testid="fs-av" /> AV ekipmanı (₺75)
          </label>
          <div className="grid grid-cols-2 gap-2">
            <input value={form.client_name} onChange={(e) => F("client_name", e.target.value)} data-testid="fs-client-name" className="border border-stone-300 rounded-lg px-2 py-2 text-sm" placeholder="Müşteri adı *" />
            <input value={form.client_email} onChange={(e) => F("client_email", e.target.value)} data-testid="fs-client-email" className="border border-stone-300 rounded-lg px-2 py-2 text-sm" placeholder="E-posta" />
          </div>
          <div className="flex gap-2">
            <button onClick={getQuote} disabled={busy || !form.space_id} data-testid="fs-quote-btn" className="px-3 py-2 rounded-lg bg-stone-900 text-white text-sm font-bold disabled:opacity-50">Fiyat Hesapla</button>
            <button onClick={sendProposal} disabled={busy || !form.space_id} data-testid="fs-send-proposal-btn" className="px-3 py-2 rounded-lg bg-indigo-600 text-white text-sm font-bold disabled:opacity-50">Teklif Oluştur</button>
          </div>
        </div>

        <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4" data-testid="fs-quote-result">
          <h2 className="text-base font-bold text-indigo-900 mb-2">Teklif Özeti</h2>
          {!quote ? <p className="text-sm text-indigo-700">Formu doldurup "Fiyat Hesapla"ya basın.</p> : (
            <div className="space-y-1.5 text-sm text-indigo-900">
              <div className="flex justify-between"><span>{quote.space_name} · {quote.hours} saat (₺{quote.rate_per_hour}/sa)</span><b>₺{quote.rental}</b></div>
              <div className="flex justify-between"><span>{quote.fnb_label} × {quote.attendees} kişi</span><b>₺{quote.fnb}</b></div>
              <div className="flex justify-between"><span>AV ekipmanı</span><b>₺{quote.av}</b></div>
              <div className="flex justify-between border-t border-indigo-300 pt-1.5 text-base"><span className="font-black">TOPLAM</span><b data-testid="fs-quote-total">₺{quote.total}</b></div>
              <div className="text-[12px] mt-2">{quote.available ? "✅ Salon o aralıkta müsait" : "⛔ Salon dolu"} · {quote.capacity_ok ? "Kapasite uygun" : "⚠ Kapasite aşımı!"} · RevPAM katkısı: ₺{quote.revpam_contribution}/m²</div>
            </div>
          )}
        </div>
      </section>

      {cal && (
        <section data-testid="fs-calendar-section">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
            <h2 className="text-base font-bold text-stone-800">Salon Takvimi — {cal.week_start} haftası</h2>
            <div className="flex items-center gap-2">
              <button onClick={() => shiftWeek(-1)} data-testid="fs-cal-prev" className="px-2.5 py-1.5 border border-stone-300 rounded-lg text-sm">←</button>
              <button onClick={() => shiftWeek(1)} data-testid="fs-cal-next" className="px-2.5 py-1.5 border border-stone-300 rounded-lg text-sm">→</button>
            </div>
          </div>
          <div className="space-y-3">
            {cal.spaces.map((sp) => (
              <div key={sp.space_id} className="bg-white border border-stone-200 rounded-xl p-3" data-testid={`fs-cal-${sp.space_id}`}>
                <div className="text-xs font-bold text-stone-700 mb-2">{sp.name} <span className="text-stone-400 font-normal">({sp.open_hour}:00–{sp.close_hour}:00)</span></div>
                <div className="grid grid-cols-7 gap-1.5">
                  {sp.days.map((d) => (
                    <div key={d.date} className="rounded-lg border border-stone-100 p-1.5 min-h-[70px]">
                      <div className="text-[10px] font-bold text-stone-500 mb-1">{["Pzt","Sal","Çar","Per","Cum","Cmt","Paz"][(new Date(d.date+"T00:00:00").getDay()+6)%7]} {d.date.slice(8)}</div>
                      {d.busy.map((b, i) => (
                        <div key={`b${i}`} className="text-[10px] bg-rose-100 text-rose-700 rounded px-1 py-0.5 mb-0.5 truncate" title={b.guest}>{b.start_hour}–{b.end_hour} dolu</div>
                      ))}
                      {d.free.filter((f) => f.end_hour - f.start_hour >= 1).slice(0, 2).map((f, i) => (
                        <button key={`f${i}`} onClick={() => slotToQuote(sp.space_id, d.date, f)} data-testid={`fs-slot-${sp.space_id}-${d.date}-${f.start_hour}`}
                          className="block w-full text-left text-[10px] bg-emerald-50 hover:bg-emerald-100 text-emerald-700 rounded px-1 py-0.5 mb-0.5 font-bold">
                          {f.start_hour}–{f.end_hour} boş → teklif
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {winData && (
        <section data-testid="fs-win-section">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
            <div className="flex items-center gap-2"><Trophy size={16} className="text-amber-500" /><h2 className="text-base font-bold text-stone-800">Teklif Kazanma Analizi (6 ay)</h2></div>
            <div className="flex gap-2">
              {winData.total_win_rate_pct != null && (
                <span className={`px-2.5 py-1 rounded-full text-[11px] font-black ${winData.total_win_rate_pct >= 50 ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`} data-testid="fs-win-rate-badge">Kazanma oranı: %{winData.total_win_rate_pct}</span>
              )}
              <span className="px-2.5 py-1 rounded-full bg-stone-100 text-stone-600 text-[11px] font-black" data-testid="fs-win-value">Kazanılan ciro: ₺{winData.total_accepted_value.toLocaleString("tr-TR")}</span>
            </div>
          </div>
          <div className="grid md:grid-cols-3 gap-3">
            <div className="md:col-span-2 bg-white border border-stone-200 rounded-xl p-3" data-testid="fs-win-chart">
              {winData.months.length === 0 ? <p className="text-sm text-stone-500 p-3">Henüz teklif verisi yok.</p> : (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={winData.months} margin={{ top: 5, right: 10, left: -15, bottom: 0 }}>
                    <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="accepted" name="Kabul" fill="#059669" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="rejected" name="Red" fill="#e11d48" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="pending" name="Bekleyen" fill="#a8a29e" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
            <div className="bg-white border border-stone-200 rounded-xl p-3" data-testid="fs-loss-reasons">
              <div className="text-xs font-bold text-stone-500 mb-2">KAYBEDİLME NEDENLERİ</div>
              {winData.reasons.length === 0 ? <p className="text-[12px] text-stone-400">Henüz red nedeni kaydedilmedi — Red butonunda neden seçin.</p> : (
                <div className="space-y-1.5">
                  {winData.reasons.map((r) => (
                    <div key={r.reason} className="flex items-center justify-between text-sm" data-testid={`fs-reason-${r.reason}`}>
                      <span className="capitalize text-stone-700">{r.reason}</span>
                      <span className="px-2 py-0.5 rounded-full bg-rose-100 text-rose-700 text-[11px] font-black">{r.count}</span>
                    </div>
                  ))}
                </div>
              )}
              <p className="text-[10px] text-stone-400 mt-2">{winData.note}</p>
            </div>
          </div>
        </section>
      )}

      <section data-testid="fs-proposals-section">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
          <div className="flex items-center gap-2"><FileText size={16} className="text-stone-600" /><h2 className="text-base font-bold text-stone-800">Teklifler ({props.length})</h2></div>
          <button onClick={runReminders} disabled={busy} data-testid="fs-run-reminders-btn" className="px-3 py-1.5 rounded-lg border border-amber-300 bg-amber-50 text-amber-700 text-[12px] font-bold disabled:opacity-50">⏰ Hatırlatmaları Çalıştır (3+ gün yanıtsız)</button>
        </div>
        {props.length === 0 ? <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 text-sm text-stone-500" data-testid="fs-proposals-empty">Henüz teklif yok.</div> : (
          <div className="bg-white border border-stone-200 rounded-xl overflow-x-auto">
            <table className="w-full text-sm" data-testid="fs-proposals-table">
              <thead><tr className="text-left text-[11px] text-stone-400 border-b border-stone-100">
                <th className="p-2.5">Müşteri</th><th className="p-2.5">Salon</th><th className="p-2.5">Tarih</th><th className="p-2.5">Kişi</th><th className="p-2.5">Toplam</th><th className="p-2.5">Durum</th><th className="p-2.5">Aksiyon</th>
              </tr></thead>
              <tbody>
                {props.map((p) => (
                  <tr key={p.id} className="border-t border-stone-100" data-testid={`fs-proposal-${p.id}`}>
                    <td className="p-2.5 font-bold">{p.client_name}</td>
                    <td className="p-2.5">{p.space_name}</td>
                    <td className="p-2.5 text-[12px]">{p.date} {String(p.start).slice(11, 16)}–{String(p.end).slice(11, 16)}</td>
                    <td className="p-2.5">{p.attendees}</td>
                    <td className="p-2.5 font-black">₺{p.total}</td>
                    <td className="p-2.5"><span className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${STATUS[p.status] || ""}`}>{STATUS_TR[p.status] || p.status}</span>
                      {p.reminder_sent_at && <span className="ml-1 px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[10px] font-bold" data-testid={`fs-reminded-${p.id}`}>⏰ Hatırlatıldı</span>}
                    </td>
                    <td className="p-2.5">
                      <div className="flex gap-1.5 flex-wrap items-center">
                        {p.status === "sent" && rejectingId !== p.id && (
                          <>
                            <button onClick={() => act(p.id, "accept")} data-testid={`fs-accept-${p.id}`} className="px-2 py-1 rounded-md bg-emerald-600 text-white text-[11px] font-bold">Kabul + Rezerve</button>
                            <button onClick={() => { setRejectingId(p.id); setRejectReason("fiyat"); }} data-testid={`fs-reject-${p.id}`} className="px-2 py-1 rounded-md bg-stone-200 text-stone-600 text-[11px] font-bold">Red</button>
                          </>
                        )}
                        {p.status === "sent" && rejectingId === p.id && (
                          <>
                            <select value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} data-testid={`fs-reject-reason-${p.id}`} className="border border-stone-300 rounded-md px-1.5 py-1 text-[11px]">
                              <option value="fiyat">Fiyat yüksek</option>
                              <option value="tarih">Tarih uymadı</option>
                              <option value="mekan">Mekan beğenilmedi</option>
                              <option value="rakip">Rakibe gitti</option>
                              <option value="iptal">Etkinlik iptal</option>
                              <option value="diğer">Diğer</option>
                            </select>
                            <button onClick={() => confirmReject(p.id)} data-testid={`fs-reject-confirm-${p.id}`} className="px-2 py-1 rounded-md bg-rose-600 text-white text-[11px] font-bold">Onayla</button>
                            <button onClick={() => setRejectingId(null)} className="px-2 py-1 rounded-md bg-stone-100 text-stone-500 text-[11px] font-bold">Vazgeç</button>
                          </>
                        )}
                        <a href={`${API}/api/function-space/${pid}/proposals/${p.id}/pdf`} target="_blank" rel="noreferrer" data-testid={`fs-pdf-${p.id}`} className="px-2 py-1 rounded-md bg-indigo-100 text-indigo-700 text-[11px] font-bold">PDF</a>
                        {p.client_email && <button onClick={() => emailProposal(p.id)} data-testid={`fs-email-${p.id}`} className="px-2 py-1 rounded-md bg-sky-100 text-sky-700 text-[11px] font-bold">{p.emailed_at ? "Tekrar Gönder" : "E-posta"}</button>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
