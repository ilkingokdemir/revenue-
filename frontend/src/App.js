import { useEffect, useState, useCallback } from "react";
import "@/App.css";
import axios from "axios";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import {
  Star,
  CheckCircle,
  WarningCircle,
  Sparkle,
  ChatText,
  FunnelSimple,
  ArrowsClockwise,
  Buildings,
  Quotes,
  PaperPlaneTilt,
  PencilSimple,
  Bell,
  X,
  EnvelopeSimple,
  TestTube,
  FileText,
  Plus,
  Trash,
  Copy,
  Tag
} from "@phosphor-icons/react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Platform configuration with colors
const PLATFORMS = {
  "booking.com": { name: "Booking.com", color: "#003580", bg: "bg-[#003580]" },
  "airbnb": { name: "Airbnb", color: "#FF5A5F", bg: "bg-[#FF5A5F]" },
  "expedia": { name: "Expedia", color: "#FFCC00", bg: "bg-[#FFCC00]", textDark: true },
  "tripadvisor": { name: "TripAdvisor", color: "#00AF87", bg: "bg-[#00AF87]" },
  "google": { name: "Google", color: "#4285F4", bg: "bg-[#4285F4]" },
  "trip.com": { name: "Trip.com", color: "#287DFA", bg: "bg-[#287DFA]" }
};

// Template categories
const TEMPLATE_CATEGORIES = {
  positive: { name: "Positive", color: "bg-[#5A6B50]", icon: "👍" },
  negative: { name: "Negative", color: "bg-[#C05A44]", icon: "👎" },
  neutral: { name: "Neutral", color: "bg-[#57534E]", icon: "➖" },
  complaint: { name: "Complaint", color: "bg-[#D4A373]", icon: "⚠️" },
  praise: { name: "Praise", color: "bg-[#3E5245]", icon: "⭐" }
};

// Star Rating Component
const StarRating = ({ rating, size = 16 }) => {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <Star
          key={star}
          size={size}
          weight={star <= rating ? "fill" : "regular"}
          className={star <= rating ? "text-[#D4A373]" : "text-[#E7E5E4]"}
        />
      ))}
    </div>
  );
};

// Platform Badge Component
const PlatformBadge = ({ platform }) => {
  const config = PLATFORMS[platform] || { name: platform, bg: "bg-gray-500" };
  return (
    <span
      className={`${config.bg} ${config.textDark ? "text-[#1C1917]" : "text-white"} px-2 py-0.5 rounded text-xs font-medium`}
      data-testid={`platform-badge-${platform}`}
    >
      {config.name}
    </span>
  );
};

// Stats Card Component
const StatsCard = ({ icon: Icon, label, value, subtext }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    className="border border-stone-200 rounded-md bg-white p-6 flex flex-col gap-2"
    data-testid={`stats-card-${label.toLowerCase().replace(/\s/g, '-')}`}
  >
    <div className="flex items-center gap-2 text-[#57534E]">
      <Icon size={18} weight="regular" />
      <span className="text-xs tracking-[0.2em] uppercase font-medium">{label}</span>
    </div>
    <div className="text-3xl font-semibold text-[#1C1917] font-['Work_Sans']">{value}</div>
    {subtext && <div className="text-sm text-[#57534E]">{subtext}</div>}
  </motion.div>
);

// Review Card Component
const ReviewCard = ({ review, isSelected, onClick }) => {
  const isPending = review.response_status === "pending";
  
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      onClick={onClick}
      className={`p-4 border-b border-stone-100 hover:bg-[#FAF9F6] cursor-pointer transition-colors group ${
        isSelected ? "bg-[#E8EDE7] border-l-[3px] border-l-[#3E5245]" : ""
      }`}
      data-testid={`review-card-${review.id}`}
    >
      <div className="flex items-start gap-3">
        <img
          src={review.guest_avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(review.guest_name)}&background=E8EDE7&color=3E5245`}
          alt={review.guest_name}
          className="w-10 h-10 rounded-full object-cover"
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 mb-1">
            <span className="font-medium text-[#1C1917] truncate">{review.guest_name}</span>
            <PlatformBadge platform={review.platform} />
          </div>
          <StarRating rating={review.rating} size={14} />
          <p className="text-sm text-[#57534E] line-clamp-2 mt-2">{review.review_text}</p>
          <div className="flex items-center justify-between mt-2">
            <span className="text-xs text-[#57534E]">
              {new Date(review.review_date).toLocaleDateString()}
            </span>
            {isPending ? (
              <span className="flex items-center gap-1 text-xs text-[#D4A373]">
                <WarningCircle size={14} weight="fill" />
                Pending
              </span>
            ) : (
              <span className="flex items-center gap-1 text-xs text-[#5A6B50]">
                <CheckCircle size={14} weight="fill" />
                Responded
              </span>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
};

// AI Response Panel Component
const AIResponsePanel = ({ review, onResponseSubmit, isLoading, templateText, onTemplateApplied }) => {
  const [responseText, setResponseText] = useState("");
  const [tone, setTone] = useState("professional");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    if (review?.response_text) {
      setResponseText(review.response_text);
    } else {
      setResponseText("");
    }
  }, [review]);

  // Handle template application
  useEffect(() => {
    if (templateText && review) {
      // Replace {guest_name} placeholder with actual guest name
      const processedText = templateText.replace(/\{guest_name\}/g, review.guest_name);
      setResponseText(processedText);
      if (onTemplateApplied) onTemplateApplied();
    }
  }, [templateText, review, onTemplateApplied]);

  const generateAIResponse = async () => {
    if (!review) return;
    
    setIsGenerating(true);
    try {
      const response = await axios.post(`${API}/reviews/generate-ai-response`, {
        review_id: review.id,
        tone: tone
      });
      
      // Typewriter effect
      const text = response.data.generated_text;
      let currentIndex = 0;
      setResponseText("");
      
      const typeWriter = setInterval(() => {
        if (currentIndex < text.length) {
          setResponseText(text.substring(0, currentIndex + 1));
          currentIndex++;
        } else {
          clearInterval(typeWriter);
          setIsGenerating(false);
        }
      }, 15);
      
      toast.success("AI response generated!");
    } catch (error) {
      console.error("Error generating AI response:", error);
      toast.error("Failed to generate AI response");
      setIsGenerating(false);
    }
  };

  const handleSubmit = async () => {
    if (!responseText.trim() || !review) return;
    
    try {
      await onResponseSubmit(review.id, responseText);
      toast.success("Response published successfully!");
      setIsEditing(false);
    } catch (error) {
      console.error("Error submitting response:", error);
      toast.error("Failed to publish response");
    }
  };

  if (!review) {
    return (
      <div className="flex-1 flex items-center justify-center text-[#57534E]" data-testid="no-review-selected">
        <div className="text-center">
          <ChatText size={48} className="mx-auto mb-4 opacity-50" />
          <p>Select a review to view details and respond</p>
        </div>
      </div>
    );
  }

  const isResponded = review.response_status === "responded";

  return (
    <div className="flex-1 flex flex-col" data-testid="ai-response-panel">
      {/* Review Details */}
      <div className="border-b border-stone-200 pb-6 mb-6">
        <div className="flex items-start gap-4">
          <img
            src={review.guest_avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(review.guest_name)}&background=E8EDE7&color=3E5245`}
            alt={review.guest_name}
            className="w-14 h-14 rounded-full object-cover"
          />
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <h3 className="text-xl font-medium text-[#1C1917] font-['Work_Sans']" data-testid="review-guest-name">
                {review.guest_name}
              </h3>
              <PlatformBadge platform={review.platform} />
              {isResponded ? (
                <Badge className="bg-[#5A6B50] text-white border-0">
                  <CheckCircle size={14} className="mr-1" weight="fill" />
                  Responded
                </Badge>
              ) : (
                <Badge className="bg-[#D4A373] text-white border-0">
                  <WarningCircle size={14} className="mr-1" weight="fill" />
                  Pending
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-4 text-sm text-[#57534E]">
              <StarRating rating={review.rating} />
              <span>{review.room_type}</span>
              <span>Stayed: {review.stay_date}</span>
            </div>
          </div>
        </div>
        
        <div className="mt-4 bg-[#FAF9F6] rounded-md p-4 relative" data-testid="review-text-container">
          <Quotes size={24} className="absolute top-2 left-2 text-[#E7E5E4]" weight="fill" />
          <p className="text-[#1C1917] leading-relaxed pl-6" data-testid="review-text">
            {review.review_text}
          </p>
        </div>
      </div>

      {/* AI Response Generator */}
      <div className="bg-[#E8EDE7] border border-[#D5DDD3] rounded-md p-6 relative overflow-hidden" data-testid="ai-generator-panel">
        {/* Texture overlay */}
        <div 
          className="absolute inset-0 ai-texture-overlay pointer-events-none"
          style={{
            backgroundImage: "url('https://static.prod-images.emergentagent.com/jobs/f284f94c-059d-4721-a5db-def78e330cac/images/06790bb25ee93b714799620c98d82862ea6db3df67429246c55c3ae00c5536b8.png')",
            backgroundSize: "cover",
            opacity: 0.12
          }}
        />
        
        <div className="relative z-10">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Sparkle size={20} className="text-[#3E5245]" weight="fill" />
              <span className="text-sm font-medium text-[#1C1917]">AI Response Assistant</span>
            </div>
            
            {!isResponded && (
              <div className="flex items-center gap-3">
                <Select value={tone} onValueChange={setTone} data-testid="tone-select">
                  <SelectTrigger className="w-[140px] bg-white border-stone-200">
                    <SelectValue placeholder="Select tone" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="professional">Professional</SelectItem>
                    <SelectItem value="friendly">Friendly</SelectItem>
                    <SelectItem value="apologetic">Apologetic</SelectItem>
                  </SelectContent>
                </Select>
                
                <button
                  onClick={generateAIResponse}
                  disabled={isGenerating || isLoading}
                  className="bg-[#3E5245] text-white px-4 py-2 rounded-md hover:bg-[#2A3B30] transition-colors disabled:opacity-50 flex items-center gap-2"
                  data-testid="generate-ai-btn"
                >
                  {isGenerating ? (
                    <>
                      <ArrowsClockwise size={16} className="animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <Sparkle size={16} weight="fill" />
                      Generate AI Reply
                    </>
                  )}
                </button>
              </div>
            )}
          </div>

          {isGenerating && (
            <div className="ai-shimmer h-2 rounded-full mb-4" />
          )}

          <div className="relative">
            <Textarea
              value={responseText}
              onChange={(e) => setResponseText(e.target.value)}
              placeholder={isResponded ? "Response already submitted" : "AI-generated response will appear here. You can edit it before publishing..."}
              className={`min-h-[180px] bg-white border-stone-200 resize-none ${isGenerating ? "cursor-blink" : ""}`}
              disabled={isResponded && !isEditing}
              data-testid="response-textarea"
            />
            
            {isResponded && !isEditing && (
              <button
                onClick={() => setIsEditing(true)}
                className="absolute top-2 right-2 p-2 bg-white rounded-md border border-stone-200 hover:bg-stone-50 transition-colors"
                data-testid="edit-response-btn"
              >
                <PencilSimple size={16} className="text-[#57534E]" />
              </button>
            )}
          </div>

          <div className="flex items-center justify-between mt-4">
            <p className="text-xs text-[#57534E]">
              {isResponded ? "This review has been responded to." : "Edit the AI response before publishing to the platform."}
            </p>
            
            {(!isResponded || isEditing) && (
              <div className="flex items-center gap-2">
                {isEditing && (
                  <button
                    onClick={() => {
                      setIsEditing(false);
                      setResponseText(review.response_text || "");
                    }}
                    className="bg-white border border-stone-200 text-[#1C1917] px-4 py-2 rounded-md hover:bg-stone-50 transition-colors"
                    data-testid="cancel-edit-btn"
                  >
                    Cancel
                  </button>
                )}
                <button
                  onClick={handleSubmit}
                  disabled={!responseText.trim() || isLoading || isGenerating}
                  className="bg-[#3E5245] text-white px-4 py-2 rounded-md hover:bg-[#2A3B30] transition-colors disabled:opacity-50 flex items-center gap-2"
                  data-testid="publish-response-btn"
                >
                  <PaperPlaneTilt size={16} weight="fill" />
                  {isEditing ? "Update Response" : "Publish Response"}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Info Banner */}
      <div className="mt-4 p-3 bg-[#FAF9F6] border border-[#E7E5E4] rounded-md">
        <p className="text-xs text-[#57534E] flex items-center gap-2">
          <span className="inline-block w-2 h-2 rounded-full bg-[#D4A373]"></span>
          <strong>DEMO MODE:</strong> Reviews are mocked for demonstration. In production, responses will sync to {PLATFORMS[review.platform]?.name || review.platform}.
        </p>
      </div>
    </div>
  );
};

// Notification Settings Component
const NotificationSettings = ({ isOpen, onClose }) => {
  const [settings, setSettings] = useState({
    email: "",
    notify_negative_reviews: true,
    negative_threshold: 2,
    enabled: false
  });
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetchSettings();
    }
  }, [isOpen]);

  const fetchSettings = async () => {
    try {
      const response = await axios.get(`${API}/notifications/settings`);
      setSettings(response.data);
    } catch (error) {
      console.error("Error fetching notification settings:", error);
    }
  };

  const saveSettings = async () => {
    setIsSaving(true);
    try {
      await axios.put(`${API}/notifications/settings`, settings);
      toast.success("Notification settings saved!");
    } catch (error) {
      console.error("Error saving settings:", error);
      toast.error("Failed to save settings");
    } finally {
      setIsSaving(false);
    }
  };

  const sendTestNotification = async () => {
    setIsTesting(true);
    try {
      await axios.post(`${API}/notifications/test`);
      toast.success("Test notification sent! Check your email.");
    } catch (error) {
      console.error("Error sending test notification:", error);
      toast.error(error.response?.data?.detail || "Failed to send test notification");
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <DialogContent className="sm:max-w-[500px]" data-testid="notification-settings-dialog">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2 text-[#1C1917] font-['Work_Sans']">
          <Bell size={20} weight="fill" className="text-[#3E5245]" />
          Email Notifications
        </DialogTitle>
      </DialogHeader>
      
      <div className="space-y-6 py-4">
        {/* Enable/Disable Toggle */}
        <div className="flex items-center justify-between p-4 bg-[#FAF9F6] rounded-md border border-[#E7E5E4]">
          <div>
            <p className="font-medium text-[#1C1917]">Enable Notifications</p>
            <p className="text-sm text-[#57534E]">Receive alerts for negative reviews</p>
          </div>
          <Switch
            checked={settings.enabled}
            onCheckedChange={(checked) => setSettings(prev => ({ ...prev, enabled: checked }))}
            data-testid="notification-enable-switch"
          />
        </div>

        {/* Email Address */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-[#1C1917] flex items-center gap-2">
            <EnvelopeSimple size={16} className="text-[#57534E]" />
            Notification Email
          </label>
          <Input
            type="email"
            placeholder="hotel@example.com"
            value={settings.email}
            onChange={(e) => setSettings(prev => ({ ...prev, email: e.target.value }))}
            className="border-stone-200"
            data-testid="notification-email-input"
          />
          <p className="text-xs text-[#57534E]">Email address to receive negative review alerts</p>
        </div>

        {/* Rating Threshold */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-[#1C1917]">Alert Threshold</label>
          <Select
            value={String(settings.negative_threshold)}
            onValueChange={(value) => setSettings(prev => ({ ...prev, negative_threshold: parseInt(value) }))}
            data-testid="threshold-select"
          >
            <SelectTrigger className="border-stone-200">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">1 star only</SelectItem>
              <SelectItem value="2">1-2 stars (recommended)</SelectItem>
              <SelectItem value="3">1-3 stars</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-[#57534E]">Send alerts when reviews are at or below this rating</p>
        </div>

        {/* Info Banner */}
        <div className="p-3 bg-[#E8EDE7] border border-[#D5DDD3] rounded-md">
          <p className="text-xs text-[#57534E]">
            <strong>Note:</strong> In demo mode, notifications are logged but not actually sent. 
            Configure a valid Resend API key in production to enable real email delivery.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-between pt-4 border-t border-stone-200">
          <button
            onClick={sendTestNotification}
            disabled={!settings.enabled || !settings.email || isTesting}
            className="bg-white border border-stone-200 text-[#1C1917] px-4 py-2 rounded-md hover:bg-stone-50 transition-colors disabled:opacity-50 flex items-center gap-2"
            data-testid="test-notification-btn"
          >
            <TestTube size={16} />
            {isTesting ? "Sending..." : "Send Test"}
          </button>
          
          <button
            onClick={saveSettings}
            disabled={isSaving}
            className="bg-[#3E5245] text-white px-4 py-2 rounded-md hover:bg-[#2A3B30] transition-colors disabled:opacity-50 flex items-center gap-2"
            data-testid="save-notification-settings-btn"
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
    </DialogContent>
  );
};

// Templates Manager Component
const TemplatesManager = ({ isOpen, onClose, onSelectTemplate }) => {
  const [templates, setTemplates] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [formData, setFormData] = useState({
    name: "",
    category: "positive",
    content: "",
    tone: "professional"
  });

  const fetchTemplates = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await axios.get(`${API}/templates`);
      setTemplates(response.data);
    } catch (error) {
      console.error("Error fetching templates:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const seedTemplates = useCallback(async () => {
    try {
      const response = await axios.post(`${API}/templates/seed`);
      if (response.data.seeded) {
        toast.success("Default templates loaded!");
        await fetchTemplates();
      }
    } catch (error) {
      console.error("Error seeding templates:", error);
    }
  }, [fetchTemplates]);

  useEffect(() => {
    if (isOpen) {
      seedTemplates();
      fetchTemplates();
    }
  }, [isOpen, fetchTemplates, seedTemplates]);

  const handleCreateOrUpdate = async () => {
    try {
      if (editingTemplate) {
        await axios.put(`${API}/templates/${editingTemplate.id}`, formData);
        toast.success("Template updated!");
      } else {
        await axios.post(`${API}/templates`, formData);
        toast.success("Template created!");
      }
      setShowCreateForm(false);
      setEditingTemplate(null);
      setFormData({ name: "", category: "positive", content: "", tone: "professional" });
      await fetchTemplates();
    } catch (error) {
      console.error("Error saving template:", error);
      toast.error("Failed to save template");
    }
  };

  const handleDelete = async (templateId) => {
    if (!window.confirm("Are you sure you want to delete this template?")) return;
    try {
      await axios.delete(`${API}/templates/${templateId}`);
      toast.success("Template deleted!");
      await fetchTemplates();
    } catch (error) {
      console.error("Error deleting template:", error);
      toast.error("Failed to delete template");
    }
  };

  const handleUseTemplate = async (template) => {
    try {
      await axios.post(`${API}/templates/${template.id}/use`);
      onSelectTemplate(template.content);
      onClose();
      toast.success("Template applied!");
    } catch (error) {
      console.error("Error using template:", error);
    }
  };

  const handleEdit = (template) => {
    setEditingTemplate(template);
    setFormData({
      name: template.name,
      category: template.category,
      content: template.content,
      tone: template.tone
    });
    setShowCreateForm(true);
  };

  const filteredTemplates = selectedCategory === "all" 
    ? templates 
    : templates.filter(t => t.category === selectedCategory);

  return (
    <DialogContent className="sm:max-w-[700px] max-h-[85vh]" data-testid="templates-dialog">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2 text-[#1C1917] font-['Work_Sans']">
          <FileText size={20} weight="fill" className="text-[#3E5245]" />
          Response Templates
        </DialogTitle>
      </DialogHeader>

      <Tabs defaultValue="browse" className="w-full">
        <TabsList className="grid w-full grid-cols-2 mb-4">
          <TabsTrigger value="browse" data-testid="templates-browse-tab">Browse Templates</TabsTrigger>
          <TabsTrigger 
            value="create" 
            onClick={() => {
              setShowCreateForm(true);
              setEditingTemplate(null);
              setFormData({ name: "", category: "positive", content: "", tone: "professional" });
            }}
            data-testid="templates-create-tab"
          >
            {editingTemplate ? "Edit Template" : "Create New"}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="browse" className="space-y-4">
          {/* Category Filter */}
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => setSelectedCategory("all")}
              className={`px-3 py-1 rounded-full text-sm transition-colors ${
                selectedCategory === "all" 
                  ? "bg-[#3E5245] text-white" 
                  : "bg-[#E8EDE7] text-[#1C1917] hover:bg-[#D5DDD3]"
              }`}
              data-testid="category-filter-all"
            >
              All
            </button>
            {Object.entries(TEMPLATE_CATEGORIES).map(([key, cat]) => (
              <button
                key={key}
                onClick={() => setSelectedCategory(key)}
                className={`px-3 py-1 rounded-full text-sm transition-colors flex items-center gap-1 ${
                  selectedCategory === key 
                    ? `${cat.color} text-white` 
                    : "bg-[#E8EDE7] text-[#1C1917] hover:bg-[#D5DDD3]"
                }`}
                data-testid={`category-filter-${key}`}
              >
                {cat.name}
              </button>
            ))}
          </div>

          {/* Templates List */}
          <ScrollArea className="h-[400px] pr-4">
            {isLoading ? (
              <div className="flex items-center justify-center h-32">
                <ArrowsClockwise size={24} className="animate-spin text-[#57534E]" />
              </div>
            ) : filteredTemplates.length === 0 ? (
              <div className="text-center py-8 text-[#57534E]">
                <FileText size={32} className="mx-auto mb-2 opacity-50" />
                <p>No templates found</p>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredTemplates.map((template) => (
                  <motion.div
                    key={template.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="border border-stone-200 rounded-md p-4 bg-white hover:shadow-sm transition-shadow"
                    data-testid={`template-card-${template.id}`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <h4 className="font-medium text-[#1C1917]">{template.name}</h4>
                        <div className="flex items-center gap-2 mt-1">
                          <span className={`${TEMPLATE_CATEGORIES[template.category]?.color || "bg-gray-500"} text-white px-2 py-0.5 rounded text-xs`}>
                            {TEMPLATE_CATEGORIES[template.category]?.name || template.category}
                          </span>
                          <span className="text-xs text-[#57534E]">
                            <Tag size={12} className="inline mr-1" />
                            {template.tone}
                          </span>
                          <span className="text-xs text-[#57534E]">
                            Used {template.usage_count || 0} times
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleEdit(template)}
                          className="p-2 hover:bg-stone-100 rounded-md transition-colors"
                          title="Edit"
                          data-testid={`edit-template-${template.id}`}
                        >
                          <PencilSimple size={16} className="text-[#57534E]" />
                        </button>
                        <button
                          onClick={() => handleDelete(template.id)}
                          className="p-2 hover:bg-red-50 rounded-md transition-colors"
                          title="Delete"
                          data-testid={`delete-template-${template.id}`}
                        >
                          <Trash size={16} className="text-[#C05A44]" />
                        </button>
                      </div>
                    </div>
                    <p className="text-sm text-[#57534E] line-clamp-3 mb-3">
                      {template.content}
                    </p>
                    <button
                      onClick={() => handleUseTemplate(template)}
                      className="bg-[#3E5245] text-white px-3 py-1.5 rounded-md text-sm hover:bg-[#2A3B30] transition-colors flex items-center gap-1"
                      data-testid={`use-template-${template.id}`}
                    >
                      <Copy size={14} />
                      Use This Template
                    </button>
                  </motion.div>
                ))}
              </div>
            )}
          </ScrollArea>
        </TabsContent>

        <TabsContent value="create" className="space-y-4">
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-[#1C1917] block mb-1">Template Name</label>
              <Input
                placeholder="e.g., Thank You - Great Stay"
                value={formData.name}
                onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                className="border-stone-200"
                data-testid="template-name-input"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-[#1C1917] block mb-1">Category</label>
                <Select
                  value={formData.category}
                  onValueChange={(value) => setFormData(prev => ({ ...prev, category: value }))}
                  data-testid="template-category-select"
                >
                  <SelectTrigger className="border-stone-200">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(TEMPLATE_CATEGORIES).map(([key, cat]) => (
                      <SelectItem key={key} value={key}>{cat.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm font-medium text-[#1C1917] block mb-1">Tone</label>
                <Select
                  value={formData.tone}
                  onValueChange={(value) => setFormData(prev => ({ ...prev, tone: value }))}
                  data-testid="template-tone-select"
                >
                  <SelectTrigger className="border-stone-200">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="professional">Professional</SelectItem>
                    <SelectItem value="friendly">Friendly</SelectItem>
                    <SelectItem value="apologetic">Apologetic</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <label className="text-sm font-medium text-[#1C1917] block mb-1">
                Template Content
                <span className="text-xs text-[#57534E] ml-2">Use {"{guest_name}"} as placeholder</span>
              </label>
              <Textarea
                placeholder="Dear {guest_name},&#10;&#10;Thank you for your feedback..."
                value={formData.content}
                onChange={(e) => setFormData(prev => ({ ...prev, content: e.target.value }))}
                className="min-h-[200px] border-stone-200"
                data-testid="template-content-textarea"
              />
            </div>

            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowCreateForm(false);
                  setEditingTemplate(null);
                  setFormData({ name: "", category: "positive", content: "", tone: "professional" });
                }}
                className="bg-white border border-stone-200 text-[#1C1917] px-4 py-2 rounded-md hover:bg-stone-50 transition-colors"
                data-testid="cancel-template-btn"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateOrUpdate}
                disabled={!formData.name || !formData.content}
                className="bg-[#3E5245] text-white px-4 py-2 rounded-md hover:bg-[#2A3B30] transition-colors disabled:opacity-50 flex items-center gap-2"
                data-testid="save-template-btn"
              >
                <Plus size={16} />
                {editingTemplate ? "Update Template" : "Create Template"}
              </button>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </DialogContent>
  );
};

// Main Dashboard Component
const Dashboard = () => {
  const [reviews, setReviews] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedReview, setSelectedReview] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showNotificationSettings, setShowNotificationSettings] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [templateTextToApply, setTemplateTextToApply] = useState(null);
  const [filters, setFilters] = useState({
    platform: "all",
    status: "all"
  });

  const handleApplyTemplate = (templateContent) => {
    setTemplateTextToApply(templateContent);
  };

  const fetchReviews = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (filters.platform !== "all") params.append("platform", filters.platform);
      if (filters.status !== "all") params.append("status", filters.status);
      
      const response = await axios.get(`${API}/reviews?${params.toString()}`);
      setReviews(response.data);
    } catch (error) {
      console.error("Error fetching reviews:", error);
      toast.error("Failed to load reviews");
    }
  }, [filters]);

  const fetchStats = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/reviews/stats/summary`);
      setStats(response.data);
    } catch (error) {
      console.error("Error fetching stats:", error);
    }
  }, []);

  const seedReviews = useCallback(async () => {
    try {
      const response = await axios.post(`${API}/reviews/seed`);
      if (response.data.seeded) {
        toast.success("Demo reviews loaded!");
        await fetchReviews();
        await fetchStats();
      }
    } catch (error) {
      console.error("Error seeding reviews:", error);
    }
  }, [fetchReviews, fetchStats]);

  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      await seedReviews();
      await fetchReviews();
      await fetchStats();
      setIsLoading(false);
    };
    init();
  }, []);

  useEffect(() => {
    fetchReviews();
  }, [filters, fetchReviews]);

  const handleResponseSubmit = async (reviewId, responseText) => {
    setIsLoading(true);
    try {
      await axios.put(`${API}/reviews/${reviewId}/respond`, {
        response_text: responseText
      });
      await fetchReviews();
      await fetchStats();
      
      // Update selected review
      const updatedReview = reviews.find(r => r.id === reviewId);
      if (updatedReview) {
        setSelectedReview({
          ...updatedReview,
          response_text: responseText,
          response_status: "responded"
        });
      }
    } catch (error) {
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FAF9F6]" data-testid="review-dashboard">
      {/* Header */}
      <header className="bg-white border-b border-stone-200 px-6 py-4" data-testid="dashboard-header">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-[#3E5245] rounded-md flex items-center justify-center">
              <Buildings size={24} className="text-white" weight="fill" />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-[#1C1917] font-['Work_Sans']">Review Hub</h1>
              <p className="text-sm text-[#57534E]">Manage all your guest reviews in one place</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Dialog open={showTemplates} onOpenChange={setShowTemplates}>
              <DialogTrigger asChild>
                <button
                  className="bg-white border border-stone-200 text-[#1C1917] px-4 py-2 rounded-md hover:bg-stone-50 transition-colors flex items-center gap-2"
                  data-testid="templates-btn"
                >
                  <FileText size={18} />
                  Templates
                </button>
              </DialogTrigger>
              <TemplatesManager 
                isOpen={showTemplates} 
                onClose={() => setShowTemplates(false)}
                onSelectTemplate={handleApplyTemplate}
              />
            </Dialog>
            <Dialog open={showNotificationSettings} onOpenChange={setShowNotificationSettings}>
              <DialogTrigger asChild>
                <button
                  className="bg-white border border-stone-200 text-[#1C1917] px-4 py-2 rounded-md hover:bg-stone-50 transition-colors flex items-center gap-2"
                  data-testid="notification-settings-btn"
                >
                  <Bell size={18} />
                  Alerts
                </button>
              </DialogTrigger>
              <NotificationSettings 
                isOpen={showNotificationSettings} 
                onClose={() => setShowNotificationSettings(false)} 
              />
            </Dialog>
            <button
              onClick={() => {
                fetchReviews();
                fetchStats();
                toast.success("Reviews refreshed!");
              }}
              className="bg-white border border-stone-200 text-[#1C1917] px-4 py-2 rounded-md hover:bg-stone-50 transition-colors flex items-center gap-2"
              data-testid="refresh-btn"
            >
              <ArrowsClockwise size={18} />
              Refresh
            </button>
          </div>
        </div>
      </header>

      <div className="p-6 lg:p-8">
        {/* Stats Row */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <StatsCard
            icon={ChatText}
            label="Total Reviews"
            value={stats?.total_reviews || 0}
            subtext={`Across ${Object.keys(stats?.by_platform || {}).length} platforms`}
          />
          <StatsCard
            icon={Star}
            label="Average Rating"
            value={stats?.average_rating ? `${stats.average_rating}/5` : "N/A"}
            subtext={<StarRating rating={Math.round(stats?.average_rating || 0)} size={12} />}
          />
          <StatsCard
            icon={CheckCircle}
            label="Response Rate"
            value={`${stats?.response_rate || 0}%`}
            subtext={`${stats?.responded || 0} of ${stats?.total_reviews || 0} responded`}
          />
          <StatsCard
            icon={WarningCircle}
            label="Pending"
            value={stats?.pending || 0}
            subtext="Reviews awaiting response"
          />
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
          {/* Filters & Review List */}
          <div className="md:col-span-4 bg-white border border-stone-200 rounded-md overflow-hidden" data-testid="review-list-panel">
            {/* Filters */}
            <div className="p-4 border-b border-stone-200 bg-[#FAF9F6]">
              <div className="flex items-center gap-2 mb-3">
                <FunnelSimple size={18} className="text-[#57534E]" />
                <span className="text-sm font-medium text-[#1C1917]">Filters</span>
              </div>
              <div className="flex gap-2">
                <Select
                  value={filters.platform}
                  onValueChange={(value) => setFilters(prev => ({ ...prev, platform: value }))}
                  data-testid="platform-filter"
                >
                  <SelectTrigger className="flex-1 bg-white border-stone-200">
                    <SelectValue placeholder="Platform" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Platforms</SelectItem>
                    {Object.entries(PLATFORMS).map(([key, config]) => (
                      <SelectItem key={key} value={key}>{config.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                
                <Select
                  value={filters.status}
                  onValueChange={(value) => setFilters(prev => ({ ...prev, status: value }))}
                  data-testid="status-filter"
                >
                  <SelectTrigger className="flex-1 bg-white border-stone-200">
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Status</SelectItem>
                    <SelectItem value="pending">Pending</SelectItem>
                    <SelectItem value="responded">Responded</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Review List */}
            <ScrollArea className="h-[calc(100vh-380px)]" data-testid="review-list">
              {isLoading ? (
                <div className="p-8 text-center text-[#57534E]">
                  <ArrowsClockwise size={32} className="mx-auto mb-2 animate-spin" />
                  <p>Loading reviews...</p>
                </div>
              ) : reviews.length === 0 ? (
                <div className="p-8 text-center text-[#57534E]">
                  <ChatText size={32} className="mx-auto mb-2 opacity-50" />
                  <p>No reviews found</p>
                </div>
              ) : (
                <AnimatePresence>
                  {reviews.map((review, index) => (
                    <ReviewCard
                      key={review.id}
                      review={review}
                      isSelected={selectedReview?.id === review.id}
                      onClick={() => setSelectedReview(review)}
                    />
                  ))}
                </AnimatePresence>
              )}
            </ScrollArea>
          </div>

          {/* Review Detail & Response Editor */}
          <div className="md:col-span-8 bg-white border border-stone-200 rounded-md p-8 flex flex-col" data-testid="review-detail-panel">
            <AIResponsePanel
              review={selectedReview}
              onResponseSubmit={handleResponseSubmit}
              isLoading={isLoading}
              templateText={templateTextToApply}
              onTemplateApplied={() => setTemplateTextToApply(null)}
            />
          </div>
        </div>
      </div>

      <Toaster position="top-right" richColors />
    </div>
  );
};

function App() {
  return (
    <div className="App">
      <Dashboard />
    </div>
  );
}

export default App;
