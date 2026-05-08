"""Regression tests for Booking.com scraper (2026-04 rewrite).

Covers the exact bug the user reported: scraper missing prices on the specific
dated detail URL for 'Franziskaner by Centra' in Zurich. The searchresults
endpoint path must keep returning a valid price + hotel_id so Market Robot's
competitive pricing rules stay honest.

NOTE: These tests hit the live booking.com site. Heavy (30-60s per test).
Marked with `pytestmark = pytest.mark.integration` so unit-only runs can skip.
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/pw-browsers")

from utils.booking_scraper import (  # noqa: E402
    build_dated_url,
    close_browser,
    resolve_hotel_id,
    scrape_booking_url,
    validate_booking_url,
)

FRANZISKANER_URL = "https://www.booking.com/hotel/ch/franziskaner-by-centra.en-gb.html"
FRANZISKANER_EXPECTED_ID = "14990420"

pytestmark = pytest.mark.integration


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if asyncio.get_event_loop().is_running() is False \
        else asyncio.new_event_loop().run_until_complete(coro)


def test_resolve_hotel_id_franziskaner():
    async def inner():
        hid = await resolve_hotel_id(FRANZISKANER_URL, timeout_ms=35000, force_refresh=True)
        assert hid == FRANZISKANER_EXPECTED_ID, f"expected {FRANZISKANER_EXPECTED_ID}, got {hid}"
    asyncio.run(inner())


def test_validate_booking_url_franziskaner():
    async def inner():
        v = await validate_booking_url(FRANZISKANER_URL, currency="CHF")
        assert v["ok"] is True, f"expected ok=True, got {v}"
        assert v["hotel_id"] == FRANZISKANER_EXPECTED_ID
        assert "Franziskaner" in (v["hotel_name"] or "")
        assert v["sample_price"] and v["sample_price"] > 0, f"no price: {v}"
        assert v["currency"] == "CHF"
    asyncio.run(inner())


def test_validate_booking_url_invalid():
    async def inner():
        v = await validate_booking_url(
            "https://www.booking.com/hotel/ch/not-a-real-hotel-xyz-999.html",
            currency="CHF",
        )
        assert v["ok"] is False
        assert v["hotel_id"] is None
        assert v["error"]
    asyncio.run(inner())


def test_validate_booking_url_non_booking():
    async def inner():
        v = await validate_booking_url("https://www.example.com/hotel", currency="CHF")
        assert v["ok"] is False
        assert v["error"] == "not_a_booking_url"
    asyncio.run(inner())


def test_scrape_dated_url_returns_price():
    async def inner():
        url = build_dated_url(FRANZISKANER_URL, "2026-05-15", "2026-05-16", "CHF")
        r = await scrape_booking_url(url)
        assert r["scraped"] is True, f"scrape failed: {r}"
        assert r["lowest_price"] and r["lowest_price"] > 50, f"unrealistic price: {r}"
        assert r["hotel_id"] == FRANZISKANER_EXPECTED_ID
        await close_browser()
    asyncio.run(inner())
