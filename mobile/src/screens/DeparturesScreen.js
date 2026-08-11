import { useEffect, useState, useCallback } from "react";
import { View, Text, FlatList, RefreshControl, StyleSheet, TouchableOpacity, Alert } from "react-native";
import api from "../api";
import { colors, card } from "../theme";

export default function DeparturesScreen() {
  const [items, setItems] = useState([]);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [ta, sc] = await Promise.all([
        api.get("/bookings/timeline/all/todays-actions"),
        api.get("/checkout/scheduled/today").catch(() => ({ data: { items: [] } })),
      ]);
      const departures = (ta.data.departures || []).map((d) => ({ ...d, kind: "departure" }));
      const scheduledIds = new Set((sc.data.items || []).map((x) => x.booking_id));
      const scheduled = (sc.data.items || []).map((x) => ({
        id: x.booking_id, guest_name: x.guest_name, room_number: x.room_number,
        checkout_at: x.checkout_at, minutes_left: x.minutes_left,
        is_overdue: x.is_overdue, kind: "scheduled",
      }));
      setItems([...scheduled, ...departures.filter((d) => !scheduledIds.has(d.id))]);
    } catch (e) { /* silent */ }
  }, []);

  useEffect(() => { load(); }, [load]);
  const onRefresh = async () => { setRefreshing(true); await load(); setRefreshing(false); };

  const checkOut = (b) => {
    Alert.alert("Check-out", `${b.guest_name} çıkış yapsın mı?`, [
      { text: "Vazgeç" },
      {
        text: "Check-out Yap",
        style: "destructive",
        onPress: async () => {
          try {
            if (b.kind === "scheduled") {
              await api.post(`/checkout/scheduled/${b.id}/execute-now`);
            } else {
              await api.put(`/bookings/${b.id}/status`, null, { params: { status: "checked_out" } });
            }
            load();
          } catch (e) {
            Alert.alert("Hata", e.response?.data?.detail || "Check-out başarısız");
          }
        },
      },
    ]);
  };

  return (
    <View style={s.wrap}>
      <Text style={s.h1}>Bugünkü Çıkışlar</Text>
      <FlatList
        data={items}
        keyExtractor={(b) => `${b.kind}-${b.id}`}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        renderItem={({ item: b }) => (
          <View style={[card, s.item]}>
            <View style={{ flex: 1 }}>
              <Text style={s.guest}>{b.guest_name || "Misafir"}</Text>
              <Text style={s.sub}>
                {b.room_number ? `Oda ${b.room_number} · ` : ""}
                {b.kind === "scheduled"
                  ? (b.is_overdue ? "⚠ Planlı saat geçti" : `Planlı · ${Math.max(b.minutes_left || 0, 0)} dk kaldı`)
                  : `Check-out: ${b.check_out || "bugün"}`}
              </Text>
            </View>
            {b.status === "checked_out" ? (
              <Text style={s.done}>✓ Çıktı</Text>
            ) : (
              <TouchableOpacity style={[s.btn, b.is_overdue && s.btnWarn]} onPress={() => checkOut(b)}>
                <Text style={s.btnTxt}>Check-out</Text>
              </TouchableOpacity>
            )}
          </View>
        )}
        ListEmptyComponent={<Text style={s.sub}>Bugün çıkış yok</Text>}
      />
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.bg, padding: 16 },
  h1: { fontSize: 26, fontWeight: "900", color: colors.text, marginBottom: 12 },
  item: { flexDirection: "row", alignItems: "center", marginBottom: 8 },
  guest: { fontSize: 14, fontWeight: "700", color: colors.text },
  sub: { fontSize: 11, color: colors.sub, marginTop: 2 },
  btn: { backgroundColor: "#B45309", borderRadius: 10, paddingHorizontal: 14, paddingVertical: 9 },
  btnWarn: { backgroundColor: "#DC2626" },
  btnTxt: { color: "#fff", fontWeight: "800", fontSize: 12 },
  done: { color: colors.emerald, fontWeight: "800", fontSize: 12 },
});
