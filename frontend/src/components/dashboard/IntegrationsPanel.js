import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle, WarningCircle, ArrowsClockwise, Plus, Link, LinkBreak, CloudArrowUp, Info, CaretRight, X, PlugsConnected, Database, Code, CopySimple, Eye, Key, Trash, Copy, Star, Buildings, WebhookLogo, Gear, ArrowSquareOut } from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { ScrollArea } from "@/components/ui/scroll-area";
import { API, formatApiErrorDetail, PLATFORMS } from "./config";

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


export { IntegrationsPanel };
