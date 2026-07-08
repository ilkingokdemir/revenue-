import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { PaintBrush, Palette, Upload, Image, ArrowsClockwise, Buildings, X } from "@phosphor-icons/react";
import { DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { API, formatApiErrorDetail } from "./config";

const BrandingPanel = ({ isOpen, onClose, branding, onBrandingUpdate }) => {
  const [form, setForm] = useState({
    app_name: "",
    subtitle: "",
    primary_color: "#3E5245",
    accent_color: "#D4A373",
    powered_by_text: "",
    powered_by_visible: false
  });
  const [isSaving, setIsSaving] = useState(false);
  const [logoPreview, setLogoPreview] = useState(null);
  const [isUploadingLogo, setIsUploadingLogo] = useState(false);

  useEffect(() => {
    if (branding) {
      setForm({
        app_name: branding.app_name || "MyHotelBox & ReveniQ",
        subtitle: branding.subtitle || "Otel PMS & Revenue Management",
        primary_color: branding.primary_color || "#3E5245",
        accent_color: branding.accent_color || "#D4A373",
        powered_by_text: branding.powered_by_text || "",
        powered_by_visible: branding.powered_by_visible || false
      });
      setLogoPreview(branding.logo_url || null);
    }
  }, [branding]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const response = await axios.put(`${API}/branding`, form);
      onBrandingUpdate(response.data);
      toast.success("Branding updated!");
    } catch (error) {
      toast.error("Failed to save branding");
    } finally {
      setIsSaving(false);
    }
  };

  const handleLogoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast.error("Please select an image file");
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      toast.error("Image must be under 2MB");
      return;
    }
    setIsUploadingLogo(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await axios.post(`${API}/branding/logo`, formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      setLogoPreview(response.data.logo_url);
      onBrandingUpdate({ ...branding, logo_url: response.data.logo_url });
      toast.success("Logo uploaded!");
    } catch (error) {
      toast.error("Failed to upload logo");
    } finally {
      setIsUploadingLogo(false);
    }
  };

  const handleRemoveLogo = async () => {
    try {
      await axios.delete(`${API}/branding/logo`);
      setLogoPreview(null);
      onBrandingUpdate({ ...branding, logo_url: null });
      toast.success("Logo removed");
    } catch (error) {
      toast.error("Failed to remove logo");
    }
  };

  const presetColors = [
    { name: "Forest", primary: "#3E5245", accent: "#D4A373" },
    { name: "Ocean", primary: "#1E3A5F", accent: "#4ECDC4" },
    { name: "Midnight", primary: "#1A1A2E", accent: "#E94560" },
    { name: "Plum", primary: "#4A1942", accent: "#C47AFF" },
    { name: "Charcoal", primary: "#2D2D2D", accent: "#FFB347" },
    { name: "Navy", primary: "#003366", accent: "#F0C040" }
  ];

  return (
    <DialogContent className="sm:max-w-[650px] max-h-[90vh] overflow-y-auto" data-testid="branding-dialog">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2 text-[#1C1917] font-['Work_Sans']">
          <PaintBrush size={22} className="text-[#3E5245]" />
          White-Label Branding
        </DialogTitle>
      </DialogHeader>

      <div className="space-y-6 mt-2">
        {/* Live Preview */}
        <div className="border border-stone-200 rounded-lg overflow-hidden" data-testid="branding-preview">
          <div className="px-4 py-3 border-b border-stone-100" style={{ backgroundColor: form.primary_color }}>
            <div className="flex items-center gap-3">
              {logoPreview ? (
                <img src={logoPreview} alt="Logo" className="w-9 h-9 rounded-md object-cover" />
              ) : (
                <div className="w-9 h-9 rounded-md flex items-center justify-center" style={{ backgroundColor: "rgba(255,255,255,0.2)" }}>
                  <Buildings size={20} className="text-white" weight="fill" />
                </div>
              )}
              <div>
                <h3 className="text-sm font-semibold text-white font-['Work_Sans']">{form.app_name || "MyHotelBox & ReveniQ"}</h3>
                <p className="text-xs" style={{ color: "rgba(255,255,255,0.7)" }}>{form.subtitle || "Otel PMS & Revenue Management"}</p>
              </div>
            </div>
          </div>
          <div className="px-4 py-3 bg-[#FAF9F6] flex items-center gap-2">
            <div className="h-2 w-16 rounded-full" style={{ backgroundColor: form.primary_color }}></div>
            <div className="h-2 w-10 rounded-full" style={{ backgroundColor: form.accent_color }}></div>
            <div className="h-2 w-12 rounded-full bg-stone-200"></div>
            <span className="text-[10px] text-[#57534E] ml-auto italic">Live Preview</span>
          </div>
          {form.powered_by_visible && form.powered_by_text && (
            <div className="px-4 py-1.5 bg-stone-50 border-t border-stone-100 text-center">
              <span className="text-[10px] text-[#78716C]">Powered by {form.powered_by_text}</span>
            </div>
          )}
        </div>

        {/* Logo Upload */}
        <div>
          <label className="text-sm font-medium text-[#1C1917] mb-2 block">Logo</label>
          <div className="flex items-center gap-3">
            {logoPreview ? (
              <div className="relative group">
                <img src={logoPreview} alt="Logo" className="w-14 h-14 rounded-lg object-cover border border-stone-200" data-testid="branding-logo-preview" />
                <button
                  onClick={handleRemoveLogo}
                  className="absolute -top-1.5 -right-1.5 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                  data-testid="remove-logo-btn"
                >
                  <X size={10} />
                </button>
              </div>
            ) : (
              <div className="w-14 h-14 rounded-lg border-2 border-dashed border-stone-300 flex items-center justify-center text-stone-400">
                <Image size={24} />
              </div>
            )}
            <div>
              <label
                className="inline-flex items-center gap-1.5 bg-white border border-stone-200 text-[#1C1917] px-3 py-1.5 rounded-md text-sm hover:bg-stone-50 transition-colors cursor-pointer"
                data-testid="upload-logo-btn"
              >
                <Upload size={14} />
                {isUploadingLogo ? "Uploading..." : "Upload Logo"}
                <input
                  type="file"
                  accept="image/*"
                  onChange={handleLogoUpload}
                  className="hidden"
                  disabled={isUploadingLogo}
                />
              </label>
              <p className="text-[10px] text-[#78716C] mt-1">PNG, JPG, SVG. Max 2MB.</p>
            </div>
          </div>
        </div>

        {/* App Name & Subtitle */}
        <div className="grid grid-cols-1 gap-3">
          <div>
            <label className="text-sm font-medium text-[#1C1917] mb-1 block">App Name</label>
            <Input
              value={form.app_name}
              onChange={(e) => setForm(prev => ({ ...prev, app_name: e.target.value }))}
              placeholder="MyHotelBox & ReveniQ"
              className="border-stone-200"
              data-testid="branding-app-name"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-[#1C1917] mb-1 block">Subtitle</label>
            <Input
              value={form.subtitle}
              onChange={(e) => setForm(prev => ({ ...prev, subtitle: e.target.value }))}
              placeholder="Otel PMS & Revenue Management"
              className="border-stone-200"
              data-testid="branding-subtitle"
            />
          </div>
        </div>

        {/* Color Presets */}
        <div>
          <label className="text-sm font-medium text-[#1C1917] mb-2 block">Color Theme</label>
          <div className="grid grid-cols-3 gap-2 mb-3">
            {presetColors.map((preset) => (
              <button
                key={preset.name}
                onClick={() => setForm(prev => ({ ...prev, primary_color: preset.primary, accent_color: preset.accent }))}
                className={`flex items-center gap-2 p-2 rounded-md border text-xs transition-all ${
                  form.primary_color === preset.primary ? "border-stone-800 bg-stone-50 ring-1 ring-stone-300" : "border-stone-200 hover:border-stone-300"
                }`}
                data-testid={`color-preset-${preset.name.toLowerCase()}`}
              >
                <div className="flex gap-0.5">
                  <div className="w-4 h-4 rounded-sm" style={{ backgroundColor: preset.primary }}></div>
                  <div className="w-4 h-4 rounded-sm" style={{ backgroundColor: preset.accent }}></div>
                </div>
                <span className="text-[#57534E]">{preset.name}</span>
              </button>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-[#57534E] mb-1 block">Primary Color</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={form.primary_color}
                  onChange={(e) => setForm(prev => ({ ...prev, primary_color: e.target.value }))}
                  className="w-8 h-8 rounded border border-stone-200 cursor-pointer"
                  data-testid="branding-primary-color"
                />
                <Input
                  value={form.primary_color}
                  onChange={(e) => setForm(prev => ({ ...prev, primary_color: e.target.value }))}
                  className="border-stone-200 font-mono text-xs"
                />
              </div>
            </div>
            <div>
              <label className="text-xs text-[#57534E] mb-1 block">Accent Color</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={form.accent_color}
                  onChange={(e) => setForm(prev => ({ ...prev, accent_color: e.target.value }))}
                  className="w-8 h-8 rounded border border-stone-200 cursor-pointer"
                  data-testid="branding-accent-color"
                />
                <Input
                  value={form.accent_color}
                  onChange={(e) => setForm(prev => ({ ...prev, accent_color: e.target.value }))}
                  className="border-stone-200 font-mono text-xs"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Powered By */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium text-[#1C1917]">Powered By Badge</label>
            <Switch
              checked={form.powered_by_visible}
              onCheckedChange={(checked) => setForm(prev => ({ ...prev, powered_by_visible: checked }))}
              data-testid="branding-powered-by-toggle"
            />
          </div>
          {form.powered_by_visible && (
            <Input
              value={form.powered_by_text}
              onChange={(e) => setForm(prev => ({ ...prev, powered_by_text: e.target.value }))}
              placeholder="MyHotelBox"
              className="border-stone-200"
              data-testid="branding-powered-by-text"
            />
          )}
        </div>

        {/* Save */}
        <button
          onClick={handleSave}
          disabled={isSaving}
          className="w-full text-white py-2.5 rounded-md transition-colors flex items-center justify-center gap-2 disabled:opacity-50 font-medium"
          style={{ backgroundColor: form.primary_color }}
          data-testid="save-branding-btn"
        >
          {isSaving ? (
            <ArrowsClockwise size={16} className="animate-spin" />
          ) : (
            <PaintBrush size={16} />
          )}
          {isSaving ? "Saving..." : "Save Branding"}
        </button>
      </div>
    </DialogContent>
  );
};


export { BrandingPanel };
