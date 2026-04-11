import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  WhatsappLogo, TelegramLogo, Envelope, DeviceMobile, Gear,
  CheckCircle, ArrowsClockwise, Eye, EyeSlash, Info,
  PaperPlaneTilt, Robot,
} from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function SettingsCard({ icon: Icon, iconColor, title, description, enabled, onToggle, children, testId }) {
  return (
    <div className={`bg-white border border-stone-200 rounded-xl overflow-hidden transition-opacity ${!enabled ? "opacity-60" : ""}`} data-testid={testId}>
      <div className="px-5 py-4 flex items-center justify-between border-b border-stone-100">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: `${iconColor}15` }}>
            <Icon size={18} style={{ color: iconColor }} weight="fill" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-stone-900">{title}</h3>
            <p className="text-[11px] text-stone-400">{description}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${enabled ? "bg-emerald-50 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>
            {enabled ? "Active" : "Inactive"}
          </span>
          <Switch checked={enabled} onCheckedChange={onToggle} data-testid={`${testId}-toggle`} />
        </div>
      </div>
      {enabled && <div className="px-5 py-4 space-y-4">{children}</div>}
    </div>
  );
}

function SecretInput({ value, onChange, placeholder, testId }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <Input type={visible ? "text" : "password"} value={value} onChange={onChange} placeholder={placeholder}
        className="pr-10 h-9 text-sm font-mono" data-testid={testId} />
      <button onClick={() => setVisible(!visible)} className="absolute right-3 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-600">
        {visible ? <EyeSlash size={14} /> : <Eye size={14} />}
      </button>
    </div>
  );
}

export function ChannelSettingsPanel({ properties, activePropertyId: propActivePropertyId }) {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState("");
  const propertyId = (propActivePropertyId && propActivePropertyId !== "all") ? propActivePropertyId : (properties?.[0]?.id || "aldgate-flats");

  const fetchSettings = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/messaging/channel-settings/${propertyId}`);
      setSettings(data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [propertyId]);

  useEffect(() => { fetchSettings(); }, [fetchSettings]);

  const save = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/messaging/channel-settings/${propertyId}`, settings);
      toast.success("Channel settings saved");
    } catch (e) { toast.error("Failed to save"); }
    finally { setSaving(false); }
  };

  const testChannel = async (channel) => {
    setTesting(channel);
    try {
      if (channel === "whatsapp") {
        const { data } = await axios.post(`${API}/messaging/send/whatsapp`, {
          property_id: propertyId, phone: "+0000000000", message: "Test message from MyHotelBox"
        });
        if (data.sent) toast.success("WhatsApp test sent!");
        else toast(data.message, { description: data.status });
      } else if (channel === "telegram") {
        const { data } = await axios.post(`${API}/messaging/send/telegram`, {
          property_id: propertyId, chat_id: "test", message: "Test message from MyHotelBox"
        });
        if (data.sent) toast.success("Telegram test sent!");
        else toast(data.message, { description: data.status });
      } else if (channel === "email") {
        const { data } = await axios.post(`${API}/messaging/send/email`, {
          email: "test@example.com", subject: "MyHotelBox Test", message: "This is a test email from MyHotelBox."
        });
        if (data.sent) toast.success("Email test sent!");
        else toast(data.message, { description: data.status });
      }
    } catch (e) { toast.error(`${channel} test failed`); }
    finally { setTesting(""); }
  };

  const updateField = (field, value) => setSettings(prev => ({ ...prev, [field]: value }));

  if (loading || !settings) {
    return (
      <div className="p-5 flex justify-center py-20">
        <ArrowsClockwise size={24} className="animate-spin text-stone-400" />
      </div>
    );
  }

  return (
    <div className="p-5 max-w-3xl" data-testid="channel-settings-panel">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-stone-900 flex items-center gap-2">
            <Gear size={20} weight="fill" className="text-stone-500" /> Channel Settings
          </h2>
          <p className="text-sm text-stone-500">Configure messaging channels to send real messages to guests</p>
        </div>
        <button onClick={save} disabled={saving}
          className="text-xs bg-emerald-600 text-white px-4 py-2 rounded-lg hover:bg-emerald-700 flex items-center gap-1.5 font-medium transition-colors disabled:opacity-50"
          data-testid="save-settings-btn">
          <CheckCircle size={13} weight="fill" /> {saving ? "Saving..." : "Save Settings"}
        </button>
      </div>

      <div className="space-y-5">
        {/* WhatsApp — Meta Cloud API */}
        <SettingsCard icon={WhatsappLogo} iconColor="#25D366" title="WhatsApp Business" description="Send messages via Meta WhatsApp Cloud API"
          enabled={settings.whatsapp_enabled} onToggle={v => updateField("whatsapp_enabled", v)} testId="whatsapp-settings">
          <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-xs text-green-800">
            <p className="font-medium mb-1 flex items-center gap-1"><Info size={12} /> Setup Guide</p>
            <ol className="list-decimal ml-4 space-y-0.5">
              <li>Go to <a href="https://business.facebook.com" target="_blank" rel="noreferrer" className="underline font-medium">Meta Business Suite</a></li>
              <li>Create a WhatsApp Business App in <a href="https://developers.facebook.com" target="_blank" rel="noreferrer" className="underline font-medium">Meta Developers</a></li>
              <li>Get your Phone Number ID and Access Token from the API Setup page</li>
              <li>Paste them below and click Save</li>
            </ol>
          </div>
          <div>
            <label className="text-[11px] font-medium text-stone-600 mb-1 block">Phone Number ID</label>
            <Input value={settings.whatsapp_phone_number_id} onChange={e => updateField("whatsapp_phone_number_id", e.target.value)}
              placeholder="e.g. 123456789012345" className="h-9 text-sm font-mono" data-testid="wa-phone-id" />
          </div>
          <div>
            <label className="text-[11px] font-medium text-stone-600 mb-1 block">Access Token</label>
            <SecretInput value={settings.whatsapp_access_token} onChange={e => updateField("whatsapp_access_token", e.target.value)}
              placeholder="EAAxxxxxxx..." testId="wa-access-token" />
          </div>
          <div>
            <label className="text-[11px] font-medium text-stone-600 mb-1 block">Business Account ID (optional)</label>
            <Input value={settings.whatsapp_business_id} onChange={e => updateField("whatsapp_business_id", e.target.value)}
              placeholder="e.g. 987654321012345" className="h-9 text-sm font-mono" data-testid="wa-business-id" />
          </div>
          <button onClick={() => testChannel("whatsapp")} disabled={testing === "whatsapp"}
            className="text-xs bg-green-600 text-white px-3 py-1.5 rounded-lg hover:bg-green-700 flex items-center gap-1.5 font-medium transition-colors disabled:opacity-50"
            data-testid="test-whatsapp-btn">
            <PaperPlaneTilt size={12} weight="fill" /> {testing === "whatsapp" ? "Testing..." : "Test Connection"}
          </button>
        </SettingsCard>

        {/* Telegram — Bot API */}
        <SettingsCard icon={TelegramLogo} iconColor="#0088cc" title="Telegram Bot" description="Send messages via Telegram Bot API"
          enabled={settings.telegram_enabled} onToggle={v => updateField("telegram_enabled", v)} testId="telegram-settings">
          <div className="bg-sky-50 border border-sky-200 rounded-lg px-4 py-3 text-xs text-sky-800">
            <p className="font-medium mb-1 flex items-center gap-1"><Info size={12} /> Setup Guide</p>
            <ol className="list-decimal ml-4 space-y-0.5">
              <li>Open Telegram and message <code className="bg-sky-100 px-1 rounded">@BotFather</code></li>
              <li>Send <code className="bg-sky-100 px-1 rounded">/newbot</code> and follow the prompts</li>
              <li>Copy the Bot Token provided</li>
              <li>Paste it below and click Save</li>
            </ol>
          </div>
          <div>
            <label className="text-[11px] font-medium text-stone-600 mb-1 block">Bot Token</label>
            <SecretInput value={settings.telegram_bot_token} onChange={e => updateField("telegram_bot_token", e.target.value)}
              placeholder="e.g. 123456:ABC-DEF1234ghIkl-zyx57W2v..." testId="tg-bot-token" />
          </div>
          <div>
            <label className="text-[11px] font-medium text-stone-600 mb-1 block">Bot Username</label>
            <Input value={settings.telegram_bot_username} onChange={e => updateField("telegram_bot_username", e.target.value)}
              placeholder="e.g. @MyHotelBot" className="h-9 text-sm" data-testid="tg-bot-username" />
          </div>
          <button onClick={() => testChannel("telegram")} disabled={testing === "telegram"}
            className="text-xs bg-sky-600 text-white px-3 py-1.5 rounded-lg hover:bg-sky-700 flex items-center gap-1.5 font-medium transition-colors disabled:opacity-50"
            data-testid="test-telegram-btn">
            <PaperPlaneTilt size={12} weight="fill" /> {testing === "telegram" ? "Testing..." : "Test Connection"}
          </button>
        </SettingsCard>

        {/* SMS */}
        <SettingsCard icon={DeviceMobile} iconColor="#8b5cf6" title="SMS" description="Send text messages to guests"
          enabled={settings.sms_enabled} onToggle={v => updateField("sms_enabled", v)} testId="sms-settings">
          <div className="bg-purple-50 border border-purple-200 rounded-lg px-4 py-3 text-xs text-purple-800">
            <p className="font-medium flex items-center gap-1"><Info size={12} /> SMS requires a provider (Twilio, Vonage, etc). Contact support to set up.</p>
          </div>
          <div>
            <label className="text-[11px] font-medium text-stone-600 mb-1 block">Provider</label>
            <Input value={settings.sms_provider} onChange={e => updateField("sms_provider", e.target.value)}
              placeholder="e.g. twilio, vonage" className="h-9 text-sm" data-testid="sms-provider" />
          </div>
          <div>
            <label className="text-[11px] font-medium text-stone-600 mb-1 block">API Key</label>
            <SecretInput value={settings.sms_api_key} onChange={e => updateField("sms_api_key", e.target.value)}
              placeholder="Provider API key" testId="sms-api-key" />
          </div>
          <div>
            <label className="text-[11px] font-medium text-stone-600 mb-1 block">Sender Number</label>
            <Input value={settings.sms_sender_number} onChange={e => updateField("sms_sender_number", e.target.value)}
              placeholder="+44..." className="h-9 text-sm" data-testid="sms-sender" />
          </div>
        </SettingsCard>

        {/* Email */}
        <SettingsCard icon={Envelope} iconColor="#3b82f6" title="Email (Resend)" description="Send emails to guests via Resend"
          enabled={settings.email_enabled} onToggle={v => updateField("email_enabled", v)} testId="email-settings">
          <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-xs text-blue-800">
            <p className="flex items-center gap-1"><Info size={12} /> Email is configured via environment variables. Current status: <span className="font-medium">Active (Resend)</span></p>
          </div>
          <button onClick={() => testChannel("email")} disabled={testing === "email"}
            className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 flex items-center gap-1.5 font-medium transition-colors disabled:opacity-50"
            data-testid="test-email-btn">
            <PaperPlaneTilt size={12} weight="fill" /> {testing === "email" ? "Testing..." : "Test Email"}
          </button>
        </SettingsCard>

        {/* Auto-Reply Settings */}
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="auto-reply-settings">
          <div className="px-5 py-4 flex items-center justify-between border-b border-stone-100">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-amber-50 flex items-center justify-center">
                <Robot size={18} className="text-amber-600" weight="fill" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-stone-900">Auto-Reply</h3>
                <p className="text-[11px] text-stone-400">Automatic response when no staff is available</p>
              </div>
            </div>
            <Switch checked={settings.auto_reply_enabled} onCheckedChange={v => updateField("auto_reply_enabled", v)} data-testid="auto-reply-toggle" />
          </div>
          {settings.auto_reply_enabled && (
            <div className="px-5 py-4 space-y-3">
              <div>
                <label className="text-[11px] font-medium text-stone-600 mb-1 block">Welcome Message (sent on first contact)</label>
                <Input value={settings.welcome_message} onChange={e => updateField("welcome_message", e.target.value)}
                  className="h-9 text-sm" data-testid="welcome-msg" />
              </div>
              <div>
                <label className="text-[11px] font-medium text-stone-600 mb-1 block">Auto-Reply Message (sent when staff unavailable)</label>
                <Input value={settings.auto_reply_message} onChange={e => updateField("auto_reply_message", e.target.value)}
                  className="h-9 text-sm" data-testid="auto-reply-msg" />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
