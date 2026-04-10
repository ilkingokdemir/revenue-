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
  Tag,
  ChartBar,
  TrendUp,
  TrendDown,
  Lightning,
  Users,
  Trophy,
  Target,
  Brain,
  Fire,
  Smiley,
  SmileyMeh,
  SmileySad,
  CalendarBlank,
  PaperPlaneTilt as Send,
  Eye,
  PlugsConnected,
  Link,
  LinkBreak,
  CloudArrowUp,
  Database,
  Info,
  CaretRight,
  PaintBrush,
  Palette,
  Upload,
  Image
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
import { Progress } from "@/components/ui/progress";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Platform configuration with colors
const PLATFORMS = {
  "booking.com": { name: "Booking.com", color: "#003580", bg: "bg-[#003580]" },
  "airbnb": { name: "Airbnb", color: "#FF5A5F", bg: "bg-[#FF5A5F]" },
  "expedia": { name: "Expedia", color: "#FFCC00", bg: "bg-[#FFCC00]", textDark: true },
  "tripadvisor": { name: "TripAdvisor", color: "#00AF87", bg: "bg-[#00AF87]" },
  "google": { name: "Google", color: "#4285F4", bg: "bg-[#4285F4]" },
  "trip.com": { name: "Trip.com", color: "#287DFA", bg: "bg-[#287DFA]" },
  "agoda": { name: "Agoda", color: "#5542B6", bg: "bg-[#5542B6]" },
  "hotels.com": { name: "Hotels.com", color: "#D32F2F", bg: "bg-[#D32F2F]" },
  "yelp": { name: "Yelp", color: "#D32323", bg: "bg-[#D32323]" },
  "facebook": { name: "Facebook", color: "#1877F2", bg: "bg-[#1877F2]" },
  "makemytrip": { name: "MakeMyTrip", color: "#EE2E24", bg: "bg-[#EE2E24]" },
  "hrs": { name: "HRS", color: "#C4161C", bg: "bg-[#C4161C]" },
  "despegar": { name: "Despegar", color: "#6B2D8B", bg: "bg-[#6B2D8B]" },
  "hostelworld": { name: "Hostelworld", color: "#F47920", bg: "bg-[#F47920]" }
};

// Template categories
const TEMPLATE_CATEGORIES = {
  positive: { name: "Positive", color: "bg-[#5A6B50]", icon: "👍" },
  negative: { name: "Negative", color: "bg-[#C05A44]", icon: "👎" },
  neutral: { name: "Neutral", color: "bg-[#57534E]", icon: "➖" },
  complaint: { name: "Complaint", color: "bg-[#D4A373]", icon: "⚠️" },
  praise: { name: "Praise", color: "bg-[#3E5245]", icon: "⭐" }
};

// Sentiment colors
const SENTIMENT_COLORS = {
  positive: { bg: "bg-[#5A6B50]", text: "text-[#5A6B50]", light: "bg-[#E8EDE7]" },
  negative: { bg: "bg-[#C05A44]", text: "text-[#C05A44]", light: "bg-red-50" },
  neutral: { bg: "bg-[#57534E]", text: "text-[#57534E]", light: "bg-stone-100" },
  mixed: { bg: "bg-[#D4A373]", text: "text-[#D4A373]", light: "bg-amber-50" }
};

// Urgency colors
const URGENCY_COLORS = {
  low: "bg-[#5A6B50]",
  medium: "bg-[#D4A373]",
  high: "bg-orange-500",
  critical: "bg-[#C05A44]"
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
          className={star <= rating ? "text-amber-400 star-glow" : "text-stone-200"}
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
      className={`platform-pill ${config.bg} ${config.textDark ? "text-stone-900" : "text-white"}`}
      data-testid={`platform-badge-${platform}`}
    >
      {config.name}
    </span>
  );
};

// Stats Card Component
const StatsCard = ({ icon: Icon, label, value, subtext }) => (
  <motion.div
    initial={{ opacity: 0, y: 16 }}
    animate={{ opacity: 1, y: 0 }}
    className="border border-stone-200/80 rounded-xl bg-white p-5 flex flex-col gap-1.5 shadow-card card-hover relative overflow-hidden"
    data-testid={`stats-card-${label.toLowerCase().replace(/\s/g, '-')}`}
  >
    <div className="flex items-center justify-between">
      <span className="text-[11px] tracking-[0.15em] uppercase font-semibold text-stone-400">{label}</span>
      <div className="w-8 h-8 rounded-lg bg-stone-50 flex items-center justify-center">
        <Icon size={16} weight="regular" className="text-stone-400" />
      </div>
    </div>
    <div className="text-3xl font-semibold tracking-tight text-stone-900">{value}</div>
    {subtext && <div className="text-xs text-stone-500">{subtext}</div>}
  </motion.div>
);

// Review Card Component
const ReviewCard = ({ review, isSelected, onClick }) => {
  const isPending = review.response_status === "pending";
  
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      onClick={onClick}
      className={`px-4 py-3.5 cursor-pointer review-item ${
        isSelected ? "review-item-active" : ""
      }`}
      data-testid={`review-card-${review.id}`}
    >
      <div className="flex items-start gap-3">
        <img
          src={review.guest_avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(review.guest_name)}&background=f5f5f4&color=3E5245&bold=true`}
          alt={review.guest_name}
          className="w-9 h-9 rounded-full object-cover ring-1 ring-stone-200"
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 mb-0.5">
            <span className="font-medium text-sm text-stone-900 truncate">{review.guest_name}</span>
            <PlatformBadge platform={review.platform} />
          </div>
          <StarRating rating={review.rating} size={12} />
          <p className="text-sm text-stone-500 line-clamp-2 mt-1.5 leading-relaxed">{review.review_text}</p>
          <div className="flex items-center justify-between mt-2">
            <span className="text-[11px] text-stone-400">
              {new Date(review.review_date).toLocaleDateString()}
            </span>
            {isPending ? (
              <span className="flex items-center gap-1 text-[11px] font-medium text-amber-600">
                <WarningCircle size={12} weight="fill" />
                Pending
              </span>
            ) : (
              <span className="flex items-center gap-1 text-[11px] font-medium text-emerald-700">
                <CheckCircle size={12} weight="fill" />
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
  const [language, setLanguage] = useState("auto");
  const [detectedLang, setDetectedLang] = useState(null);
  const [isDetecting, setIsDetecting] = useState(false);
  const [isTranslating, setIsTranslating] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [sentimentData, setSentimentData] = useState(null);
  const [suggestedTemplates, setSuggestedTemplates] = useState([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const LANGUAGES = [
    { code: "auto", name: "Auto-detect" },
    { code: "en", name: "English" },
    { code: "fr", name: "French" },
    { code: "de", name: "German" },
    { code: "es", name: "Spanish" },
    { code: "it", name: "Italian" },
    { code: "pt", name: "Portuguese" },
    { code: "zh", name: "Chinese" },
    { code: "ja", name: "Japanese" },
    { code: "ko", name: "Korean" },
    { code: "ar", name: "Arabic" },
    { code: "ru", name: "Russian" },
    { code: "nl", name: "Dutch" },
    { code: "th", name: "Thai" },
    { code: "hi", name: "Hindi" },
    { code: "tr", name: "Turkish" }
  ];

  useEffect(() => {
    if (review?.response_text) {
      setResponseText(review.response_text);
    } else {
      setResponseText("");
    }
    setSentimentData(review?.sentiment_analysis || null);
    setSuggestedTemplates([]);
    setDetectedLang(null);
    setLanguage("auto");
  }, [review]);

  // Auto-detect language when review changes
  useEffect(() => {
    if (review && !review.response_text) {
      detectLanguage();
    }
  }, [review?.id]);

  const detectLanguage = async () => {
    if (!review) return;
    setIsDetecting(true);
    try {
      const response = await axios.post(`${API}/reviews/${review.id}/detect-language`);
      setDetectedLang(response.data);
    } catch (error) {
      console.error("Language detection error:", error);
    } finally {
      setIsDetecting(false);
    }
  };

  const translateToEnglish = async () => {
    if (!responseText.trim()) return;
    setIsTranslating(true);
    try {
      const response = await axios.post(`${API}/reviews/translate`, {
        text: responseText,
        target_language: "en"
      });
      setResponseText(response.data.translated_text);
      toast.success("Translated to English");
    } catch (error) {
      toast.error("Translation failed");
    } finally {
      setIsTranslating(false);
    }
  };

  // Handle template application
  useEffect(() => {
    if (templateText && review) {
      // Replace {guest_name} placeholder with actual guest name
      const processedText = templateText.replace(/\{guest_name\}/g, review.guest_name);
      setResponseText(processedText);
      if (onTemplateApplied) onTemplateApplied();
    }
  }, [templateText, review, onTemplateApplied]);

  const analyzeSentiment = async () => {
    if (!review) return;
    setIsAnalyzing(true);
    try {
      const response = await axios.post(`${API}/reviews/${review.id}/analyze`);
      setSentimentData(response.data.analysis);
      setSuggestedTemplates(response.data.suggested_templates || []);
      
      // Auto-set tone based on analysis
      if (response.data.analysis?.suggested_tone) {
        setTone(response.data.analysis.suggested_tone);
      }
      
      toast.success("Sentiment analyzed!");
    } catch (error) {
      console.error("Error analyzing sentiment:", error);
      toast.error("Failed to analyze sentiment");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const applyTemplate = (templateContent) => {
    const processedText = templateContent.replace(/\{guest_name\}/g, review?.guest_name || "Guest");
    setResponseText(processedText);
    toast.success("Template applied!");
  };

  const generateAIResponse = async () => {
    if (!review) return;
    
    setIsGenerating(true);
    try {
      const response = await axios.post(`${API}/reviews/generate-ai-response`, {
        review_id: review.id,
        tone: tone,
        language: language
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
      <div className="flex-1 flex items-center justify-center" data-testid="no-review-selected">
        <div className="text-center">
          <div className="w-16 h-16 rounded-2xl bg-stone-100 flex items-center justify-center mx-auto mb-4">
            <ChatText size={28} className="text-stone-300" />
          </div>
          <p className="text-sm font-medium text-stone-400">Select a review to view details and respond</p>
          <p className="text-xs text-stone-300 mt-1">Choose from the list on the left</p>
        </div>
      </div>
    );
  }

  const isResponded = review.response_status === "responded";

  return (
    <div className="flex-1 flex flex-col" data-testid="ai-response-panel">
      {/* Review Details */}
      <div className="border-b border-stone-100 pb-6 mb-6">
        <div className="flex items-start gap-4">
          <img
            src={review.guest_avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(review.guest_name)}&background=f5f5f4&color=3E5245&bold=true`}
            alt={review.guest_name}
            className="w-12 h-12 rounded-full object-cover ring-2 ring-stone-100"
          />
          <div className="flex-1">
            <div className="flex items-center gap-2.5 mb-1.5">
              <h3 className="text-lg font-semibold tracking-tight text-stone-900" data-testid="review-guest-name">
                {review.guest_name}
              </h3>
              <PlatformBadge platform={review.platform} />
              {isResponded ? (
                <Badge className="bg-emerald-50 text-emerald-700 border border-emerald-200">
                  <CheckCircle size={12} className="mr-1" weight="fill" />
                  Responded
                </Badge>
              ) : (
                <Badge className="bg-amber-50 text-amber-700 border border-amber-200">
                  <WarningCircle size={12} className="mr-1" weight="fill" />
                  Pending
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-3 text-xs text-stone-500">
              <StarRating rating={review.rating} />
              {review.room_type && <span className="text-stone-300">|</span>}
              {review.room_type && <span>{review.room_type}</span>}
              {review.stay_date && <span className="text-stone-300">|</span>}
              {review.stay_date && <span>Stayed: {review.stay_date}</span>}
            </div>
          </div>
        </div>
        
        <div className="mt-4 bg-stone-50 rounded-xl p-5 relative" data-testid="review-text-container">
          <Quotes size={20} className="absolute top-3 left-3 text-stone-200" weight="fill" />
          <p className="text-stone-700 leading-relaxed pl-6 text-sm" data-testid="review-text">
            {review.review_text}
          </p>
          {/* Language Detection Badge */}
          {detectedLang && (
            <div className="mt-3 pt-3 border-t border-stone-200/60 flex items-center gap-2" data-testid="detected-language">
              <span className="text-[11px] text-stone-400">Detected language:</span>
              <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-100">
                {detectedLang.name}
              </span>
              {detectedLang.confidence && (
                <span className="text-[10px] text-stone-300">{Math.round(detectedLang.confidence * 100)}% confidence</span>
              )}
            </div>
          )}
          {isDetecting && (
            <div className="mt-3 pt-3 border-t border-stone-200/60 flex items-center gap-2">
              <ArrowsClockwise size={12} className="animate-spin text-stone-300" />
              <span className="text-[11px] text-stone-400">Detecting language...</span>
            </div>
          )}
        </div>

        {/* Sentiment Analysis Section */}
        <div className="mt-4 border border-stone-200 rounded-md bg-white p-4" data-testid="sentiment-section">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Brain size={18} className="text-[#3E5245]" />
              <span className="text-sm font-medium text-[#1C1917]">Smart Analysis</span>
            </div>
            {!sentimentData && (
              <button
                onClick={analyzeSentiment}
                disabled={isAnalyzing}
                className="text-sm text-[#3E5245] hover:text-[#2A3B30] flex items-center gap-1"
                data-testid="analyze-sentiment-btn"
              >
                {isAnalyzing ? <ArrowsClockwise size={14} className="animate-spin" /> : <Sparkle size={14} />}
                {isAnalyzing ? "Analyzing..." : "Analyze Review"}
              </button>
            )}
          </div>

          {sentimentData ? (
            <div className="space-y-3">
              {/* Sentiment Badge */}
              <div className="flex items-center gap-3 flex-wrap">
                <div className={`${SENTIMENT_COLORS[sentimentData.sentiment]?.light || 'bg-stone-100'} px-3 py-1 rounded-full flex items-center gap-2`}>
                  {sentimentData.sentiment === 'positive' && <Smiley size={16} weight="fill" className="text-[#5A6B50]" />}
                  {sentimentData.sentiment === 'negative' && <SmileySad size={16} weight="fill" className="text-[#C05A44]" />}
                  {(sentimentData.sentiment === 'neutral' || sentimentData.sentiment === 'mixed') && <SmileyMeh size={16} weight="fill" className="text-[#57534E]" />}
                  <span className="text-sm font-medium capitalize">{sentimentData.sentiment}</span>
                </div>
                <Badge className={`${URGENCY_COLORS[sentimentData.urgency]} text-white`}>
                  {sentimentData.urgency} urgency
                </Badge>
                <Badge className="bg-[#E8EDE7] text-[#1C1917]">
                  Suggested: {sentimentData.suggested_tone}
                </Badge>
              </div>

              {/* Topics */}
              {sentimentData.topics?.length > 0 && (
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs text-[#57534E]">Topics:</span>
                  {sentimentData.topics.slice(0, 5).map((topic) => (
                    <span key={topic} className="text-xs bg-stone-100 px-2 py-0.5 rounded capitalize">{topic}</span>
                  ))}
                </div>
              )}

              {/* Key Issues & Praises */}
              <div className="grid grid-cols-2 gap-3">
                {sentimentData.key_issues?.length > 0 && (
                  <div className="text-sm">
                    <span className="text-[#C05A44] font-medium flex items-center gap-1 mb-1">
                      <TrendDown size={14} /> Issues
                    </span>
                    {sentimentData.key_issues.slice(0, 2).map((issue, idx) => (
                      <div key={idx} className="text-xs text-[#57534E] truncate">• {issue}</div>
                    ))}
                  </div>
                )}
                {sentimentData.key_praises?.length > 0 && (
                  <div className="text-sm">
                    <span className="text-[#5A6B50] font-medium flex items-center gap-1 mb-1">
                      <TrendUp size={14} /> Praises
                    </span>
                    {sentimentData.key_praises.slice(0, 2).map((praise, idx) => (
                      <div key={idx} className="text-xs text-[#57534E] truncate">• {praise}</div>
                    ))}
                  </div>
                )}
              </div>

              {/* Suggested Templates */}
              {suggestedTemplates.length > 0 && (
                <div className="pt-3 border-t border-stone-200">
                  <span className="text-xs font-medium text-[#1C1917] mb-2 block">Suggested Templates:</span>
                  <div className="flex gap-2 flex-wrap">
                    {suggestedTemplates.map((template) => (
                      <button
                        key={template.id}
                        onClick={() => applyTemplate(template.content)}
                        className="text-xs bg-[#E8EDE7] hover:bg-[#D5DDD3] px-2 py-1 rounded flex items-center gap-1 transition-colors"
                        data-testid={`suggested-template-${template.id}`}
                      >
                        <Copy size={12} />
                        {template.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-[#57534E]">
              Click "Analyze Review" to get AI-powered sentiment analysis and template suggestions.
            </p>
          )}
        </div>
      </div>

      {/* AI Response Generator */}
      <div className="bg-emerald-50/50 border border-emerald-100 rounded-xl p-6 relative overflow-hidden" data-testid="ai-generator-panel">
        {/* Texture overlay */}
        <div 
          className="absolute inset-0 ai-texture-overlay pointer-events-none"
          style={{
            backgroundImage: "url('https://static.prod-images.emergentagent.com/jobs/f284f94c-059d-4721-a5db-def78e330cac/images/06790bb25ee93b714799620c98d82862ea6db3df67429246c55c3ae00c5536b8.png')",
            backgroundSize: "cover"
          }}
        />
        
        <div className="relative z-10">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-emerald-800 flex items-center justify-center">
                <Sparkle size={14} className="text-white" weight="fill" />
              </div>
              <span className="text-sm font-semibold text-emerald-900 tracking-tight">AI Response Assistant</span>
            </div>
            
            {!isResponded && (
              <div className="flex items-center gap-2">
                <Select value={language} onValueChange={setLanguage} data-testid="language-select">
                  <SelectTrigger className="w-[130px] bg-white/80 border-emerald-200 text-xs h-8">
                    <SelectValue placeholder="Language" />
                  </SelectTrigger>
                  <SelectContent>
                    {LANGUAGES.map((lang) => (
                      <SelectItem key={lang.code} value={lang.code}>
                        {lang.code === "auto" && detectedLang ? `Auto (${detectedLang.name})` : lang.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Select value={tone} onValueChange={setTone} data-testid="tone-select">
                  <SelectTrigger className="w-[120px] bg-white/80 border-emerald-200 text-xs h-8">
                    <SelectValue placeholder="Tone" />
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
                  className="bg-emerald-800 text-white px-3.5 py-1.5 rounded-lg hover:bg-emerald-900 transition-all active:scale-[0.98] disabled:opacity-50 flex items-center gap-1.5 text-sm font-medium"
                  data-testid="generate-ai-btn"
                >
                  {isGenerating ? (
                    <>
                      <ArrowsClockwise size={14} className="animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <Sparkle size={14} weight="fill" />
                      Generate Reply
                    </>
                  )}
                </button>
              </div>
            )}
          </div>

          {isGenerating && (
            <div className="ai-shimmer h-1.5 rounded-full mb-3" />
          )}

          <div className="relative">
            <Textarea
              value={responseText}
              onChange={(e) => setResponseText(e.target.value)}
              placeholder={isResponded ? "Response already submitted" : "AI-generated response will appear here. You can edit before publishing..."}
              className={`min-h-[160px] bg-white border-emerald-200/60 rounded-lg resize-none text-sm focus:ring-2 focus:ring-emerald-800/15 focus:border-emerald-300 ${isGenerating ? "cursor-blink" : ""}`}
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
            <div className="flex items-center gap-2">
              {responseText.trim() && !isResponded && (
                <button
                  onClick={translateToEnglish}
                  disabled={isTranslating}
                  className="bg-white border border-emerald-200 text-emerald-800 px-2.5 py-1 rounded-lg hover:bg-emerald-50 transition-all text-xs font-medium flex items-center gap-1 disabled:opacity-50"
                  data-testid="translate-to-english-btn"
                >
                  {isTranslating ? (
                    <ArrowsClockwise size={12} className="animate-spin" />
                  ) : (
                    <span>EN</span>
                  )}
                  {isTranslating ? "Translating..." : "Translate to English"}
                </button>
              )}
              <p className="text-[11px] text-stone-400">
                {isResponded ? "This review has been responded to." : ""}
              </p>
            </div>
            
            {(!isResponded || isEditing) && (
              <div className="flex items-center gap-2">
                {isEditing && (
                  <button
                    onClick={() => {
                      setIsEditing(false);
                      setResponseText(review.response_text || "");
                    }}
                    className="bg-white border border-stone-200 text-stone-700 px-3 py-1.5 rounded-lg hover:bg-stone-50 transition-all text-sm"
                    data-testid="cancel-edit-btn"
                  >
                    Cancel
                  </button>
                )}
                <button
                  onClick={handleSubmit}
                  disabled={!responseText.trim() || isLoading || isGenerating}
                  className="bg-emerald-800 text-white px-4 py-1.5 rounded-lg hover:bg-emerald-900 transition-all active:scale-[0.98] disabled:opacity-50 flex items-center gap-1.5 text-sm font-medium"
                  data-testid="publish-response-btn"
                >
                  <PaperPlaneTilt size={14} weight="fill" />
                  {isEditing ? "Update" : "Publish"}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Info Banner */}
      <div className="mt-4 px-4 py-2.5 bg-stone-50 border border-stone-100 rounded-lg">
        <p className="text-[11px] text-stone-400 flex items-center gap-2">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-400"></span>
          <strong className="text-stone-500">DEMO:</strong> Responses will sync to {PLATFORMS[review.platform]?.name || review.platform} in production.
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

// Analytics Panel Component
const AnalyticsPanel = ({ isOpen, onClose }) => {
  const [analytics, setAnalytics] = useState(null);
  const [competitors, setCompetitors] = useState([]);
  const [benchmark, setBenchmark] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [newCompetitor, setNewCompetitor] = useState({ name: "", avg_rating: 4.0, total_reviews: 100, response_rate: 50 });

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [analyticsRes, competitorsRes, benchmarkRes] = await Promise.all([
        axios.get(`${API}/analytics/dashboard`),
        axios.get(`${API}/competitors`),
        axios.get(`${API}/competitors/benchmark`)
      ]);
      setAnalytics(analyticsRes.data);
      setCompetitors(competitorsRes.data);
      setBenchmark(benchmarkRes.data);
    } catch (error) {
      console.error("Error fetching analytics:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const seedCompetitors = useCallback(async () => {
    try {
      await axios.post(`${API}/competitors/seed`);
      await fetchData();
    } catch (error) {
      console.error("Error seeding competitors:", error);
    }
  }, [fetchData]);

  useEffect(() => {
    if (isOpen) {
      seedCompetitors();
      fetchData();
    }
  }, [isOpen, fetchData, seedCompetitors]);

  const runBatchAnalysis = async () => {
    setIsAnalyzing(true);
    try {
      const result = await axios.post(`${API}/reviews/analyze-batch`);
      toast.success(`Analyzed ${result.data.analyzed} reviews!`);
      await fetchData();
    } catch (error) {
      console.error("Error running analysis:", error);
      toast.error("Failed to run analysis");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const addCompetitor = async () => {
    if (!newCompetitor.name) return;
    try {
      await axios.post(`${API}/competitors`, {
        ...newCompetitor,
        platform: "all"
      });
      toast.success("Competitor added!");
      setNewCompetitor({ name: "", avg_rating: 4.0, total_reviews: 100, response_rate: 50 });
      await fetchData();
    } catch (error) {
      console.error("Error adding competitor:", error);
      toast.error("Failed to add competitor");
    }
  };

  const deleteCompetitor = async (id) => {
    try {
      await axios.delete(`${API}/competitors/${id}`);
      toast.success("Competitor removed");
      await fetchData();
    } catch (error) {
      console.error("Error deleting competitor:", error);
    }
  };

  const getSentimentIcon = (sentiment) => {
    switch (sentiment) {
      case "positive": return <Smiley size={16} weight="fill" className="text-[#5A6B50]" />;
      case "negative": return <SmileySad size={16} weight="fill" className="text-[#C05A44]" />;
      default: return <SmileyMeh size={16} weight="fill" className="text-[#57534E]" />;
    }
  };

  return (
    <DialogContent className="sm:max-w-[900px] max-h-[90vh] overflow-y-auto" data-testid="analytics-dialog">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2 text-[#1C1917] font-['Work_Sans']">
          <ChartBar size={20} weight="fill" className="text-[#3E5245]" />
          Analytics & Insights
        </DialogTitle>
      </DialogHeader>

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <ArrowsClockwise size={32} className="animate-spin text-[#3E5245]" />
        </div>
      ) : (
        <Tabs defaultValue="overview" className="w-full">
          <TabsList className="grid w-full grid-cols-3 mb-4">
            <TabsTrigger value="overview" data-testid="analytics-overview-tab">Overview</TabsTrigger>
            <TabsTrigger value="sentiment" data-testid="analytics-sentiment-tab">Sentiment</TabsTrigger>
            <TabsTrigger value="competitors" data-testid="analytics-competitors-tab">Competitors</TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-4">
            {/* Key Metrics */}
            <div className="grid grid-cols-4 gap-3">
              <div className="bg-[#FAF9F6] border border-stone-200 rounded-md p-4">
                <div className="flex items-center gap-2 text-[#57534E] mb-1">
                  <ChatText size={16} />
                  <span className="text-xs uppercase tracking-wider">Reviews</span>
                </div>
                <div className="text-2xl font-semibold text-[#1C1917]">{analytics?.overview?.total_reviews || 0}</div>
              </div>
              <div className="bg-[#FAF9F6] border border-stone-200 rounded-md p-4">
                <div className="flex items-center gap-2 text-[#57534E] mb-1">
                  <Star size={16} weight="fill" className="text-[#D4A373]" />
                  <span className="text-xs uppercase tracking-wider">Avg Rating</span>
                </div>
                <div className="text-2xl font-semibold text-[#1C1917]">{analytics?.overview?.avg_rating || 0}/5</div>
              </div>
              <div className="bg-[#FAF9F6] border border-stone-200 rounded-md p-4">
                <div className="flex items-center gap-2 text-[#57534E] mb-1">
                  <CheckCircle size={16} className="text-[#5A6B50]" />
                  <span className="text-xs uppercase tracking-wider">Response Rate</span>
                </div>
                <div className="text-2xl font-semibold text-[#1C1917]">{analytics?.overview?.response_rate || 0}%</div>
              </div>
              <div className="bg-[#FAF9F6] border border-stone-200 rounded-md p-4">
                <div className="flex items-center gap-2 text-[#57534E] mb-1">
                  <WarningCircle size={16} className="text-[#D4A373]" />
                  <span className="text-xs uppercase tracking-wider">Pending</span>
                </div>
                <div className="text-2xl font-semibold text-[#1C1917]">{analytics?.overview?.pending || 0}</div>
              </div>
            </div>

            {/* Rating Distribution */}
            <div className="bg-white border border-stone-200 rounded-md p-4">
              <h4 className="font-medium text-[#1C1917] mb-3 flex items-center gap-2">
                <Star size={18} className="text-[#D4A373]" />
                Rating Distribution
              </h4>
              <div className="space-y-2">
                {[5, 4, 3, 2, 1].map((rating) => {
                  const count = analytics?.rating_distribution?.[rating] || 0;
                  const total = analytics?.overview?.total_reviews || 1;
                  const percentage = Math.round((count / total) * 100);
                  return (
                    <div key={rating} className="flex items-center gap-3">
                      <span className="w-12 text-sm text-[#57534E]">{rating} star</span>
                      <Progress value={percentage} className="flex-1 h-2" />
                      <span className="w-16 text-sm text-[#57534E] text-right">{count} ({percentage}%)</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Platform Stats */}
            <div className="bg-white border border-stone-200 rounded-md p-4">
              <h4 className="font-medium text-[#1C1917] mb-3">Platform Performance</h4>
              <div className="grid grid-cols-3 gap-2">
                {analytics?.platform_stats?.map((platform) => (
                  <div key={platform.platform} className="flex items-center justify-between p-2 bg-[#FAF9F6] rounded">
                    <span className="text-sm font-medium">{PLATFORMS[platform.platform]?.name || platform.platform}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-[#57534E]">{platform.count} reviews</span>
                      <Badge className="bg-[#3E5245] text-white">{platform.avg_rating}/5</Badge>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Priority Queue */}
            {analytics?.priority_queue?.length > 0 && (
              <div className="bg-red-50 border border-[#C05A44] rounded-md p-4">
                <h4 className="font-medium text-[#C05A44] mb-3 flex items-center gap-2">
                  <Fire size={18} weight="fill" />
                  Priority Queue - Urgent Reviews
                </h4>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {analytics.priority_queue.slice(0, 5).map((review) => (
                    <div key={review.id} className="flex items-center justify-between p-2 bg-white rounded border border-stone-200">
                      <div>
                        <span className="font-medium text-sm">{review.guest_name}</span>
                        <span className="text-xs text-[#57534E] ml-2">- {PLATFORMS[review.platform]?.name}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <StarRating rating={review.rating} size={12} />
                        <Badge className={`${URGENCY_COLORS[review.sentiment_analysis?.urgency || 'high']} text-white`}>
                          {review.sentiment_analysis?.urgency || 'urgent'}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </TabsContent>

          {/* Sentiment Tab */}
          <TabsContent value="sentiment" className="space-y-4">
            <div className="flex justify-between items-center">
              <h4 className="font-medium text-[#1C1917] flex items-center gap-2">
                <Brain size={18} className="text-[#3E5245]" />
                AI Sentiment Analysis
              </h4>
              <button
                onClick={runBatchAnalysis}
                disabled={isAnalyzing}
                className="bg-[#3E5245] text-white px-3 py-1.5 rounded-md text-sm hover:bg-[#2A3B30] transition-colors disabled:opacity-50 flex items-center gap-2"
                data-testid="run-analysis-btn"
              >
                {isAnalyzing ? <ArrowsClockwise size={14} className="animate-spin" /> : <Sparkle size={14} />}
                {isAnalyzing ? "Analyzing..." : "Run Analysis"}
              </button>
            </div>

            {/* Sentiment Distribution */}
            <div className="grid grid-cols-4 gap-3">
              {Object.entries(analytics?.sentiment_distribution || {}).map(([sentiment, count]) => (
                <div key={sentiment} className={`${SENTIMENT_COLORS[sentiment]?.light || 'bg-stone-100'} border rounded-md p-4`}>
                  <div className="flex items-center gap-2 mb-2">
                    {getSentimentIcon(sentiment)}
                    <span className="text-sm font-medium capitalize">{sentiment}</span>
                  </div>
                  <div className="text-2xl font-semibold">{count}</div>
                </div>
              ))}
            </div>

            {/* Urgency Distribution */}
            <div className="bg-white border border-stone-200 rounded-md p-4">
              <h4 className="font-medium text-[#1C1917] mb-3 flex items-center gap-2">
                <Lightning size={18} className="text-[#D4A373]" />
                Urgency Breakdown
              </h4>
              <div className="flex gap-2">
                {Object.entries(analytics?.urgency_distribution || {}).map(([urgency, count]) => (
                  <div key={urgency} className="flex-1 text-center">
                    <div className={`${URGENCY_COLORS[urgency]} text-white rounded-md p-3 mb-1`}>
                      <div className="text-xl font-semibold">{count}</div>
                    </div>
                    <span className="text-xs text-[#57534E] capitalize">{urgency}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Top Topics */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white border border-stone-200 rounded-md p-4">
                <h4 className="font-medium text-[#1C1917] mb-3 flex items-center gap-2">
                  <Tag size={18} className="text-[#3E5245]" />
                  Top Mentioned Topics
                </h4>
                <div className="space-y-2">
                  {analytics?.top_topics?.slice(0, 6).map((topic, idx) => (
                    <div key={topic.topic} className="flex items-center justify-between">
                      <span className="text-sm capitalize">{topic.topic}</span>
                      <Badge className="bg-[#E8EDE7] text-[#1C1917]">{topic.count}</Badge>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-4">
                {/* Common Issues */}
                <div className="bg-red-50 border border-red-200 rounded-md p-4">
                  <h4 className="font-medium text-[#C05A44] mb-2 flex items-center gap-2">
                    <TrendDown size={16} />
                    Common Issues
                  </h4>
                  <div className="space-y-1">
                    {analytics?.common_issues?.slice(0, 3).map((item) => (
                      <div key={item.issue} className="text-sm text-[#57534E] truncate">
                        • {item.issue} ({item.count})
                      </div>
                    ))}
                    {(!analytics?.common_issues || analytics.common_issues.length === 0) && (
                      <div className="text-sm text-[#57534E]">Run analysis to see issues</div>
                    )}
                  </div>
                </div>

                {/* Common Praises */}
                <div className="bg-[#E8EDE7] border border-[#D5DDD3] rounded-md p-4">
                  <h4 className="font-medium text-[#3E5245] mb-2 flex items-center gap-2">
                    <TrendUp size={16} />
                    Common Praises
                  </h4>
                  <div className="space-y-1">
                    {analytics?.common_praises?.slice(0, 3).map((item) => (
                      <div key={item.praise} className="text-sm text-[#57534E] truncate">
                        • {item.praise} ({item.count})
                      </div>
                    ))}
                    {(!analytics?.common_praises || analytics.common_praises.length === 0) && (
                      <div className="text-sm text-[#57534E]">Run analysis to see praises</div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </TabsContent>

          {/* Competitors Tab */}
          <TabsContent value="competitors" className="space-y-4">
            {/* Your Ranking */}
            {benchmark && (
              <div className="bg-[#E8EDE7] border border-[#D5DDD3] rounded-md p-4">
                <h4 className="font-medium text-[#1C1917] mb-3 flex items-center gap-2">
                  <Trophy size={18} className="text-[#D4A373]" />
                  Your Competitive Position
                </h4>
                <div className="grid grid-cols-3 gap-4">
                  <div className="text-center">
                    <div className="text-3xl font-bold text-[#3E5245]">#{benchmark.ranking?.rating_rank}</div>
                    <div className="text-sm text-[#57534E]">Rating Rank</div>
                    <div className="text-xs text-[#57534E]">of {benchmark.ranking?.total_competitors}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-3xl font-bold text-[#3E5245]">{benchmark.your_hotel?.avg_rating}/5</div>
                    <div className="text-sm text-[#57534E]">Your Rating</div>
                  </div>
                  <div className="text-center">
                    <div className="text-3xl font-bold text-[#3E5245]">{benchmark.your_hotel?.response_rate}%</div>
                    <div className="text-sm text-[#57534E]">Response Rate</div>
                  </div>
                </div>
              </div>
            )}

            {/* Competitor List */}
            <div className="bg-white border border-stone-200 rounded-md p-4">
              <h4 className="font-medium text-[#1C1917] mb-3 flex items-center gap-2">
                <Users size={18} className="text-[#3E5245]" />
                Competitor Comparison
              </h4>
              <div className="space-y-2">
                {/* Your Hotel Row */}
                <div className="flex items-center justify-between p-3 bg-[#E8EDE7] rounded-md border-2 border-[#3E5245]">
                  <div className="flex items-center gap-2">
                    <Buildings size={20} className="text-[#3E5245]" />
                    <span className="font-medium">Your Hotel</span>
                    <Badge className="bg-[#3E5245] text-white">You</Badge>
                  </div>
                  <div className="flex items-center gap-6">
                    <div className="text-center">
                      <div className="font-semibold">{benchmark?.your_hotel?.avg_rating}/5</div>
                      <div className="text-xs text-[#57534E]">Rating</div>
                    </div>
                    <div className="text-center">
                      <div className="font-semibold">{benchmark?.your_hotel?.total_reviews}</div>
                      <div className="text-xs text-[#57534E]">Reviews</div>
                    </div>
                    <div className="text-center">
                      <div className="font-semibold">{benchmark?.your_hotel?.response_rate}%</div>
                      <div className="text-xs text-[#57534E]">Response</div>
                    </div>
                  </div>
                </div>

                {/* Competitors */}
                {competitors.map((comp) => (
                  <div key={comp.id} className="flex items-center justify-between p-3 bg-[#FAF9F6] rounded-md">
                    <div className="flex items-center gap-2">
                      <Target size={20} className="text-[#57534E]" />
                      <span className="font-medium">{comp.name}</span>
                    </div>
                    <div className="flex items-center gap-6">
                      <div className="text-center">
                        <div className="font-semibold">{comp.avg_rating}/5</div>
                        <div className="text-xs text-[#57534E]">Rating</div>
                      </div>
                      <div className="text-center">
                        <div className="font-semibold">{comp.total_reviews}</div>
                        <div className="text-xs text-[#57534E]">Reviews</div>
                      </div>
                      <div className="text-center">
                        <div className="font-semibold">{comp.response_rate}%</div>
                        <div className="text-xs text-[#57534E]">Response</div>
                      </div>
                      <button
                        onClick={() => deleteCompetitor(comp.id)}
                        className="p-1 hover:bg-red-50 rounded transition-colors"
                        data-testid={`delete-competitor-${comp.id}`}
                      >
                        <Trash size={16} className="text-[#C05A44]" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Add Competitor */}
              <div className="mt-4 pt-4 border-t border-stone-200">
                <h5 className="text-sm font-medium text-[#1C1917] mb-2">Add Competitor</h5>
                <div className="flex gap-2">
                  <Input
                    placeholder="Hotel name"
                    value={newCompetitor.name}
                    onChange={(e) => setNewCompetitor(prev => ({ ...prev, name: e.target.value }))}
                    className="flex-1"
                    data-testid="competitor-name-input"
                  />
                  <Input
                    type="number"
                    placeholder="Rating"
                    value={newCompetitor.avg_rating}
                    onChange={(e) => setNewCompetitor(prev => ({ ...prev, avg_rating: parseFloat(e.target.value) }))}
                    className="w-20"
                    step="0.1"
                    min="1"
                    max="5"
                  />
                  <Input
                    type="number"
                    placeholder="Reviews"
                    value={newCompetitor.total_reviews}
                    onChange={(e) => setNewCompetitor(prev => ({ ...prev, total_reviews: parseInt(e.target.value) }))}
                    className="w-24"
                  />
                  <Input
                    type="number"
                    placeholder="Resp %"
                    value={newCompetitor.response_rate}
                    onChange={(e) => setNewCompetitor(prev => ({ ...prev, response_rate: parseFloat(e.target.value) }))}
                    className="w-20"
                  />
                  <button
                    onClick={addCompetitor}
                    disabled={!newCompetitor.name}
                    className="bg-[#3E5245] text-white px-3 py-2 rounded-md hover:bg-[#2A3B30] transition-colors disabled:opacity-50"
                    data-testid="add-competitor-btn"
                  >
                    <Plus size={16} />
                  </button>
                </div>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      )}
    </DialogContent>
  );
};

// Reports Settings Component
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

// Platform Integrations Component
const IntegrationsPanel = ({ isOpen, onClose, onSyncComplete }) => {
  const [integrations, setIntegrations] = useState([]);
  const [requirements, setRequirements] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [syncingPlatform, setSyncingPlatform] = useState(null);
  const [showManualImport, setShowManualImport] = useState(false);
  const [manualReview, setManualReview] = useState({
    platform: "google",
    guest_name: "",
    rating: 5,
    review_text: "",
    stay_date: "",
    room_type: ""
  });
  const [selectedPlatformDetails, setSelectedPlatformDetails] = useState(null);
  const [showConfigWizard, setShowConfigWizard] = useState(null);
  const [configCredentials, setConfigCredentials] = useState({});
  const [isSavingConfig, setIsSavingConfig] = useState(false);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [integrationsRes, requirementsRes] = await Promise.all([
        axios.get(`${API}/integrations`),
        axios.get(`${API}/integrations/requirements`)
      ]);
      setIntegrations(integrationsRes.data);
      setRequirements(requirementsRes.data);
    } catch (error) {
      console.error("Error fetching integrations:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      fetchData();
    }
  }, [isOpen, fetchData]);

  const handleSync = async (platform) => {
    setSyncingPlatform(platform);
    try {
      const response = await axios.post(`${API}/integrations/${platform}/sync`);
      if (response.data.reviews_synced > 0) {
        toast.success(`Synced ${response.data.reviews_synced} reviews from ${platform}!`);
        if (onSyncComplete) onSyncComplete();
      } else if (response.data.errors?.length > 0) {
        toast.info(response.data.errors[0]);
      }
      await fetchData();
    } catch (error) {
      console.error("Sync error:", error);
      toast.error(error.response?.data?.detail || "Sync failed");
    } finally {
      setSyncingPlatform(null);
    }
  };

  const handleManualImport = async () => {
    if (!manualReview.guest_name || !manualReview.review_text) {
      toast.error("Please fill in guest name and review text");
      return;
    }
    try {
      await axios.post(`${API}/integrations/import`, [manualReview]);
      toast.success("Review imported successfully!");
      setManualReview({ platform: "google", guest_name: "", rating: 5, review_text: "", stay_date: "", room_type: "" });
      setShowManualImport(false);
      if (onSyncComplete) onSyncComplete();
    } catch (error) {
      console.error("Import error:", error);
      toast.error("Failed to import review");
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append("file", file);
    
    try {
      const response = await axios.post(`${API}/integrations/import-csv`, formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      toast.success(`Imported ${response.data.imported} reviews!`);
      if (onSyncComplete) onSyncComplete();
    } catch (error) {
      console.error("CSV import error:", error);
      toast.error("Failed to import CSV");
    }
  };

  const getPlatformIcon = (platform) => {
    const icons = {
      "google": "🔍",
      "booking.com": "🅱️",
      "tripadvisor": "🦉",
      "airbnb": "🏠",
      "expedia": "✈️",
      "trip.com": "🌏",
      "agoda": "🏨",
      "hotels.com": "🛏️",
      "yelp": "📣",
      "facebook": "👤",
      "makemytrip": "🇮🇳",
      "hrs": "💼",
      "despegar": "🌎",
      "hostelworld": "🎒"
    };
    return icons[platform] || "🌐";
  };

  const getStatusBadge = (status, configured) => {
    if (status === "connected") {
      return <Badge className="bg-[#5A6B50] text-white"><CheckCircle size={12} className="mr-1" />Connected</Badge>;
    } else if (status === "error") {
      return <Badge className="bg-[#C05A44] text-white"><WarningCircle size={12} className="mr-1" />Error</Badge>;
    } else if (configured) {
      return <Badge className="bg-[#D4A373] text-white"><Link size={12} className="mr-1" />Configured</Badge>;
    }
    return <Badge className="bg-stone-400 text-white"><LinkBreak size={12} className="mr-1" />Not Connected</Badge>;
  };

  const handleSaveConfig = async (platform) => {
    setIsSavingConfig(true);
    try {
      await axios.put(`${API}/integrations/${platform}/configure`, {
        platform: platform,
        credentials: configCredentials,
        location_id: configCredentials.location_id || configCredentials.property_id || configCredentials.hotel_id,
        property_name: configCredentials.property_name
      });
      toast.success(`${platform} credentials saved!`);
      setShowConfigWizard(null);
      setConfigCredentials({});
      await fetchData();
    } catch (error) {
      console.error("Config save error:", error);
      toast.error("Failed to save configuration");
    } finally {
      setIsSavingConfig(false);
    }
  };

  // Setup guides for each platform
  const setupGuides = {
    google: {
      title: "Google Business Profile Setup Guide",
      steps: [
        { title: "1. Verify Your Business", description: "Go to business.google.com and claim/verify your hotel listing if you haven't already." },
        { title: "2. Create Google Cloud Project", description: "Visit console.cloud.google.com → Create new project → Name it 'Review Hub Integration'" },
        { title: "3. Enable APIs", description: "In your project, go to 'APIs & Services' → 'Enable APIs' → Search and enable 'My Business Business Information API' and 'My Business Account Management API'" },
        { title: "4. Create OAuth Credentials", description: "Go to 'APIs & Services' → 'Credentials' → 'Create Credentials' → 'OAuth client ID' → Select 'Web application'" },
        { title: "5. Configure OAuth Consent", description: "Set up OAuth consent screen with your business info. Add scopes for business.manage" },
        { title: "6. Get Your Location ID", description: "Your location ID format is: accounts/{account_id}/locations/{location_id}. Find this in your Business Profile dashboard." },
        { title: "7. Generate Refresh Token", description: "Use Google's OAuth Playground (developers.google.com/oauthplayground) to generate a refresh token with your credentials." }
      ],
      fields: [
        { key: "client_id", label: "OAuth Client ID", placeholder: "xxxx.apps.googleusercontent.com", type: "text" },
        { key: "client_secret", label: "OAuth Client Secret", placeholder: "GOCSPX-xxxxx", type: "password" },
        { key: "refresh_token", label: "Refresh Token", placeholder: "1//xxxxx", type: "password" },
        { key: "location_id", label: "Location ID", placeholder: "accounts/123/locations/456", type: "text" },
        { key: "property_name", label: "Hotel Name", placeholder: "Your Hotel Name", type: "text" }
      ]
    },
    "booking.com": {
      title: "Booking.com Connectivity Partner Setup",
      steps: [
        { title: "1. Apply for Partner Program", description: "Visit connect.booking.com and apply for the Connectivity Partner program. This requires a formal business application." },
        { title: "2. Wait for Approval", description: "Booking.com reviews applications and typically responds within 2-4 weeks. They evaluate your business and technical capabilities." },
        { title: "3. Complete Technical Onboarding", description: "Once approved, you'll receive access to their Partner Portal and technical documentation." },
        { title: "4. Get Machine Account Credentials", description: "Booking.com will provide you with a machine account username and password for API access." },
        { title: "5. Register Your Property", description: "Link your hotel property ID from your Booking.com extranet to the API connection." },
        { title: "6. Test in Sandbox", description: "Booking.com provides a sandbox environment to test your integration before going live." }
      ],
      fields: [
        { key: "username", label: "Machine Account Username", placeholder: "your_machine_account", type: "text" },
        { key: "password", label: "Machine Account Password", placeholder: "••••••••", type: "password" },
        { key: "property_id", label: "Property ID", placeholder: "12345678", type: "text" },
        { key: "property_name", label: "Hotel Name", placeholder: "Your Hotel Name", type: "text" }
      ],
      notice: "Booking.com API access requires approved Connectivity Partner status. Apply at connect.booking.com"
    },
    tripadvisor: {
      title: "TripAdvisor Content API Setup",
      steps: [
        { title: "1. Apply for Content API", description: "Visit developer.tripadvisor.com and register for the Content API partner program." },
        { title: "2. Submit Business Details", description: "Provide your business information and explain your use case for review management." },
        { title: "3. Receive API Key", description: "Once approved, you'll receive an API key for accessing TripAdvisor's Content API." },
        { title: "4. Find Your Location ID", description: "Search for your hotel on TripAdvisor. The location ID is in the URL (e.g., Hotel_Review-g123-d456)." }
      ],
      fields: [
        { key: "api_key", label: "API Key", placeholder: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx", type: "password" },
        { key: "location_id", label: "Location ID", placeholder: "d123456", type: "text" },
        { key: "property_name", label: "Hotel Name", placeholder: "Your Hotel Name", type: "text" }
      ],
      notice: "TripAdvisor Content API requires partner approval. Apply at developer.tripadvisor.com"
    },
    airbnb: {
      title: "Airbnb API Setup",
      steps: [
        { title: "1. Join Partner Program", description: "Visit airbnb.com/partner and apply for their technology partner program." },
        { title: "2. Provide Business Documentation", description: "Submit required business documentation for partner verification." },
        { title: "3. Complete Integration Review", description: "Airbnb will review your integration requirements and use case." }
      ],
      fields: [
        { key: "api_key", label: "API Key", placeholder: "Your Airbnb API key", type: "password" },
        { key: "listing_id", label: "Listing ID", placeholder: "12345678", type: "text" },
        { key: "property_name", label: "Property Name", placeholder: "Your Property Name", type: "text" }
      ],
      notice: "Airbnb API is primarily available to property management software partners."
    },
    expedia: {
      title: "Expedia Partner Central Setup",
      steps: [
        { title: "1. Access Partner Central", description: "Log into your Expedia Partner Central account at expediapartnercentral.com" },
        { title: "2. Request API Access", description: "Contact your Expedia market manager to request API access for review management." },
        { title: "3. Receive Credentials", description: "Once approved, you'll receive API key and secret for authentication." }
      ],
      fields: [
        { key: "api_key", label: "API Key", placeholder: "Your Expedia API key", type: "password" },
        { key: "secret_key", label: "Secret Key", placeholder: "Your secret key", type: "password" },
        { key: "property_id", label: "Property ID", placeholder: "12345678", type: "text" },
        { key: "property_name", label: "Hotel Name", placeholder: "Your Hotel Name", type: "text" }
      ],
      notice: "Contact your Expedia market manager for API access."
    },
    "trip.com": {
      title: "Trip.com Partner API Setup",
      steps: [
        { title: "1. Contact Trip.com Partner Team", description: "Reach out to Trip.com's partner team at partner.trip.com to request API access." },
        { title: "2. Complete Partner Agreement", description: "Sign the necessary partner agreements and provide business documentation." },
        { title: "3. Receive API Credentials", description: "Once approved, you'll receive your API key and hotel ID mapping." }
      ],
      fields: [
        { key: "api_key", label: "API Key", placeholder: "Your Trip.com API key", type: "password" },
        { key: "hotel_id", label: "Hotel ID", placeholder: "Your Trip.com hotel ID", type: "text" },
        { key: "property_name", label: "Hotel Name", placeholder: "Your Hotel Name", type: "text" }
      ],
      notice: "Contact Trip.com partner support for API access."
    },
    "agoda": {
      title: "Agoda Partner API Setup",
      steps: [
        { title: "1. Join Agoda Partner Program", description: "Visit partners.agoda.com and apply for the Agoda Partner Program with your business credentials." },
        { title: "2. Access YCS (Yield Control System)", description: "Log into Agoda's YCS platform to manage your property and review settings." },
        { title: "3. Request API Credentials", description: "Contact your Agoda market manager to request API access credentials for review management." },
        { title: "4. Get Property ID", description: "Find your Property ID in the YCS dashboard under Property Settings." }
      ],
      fields: [
        { key: "api_key", label: "API Key", placeholder: "Your Agoda API key", type: "password" },
        { key: "property_id", label: "Property ID", placeholder: "Your Agoda property ID", type: "text" },
        { key: "property_name", label: "Hotel Name", placeholder: "Your Hotel Name", type: "text" }
      ],
      notice: "Agoda is part of Booking Holdings. Contact your market manager for API access."
    },
    "hotels.com": {
      title: "Hotels.com Partner Setup",
      steps: [
        { title: "1. Access Hotels.com Supplier Portal", description: "Visit hotels.com/hotel-supplier and log into your partner account." },
        { title: "2. Use Expedia Partner Central", description: "Hotels.com uses Expedia's backend — access API settings via expediapartnercentral.com." },
        { title: "3. Request API Credentials", description: "Apply for API access through Expedia Partner Central and receive your API key and secret." },
        { title: "4. Get Property ID", description: "Find your Hotels.com Property ID in your Partner Central dashboard." }
      ],
      fields: [
        { key: "api_key", label: "API Key", placeholder: "Your Hotels.com API key", type: "password" },
        { key: "secret_key", label: "Secret Key", placeholder: "Your secret key", type: "password" },
        { key: "property_id", label: "Property ID", placeholder: "Your Hotels.com property ID", type: "text" },
        { key: "property_name", label: "Hotel Name", placeholder: "Your Hotel Name", type: "text" }
      ],
      notice: "Hotels.com is part of Expedia Group — use Expedia Partner Central for API access."
    },
    "yelp": {
      title: "Yelp Fusion API Setup",
      steps: [
        { title: "1. Claim Your Business", description: "Go to biz.yelp.com and claim your business listing if you haven't already." },
        { title: "2. Create a Yelp Fusion App", description: "Visit yelp.com/developers, create an app, and generate your Fusion API key." },
        { title: "3. Get Business ID", description: "Use the Yelp Business Search API or find your Business ID in your Yelp business page URL." }
      ],
      fields: [
        { key: "api_key", label: "Fusion API Key", placeholder: "Your Yelp Fusion API key", type: "password" },
        { key: "business_id", label: "Business ID", placeholder: "your-hotel-city", type: "text" },
        { key: "property_name", label: "Hotel Name", placeholder: "Your Hotel Name", type: "text" }
      ],
      notice: "Yelp Fusion API is free for limited use — great for local discovery and reviews."
    },
    "facebook": {
      title: "Facebook Reviews Setup",
      steps: [
        { title: "1. Set Up Facebook Business Page", description: "Ensure your hotel has a Facebook Business Page with reviews enabled." },
        { title: "2. Access Meta Business Suite", description: "Go to business.facebook.com and set up Meta Business Suite for your page." },
        { title: "3. Create a Facebook App", description: "Visit developers.facebook.com, create an app, and request pages_read_engagement permission." },
        { title: "4. Generate Access Token", description: "Use the Graph API Explorer to generate a long-lived Page Access Token." },
        { title: "5. Get Page ID", description: "Find your Page ID in your Facebook Page's About section or via the Graph API." }
      ],
      fields: [
        { key: "access_token", label: "Page Access Token", placeholder: "Your Facebook page access token", type: "password" },
        { key: "page_id", label: "Page ID", placeholder: "Your Facebook Page ID", type: "text" },
        { key: "property_name", label: "Hotel Name", placeholder: "Your Hotel Name", type: "text" }
      ],
      notice: "Use Meta Business Suite for managing reviews. Graph API required for automation."
    },
    "makemytrip": {
      title: "MakeMyTrip Partner Setup",
      steps: [
        { title: "1. Access Partner Extranet", description: "Log into your MakeMyTrip Partner Extranet account at partner.makemytrip.com." },
        { title: "2. Request API Access", description: "Contact your MakeMyTrip partner manager to request API access for review management." },
        { title: "3. Get Property ID", description: "Find your Property ID in the MMT Extranet dashboard under property settings." }
      ],
      fields: [
        { key: "api_key", label: "API Key", placeholder: "Your MakeMyTrip API key", type: "password" },
        { key: "property_id", label: "Property ID", placeholder: "Your MMT property ID", type: "text" },
        { key: "property_name", label: "Hotel Name", placeholder: "Your Hotel Name", type: "text" }
      ],
      notice: "#1 platform in India — contact partner support for API access."
    },
    "hrs": {
      title: "HRS Partner API Setup",
      steps: [
        { title: "1. Register as HRS Partner", description: "Visit hrs.com/hotel and register your property as an HRS hotel partner." },
        { title: "2. Access Partner Portal", description: "Log into the HRS Partner Portal and navigate to API settings." },
        { title: "3. Request API Credentials", description: "Apply for API credentials through your HRS account manager." },
        { title: "4. Get Hotel ID", description: "Find your HRS Hotel ID in your partner dashboard." }
      ],
      fields: [
        { key: "api_key", label: "API Key", placeholder: "Your HRS API key", type: "password" },
        { key: "hotel_id", label: "Hotel ID", placeholder: "Your HRS hotel ID", type: "text" },
        { key: "property_name", label: "Hotel Name", placeholder: "Your Hotel Name", type: "text" }
      ],
      notice: "Popular in Germany and Europe for business travel bookings."
    },
    "despegar": {
      title: "Despegar Partner API Setup",
      steps: [
        { title: "1. Join Despegar Partner Program", description: "Visit despegar.com/hoteles and apply for the partner program." },
        { title: "2. Complete Onboarding", description: "Work with the Despegar partner team to complete technical onboarding." },
        { title: "3. Receive API Credentials", description: "Once approved, you'll receive API keys and property mapping from the Despegar team." }
      ],
      fields: [
        { key: "api_key", label: "API Key", placeholder: "Your Despegar API key", type: "password" },
        { key: "property_id", label: "Property ID", placeholder: "Your Despegar property ID", type: "text" },
        { key: "property_name", label: "Hotel Name", placeholder: "Your Hotel Name", type: "text" }
      ],
      notice: "#1 OTA in Latin America — contact partner team for API access."
    },
    "hostelworld": {
      title: "Hostelworld API Setup",
      steps: [
        { title: "1. Register on Hostelworld", description: "Visit hostelworldgroup.com and register your property (hostels and budget accommodations)." },
        { title: "2. Access Inbox Dashboard", description: "Log into your Hostelworld Inbox to manage reviews and guest communication." },
        { title: "3. Request API Credentials", description: "Contact Hostelworld support to request API access for review integration." }
      ],
      fields: [
        { key: "api_key", label: "API Key", placeholder: "Your Hostelworld API key", type: "password" },
        { key: "property_id", label: "Property ID", placeholder: "Your Hostelworld property ID", type: "text" },
        { key: "property_name", label: "Hotel Name", placeholder: "Your Hotel Name", type: "text" }
      ],
      notice: "Best for hostels and budget accommodations worldwide."
    }
  };

  return (
    <DialogContent className="sm:max-w-[750px] max-h-[90vh] overflow-y-auto" data-testid="integrations-dialog">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2 text-[#1C1917] font-['Work_Sans']">
          <PlugsConnected size={20} weight="fill" className="text-[#3E5245]" />
          Platform Integrations
        </DialogTitle>
      </DialogHeader>

      {/* Configuration Wizard Modal */}
      {showConfigWizard && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowConfigWizard(null)}>
          <div className="bg-white rounded-lg max-w-2xl max-h-[90vh] overflow-auto m-4 w-full" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 bg-white border-b border-stone-200 p-4 flex justify-between items-center">
              <h3 className="font-semibold text-lg flex items-center gap-2">
                <span className="text-2xl">{getPlatformIcon(showConfigWizard)}</span>
                {setupGuides[showConfigWizard]?.title || `${showConfigWizard} Setup`}
              </h3>
              <button onClick={() => setShowConfigWizard(null)} className="p-2 hover:bg-stone-100 rounded-md">
                <X size={20} />
              </button>
            </div>
            
            <div className="p-6 space-y-6">
              {/* Setup Steps */}
              <div className="space-y-4">
                <h4 className="font-medium text-[#1C1917] flex items-center gap-2">
                  <Info size={18} className="text-[#3E5245]" />
                  Setup Steps
                </h4>
                <div className="space-y-3">
                  {setupGuides[showConfigWizard]?.steps.map((step, idx) => (
                    <div key={idx} className="flex gap-3 p-3 bg-[#FAF9F6] rounded-md">
                      <div className="w-6 h-6 bg-[#3E5245] text-white rounded-full flex items-center justify-center text-sm font-medium flex-shrink-0">
                        {idx + 1}
                      </div>
                      <div>
                        <div className="font-medium text-sm text-[#1C1917]">{step.title.replace(/^\d+\.\s*/, '')}</div>
                        <div className="text-xs text-[#57534E] mt-1">{step.description}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Notice if any */}
              {setupGuides[showConfigWizard]?.notice && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-md">
                  <p className="text-sm text-amber-800 flex items-center gap-2">
                    <WarningCircle size={16} />
                    {setupGuides[showConfigWizard].notice}
                  </p>
                </div>
              )}

              {/* Credential Fields */}
              <div className="space-y-4">
                <h4 className="font-medium text-[#1C1917] flex items-center gap-2">
                  <Link size={18} className="text-[#3E5245]" />
                  Enter Your Credentials
                </h4>
                <div className="space-y-3">
                  {setupGuides[showConfigWizard]?.fields.map((field) => (
                    <div key={field.key}>
                      <label className="text-sm font-medium text-[#57534E] block mb-1">{field.label}</label>
                      <Input
                        type={field.type}
                        placeholder={field.placeholder}
                        value={configCredentials[field.key] || ""}
                        onChange={(e) => setConfigCredentials(prev => ({ ...prev, [field.key]: e.target.value }))}
                        className="border-stone-200"
                        data-testid={`config-${field.key}`}
                      />
                    </div>
                  ))}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex justify-end gap-3 pt-4 border-t border-stone-200">
                <button
                  onClick={() => setShowConfigWizard(null)}
                  className="px-4 py-2 border border-stone-200 rounded-md hover:bg-stone-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={() => handleSaveConfig(showConfigWizard)}
                  disabled={isSavingConfig}
                  className="px-4 py-2 bg-[#3E5245] text-white rounded-md hover:bg-[#2A3B30] transition-colors disabled:opacity-50 flex items-center gap-2"
                  data-testid="save-config-btn"
                >
                  {isSavingConfig ? <ArrowsClockwise size={16} className="animate-spin" /> : <CheckCircle size={16} />}
                  Save Configuration
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center h-48">
          <ArrowsClockwise size={32} className="animate-spin text-[#3E5245]" />
        </div>
      ) : (
        <Tabs defaultValue="platforms" className="w-full">
          <TabsList className="grid w-full grid-cols-3 mb-4">
            <TabsTrigger value="platforms" data-testid="integrations-platforms-tab">Platforms</TabsTrigger>
            <TabsTrigger value="guides" data-testid="integrations-guides-tab">Setup Guides</TabsTrigger>
            <TabsTrigger value="import" data-testid="integrations-import-tab">Manual Import</TabsTrigger>
          </TabsList>

          <TabsContent value="platforms" className="space-y-4">
            {/* Info Banner */}
            <div className="p-3 bg-[#E8EDE7] border border-[#D5DDD3] rounded-md">
              <p className="text-sm text-[#57534E] flex items-center gap-2">
                <Info size={16} className="text-[#3E5245]" />
                Connect your review platforms to automatically sync reviews. Click "Configure" to enter your API credentials.
              </p>
            </div>

            {/* Platforms List */}
            <div className="space-y-3">
              {integrations.map((integration) => {
                const req = requirements[integration.platform] || {};
                return (
                  <div 
                    key={integration.platform}
                    className="border border-stone-200 rounded-md bg-white overflow-hidden"
                    data-testid={`integration-${integration.platform}`}
                  >
                    <div className="p-4 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="text-2xl">{getPlatformIcon(integration.platform)}</span>
                        <div>
                          <div className="font-medium text-[#1C1917] flex items-center gap-2">
                            {req.name || integration.platform}
                            {getStatusBadge(integration.status, integration.credentials_configured)}
                          </div>
                          <div className="text-xs text-[#57534E]">
                            {integration.total_reviews_synced > 0 
                              ? `${integration.total_reviews_synced} reviews synced` 
                              : "No reviews synced yet"}
                            {integration.last_sync && ` • Last: ${new Date(integration.last_sync).toLocaleDateString()}`}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setShowConfigWizard(integration.platform)}
                          className="bg-white border border-stone-200 text-[#1C1917] px-3 py-1.5 rounded-md text-sm hover:bg-stone-50 transition-colors flex items-center gap-1"
                          data-testid={`configure-${integration.platform}`}
                        >
                          <Link size={14} />
                          Configure
                        </button>
                        <button
                          onClick={() => handleSync(integration.platform)}
                          disabled={syncingPlatform === integration.platform}
                          className="bg-[#3E5245] text-white px-3 py-1.5 rounded-md text-sm hover:bg-[#2A3B30] transition-colors disabled:opacity-50 flex items-center gap-1"
                          data-testid={`sync-${integration.platform}`}
                        >
                          {syncingPlatform === integration.platform ? (
                            <ArrowsClockwise size={14} className="animate-spin" />
                          ) : (
                            <CloudArrowUp size={14} />
                          )}
                          Sync
                        </button>
                      </div>
                    </div>

                    {/* Expanded Details */}
                    {selectedPlatformDetails === integration.platform && (
                      <div className="px-4 pb-4 pt-2 border-t border-stone-100 bg-[#FAF9F6]">
                        <h5 className="text-sm font-medium text-[#1C1917] mb-2">Requirements:</h5>
                        <ul className="text-xs text-[#57534E] space-y-1 mb-3">
                          {req.requirements?.map((r, idx) => (
                            <li key={idx} className="flex items-start gap-2">
                              <span className="text-[#3E5245]">•</span> {r}
                            </li>
                          ))}
                        </ul>
                        {req.setup_url && (
                          <a 
                            href={req.setup_url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="text-xs text-[#3E5245] hover:underline flex items-center gap-1"
                          >
                            <Link size={12} /> Setup Guide
                          </a>
                        )}
                        {req.note && (
                          <p className="mt-2 text-xs text-[#D4A373] bg-amber-50 p-2 rounded">
                            ⚠️ {req.note}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </TabsContent>

          {/* Setup Guides Tab */}
          <TabsContent value="guides" className="space-y-4">
            <div className="p-3 bg-[#E8EDE7] border border-[#D5DDD3] rounded-md">
              <p className="text-sm text-[#57534E] flex items-center gap-2">
                <Info size={16} className="text-[#3E5245]" />
                Step-by-step guides to connect each platform. Click on a platform to see detailed setup instructions.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              {Object.entries(setupGuides).map(([platform, guide]) => (
                <div 
                  key={platform}
                  className="border border-stone-200 rounded-md p-4 bg-white hover:shadow-md transition-shadow cursor-pointer"
                  onClick={() => setShowConfigWizard(platform)}
                  data-testid={`guide-${platform}`}
                >
                  <div className="flex items-center gap-3 mb-3">
                    <span className="text-3xl">{getPlatformIcon(platform)}</span>
                    <div>
                      <h4 className="font-medium text-[#1C1917]">{guide.title.replace(' Setup Guide', '').replace(' Setup', '')}</h4>
                      <p className="text-xs text-[#57534E]">{guide.steps.length} steps to connect</p>
                    </div>
                  </div>
                  <div className="text-xs text-[#57534E] space-y-1">
                    {guide.steps.slice(0, 2).map((step, idx) => (
                      <div key={idx} className="flex items-start gap-2">
                        <span className="text-[#3E5245] font-medium">{idx + 1}.</span>
                        <span className="line-clamp-1">{step.title.replace(/^\d+\.\s*/, '')}</span>
                      </div>
                    ))}
                    <div className="text-[#3E5245] font-medium">+ {guide.steps.length - 2} more steps...</div>
                  </div>
                  <button className="mt-3 w-full py-2 bg-[#FAF9F6] text-[#3E5245] rounded-md text-sm hover:bg-[#E8EDE7] transition-colors flex items-center justify-center gap-2">
                    View Full Guide & Configure
                    <CaretRight size={14} />
                  </button>
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="import" className="space-y-4">
            {/* CSV Import */}
            <div className="border border-stone-200 rounded-md p-4 bg-white">
              <h4 className="font-medium text-[#1C1917] mb-3 flex items-center gap-2">
                <Database size={18} className="text-[#3E5245]" />
                Import from CSV
              </h4>
              <p className="text-sm text-[#57534E] mb-3">
                Upload a CSV file with columns: platform, guest_name, rating, review_text, review_date, stay_date, room_type
              </p>
              <label className="block">
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleFileUpload}
                  className="block w-full text-sm text-[#57534E] file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-[#3E5245] file:text-white hover:file:bg-[#2A3B30] cursor-pointer"
                  data-testid="csv-upload-input"
                />
              </label>
            </div>

            {/* Manual Entry */}
            <div className="border border-stone-200 rounded-md p-4 bg-white">
              <div className="flex items-center justify-between mb-3">
                <h4 className="font-medium text-[#1C1917] flex items-center gap-2">
                  <Plus size={18} className="text-[#3E5245]" />
                  Add Review Manually
                </h4>
                <button
                  onClick={() => setShowManualImport(!showManualImport)}
                  className="text-sm text-[#3E5245] hover:underline"
                >
                  {showManualImport ? "Hide" : "Show Form"}
                </button>
              </div>

              {showManualImport && (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-medium text-[#57534E]">Platform</label>
                      <Select
                        value={manualReview.platform}
                        onValueChange={(value) => setManualReview(prev => ({ ...prev, platform: value }))}
                      >
                        <SelectTrigger className="border-stone-200 mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {Object.entries(PLATFORMS).map(([key, config]) => (
                            <SelectItem key={key} value={key}>{config.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <label className="text-xs font-medium text-[#57534E]">Rating</label>
                      <Select
                        value={String(manualReview.rating)}
                        onValueChange={(value) => setManualReview(prev => ({ ...prev, rating: parseInt(value) }))}
                      >
                        <SelectTrigger className="border-stone-200 mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {[5, 4, 3, 2, 1].map((r) => (
                            <SelectItem key={r} value={String(r)}>{r} Star{r !== 1 ? 's' : ''}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div>
                    <label className="text-xs font-medium text-[#57534E]">Guest Name</label>
                    <Input
                      value={manualReview.guest_name}
                      onChange={(e) => setManualReview(prev => ({ ...prev, guest_name: e.target.value }))}
                      placeholder="John Doe"
                      className="border-stone-200 mt-1"
                      data-testid="manual-guest-name"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-medium text-[#57534E]">Review Text</label>
                    <Textarea
                      value={manualReview.review_text}
                      onChange={(e) => setManualReview(prev => ({ ...prev, review_text: e.target.value }))}
                      placeholder="Write the review text here..."
                      className="border-stone-200 mt-1 min-h-[100px]"
                      data-testid="manual-review-text"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-medium text-[#57534E]">Stay Date</label>
                      <Input
                        value={manualReview.stay_date}
                        onChange={(e) => setManualReview(prev => ({ ...prev, stay_date: e.target.value }))}
                        placeholder="January 2026"
                        className="border-stone-200 mt-1"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-[#57534E]">Room Type</label>
                      <Input
                        value={manualReview.room_type}
                        onChange={(e) => setManualReview(prev => ({ ...prev, room_type: e.target.value }))}
                        placeholder="Deluxe Room"
                        className="border-stone-200 mt-1"
                      />
                    </div>
                  </div>

                  <button
                    onClick={handleManualImport}
                    className="w-full bg-[#3E5245] text-white py-2 rounded-md hover:bg-[#2A3B30] transition-colors flex items-center justify-center gap-2"
                    data-testid="import-manual-review-btn"
                  >
                    <Plus size={16} />
                    Import Review
                  </button>
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      )}
    </DialogContent>
  );
};

// Branding Panel Component
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
        app_name: branding.app_name || "Review Hub",
        subtitle: branding.subtitle || "Manage all your guest reviews in one place",
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
                <h3 className="text-sm font-semibold text-white font-['Work_Sans']">{form.app_name || "Review Hub"}</h3>
                <p className="text-xs" style={{ color: "rgba(255,255,255,0.7)" }}>{form.subtitle || "Manage all your guest reviews in one place"}</p>
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
              placeholder="Review Hub"
              className="border-stone-200"
              data-testid="branding-app-name"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-[#1C1917] mb-1 block">Subtitle</label>
            <Input
              value={form.subtitle}
              onChange={(e) => setForm(prev => ({ ...prev, subtitle: e.target.value }))}
              placeholder="Manage all your guest reviews in one place"
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

// Main Dashboard Component
const Dashboard = () => {
  const [reviews, setReviews] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedReview, setSelectedReview] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showNotificationSettings, setShowNotificationSettings] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [showAnalytics, setShowAnalytics] = useState(false);
  const [showReports, setShowReports] = useState(false);
  const [showIntegrations, setShowIntegrations] = useState(false);
  const [showBranding, setShowBranding] = useState(false);
  const [branding, setBranding] = useState(null);
  const [templateTextToApply, setTemplateTextToApply] = useState(null);
  const [filters, setFilters] = useState({
    platform: "all",
    status: "all"
  });

  const handleApplyTemplate = (templateContent) => {
    setTemplateTextToApply(templateContent);
  };

  const handleSyncComplete = () => {
    fetchReviews();
    fetchStats();
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

  const fetchBranding = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/branding`);
      setBranding(response.data);
    } catch (error) {
      console.error("Error fetching branding:", error);
    }
  }, []);

  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      await seedReviews();
      await fetchReviews();
      await fetchStats();
      await fetchBranding();
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
    <div className="min-h-screen bg-stone-50" data-testid="review-dashboard">
      {/* Header */}
      <header className="bg-white border-b border-stone-200/80 px-6 py-3 sticky top-0 z-40 shadow-sm" data-testid="dashboard-header">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {branding?.logo_url ? (
              <img src={branding.logo_url} alt="Logo" className="w-9 h-9 rounded-lg object-cover" data-testid="header-logo" />
            ) : (
              <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ backgroundColor: branding?.primary_color || "#3E5245" }}>
                <Buildings size={20} className="text-white" weight="fill" />
              </div>
            )}
            <div>
              <h1 className="text-base font-semibold tracking-tight text-stone-900" data-testid="header-app-name">{branding?.app_name || "Review Hub"}</h1>
              <p className="text-[11px] text-stone-400" data-testid="header-subtitle">{branding?.subtitle || "Manage all your guest reviews in one place"}</p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Dialog open={showAnalytics} onOpenChange={setShowAnalytics}>
              <DialogTrigger asChild>
                <button className="nav-btn nav-btn-primary" data-testid="analytics-btn">
                  <ChartBar size={15} />
                  Analytics
                </button>
              </DialogTrigger>
              <AnalyticsPanel 
                isOpen={showAnalytics} 
                onClose={() => setShowAnalytics(false)}
              />
            </Dialog>
            <Dialog open={showTemplates} onOpenChange={setShowTemplates}>
              <DialogTrigger asChild>
                <button className="nav-btn" data-testid="templates-btn">
                  <FileText size={15} />
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
                <button className="nav-btn" data-testid="notification-settings-btn">
                  <Bell size={15} />
                  Alerts
                </button>
              </DialogTrigger>
              <NotificationSettings 
                isOpen={showNotificationSettings} 
                onClose={() => setShowNotificationSettings(false)} 
              />
            </Dialog>
            <Dialog open={showReports} onOpenChange={setShowReports}>
              <DialogTrigger asChild>
                <button className="nav-btn" data-testid="reports-btn">
                  <CalendarBlank size={15} />
                  Reports
                </button>
              </DialogTrigger>
              <ReportsSettings 
                isOpen={showReports} 
                onClose={() => setShowReports(false)} 
              />
            </Dialog>
            <Dialog open={showIntegrations} onOpenChange={setShowIntegrations}>
              <DialogTrigger asChild>
                <button className="nav-btn" data-testid="integrations-btn">
                  <PlugsConnected size={15} />
                  Integrations
                </button>
              </DialogTrigger>
              <IntegrationsPanel 
                isOpen={showIntegrations} 
                onClose={() => setShowIntegrations(false)}
                onSyncComplete={handleSyncComplete}
              />
            </Dialog>
            <Dialog open={showBranding} onOpenChange={setShowBranding}>
              <DialogTrigger asChild>
                <button className="nav-btn" data-testid="branding-btn">
                  <Palette size={15} />
                  Branding
                </button>
              </DialogTrigger>
              <BrandingPanel
                isOpen={showBranding}
                onClose={() => setShowBranding(false)}
                branding={branding}
                onBrandingUpdate={(updated) => setBranding(updated)}
              />
            </Dialog>
            <button
              onClick={() => {
                fetchReviews();
                fetchStats();
                toast.success("Reviews refreshed!");
              }}
              className="nav-btn"
              data-testid="refresh-btn"
            >
              <ArrowsClockwise size={15} />
              Refresh
            </button>
          </div>
        </div>
      </header>

      <div className="p-4 sm:p-6 lg:p-8">
        {/* Stats Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
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
          <div className="md:col-span-4 bg-white border border-stone-200/80 rounded-xl shadow-card overflow-hidden" data-testid="review-list-panel">
            {/* Filters */}
            <div className="p-4 border-b border-stone-100 bg-stone-50/50">
              <div className="flex items-center gap-2 mb-2.5">
                <FunnelSimple size={15} className="text-stone-400" />
                <span className="text-xs font-semibold uppercase tracking-wider text-stone-400">Filters</span>
              </div>
              <div className="flex gap-2">
                <Select
                  value={filters.platform}
                  onValueChange={(value) => setFilters(prev => ({ ...prev, platform: value }))}
                  data-testid="platform-filter"
                >
                  <SelectTrigger className="flex-1 bg-white border-stone-200 h-8 text-xs">
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
                  <SelectTrigger className="flex-1 bg-white border-stone-200 h-8 text-xs">
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
            <ScrollArea className="h-[calc(100vh-340px)] custom-scrollbar" data-testid="review-list">
              {isLoading ? (
                <div className="p-8 text-center">
                  <ArrowsClockwise size={24} className="mx-auto mb-2 animate-spin text-stone-300" />
                  <p className="text-sm text-stone-400">Loading reviews...</p>
                </div>
              ) : reviews.length === 0 ? (
                <div className="p-8 text-center">
                  <ChatText size={24} className="mx-auto mb-2 text-stone-300" />
                  <p className="text-sm text-stone-400">No reviews found</p>
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
          <div className="md:col-span-8 bg-white border border-stone-200/80 rounded-xl shadow-card p-6 flex flex-col" data-testid="review-detail-panel">
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

      {/* Powered By Footer */}
      {branding?.powered_by_visible && branding?.powered_by_text && (
        <div className="text-center py-2 border-t border-stone-100 bg-white/80" data-testid="powered-by-footer">
          <span className="text-[11px] text-stone-400">Powered by {branding.powered_by_text}</span>
        </div>
      )}

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
