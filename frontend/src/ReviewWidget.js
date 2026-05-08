import { useEffect, useState, useCallback, useRef } from "react";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Notification sound - short pleasant chime using Web Audio API
const playNotificationSound = (isUrgent = false) => {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const playTone = (freq, start, dur, vol = 0.15) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = freq;
      osc.type = isUrgent ? "square" : "sine";
      gain.gain.setValueAtTime(vol, ctx.currentTime + start);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + dur);
      osc.start(ctx.currentTime + start);
      osc.stop(ctx.currentTime + start + dur);
    };
    if (isUrgent) {
      // Urgent alert: descending alarm tones, louder, repeated
      playTone(880, 0, 0.15, 0.2);
      playTone(660, 0.12, 0.15, 0.2);
      playTone(880, 0.28, 0.15, 0.2);
      playTone(660, 0.40, 0.15, 0.2);
      playTone(440, 0.56, 0.25, 0.2);
    } else {
      // Normal: ascending pleasant chime
      playTone(880, 0, 0.15);
      playTone(1100, 0.12, 0.15);
      playTone(1320, 0.24, 0.2);
    }
  } catch (e) { /* audio not supported */ }
};

// Red popup notification component
const NotificationPopup = ({ notifications, onDismiss, onDismissAll, isDark }) => {
  if (notifications.length === 0) return null;

  return (
    <div style={{ position: "fixed", top: 16, right: 16, zIndex: 9999, display: "flex", flexDirection: "column", gap: 8, maxWidth: 420 }} data-testid="notification-popup-container">
      {notifications.map((n, i) => {
        const isLowRating = n.rating <= 2;
        return (
        <div
          key={n.id}
          style={{
            background: isLowRating
              ? "linear-gradient(135deg, #991B1B, #7F1D1D)"
              : "linear-gradient(135deg, #DC2626, #B91C1C)",
            borderRadius: isLowRating ? 14 : 12,
            padding: isLowRating ? "16px 18px" : "14px 16px",
            color: "#FFF",
            boxShadow: isLowRating
              ? "0 12px 48px rgba(153,27,27,0.5), 0 4px 12px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.1)"
              : "0 8px 32px rgba(220,38,38,0.4), 0 2px 8px rgba(0,0,0,0.15)",
            animation: isLowRating
              ? `slideIn 0.4s ease-out ${i * 0.1}s both, urgentPulse 1.5s ease-in-out infinite`
              : `slideIn 0.4s ease-out ${i * 0.1}s both`,
            display: "flex",
            gap: 12,
            alignItems: "flex-start",
            cursor: "pointer",
            maxWidth: isLowRating ? 420 : 380,
            border: isLowRating ? "2px solid rgba(239,68,68,0.5)" : "none",
          }}
          onClick={() => onDismiss(n.id)}
          data-testid={`notification-popup-${n.id}`}
        >
          {/* Icon */}
          <div style={{
            width: isLowRating ? 40 : 32,
            height: isLowRating ? 40 : 32,
            borderRadius: "50%",
            background: isLowRating ? "rgba(254,202,202,0.25)" : "rgba(255,255,255,0.2)",
            display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0
          }}>
            {isLowRating ? (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#FCA5A5" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>
              </svg>
            )}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontSize: isLowRating ? 12 : 11,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              opacity: isLowRating ? 1 : 0.85,
              marginBottom: isLowRating ? 4 : 2,
              display: "flex", alignItems: "center", gap: 6
            }}>
              {isLowRating ? (
                <>
                  <span style={{ background: "#FEE2E2", color: "#991B1B", padding: "2px 8px", borderRadius: 4, fontSize: 10 }}>LOW RATING ALERT</span>
                  <span style={{ fontSize: 10, opacity: 0.7 }}>Needs Attention</span>
                </>
              ) : "New Review"}
            </div>
            <div style={{ fontSize: isLowRating ? 14 : 13, fontWeight: 600, marginBottom: 4 }}>
              {n.guest_name}
              <span style={{ marginLeft: 6, fontSize: 10, padding: "1px 6px", borderRadius: 4, background: "rgba(255,255,255,0.2)" }}>{n.platform_label}</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 4 }}>
              {[1,2,3,4,5].map(s => (
                <svg key={s} width={isLowRating ? 12 : 10} height={isLowRating ? 12 : 10} viewBox="0 0 20 20" fill={s <= n.rating ? (isLowRating ? "#FCA5A5" : "#FDE68A") : "rgba(255,255,255,0.3)"}>
                  <path d="M10 1l2.39 4.84 5.34.78-3.87 3.77.91 5.32L10 13.27l-4.77 2.51.91-5.32L2.27 6.69l5.34-.78L10 1z"/>
                </svg>
              ))}
              {isLowRating && <span style={{ fontSize: 10, marginLeft: 4, opacity: 0.8 }}>{n.rating}/5</span>}
            </div>
            <div style={{ fontSize: isLowRating ? 12 : 11, opacity: isLowRating ? 0.95 : 0.85, lineHeight: 1.4, overflow: "hidden", textOverflow: "ellipsis", display: "-webkit-box", WebkitLineClamp: isLowRating ? 3 : 2, WebkitBoxOrient: "vertical" }}>
              {n.review_text}
            </div>
            {isLowRating && (
              <div style={{ marginTop: 8, fontSize: 10, display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ background: "rgba(254,202,202,0.2)", padding: "3px 8px", borderRadius: 4, fontWeight: 600 }}>
                  Respond quickly to protect your reputation
                </span>
              </div>
            )}
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); onDismiss(n.id); }}
            style={{ background: "none", border: "none", color: "rgba(255,255,255,0.6)", cursor: "pointer", fontSize: 18, padding: 2, flexShrink: 0 }}
            data-testid={`dismiss-notification-${n.id}`}
          >&times;</button>
        </div>
        );
      })}
      {notifications.length > 1 && (
        <button
          onClick={onDismissAll}
          style={{ alignSelf: "flex-end", fontSize: 10, color: isDark ? "#A8A29E" : "#78716C", background: isDark ? "#292524" : "#FFF", border: `1px solid ${isDark ? "#44403C" : "#E7E5E4"}`, borderRadius: 6, padding: "4px 10px", cursor: "pointer" }}
          data-testid="dismiss-all-notifications"
        >
          Dismiss all
        </button>
      )}
    </div>
  );
};

const StarRating = ({ rating, size = 14 }) => (
  <div className="flex gap-0.5">
    {[1, 2, 3, 4, 5].map((s) => (
      <svg key={s} width={size} height={size} viewBox="0 0 20 20" fill={s <= rating ? "#D97706" : "#E5E7EB"}>
        <path d="M10 1l2.39 4.84 5.34.78-3.87 3.77.91 5.32L10 13.27l-4.77 2.51.91-5.32L2.27 6.69l5.34-.78L10 1z" />
      </svg>
    ))}
  </div>
);

const platformColors = {
  google: { bg: "#EEF7FF", text: "#1A73E8", label: "Google" },
  "booking.com": { bg: "#EBF0FF", text: "#003580", label: "Booking.com" },
  tripadvisor: { bg: "#E8F5E9", text: "#00AA6C", label: "TripAdvisor" },
  airbnb: { bg: "#FFF0EE", text: "#FF5A5F", label: "Airbnb" },
  expedia: { bg: "#FFFDE7", text: "#FBAB18", label: "Expedia" },
  "trip.com": { bg: "#E3F2FD", text: "#287DFA", label: "Trip.com" },
  agoda: { bg: "#FFF3E0", text: "#5C2D91", label: "Agoda" },
  "hotels.com": { bg: "#FFF8E1", text: "#D32F2F", label: "Hotels.com" },
  yelp: { bg: "#FFEBEE", text: "#D32323", label: "Yelp" },
  facebook: { bg: "#E8EAF6", text: "#1877F2", label: "Facebook" },
  makemytrip: { bg: "#E3F2FD", text: "#EB2126", label: "MakeMyTrip" },
  hrs: { bg: "#FFF8E1", text: "#CC0000", label: "HRS" },
  despegar: { bg: "#E8F5E9", text: "#7B1FA2", label: "Despegar" },
  hostelworld: { bg: "#FFF3E0", text: "#F26522", label: "Hostelworld" },
};

const statusStyles = {
  pending: { bg: "#FEF3C7", text: "#92400E", label: "Pending" },
  draft: { bg: "#E0E7FF", text: "#3730A3", label: "Draft" },
  pending_approval: { bg: "#FED7AA", text: "#9A3412", label: "Awaiting Approval" },
  approved: { bg: "#D1FAE5", text: "#065F46", label: "Approved" },
  rejected: { bg: "#FEE2E2", text: "#991B1B", label: "Rejected" },
  responded: { bg: "#D1FAE5", text: "#065F46", label: "Responded" },
};

export default function ReviewWidget() {
  const [reviews, setReviews] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedReview, setSelectedReview] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [filterPlatform, setFilterPlatform] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState([]);
  const lastCheckRef = useRef(null);
  const pollIntervalRef = useRef(null);

  const params = new URLSearchParams(window.location.search);
  const apiKey = params.get("api_key") || "";
  const propertyId = params.get("property_id") || "default";
  const theme = params.get("theme") || "light";

  const headers = { Authorization: `Bearer ${apiKey}` };

  const fetchData = useCallback(async () => {
    if (!apiKey) { setError("Missing api_key parameter"); setIsLoading(false); return; }
    setIsLoading(true);
    try {
      let reviewUrl = `${API}/widget/reviews?api_key=${apiKey}&property_id=${propertyId}&limit=30`;
      if (filterPlatform) reviewUrl += `&platform=${filterPlatform}`;
      if (filterStatus) reviewUrl += `&status=${filterStatus}`;

      const [revRes, statRes, unreadRes] = await Promise.all([
        axios.get(reviewUrl),
        axios.get(`${API}/widget/stats?api_key=${apiKey}&property_id=${propertyId}`),
        axios.get(`${API}/widget/unread-count?api_key=${apiKey}&property_id=${propertyId}`)
      ]);
      setReviews(revRes.data);
      setStats(statRes.data);
      setUnreadCount(unreadRes.data.unread);
      setError(null);
    } catch (e) {
      setError(e.response?.status === 401 ? "Invalid API key" : "Failed to load reviews");
    } finally {
      setIsLoading(false);
    }
  }, [apiKey, propertyId, filterPlatform, filterStatus]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Set initial timestamp for polling
  useEffect(() => {
    if (!lastCheckRef.current) {
      lastCheckRef.current = new Date().toISOString();
    }
  }, []);

  // Poll for new reviews every 20 seconds
  useEffect(() => {
    if (!apiKey) return;

    const checkNewReviews = async () => {
      if (!lastCheckRef.current) return;
      try {
        const { data } = await axios.get(
          `${API}/widget/reviews/new?api_key=${apiKey}&property_id=${propertyId}&since=${lastCheckRef.current}`
        );
        if (data.length > 0) {
          lastCheckRef.current = new Date().toISOString();
          const newNotifs = data.map(r => ({
            id: r.id,
            guest_name: r.guest_name,
            platform: r.platform,
            platform_label: (platformColors[r.platform] || { label: r.platform }).label,
            rating: r.rating,
            review_text: r.review_text,
            timestamp: Date.now()
          }));
          setNotifications(prev => [...newNotifs, ...prev].slice(0, 5));
          const hasLowRating = data.some(r => r.rating <= 2);
          playNotificationSound(hasLowRating);
          fetchData(); // refresh the list
        }
      } catch (e) { /* silent */ }
    };

    pollIntervalRef.current = setInterval(checkNewReviews, 20000);
    return () => { if (pollIntervalRef.current) clearInterval(pollIntervalRef.current); };
  }, [apiKey, propertyId, fetchData]);

  // Auto-dismiss notifications (low-rating lasts 15s, normal 8s)
  useEffect(() => {
    if (notifications.length === 0) return;
    const oldest = notifications[notifications.length - 1];
    const timeout = oldest.rating <= 2 ? 15000 : 8000;
    const timer = setTimeout(() => {
      setNotifications(prev => prev.slice(0, -1));
    }, timeout);
    return () => clearTimeout(timer);
  }, [notifications]);

  const dismissNotification = (id) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  const dismissAllNotifications = () => {
    setNotifications([]);
  };

  const handleGenerateResponse = async (reviewId) => {
    setGenerating(true);
    try {
      const { data } = await axios.post(`${API}/widget/generate-response?api_key=${apiKey}`, {
        review_id: reviewId, language: "en", tone: "professional"
      });
      setSelectedReview(prev => prev ? { ...prev, response_text: data.response_text, response_status: "draft" } : prev);
      fetchData();
    } catch (e) {
      console.error("AI generation failed");
    } finally {
      setGenerating(false);
    }
  };

  const handleSelectReview = async (review) => {
    setSelectedReview(review);
    if (!review.is_read) {
      try {
        await axios.put(`${API}/widget/reviews/${review.id}/read?api_key=${apiKey}`);
        setReviews(prev => prev.map(r => r.id === review.id ? { ...r, is_read: true } : r));
        setUnreadCount(prev => Math.max(0, prev - 1));
      } catch (e) { /* silent */ }
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await axios.put(`${API}/widget/reviews/mark-all-read?api_key=${apiKey}&property_id=${propertyId}`);
      setReviews(prev => prev.map(r => ({ ...r, is_read: true })));
      setUnreadCount(0);
    } catch (e) { /* silent */ }
  };

  const isDark = theme === "dark";
  const bg = isDark ? "#1C1917" : "#FAFAF9";
  const cardBg = isDark ? "#292524" : "#FFFFFF";
  const textPrimary = isDark ? "#F5F5F4" : "#1C1917";
  const textSecondary = isDark ? "#A8A29E" : "#78716C";
  const borderColor = isDark ? "#44403C" : "#E7E5E4";
  const accentColor = "#059669";

  if (error) {
    return (
      <div style={{ fontFamily: "system-ui, -apple-system, sans-serif", background: bg, minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ textAlign: "center", padding: 40 }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>!</div>
          <p style={{ color: textPrimary, fontSize: 14, fontWeight: 600 }}>{error}</p>
          <p style={{ color: textSecondary, fontSize: 12, marginTop: 4 }}>Check your API key and try again</p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div style={{ fontFamily: "system-ui, -apple-system, sans-serif", background: bg, minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ width: 24, height: 24, border: `2px solid ${borderColor}`, borderTopColor: accentColor, borderRadius: "50%", animation: "spin 0.8s linear infinite", margin: "0 auto 12px" }} />
          <p style={{ color: textSecondary, fontSize: 12 }}>Loading reviews...</p>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      </div>
    );
  }

  return (
    <div style={{ fontFamily: "system-ui, -apple-system, sans-serif", background: bg, minHeight: "100vh", padding: 16 }} data-testid="review-widget">
      <style>{`@keyframes spin { to { transform: rotate(360deg); } } @keyframes badgePulse { 0%, 100% { box-shadow: 0 2px 8px rgba(220,38,38,0.35); } 50% { box-shadow: 0 2px 16px rgba(220,38,38,0.55); } } @keyframes slideIn { from { transform: translateX(120%); opacity: 0; } to { transform: translateX(0); opacity: 1; } } @keyframes urgentPulse { 0%, 100% { box-shadow: 0 12px 48px rgba(153,27,27,0.5), 0 4px 12px rgba(0,0,0,0.2); transform: scale(1); } 50% { box-shadow: 0 16px 56px rgba(153,27,27,0.7), 0 6px 16px rgba(0,0,0,0.25); transform: scale(1.01); } } * { box-sizing: border-box; margin: 0; padding: 0; } ::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-thumb { background: ${borderColor}; border-radius: 4px; }`}</style>

      {/* Notification Popups */}
      <NotificationPopup
        notifications={notifications}
        onDismiss={dismissNotification}
        onDismissAll={dismissAllNotifications}
        isDark={isDark}
      />

      {/* Notification Badge + Stats Bar */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        {/* Red Notification Badge */}
        {unreadCount > 0 && (
          <div style={{ position: "relative" }} data-testid="notification-badge-container">
            <div
              style={{
                background: "#DC2626", color: "#FFF", borderRadius: 20,
                padding: "6px 14px", fontSize: 12, fontWeight: 700,
                display: "flex", alignItems: "center", gap: 8,
                boxShadow: "0 2px 8px rgba(220,38,38,0.35)",
                animation: "badgePulse 2s ease-in-out infinite",
                cursor: "pointer", userSelect: "none",
                whiteSpace: "nowrap"
              }}
              onClick={handleMarkAllRead}
              data-testid="unread-badge"
              title="Click to mark all as read"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>
              </svg>
              {unreadCount} new {unreadCount === 1 ? "review" : "reviews"}
            </div>
          </div>
        )}
        {/* Stats */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, flex: 1 }} data-testid="widget-stats">
        {[
          { label: "Reviews", value: stats?.total_reviews || 0 },
          { label: "Avg Rating", value: stats?.average_rating ? `${stats.average_rating}/5` : "N/A" },
          { label: "Response Rate", value: `${stats?.response_rate || 0}%` },
          { label: "Pending", value: stats?.pending || 0 },
        ].map((s) => (
          <div key={s.label} style={{ background: cardBg, border: `1px solid ${borderColor}`, borderRadius: 8, padding: "10px 12px", textAlign: "center" }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: textPrimary }}>{s.value}</div>
            <div style={{ fontSize: 10, color: textSecondary, marginTop: 2, textTransform: "uppercase", letterSpacing: "0.05em" }}>{s.label}</div>
          </div>
        ))}
      </div>
      </div>

      {/* Filters */}
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <select
          value={filterPlatform}
          onChange={(e) => setFilterPlatform(e.target.value)}
          style={{ fontSize: 11, padding: "5px 8px", border: `1px solid ${borderColor}`, borderRadius: 6, background: cardBg, color: textPrimary, outline: "none" }}
          data-testid="widget-filter-platform"
        >
          <option value="">All Platforms</option>
          {Object.entries(platformColors).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          style={{ fontSize: 11, padding: "5px 8px", border: `1px solid ${borderColor}`, borderRadius: 6, background: cardBg, color: textPrimary, outline: "none" }}
          data-testid="widget-filter-status"
        >
          <option value="">All Status</option>
          {Object.entries(statusStyles).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <div style={{ flex: 1 }} />
        <div style={{ fontSize: 10, color: textSecondary, alignSelf: "center" }}>
          Review Hub Widget
        </div>
      </div>

      {/* Main Content: Review List + Detail */}
      <div style={{ display: "flex", gap: 12, height: "calc(100vh - 150px)" }}>
        {/* Review List */}
        <div style={{ width: selectedReview ? "40%" : "100%", overflowY: "auto", display: "flex", flexDirection: "column", gap: 6 }} data-testid="widget-review-list">
          {reviews.length === 0 ? (
            <div style={{ textAlign: "center", padding: 40, color: textSecondary, fontSize: 12 }}>No reviews found</div>
          ) : reviews.map((r) => {
            const pc = platformColors[r.platform] || { bg: "#F5F5F4", text: "#57534E", label: r.platform };
            const sc = statusStyles[r.response_status] || statusStyles.pending;
            const isSelected = selectedReview?.id === r.id;
            return (
              <div
                key={r.id}
                onClick={() => handleSelectReview(r)}
                style={{
                  background: isSelected ? (isDark ? "#3E5245" : "#ECFDF5") : cardBg,
                  border: `1px solid ${isSelected ? accentColor : borderColor}`,
                  borderRadius: 8,
                  padding: 12,
                  cursor: "pointer",
                  transition: "all 0.15s",
                  position: "relative",
                }}
                data-testid={`widget-review-${r.id}`}
              >
                {!r.is_read && (
                  <div style={{ position: "absolute", top: 8, right: 8, width: 8, height: 8, borderRadius: "50%", background: "#DC2626", boxShadow: "0 0 4px rgba(220,38,38,0.5)" }} data-testid={`unread-dot-${r.id}`} />
                )}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: textPrimary }}>{r.guest_name}</span>
                    <span style={{ fontSize: 9, padding: "2px 6px", borderRadius: 4, background: pc.bg, color: pc.text, fontWeight: 600 }}>{pc.label}</span>
                  </div>
                  <span style={{ fontSize: 9, padding: "2px 6px", borderRadius: 10, background: sc.bg, color: sc.text, fontWeight: 500 }}>{sc.label}</span>
                </div>
                <StarRating rating={r.rating} size={11} />
                <p style={{ fontSize: 11, color: textSecondary, marginTop: 4, lineHeight: 1.4, overflow: "hidden", textOverflow: "ellipsis", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
                  {r.review_text}
                </p>
                <div style={{ fontSize: 9, color: textSecondary, marginTop: 6, opacity: 0.7 }}>
                  {r.created_at ? new Date(r.created_at).toLocaleDateString() : ""}
                </div>
              </div>
            );
          })}
        </div>

        {/* Review Detail */}
        {selectedReview && (
          <div style={{ flex: 1, background: cardBg, border: `1px solid ${borderColor}`, borderRadius: 8, padding: 16, overflowY: "auto" }} data-testid="widget-review-detail">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
              <div>
                <h3 style={{ fontSize: 14, fontWeight: 600, color: textPrimary }}>{selectedReview.guest_name}</h3>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
                  <StarRating rating={selectedReview.rating} size={13} />
                  <span style={{ fontSize: 10, padding: "2px 6px", borderRadius: 4, background: (platformColors[selectedReview.platform] || {}).bg, color: (platformColors[selectedReview.platform] || {}).text, fontWeight: 600 }}>
                    {(platformColors[selectedReview.platform] || { label: selectedReview.platform }).label}
                  </span>
                </div>
              </div>
              <button onClick={() => setSelectedReview(null)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 16, color: textSecondary, padding: 4 }} data-testid="close-detail">&times;</button>
            </div>

            <div style={{ background: isDark ? "#1C1917" : "#F5F5F4", borderRadius: 6, padding: 12, marginBottom: 12 }}>
              <p style={{ fontSize: 12, color: textPrimary, lineHeight: 1.6 }}>{selectedReview.review_text}</p>
            </div>

            {/* Response Section */}
            <div style={{ borderTop: `1px solid ${borderColor}`, paddingTop: 12 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: textPrimary }}>Response</span>
                {(!selectedReview.response_text || selectedReview.response_status === "pending") && (
                  <button
                    onClick={() => handleGenerateResponse(selectedReview.id)}
                    disabled={generating}
                    style={{
                      fontSize: 10, padding: "5px 10px", borderRadius: 6, border: "none",
                      background: generating ? "#A8A29E" : accentColor, color: "#FFF",
                      cursor: generating ? "wait" : "pointer", fontWeight: 600, display: "flex", alignItems: "center", gap: 4
                    }}
                    data-testid="widget-generate-ai-btn"
                  >
                    {generating ? (
                      <><span style={{ width: 10, height: 10, border: "2px solid #FFF4", borderTopColor: "#FFF", borderRadius: "50%", display: "inline-block", animation: "spin 0.8s linear infinite" }} /> Generating...</>
                    ) : (
                      "Generate AI Response"
                    )}
                  </button>
                )}
              </div>
              {selectedReview.response_text ? (
                <div style={{ background: isDark ? "#1C1917" : "#ECFDF5", borderRadius: 6, padding: 12 }}>
                  <p style={{ fontSize: 12, color: textPrimary, lineHeight: 1.6 }}>{selectedReview.response_text}</p>
                  <div style={{ marginTop: 8, fontSize: 9, color: textSecondary }}>
                    Status: {(statusStyles[selectedReview.response_status] || {}).label || selectedReview.response_status}
                    {selectedReview.response_generated_at && ` · Generated ${new Date(selectedReview.response_generated_at).toLocaleString()}`}
                  </div>
                </div>
              ) : (
                <p style={{ fontSize: 11, color: textSecondary, fontStyle: "italic" }}>No response yet. Click "Generate AI Response" to create one.</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
