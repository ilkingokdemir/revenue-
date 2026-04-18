"""
Integrations Marketplace — 120+ curated integrations across 14 categories.
Persists installation/enabled state per property.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import logging

logger = logging.getLogger(__name__)


# ============== CATALOG (120+ integrations) ==============
CATALOG = [
    # OTAs (15)
    {"id": "booking",         "name": "Booking.com",   "cat": "ota", "domain": "booking.com",        "desc": "World's largest OTA — sync inventory, rates, bookings.",                   "featured": True,  "tier": "premium"},
    {"id": "airbnb",          "name": "Airbnb",        "cat": "ota", "domain": "airbnb.com",         "desc": "Global home-sharing platform with instant booking.",                       "featured": True,  "tier": "premium"},
    {"id": "expedia",         "name": "Expedia Group", "cat": "ota", "domain": "expedia.com",        "desc": "Expedia, Hotels.com, Travelocity, Orbitz — one connection.",               "featured": True,  "tier": "premium"},
    {"id": "hotels",          "name": "Hotels.com",    "cat": "ota", "domain": "hotels.com",         "desc": "Part of Expedia Group — leverage rewards traveller base."},
    {"id": "agoda",           "name": "Agoda",         "cat": "ota", "domain": "agoda.com",          "desc": "Leading OTA in Asia-Pacific with 2.5M+ properties."},
    {"id": "vrbo",            "name": "VRBO",          "cat": "ota", "domain": "vrbo.com",           "desc": "Vacation Rentals By Owner — whole-home rentals."},
    {"id": "google-travel",   "name": "Google Travel", "cat": "ota", "domain": "google.com",         "desc": "Free Booking Links + Google Hotel Ads.",                                   "featured": True},
    {"id": "tripadvisor",     "name": "Tripadvisor",   "cat": "ota", "domain": "tripadvisor.com",    "desc": "World's largest travel guidance platform."},
    {"id": "hostelworld",     "name": "Hostelworld",   "cat": "ota", "domain": "hostelworld.com",    "desc": "Leading OTA for hostels and budget properties."},
    {"id": "trip-com",        "name": "Trip.com",      "cat": "ota", "domain": "trip.com",           "desc": "Major Asian OTA (Ctrip group) with 400M+ users."},
    {"id": "despegar",        "name": "Despegar",      "cat": "ota", "domain": "despegar.com",       "desc": "Leading Latin American travel platform."},
    {"id": "traveloka",       "name": "Traveloka",     "cat": "ota", "domain": "traveloka.com",      "desc": "Southeast Asia's leading online travel platform."},
    {"id": "makemytrip",      "name": "MakeMyTrip",    "cat": "ota", "domain": "makemytrip.com",     "desc": "India's top travel booking platform."},
    {"id": "kayak",           "name": "KAYAK",         "cat": "ota", "domain": "kayak.com",          "desc": "Meta-search aggregator — boost visibility."},
    {"id": "trivago",         "name": "Trivago",       "cat": "ota", "domain": "trivago.com",        "desc": "Leading hotel meta-search — price comparison."},

    # Payments (10)
    {"id": "stripe",          "name": "Stripe",        "cat": "payments", "domain": "stripe.com",    "desc": "Cards, Apple Pay, Google Pay, 3DS — industry leader.",                    "featured": True, "tier": "premium"},
    {"id": "paypal",          "name": "PayPal",        "cat": "payments", "domain": "paypal.com",    "desc": "Accept PayPal and Pay in 3 at checkout."},
    {"id": "square",          "name": "Square",        "cat": "payments", "domain": "squareup.com",  "desc": "In-person card readers + online payments."},
    {"id": "adyen",           "name": "Adyen",         "cat": "payments", "domain": "adyen.com",     "desc": "Enterprise-grade global payment processor."},
    {"id": "amex",            "name": "American Express","cat": "payments","domain":"americanexpress.com","desc":"Accept Amex cards with direct API."},
    {"id": "klarna",          "name": "Klarna",        "cat": "payments", "domain": "klarna.com",    "desc": "Buy now, pay later for longer stays."},
    {"id": "afterpay",        "name": "Afterpay",      "cat": "payments", "domain": "afterpay.com",  "desc": "Split payments into 4 interest-free instalments."},
    {"id": "razorpay",        "name": "Razorpay",      "cat": "payments", "domain": "razorpay.com",  "desc": "India's leading payment gateway with UPI."},
    {"id": "wise",            "name": "Wise",          "cat": "payments", "domain": "wise.com",      "desc": "Multi-currency accounts for global guests."},
    {"id": "revolut",         "name": "Revolut Business","cat":"payments","domain":"revolut.com",    "desc": "Multi-currency business accounts with FX."},

    # Channel Managers (6)
    {"id": "siteminder",      "name": "SiteMinder",    "cat": "channel", "domain": "siteminder.com", "desc": "Leading channel manager with 450+ channels."},
    {"id": "cloudbeds-cm",    "name": "Cloudbeds CM",  "cat": "channel", "domain": "cloudbeds.com",  "desc": "Channel manager with Price Intelligence."},
    {"id": "rategain",        "name": "RateGain",      "cat": "channel", "domain": "rategain.com",   "desc": "Enterprise rate distribution + shopping."},
    {"id": "d-edge",          "name": "D-EDGE",        "cat": "channel", "domain": "d-edge.com",     "desc": "Central reservation system + channel manager."},
    {"id": "staah",           "name": "STAAH",         "cat": "channel", "domain": "staah.com",      "desc": "Channel manager + booking engine."},
    {"id": "ezee",            "name": "eZee Centrix",  "cat": "channel", "domain": "ezeetechnosys.com", "desc": "Channel manager with 150+ OTA links."},

    # Revenue Management (8)
    {"id": "duetto",          "name": "Duetto",        "cat": "revenue", "domain": "duettocloud.com","desc": "Enterprise revenue strategy & pricing AI."},
    {"id": "ideas",           "name": "IDeaS G3",      "cat": "revenue", "domain": "ideas.com",      "desc": "SAS-powered revenue science for hotels."},
    {"id": "atomize",         "name": "Atomize",       "cat": "revenue", "domain": "atomize.com",    "desc": "Real-time dynamic pricing engine."},
    {"id": "pace",            "name": "Pace Revenue",  "cat": "revenue", "domain": "paceup.com",     "desc": "AI-powered yield management."},
    {"id": "revcontrol",      "name": "RevControl",    "cat": "revenue", "domain": "revcontrol.com", "desc": "Smart revenue management for indies."},
    {"id": "rev-plus",        "name": "Rev+",          "cat": "revenue", "domain": "revplus.io",     "desc": "Hotel revenue insights & forecasting."},
    {"id": "hotelpartner",    "name": "HotelPartner",  "cat": "revenue", "domain": "hotelpartner.com","desc":"Managed revenue service + technology."},
    {"id": "climber-rms",     "name": "Climber RMS",   "cat": "revenue", "domain": "climberrms.com", "desc": "Revenue management for independent hotels."},

    # Messaging & CRM (10)
    {"id": "whatsapp",        "name": "WhatsApp Business","cat":"messaging","domain":"whatsapp.com", "desc": "Guest messaging via WhatsApp Business API.",                                "featured": True},
    {"id": "twilio",          "name": "Twilio SMS",    "cat": "messaging","domain": "twilio.com",    "desc": "SMS + voice + WhatsApp in one API."},
    {"id": "intercom",        "name": "Intercom",      "cat": "messaging","domain": "intercom.com",  "desc": "Guest messenger + support workflows."},
    {"id": "zendesk",         "name": "Zendesk",       "cat": "messaging","domain": "zendesk.com",   "desc": "Omnichannel customer support."},
    {"id": "mailchimp",       "name": "Mailchimp",     "cat": "messaging","domain": "mailchimp.com", "desc": "Email marketing + guest campaigns."},
    {"id": "sendgrid",        "name": "SendGrid",      "cat": "messaging","domain": "sendgrid.com",  "desc": "Transactional email at scale."},
    {"id": "resend",          "name": "Resend",        "cat": "messaging","domain": "resend.com",    "desc": "Modern email API for developers.",                                         "enabled_default": True},
    {"id": "klaviyo",         "name": "Klaviyo",       "cat": "messaging","domain": "klaviyo.com",   "desc": "Marketing automation for guest retention."},
    {"id": "hubspot",         "name": "HubSpot CRM",   "cat": "messaging","domain": "hubspot.com",   "desc": "CRM + marketing + sales hub."},
    {"id": "salesforce",      "name": "Salesforce",    "cat": "messaging","domain": "salesforce.com","desc": "Enterprise CRM for large hotel groups."},

    # AI (8)
    {"id": "openai",          "name": "OpenAI (GPT-5.2)","cat":"ai",     "domain": "openai.com",     "desc": "GPT-5.2 for AI guest responses, reviews, upsell.",                         "featured": True, "enabled_default": True},
    {"id": "anthropic",       "name": "Anthropic Claude","cat":"ai",     "domain": "anthropic.com",  "desc": "Claude 4.5 for nuanced guest conversations."},
    {"id": "gemini",          "name": "Google Gemini", "cat": "ai",      "domain": "google.com",     "desc": "Gemini 3 for multilingual + multimodal AI."},
    {"id": "nano-banana",     "name": "Nano Banana",   "cat": "ai",      "domain": "gemini.google.com","desc":"Gemini image generation for marketing assets."},
    {"id": "elevenlabs",      "name": "ElevenLabs",    "cat": "ai",      "domain": "elevenlabs.io",  "desc": "AI voice agents for reservation calls."},
    {"id": "deepl",           "name": "DeepL",         "cat": "ai",      "domain": "deepl.com",      "desc": "Translate guest messages in 32 languages."},
    {"id": "revinate-ai",     "name": "Revinate AI",   "cat": "ai",      "domain": "revinate.com",   "desc": "AI-powered guest data platform."},
    {"id": "emergent-ai",     "name": "Emergent LLM",  "cat": "ai",      "domain": "emergent.sh",    "desc": "Universal AI key — OpenAI, Claude, Gemini in one.",                         "enabled_default": True},

    # Reviews (6)
    {"id": "tripadvisor-reviews","name":"Tripadvisor Reviews","cat":"reviews","domain":"tripadvisor.com","desc":"Pull and respond to Tripadvisor reviews."},
    {"id": "google-reviews",  "name": "Google Business","cat":"reviews", "domain": "google.com",     "desc": "Manage Google reviews and Q&A."},
    {"id": "trustpilot",      "name": "Trustpilot",    "cat": "reviews", "domain": "trustpilot.com", "desc": "Open review platform for trust signals."},
    {"id": "revinate",        "name": "Revinate",      "cat": "reviews", "domain": "revinate.com",   "desc": "Guest feedback surveys + review aggregation."},
    {"id": "guest-revu",      "name": "GuestRevu",     "cat": "reviews", "domain": "guestrevu.com",  "desc": "Review aggregation + sentiment analytics."},
    {"id": "customer-alliance","name":"Customer Alliance","cat":"reviews","domain":"customer-alliance.com","desc":"Reputation management + surveys."},

    # Smart Locks & Access (8)
    {"id": "ttlock",          "name": "TTLock",        "cat": "locks",   "domain": "ttlock.com",     "desc": "Smart lock + keypad + Bluetooth unlock."},
    {"id": "august",          "name": "August",        "cat": "locks",   "domain": "august.com",     "desc": "Smart locks with DoorSense."},
    {"id": "yale",            "name": "Yale",          "cat": "locks",   "domain": "yale.com",       "desc": "Pro-grade electronic locks + cameras."},
    {"id": "salto",           "name": "Salto KS",      "cat": "locks",   "domain": "saltosystems.com","desc":"Cloud-based access control."},
    {"id": "assa-abloy",      "name": "ASSA ABLOY",    "cat": "locks",   "domain": "assaabloy.com",  "desc": "VingCard + Mobile Access door hardware."},
    {"id": "dormakaba",       "name": "Dormakaba",     "cat": "locks",   "domain": "dormakaba.com",  "desc": "RFID + mobile key hotel solutions."},
    {"id": "nuki",            "name": "Nuki",          "cat": "locks",   "domain": "nuki.io",        "desc": "Smart lock for short-term rentals."},
    {"id": "igloohome",       "name": "igloohome",     "cat": "locks",   "domain": "igloohome.co",   "desc": "PIN-code smart locks — no Wi-Fi needed."},

    # Accounting (8)
    {"id": "xero",            "name": "Xero",          "cat": "accounting","domain":"xero.com",      "desc": "Cloud accounting with invoicing.",                                         "featured": True},
    {"id": "quickbooks",      "name": "QuickBooks",    "cat": "accounting","domain":"quickbooks.intuit.com","desc":"Small business accounting standard."},
    {"id": "sage",            "name": "Sage",          "cat": "accounting","domain":"sage.com",      "desc": "Enterprise accounting + payroll."},
    {"id": "freshbooks",      "name": "FreshBooks",    "cat": "accounting","domain":"freshbooks.com","desc":"Invoicing + time tracking + expenses."},
    {"id": "wave",            "name": "Wave",          "cat": "accounting","domain":"waveapps.com",  "desc": "Free accounting for small properties."},
    {"id": "zoho-books",      "name": "Zoho Books",    "cat": "accounting","domain":"zoho.com",      "desc": "Accounting suite with automation."},
    {"id": "netsuite",        "name": "NetSuite",      "cat": "accounting","domain":"netsuite.com",  "desc": "Oracle ERP for enterprise hotels."},
    {"id": "expensify",       "name": "Expensify",     "cat": "accounting","domain":"expensify.com", "desc": "Expense tracking + receipt scanning."},

    # POS & F&B (8)
    {"id": "square-pos",      "name": "Square POS",    "cat": "pos",     "domain": "squareup.com",   "desc": "Cloud POS for restaurants + bars."},
    {"id": "toast",           "name": "Toast POS",     "cat": "pos",     "domain": "pos.toasttab.com","desc":"Restaurant POS + kitchen display."},
    {"id": "lightspeed",      "name": "Lightspeed",    "cat": "pos",     "domain": "lightspeedhq.com","desc":"Cloud POS for retail + hospitality."},
    {"id": "clover",          "name": "Clover",        "cat": "pos",     "domain": "clover.com",     "desc": "Fiserv's all-in-one POS."},
    {"id": "revel",           "name": "Revel Systems", "cat": "pos",     "domain": "revelsystems.com","desc":"iPad POS with deep hotel integration."},
    {"id": "oracle-micros",   "name": "Oracle Simphony","cat":"pos",     "domain": "oracle.com",     "desc": "Enterprise Micros POS for F&B."},
    {"id": "ikentoo",         "name": "ikentoo",       "cat": "pos",     "domain": "ikentoo.com",    "desc": "EPOS for pubs, restaurants, hotels."},
    {"id": "zettle",          "name": "Zettle by PayPal","cat":"pos",    "domain": "zettle.com",     "desc": "Mobile card reader + POS."},

    # Analytics & BI (6)
    {"id": "google-analytics","name": "Google Analytics","cat":"analytics","domain":"analytics.google.com","desc":"Web analytics for booking funnel."},
    {"id": "mixpanel",        "name": "Mixpanel",      "cat": "analytics","domain": "mixpanel.com",  "desc": "Product analytics + retention."},
    {"id": "amplitude",       "name": "Amplitude",     "cat": "analytics","domain": "amplitude.com", "desc": "Digital analytics platform."},
    {"id": "looker",          "name": "Looker",        "cat": "analytics","domain": "looker.com",    "desc": "Google Cloud BI platform."},
    {"id": "tableau",         "name": "Tableau",       "cat": "analytics","domain": "tableau.com",   "desc": "Enterprise data visualisation."},
    {"id": "metabase",        "name": "Metabase",      "cat": "analytics","domain": "metabase.com",  "desc": "Open-source BI for custom dashboards."},

    # Housekeeping & Ops (6)
    {"id": "optii",           "name": "Optii",         "cat": "ops",     "domain": "optii.com",      "desc": "Smart housekeeping + staff ops."},
    {"id": "hkeeper",         "name": "HKeeper",       "cat": "ops",     "domain": "hkeeper.com",    "desc": "Hotel operations + maintenance app."},
    {"id": "hotelkit",        "name": "hotelkit",      "cat": "ops",     "domain": "hotelkit.net",   "desc": "Team collaboration + checklists."},
    {"id": "alice",           "name": "Alice",         "cat": "ops",     "domain": "aliceapp.com",   "desc": "Guest requests + operations platform."},
    {"id": "quore",           "name": "Quore",         "cat": "ops",     "domain": "quore.com",      "desc": "Glitch + maintenance tracking."},
    {"id": "vendorli",        "name": "Vendorli",      "cat": "ops",     "domain": "vendorli.com",   "desc": "Vendor + compliance tracking."},

    # Marketing (8)
    {"id": "google-ads",      "name": "Google Ads",    "cat": "marketing","domain":"ads.google.com", "desc": "Search + Hotel Ads + Display."},
    {"id": "meta-ads",        "name": "Meta Ads",      "cat": "marketing","domain": "facebook.com",  "desc": "Facebook + Instagram ads."},
    {"id": "tiktok-ads",      "name": "TikTok Ads",    "cat": "marketing","domain": "tiktok.com",    "desc": "Short-form video ads + shop."},
    {"id": "pinterest",       "name": "Pinterest",     "cat": "marketing","domain": "pinterest.com", "desc": "Visual discovery for travel inspiration."},
    {"id": "buffer",          "name": "Buffer",        "cat": "marketing","domain": "buffer.com",    "desc": "Social media scheduling + analytics."},
    {"id": "hootsuite",       "name": "Hootsuite",     "cat": "marketing","domain": "hootsuite.com", "desc": "Social media management platform."},
    {"id": "canva",           "name": "Canva",         "cat": "marketing","domain": "canva.com",     "desc": "Design graphics for social + print."},
    {"id": "later",           "name": "Later",         "cat": "marketing","domain": "later.com",     "desc": "Visual content scheduler for IG."},

    # Calendars & Productivity (6)
    {"id": "google-calendar", "name": "Google Calendar","cat":"productivity","domain":"calendar.google.com","desc":"Sync bookings to staff calendars."},
    {"id": "outlook",         "name": "Microsoft 365", "cat": "productivity","domain":"microsoft.com","desc":"Outlook + Teams + SharePoint."},
    {"id": "slack",           "name": "Slack",         "cat": "productivity","domain":"slack.com",   "desc": "Team messaging + notifications."},
    {"id": "discord",         "name": "Discord",       "cat": "productivity","domain":"discord.com", "desc": "Real-time team comms."},
    {"id": "notion",          "name": "Notion",        "cat": "productivity","domain":"notion.so",   "desc": "Docs + wikis + SOPs."},
    {"id": "zapier",          "name": "Zapier",        "cat": "productivity","domain":"zapier.com",  "desc": "Connect 6000+ apps with automations.",                                     "featured": True},

    # Storage & CDN (4)
    {"id": "gdrive",          "name": "Google Drive",  "cat": "storage", "domain": "drive.google.com","desc":"Cloud file storage + collaboration."},
    {"id": "dropbox",         "name": "Dropbox",       "cat": "storage", "domain": "dropbox.com",    "desc": "File sync + e-signatures."},
    {"id": "aws-s3",          "name": "AWS S3",        "cat": "storage", "domain": "aws.amazon.com", "desc": "Durable object storage."},
    {"id": "cloudflare",      "name": "Cloudflare",    "cat": "storage", "domain": "cloudflare.com", "desc": "CDN + R2 storage + security."},

    # Identity & Auth (4)
    {"id": "auth0",           "name": "Auth0",         "cat": "identity","domain": "auth0.com",      "desc": "Enterprise authentication platform."},
    {"id": "okta",            "name": "Okta",          "cat": "identity","domain": "okta.com",       "desc": "SSO for hotel groups."},
    {"id": "google-auth",     "name": "Google SSO",    "cat": "identity","domain": "google.com",     "desc": "Sign in with Google for staff."},
    {"id": "microsoft-sso",   "name": "Microsoft SSO", "cat": "identity","domain": "microsoft.com",  "desc": "Azure AD for enterprise staff."},

    # Reporting to Governments (3)
    {"id": "police-reporting","name": "Police Reporting","cat":"compliance","domain":"gov.uk",       "desc": "Automated guest register submission."},
    {"id": "tax-authority",   "name": "Tax Authority",  "cat":"compliance","domain":"gov.uk",        "desc": "VAT + occupancy tax filing."},
    {"id": "tourism-board",   "name": "Tourism Board",  "cat":"compliance","domain":"visitbritain.com","desc":"Tourism stats submission."},
]

CATEGORIES = [
    {"id": "ota",         "name": "OTAs & Channels",     "icon": "globe",     "color": "#3B82F6"},
    {"id": "payments",    "name": "Payments",            "icon": "credit-card","color":"#10B981"},
    {"id": "channel",     "name": "Channel Managers",    "icon": "route",     "color": "#06B6D4"},
    {"id": "revenue",     "name": "Revenue Management",  "icon": "line-chart","color": "#F59E0B"},
    {"id": "messaging",   "name": "Messaging & CRM",     "icon": "message",   "color": "#EC4899"},
    {"id": "ai",          "name": "Artificial Intelligence","icon":"sparkle", "color": "#8B5CF6"},
    {"id": "reviews",     "name": "Reviews & Reputation","icon": "star",      "color": "#EAB308"},
    {"id": "locks",       "name": "Smart Locks & Access","icon": "lock",      "color": "#EF4444"},
    {"id": "accounting",  "name": "Accounting & Finance","icon": "wallet",    "color": "#14B8A6"},
    {"id": "pos",         "name": "POS & F&B",           "icon": "utensils",  "color": "#F97316"},
    {"id": "analytics",   "name": "Analytics & BI",      "icon": "bar-chart", "color": "#6366F1"},
    {"id": "ops",         "name": "Operations",          "icon": "sparkles",  "color": "#84CC16"},
    {"id": "marketing",   "name": "Marketing",           "icon": "megaphone", "color": "#D946EF"},
    {"id": "productivity","name": "Productivity",        "icon": "zap",       "color": "#F59E0B"},
    {"id": "storage",     "name": "Storage & CDN",       "icon": "cloud",     "color": "#64748B"},
    {"id": "identity",    "name": "Identity & SSO",      "icon": "shield",    "color": "#0891B2"},
    {"id": "compliance",  "name": "Compliance & Gov",    "icon": "file-check","color": "#78716C"},
]


def create_marketplace_router(db, require_roles):
    router = APIRouter()

    @router.get("/marketplace/catalog/{property_id}")
    async def catalog(property_id: str, category: str = "", q: str = "",
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        # Load install state
        installs = await db.marketplace_installs.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(500)
        install_map = {i["integration_id"]: i for i in installs}

        items = []
        for x in CATALOG:
            inst = install_map.get(x["id"])
            item = {
                **x,
                "installed": bool(inst),
                "enabled": (inst and inst.get("enabled")) if inst else x.get("enabled_default", False),
                "configured_at": inst.get("configured_at") if inst else None,
                "last_sync": inst.get("last_sync") if inst else None,
                "status": inst.get("status", "ready") if inst else "available",
            }
            if category and item["cat"] != category:
                continue
            if q:
                ql = q.lower()
                if ql not in item["name"].lower() and ql not in item["desc"].lower():
                    continue
            items.append(item)

        # Counts per category (across all, ignoring filter)
        cat_counts = {}
        inst_counts = {}
        for x in CATALOG:
            cat_counts[x["cat"]] = cat_counts.get(x["cat"], 0) + 1
            inst = install_map.get(x["id"])
            if inst or x.get("enabled_default"):
                inst_counts[x["cat"]] = inst_counts.get(x["cat"], 0) + 1

        cats = [
            {**c, "count": cat_counts.get(c["id"], 0), "installed": inst_counts.get(c["id"], 0)}
            for c in CATEGORIES
        ]
        total_installed = sum(1 for x in CATALOG if x["id"] in install_map or x.get("enabled_default"))

        return {
            "integrations": items,
            "categories": cats,
            "total_available": len(CATALOG),
            "total_installed": total_installed,
            "featured": [x for x in items if x.get("featured")],
        }

    @router.post("/marketplace/install/{property_id}/{integration_id}")
    async def install(property_id: str, integration_id: str, data: Dict = None,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        found = next((x for x in CATALOG if x["id"] == integration_id), None)
        if not found:
            raise HTTPException(404, "Integration not found")
        data = data or {}
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "property_id": property_id,
            "integration_id": integration_id,
            "name": found["name"],
            "category": found["cat"],
            "enabled": True,
            "status": "connected",
            "config": data.get("config", {}),
            "configured_at": now,
            "configured_by": current_user.get("name", ""),
            "last_sync": now,
            "updated_at": now,
        }
        await db.marketplace_installs.update_one(
            {"property_id": property_id, "integration_id": integration_id},
            {"$set": doc}, upsert=True
        )
        return {"ok": True, "installed": doc}

    @router.post("/marketplace/toggle/{property_id}/{integration_id}")
    async def toggle(property_id: str, integration_id: str,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        inst = await db.marketplace_installs.find_one(
            {"property_id": property_id, "integration_id": integration_id}, {"_id": 0}
        )
        if not inst:
            raise HTTPException(404, "Not installed")
        new_state = not inst.get("enabled", True)
        await db.marketplace_installs.update_one(
            {"property_id": property_id, "integration_id": integration_id},
            {"$set": {"enabled": new_state, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"ok": True, "enabled": new_state}

    @router.delete("/marketplace/uninstall/{property_id}/{integration_id}")
    async def uninstall(property_id: str, integration_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.marketplace_installs.delete_one(
            {"property_id": property_id, "integration_id": integration_id}
        )
        if r.deleted_count == 0:
            raise HTTPException(404, "Not installed")
        return {"uninstalled": True}

    @router.post("/marketplace/sync/{property_id}/{integration_id}")
    async def sync(property_id: str, integration_id: str,
                   current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        await db.marketplace_installs.update_one(
            {"property_id": property_id, "integration_id": integration_id},
            {"$set": {"last_sync": now, "status": "synced", "updated_at": now}}
        )
        return {"ok": True, "last_sync": now}

    return router
