import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  CurrencyGbp, ArrowsClockwise, CheckCircle, WarningCircle, Clock,
} from "@phosphor-icons/react";
import { CreditCard, BarChart3, Settings, TrendingUp, Shield, Smartphone, Plus } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function PaymentsPanel({ properties, activePropertyId: propActivePropertyId }) {
  const [tab, setTab] = useState("dashboard");
  const [dashboard, setDashboard] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [settings, setSettings] = useState(null);
  const [terminalSettings, setTerminalSettings] = useState(null);
  const [devices, setDevices] = useState([]);
  const [terminalPayments, setTerminalPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState("30d");
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterType, setFilterType] = useState("all");
  const [savingSettings, setSavingSettings] = useState(false);

  const propertyId = (propActivePropertyId && propActivePropertyId !== "all") ? propActivePropertyId : (properties?.[0]?.id || "aldgate-flats");

  const fetchDashboard = useCallback(async () => {
    const { data } = await axios.get(`${API}/payments/dashboard/${propertyId}?period=${period}`);
    setDashboard(data);
  }, [propertyId, period]);

  const fetchTransactions = useCallback(async () => {
    let url = `${API}/payments/transactions/${propertyId}`;
    const params = [];
    if (filterStatus && filterStatus !== "all") params.push(`status=${filterStatus}`);
    if (filterType && filterType !== "all") params.push(`type=${filterType}`);
    if (params.length) url += `?${params.join("&")}`;
    const { data } = await axios.get(url);
    setTransactions(data);
  }, [propertyId, filterStatus, filterType]);

  const fetchSettings = useCallback(async () => {
    const { data } = await axios.get(`${API}/payments/settings/${propertyId}`);
    setSettings(data);
  }, [propertyId]);

  const fetchTerminal = useCallback(async () => {
    const [ts, dv, tp] = await Promise.all([
      axios.get(`${API}/terminal/settings/${propertyId}`),
      axios.get(`${API}/terminal/devices/${propertyId}`),
      axios.get(`${API}/terminal/payments/${propertyId}`),
    ]);
    setTerminalSettings(ts.data);
    setDevices(dv.data);
    setTerminalPayments(tp.data);
  }, [propertyId]);

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchDashboard(), fetchTransactions(), fetchSettings(), fetchTerminal()])
      .then(() => setLoading(false));
  }, [fetchDashboard, fetchTransactions, fetchSettings, fetchTerminal]);

  const saveSettings = async () => {
    setSavingSettings(true);
    try {
      await axios.put(`${API}/payments/settings/${propertyId}`, settings);
      toast.success("Payment settings saved");
    } catch (e) { toast.error("Failed to save"); }
    finally { setSavingSettings(false); }
  };

  const upd = (k, v) => setSettings(p => ({ ...p, [k]: v }));

  const tabs = [
    { id: "dashboard", label: "Overview", icon: BarChart3 },
    { id: "terminal", label: "Card Terminals", icon: Smartphone },
    { id: "transactions", label: "Transactions", icon: CreditCard },
    { id: "settings", label: "Settings", icon: Settings },
  ];

  if (loading) return <div className="flex justify-center py-24"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div>;

  return (
    <div className="h-[calc(100vh-0px)] flex flex-col" data-testid="payments-panel">
      <div className="border-b border-stone-200 bg-white px-6 py-4 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-green-100 flex items-center justify-center">
            <CreditCard size={18} className="text-green-700" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-stone-900">Payment Gateway</h2>
            <p className="text-xs text-stone-400">Stripe-powered payments for bookings & POS</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Select value={period} onValueChange={setPeriod}>
            <SelectTrigger className="h-8 text-xs w-28"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="7d">7 days</SelectItem>
              <SelectItem value="30d">30 days</SelectItem>
              <SelectItem value="90d">90 days</SelectItem>
            </SelectContent>
          </Select>
          <div className="flex items-center gap-1.5 text-[10px] bg-emerald-50 text-emerald-700 px-2.5 py-1.5 rounded-lg font-medium">
            <Shield size={12} /> Stripe Connected
          </div>
        </div>
      </div>

      <div className="border-b border-stone-200 bg-white px-6 flex gap-1 flex-shrink-0">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium border-b-2 ${tab === t.id ? "border-green-500 text-green-700" : "border-transparent text-stone-400 hover:text-stone-600"}`} data-testid={`pay-tab-${t.id}`}>
            <t.icon size={14} /> {t.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto bg-stone-50">
        {/* Dashboard */}
        {tab === "dashboard" && dashboard && (
          <div className="p-6 max-w-5xl mx-auto space-y-5" data-testid="payments-dashboard">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center">
                <div className="text-2xl font-bold text-emerald-700">£{dashboard.total_processed?.toLocaleString()}</div>
                <div className="text-[10px] text-emerald-600">Processed</div>
              </div>
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-center">
                <div className="text-2xl font-bold text-amber-700">£{dashboard.total_pending?.toLocaleString()}</div>
                <div className="text-[10px] text-amber-600">Pending</div>
              </div>
              <div className="bg-white border border-stone-200 rounded-xl p-4 text-center">
                <div className="text-2xl font-bold text-stone-800">{dashboard.total_transactions}</div>
                <div className="text-[10px] text-stone-500">Transactions</div>
              </div>
              <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center">
                <div className="text-2xl font-bold text-blue-700">{dashboard.success_rate}%</div>
                <div className="text-[10px] text-blue-600">Success Rate</div>
              </div>
            </div>

            {Object.keys(dashboard.by_type || {}).length > 0 && (
              <div className="bg-white rounded-xl border border-stone-200 p-4">
                <div className="text-sm font-semibold text-stone-800 mb-3">Revenue by Type</div>
                {Object.entries(dashboard.by_type).map(([type, data]) => (
                  <div key={type} className="flex items-center justify-between text-xs py-2 border-b border-stone-50">
                    <span className="text-stone-600 capitalize">{type}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-stone-400">{data.count} transactions</span>
                      <span className="font-bold text-stone-800">£{data.amount?.toLocaleString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {dashboard.daily_trend?.length > 0 && (
              <div className="bg-white rounded-xl border border-stone-200 p-4">
                <div className="text-sm font-semibold text-stone-800 mb-3">Daily Payment Volume</div>
                <div className="flex items-end gap-1 h-32">
                  {dashboard.daily_trend.slice(-14).map((d, i) => {
                    const max = Math.max(...dashboard.daily_trend.slice(-14).map(t => t.amount || 1), 1);
                    const h = ((d.amount || 0) / max) * 100;
                    return (
                      <div key={i} className="flex-1 flex flex-col items-center gap-1">
                        <span className="text-[8px] text-stone-400">£{d.amount}</span>
                        <div className="w-full bg-emerald-400 rounded-t-md" style={{ height: `${Math.max(h, 3)}%` }} />
                        <span className="text-[7px] text-stone-400">{d.date?.slice(5)}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {dashboard.total_transactions === 0 && (
              <div className="bg-white rounded-xl border border-stone-200 p-10 text-center">
                <CreditCard size={32} className="mx-auto text-stone-300 mb-3" />
                <p className="text-sm text-stone-500">No payment transactions yet</p>
                <p className="text-xs text-stone-400 mt-1">Payments will appear here when guests pay via Stripe</p>
              </div>
            )}
          </div>
        )}

        {/* Transactions */}
        {tab === "transactions" && (
          <div className="p-6 max-w-5xl mx-auto space-y-3" data-testid="payments-transactions">
            <div className="flex gap-2">
              <Select value={filterStatus} onValueChange={v => { setFilterStatus(v); }}>
                <SelectTrigger className="h-8 text-xs w-32"><SelectValue placeholder="All Status" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="paid">Paid</SelectItem>
                  <SelectItem value="initiated">Initiated</SelectItem>
                  <SelectItem value="expired">Expired</SelectItem>
                </SelectContent>
              </Select>
              <Select value={filterType} onValueChange={v => { setFilterType(v); }}>
                <SelectTrigger className="h-8 text-xs w-32"><SelectValue placeholder="All Types" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="booking">Booking</SelectItem>
                  <SelectItem value="pos">POS</SelectItem>
                </SelectContent>
              </Select>
              <button onClick={fetchTransactions} className="text-xs px-3 py-1.5 bg-stone-100 text-stone-600 rounded-lg"><ArrowsClockwise size={12} /></button>
            </div>
            {transactions.length === 0 ? (
              <div className="text-center py-12 text-stone-400 text-sm">No transactions found</div>
            ) : (
              transactions.map(t => (
                <div key={t.id} className="bg-white border border-stone-200 rounded-xl p-3 flex items-center justify-between" data-testid={`tx-${t.id}`}>
                  <div className="flex items-center gap-3">
                    <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${t.payment_status === "paid" ? "bg-emerald-50" : t.payment_status === "initiated" ? "bg-amber-50" : "bg-red-50"}`}>
                      {t.payment_status === "paid" ? <CheckCircle size={16} className="text-emerald-500" weight="fill" /> :
                       t.payment_status === "initiated" ? <Clock size={16} className="text-amber-500" /> :
                       <WarningCircle size={16} className="text-red-500" />}
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-stone-800">{t.reference_number || t.type}</div>
                      <div className="text-[10px] text-stone-400">
                        {t.type} · {t.guest_name || "Guest"} · {t.payment_method}
                        {t.paid_at && ` · ${t.paid_at.slice(0, 16).replace("T", " ")}`}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-stone-800">£{t.amount}</span>
                    <Badge className={`text-[9px] ${t.payment_status === "paid" ? "bg-emerald-100 text-emerald-700" : t.payment_status === "initiated" ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700"}`}>{t.payment_status}</Badge>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Terminal */}
        {tab === "terminal" && (
          <div className="p-6 max-w-5xl mx-auto space-y-5" data-testid="terminal-tab">
            {/* How It Works */}
            <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-green-800 mb-2">How Card Terminal Payments Work</h3>
              <div className="grid grid-cols-4 gap-3 text-center text-xs text-green-700">
                <div className="bg-white rounded-lg p-3"><div className="text-lg mb-1">1</div><span>Staff selects "Pay by Terminal" on POS order</span></div>
                <div className="bg-white rounded-lg p-3"><div className="text-lg mb-1">2</div><span>Amount auto-sent to card reader device</span></div>
                <div className="bg-white rounded-lg p-3"><div className="text-lg mb-1">3</div><span>Guest inserts / taps card on terminal</span></div>
                <div className="bg-white rounded-lg p-3"><div className="text-lg mb-1">4</div><span>Payment confirmed, order marked paid</span></div>
              </div>
            </div>

            {/* Active Provider */}
            {terminalSettings && (
              <div className="bg-white rounded-xl border border-stone-200 p-5">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-stone-800">Terminal Provider</h3>
                  <Badge className="text-[9px] bg-green-100 text-green-700 capitalize">{terminalSettings.active_provider}</Badge>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { id: "stripe", name: "Stripe Terminal", desc: "Global — Visa, MC, Amex, Contactless", flag: "🌍" },
                    { id: "iyzico", name: "iyzico", desc: "Turkey — All Turkish banks, Installments", flag: "🇹🇷" },
                    { id: "paytr", name: "PayTR", desc: "Turkey — Virtual POS, SMS payment", flag: "🇹🇷" },
                  ].map(p => (
                    <button key={p.id} onClick={async () => {
                      await axios.put(`${API}/terminal/settings/${propertyId}`, { active_provider: p.id });
                      fetchTerminal();
                      toast.success(`Switched to ${p.name}`);
                    }} className={`text-left p-3 rounded-xl border-2 transition-all ${terminalSettings.active_provider === p.id ? "border-green-500 bg-green-50" : "border-stone-200 hover:border-stone-300"}`}
                      data-testid={`provider-${p.id}`}>
                      <div className="text-sm mb-0.5">{p.flag} <span className="font-semibold text-stone-800">{p.name}</span></div>
                      <div className="text-[10px] text-stone-500">{p.desc}</div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Registered Devices */}
            <div className="bg-white rounded-xl border border-stone-200 p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-stone-800">Card Readers ({devices.length})</h3>
                <button onClick={async () => {
                  const name = prompt("Device name (e.g., Reception Reader):");
                  const readerId = prompt("Stripe Reader ID (e.g., tmr_xxx) or Device Serial:");
                  if (name && readerId) {
                    await axios.post(`${API}/terminal/devices`, {
                      property_id: propertyId, name, provider_device_id: readerId, provider: terminalSettings?.active_provider || "stripe"
                    });
                    fetchTerminal();
                    toast.success("Device registered");
                  }
                }} className="text-xs px-3 py-1.5 bg-green-600 text-white rounded-lg font-medium" data-testid="add-device-btn">
                  <Plus size={12} className="inline mr-1" /> Add Reader
                </button>
              </div>
              {devices.length === 0 ? (
                <div className="text-center py-8 text-stone-400 text-sm">
                  <Smartphone size={24} className="mx-auto mb-2 text-stone-300" />
                  <p>No card readers registered</p>
                  <p className="text-[10px] mt-1">Add your Stripe Terminal reader or iyzico device to start accepting card payments</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {devices.map(d => (
                    <div key={d.id} className="flex items-center justify-between bg-stone-50 rounded-lg px-3 py-2.5" data-testid={`device-${d.id}`}>
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-lg bg-green-100 flex items-center justify-center"><Smartphone size={16} className="text-green-700" /></div>
                        <div>
                          <div className="text-xs font-semibold text-stone-800">{d.name}</div>
                          <div className="text-[10px] text-stone-400">{d.provider} · {d.provider_device_id?.slice(0, 20)} {d.location && `· ${d.location}`}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge className={`text-[9px] ${d.status === "active" ? "bg-green-100 text-green-700" : "bg-stone-100 text-stone-500"}`}>{d.status}</Badge>
                        {d.last_used && <span className="text-[9px] text-stone-400">Last: {d.last_used?.slice(0, 10)}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Terminal Credentials */}
            {terminalSettings && (
              <div className="bg-white rounded-xl border border-stone-200 p-5">
                <h3 className="text-sm font-semibold text-stone-800 mb-3">API Credentials</h3>
                {terminalSettings.active_provider === "stripe" && (
                  <div className="space-y-2">
                    <div><label className="text-[11px] font-medium text-stone-600 block mb-1">Stripe Location ID</label>
                      <Input value={terminalSettings.stripe_location_id || ""} onChange={e => setTerminalSettings(p => ({...p, stripe_location_id: e.target.value}))} placeholder="tml_xxx" className="h-8 text-sm" data-testid="stripe-location-id" /></div>
                    <p className="text-[10px] text-stone-400">Stripe API Key is already configured in your environment.</p>
                  </div>
                )}
                {terminalSettings.active_provider === "iyzico" && (
                  <div className="space-y-2">
                    <div><label className="text-[11px] font-medium text-stone-600 block mb-1">iyzico API Key</label>
                      <Input value={terminalSettings.iyzico_api_key || ""} onChange={e => setTerminalSettings(p => ({...p, iyzico_api_key: e.target.value}))} placeholder="Enter API Key" className="h-8 text-sm" /></div>
                    <div><label className="text-[11px] font-medium text-stone-600 block mb-1">iyzico Secret Key</label>
                      <Input type="password" value={terminalSettings.iyzico_secret_key || ""} onChange={e => setTerminalSettings(p => ({...p, iyzico_secret_key: e.target.value}))} placeholder="Enter Secret Key" className="h-8 text-sm" /></div>
                  </div>
                )}
                {terminalSettings.active_provider === "paytr" && (
                  <div className="space-y-2">
                    <div><label className="text-[11px] font-medium text-stone-600 block mb-1">PayTR Merchant ID</label>
                      <Input value={terminalSettings.paytr_merchant_id || ""} onChange={e => setTerminalSettings(p => ({...p, paytr_merchant_id: e.target.value}))} className="h-8 text-sm" /></div>
                    <div><label className="text-[11px] font-medium text-stone-600 block mb-1">PayTR Merchant Key</label>
                      <Input type="password" value={terminalSettings.paytr_merchant_key || ""} onChange={e => setTerminalSettings(p => ({...p, paytr_merchant_key: e.target.value}))} className="h-8 text-sm" /></div>
                  </div>
                )}
                <button onClick={async () => {
                  await axios.put(`${API}/terminal/settings/${propertyId}`, terminalSettings);
                  toast.success("Terminal settings saved");
                }} className="w-full mt-3 bg-green-600 text-white py-2 rounded-lg text-xs font-medium hover:bg-green-700" data-testid="save-terminal-settings">Save Terminal Settings</button>
              </div>
            )}

            {/* Recent Terminal Payments */}
            {terminalPayments.length > 0 && (
              <div className="bg-white rounded-xl border border-stone-200 p-5">
                <h3 className="text-sm font-semibold text-stone-800 mb-3">Recent Terminal Payments</h3>
                <div className="space-y-1.5">
                  {terminalPayments.slice(0, 10).map(p => (
                    <div key={p.id} className="flex items-center justify-between text-xs bg-stone-50 rounded-lg px-3 py-2">
                      <div>
                        <span className="font-medium text-stone-700">{p.type} · {p.reference_id?.slice(0, 8)}</span>
                        <span className="text-stone-400 ml-2">{p.provider}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-stone-800">£{p.amount}</span>
                        <Badge className={`text-[9px] ${p.payment_status === "paid" ? "bg-green-100 text-green-700" : p.status === "sent_to_reader" ? "bg-blue-100 text-blue-700" : "bg-amber-100 text-amber-700"}`}>{p.payment_status || p.status}</Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Settings */}
        {tab === "settings" && settings && (
          <div className="p-6 max-w-3xl mx-auto" data-testid="payments-settings">
            <div className="bg-white rounded-xl border border-stone-200 p-5 space-y-4">
              <div className="flex items-center gap-2 mb-2">
                <Shield size={16} className="text-green-600" />
                <span className="text-sm font-semibold text-stone-800">Payment Methods</span>
              </div>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div><span className="text-xs text-stone-700 font-medium">Stripe Online Payments</span><p className="text-[10px] text-stone-400">Card payments via Stripe Checkout</p></div>
                  <Switch checked={settings.stripe_enabled} onCheckedChange={v => upd("stripe_enabled", v)} data-testid="stripe-toggle" />
                </div>
                <div className="flex items-center justify-between">
                  <div><span className="text-xs text-stone-700 font-medium">Pay at Hotel</span><p className="text-[10px] text-stone-400">Guests pay on arrival</p></div>
                  <Switch checked={settings.pay_at_hotel_enabled} onCheckedChange={v => upd("pay_at_hotel_enabled", v)} />
                </div>
                <div className="flex items-center justify-between">
                  <div><span className="text-xs text-stone-700 font-medium">Room Charging</span><p className="text-[10px] text-stone-400">Charge POS orders to guest room folio</p></div>
                  <Switch checked={settings.room_charge_enabled} onCheckedChange={v => upd("room_charge_enabled", v)} />
                </div>
                <div className="flex items-center justify-between">
                  <div><span className="text-xs text-stone-700 font-medium">Cash Payments</span><p className="text-[10px] text-stone-400">Accept cash at POS</p></div>
                  <Switch checked={settings.cash_enabled} onCheckedChange={v => upd("cash_enabled", v)} />
                </div>
                <div className="flex items-center justify-between">
                  <div><span className="text-xs text-stone-700 font-medium">Contactless</span><p className="text-[10px] text-stone-400">Apple Pay, Google Pay</p></div>
                  <Switch checked={settings.contactless_enabled} onCheckedChange={v => upd("contactless_enabled", v)} />
                </div>
              </div>
              <div className="border-t border-stone-100 pt-4">
                <span className="text-xs font-semibold text-stone-700">Tipping</span>
                <div className="flex items-center justify-between mt-2">
                  <span className="text-xs text-stone-600">Enable tipping on POS</span>
                  <Switch checked={settings.tipping_enabled} onCheckedChange={v => upd("tipping_enabled", v)} />
                </div>
              </div>
              <div className="border-t border-stone-100 pt-4">
                <span className="text-xs font-semibold text-stone-700">Currency</span>
                <Select value={settings.default_currency} onValueChange={v => upd("default_currency", v)}>
                  <SelectTrigger className="h-8 text-xs mt-1 w-32"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {["GBP", "USD", "EUR", "AED", "CHF", "AUD", "CAD", "JPY", "SGD"].map(c => (
                      <SelectItem key={c} value={c}>{c}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <button onClick={saveSettings} disabled={savingSettings}
                className="w-full bg-green-600 text-white py-2.5 rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50 mt-2"
                data-testid="save-payment-settings">
                {savingSettings ? "Saving..." : "Save Payment Settings"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
