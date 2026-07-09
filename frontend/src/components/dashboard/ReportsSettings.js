import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { FileText, CalendarBlank, EnvelopeSimple, X, Plus, Trash, ArrowsClockwise, Eye, PaperPlaneTilt as Send, CheckCircle } from "@phosphor-icons/react";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
// iter 389: converted from modal to inline page panel (Dialog imports replaced by shells)
const DialogContent = ({ children, className = "", ...rest }) => (
  <div className={`bg-white border border-stone-200/80 rounded-xl shadow-card p-6 w-full ${className}`} {...rest}>{children}</div>
);
const DialogHeader = ({ children, className = "" }) => <div className={`mb-4 ${className}`}>{children}</div>;
const DialogTitle = ({ children, className = "" }) => <h2 className={`text-lg font-semibold ${className}`}>{children}</h2>;
import { Switch } from "@/components/ui/switch";
import { API, formatApiErrorDetail } from "./config";

const ReportsSettings = ({ isOpen, onClose }) => {
  const [settings, setSettings] = useState({
    email: "",
    frequency: "weekly",
    include_competitor_comparison: true,
    include_sentiment_summary: true,
    include_action_items: true,
    enabled: false,
    last_sent: null
  });
  const [isSaving, setIsSaving] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [previewHtml, setPreviewHtml] = useState("");

  useEffect(() => {
    if (isOpen) {
      fetchSettings();
    }
  }, [isOpen]);

  const fetchSettings = async () => {
    try {
      const response = await axios.get(`${API}/reports/settings`);
      setSettings(response.data);
    } catch (error) {
      console.error("Error fetching report settings:", error);
    }
  };

  const saveSettings = async () => {
    setIsSaving(true);
    try {
      await axios.put(`${API}/reports/settings`, settings);
      toast.success("Report settings saved!");
    } catch (error) {
      console.error("Error saving settings:", error);
      toast.error("Failed to save settings");
    } finally {
      setIsSaving(false);
    }
  };

  const sendReportNow = async () => {
    setIsSending(true);
    try {
      const result = await axios.post(`${API}/reports/send-now`);
      toast.success(result.data.message);
      await fetchSettings();
    } catch (error) {
      console.error("Error sending report:", error);
      toast.error(error.response?.data?.detail || "Failed to send report");
    } finally {
      setIsSending(false);
    }
  };

  const previewReport = async () => {
    try {
      const response = await axios.get(`${API}/reports/preview`);
      setPreviewHtml(response.data.html);
      setShowPreview(true);
    } catch (error) {
      console.error("Error loading preview:", error);
      toast.error("Failed to load report preview");
    }
  };

  return (
    <DialogContent className="sm:max-w-[550px]" data-testid="reports-settings-dialog">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2 text-[#1C1917] font-['Work_Sans']">
          <CalendarBlank size={20} weight="fill" className="text-[#3E5245]" />
          Scheduled Reports
        </DialogTitle>
      </DialogHeader>
      
      <div className="space-y-6 py-4">
        {/* Enable/Disable Toggle */}
        <div className="flex items-center justify-between p-4 bg-[#FAF9F6] rounded-md border border-[#E7E5E4]">
          <div>
            <p className="font-medium text-[#1C1917]">Enable Scheduled Reports</p>
            <p className="text-sm text-[#57534E]">Receive automated performance summaries</p>
          </div>
          <Switch
            checked={settings.enabled}
            onCheckedChange={(checked) => setSettings(prev => ({ ...prev, enabled: checked }))}
            data-testid="reports-enable-switch"
          />
        </div>

        {/* Email & Frequency */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-[#1C1917] flex items-center gap-2">
              <EnvelopeSimple size={16} className="text-[#57534E]" />
              Email Address
            </label>
            <Input
              type="email"
              placeholder="hotel@example.com"
              value={settings.email}
              onChange={(e) => setSettings(prev => ({ ...prev, email: e.target.value }))}
              className="border-stone-200"
              data-testid="report-email-input"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-[#1C1917]">Frequency</label>
            <Select
              value={settings.frequency}
              onValueChange={(value) => setSettings(prev => ({ ...prev, frequency: value }))}
              data-testid="report-frequency-select"
            >
              <SelectTrigger className="border-stone-200">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="daily">Daily</SelectItem>
                <SelectItem value="weekly">Weekly</SelectItem>
                <SelectItem value="monthly">Monthly</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Report Content Options */}
        <div className="space-y-3">
          <label className="text-sm font-medium text-[#1C1917]">Report Contents</label>
          
          <div className="flex items-center justify-between p-3 bg-white border border-stone-200 rounded-md">
            <span className="text-sm">Competitor Comparison</span>
            <Switch
              checked={settings.include_competitor_comparison}
              onCheckedChange={(checked) => setSettings(prev => ({ ...prev, include_competitor_comparison: checked }))}
              data-testid="include-competitors-switch"
            />
          </div>
          
          <div className="flex items-center justify-between p-3 bg-white border border-stone-200 rounded-md">
            <span className="text-sm">Sentiment Summary</span>
            <Switch
              checked={settings.include_sentiment_summary}
              onCheckedChange={(checked) => setSettings(prev => ({ ...prev, include_sentiment_summary: checked }))}
              data-testid="include-sentiment-switch"
            />
          </div>
          
          <div className="flex items-center justify-between p-3 bg-white border border-stone-200 rounded-md">
            <span className="text-sm">Action Items & Recommendations</span>
            <Switch
              checked={settings.include_action_items}
              onCheckedChange={(checked) => setSettings(prev => ({ ...prev, include_action_items: checked }))}
              data-testid="include-actions-switch"
            />
          </div>
        </div>

        {/* Last Sent Info */}
        {settings.last_sent && (
          <div className="p-3 bg-[#E8EDE7] border border-[#D5DDD3] rounded-md">
            <p className="text-sm text-[#57534E]">
              Last report sent: <strong>{new Date(settings.last_sent).toLocaleString()}</strong>
            </p>
          </div>
        )}

        {/* Demo Mode Notice */}
        <div className="p-3 bg-[#FAF9F6] border border-[#E7E5E4] rounded-md">
          <p className="text-xs text-[#57534E]">
            <strong>Note:</strong> In demo mode, reports are logged but not actually sent. 
            Configure a production Resend API key to enable real email delivery.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-between pt-4 border-t border-stone-200">
          <div className="flex items-center gap-2">
            <button
              onClick={previewReport}
              className="bg-white border border-stone-200 text-[#1C1917] px-3 py-2 rounded-md hover:bg-stone-50 transition-colors flex items-center gap-2"
              data-testid="preview-report-btn"
            >
              <Eye size={16} />
              Preview
            </button>
            <button
              onClick={sendReportNow}
              disabled={!settings.email || isSending}
              className="bg-white border border-stone-200 text-[#1C1917] px-3 py-2 rounded-md hover:bg-stone-50 transition-colors disabled:opacity-50 flex items-center gap-2"
              data-testid="send-report-now-btn"
            >
              <Send size={16} />
              {isSending ? "Sending..." : "Send Now"}
            </button>
          </div>
          
          <button
            onClick={saveSettings}
            disabled={isSaving}
            className="bg-[#3E5245] text-white px-4 py-2 rounded-md hover:bg-[#2A3B30] transition-colors disabled:opacity-50 flex items-center gap-2"
            data-testid="save-report-settings-btn"
          >
            {isSaving ? (
              <>
                <ArrowsClockwise size={16} className="animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <CheckCircle size={16} weight="fill" />
                Save Settings
              </>
            )}
          </button>
        </div>
      </div>

      {/* Preview Modal */}
      {showPreview && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowPreview(false)}>
          <div className="bg-white rounded-lg max-w-3xl max-h-[90vh] overflow-auto m-4" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 bg-white border-b border-stone-200 p-4 flex justify-between items-center">
              <h3 className="font-medium">Report Preview</h3>
              <button onClick={() => setShowPreview(false)} className="p-2 hover:bg-stone-100 rounded-md">
                <X size={20} />
              </button>
            </div>
            <div dangerouslySetInnerHTML={{ __html: previewHtml }} />
          </div>
        </div>
      )}
    </DialogContent>
  );
};



export { ReportsSettings };
