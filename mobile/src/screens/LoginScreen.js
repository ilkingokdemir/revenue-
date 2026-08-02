import { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ActivityIndicator, KeyboardAvoidingView, Platform } from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { login, DEFAULT_SERVER } from "../api";
import { colors } from "../theme";

export default function LoginScreen({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [server, setServer] = useState(DEFAULT_SERVER);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      await AsyncStorage.setItem("server_url", server.trim());
      await login(email.trim(), password);
      onLogin();
    } catch (e) {
      setError(e.response?.data?.detail || "Giriş başarısız — bilgileri kontrol edin");
    }
    setBusy(false);
  };

  return (
    <KeyboardAvoidingView style={s.wrap} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <Text style={s.logo}>MyHotelBox</Text>
      <Text style={s.sub}>Otel PMS & Gelir Yönetimi</Text>
      <TextInput style={s.input} placeholder="Sunucu URL" autoCapitalize="none" value={server} onChangeText={setServer} />
      <TextInput style={s.input} placeholder="E-posta" autoCapitalize="none" keyboardType="email-address" value={email} onChangeText={setEmail} />
      <TextInput style={s.input} placeholder="Şifre" secureTextEntry value={password} onChangeText={setPassword} />
      {error ? <Text style={s.err}>{error}</Text> : null}
      <TouchableOpacity style={s.btn} onPress={submit} disabled={busy}>
        {busy ? <ActivityIndicator color="#fff" /> : <Text style={s.btnTxt}>Giriş Yap</Text>}
      </TouchableOpacity>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.text, justifyContent: "center", padding: 28 },
  logo: { fontSize: 32, fontWeight: "900", color: "#fff", textAlign: "center" },
  sub: { fontSize: 13, color: "#a8a29e", textAlign: "center", marginBottom: 32 },
  input: { backgroundColor: "#292524", borderRadius: 12, padding: 14, color: "#fff", marginBottom: 10, fontSize: 14 },
  btn: { backgroundColor: colors.accent, borderRadius: 12, padding: 15, alignItems: "center", marginTop: 8 },
  btnTxt: { color: "#fff", fontWeight: "700", fontSize: 15 },
  err: { color: "#fda4af", fontSize: 12, marginBottom: 6 },
});
