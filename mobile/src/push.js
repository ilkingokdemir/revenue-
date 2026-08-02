import * as Notifications from "expo-notifications";
import * as Device from "expo-device";
import api from "./api";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

export async function registerPush() {
  try {
    if (!Device.isDevice) return null;
    const { status: existing } = await Notifications.getPermissionsAsync();
    let status = existing;
    if (existing !== "granted") {
      const req = await Notifications.requestPermissionsAsync();
      status = req.status;
    }
    if (status !== "granted") return null;
    const { data: token } = await Notifications.getExpoPushTokenAsync();
    await api.post("/mobile/push-token", { token, platform: Device.osName || "unknown" });
    return token;
  } catch (e) {
    return null;
  }
}
