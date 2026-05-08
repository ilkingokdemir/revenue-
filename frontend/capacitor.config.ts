/// <reference types="@capacitor/cli" />
import type { CapacitorConfig } from "@capacitor/cli";

/**
 * Capacitor configuration for Hotel PMS & Revenue Management.
 *
 * Build flow on a developer Mac (iOS) or any machine (Android):
 *   yarn build                    # produce ./build
 *   npx cap add ios               # one-time, on macOS only
 *   npx cap add android           # one-time
 *   npx cap sync                  # copy web assets + plugins
 *   npx cap open ios              # opens Xcode
 *   npx cap open android          # opens Android Studio
 *
 * `server.url` is intentionally empty so the bundle ships with web assets
 * inlined; flip it to your dashboard URL in development to live-reload from
 * a running React dev server.
 */
const config: CapacitorConfig = {
  appId: "com.hotelpms.app",
  appName: "Hotel PMS",
  webDir: "build",
  bundledWebRuntime: false,
  ios: {
    contentInset: "automatic",
    scheme: "HotelPMS",
    backgroundColor: "#0c0a09",
  },
  android: {
    backgroundColor: "#0c0a09",
    allowMixedContent: false,
  },
  server: {
    androidScheme: "https",
    iosScheme: "https",
    cleartext: false,
    // Uncomment for live-reload during development
    // url: "https://your-tunnel-url.ngrok.io",
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 1500,
      backgroundColor: "#3E5245",
      androidSplashResourceName: "splash",
      androidScaleType: "CENTER_CROP",
      showSpinner: false,
    },
    PushNotifications: {
      presentationOptions: ["badge", "sound", "alert"],
    },
    Keyboard: {
      resize: "body",
      style: "DARK",
    },
  },
};

export default config;
