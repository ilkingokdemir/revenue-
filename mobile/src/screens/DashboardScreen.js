import { useEffect, useState, useCallback } from "react";
import { View, Text, ScrollView, RefreshControl, StyleSheet, Switch } from "react-native";
import api from "../api";
import { colors, card } from "../theme";

const PREF_LABELS = {
  payment_received: "Ödeme alındı bildirimleri",
  pickup_strong: "Güçlü satış günü bildirimleri",
  channel_drop: "Kanal düşüş uyarıları",
  new_complaint: "Yeni şikayet bildirimleri",
};

const Kpi = ({ label, value, color = colors.text }) => (
  <View style={[card, s.kpi]}>
    <Text style={[s.kpiVal, { color }]}>{value}</Text>
    <Text style={s.kpiLbl}>{label}</Text>
  </View>
);

export default function DashboardScreen() {
  const [pickup, setPickup] = useState(null);
  const [notifs, setNotifs] = useState([]);
  const [refreshing, setRefreshing] = useState(false);
  const [prefs, setPrefs] = useState(null);

  useEffect(() => {
    api.get("/mobile/push-prefs").then(({ data }) => setPrefs(data)).catch(() => {});
  }, []);

  const togglePref = async (key) => {
    const next = { ...prefs, [key]: !prefs[key] };
    setPrefs(next);
    try { await api.post("/mobile/push-prefs", next); } catch (e) { /* silent */ }
  };

  const load = useCallback(async () => {
    try {
      const [p, n] = await Promise.all([
        api.get("/pulse/pickup-24h"),
        api.get("/dashboard/notifications/all"),
      ]);
      setPickup(p.data);
      setNotifs(n.data.notifications?.slice(0, 8) || []);
    } catch (e) { /* silent */ }
  }, []);

  useEffect(() => { load(); }, [load]);
  const onRefresh = async () => { setRefreshing(true); await load(); setRefreshing(false); };

  return (
    <ScrollView style={s.wrap} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}>
      <Text style={s.h1}>Bugün</Text>
      {pickup && (
        <>
          <Text style={s.section}>24 Saat Pickup</Text>
          <View style={s.row}>
            <Kpi label="Satılan Oda" value={pickup.rooms_sold_24h} color={colors.rose} />
            <Kpi label="Pickup %" value={`%${pickup.pickup_pct}`} />
          </View>
          <View style={s.row}>
            <Kpi label="Gelir (24s)" value={`£${(pickup.revenue_24h || 0).toLocaleString()}`} color={colors.emerald} />
            <Kpi label="ADR" value={`£${pickup.adr_24h}`} color={colors.accent} />
          </View>
          {pickup.target?.target_rooms > 0 && (
            <View style={[card, { marginTop: 8 }]}>
              <Text style={s.kpiLbl}>Aylık Hedef — {pickup.target.month}</Text>
              <Text style={s.tgt}>{pickup.target.mtd_rooms} / {pickup.target.target_rooms} oda (%{pickup.target.progress_pct})</Text>
              <View style={s.barBg}>
                <View style={[s.bar, { width: `${Math.min(100, pickup.target.progress_pct)}%` }]} />
              </View>
            </View>
          )}
        </>
      )}
      <Text style={s.section}>Bildirimler</Text>
      {notifs.map((n, i) => (
        <View key={i} style={[card, { marginBottom: 8 }]}>
          <Text style={s.notifTitle}>{n.title}</Text>
          {n.subtitle ? <Text style={s.notifSub}>{n.subtitle}</Text> : null}
        </View>
      ))}
      {notifs.length === 0 && <Text style={s.notifSub}>Bildirim yok</Text>}
      <View style={{ height: 30 }} />
    </ScrollView>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.bg, padding: 16 },
  h1: { fontSize: 26, fontWeight: "900", color: colors.text, marginBottom: 4 },
  section: { fontSize: 12, fontWeight: "700", color: colors.sub, textTransform: "uppercase", marginTop: 16, marginBottom: 8 },
  row: { flexDirection: "row", gap: 8, marginBottom: 8 },
  kpi: { flex: 1, alignItems: "center" },
  kpiVal: { fontSize: 22, fontWeight: "900" },
  kpiLbl: { fontSize: 10, color: colors.sub, textTransform: "uppercase", fontWeight: "600" },
  tgt: { fontSize: 15, fontWeight: "700", color: colors.text, marginVertical: 4 },
  barBg: { height: 6, backgroundColor: "#e7e5e4", borderRadius: 3 },
  bar: { height: 6, backgroundColor: colors.accent, borderRadius: 3 },
  notifTitle: { fontSize: 13, fontWeight: "700", color: colors.text },
  notifSub: { fontSize: 11, color: colors.sub, marginTop: 2 },
  prefRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8, paddingVertical: 8 },
  prefLbl: { fontSize: 13, color: colors.text, fontWeight: "600" },
});
