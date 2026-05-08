import { Star } from "@phosphor-icons/react";
import { motion } from "framer-motion";
import { CheckCircle, WarningCircle, ClockCounterClockwise, X } from "@phosphor-icons/react";
import { PLATFORMS } from "./config";

export const StarRating = ({ rating, size = 16 }) => {
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

export const PlatformBadge = ({ platform }) => {
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

export const StatsCard = ({ icon: Icon, label, value, subtext }) => (
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

export const ReviewCard = ({ review, isSelected, onClick }) => {
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
            {review.response_status === "pending" && (
              <span className="flex items-center gap-1 text-[11px] font-medium text-amber-600">
                <WarningCircle size={12} weight="fill" />
                Pending
              </span>
            )}
            {review.response_status === "pending_approval" && (
              <span className="flex items-center gap-1 text-[11px] font-medium text-blue-600">
                <ClockCounterClockwise size={12} weight="fill" />
                Awaiting Approval
              </span>
            )}
            {review.response_status === "rejected" && (
              <span className="flex items-center gap-1 text-[11px] font-medium text-red-600">
                <X size={12} weight="bold" />
                Rejected
              </span>
            )}
            {review.response_status === "responded" && (
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
