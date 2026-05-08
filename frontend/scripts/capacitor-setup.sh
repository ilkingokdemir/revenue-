#!/usr/bin/env bash
#
# Capacitor — one-shot setup for iOS + Android native wrappers.
#
# Run this on your local development machine (Mac for iOS, any OS for Android).
# Requires:
#   - Node 22+ (Capacitor 7 minimum)
#   - Yarn / npm
#   - Xcode + Xcode CLI tools (for iOS)
#   - Android Studio + JDK 17 (for Android)
#
# Usage:
#   bash scripts/capacitor-setup.sh              # add platforms + sync
#   bash scripts/capacitor-setup.sh ios          # iOS only
#   bash scripts/capacitor-setup.sh android      # Android only
#   bash scripts/capacitor-setup.sh sync         # rebuild + sync
#   bash scripts/capacitor-setup.sh open ios     # opens Xcode
#   bash scripts/capacitor-setup.sh open android # opens Android Studio

set -euo pipefail
cd "$(dirname "$0")/.."

CMD=${1:-all}
PLAT=${2:-}

build_web() {
  echo "==> Building web bundle (yarn build)"
  yarn build
}

case "$CMD" in
  all)
    build_web
    [ ! -d ios ] && npx cap add ios || echo "iOS platform already present"
    [ ! -d android ] && npx cap add android || echo "Android platform already present"
    npx cap sync
    echo
    echo "Done. Next steps:"
    echo "  npx cap open ios       # → Xcode"
    echo "  npx cap open android   # → Android Studio"
    ;;
  ios)
    build_web
    [ ! -d ios ] && npx cap add ios || echo "iOS platform already present"
    npx cap sync ios
    npx cap open ios
    ;;
  android)
    build_web
    [ ! -d android ] && npx cap add android || echo "Android platform already present"
    npx cap sync android
    npx cap open android
    ;;
  sync)
    build_web
    npx cap sync
    ;;
  open)
    [ -z "$PLAT" ] && { echo "open requires platform: ios | android"; exit 1; }
    npx cap open "$PLAT"
    ;;
  *)
    echo "Usage: $0 [all|ios|android|sync|open <ios|android>]"
    exit 1
    ;;
esac
