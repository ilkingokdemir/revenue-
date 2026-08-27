// Dashboard view router — extracted from App.js (iter 507 refactor).
// Renders the activeView-conditional panel blocks. Complex state-bound views
// (dashboard home, reviews, analytics/templates/approvals/integrations) stay in App.js.
import {
  ABTestPanel,
  AIPredictionsPanel,
  AIPricingV2Panel,
  AIReplyRobotPanel,
  AccountingExportPanel,
  AccountingPanel,
  AddOnsPanel,
  AdminPanel,
  AgencyPortalAdminPanel,
  AgentsB2BPanel,
  AgentsPanel,
  AllotmentsPanel,
  AnomalyPanel,
  ArReconPanel,
  ArrivalsCockpit,
  AssetRegisterPanel,
  AttributionPanel,
  AuditTrailPanel,
  AutomationHubPanel,
  AutomationPanel,
  AvailabilityCalendarPanel,
  BanquetOrdersPanel,
  BasePriceCurvePanel,
  BeachPosPanel,
  BiFeedPanel,
  BirthdayPanel,
  BookingEngineAdmin,
  BookingEnginePanel,
  BookingEngineV2Panel,
  BookingTimeline,
  BrandPortalPanel,
  BrandVoicePanel,
  BrandingPanel,
  BudgetActualPanel,
  BugTrackerPanel,
  CISlotsPanel,
  CampaignsPanel,
  CancelInsurancePanel,
  CarbonReportingV2Panel,
  CardVaultPanel,
  CashDrawerPanel,
  CashFlowForecast,
  ChainBenchmarkPanel,
  ChannelHealthPanel,
  ChannelInboundPanel,
  ChannelManagerHub,
  ChannelManagerV2Panel,
  ChannelMappingsPanel,
  ChannelParityPanel,
  ChannelRestrictionsPanel,
  ChannelRevenuePanel,
  ChannelSettingsPanel,
  ChargebackPanel,
  ChatbotAutomationPanel,
  CityLedgerPanel,
  CleaningChecklistsPanel,
  CollisionsPanel,
  CommissionReconPanel,
  ComplianceRegister,
  CompsetPanel,
  ConciergeAnalyticsPanel,
  ConciergeInboxPanel,
  ConferenceSCPanel,
  CopilotLibraryPanel,
  CurrencyFxPanel,
  CurrencyPanel,
  CustomDashboardBuilder,
  DemoLeadsPanel,
  DepositAutomationPanel,
  DepositLedgerPanel,
  DepositPolicyPanel,
  DevPortalAdminPanel,
  DigitalAuthPanel,
  DirectConversionPanel,
  DiscountStackPanel,
  EUCompliancePanel,
  EventsPanel,
  ExpenseManagement,
  ExternalLoyaltyPanel,
  FinancePL,
  FinancePanel,
  FnbPosHubPanel,
  FnbTabsPanel,
  FolioLivePanel,
  FolioSplitPanel,
  ForecastPanel,
  ForecastPlansPanel,
  ForecastV2Panel,
  GapFillerPanel,
  GdprPanel,
  GiftCardsPanel,
  GlitchLogPanel,
  GroupBlocksPanel,
  GroupBookingsPanel,
  GroupRequestsPanel,
  GroupRoomingImportPanel,
  GroupRoomingWizPanel,
  GuestAppPanel,
  GuestCRM360Panel,
  GuestJourneyPanel,
  GuestPortalV2Panel,
  GuestPrefsPanel,
  GuestProfilesPanel,
  GuestRfmPanel,
  GuestRiskPanel,
  GuestSegmentsPanel,
  HelpGuidePanel,
  HkDispatchPanel,
  HousekeepingHubPanel,
  HousekeepingRoutePanel,
  HurdleLrvPanel,
  ImportModulePanel,
  IntradayRepricePanel,
  LastDayLadderPanel,
  StorefrontVerifyPanel,
  SecondWriterPanel,
  AnnualPlanPanel,
  RampLadderPanel,
  WriteLeasePanel,
  MorningKarnePanel,
  LiveSmokePanel,
  NoShowRiskPanel,
  SegmentGroupPanel,
  RateMixPanel,
  RmsUpliftPanel,
  Forecast730Panel,
  CompAnomalyPanel,
  ProfitBenchmarkPanel,
  SentimentPricingPanel,
  MobileApprovalsPanel,
  IpAllowlistPanel,
  KDSPanel,
  KeyFiguresPanel,
  LateCheckoutOfferPanel,
  LateCheckoutPanel,
  LaundryManagement,
  LaundrySettingsPanel,
  LeadFunnelPanel,
  LeakagePanel,
  LegalDocumentsPanel,
  LiveChatInboxPanel,
  LockSDKPanel,
  LogbookPanel,
  LongStayPanel,
  LostDemandPanel,
  LostFoundPanel,
  LowStockPanel,
  LoyaltyAutoPanel,
  LoyaltyPanel,
  LoyaltyTierPanel,
  LoyaltyTiersPanel,
  LoyaltyV2Panel,
  MarketingVideosPanel,
  MarketplacePanel,
  MeetingsSalesPanel,
  MenuEngineeringPanel,
  MessagingHub,
  MewsUniversityPanel,
  MidStaySurveyPanel,
  MinRateFloorsPanel,
  MobileCompanion,
  MorningBriefPanel,
  MsgTemplatesPanel,
  MultiPropertyRollupPanel,
  MyRatesPanel,
  MyTasksPanel,
  NightAuditClosePanel,
  NightAuditPanel,
  NightlyRecapPanel,
  NoShowPanel,
  OTACommissionPanel,
  OTAStopSellForecastPanel,
  OnboardingWizard,
  OpenPricingPanel,
  OperationsHubPanel,
  OpsQuickActionsPanel,
  OpsV2Panel,
  OtaHealthPanel,
  OwnerPortalPanel,
  OwnerPulseAdminPanel,
  OwnerRatesAdminPanel,
  OwnerSummaryPanel,
  POSPanel,
  PaceReports,
  ParityHeatmapPanel,
  PartnerWebhooksPanel,
  PassOverDuties,
  PaymentsPanel,
  PayrollManagement,
  PayrollRateMatrix,
  PmsCrsSyncPanel,
  PmsProPanel,
  PoliciesPanel,
  PortfolioBoardPanel,
  PreArrivalDripPanel,
  PreAuthPanel,
  PreventiveMaintenancePanel,
  PricingExplainPanel,
  ProfitPricingPanel,
  AbsPanel,
  RevPAMPanel,
  DecisionAssurancePanel,
  DataQualityPanel,
  GroupSalesPanel,
  OverbookingControlPanel,
  RoomTypeForecastPanel,
  ProfitOSPanel,
  PromoCodesPanel,
  PropertyMappingPanel,
  PublicApiPortalPanel,
  PublicEventsPanel,
  RMLabPanel,
  RateManagerPanel,
  RateStructurePanel,
  RebookPanel,
  ReceptionReport,
  RecipeCogsPanel,
  ReportsHub,
  ReportsSettings,
  ResQualityPanel,
  RestrictionAdvisorPanel,
  RevenueHealthPanel,
  RevenuePanel,
  RevenueProtectionPanel,
  RmsComparisonPanel,
  RmsSetupWizard,
  CmSetupWizard,
  ChannelListingPanel,
  IcalSyncPanel,
  SiteBuilderPanel,
  TerminalPanel,
  AiCopilotPanel,
  PresetsPanel,
  PriceGuardsPanel,
  MarketingRadarPanel,
  BIChatPanel,
  ParkingRmsPanel,
  ErrorSentinelPanel,
  DemandCalendarPanel,
  LosWashMetricsPanel,
  FunctionSpacePanel,
  HotelRunnerPanel,
  CloudbedsPanel,
  ConnectorCatalogPanel,
  PlatformAdminPanel,
  SystemHealthPanel,
  PmsConnectHub,
  MorningReportPanel,
  TrustCenterPanel,
  SimulatorPanel,
  RevenueStrategistPanel,
  ReviewAgentPanel,
  ReviewSentimentPanel,
  RolesPermissionsPanel,
  RoomQRPanel,
  SRVoucherPanel,
  ScheduledReports,
  ScheduledReportsPanel,
  SecurityOwnerPanel,
  SelfCheckInPipelinePanel,
  SelfCheckinAutoPanel,
  SentimentHeatmapPanel,
  ServiceRecoveryPanel,
  SettingsHubPanel,
  SetupWizardPanel,
  ShiftScheduler,
  SiteFeasibilityPanel,
  SiteMinderPanel,
  SmartLocksPanel,
  SmartRoomsPanel,
  SopsPanel,
  SpaActivitiesPanel,
  SpacesPanel,
  StaffContractsPanel,
  StaffManagementPanel,
  StaffOnboardingAdminPanel,
  StaffOpsPanel,
  StaffPerformancePanel,
  StayExtPanel,
  StockManagementPanel,
  SurveyPanel,
  SustainabilityPanel,
  SyncLogPanel,
  SyncQueuePanel,
  TRCompliancePanel,
  TaxConfigPanel,
  TaxPresetsPanel,
  TaxReportsV2Panel,
  TeamChatPanel,
  TemplateCustomizer,
  TemplateGallery,
  Tier1DashboardPanel,
  TimeSlotsPanel,
  TippingPanel,
  TwoFactorAuthPanel,
  UnifiedInboxPanel,
  VacationRentalPanel,
  VccPanel,
  VoiceConciergePanel,
  WaitlistPanel,
  WalkInPanel,
  WebConciergeAdminPanel,
  WebPushPanel,
  WhatsAppVoicePanel,
  WholesalerHubPanel,
} from "./lazyPanels";
import { DamageProtectionPanel } from "./components/dashboard/DamageProtectionPanel";
import { DepartmentShortcutsPanel } from "./components/dashboard/DepartmentShortcutsPanel";
import { GroupDisplacementPanel } from "./components/dashboard/GroupDisplacementPanel";
import { NotificationSettings } from "@/panels/ReviewToolsPanels";
import { IntegrationGuidePanel } from "@/panels/SystemToolsPanels";
import { ChatText } from "@phosphor-icons/react";

export default function DashboardViews({ activeView, activePropertyId, setActivePropertyId, properties, branding, setBranding, user, permissions, navigate, setActiveView, commandItems, fetchDeptShortcuts }) {
  return (
    <>
        {/* TR Compliance — KBS + e-Fatura */}
        {activeView === "tr-compliance" && (
          <TRCompliancePanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
            hotelName={properties?.find?.((p) => p.id === activePropertyId)?.name || branding?.app_name}
          />
        )}

        {/* EU Compliance — 7 country hub */}
        {activeView === "eu-compliance" && (
          <EUCompliancePanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
            hotelName={properties?.find?.((p) => p.id === activePropertyId)?.name || branding?.app_name}
          />
        )}

        {/* AI Predictions — Cancel Risk + Upsell Propensity */}
        {activeView === "ai-predictions" && (
          <AIPredictionsPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
            hotelName={properties?.find?.((p) => p.id === activePropertyId)?.name || branding?.app_name}
          />
        )}

        {/* Channel Revenue — Open Pricing + Yield Rules */}
        {activeView === "channel-revenue" && (
          <ChannelRevenuePanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
            hotelName={properties?.find?.((p) => p.id === activePropertyId)?.name || branding?.app_name}
          />
        )}

        {/* Yield Guard — Hurdle Rate & Last Room Value */}
        {activeView === "hurdle-lrv" && (
          <HurdleLrvPanel propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")} />
        )}

        {/* KDS — Kitchen Display + 86 List + Recipes */}
        {activeView === "kds" && (
          <KDSPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
            hotelName={properties?.find?.((p) => p.id === activePropertyId)?.name || branding?.app_name}
          />
        )}

        {/* Loyalty v2 — Tier Benefits + Referrals + Dynamic Packaging */}
        {activeView === "loyalty-v2" && (
          <LoyaltyV2Panel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
            hotelName={properties?.find?.((p) => p.id === activePropertyId)?.name || branding?.app_name}
          />
        )}

        {/* External Loyalty — Marriott Bonvoy, Hilton, IHG, Accor, Hyatt, Wyndham, BW */}
        {activeView === "external-loyalty" && (
          <ExternalLoyaltyPanel
            activePropertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* OTA Commission Dashboard — net revenue per channel */}
        {activeView === "ota-commission" && (
          <OTACommissionPanel activePropertyId={activePropertyId} />
        )}

        {/* Direct Booking Conversion Engine — OTA→Direct kupon motoru */}
        {activeView === "direct-conversion" && <DirectConversionPanel />}

        {/* SiteMinder Middleware Translator Adapter */}
        {activeView === "siteminder" && (
          <SiteMinderPanel activePropertyId={activePropertyId} />
        )}

        {/* Müsaitlik Takvimi — aylık doluluk ısı haritası (iter 378'de canlandırıldı) */}
        {activeView === "availability-calendar" && (
          <AvailabilityCalendarPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Sentiment Heatmap — Cross-channel guest voice */}
        {activeView === "sentiment-heatmap" && (
          <SentimentHeatmapPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
            hotelName={properties?.find?.((p) => p.id === activePropertyId)?.name || branding?.app_name}
          />
        )}

        {/* Self Check-in v2 — Pre-arrival pipeline */}
        {activeView === "self-checkin-v2" && (
          <SelfCheckInPipelinePanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
            hotelName={properties?.find?.((p) => p.id === activePropertyId)?.name || branding?.app_name}
          />
        )}

        {/* Brand Portal — Chain HQ rollup + white-label */}
        {activeView === "brand-portal" && (
          <BrandPortalPanel
            hotelName={branding?.app_name}
          />
        )}

        {/* Ops — Misafir Talepleri + Bakım İş Emirleri + Çamaşır PAR + HK Denetim */}
        {(activeView === "ops-v2" || activeView === "maintenance") && (
          <OpsV2Panel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
            hotelName={properties?.find?.((p) => p.id === activePropertyId)?.name || branding?.app_name}
            properties={properties}
          />
        )}

        {/* Glitch Log & Shift Handover (Flexkeeping-style) */}
        {activeView === "glitch-log" && (
          <GlitchLogPanel propertyId={activePropertyId || "all"} />
        )}

        {/* SOP Library (Standard Operating Procedures) */}
        {activeView === "sops" && (
          <SopsPanel propertyId={activePropertyId || "all"} user={user} />
        )}

        {/* Automation Rules (event-driven workflows) */}
        {["automation-hub", "automation-rules"].includes(activeView) && (
          <AutomationHubPanel key={activeView} initialView={activeView}
            propertyId={activePropertyId || "all"} user={user} onNavigate={navigate} />
        )}

        {/* Team Chat (multi-channel internal communication) */}
        {activeView === "team-chat" && (
          <div className="p-5 max-w-[1400px] mx-auto">
            <div className="mb-4">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
                <ChatText size={12} weight="fill" className="text-blue-500" />
                <span>Collaboration Suite</span>
              </div>
              <h1 className="text-2xl font-semibold text-stone-900">Team Chat</h1>
              <p className="text-sm text-stone-500 mt-1 max-w-2xl">
                Departman bazlı kanal sohbeti — vardiyalar arası iletişim, hızlı bildirim ve takip. Real-time polling (4sn).
              </p>
            </div>
            <TeamChatPanel user={user} />
          </div>
        )}

        {/* Guest CRM 360 (Revinate-killer) */}
        {activeView === "crm-360" && <GuestCRM360Panel user={user} />}

        {/* Channel Manager v2 (production OTA framework) */}
        {activeView === "channels-v2" && <ChannelManagerV2Panel />}

        {/* ===== Competitor Parity v3 (Iter 277) ===== */}
        {activeView === "booking-engine-v2" && (
          <BookingEngineV2Panel propertyId={activePropertyId || "all"} />
        )}
        {activeView === "owner-portal" && <OwnerPortalPanel />}
        {activeView === "agency-portal" && <AgencyPortalAdminPanel />}
        {activeView === "web-concierge" && <WebConciergeAdminPanel />}
        {activeView === "review-agent" && <ReviewAgentPanel />}
        {activeView === "open-pricing" && (
          <OpenPricingPanel propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")} />
        )}
        {activeView === "beach-pos" && (
          <BeachPosPanel propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")} />
        )}
        {activeView === "public-events" && (
          <PublicEventsPanel propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")} />
        )}
        {activeView === "spa-activities" && (
          <SpaActivitiesPanel propertyId={activePropertyId || "all"} />
        )}
        {activeView === "loyalty-tiers-v2" && <LoyaltyTiersPanel />}
        {activeView === "budget-actual" && (
          <BudgetActualPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}
        {activeView === "compset" && (
          <CompsetPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}
        {activeView === "partner-webhooks" && <PartnerWebhooksPanel />}
        {["automation-analytics", "automation-roi", "automation-settings"].includes(activeView) && (
          <AutomationHubPanel key={activeView} initialView={activeView}
            propertyId={activePropertyId || "all"} user={user} onNavigate={navigate} />
        )}
        {activeView === "leakage-audit" && (
          <LeakagePanel propertyId={activePropertyId || "all"} />
        )}
        {activeView === "guest-risk" && (
          <GuestRiskPanel propertyId={activePropertyId || "all"} />
        )}
        {activeView === "waitlist" && (
          <WaitlistPanel propertyId={activePropertyId || "all"} />
        )}
        {activeView === "hk-dispatch" && (
          <HkDispatchPanel propertyId={activePropertyId || "all"} />
        )}
        {activeView === "res-quality" && (
          <ResQualityPanel propertyId={activePropertyId || "all"} />
        )}
        {activeView === "guest-segments" && <GuestSegmentsPanel />}
        {activeView === "channel-health" && (
          <ChannelHealthPanel propertyId={activePropertyId || "all"} />
        )}
        {activeView === "key-figures" && (
          <KeyFiguresPanel propertyId={activePropertyId || "all"} />
        )}
        {activeView === "comp-radar" && (
          <CompsetPanel propertyId={activePropertyId || "default"} initialTab="radar" />
        )}
        {activeView === "meetings-sales" && (
          <MeetingsSalesPanel propertyId={activePropertyId || "all"} />
        )}
        {activeView === "fnb-pos-hub" && (
          <FnbPosHubPanel propertyId={activePropertyId || "all"} />
        )}
        {activeView === "carbon-v2" && (
          <CarbonReportingV2Panel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Forecast v2 — 24-month horizon + Demand Calendar + Pickup Curve */}
        {activeView === "forecast-v2" && (
          <ForecastV2Panel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Anomaly Radar — statistical z-score detection + GPT root-cause explain */}
        {activeView === "anomaly" && (
          <AnomalyPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Digital Tipping — Stripe-powered guest-to-staff tipping */}
        {activeView === "tipping" && (
          <TippingPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Guest Portal v2 — Self-Modify + Cancel */}
        {activeView === "guest-portal-v2" && (
          <GuestPortalV2Panel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Conference S&C — MICE Proposal Builder */}
        {activeView === "conference-sc" && (
          <ConferenceSCPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Banquet Event Orders */}
        {activeView === "banquet-orders" && (
          <BanquetOrdersPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Help & user guide */}
        {activeView === "help-guide" && <HelpGuidePanel />}

        {/* Site Feasibility & Investor Analysis */}
        {activeView === "site-feasibility" && (
          <SiteFeasibilityPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Auto pre-arrival self check-in trigger */}
        {activeView === "self-checkin-auto" && (
          <SelfCheckinAutoPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Hardware Lock SDK adapter (Batch 39) */}
        {activeView === "lock-sdk" && (
          <LockSDKPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Recipe COGS & modifier trees (Batch 40) */}
        {activeView === "recipe-cogs" && (
          <RecipeCogsPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Voice Concierge — Whisper STT + LLM (Batch 42) */}
        {activeView === "voice-concierge" && (
          <VoiceConciergePanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
            currentUser={user}
          />
        )}

        {/* WhatsApp Voice Concierge — Twilio inbound webhook admin */}
        {activeView === "whatsapp-voice" && (
          <WhatsAppVoicePanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* AI Copilot Library */}
        {activeView === "copilot" && (
          <CopilotLibraryPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Image AI Cleanliness Scoring — merged into Housekeeping hub */}

        {/* HK Turnover — merged into Housekeeping hub */}

        {/* AI Pricing Explainability */}
        {activeView === "pricing-explain" && (
          <PricingExplainPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* F&B Tab Transfer */}
        {activeView === "fnb-tabs" && (
          <FnbTabsPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* BI Feed (Power BI / Tableau / Excel) */}
        {activeView === "bi-feed" && (
          <BiFeedPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* My Tasks */}
        {activeView === "my-tasks" && (
          <MyTasksPanel user={user} />
        )}

        {/* Booking Calendar Timeline */}
        {activeView === "calendar" && (
          <BookingTimeline properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Revenue Management */}
        {activeView === "revenue" && (
          <RevenuePanel properties={properties} activePropertyId={activePropertyId} />
        )}


        {/* Integration Guide View */}
        {activeView === "guide" && (
          <IntegrationGuidePanel />
        )}

        {/* Alerts View */}
        {activeView === "alerts" && (
          <NotificationSettings isOpen={true} onClose={() => setActiveView("reviews")} />
        )}

        {/* Reports View */}
        {activeView === "reports" && (
          <ReportsSettings isOpen={true} onClose={() => setActiveView("reviews")} />
        )}

        {/* Branding View */}
        {activeView === "branding" && (
          <BrandingPanel isOpen={true} onClose={() => setActiveView("reviews")} branding={branding} onBrandingUpdate={(updated) => setBranding(updated)} />
        )}

        {/* Team View - Enhanced Staff Management */}
        {activeView === "team" && (
          <StaffManagementPanel properties={properties} user={user} activePropertyId={activePropertyId} />
        )}

        {/* Admin Panel */}
        {activeView === "admin-panel" && (
          <AdminPanel properties={properties} user={user} activePropertyId={activePropertyId} />
        )}

        {/* Settings Hub */}
        {activeView === "settings-hub" && (
          <SettingsHubPanel />
        )}

        {/* Sync Log View */}
        {activeView === "synclog" && (
          <SyncLogPanel />
        )}

        {/* Property Mapping View */}
        {activeView === "mapping" && (
          <PropertyMappingPanel user={user} />
        )}

        {/* Booking Engine View */}
        {activeView === "booking" && (
          <BookingEnginePanel properties={properties} />
        )}

        {/* Templates Gallery View */}
        {activeView === "website-templates" && (
          <TemplateGallery properties={properties} />
        )}

        {/* Template Customizer View */}
        {activeView === "customize-template" && (
          <TemplateCustomizer properties={properties} />
        )}

        {/* Promo Codes View */}
        {activeView === "promo-codes" && (
          <PromoCodesPanel properties={properties} />
        )}

        {/* Add-ons View */}
        {activeView === "add-ons" && (
          <AddOnsPanel properties={properties} />
        )}

        {/* Policies & Facilities View */}
        {activeView === "policies" && (
          <PoliciesPanel properties={properties} />
        )}

        {/* Guest Messaging Hub */}
        {activeView === "messaging" && (
          <MessagingHub properties={properties} user={user} activePropertyId={activePropertyId} />
        )}

        {/* AI Concierge Analytics */}
        {activeView === "concierge-analytics" && (
          <ConciergeAnalyticsPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Automation */}
        {activeView === "automation" && (
          <AutomationPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Chatbot Automation (Cloudbeds Guest Experience parity) */}
        {activeView === "chatbot-automation" && (
          <ChatbotAutomationPanel propertyId={activePropertyId} />
        )}

        {/* Live Chat Inbox (handoff sessions) */}
        {activeView === "live-chat-inbox" && (
          <LiveChatInboxPanel propertyId={activePropertyId} />
        )}

        {/* Channel Settings */}
        {activeView === "channel-settings" && (
          <ChannelSettingsPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Staff Performance */}
        {activeView === "staff-performance" && (
          <StaffPerformancePanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Guest Profiles */}
        {activeView === "guest-profiles" && (
          <GuestProfilesPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Guest Journey */}
        {activeView === "guest-journey" && (
          <GuestJourneyPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Campaigns */}
        {activeView === "campaigns" && (
          <CampaignsPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Guest App */}
        {activeView === "guest-app" && (
          <GuestAppPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Smart Locks / Digital Keys */}
        {activeView === "smart-locks" && (
          <SmartLocksPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Smart Rooms / IoT Control */}
        {activeView === "smart-rooms" && (
          <SmartRoomsPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Base Price Curve (18-month pricing) */}
        {activeView === "base-curve" && (
          <BasePriceCurvePanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Öğrenen Revenue Beyni — artık Revenue management içinde sekme (geriye dönük yönlendirme) */}
        {activeView === "revenue-brain" && (
          <RevenuePanel properties={properties} activePropertyId={activePropertyId} initialTab="learning-robot" />
        )}

        {/* RMS Rakip Karşılaştırma — satış demosu sayfası */}
        {activeView === "rms-comparison" && (
          <RmsComparisonPanel activePropertyId={activePropertyId} properties={properties} />
        )}
        {activeView === "rms-setup" && (
          <RmsSetupWizard activePropertyId={activePropertyId} properties={properties} />
        )}
        {activeView === "cm-setup" && (
          <CmSetupWizard activePropertyId={activePropertyId} properties={properties} />
        )}
        {activeView === "channel-listings" && (
          <ChannelListingPanel activePropertyId={activePropertyId} properties={properties} />
        )}
        {activeView === "ical-sync" && (
          <IcalSyncPanel activePropertyId={activePropertyId} properties={properties} />
        )}
        {activeView === "site-builder" && (
          <SiteBuilderPanel activePropertyId={activePropertyId} properties={properties} />
        )}
        {activeView === "payment-terminal" && (
          <TerminalPanel activePropertyId={activePropertyId} properties={properties} />
        )}
        {activeView === "ai-copilot" && (
          <AiCopilotPanel activePropertyId={activePropertyId} properties={properties} onNavigate={navigate} />
        )}
        {activeView === "property-presets" && (
          <PresetsPanel activePropertyId={activePropertyId} properties={properties} />
        )}
        {activeView === "price-guards" && (
          <PriceGuardsPanel activePropertyId={activePropertyId} properties={properties} />
        )}

        {/* Pazarlama Fırsat Radarı (IDeaS Marketing Optimization paritesi) */}
        {activeView === "marketing-radar" && (
          <MarketingRadarPanel activePropertyId={activePropertyId} properties={properties} />
        )}

        {/* Doğal Dil BI Chat (FLYR Insights paritesi) */}
        {activeView === "bi-chat" && (
          <BIChatPanel activePropertyId={activePropertyId} properties={properties} />
        )}

        {/* Otopark RMS (IDeaS Car Park paritesi) */}
        {activeView === "parking-rms" && (
          <ParkingRmsPanel activePropertyId={activePropertyId} properties={properties} />
        )}

        {/* Hata Nöbetçisi */}
        {activeView === "error-sentinel" && (
          <ErrorSentinelPanel />
        )}

        {/* Talep Takvimi (Duetto Advance paritesi) + Yetim Geceler */}
        {activeView === "demand-calendar" && (
          <DemandCalendarPanel activePropertyId={activePropertyId} properties={properties} />
        )}
        {activeView === "los-wash-metrics" && (
          <LosWashMetricsPanel activePropertyId={activePropertyId} properties={properties} />
        )}
        {activeView === "function-space" && (
          <FunctionSpacePanel activePropertyId={activePropertyId} properties={properties} />
        )}
        {activeView === "hotelrunner-live" && (
          <HotelRunnerPanel activePropertyId={activePropertyId} properties={properties} />
        )}
        {activeView === "cloudbeds-live" && (
          <CloudbedsPanel activePropertyId={activePropertyId} properties={properties} />
        )}
        {activeView === "connector-catalog" && (
          <ConnectorCatalogPanel activePropertyId={activePropertyId} properties={properties} onNavigate={navigate} />
        )}
        {activeView === "super-admin" && (
          <PlatformAdminPanel activePropertyId={activePropertyId} properties={properties} />
        )}
        {activeView === "system-health" && <SystemHealthPanel />}
        {activeView === "pms-connect" && (
          <PmsConnectHub activePropertyId={activePropertyId} properties={properties} />
        )}
        {activeView === "morning-report" && (
          <MorningReportPanel activePropertyId={activePropertyId} properties={properties} />
        )}
        {activeView === "trust-center" && (
          <TrustCenterPanel activePropertyId={activePropertyId} properties={properties} />
        )}
        {activeView === "rm-simulator" && (
          <SimulatorPanel activePropertyId={activePropertyId} properties={properties} />
        )}

        {/* Setup Wizard */}
        {activeView === "setup-wizard" && (
          <SetupWizardPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Department Shortcuts admin */}
        {activeView === "dept-shortcuts" && (
          <div className="p-6"><DepartmentShortcutsPanel catalog={commandItems} onChanged={fetchDeptShortcuts} /></div>
        )}

        {/* Group Displacement Analyzer */}
        {activeView === "group-displacement" && (
          <GroupDisplacementPanel activePropertyId={activePropertyId} />
        )}

        {/* Damage Protection */}
        {activeView === "damage-protection" && (
          <DamageProtectionPanel activePropertyId={activePropertyId} />
        )}

        {/* Stock Management */}
        {activeView === "stock-management" && (
          <StockManagementPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Housekeeping Hub — merged: Rooms · Turnover · Route · Checklists · AI Score · QR · Laundry */}
        {["housekeeping", "hk-turnover", "hk-route", "cleaning-checklists",
          "image-ai", "room-qr", "laundry", "laundry-settings"].includes(activeView) && (
          <HousekeepingHubPanel
            properties={properties}
            activePropertyId={activePropertyId}
            user={user}
            permissions={permissions}
            initialTab={{
              "housekeeping": "rooms",
              "hk-turnover": "turnover",
              "hk-route": "route",
              "cleaning-checklists": "checklists",
              "image-ai": "ai-score",
              "room-qr": "qr",
              "laundry": "laundry",
              "laundry-settings": "laundry-cfg",
            }[activeView] || "rooms"}
          />
        )}

        {activeView === "hk-route" && false && (
          <HousekeepingRoutePanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {activeView === "room-qr" && false && (
          <RoomQRPanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {activeView === "ai-reply-robot" && (
          <div className="p-6">
            <AIReplyRobotPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "service-recovery" && (
          <ServiceRecoveryPanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {activeView === "late-checkout" && (
          <LateCheckoutPanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {/* Iter 214 — Batch 1 Keyless Features */}
        {activeView === "tax-presets" && (
          <div className="p-6">
            <TaxPresetsPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "walkin" && (
          <div className="p-6">
            <WalkInPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "no-show" && (
          <div className="p-6">
            <NoShowPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "guest-prefs" && (
          <div className="p-6">
            <GuestPrefsPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "cleaning-checklists" && false && (
          <div className="p-6">
            <CleaningChecklistsPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "ops-quick" && (
          <div className="p-6">
            <OpsQuickActionsPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "group-rooming" && (
          <div className="p-6">
            <GroupRoomingImportPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "attribution" && (
          <div className="p-6">
            <AttributionPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "mews-university" && (
          <div className="p-6">
            <MewsUniversityPanel userRole={user?.role || ""} />
          </div>
        )}

        {activeView === "scheduled-reports" && (
          <div className="p-6">
            <ScheduledReportsPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : null}
              userEmail={user?.email || ""}
            />
          </div>
        )}

        {activeView === "custom-dashboard" && (
          <div className="p-6">
            <CustomDashboardBuilder
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : null}
            />
          </div>
        )}

        {activeView === "timeslots" && (
          <div className="p-6">
            <TimeSlotsPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "staff-ops" && (
          <div className="p-6">
            <StaffOpsPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "rev-protection" && (
          <div className="p-6">
            <RevenueProtectionPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "spaces" && (
          <div className="p-6">
            <SpacesPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "marketplace" && (
          <div className="p-6">
            <MarketplacePanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "multi-rollup" && (
          <div className="p-6">
            <MultiPropertyRollupPanel hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""} />
          </div>
        )}
        {activeView === "chain-benchmark" && <ChainBenchmarkPanel onNavigate={navigate} />}

        {activeView === "currency" && (
          <div className="p-6">
            <CurrencyPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "b2b-agents" && (
          <div className="p-6">
            <AgentsB2BPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "security-owner" && (
          <div className="p-6">
            <SecurityOwnerPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "preauth" && (
          <div className="p-6">
            <PreAuthPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "chargeback" && (
          <div className="p-6">
            <ChargebackPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "web-push" && (
          <div className="p-6">
            <WebPushPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
              currentUser={user}
            />
          </div>
        )}

        {activeView === "pms-crs" && (
          <div className="p-6">
            <PmsCrsSyncPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "pms-pro" && (
          <div className="p-6">
            <PmsProPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "public-api" && (
          <div className="p-6">
            <PublicApiPortalPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "mid-stay" && (
          <div className="p-6">
            <MidStaySurveyPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "folio-live" && (
          <div className="p-6">
            <FolioLivePanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "ab-test" && (
          <div className="p-6">
            <ABTestPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "pre-arrival" && (
          <div className="p-6">
            <PreArrivalDripPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "menu-engineering" && (
          <div className="p-6">
            <MenuEngineeringPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "sr-voucher" && (
          <div className="p-6">
            <SRVoucherPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "folio-split" && (
          <div className="p-6">
            <FolioSplitPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "loyalty-auto" && (
          <div className="p-6">
            <LoyaltyAutoPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "late-checkout-offer" && (
          <div className="p-6">
            <LateCheckoutOfferPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "ota-forecast" && (
          <div className="p-6">
            <OTAStopSellForecastPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "msg-templates" && (
          <div className="p-6">
            <MsgTemplatesPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "birthday" && (
          <div className="p-6">
            <BirthdayPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "low-stock" && (
          <div className="p-6">
            <LowStockPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "rebook" && (
          <div className="p-6">
            <RebookPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "stay-ext" && (
          <div className="p-6">
            <StayExtPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "long-stay" && (
          <div className="p-6">
            <LongStayPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "cancel-insurance" && (
          <div className="p-6">
            <CancelInsurancePanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "group-rooming-wiz" && (
          <div className="p-6">
            <GroupRoomingWizPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "tax-reports-v2" && (
          <div className="p-6">
            <TaxReportsV2Panel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "ci-slots" && (
          <div className="p-6">
            <CISlotsPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "tier1-dashboard" && (
          <div className="p-6">
            <Tier1DashboardPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {/* Maintenance — merged into Operasyon (ops-v2) tab "Misafir Talepleri" */}

        {/* Night Audit */}
        {activeView === "night-audit" && (
          <NightAuditPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Loyalty Program */}
        {activeView === "loyalty" && (
          <LoyaltyPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {activeView === "loyalty-tier" && (
          <LoyaltyTierPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Duty Logbook */}
        {activeView === "logbook" && (
          <LogbookPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Occupancy Forecast */}
        {activeView === "forecast" && (
          <ForecastPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Pace Reports — STLY + Pickup + Source */}
        {activeView === "pace-reports" && (
          <PaceReports
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {/* AI Dynamic Pricing v2 (GPT-5.2) */}
        {activeView === "ai-pricing-v2" && (
          <AIPricingV2Panel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {/* Rate Parity Heatmap */}
        {activeView === "parity-heatmap" && (
          <ParityHeatmapPanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {/* Morning Brief & Pricing Autopilot */}
        {activeView === "morning-brief" && (
          <MorningBriefPanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {/* Nightly Recap */}
        {activeView === "nightly-recap" && (
          <NightlyRecapPanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {/* Accounting Export */}
        {activeView === "accounting-export" && (
          <AccountingExportPanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {/* RM Lab — Forecast Accuracy + Marketing Automation */}
        {activeView === "rm-lab" && (
          <RMLabPanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {/* Concierge Inbox — Admin view of AI guest chats */}
        {activeView === "concierge-inbox" && (
          <ConciergeInboxPanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {/* Group Requests & Allotments — B2B / corporate / wedding */}
        {activeView === "group-requests" && (
          <GroupRequestsPanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {/* Sustainability & ESG */}
        {activeView === "sustainability" && (
          <SustainabilityPanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {/* Accounting */}
        {activeView === "accounting" && (
          <AccountingPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Point of Sale */}
        {activeView === "pos" && (
          <POSPanel properties={properties} user={user} activePropertyId={activePropertyId} />
        )}

        {/* Payment Gateway */}
        {activeView === "payments" && (
          <PaymentsPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Rate Manager */}
        {activeView === "rate-manager" && (
          <RateManagerPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* My Rates — Market-Pulse style 365-day grid with PMS Override + AI rate */}
        {activeView === "my-rates" && (
          <MyRatesPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Reports Centre */}
        {activeView === "reports-centre" && (
          <div className="p-6"><ReportsHub propertyId={activePropertyId} /></div>
        )}

        {/* Scheduled Reports */}
        {activeView === "scheduled-reports" && (
          <div className="p-6"><ScheduledReports propertyId={activePropertyId} /></div>
        )}

        {/* Mobile Companion */}
        {activeView === "mobile-companion" && (
          <div className="p-6"><MobileCompanion propertyId={activePropertyId} /></div>
        )}

        {/* Operations Hub */}
        {activeView === "operations-hub" && (
          <OperationsHubPanel properties={properties} activePropertyId={activePropertyId} user={user} />
        )}

        {/* Finance */}
        {activeView === "finance" && (
          <FinancePanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Finance P&L */}
        {activeView === "finance-pl" && (
          <div className="p-6"><FinancePL propertyId={activePropertyId} /></div>
        )}

        {/* Lost & Found */}
        {activeView === "lost-found" && (
          <LostFoundPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Events & Meeting Rooms */}
        {activeView === "events" && (
          <EventsPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Booking Engine Admin */}
        {activeView === "booking-engine-admin" && (
          <BookingEngineAdmin properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Guest Satisfaction Surveys */}
        {activeView === "surveys" && (
          <SurveyPanel properties={properties} user={user} activePropertyId={activePropertyId} />
        )}

        {/* Shift Scheduler */}
        {activeView === "shift-scheduler" && (
          <div className="p-6"><ShiftScheduler propertyId={activePropertyId} /></div>
        )}

        {/* Reception Report */}
        {activeView === "reception-report" && (
          <div className="p-6"><ReceptionReport propertyId={activePropertyId} /></div>
        )}

        {/* Pass Over Duties */}
        {activeView === "pass-over" && (
          <div className="p-6"><PassOverDuties propertyId={activePropertyId} user={user} /></div>
        )}

        {/* Compliance Register */}
        {activeView === "compliance" && (
          <div className="p-6"><ComplianceRegister propertyId={activePropertyId} user={user} /></div>
        )}

        {/* Laundry Management — merged into Housekeeping hub */}
        {activeView === "laundry" && false && (
          <div className="p-6"><LaundryManagement propertyId={activePropertyId} user={user} permissions={permissions} /></div>
        )}

        {/* Payroll Management */}
        {activeView === "payroll" && (
          <div className="p-6"><PayrollManagement propertyId={activePropertyId} user={user} /></div>
        )}

        {/* Expense Management */}
        {activeView === "expenses" && (
          <div className="p-6"><ExpenseManagement propertyId={activePropertyId} user={user} permissions={permissions} /></div>
        )}

        {/* Cash Flow Forecast */}
        {activeView === "cash-flow" && (
          <div className="p-6"><CashFlowForecast propertyId={activePropertyId} user={user} /></div>
        )}

        {/* Arrivals Cockpit */}
        {activeView === "arrivals" && (
          <div className="p-6"><ArrivalsCockpit propertyId={activePropertyId} user={user} /></div>
        )}

        {/* Staff Contracts */}
        {activeView === "contracts" && (
          <div className="p-6"><StaffContractsPanel propertyId={activePropertyId} user={user} /></div>
        )}

        {/* Legal Documents & Consents */}
        {activeView === "legal-docs" && (
          <div className="p-6"><LegalDocumentsPanel user={user} /></div>
        )}

        {/* Onboarding Review (admin/manager) */}
        {activeView === "onboarding-admin" && (
          <div className="p-6"><StaffOnboardingAdminPanel user={user} /></div>
        )}

        {/* Payroll Rate Matrix */}
        {activeView === "rate-matrix" && (
          <div className="p-6"><PayrollRateMatrix user={user} /></div>
        )}

        {/* City Ledger (Corporate AR) */}
        {activeView === "city-ledger" && (
          <CityLedgerPanel user={user} />
        )}

        {activeView === "ar-recon" && <ArReconPanel />}

        {activeView === "digital-auth" && <DigitalAuthPanel propertyId={activePropertyId || "all"} />}
        {activeView === "allotments" && <AllotmentsPanel propertyId={activePropertyId || "all"} />}
        {activeView === "forecast-plans" && <ForecastPlansPanel propertyId={activePropertyId || "all"} />}
        {activeView === "intraday-reprice" && <IntradayRepricePanel propertyId={activePropertyId || "all"} />}
        {activeView === "lastday-ladder" && <LastDayLadderPanel propertyId={activePropertyId || "default"} />}
        {activeView === "storefront-verify" && <StorefrontVerifyPanel propertyId={activePropertyId || "default"} />}
        {activeView === "second-writer" && <SecondWriterPanel propertyId={activePropertyId || "default"} />}
        {activeView === "annual-plan" && <AnnualPlanPanel propertyId={activePropertyId || "default"} />}
        {activeView === "ramp-ladder" && <RampLadderPanel propertyId={activePropertyId || "default"} />}
        {activeView === "write-lease" && <WriteLeasePanel propertyId={activePropertyId || "default"} />}
        {activeView === "morning-karne" && <MorningKarnePanel propertyId={activePropertyId || "default"} />}
        {activeView === "live-smoke" && <LiveSmokePanel />}
        {activeView === "noshow-risk" && <NoShowRiskPanel propertyId={activePropertyId || "default"} />}
        {activeView === "segment-group" && <SegmentGroupPanel propertyId={activePropertyId || "default"} />}
        {activeView === "rate-mix" && <RateMixPanel propertyId={activePropertyId || "all"} />}
        {activeView === "rms-uplift" && <RmsUpliftPanel propertyId={activePropertyId || "default"} />}
        {activeView === "forecast-730" && <Forecast730Panel propertyId={activePropertyId || "default"} />}
        {activeView === "comp-anomaly" && <CompAnomalyPanel propertyId={activePropertyId || "default"} />}
        {activeView === "profit-benchmark" && <ProfitBenchmarkPanel />}
        {activeView === "sentiment-pricing" && <SentimentPricingPanel propertyId={activePropertyId || "default"} />}
        {activeView === "mobile-approvals" && <MobileApprovalsPanel propertyId={activePropertyId || "default"} />}
        {activeView === "restriction-advisor" && <RestrictionAdvisorPanel propertyId={activePropertyId || "all"} />}
        {activeView === "gap-filler" && <GapFillerPanel propertyId={activePropertyId || "all"} />}
        {activeView === "lost-demand" && <LostDemandPanel propertyId={activePropertyId || "all"} />}
        {activeView === "demo-leads" && <DemoLeadsPanel />}
        {activeView === "revenue-strategist" && <RevenueStrategistPanel propertyId={activePropertyId || "default"} />}
        {activeView === "min-rates" && <MinRateFloorsPanel propertyId={activePropertyId || "default"} />}
        {activeView === "discount-stack" && <DiscountStackPanel propertyId={activePropertyId || "default"} />}
        {activeView === "owner-rates" && <OwnerRatesAdminPanel propertyId={activePropertyId || "default"} />}
        {activeView === "owner-pulse-admin" && <OwnerPulseAdminPanel propertyId={activePropertyId || "default"} />}
        {activeView === "portfolio-board" && <PortfolioBoardPanel />}

        {activeView === "vcc-automation" && (
          <VccPanel propertyId={activePropertyId || "all"} />
        )}

        {activeView === "owner-summary" && (
          <OwnerSummaryPanel propertyId={activePropertyId || "all"} />
        )}

        {/* Tax Configuration */}
        {activeView === "tax-config" && (
          <TaxConfigPanel propertyId={activePropertyId} user={user} />
        )}

        {/* Deposit Policies */}
        {activeView === "deposit-policies" && (
          <DepositPolicyPanel propertyId={activePropertyId} user={user} />
        )}

        {/* Multi-Currency / FX */}
        {activeView === "currency-fx" && (
          <CurrencyFxPanel user={user} />
        )}

        {/* Rate Structure / OTA Mapping */}
        {activeView === "rate-structure" && (
          <RateStructurePanel propertyId={activePropertyId} user={user} />
        )}

        {/* Group Bookings */}
        {activeView === "group-bookings" && (
          <GroupBookingsPanel propertyId={activePropertyId} user={user} />
        )}

        {/* GDPR Data Rights */}
        {activeView === "gdpr" && (
          <GdprPanel user={user} />
        )}

        {/* Iter 156 — Top-10 Competitor Gap Features */}
        {activeView === "night-audit-close" && <div className="p-6"><NightAuditClosePanel activePropertyId={activePropertyId} /></div>}
        {activeView === "deposit-ledger" && <div className="p-6"><DepositLedgerPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "commission-recon" && <div className="p-6"><CommissionReconPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "gift-cards" && <div className="p-6"><GiftCardsPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "review-sentiment" && <div className="p-6"><ReviewSentimentPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "guest-rfm" && <div className="p-6"><GuestRfmPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "preventive-maintenance" && <div className="p-6"><PreventiveMaintenancePanel activePropertyId={activePropertyId} /></div>}
        {activeView === "asset-register" && <div className="p-6"><AssetRegisterPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "cash-drawer" && <div className="p-6"><CashDrawerPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "two-factor-auth" && <div className="p-6"><TwoFactorAuthPanel /></div>}

        {/* Iter 157 — Remaining gaps: Revenue Health, IP Allowlist, PCI Card Vault */}
        {activeView === "revenue-health" && <div className="p-6"><RevenueHealthPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "ip-allowlist" && <div className="p-6"><IpAllowlistPanel /></div>}
        {activeView === "card-vault" && <div className="p-6"><CardVaultPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "deposit-automation" && <div className="p-6"><DepositAutomationPanel activePropertyId={activePropertyId} /></div>}

        {/* Iter 160 — Channel Manager MVP */}
        {activeView === "channel-restrictions" && <div className="p-6"><ChannelRestrictionsPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "channel-inbound" && <div className="p-6"><ChannelInboundPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "channel-parity" && <div className="p-6"><ChannelParityPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "ota-health" && <div className="p-6"><OtaHealthPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "channel-map-matrix" && <div className="p-6"><ChannelMappingsPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "channel-sync-queue" && <div className="p-6"><SyncQueuePanel activePropertyId={activePropertyId} /></div>}

        {/* Iter 163 — Channel Manager Hub (Dashboard, Channels, Mappings, Rate Structure, Publish Jobs, Audit Logs, Benchmark, Profiles, Overrides) */}
        {activeView === "chmgr-hub" && <ChannelManagerHub activePropertyId={activePropertyId} />}
        {activeView?.startsWith?.("chmgr-hub:") && <ChannelManagerHub activePropertyId={activePropertyId} initialPanel={activeView.split(":")[1]} />}

        {/* Iter 165 — Group Blocks (Smart Rate Control lives inside Revenue → Pricing tab to avoid duplication) */}
        {activeView === "group-blocks" && <GroupBlocksPanel activePropertyId={activePropertyId} />}

        {/* Iter 165.4 — Laundry Settings (Providers + Contracts with Per Piece / Flat Rate / Hybrid pricing) */}
        {activeView === "laundry-settings" && false && <LaundrySettingsPanel activePropertyId={activePropertyId} />}

        {/* Onboarding Wizard */}
        {activeView === "onboarding" && (
          <div className="p-6">
            <OnboardingWizard
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : "default"}
              onClose={() => setActiveView("calendar")}
              onNavigate={(view) => setActiveView(view)}
            />
          </div>
        )}

        {/* Unified Inbox */}
        {activeView === "unified-inbox" && (
          <UnifiedInboxPanel user={user} />
        )}

        {/* Bug Tracker */}
        {activeView === "bug-tracker" && (
          <div className="p-6"><BugTrackerPanel user={user} /></div>
        )}

        {/* Roles & Permissions */}
        {activeView === "roles-permissions" && (
          <div className="p-6"><RolesPermissionsPanel user={user} propertyId={activePropertyId && activePropertyId !== "all" ? activePropertyId : null} /></div>
        )}

        {/* Import Module */}
        {activeView === "import-module" && (
          <div className="p-6"><ImportModulePanel user={user} /></div>
        )}

        {/* Audit Trail */}
        {activeView === "audit-trail" && (
          <div className="p-6"><AuditTrailPanel user={user} /></div>
        )}

        {/* Collisions */}
        {activeView === "collisions" && (
          <div className="p-6"><CollisionsPanel user={user} onJumpToCalendar={(pid) => { if (pid) setActivePropertyId(pid); setActiveView("calendar"); }} /></div>
        )}

        {/* Profit OS */}
        {activeView === "profit-os" && (
          <div className="p-6"><ProfitOSPanel user={user} propertyId={activePropertyId} /></div>
        )}

        {/* Agentic AI Loops — Mews 2026 parity (Iter 286) */}
        {activeView === "ai-agents" && <AgentsPanel />}

        {/* Vacation Rental dedicated view — Eviivo/Lighthouse parity (Iter 286) */}
        {activeView === "vacation-rental" && <VacationRentalPanel />}

        {/* Dev Portal / Wholesaler / Lead Funnel — Iter 287 */}
        {activeView === "dev-portal" && <DevPortalAdminPanel />}
        {activeView === "wholesaler-hub" && (
          <WholesalerHubPanel propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")} />
        )}
        {activeView === "lead-funnel" && (
          <LeadFunnelPanel propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")} />
        )}
        {activeView === "marketing-videos" && <MarketingVideosPanel />}
        {activeView === "brand-voice" && (
          <BrandVoicePanel propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")} />
        )}
        {activeView === "profit-pricing" && (
          <ProfitPricingPanel propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")} />
        )}
        {activeView === "abs-selling" && (
          <AbsPanel propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")} />
        )}
        {activeView === "revpam" && (
          <RevPAMPanel propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")} />
        )}
        {activeView === "decision-assurance" && (
          <DecisionAssurancePanel propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")} />
        )}
        {activeView === "data-quality" && (
          <DataQualityPanel propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")} />
        )}
        {activeView === "group-sales" && (
          <GroupSalesPanel propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")} />
        )}
        {activeView === "overbooking-control" && (
          <OverbookingControlPanel propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")} />
        )}
        {activeView === "room-type-forecast" && (
          <RoomTypeForecastPanel propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")} />
        )}
    </>
  );
}
