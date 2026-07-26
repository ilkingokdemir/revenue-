import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Bank, ArrowsClockwise, Plus, CheckCircle, Warning, Coins } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/ar-agent`;

const STATUS_META = {
  unapplied: { label: "Bekliyor", cls: "bg-amber-50 text-amber-700" },
  needs_review: { label: "İnceleme gerekli", cls: "bg-rose-50 text-rose-700" },
  applied: { label: "Eşleşti", cls: "bg-emerald-50 text-emerald-700" },
  applied_with_credit: { label: "Eşleşti + alacak", cls: "bg-teal-50 text-teal-700" },
};
const MATCH_LABELS = {
  reference: "Fatura no (referans)", reference_batch: "Fatura no (toplu)",
  exact_amount: "Tam tutar", subset_batch: "Alt-küme (toplu)",
  partial: "Kısmi ödeme", overpayment: "Fazla ödeme", manual: "Manuel",
};

export default function ArReconPanel() {
  const [data, setData] = useState(null);
  const [running, setRunning] = useState(false);
  const [form, setForm] = useState({ payer_name: "", amount: "", reference: "" });

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/overview`);
      setData(r.data);
    } catch { toast.error("AR verileri yüklenemedi"); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function addPayment() {
    if (!form.payer_name || !form.amount) { toast.error("Ödeyen adı ve tutar gerekli"); return; }
    try {
      await axios.post(`${API}/payments`, { ...form, amount: parseFloat(form.amount) });
      toast.success("Ödeme kaydedildi");
      setForm({ payer_name: "", amount: "", reference: "" });
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Kaydedilemedi"); }
  }

  async function runMatch() {
    setRunning(true);
    try {
      const r = await axios.post(`${API}/match-run`);
      toast.success(`Eşleştirme: ${r.data.matched} eşleşti · ${r.data.needs_review} incelemede · £${r.data.credits_created} alacak`);
      load();
    } catch { toast.error("Eşleştirme çalıştırılamadı"); }
    setRunning(false);
  }

  if (!data) return <div className="p-8 text-center text-stone-400">Yükleniyor…</div>;

  return (
    <div className="p-5 max-w-[1300px] mx-auto space-y-4" data-testid="ar-recon-panel">
      <div className="bg-gradient-to-br from-stone-900 via-emerald-950 to-teal-900 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-teal-300">
              <Bank size={14} /> Accounts Receivable
            </div>
            <h1 className="text-2xl font-bold mt-1">AR Mutabakat Agent'ı</h1>
            <p className="text-sm text-stone-300 mt-1">Gelen ödemeleri açık faturalarla akıllı eşleştirir — kısmi, fazla ve toplu ödemeler dahil.</p>
          </div>
          <button onClick={runMatch} disabled={running} data-testid="ar-match-run-btn"
            className="px-4 py-2 bg-teal-500 hover:bg-teal-400 text-stone-900 rounded-lg text-sm font-bold inline-flex items-center gap-2 disabled:opacity-60">
            <ArrowsClockwise size={16} className={running ? "animate-spin" : ""} />
            {running ? "Eşleştiriliyor…" : "Şimdi Eşleştir"}
          </button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5">
          <Stat label="Açık fatura" value={data.open_invoice_count} sub={`£${data.open_balance?.toLocaleString()}`} testid="ar-stat-open" />
          <Stat label="Bekleyen ödeme" value={data.unapplied_count} testid="ar-stat-unapplied" />
          <Stat label="İnceleme gerekli" value={data.needs_review_count} warn={data.needs_review_count > 0} testid="ar-stat-review" />
          <Stat label="Açık alacak (kredi)" value={`£${data.credits_total?.toLocaleString()}`} testid="ar-stat-credits" />
        </div>
      </div>

      {/* Manual payment entry */}
      <div className="bg-white border border-stone-200 rounded-xl p-4">
        <div className="text-[11px] uppercase tracking-wider text-stone-500 mb-2 flex items-center gap-1.5"><Plus size={12} /> Gelen ödeme kaydet</div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
          <input placeholder="Ödeyen (şirket adı)" value={form.payer_name} data-testid="ar-input-payer"
            onChange={e => setForm(f => ({ ...f, payer_name: e.target.value }))}
            className="px-3 py-2 text-sm border border-stone-300 rounded-lg" />
          <input placeholder="Tutar" type="number" value={form.amount} data-testid="ar-input-amount"
            onChange={e => setForm(f => ({ ...f, amount: e.target.value }))}
            className="px-3 py-2 text-sm border border-stone-300 rounded-lg" />
          <input placeholder="Banka referansı (örn: CL-2026-00012)" value={form.reference} data-testid="ar-input-ref"
            onChange={e => setForm(f => ({ ...f, reference: e.target.value }))}
            className="px-3 py-2 text-sm border border-stone-300 rounded-lg" />
          <button onClick={addPayment} data-testid="ar-add-payment-btn"
            className="px-3 py-2 text-sm font-medium text-white bg-stone-900 rounded-lg hover:bg-stone-800">Kaydet</button>
        </div>
      </div>

      {/* Payments table */}
      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-stone-100 text-sm font-semibold text-stone-800">Gelen ödemeler</div>
        <table className="w-full text-sm">
          <thead><tr className="text-[11px] uppercase text-stone-400 border-b border-stone-100">
            <th className="text-left px-4 py-2">Ödeyen</th><th className="text-right px-2 py-2">Tutar</th>
            <th className="text-left px-2 py-2">Referans</th><th className="text-left px-2 py-2">Durum</th>
            <th className="text-left px-2 py-2">Eşleşme</th><th className="text-left px-2 py-2">Faturalar</th>
          </tr></thead>
          <tbody>
            {(data.payments || []).slice(0, 30).map(p => {
              const sm = STATUS_META[p.status] || STATUS_META.unapplied;
              return (
                <tr key={p.id} className="border-b border-stone-50" data-testid={`ar-payment-${p.id}`}>
                  <td className="px-4 py-2 font-medium text-stone-800">{p.payer_name}</td>
                  <td className="px-2 py-2 text-right font-mono">£{Number(p.amount).toFixed(2)}</td>
                  <td className="px-2 py-2 text-stone-500 text-xs">{p.reference || "—"}</td>
                  <td className="px-2 py-2"><span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${sm.cls}`}>{sm.label}</span>
                    {p.status === "needs_review" && p.review_reason && <div className="text-[10px] text-rose-500 mt-0.5">{p.review_reason}</div>}</td>
                  <td className="px-2 py-2 text-xs text-stone-600">{MATCH_LABELS[p.matched_by] || "—"}</td>
                  <td className="px-2 py-2 text-xs font-mono text-stone-500">{(p.applied_invoices || []).join(", ") || "—"}</td>
                </tr>
              );
            })}
            {(!data.payments || data.payments.length === 0) && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-stone-400 text-sm">Henüz gelen ödeme kaydı yok.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Credits */}
      {(data.credits || []).length > 0 && (
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="ar-credits-card">
          <div className="text-[11px] uppercase tracking-wider text-stone-500 mb-2 flex items-center gap-1.5"><Coins size={12} /> Açık alacaklar (fazla ödemeler)</div>
          {data.credits.map(c => (
            <div key={c.id} className="flex items-center justify-between py-1.5 border-b border-stone-50 text-sm">
              <span className="text-stone-700">{c.company_name}</span>
              <span className="font-mono font-semibold text-teal-700">£{Number(c.amount).toFixed(2)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Match log */}
      <div className="bg-white border border-stone-200 rounded-xl p-4">
        <div className="text-[11px] uppercase tracking-wider text-stone-500 mb-2">Eşleştirme geçmişi</div>
        {(data.match_log || []).slice(0, 15).map(l => (
          <div key={l.id} className="flex items-center gap-2 py-1.5 border-b border-stone-50 text-xs">
            {l.applications?.length ? <CheckCircle size={14} className="text-emerald-500 shrink-0" /> : <Warning size={14} className="text-rose-500 shrink-0" />}
            <span className="font-medium text-stone-700">{l.payer_name}</span>
            <span className="font-mono">£{Number(l.amount).toFixed(2)}</span>
            <span className="text-stone-400">→ {l.applications?.length ? `${(l.applications || []).map(a => a.invoice_number).join(", ")} (${MATCH_LABELS[l.matched_by] || l.matched_by})` : l.needs_review}</span>
            {l.credit > 0 && <span className="text-teal-600 font-semibold">+£{l.credit} alacak</span>}
            <span className="ml-auto text-stone-300">{new Date(l.created_at).toLocaleString("tr-TR")}</span>
          </div>
        ))}
        {(!data.match_log || data.match_log.length === 0) && <p className="text-sm text-stone-400 py-4 text-center">Henüz eşleştirme çalıştırılmadı.</p>}
      </div>
    </div>
  );
}

function Stat({ label, value, sub, warn, testid }) {
  return (
    <div className={`rounded-xl p-3 ${warn ? "bg-rose-500/20" : "bg-white/10"}`} data-testid={testid}>
      <div className="text-[10px] uppercase tracking-wider text-stone-300">{label}</div>
      <div className="text-xl font-bold mt-0.5">{value}</div>
      {sub && <div className="text-[11px] text-teal-300">{sub}</div>}
    </div>
  );
}
