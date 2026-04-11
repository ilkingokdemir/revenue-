import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Palette, Buildings, Phone, EnvelopeSimple, MapPin, Image, Eye, CheckCircle,
  ArrowsClockwise, FloppyDisk, Trash, CaretRight, Layout, Globe, Sparkle,
  TextT, InstagramLogo, FacebookLogo, Link as LinkIcon,
} from "@phosphor-icons/react";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { API } from "./config";
import { TEMPLATE_LIST, getTemplate } from "../../templates/templateConfig";

const TemplateCustomizer = ({ properties }) => {
  const [selectedProperty, setSelectedProperty] = useState(properties?.filter(p => p.id !== "default")[0]?.id || "");
  const [settings, setSettings] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [activeSection, setActiveSection] = useState("info");
  const [galleryInput, setGalleryInput] = useState("");

  const fetchSettings = useCallback(async () => {
    if (!selectedProperty) return;
    setIsLoading(true);
    try {
      const { data } = await axios.get(`${API}/template-settings/${selectedProperty}`);
      setSettings(data);
    } catch (e) {
      toast.error("Failed to load template settings");
    } finally {
      setIsLoading(false);
    }
  }, [selectedProperty]);

  useEffect(() => { fetchSettings(); }, [fetchSettings]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const { data } = await axios.put(`${API}/template-settings/${selectedProperty}`, settings);
      setSettings(data);
      toast.success("Template settings saved!");
    } catch (e) {
      toast.error("Failed to save settings");
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = async () => {
    try {
      await axios.delete(`${API}/template-settings/${selectedProperty}`);
      setSettings({ property_id: selectedProperty, template_id: "booking-classic" });
      toast.success("Template reset to defaults");
    } catch (e) {
      toast.error("Failed to reset");
    }
  };

  const update = (field, value) => setSettings(prev => ({ ...prev, [field]: value }));

  const addGalleryImage = () => {
    if (!galleryInput.trim()) return;
    update("gallery_images", [...(settings.gallery_images || []), galleryInput.trim()]);
    setGalleryInput("");
  };

  const removeGalleryImage = (idx) => {
    update("gallery_images", (settings.gallery_images || []).filter((_, i) => i !== idx));
  };

  const currentTemplate = getTemplate(settings?.template_id || "booking-classic");
  const previewUrl = `${window.location.origin}/book?property=${selectedProperty}&template=${settings?.template_id || "booking-classic"}`;

  const sections = [
    { id: "info", icon: Buildings, label: "Hotel Info" },
    { id: "template", icon: Layout, label: "Template" },
    { id: "colors", icon: Palette, label: "Colors" },
    { id: "images", icon: Image, label: "Images" },
    { id: "features", icon: Sparkle, label: "Features" },
    { id: "text", icon: TextT, label: "Custom Text" },
    { id: "social", icon: Globe, label: "Social & SEO" },
  ];

  if (isLoading || !settings) {
    return (
      <div className="p-5">
        <div className="flex justify-center py-20">
          <ArrowsClockwise size={24} className="animate-spin text-stone-400" />
        </div>
      </div>
    );
  }

  return (
    <div className="p-5" data-testid="template-customizer">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-stone-800" data-testid="customizer-title">Customize Template</h2>
          <p className="text-sm text-stone-500 mt-0.5">Personalize your booking website for each property</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={selectedProperty} onChange={e => setSelectedProperty(e.target.value)}
            className="text-xs border border-stone-200 rounded-lg px-2.5 py-1.5 bg-white text-stone-700 font-medium"
            data-testid="customizer-property-select">
            {properties?.filter(p => p.id !== "default").map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          <a href={previewUrl} target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 bg-stone-800 text-white text-xs font-medium rounded-lg hover:bg-stone-900 transition-colors"
            data-testid="preview-live-btn">
            <Eye size={13} /> Live Preview
          </a>
        </div>
      </div>

      <div className="flex gap-5">
        {/* Left: Section Nav + Form */}
        <div className="w-80 flex-shrink-0 space-y-4">
          {/* Section Tabs */}
          <div className="bg-white border border-stone-200 rounded-lg overflow-hidden">
            {sections.map(s => (
              <button key={s.id} onClick={() => setActiveSection(s.id)}
                className={`w-full flex items-center gap-2.5 px-4 py-2.5 text-left text-sm transition-colors ${
                  activeSection === s.id ? "bg-emerald-50 text-emerald-800 font-medium border-r-2 border-emerald-600" : "text-stone-600 hover:bg-stone-50"
                }`}
                data-testid={`section-${s.id}`}>
                <s.icon size={16} weight={activeSection === s.id ? "fill" : "regular"} />
                {s.label}
              </button>
            ))}
          </div>

          {/* Save / Reset */}
          <div className="flex gap-2">
            <button onClick={handleSave} disabled={isSaving}
              className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2.5 bg-emerald-700 text-white text-sm font-medium rounded-lg hover:bg-emerald-800 transition-colors disabled:opacity-50"
              data-testid="save-settings-btn">
              {isSaving ? <ArrowsClockwise size={14} className="animate-spin" /> : <FloppyDisk size={14} />}
              {isSaving ? "Saving..." : "Save Changes"}
            </button>
            <button onClick={handleReset}
              className="px-3 py-2.5 border border-stone-300 text-stone-600 text-sm rounded-lg hover:bg-stone-50 transition-colors"
              data-testid="reset-settings-btn">
              <Trash size={14} />
            </button>
          </div>
        </div>

        {/* Right: Form Content */}
        <div className="flex-1 min-w-0">
          {/* Hotel Info Section */}
          {activeSection === "info" && (
            <div className="bg-white border border-stone-200 rounded-lg p-5 space-y-4" data-testid="section-info-form">
              <h3 className="text-sm font-semibold text-stone-800 flex items-center gap-2"><Buildings size={16} className="text-emerald-600" /> Hotel Information</h3>
              <p className="text-xs text-stone-500 -mt-2">Override your hotel details displayed on the booking page</p>
              <FieldGroup label="Hotel Name" hint="Leave empty to use property name from settings">
                <Input value={settings.hotel_name || ""} onChange={e => update("hotel_name", e.target.value)} placeholder="e.g. The Grand Hotel London" data-testid="input-hotel-name" />
              </FieldGroup>
              <FieldGroup label="Tagline">
                <Input value={settings.tagline || ""} onChange={e => update("tagline", e.target.value)} placeholder="e.g. Your Home in the Heart of London" data-testid="input-tagline" />
              </FieldGroup>
              <FieldGroup label="Description">
                <textarea value={settings.description || ""} onChange={e => update("description", e.target.value)} placeholder="Describe your property..." rows={3} className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm resize-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent" data-testid="input-description" />
              </FieldGroup>
              <div className="grid grid-cols-2 gap-3">
                <FieldGroup label="Phone">
                  <div className="relative">
                    <Phone size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
                    <Input value={settings.contact_phone || ""} onChange={e => update("contact_phone", e.target.value)} placeholder="+44 20 7123 4567" className="pl-9" data-testid="input-phone" />
                  </div>
                </FieldGroup>
                <FieldGroup label="Email">
                  <div className="relative">
                    <EnvelopeSimple size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
                    <Input value={settings.contact_email || ""} onChange={e => update("contact_email", e.target.value)} placeholder="info@hotel.com" className="pl-9" data-testid="input-email" />
                  </div>
                </FieldGroup>
              </div>
              <FieldGroup label="Address">
                <div className="relative">
                  <MapPin size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
                  <Input value={settings.address || ""} onChange={e => update("address", e.target.value)} placeholder="123 High Street, London EC1A 1BB" className="pl-9" data-testid="input-address" />
                </div>
              </FieldGroup>
            </div>
          )}

          {/* Template Selection */}
          {activeSection === "template" && (
            <div className="bg-white border border-stone-200 rounded-lg p-5 space-y-4" data-testid="section-template-form">
              <h3 className="text-sm font-semibold text-stone-800 flex items-center gap-2"><Layout size={16} className="text-emerald-600" /> Select Template</h3>
              <p className="text-xs text-stone-500 -mt-2">Choose a base template design for your booking website</p>
              <div className="grid grid-cols-2 gap-3">
                {TEMPLATE_LIST.map(tmpl => (
                  <button key={tmpl.id} onClick={() => update("template_id", tmpl.id)}
                    className={`border-2 rounded-lg p-3 text-left transition-all ${settings.template_id === tmpl.id ? "border-emerald-600 bg-emerald-50" : "border-stone-200 hover:border-stone-300"}`}
                    data-testid={`select-template-${tmpl.id}`}>
                    <div className="h-16 rounded-md mb-2 overflow-hidden" style={{ background: tmpl.colors.heroBg || tmpl.colors.headerBg }}>
                      <div className="h-4" style={{ background: tmpl.colors.headerBg }} />
                    </div>
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <span className="text-xs font-semibold text-stone-800">{tmpl.name}</span>
                      {settings.template_id === tmpl.id && <CheckCircle size={14} weight="fill" className="text-emerald-600" />}
                    </div>
                    <span className="text-[10px] text-stone-500">{tmpl.platform}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Colors Section */}
          {activeSection === "colors" && (
            <div className="bg-white border border-stone-200 rounded-lg p-5 space-y-4" data-testid="section-colors-form">
              <h3 className="text-sm font-semibold text-stone-800 flex items-center gap-2"><Palette size={16} className="text-emerald-600" /> Color Overrides</h3>
              <p className="text-xs text-stone-500 -mt-2">Override template colors. Leave empty to use template defaults.</p>
              <div className="grid grid-cols-2 gap-4">
                <ColorField label="Primary Color" value={settings.primary_color} defaultVal={currentTemplate.colors.primary} onChange={v => update("primary_color", v)} testId="color-primary" />
                <ColorField label="Accent / CTA" value={settings.accent_color} defaultVal={currentTemplate.colors.accent} onChange={v => update("accent_color", v)} testId="color-accent" />
                <ColorField label="Header Background" value={settings.header_bg_color} defaultVal={currentTemplate.colors.headerBg} onChange={v => update("header_bg_color", v)} testId="color-header-bg" />
                <ColorField label="Header Text" value={settings.header_text_color} defaultVal={currentTemplate.colors.headerText} onChange={v => update("header_text_color", v)} testId="color-header-text" />
                <ColorField label="Page Background" value={settings.body_bg_color} defaultVal={currentTemplate.colors.bodyBg} onChange={v => update("body_bg_color", v)} testId="color-body-bg" />
              </div>
            </div>
          )}

          {/* Images Section */}
          {activeSection === "images" && (
            <div className="bg-white border border-stone-200 rounded-lg p-5 space-y-4" data-testid="section-images-form">
              <h3 className="text-sm font-semibold text-stone-800 flex items-center gap-2"><Image size={16} className="text-emerald-600" /> Images</h3>
              <FieldGroup label="Logo URL">
                <Input value={settings.logo_url || ""} onChange={e => update("logo_url", e.target.value)} placeholder="https://example.com/logo.png" data-testid="input-logo-url" />
                {settings.logo_url && <img src={settings.logo_url} alt="Logo" className="h-10 mt-2 object-contain rounded" />}
              </FieldGroup>
              <FieldGroup label="Hero Image URL" hint="Main header background image">
                <Input value={settings.hero_image_url || ""} onChange={e => update("hero_image_url", e.target.value)} placeholder="https://example.com/hero.jpg" data-testid="input-hero-image" />
                {settings.hero_image_url && <img src={settings.hero_image_url} alt="Hero" className="h-28 w-full mt-2 object-cover rounded-lg" />}
              </FieldGroup>
              <FieldGroup label="Gallery Images" hint="Property photo gallery for Airbnb-style templates">
                <div className="flex gap-2">
                  <Input value={galleryInput} onChange={e => setGalleryInput(e.target.value)} placeholder="https://example.com/photo.jpg" className="flex-1" data-testid="input-gallery-url" onKeyDown={e => e.key === "Enter" && addGalleryImage()} />
                  <button onClick={addGalleryImage} className="px-3 py-2 bg-emerald-700 text-white rounded-lg text-xs font-medium hover:bg-emerald-800" data-testid="add-gallery-btn">Add</button>
                </div>
                {(settings.gallery_images || []).length > 0 && (
                  <div className="grid grid-cols-4 gap-2 mt-2">
                    {settings.gallery_images.map((url, i) => (
                      <div key={i} className="relative group">
                        <img src={url} alt="" className="h-20 w-full object-cover rounded-lg" />
                        <button onClick={() => removeGalleryImage(i)}
                          className="absolute top-1 right-1 w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity text-xs"
                          data-testid={`remove-gallery-${i}`}>
                          <Trash size={10} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </FieldGroup>
            </div>
          )}

          {/* Features Section */}
          {activeSection === "features" && (
            <div className="bg-white border border-stone-200 rounded-lg p-5 space-y-4" data-testid="section-features-form">
              <h3 className="text-sm font-semibold text-stone-800 flex items-center gap-2"><Sparkle size={16} className="text-emerald-600" /> Feature Toggles</h3>
              <p className="text-xs text-stone-500 -mt-2">Enable or disable booking page features. When unset, template defaults apply.</p>
              {[
                { field: "show_rating_badge", label: "Show Rating Badge", desc: "Display the review rating score on the hero section", default: currentTemplate.showRatingBadge },
                { field: "show_urgency", label: "Show Urgency Alerts", desc: "Show 'Only X left!' warnings on rooms with low availability", default: currentTemplate.showUrgency },
                { field: "show_free_cancellation", label: "Show Free Cancellation", desc: "Highlight free cancellation badge on eligible rooms", default: currentTemplate.showFreeCancellation },
                { field: "show_security_badges", label: "Show Security Badges", desc: "Display SSL, PCI, and verified property trust badges", default: currentTemplate.showSecurityBadges },
              ].map(({ field, label, desc, default: def }) => (
                <div key={field} className="flex items-center justify-between py-2 border-b border-stone-100 last:border-0">
                  <div>
                    <span className="text-sm font-medium text-stone-700">{label}</span>
                    <p className="text-[11px] text-stone-400 mt-0.5">{desc}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-stone-400">Default: {def ? "On" : "Off"}</span>
                    <Switch
                      checked={settings[field] ?? def}
                      onCheckedChange={v => update(field, v)}
                      data-testid={`toggle-${field}`}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Custom Text */}
          {activeSection === "text" && (
            <div className="bg-white border border-stone-200 rounded-lg p-5 space-y-4" data-testid="section-text-form">
              <h3 className="text-sm font-semibold text-stone-800 flex items-center gap-2"><TextT size={16} className="text-emerald-600" /> Custom Text</h3>
              <FieldGroup label="Welcome Message" hint="Displayed below the hotel name on the landing page">
                <textarea value={settings.welcome_message || ""} onChange={e => update("welcome_message", e.target.value)} placeholder="Welcome to our hotel..." rows={2} className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm resize-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent" data-testid="input-welcome" />
              </FieldGroup>
              <FieldGroup label="Booking Button Text" hint="Custom label for the booking CTA button">
                <Input value={settings.booking_button_text || ""} onChange={e => update("booking_button_text", e.target.value)} placeholder="e.g. Reserve Now (default: Reserve)" data-testid="input-btn-text" />
              </FieldGroup>
              <FieldGroup label="Footer Text" hint="Custom text in the page footer">
                <Input value={settings.footer_text || ""} onChange={e => update("footer_text", e.target.value)} placeholder="e.g. The Grand Hotel © 2026" data-testid="input-footer" />
              </FieldGroup>
            </div>
          )}

          {/* Social & SEO */}
          {activeSection === "social" && (
            <div className="bg-white border border-stone-200 rounded-lg p-5 space-y-4" data-testid="section-social-form">
              <h3 className="text-sm font-semibold text-stone-800 flex items-center gap-2"><Globe size={16} className="text-emerald-600" /> Social Links & SEO</h3>
              <div className="grid grid-cols-2 gap-3">
                <FieldGroup label="Facebook">
                  <div className="relative">
                    <FacebookLogo size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
                    <Input value={settings.facebook_url || ""} onChange={e => update("facebook_url", e.target.value)} placeholder="https://facebook.com/hotel" className="pl-9" data-testid="input-facebook" />
                  </div>
                </FieldGroup>
                <FieldGroup label="Instagram">
                  <div className="relative">
                    <InstagramLogo size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
                    <Input value={settings.instagram_url || ""} onChange={e => update("instagram_url", e.target.value)} placeholder="https://instagram.com/hotel" className="pl-9" data-testid="input-instagram" />
                  </div>
                </FieldGroup>
                <FieldGroup label="Twitter / X">
                  <div className="relative">
                    <LinkIcon size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
                    <Input value={settings.twitter_url || ""} onChange={e => update("twitter_url", e.target.value)} placeholder="https://x.com/hotel" className="pl-9" data-testid="input-twitter" />
                  </div>
                </FieldGroup>
                <FieldGroup label="TripAdvisor">
                  <div className="relative">
                    <LinkIcon size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
                    <Input value={settings.tripadvisor_url || ""} onChange={e => update("tripadvisor_url", e.target.value)} placeholder="https://tripadvisor.com/hotel" className="pl-9" data-testid="input-tripadvisor" />
                  </div>
                </FieldGroup>
              </div>
              <div className="border-t border-stone-100 pt-4 mt-2">
                <h4 className="text-xs font-semibold text-stone-600 mb-3">SEO</h4>
                <FieldGroup label="Page Title">
                  <Input value={settings.meta_title || ""} onChange={e => update("meta_title", e.target.value)} placeholder="Book Your Stay at The Grand Hotel" data-testid="input-meta-title" />
                </FieldGroup>
                <FieldGroup label="Meta Description" className="mt-3">
                  <textarea value={settings.meta_description || ""} onChange={e => update("meta_description", e.target.value)} placeholder="Book direct for the best rates..." rows={2} className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm resize-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent" data-testid="input-meta-desc" />
                </FieldGroup>
              </div>
            </div>
          )}

          {/* Live Preview Card */}
          <div className="bg-stone-50 border border-stone-200 rounded-lg p-4 mt-4">
            <div className="flex items-center gap-2 mb-3">
              <Eye size={16} className="text-emerald-600" />
              <h4 className="text-xs font-semibold text-stone-700">Live Preview</h4>
            </div>
            <div className="rounded-lg overflow-hidden border border-stone-300 bg-white" style={{ height: "320px" }}>
              <iframe src={previewUrl} title="Template Preview" className="w-full h-full" style={{ transform: "scale(0.5)", transformOrigin: "top left", width: "200%", height: "200%" }} data-testid="preview-iframe" />
            </div>
            <a href={previewUrl} target="_blank" rel="noopener noreferrer"
              className="flex items-center justify-center gap-1.5 w-full mt-3 px-4 py-2 border border-stone-300 text-stone-700 text-xs font-medium rounded-lg hover:bg-white transition-colors"
              data-testid="open-preview-btn">
              <Eye size={13} /> Open Full Preview <CaretRight size={11} />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
};

function FieldGroup({ label, hint, children, className }) {
  return (
    <div className={className}>
      <label className="text-xs font-medium text-stone-600 mb-1 block">{label}</label>
      {hint && <p className="text-[10px] text-stone-400 mb-1.5">{hint}</p>}
      {children}
    </div>
  );
}

function ColorField({ label, value, defaultVal, onChange, testId }) {
  return (
    <div>
      <label className="text-xs font-medium text-stone-600 mb-1 block">{label}</label>
      <div className="flex items-center gap-2">
        <input
          type="color"
          value={value || defaultVal}
          onChange={e => onChange(e.target.value)}
          className="w-9 h-9 rounded-lg border border-stone-300 cursor-pointer"
          data-testid={testId}
        />
        <Input
          value={value || ""}
          onChange={e => onChange(e.target.value)}
          placeholder={`Default: ${defaultVal}`}
          className="flex-1 text-xs font-mono"
          data-testid={`${testId}-input`}
        />
        {value && (
          <button onClick={() => onChange("")} className="text-stone-400 hover:text-stone-600 text-xs" data-testid={`${testId}-clear`}>Clear</button>
        )}
      </div>
    </div>
  );
}

export { TemplateCustomizer };
