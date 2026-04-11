import { useState } from "react";
import {
  Buildings, Heart, Sparkle, Medal, Eye, Copy, CheckCircle,
  Crown, TreePalm, Briefcase, Baby, Lightning,
} from "@phosphor-icons/react";
import { toast } from "sonner";
import { TEMPLATE_LIST, PLATFORM_GROUPS, getTemplate } from "../../templates/templateConfig";

const platformStyles = {
  "Booking.com": { icon: Buildings, color: "#003B95", bg: "#EBF2FF" },
  "Airbnb": { icon: Heart, color: "#FF385C", bg: "#FFF0F3" },
  "Expedia": { icon: Sparkle, color: "#1D3C6E", bg: "#EDF0F5" },
  "Hotels.com": { icon: Medal, color: "#D32F2F", bg: "#FFEBEE" },
};

const TemplateGallery = ({ properties }) => {
  const [selectedTemplate, setSelectedTemplate] = useState("booking-classic");
  const [selectedProperty, setSelectedProperty] = useState(properties?.[0]?.id || "aldgate-flats");
  const [activeGroup, setActiveGroup] = useState("all");

  const bookingUrl = (templateId) => `${window.location.origin}/book?property=${selectedProperty}&template=${templateId}`;

  const filteredTemplates = activeGroup === "all"
    ? TEMPLATE_LIST
    : TEMPLATE_LIST.filter(t => {
        const group = PLATFORM_GROUPS.find(g => g.templates.includes(t.id));
        return group?.name.includes(activeGroup);
      });

  return (
    <div className="p-5" data-testid="template-gallery">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-stone-800" data-testid="template-gallery-title">Website Templates</h2>
          <p className="text-sm text-stone-500 mt-0.5">Choose a template for your hotel's booking page — 10 professional designs</p>
        </div>
      </div>

      {/* Active template URL */}
      <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 mb-5">
        <div className="flex items-center gap-2 mb-2">
          <Lightning size={16} className="text-emerald-600" />
          <span className="text-xs font-medium text-emerald-800">Active booking page:</span>
          <select
            value={selectedProperty}
            onChange={(e) => setSelectedProperty(e.target.value)}
            className="text-xs border border-emerald-300 rounded-lg px-2 py-1 bg-white text-emerald-800 font-medium ml-auto"
            data-testid="template-property-select"
          >
            {properties?.filter(p => p.id !== "default").map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <code className="text-xs text-emerald-700 font-mono flex-1 break-all" data-testid="active-template-url">{bookingUrl(selectedTemplate)}</code>
          <button
            onClick={() => { navigator.clipboard.writeText(bookingUrl(selectedTemplate)); toast.success("URL copied!"); }}
            className="p-1.5 text-emerald-600 hover:text-emerald-800"
            data-testid="copy-template-url"
          >
            <Copy size={14} />
          </button>
          <a href={bookingUrl(selectedTemplate)} target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1 px-3 py-1.5 bg-emerald-700 text-white rounded-lg text-xs font-medium hover:bg-emerald-800"
            data-testid="preview-template">
            <Eye size={13} /> Preview
          </a>
        </div>
      </div>

      {/* Platform Filter Tabs */}
      <div className="flex items-center gap-1 mb-5 overflow-x-auto pb-1">
        <button
          onClick={() => setActiveGroup("all")}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
            activeGroup === "all" ? "bg-stone-800 text-white" : "bg-stone-100 text-stone-600 hover:bg-stone-200"
          }`}
          data-testid="filter-all"
        >
          All Templates (10)
        </button>
        {PLATFORM_GROUPS.map((group) => {
          const style = platformStyles[group.name.replace(" Style", "")];
          const Icon = style?.icon || Buildings;
          return (
            <button
              key={group.name}
              onClick={() => setActiveGroup(group.name.replace(" Style", ""))}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors flex items-center gap-1.5 ${
                activeGroup === group.name.replace(" Style", "") ? "text-white" : "text-stone-600 hover:bg-stone-100"
              }`}
              style={activeGroup === group.name.replace(" Style", "") ? { background: style?.color } : { background: style?.bg }}
              data-testid={`filter-${group.name.toLowerCase().replace(/[^a-z]/g, "-")}`}
            >
              <Icon size={13} weight="fill" />
              {group.name} ({group.templates.length})
            </button>
          );
        })}
      </div>

      {/* Template Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="template-grid">
        {filteredTemplates.map((template) => {
          const style = platformStyles[template.platform] || {};
          const Icon = style.icon || Buildings;
          const isSelected = selectedTemplate === template.id;
          return (
            <div
              key={template.id}
              className={`border-2 rounded-xl overflow-hidden transition-all cursor-pointer ${
                isSelected ? "shadow-lg scale-[1.01]" : "hover:shadow-md border-stone-200"
              }`}
              style={{ borderColor: isSelected ? style.color : undefined }}
              onClick={() => setSelectedTemplate(template.id)}
              data-testid={`template-card-${template.id}`}
            >
              {/* Template Preview */}
              <div className="h-36 relative overflow-hidden" style={{ background: template.colors.heroBg || template.colors.headerBg }}>
                {/* Mini preview of the template */}
                <div className="absolute inset-0 flex flex-col">
                  {/* Mini header */}
                  <div className="h-7 flex items-center px-3 gap-1.5" style={{ background: template.colors.headerBg }}>
                    <div className="w-3 h-3 rounded" style={{ background: `${template.colors.headerText}40` }} />
                    <div className="h-2 w-16 rounded" style={{ background: `${template.colors.headerText}40` }} />
                  </div>
                  {/* Mini hero */}
                  <div className="flex-1 flex items-center justify-center relative">
                    {template.layout === "airbnb" ? (
                      <div className="w-4/5 grid grid-cols-3 gap-0.5 h-3/4 rounded overflow-hidden">
                        <div className="col-span-2 bg-white/20" />
                        <div className="space-y-0.5">
                          <div className="bg-white/20 flex-1 h-1/2" />
                          <div className="bg-white/20 flex-1 h-1/2" />
                        </div>
                      </div>
                    ) : (
                      <div className="text-center">
                        <div className="h-2 w-24 rounded mx-auto mb-1.5" style={{ background: `${template.colors.headerText}60` }} />
                        <div className="h-1.5 w-16 rounded mx-auto mb-3" style={{ background: `${template.colors.headerText}30` }} />
                        <div className="h-6 w-32 rounded mx-auto" style={{ background: template.colors.accent, opacity: 0.8 }} />
                      </div>
                    )}
                  </div>
                  {/* Mini room cards */}
                  <div className="h-10 px-3 pb-2 flex gap-1.5">
                    {[1,2,3].map(i => (
                      <div key={i} className="flex-1 bg-white/90 rounded-sm shadow-sm" />
                    ))}
                  </div>
                </div>
                {/* Selected badge */}
                {isSelected && (
                  <div className="absolute top-2 right-2 bg-white rounded-full p-1 shadow-md">
                    <CheckCircle size={18} weight="fill" style={{ color: style.color }} />
                  </div>
                )}
              </div>
              {/* Template Info */}
              <div className="p-4 bg-white">
                <div className="flex items-center gap-2 mb-1">
                  <Icon size={16} weight="fill" style={{ color: style.color }} />
                  <span className="text-xs font-medium px-2 py-0.5 rounded-full" style={{ background: style.bg, color: style.color }}>
                    {template.platform}
                  </span>
                </div>
                <h3 className="font-semibold text-stone-800 text-sm">{template.name}</h3>
                <p className="text-[10px] text-stone-500 mt-0.5 line-clamp-1">{template.description}</p>
                <div className="flex items-center gap-2 mt-2">
                  <a
                    href={bookingUrl(template.id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[10px] px-2 py-1 rounded-lg font-medium hover:opacity-80 transition-opacity text-white"
                    style={{ background: style.color }}
                    onClick={e => e.stopPropagation()}
                    data-testid={`preview-${template.id}`}
                  >
                    <Eye size={10} className="inline mr-1" />Preview
                  </a>
                  <button
                    onClick={e => { e.stopPropagation(); navigator.clipboard.writeText(bookingUrl(template.id)); toast.success("URL copied!"); }}
                    className="text-[10px] px-2 py-1 bg-stone-100 text-stone-600 rounded-lg font-medium hover:bg-stone-200"
                    data-testid={`copy-${template.id}`}
                  >
                    <Copy size={10} className="inline mr-1" />Copy URL
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export { TemplateGallery };
