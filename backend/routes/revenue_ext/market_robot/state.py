"""Market Robot paylaşılan durum — tarama kilitleri ve limitler."""
SCRAPE_RUNNING = False  # legacy global flag (kept for backward compat)
SCRAPE_RUNNING_GEO = False  # legacy global flag
SCRAPE_LOCKS: dict = {}
SCRAPE_LOCKS_GEO: dict = {}
MAX_CONCURRENT_SCANS = 2
AUTO_SCAN_MAX_DAYS = 30  # otomatik taramada gün üst sınırı (manuel taramada 365'e kadar)
