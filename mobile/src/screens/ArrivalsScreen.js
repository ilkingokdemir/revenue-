import { useEffect, useState, useCallback } from "react";
import { View, Text, FlatList, RefreshControl, StyleSheet, TouchableOpacity, Alert } from "react-native";
import api from "../api";
import { colors, card } from "../theme";

export default function ArrivalsScreen() {
  const [items, setItems] = useState([]);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/arrivals/all", { params: { window: "today" } });
      setItems(data.arrivals || data || []);
    } catch (e) { /* silent */ }
  }, []);

  useEffect(() => { load(); }, [load]);
  const onRefresh = async () => { setRefreshing(true); await load(); setRefreshing(false); };

  const checkIn = (b) => {
    Alert.alert("Check-in", `${b.guest_name} giriş yapsın mı?`, [
      { text: "Vazgeç" },
      {
        text: "Check-in Yap",
        onPress: async () => {
          try {
            await api.put(`/bookings/${b.id}/status`, null, { params: { status: "checked_in" } });
            load();
          } catch (e) {
            Alert.alert("Hata", e.response?.data?.detail || "Check-in başarısız");
          }
        },
      },
    ]);
  };

  return (
    <View style={s.wrap}>
      <Text style={s.h1}>Bugünkü Girişler</Text>
      <FlatList
        data={items}
        keyExtractor={(b) => b.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        renderItem={({ item: b }) => (
          <View style={[card, s.item]}>
            <View style={{ flex: 1 }}>
              <Text style={s.guest}>{b.guest_name}</Text>
              <Text style={s.sub}>{b.booking_ref} · {b.rooms || 1} oda · {b.nights || 1} gece · {b.payment_status}</Text>
            </View>
            {b.status === "checked_in" ? (
              <Text style={s.done}>✓ İçeride</Text>
            ) : (
              <TouchableOpacity style={s.btn} onPress={() => checkIn(b)}>
                <Text style={s.btnTxt}>Check-in</Text>
              </TouchableOpacity>
            )}
          </View>
        )}
        ListEmptyComponent={<Text style={s.sub}>Bugün giriş yok</Text>}
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
  btn: { backgroundColor: colors.accent, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 9 },
  btnTxt: { color: "#fff", fontWeight: "800", fontSize: 12 },
  done: { color: colors.emerald, fontWeight: "800", fontSize: 12 },
});
