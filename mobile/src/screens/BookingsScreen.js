import { useEffect, useState, useCallback } from "react";
import { View, Text, FlatList, RefreshControl, StyleSheet } from "react-native";
import api from "../api";
import { colors, card } from "../theme";

const STATUS_COLOR = { confirmed: colors.emerald, cancelled: colors.rose, checked_in: colors.accent, checked_out: colors.sub };
const PAY_COLOR = { paid: colors.emerald, partial: colors.amber, pending: colors.rose };

export default function BookingsScreen() {
  const [bookings, setBookings] = useState([]);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/bookings");
      setBookings((data || []).slice(0, 100));
    } catch (e) { /* silent */ }
  }, []);

  useEffect(() => { load(); }, [load]);
  const onRefresh = async () => { setRefreshing(true); await load(); setRefreshing(false); };

  return (
    <View style={s.wrap}>
      <Text style={s.h1}>Rezervasyonlar</Text>
      <FlatList
        data={bookings}
        keyExtractor={(b) => b.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        renderItem={({ item: b }) => (
          <View style={[card, s.item]}>
            <View style={{ flex: 1 }}>
              <Text style={s.guest}>{b.guest_name}</Text>
              <Text style={s.dates}>{b.check_in} → {b.check_out} · {b.rooms || 1} oda · {b.source || "Direct"}</Text>
              <View style={s.badges}>
                <Text style={[s.badge, { color: STATUS_COLOR[b.status] || colors.sub }]}>{b.status}</Text>
                <Text style={[s.badge, { color: PAY_COLOR[b.payment_status] || colors.sub }]}>{b.payment_status}</Text>
              </View>
            </View>
            <Text style={s.price}>£{Number(b.total_price || 0).toFixed(0)}</Text>
          </View>
        )}
      />
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.bg, padding: 16 },
  h1: { fontSize: 26, fontWeight: "900", color: colors.text, marginBottom: 12 },
  item: { flexDirection: "row", alignItems: "center", marginBottom: 8 },
  guest: { fontSize: 14, fontWeight: "700", color: colors.text },
  dates: { fontSize: 11, color: colors.sub, marginTop: 2 },
  badges: { flexDirection: "row", gap: 10, marginTop: 4 },
  badge: { fontSize: 10, fontWeight: "700", textTransform: "uppercase" },
  price: { fontSize: 16, fontWeight: "900", color: colors.text },
});
