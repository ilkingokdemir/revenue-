import { useState, useEffect, useCallback } from "react";
import { Lightning, Eye, Fire, Users, Clock } from "@phosphor-icons/react";
import { useLanguage } from "../i18n/LanguageContext";

const NOTIFICATION_TYPES = [
  { type: "viewing", icon: Eye, getMessage: (count) => `${count} people are looking at this property right now` },
  { type: "recent", icon: Fire, getMessage: (count) => `${count} bookings in the last 24 hours` },
  { type: "lastBooked", icon: Clock, getMessage: () => { const mins = Math.floor(Math.random() * 120) + 5; return mins < 60 ? `Last booked ${mins} minutes ago` : `Last booked ${Math.floor(mins / 60)}h ${mins % 60}m ago`; }},
  { type: "popular", icon: Users, getMessage: () => "Most popular property this week" },
];

export function SocialProofNotifications({ settings, recentBookings, roomsData }) {
  const { t: tr } = useLanguage();
  const [currentNotif, setCurrentNotif] = useState(null);
  const [visible, setVisible] = useState(false);
  const [notifQueue, setNotifQueue] = useState([]);
  const [cycleIndex, setCycleIndex] = useState(0);

  const buildQueue = useCallback(() => {
    if (!settings?.enabled) return [];
    const q = [];
    if (settings.show_viewing_count) {
      const viewCount = Math.floor(Math.random() * 12) + 3;
      q.push({ ...NOTIFICATION_TYPES[0], data: viewCount });
    }
    if (settings.show_recent_bookings && recentBookings > 0) {
      q.push({ ...NOTIFICATION_TYPES[1], data: recentBookings });
    }
    if (recentBookings > 0) {
      q.push({ ...NOTIFICATION_TYPES[2], data: 0 });
    }
    if (settings.show_rooms_left && roomsData) {
      const lowStock = roomsData.filter(r => r.available_rooms <= 3 && r.available_rooms > 0);
      if (lowStock.length > 0) {
        q.push({
          type: "lowStock", icon: Lightning,
          getMessage: () => `Only ${lowStock[0].available_rooms} ${lowStock[0].name} rooms left!`,
          data: 0,
        });
      }
    }
    return q;
  }, [settings, recentBookings, roomsData]);

  useEffect(() => {
    const q = buildQueue();
    setNotifQueue(q);
  }, [buildQueue]);

  useEffect(() => {
    if (notifQueue.length === 0) return;

    const showNext = () => {
      const idx = cycleIndex % notifQueue.length;
      const notif = notifQueue[idx];
      setCurrentNotif(notif);
      setVisible(true);

      // Hide after 4 seconds
      setTimeout(() => {
        setVisible(false);
      }, 4000);

      setCycleIndex(prev => prev + 1);
    };

    // Show first one after 3s, then cycle every 12s
    const initialDelay = setTimeout(showNext, 3000);
    const interval = setInterval(showNext, 12000);

    return () => { clearTimeout(initialDelay); clearInterval(interval); };
  }, [notifQueue, cycleIndex]);

  if (!settings?.enabled || !currentNotif) return null;

  const Icon = currentNotif.icon;
  const message = currentNotif.getMessage(currentNotif.data);

  return (
    <div
      className={`fixed bottom-20 sm:bottom-6 left-4 sm:left-6 z-50 transition-all duration-500 ${visible ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0 pointer-events-none"}`}
      data-testid="social-proof-notification"
    >
      <div className="bg-white border border-gray-200 rounded-xl shadow-2xl px-4 py-3 flex items-center gap-3 max-w-sm">
        <div className="w-9 h-9 rounded-full bg-orange-100 flex items-center justify-center flex-shrink-0">
          <Icon size={18} weight="fill" className="text-orange-600" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-slate-800 leading-tight">{message}</p>
          <p className="text-[10px] text-slate-400 mt-0.5">Verified activity</p>
        </div>
      </div>
    </div>
  );
}
