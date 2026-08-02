import { useEffect, useState } from "react";
import { Text, ActivityIndicator, View } from "react-native";
import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { StatusBar } from "expo-status-bar";
import { getToken } from "./src/api";
import LoginScreen from "./src/screens/LoginScreen";
import DashboardScreen from "./src/screens/DashboardScreen";
import BookingsScreen from "./src/screens/BookingsScreen";
import PaymentsScreen from "./src/screens/PaymentsScreen";
import { colors } from "./src/theme";

const Tab = createBottomTabNavigator();
const icon = (glyph) => ({ color }) => <Text style={{ fontSize: 18, color }}>{glyph}</Text>;

export default function App() {
  const [authed, setAuthed] = useState(null);

  useEffect(() => {
    getToken().then((t) => setAuthed(!!t));
  }, []);

  if (authed === null) {
    return <View style={{ flex: 1, justifyContent: "center" }}><ActivityIndicator /></View>;
  }
  if (!authed) return <LoginScreen onLogin={() => setAuthed(true)} />;

  return (
    <NavigationContainer>
      <StatusBar style="dark" />
      <Tab.Navigator
        screenOptions={{
          headerShown: false,
          tabBarActiveTintColor: colors.accent,
          tabBarInactiveTintColor: colors.sub,
          tabBarStyle: { backgroundColor: "#fff", borderTopColor: colors.border },
        }}
      >
        <Tab.Screen name="Bugün" component={DashboardScreen} options={{ tabBarIcon: icon("◉") }} />
        <Tab.Screen name="Rezervasyonlar" component={BookingsScreen} options={{ tabBarIcon: icon("▤") }} />
        <Tab.Screen name="Ödemeler" options={{ tabBarIcon: icon("£") }}>
          {() => <PaymentsScreen onLogout={() => setAuthed(false)} />}
        </Tab.Screen>
      </Tab.Navigator>
    </NavigationContainer>
  );
}
