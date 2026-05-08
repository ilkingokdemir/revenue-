# Hotel PMS — Native Mobile Apps via Capacitor

This document explains how to wrap our React frontend as **native iOS and
Android apps** with Capacitor 7. The same React codebase runs in:

* Browser (current default)
* PWA (already installable via `PwaInstallButton`)
* iOS native app (App Store)
* Android native app (Google Play)

## Why Capacitor?

* Single codebase → 3 distribution channels.
* Native splash screen, push notifications, camera, biometrics.
* Receptionists can use their own phone instead of a tablet — full PMS in
  their pocket.
* Apple / Google Pay support.

## Prerequisites

| Platform | Tool                          | Version |
|----------|-------------------------------|---------|
| Both     | Node                          | 22+ (Capacitor 7) |
| Both     | Yarn                          | 1.22+   |
| iOS      | macOS                         | required |
| iOS      | Xcode + CLI tools             | 15+     |
| iOS      | CocoaPods                     | latest  |
| Android  | Android Studio                | Hedgehog+ |
| Android  | JDK                           | 17      |

## One-time setup (on your Mac for iOS, any OS for Android)

```bash
cd frontend
bash scripts/capacitor-setup.sh           # adds ios/, android/, runs sync
```

This will:

1. Run `yarn build` to produce `build/`.
2. Add the iOS native project (`ios/`) — only on macOS.
3. Add the Android native project (`android/`).
4. Run `npx cap sync` to copy web assets + plugins.

After this you have two checked-in folders (`ios/`, `android/`) that you
should commit to your repo so other developers can build them.

## Daily workflow

```bash
# After any frontend code change:
yarn build && npx cap sync

# Open native IDE to build / run on simulator:
npx cap open ios       # Xcode
npx cap open android   # Android Studio
```

## What's already configured

`capacitor.config.ts` defines:

* App ID: `com.hotelpms.app` (rename to your actual reverse-DNS bundle ID)
* App name: `Hotel PMS`
* Splash screen: 1.5s on brand color `#3E5245`
* Push notifications: alerts, badges, sounds enabled
* Background color: `#0c0a09` (matches the dark dashboard chrome)
* Keyboard auto-resize for chat-like screens
* HTTPS-only — no cleartext on Android

## Plugins included

| Plugin                              | What it adds |
|-------------------------------------|--------------|
| `@capacitor/push-notifications`     | APNs / FCM push, foreground / background handling |
| `@capacitor/camera`                 | ID/passport scan, room damage photos |
| `@capacitor/preferences`            | Native key-value storage (replaces localStorage on device) |
| `@capacitor/network`                | Offline detection for self-checkin kiosk mode |
| `@capacitor/app`                    | App lifecycle, deep links, back-button handling |

## Permissions

iOS — add to `ios/App/App/Info.plist`:

```xml
<key>NSCameraUsageDescription</key>
<string>Used to scan IDs at check-in and capture maintenance issues.</string>
<key>NSPhotoLibraryUsageDescription</key>
<string>Used to attach photos to maintenance tickets.</string>
```

Android — add to `android/app/src/main/AndroidManifest.xml`:

```xml
<uses-permission android:name="android.permission.CAMERA" />
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
```

## Push notifications setup

* iOS: enable Push Notifications capability in Xcode → Signing & Capabilities,
  upload your APNs key to your push provider.
* Android: drop your `google-services.json` (Firebase) into
  `android/app/`. The push plugin will pick it up automatically.

Backend dispatch can use Firebase Admin SDK or a service like OneSignal —
both call our existing `/api/notifications` flow.

## Live-reload during development

Edit `capacitor.config.ts` and uncomment `server.url`:

```ts
server: {
  url: "http://YOUR-MAC-LAN-IP:3000",
  cleartext: true,
},
```

Run `yarn start` on your Mac, then `npx cap run ios --livereload` to point
the simulator at the live React dev server.

## Build for the App Store

1. In Xcode: Product → Archive.
2. Distribute via App Store Connect.
3. `appId` must match your App Store Connect record.

## Build for Google Play

1. In Android Studio: Build → Generate Signed Bundle / APK → Android App
   Bundle.
2. Upload the `.aab` to Play Console → Production track.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `pod install` fails | `cd ios/App && pod repo update && pod install` |
| Webview is blank | Check Safari Web Inspector / chrome://inspect — your `REACT_APP_BACKEND_URL` must be HTTPS |
| Push doesn't arrive on iOS | Xcode → Signing & Capabilities → enable Push Notifications + Background Modes / Remote notifications |
| Cleartext blocked on Android | Either go HTTPS (recommended) or set `cleartext: true` in `capacitor.config.ts` |

## Custom splash & icon

After `npx cap add`, you can use the official asset generator:

```bash
yarn add -D @capacitor/assets
npx capacitor-assets generate --iconBackgroundColor "#3E5245"
```

Replace `resources/icon.png` (1024×1024) and `resources/splash.png`
(2732×2732) before running this.

---

Status: ✅ Capacitor 7 installed and config wired. Run
`bash scripts/capacitor-setup.sh` on a developer machine to materialise the
native projects.
