import { useEffect, useState, useCallback } from "react";
import { View, Text, FlatList, RefreshControl, StyleSheet, TouchableOpacity } from "react-native";
import api from "../api";
import { colors, card } from "../theme";

const NEXT = { dirty: "in_progress", in_progress: "clean", clean: "inspected", inspected: "dirty", out_of_order: "out_of_order" };
const LABEL = { dirty: "Kirli", in_progress: "Temizleniyor", clean: "Temiz", inspected: "Kontrol Edildi", out_of_order: "Arızalı" };
const COLOR = { dirty: colors.rose, in_progress: colors.amber, clean: colors.emerald, inspected: colors.accent, out_of_order: colors.sub };

export default function HousekeepingScreen() {
  const [props, setProps] = useState([]);
  const [pid, setPid] = useState(null);
  const [rooms, setRooms] = useState([]);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    api.get("/properties").then(({ data }) => {
      setProps(data || []);
      if (data?.length) setPid(data[0].id);
    }).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    if (!pid) return;
    try {
      const { data } = await api.get(`/housekeeping/rooms/${pid}`);
      setRooms(data || []);
    } catch (e) { /* silent */ }
  }, [pid]);

  useEffect(() => { load(); }, [load]);
  const onRefresh = async () => { setRefreshing(true); await load(); setRefreshing(false); };

  const cycle = async (room) => {
    const next = NEXT[room.status] || "clean";
    setRooms((rs) => rs.map((r) => (r.id === room.id ? { ...r, status: next } : r)));
    try {
      await api.put(`/housekeeping/rooms/${room.id}/status`, { status: next });
    } catch (e) { load(); }
  };

  return (
    <View style={s.wrap}>
      <Text style={s.h1}>Housekeeping</Text>
      <FlatList
        horizontal={false}
        ListHeaderComponent={
          <FlatList
            horizontal
            showsHorizontalScrollIndicator={false}
            data={props}
            keyExtractor={(p) => p.id}
            style={{ marginBottom: 10 }}
            renderItem={({ item: p }) => (
              <TouchableOpacity onPress={() => setPid(p.id)}
                style={[s.chip, pid === p.id && s.chipActive]}>
                <Text style={[s.chipTxt, pid === p.id && s.chipTxtActive]}>{p.name}</Text>
              </TouchableOpacity>
            )}
          />
        }
        data={rooms}
        keyExtractor={(r) => r.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        renderItem={({ item: r }) => (
          <TouchableOpacity style={[card, s.item]} onPress={() => cycle(r)}>
            <View style={{ flex: 1 }}>
              <Text style={s.room}>Oda {r.room_number || r.id}</Text>
              <Text style={s.sub}>{r.floor ? `Kat ${r.floor} · ` : ""}dokunarak durumu değiştir</Text>
            </View>
            <View style={[s.status, { backgroundColor: (COLOR[r.status] || colors.sub) + "22" }]}>
              <Text style={[s.statusTxt, { color: COLOR[r.status] || colors.sub }]}>{LABEL[r.status] || r.status}</Text>
            </View>
          </TouchableOpacity>
        )}
        ListEmptyComponent={<Text style={s.sub}>Bu tesiste oda durumu kaydı yok</Text>}
      />
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.bg, padding: 16 },
  h1: { fontSize: 26, fontWeight: "900", color: colors.text, marginBottom: 12 },
  chip: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 999, backgroundColor: "#fff", borderWidth: 1, borderColor: colors.border, marginRight: 6 },
  chipActive: { backgroundColor: colors.text, borderColor: colors.text },
  chipTxt: { fontSize: 12, color: colors.sub, fontWeight: "600" },
  chipTxtActive: { color: "#fff" },
  item: { flexDirection: "row", alignItems: "center", marginBottom: 8 },
  room: { fontSize: 14, fontWeight: "700", color: colors.text },
  sub: { fontSize: 11, color: colors.sub, marginTop: 2 },
  status: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 999 },
  statusTxt: { fontSize: 11, fontWeight: "800" },
});
