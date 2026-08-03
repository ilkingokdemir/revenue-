# MyHotelBox Mobile (Expo React Native)

Otel ekibi için iOS/Android uygulaması — mevcut FastAPI backend'ine bağlanır.

## Özellikler (v1)
- Giriş (JWT, sunucu URL yapılandırılabilir)
- **Bugün**: 24 saat pickup KPI'ları, aylık hedef ilerlemesi, canlı bildirimler
- **Rezervasyonlar**: son 100 rezervasyon (durum + ödeme rozeti)
- **Ödemeler**: Pay-by-Link istatistikleri ve link geçmişi + çıkış

## Çalıştırma (yerel makinenizde)
```bash
cd mobile
yarn install
npx expo start
```
Telefonunuza **Expo Go** uygulamasını indirin ve QR kodu okutun.
Giriş ekranındaki "Sunucu URL" alanı deploy edilmiş backend adresinizi gösterir.

## Derleme (mağaza yayını)
```bash
npm install -g eas-cli
eas login                          # Expo hesabınızla (ücretsiz) giriş yapın
eas build --platform android --profile preview   # APK (internal test)
eas build --platform ios                          # TestFlight (Apple Developer hesabı gerekir)
```
`eas.json` hazır: `preview` profili doğrudan telefona kurulabilir APK üretir.

## Push Bildirimleri
- Girişten sonra uygulama Expo push token'ını backend'e kaydeder (izin isteği çıkar).
- Bildirim türleri "Bugün" ekranındaki **Push Bildirim Tercihleri** bölümünden açılıp kapanır.
- Sunucu tarafı: ödeme alınınca anlık; güçlü satış günü + kanal düşüşü her gün 09:00 UTC'de.

## Notlar
- Tüm veriler mevcut `/api/*` uçlarından gelir; mobil için ayrı backend gerekmez.
- Token AsyncStorage'da saklanır; çıkışta silinir.
