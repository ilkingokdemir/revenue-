/**
 * Lazy-loaded dashboard panel registry.
 * Each panel is wrapped in React.lazy() so webpack code-splits it
 * into a separate chunk fetched on demand.
 *
 * Eager-mounted panels (LoginPage, NotificationBell, OnboardingBanner,
 * TodayHub, GlobalReportIssueFAB, ActionFeedPanel, CommandPalette,
 * StaffOnboardingGate, PendingLegalDocsGate) are NOT in this file —
 * they are imported eagerly in App.js because they are rendered on
 * every dashboard render or the very first paint.
 *
 * Helper convention:
 *   - L(path) → lazy default export
 *   - N(path, name) → lazy named export (resolved into default)
 */
import { lazy } from "react";

const L = (importer) => lazy(importer);
const N = (importer, name) =>
  lazy(() => importer().then((m) => ({ default: m[name] })));

// ---------- DEFAULT exports ----------
export const ChannelManagerHub = L(() => import("./components/dashboard/ChannelManagerHub"));
export const GroupBlocksPanel = L(() => import("./components/dashboard/GroupBlocksPanel"));
export const LaundrySettingsPanel = L(() => import("./components/dashboard/LaundrySettingsPanel"));
export const TRCompliancePanel = L(() => import("./components/dashboard/TRCompliancePanel"));
export const EUCompliancePanel = L(() => import("./components/dashboard/EUCompliancePanel"));
export const AIPredictionsPanel = L(() => import("./components/dashboard/AIPredictionsPanel"));
export const ChannelRevenuePanel = L(() => import("./components/dashboard/ChannelRevenuePanel"));
export const KDSPanel = L(() => import("./components/dashboard/KDSPanel"));
export const LoyaltyV2Panel = L(() => import("./components/dashboard/LoyaltyV2Panel"));
export const SentimentHeatmapPanel = L(() => import("./components/dashboard/SentimentHeatmapPanel"));
export const SelfCheckInPipelinePanel = L(() => import("./components/dashboard/SelfCheckInPipelinePanel"));
export const BrandPortalPanel = L(() => import("./components/dashboard/BrandPortalPanel"));
export const OpsV2Panel = L(() => import("./components/dashboard/OpsV2Panel"));
export const ForecastV2Panel = L(() => import("./components/dashboard/ForecastV2Panel"));
export const AnomalyPanel = L(() => import("./components/dashboard/AnomalyPanel"));
export const TippingPanel = L(() => import("./components/dashboard/TippingPanel"));
export const GuestPortalV2Panel = L(() => import("./components/dashboard/GuestPortalV2Panel"));
export const ConferenceSCPanel = L(() => import("./components/dashboard/ConferenceSCPanel"));
export const CopilotLibraryPanel = L(() => import("./components/dashboard/CopilotLibraryPanel"));
export const ImageAIPanel = L(() => import("./components/dashboard/ImageAIPanel"));
export const FnbTabsPanel = L(() => import("./components/dashboard/FnbTabsPanel"));
export const BiFeedPanel = L(() => import("./components/dashboard/BiFeedPanel"));
export const HkTurnoverPanel = L(() => import("./components/dashboard/HkTurnoverPanel"));
export const PricingExplainPanel = L(() => import("./components/dashboard/PricingExplainPanel"));
export const LoyaltyTierPanel = L(() => import("./components/dashboard/LoyaltyTierPanel"));
export const PaceReports = L(() => import("./components/dashboard/PaceReports"));
export const AIPricingV2Panel = L(() => import("./components/dashboard/AIPricingV2Panel"));
export const ParityHeatmapPanel = L(() => import("./components/dashboard/ParityHeatmapPanel"));
export const MorningBriefPanel = L(() => import("./components/dashboard/MorningBriefPanel"));
export const RMLabPanel = L(() => import("./components/dashboard/RMLabPanel"));
export const ConciergeInboxPanel = L(() => import("./components/dashboard/ConciergeInboxPanel"));
export const GroupRequestsPanel = L(() => import("./components/dashboard/GroupRequestsPanel"));
export const SustainabilityPanel = L(() => import("./components/dashboard/SustainabilityPanel"));
export const HousekeepingRoutePanel = L(() => import("./components/dashboard/HousekeepingRoutePanel"));
export const NightlyRecapPanel = L(() => import("./components/dashboard/NightlyRecapPanel"));
export const AccountingExportPanel = L(() => import("./components/dashboard/AccountingExportPanel"));
export const LateCheckoutPanel = L(() => import("./components/dashboard/LateCheckoutPanel"));
export const ServiceRecoveryPanel = L(() => import("./components/dashboard/ServiceRecoveryPanel"));
export const RoomQRPanel = L(() => import("./components/dashboard/RoomQRPanel"));
export const TaxPresetsPanel = L(() => import("./components/dashboard/TaxPresetsPanel"));
export const WalkInPanel = L(() => import("./components/dashboard/WalkInPanel"));
export const NoShowPanel = L(() => import("./components/dashboard/NoShowPanel"));
export const GuestPrefsPanel = L(() => import("./components/dashboard/GuestPrefsPanel"));
export const CleaningChecklistsPanel = L(() => import("./components/dashboard/CleaningChecklistsPanel"));
export const AttributionPanel = L(() => import("./components/dashboard/AttributionPanel"));
export const GroupRoomingImportPanel = L(() => import("./components/dashboard/GroupRoomingImportPanel"));
export const OpsQuickActionsPanel = L(() => import("./components/dashboard/OpsQuickActionsPanel"));
export const TimeSlotsPanel = L(() => import("./components/dashboard/TimeSlotsPanel"));
export const StaffOpsPanel = L(() => import("./components/dashboard/StaffOpsPanel"));
export const RevenueProtectionPanel = L(() => import("./components/dashboard/RevenueProtectionPanel"));
export const SpacesPanel = L(() => import("./components/dashboard/SpacesPanel"));
export const MultiPropertyRollupPanel = L(() => import("./components/dashboard/MultiPropertyRollupPanel"));
export const CurrencyPanel = L(() => import("./components/dashboard/CurrencyPanel"));
export const AgentsB2BPanel = L(() => import("./components/dashboard/AgentsB2BPanel"));
export const SecurityOwnerPanel = L(() => import("./components/dashboard/SecurityOwnerPanel"));
export const PreAuthPanel = L(() => import("./components/dashboard/PreAuthPanel"));
export const ChargebackPanel = L(() => import("./components/dashboard/ChargebackPanel"));
export const WebPushPanel = L(() => import("./components/dashboard/WebPushPanel"));
export const PmsCrsSyncPanel = L(() => import("./components/dashboard/PmsCrsSyncPanel"));
export const PublicApiPortalPanel = L(() => import("./components/dashboard/PublicApiPortalPanel"));
export const MidStaySurveyPanel = L(() => import("./components/dashboard/MidStaySurveyPanel"));
export const FolioLivePanel = L(() => import("./components/dashboard/FolioLivePanel"));
export const ABTestPanel = L(() => import("./components/dashboard/ABTestPanel"));
export const PreArrivalDripPanel = L(() => import("./components/dashboard/PreArrivalDripPanel"));
export const MenuEngineeringPanel = L(() => import("./components/dashboard/MenuEngineeringPanel"));
export const SRVoucherPanel = L(() => import("./components/dashboard/SRVoucherPanel"));
export const FolioSplitPanel = L(() => import("./components/dashboard/FolioSplitPanel"));
export const LoyaltyAutoPanel = L(() => import("./components/dashboard/LoyaltyAutoPanel"));
export const LateCheckoutOfferPanel = L(() => import("./components/dashboard/LateCheckoutOfferPanel"));
export const OTAStopSellForecastPanel = L(() => import("./components/dashboard/OTAStopSellForecastPanel"));
export const MsgTemplatesPanel = L(() => import("./components/dashboard/MsgTemplatesPanel"));
export const BirthdayPanel = L(() => import("./components/dashboard/BirthdayPanel"));
export const LowStockPanel = L(() => import("./components/dashboard/LowStockPanel"));
export const RebookPanel = L(() => import("./components/dashboard/RebookPanel"));
export const StayExtPanel = L(() => import("./components/dashboard/StayExtPanel"));
export const LongStayPanel = L(() => import("./components/dashboard/LongStayPanel"));
export const CancelInsurancePanel = L(() => import("./components/dashboard/CancelInsurancePanel"));
export const GroupRoomingWizPanel = L(() => import("./components/dashboard/GroupRoomingWizPanel"));
export const TaxReportsV2Panel = L(() => import("./components/dashboard/TaxReportsV2Panel"));
export const CISlotsPanel = L(() => import("./components/dashboard/CISlotsPanel"));
export const Tier1DashboardPanel = L(() => import("./components/dashboard/Tier1DashboardPanel"));

// ---------- NAMED exports ----------
export const IntegrationsPanel = N(() => import("./components/dashboard/IntegrationsPanel"), "IntegrationsPanel");
export const IntegrationsMarketplace = N(() => import("./components/dashboard/IntegrationsMarketplace"), "IntegrationsMarketplace");
export const ArrivalsCockpit = N(() => import("./components/dashboard/ArrivalsCockpit"), "ArrivalsCockpit");
export const StaffContractsPanel = N(() => import("./components/dashboard/StaffContractsPanel"), "StaffContractsPanel");
export const StaffOnboardingAdminPanel = N(() => import("./components/dashboard/StaffOnboardingAdminPanel"), "StaffOnboardingAdminPanel");
export const PayrollRateMatrix = N(() => import("./components/dashboard/finance/PayrollRateMatrix"), "PayrollRateMatrix");
export const CityLedgerPanel = N(() => import("./components/dashboard/finance/CityLedgerPanel"), "CityLedgerPanel");
export const TaxConfigPanel = N(() => import("./components/dashboard/finance/TaxConfigPanel"), "TaxConfigPanel");
export const DepositPolicyPanel = N(() => import("./components/dashboard/finance/DepositPolicyPanel"), "DepositPolicyPanel");
export const CurrencyFxPanel = N(() => import("./components/dashboard/finance/CurrencyFxPanel"), "CurrencyFxPanel");
export const RateStructurePanel = N(() => import("./components/dashboard/finance/RateStructurePanel"), "RateStructurePanel");
export const GroupBookingsPanel = N(() => import("./components/dashboard/GroupBookingsPanel"), "GroupBookingsPanel");
export const GdprPanel = N(() => import("./components/dashboard/GdprPanel"), "GdprPanel");

// CompetitorGapPanels — multi-named export module
const _cgp = () => import("./components/dashboard/CompetitorGapPanels");
export const NightAuditClosePanel = N(_cgp, "NightAuditClosePanel");
export const DepositLedgerPanel = N(_cgp, "DepositLedgerPanel");
export const CommissionReconPanel = N(_cgp, "CommissionReconPanel");
export const GiftCardsPanel = N(_cgp, "GiftCardsPanel");
export const ReviewSentimentPanel = N(_cgp, "ReviewSentimentPanel");
export const GuestRfmPanel = N(_cgp, "GuestRfmPanel");
export const PreventiveMaintenancePanel = N(_cgp, "PreventiveMaintenancePanel");
export const AssetRegisterPanel = N(_cgp, "AssetRegisterPanel");
export const CashDrawerPanel = N(_cgp, "CashDrawerPanel");
export const TwoFactorAuthPanel = N(_cgp, "TwoFactorAuthPanel");
export const RevenueHealthPanel = N(_cgp, "RevenueHealthPanel");
export const IpAllowlistPanel = N(_cgp, "IpAllowlistPanel");
export const CardVaultPanel = N(_cgp, "CardVaultPanel");
export const DepositAutomationPanel = N(_cgp, "DepositAutomationPanel");

// ChannelManagerMvpPanels — multi-named export module
const _cmm = () => import("./components/dashboard/ChannelManagerMvpPanels");
export const ChannelRestrictionsPanel = N(_cmm, "ChannelRestrictionsPanel");
export const ChannelInboundPanel = N(_cmm, "ChannelInboundPanel");
export const ChannelParityPanel = N(_cmm, "ChannelParityPanel");
export const OtaHealthPanel = N(_cmm, "OtaHealthPanel");
export const ChannelMappingsPanel = N(_cmm, "ChannelMappingsPanel");
export const SyncQueuePanel = N(_cmm, "SyncQueuePanel");

export const OnboardingWizard = N(() => import("./components/dashboard/OnboardingWizard"), "OnboardingWizard");
export const UnifiedInboxPanel = N(() => import("./components/dashboard/UnifiedInboxPanel"), "UnifiedInboxPanel");
export const BugTrackerPanel = N(() => import("./components/dashboard/ops/BugTrackerPanel"), "BugTrackerPanel");
export const AuditTrailPanel = N(() => import("./components/dashboard/rbac/AuditTrailPanel"), "AuditTrailPanel");
export const CollisionsPanel = N(() => import("./components/dashboard/ops/CollisionsPanel"), "CollisionsPanel");
export const ProfitOSPanel = N(() => import("./components/dashboard/revenue/ProfitOSPanel"), "ProfitOSPanel");
export const RolesPermissionsPanel = N(() => import("./components/dashboard/rbac/RolesPermissionsPanel"), "RolesPermissionsPanel");
export const ImportModulePanel = N(() => import("./components/dashboard/imports/ImportModulePanel"), "ImportModulePanel");
export const LegalDocumentsPanel = N(() => import("./components/dashboard/LegalDocumentsPanel"), "LegalDocumentsPanel");
export const AnalyticsPanel = N(() => import("./components/dashboard/AnalyticsPanel"), "AnalyticsPanel");
export const ReportsSettings = N(() => import("./components/dashboard/ReportsSettings"), "ReportsSettings");
export const BrandingPanel = N(() => import("./components/dashboard/BrandingPanel"), "BrandingPanel");
export const SyncLogPanel = N(() => import("./components/dashboard/SyncLogPanel"), "SyncLogPanel");
export const PropertyMappingPanel = N(() => import("./components/dashboard/PropertyMappingPanel"), "PropertyMappingPanel");
export const BookingEnginePanel = N(() => import("./components/dashboard/BookingEnginePanel"), "BookingEnginePanel");
export const TemplateGallery = N(() => import("./components/dashboard/TemplateGallery"), "TemplateGallery");
export const TemplateCustomizer = N(() => import("./components/dashboard/TemplateCustomizer"), "TemplateCustomizer");
export const PromoCodesPanel = N(() => import("./components/dashboard/PromoCodesPanel"), "PromoCodesPanel");
export const AddOnsPanel = N(() => import("./components/dashboard/AddOnsPanel"), "AddOnsPanel");
export const PoliciesPanel = N(() => import("./components/dashboard/PoliciesPanel"), "PoliciesPanel");
export const MessagingHub = N(() => import("./components/dashboard/MessagingHub"), "MessagingHub");
export const ConciergeAnalyticsPanel = N(() => import("./components/dashboard/ConciergeAnalyticsPanel"), "ConciergeAnalyticsPanel");
export const AutomationPanel = N(() => import("./components/dashboard/AutomationPanel"), "AutomationPanel");
export const ChannelSettingsPanel = N(() => import("./components/dashboard/ChannelSettingsPanel"), "ChannelSettingsPanel");
export const DashboardHome = N(() => import("./components/dashboard/DashboardHome"), "DashboardHome");
export const StaffPerformancePanel = N(() => import("./components/dashboard/StaffPerformancePanel"), "StaffPerformancePanel");
export const GuestProfilesPanel = N(() => import("./components/dashboard/GuestProfilesPanel"), "GuestProfilesPanel");
export const AdminPanel = N(() => import("./components/dashboard/AdminPanel"), "AdminPanel");
export const HousekeepingPanel = N(() => import("./components/dashboard/HousekeepingPanel"), "HousekeepingPanel");
export const NightAuditPanel = N(() => import("./components/dashboard/NightAuditPanel"), "NightAuditPanel");
export const LoyaltyPanel = N(() => import("./components/dashboard/LoyaltyPanel"), "LoyaltyPanel");
export const LogbookPanel = N(() => import("./components/dashboard/LogbookPanel"), "LogbookPanel");
export const ForecastPanel = N(() => import("./components/dashboard/ForecastPanel"), "ForecastPanel");
export const CampaignsPanel = N(() => import("./components/dashboard/CampaignsPanel"), "CampaignsPanel");
export const GuestAppPanel = N(() => import("./components/dashboard/GuestAppPanel"), "GuestAppPanel");
export const SmartLocksPanel = N(() => import("./components/dashboard/SmartLocksPanel"), "SmartLocksPanel");
export const SetupWizardPanel = N(() => import("./components/dashboard/SetupWizardPanel"), "SetupWizardPanel");
export const StockManagementPanel = N(() => import("./components/dashboard/StockManagementPanel"), "StockManagementPanel");
export const AccountingPanel = N(() => import("./components/dashboard/AccountingPanel"), "AccountingPanel");
export const POSPanel = N(() => import("./components/dashboard/POSPanel"), "POSPanel");
export const PaymentsPanel = N(() => import("./components/dashboard/PaymentsPanel"), "PaymentsPanel");
export const SurveyPanel = N(() => import("./components/dashboard/SurveyPanel"), "SurveyPanel");
export const GuestJourneyPanel = N(() => import("./components/dashboard/GuestJourneyPanel"), "GuestJourneyPanel");
export const MaintenancePanel = N(() => import("./components/dashboard/MaintenancePanel"), "MaintenancePanel");
export const RateManagerPanel = N(() => import("./components/dashboard/RateManagerPanel"), "RateManagerPanel");
export const ReportsCentrePanel = N(() => import("./components/dashboard/ReportsCentrePanel"), "ReportsCentrePanel");
export const ScheduledReports = N(() => import("./components/dashboard/ScheduledReports"), "ScheduledReports");
export const MobileCompanion = N(() => import("./components/dashboard/MobileCompanion"), "MobileCompanion");
export const EnhancedDashboard = N(() => import("./components/dashboard/EnhancedDashboard"), "EnhancedDashboard");
export const ReportsHub = N(() => import("./components/dashboard/ReportsHub"), "ReportsHub");
export const FinancePL = N(() => import("./components/dashboard/FinancePL"), "FinancePL");
export const ShiftScheduler = N(() => import("./components/dashboard/ShiftScheduler"), "ShiftScheduler");
export const ReceptionReport = N(() => import("./components/dashboard/ReceptionReport"), "ReceptionReport");
export const PassOverDuties = N(() => import("./components/dashboard/PassOverDuties"), "PassOverDuties");
export const ComplianceRegister = N(() => import("./components/dashboard/ComplianceRegister"), "ComplianceRegister");
export const LaundryManagement = N(() => import("./components/dashboard/LaundryManagement"), "LaundryManagement");
export const PayrollManagement = N(() => import("./components/dashboard/PayrollManagement"), "PayrollManagement");
export const ExpenseManagement = N(() => import("./components/dashboard/ExpenseManagement"), "ExpenseManagement");
export const CashFlowForecast = N(() => import("./components/dashboard/CashFlowForecast"), "CashFlowForecast");
export const OperationsHubPanel = N(() => import("./components/dashboard/OperationsHubPanel"), "OperationsHubPanel");
export const FinancePanel = N(() => import("./components/dashboard/FinancePanel"), "FinancePanel");
export const StaffManagementPanel = N(() => import("./components/dashboard/StaffManagementPanel"), "StaffManagementPanel");
export const MyTasksPanel = N(() => import("./components/dashboard/MyTasksPanel"), "MyTasksPanel");
export const LostFoundPanel = N(() => import("./components/dashboard/LostFoundPanel"), "LostFoundPanel");
export const EventsPanel = N(() => import("./components/dashboard/EventsPanel"), "EventsPanel");
export const SettingsHubPanel = N(() => import("./components/dashboard/SettingsHubPanel"), "SettingsHubPanel");
export const BookingEngineAdmin = N(() => import("./components/dashboard/BookingEngineAdmin"), "BookingEngineAdmin");
export const BookingTimeline = N(() => import("./components/dashboard/BookingTimeline"), "BookingTimeline");
export const RevenuePanel = N(() => import("./components/dashboard/RevenuePanel"), "RevenuePanel");
