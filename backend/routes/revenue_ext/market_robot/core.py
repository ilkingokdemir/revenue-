"""
Market Robot — Booking.com pazar arzı tarar ve otel fiyatlarını otomatik ayarlar.
Faz-2: 9k satırlık fabrika 10 bölüm modülüne ayrıldı. Bölümler arası paylaşım
S (SimpleNamespace) üzerinden; her modül register(router, db, require_roles, resend, S) sunar.

BÖLÜMLER:
  sec_scan_engine      — scrape çekirdeği + config + neighborhood + geo tarama
  sec_geo_competitive  — geo arz/config + rekabetçi fiyatlama + haftalık özet
  sec_supply_dashboards— _do_scan + arz verisi + doluluk/talep panoları + aksiyon akışı
  sec_performance      — performans raporu (gider/gelir forecast builder'ları)
  sec_competitors      — rakip CRUD + keşif + auto-heal + geocode
  sec_fleet_ai         — fleet reset/geo doğrulama/AI sınıflandırma + vision scrape
  sec_vision_gap       — vision zenginleştirme + rakip tarama + pulse + gap kapama + AI fleet optimize
  sec_auto_helpers     — otomatik fiyat/etkinlik/rakip/otel tarama yardımcıları
  sec_scanner_metrics  — tarayıcı kontrol + oda sayısı + YoY + manuel metrikler
  sec_pulse_loop       — sıralama analizi + market pulse + auto_scan_loop
"""
from types import SimpleNamespace

from fastapi import APIRouter

from . import (sec_scan_engine, sec_geo_competitive, sec_supply_dashboards,
               sec_performance, sec_competitors, sec_fleet_ai, sec_vision_gap,
               sec_auto_helpers, sec_scanner_metrics, sec_pulse_loop)

SECTIONS = (sec_scan_engine, sec_geo_competitive, sec_supply_dashboards,
            sec_performance, sec_competitors, sec_fleet_ai, sec_vision_gap,
            sec_auto_helpers, sec_scanner_metrics, sec_pulse_loop)


def create_market_robot_router(db, require_roles, resend=None):
    router = APIRouter()
    S = SimpleNamespace()
    for section in SECTIONS:
        section.register(router, db, require_roles, resend, S)
    return router
