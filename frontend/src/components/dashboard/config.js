import axios from "axios";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

// Configure axios to send cookies
axios.defaults.withCredentials = true;

export function formatApiErrorDetail(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).filter(Boolean).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export const PLATFORMS = {
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

export const TEMPLATE_CATEGORIES = {
  positive: { name: "Positive", color: "bg-[#5A6B50]", icon: "👍" },
  negative: { name: "Negative", color: "bg-[#C05A44]", icon: "👎" },
  neutral: { name: "Neutral", color: "bg-[#57534E]", icon: "➖" },
  complaint: { name: "Complaint", color: "bg-[#D4A373]", icon: "⚠️" },
  praise: { name: "Praise", color: "bg-[#3E5245]", icon: "⭐" }
};

export const SENTIMENT_COLORS = {
  positive: { bg: "bg-[#5A6B50]", text: "text-[#5A6B50]", light: "bg-[#E8EDE7]" },
  negative: { bg: "bg-[#C05A44]", text: "text-[#C05A44]", light: "bg-red-50" },
  neutral: { bg: "bg-[#57534E]", text: "text-[#57534E]", light: "bg-stone-100" },
  mixed: { bg: "bg-[#D4A373]", text: "text-[#D4A373]", light: "bg-amber-50" }
};

export const URGENCY_COLORS = {
  low: "bg-[#5A6B50]",
  medium: "bg-[#D4A373]",
  high: "bg-orange-500",
  critical: "bg-[#C05A44]"
};

export const LANGUAGES = [
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
