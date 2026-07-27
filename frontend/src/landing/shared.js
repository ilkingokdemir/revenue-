import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ArrowRight, CheckCircle2, ChevronDown } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export const fadeUp = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-60px" },
  transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] },
};

export const goLogin = () => { window.location.href = "/login"; };
export const scrollTo = (id) => document.querySelector(id)?.scrollIntoView({ behavior: "smooth" });

export function DemoForm({ product = "pms", dark = false }) {
  const [form, setForm] = useState({ name: "", email: "", hotel_name: "", room_count: "", message: "" });
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name || !form.email || !form.hotel_name) {
      toast.error("Please fill in your name, email and hotel name");
      return;
    }
    if (!EMAIL_RE.test(form.email)) {
      toast.error("Please enter a valid work email");
      return;
    }
    setSending(true);
    try {
      await axios.post(`${API}/public/demo-requests`, { ...form, product });
      setDone(true);
      toast.success("Thanks! Our team will reach out within one business day.");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Something went wrong — please try again");
    } finally {
      setSending(false);
    }
  };

  const card = dark
    ? "bg-[#111827] border border-white/10"
    : "bg-white border border-black/5 shadow-[0_8px_32px_rgba(29,78,216,0.08)]";
  const label = `text-xs font-bold uppercase tracking-[0.15em] ${dark ? "text-stone-400" : "text-stone-500"}`;
  const inputCls = dark
    ? "w-full rounded-lg border border-white/15 bg-white/[0.04] px-3.5 py-2.5 text-sm text-white placeholder:text-stone-500 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/50 focus:border-[#1D4ED8] transition-colors"
    : "w-full rounded-lg border border-stone-200 bg-[#FDFCFB] px-3.5 py-2.5 text-sm text-stone-900 placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/40 focus:border-[#1D4ED8] transition-colors";

  if (done) {
    return (
      <div className={`${card} rounded-2xl p-10 text-center`} data-testid="demo-form-success">
        <CheckCircle2 size={40} className="mx-auto text-emerald-500 mb-4" />
        <h3 className={`text-xl font-bold ${dark ? "text-white" : "text-stone-900"}`}>Request received</h3>
        <p className={`text-sm mt-2 ${dark ? "text-stone-400" : "text-stone-500"}`}>We'll email {form.email} to schedule your personalised demo.</p>
      </div>
    );
  }

  return (
    <form onSubmit={submit} noValidate className={`${card} rounded-2xl p-6 sm:p-8 space-y-4`} data-testid="demo-request-form">
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label className={label}>Full name *</label>
          <input value={form.name} onChange={set("name")} placeholder="Jane Smith" className={`${inputCls} mt-1.5`} data-testid="demo-form-name" />
        </div>
        <div>
          <label className={label}>Work email *</label>
          <input type="email" value={form.email} onChange={set("email")} placeholder="jane@yourhotel.com" className={`${inputCls} mt-1.5`} data-testid="demo-form-email" />
        </div>
        <div>
          <label className={label}>Hotel name *</label>
          <input value={form.hotel_name} onChange={set("hotel_name")} placeholder="The Grand Hotel" className={`${inputCls} mt-1.5`} data-testid="demo-form-hotel" />
        </div>
        <div>
          <label className={label}>Rooms</label>
          <select value={form.room_count} onChange={set("room_count")} className={`${inputCls} mt-1.5`} data-testid="demo-form-rooms">
            <option value="">Select…</option>
            <option value="1-20">1 – 20</option>
            <option value="21-50">21 – 50</option>
            <option value="51-120">51 – 120</option>
            <option value="121-300">121 – 300</option>
            <option value="300+">300+</option>
          </select>
        </div>
      </div>
      <div>
        <label className={label}>Anything specific you'd like to see?</label>
        <textarea value={form.message} onChange={set("message")} rows={3}
          placeholder={product === "rms" ? "e.g. forecasting, competitor radar, autopilot pricing…" : "e.g. front desk, channel manager, group bookings…"}
          className={`${inputCls} mt-1.5 resize-none`} data-testid="demo-form-message" />
      </div>
      <button type="submit" disabled={sending} data-testid="demo-form-submit"
        className="w-full sm:w-auto px-8 py-3 rounded-lg bg-[#1D4ED8] hover:bg-[#1E40AF] text-white text-sm font-bold transition-colors disabled:opacity-60 flex items-center justify-center gap-2">
        {sending ? "Sending…" : "Request my demo"} <ArrowRight size={15} />
      </button>
      <p className={`text-[11px] ${dark ? "text-stone-500" : "text-stone-400"}`}>No credit card required · 30-minute personalised walkthrough · Replies within one business day</p>
    </form>
  );
}

export function FaqItem({ q, a, idx, dark = false }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`border-b ${dark ? "border-white/10" : "border-stone-200"}`}>
      <button onClick={() => setOpen(!open)} data-testid={`faq-item-${idx}`}
        className="w-full flex items-center justify-between gap-4 py-5 text-left group">
        <span className={`text-base font-semibold transition-colors ${dark ? "text-white group-hover:text-blue-300" : "text-stone-900 group-hover:text-[#1D4ED8]"}`}>{q}</span>
        <ChevronDown size={18} className={`shrink-0 transition-transform duration-200 ${open ? "rotate-180" : ""} ${dark ? "text-stone-500" : "text-stone-400"}`} />
      </button>
      {open && <p className={`pb-5 text-sm leading-relaxed max-w-3xl ${dark ? "text-stone-300" : "text-stone-600"}`}>{a}</p>}
    </div>
  );
}
