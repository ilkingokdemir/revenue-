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
npx eas build --platform android   # veya ios (Expo hesabı gerekir)
```

## Notlar
- Tüm veriler mevcut `/api/*` uçlarından gelir; mobil için ayrı backend gerekmez.
- Token AsyncStorage'da saklanır; çıkışta silinir.
