import { useEffect, useState, useCallback } from "react";
import { View, Text, FlatList, RefreshControl, StyleSheet, TouchableOpacity, Alert } from "react-native";
import api, { logout } from "../api";
import { colors, card } from "../theme";

export default function PaymentsScreen({ onLogout }) {
  const [links, setLinks] = useState([]);
  const [stats, setStats] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [l, st] = await Promise.all([
        api.get("/pay-links/history"),
        api.get("/pay-links/stats"),
      ]);
      setLinks(l.data || []);
      setStats(st.data);
    } catch (e) { /* silent */ }
  }, []);

  useEffect(() => { load(); }, [load]);
  const onRefresh = async () => { setRefreshing(true); await load(); setRefreshing(false); };

  const doLogout = () => {
    Alert.alert("Çıkış", "Oturumu kapatmak istiyor musunuz?", [
      { text: "Vazgeç" },
      { text: "Çıkış Yap", style: "destructive", onPress: async () => { await logout(); onLogout(); } },
    ]);
  };

  return (
    <View style={s.wrap}>
      <View style={s.head}>
        <Text style={s.h1}>Ödemeler</Text>
        <TouchableOpacity onPress={doLogout}><Text style={s.out}>Çıkış</Text></TouchableOpacity>
      </View>
      {stats && (
        <View style={s.row}>
          <View style={[card, s.kpi]}><Text style={s.kpiVal}>{stats.total_links}</Text><Text style={s.kpiLbl}>Link</Text></View>
          <View style={[card, s.kpi]}><Text style={[s.kpiVal, { color: colors.emerald }]}>{stats.paid_links}</Text><Text style={s.kpiLbl}>Ödendi</Text></View>
          <View style={[card, s.kpi]}><Text style={[s.kpiVal, { color: colors.amber }]}>%{stats.conversion_pct}</Text><Text style={s.kpiLbl}>Dönüşüm</Text></View>
          <View style={[card, s.kpi]}><Text style={[s.kpiVal, { color: colors.emerald }]}>£{stats.total_collected}</Text><Text style={s.kpiLbl}>Tahsilat</Text></View>
        </View>
      )}
      <FlatList
        data={links}
        keyExtractor={(l, i) => l.session_id || String(i)}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        renderItem={({ item: l }) => (
          <View style={[card, s.item]}>
            <View style={{ flex: 1 }}>
              <Text style={s.guest}>{l.guest_name || "Misafir"} {l.booking_ref ? `· ${l.booking_ref}` : ""}</Text>
              <Text style={s.sub}>{(l.created_at || "").slice(0, 16).replace("T", " ")}{l.created_by === "auto_reminder" ? " · HATIRLATMA" : ""}</Text>
            </View>
            <View style={{ alignItems: "flex-end" }}>
              <Text style={s.amount}>£{Number(l.amount || 0).toFixed(2)}</Text>
              <Text style={[s.status, { color: l.payment_status === "paid" ? colors.emerald : colors.amber }]}>{l.payment_status}</Text>
            </View>
          </View>
        )}
      />
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.bg, padding: 16 },
  head: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 12 },
  h1: { fontSize: 26, fontWeight: "900", color: colors.text },
  out: { color: colors.rose, fontWeight: "700", fontSize: 13 },
  row: { flexDirection: "row", gap: 6, marginBottom: 10 },
  kpi: { flex: 1, alignItems: "center", padding: 10 },
  kpiVal: { fontSize: 16, fontWeight: "900", color: colors.text },
  kpiLbl: { fontSize: 9, color: colors.sub, textTransform: "uppercase", fontWeight: "600" },
  item: { flexDirection: "row", alignItems: "center", marginBottom: 8 },
  guest: { fontSize: 13, fontWeight: "700", color: colors.text },
  sub: { fontSize: 10, color: colors.sub, marginTop: 2 },
  amount: { fontSize: 15, fontWeight: "900", color: colors.text },
  status: { fontSize: 10, fontWeight: "700", textTransform: "uppercase" },
});
