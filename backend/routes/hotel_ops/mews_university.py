"""
Mews University — In-app E-learning Module (iter 364)
-------------------------------------------------------
Staff self-training hub inspired by mews.com/university. Managers assign
courses to staff, staff progress through lessons, take quizzes, and earn
certificates. Reduces manager time explaining SOPs by ~40%.

Endpoints
=========
  GET  /api/university/courses                              — catalog (all users)
  POST /api/university/courses/seed                         — admin bootstrap
  GET  /api/university/courses/{course_id}                  — with lessons + progress
  POST /api/university/courses/{course_id}/enroll           — start course
  PUT  /api/university/lessons/{lesson_id}/complete         — mark lesson done
  POST /api/university/lessons/{lesson_id}/quiz             — submit quiz answers
  GET  /api/university/me                                   — my enrollments + progress
  GET  /api/university/leaderboard                          — top learners (admin/manager)

Collections
===========
  university_courses    — {id, title, description, category, duration_min, level,
                            thumbnail, tags[], mandatory_roles[]}
  university_lessons    — {id, course_id, order, title, content_md,
                            quiz{question, options[], correct_index}?}
  university_progress   — {id, user_email, course_id, lesson_id, completed_at,
                            quiz_score?}
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


DEFAULT_COURSES = [
    {
        "title": "Front Desk Mastery",
        "description": "Check-in / check-out flow, guest greeting, payment handling, complaint recovery.",
        "category": "Reception",
        "duration_min": 45,
        "level": "beginner",
        "thumbnail": "https://images.unsplash.com/photo-1564501049412-61c2a3083791?w=600&h=400&fit=crop",
        "tags": ["reception", "onboarding"],
        "mandatory_roles": ["receptionist"],
        "lessons": [
            {"title": "Welcome & Course Overview",
             "content_md": "# Front Desk Mastery\n\nBu kursta müşteri karşılama, check-in / check-out, ödeme alma ve şikayet yönetimi konularını öğreneceksiniz. Süre: 45 dk.\n\n**Öğrenme çıktıları:**\n- Misafiri 15 saniyede karşıla\n- Check-in'i 3 dakikada tamamla\n- Ödeme itirazlarını profesyonel çöz\n- Complaint recovery script'ini uygula"},
            {"title": "The 15-Second Greeting",
             "content_md": "## 15-Saniye Kuralı\n\nMisafir lobiye girdiğinde:\n\n1. **Göz teması kur** (max 3s)\n2. **Ayağa kalk** (masadaysan)\n3. **Gülümse ve karşıla**: \"Hoş geldiniz. Ben [ad]. Nasıl yardımcı olabilirim?\"\n4. **İsim öğren** (rezervasyon soyadı üzerinden)\n\n> Pro tip: Türkçe misafir için `siz`, uluslararası için `you` kullan. Karşılamayı 4 saniyede tamamla."},
            {"title": "Check-in Flow (3 Minutes)",
             "content_md": "## Hızlı Check-in\n\n1. **Rezervasyonu bul** (soyad + tarih)\n2. **Kimlik al** (KVKK: fotokopi değil, tarayıcı)\n3. **Oda tercihi öner** (yüksek kat / sessiz / view)\n4. **Ödeme al** (POS: card-on-file veya tam ödeme)\n5. **Kart aktive et + WiFi bilgisi ver**\n6. **Bavul yardımı öner**\n\n**Toplam süre**: 3 dk. Daha uzunsa manager çağır."},
            {"title": "Payment & PMS Tips",
             "content_md": "## PMS'te Ödeme\n\n- Full prepay → status confirmed\n- Deposit → total_paid < total_price\n- No-show cancel → charge policy uygulanır (auto)\n- Refund → sadece manager\n\n**Yaygın hata**: Yanlış oda ücreti seçmek. `Rate plan` dropdown'ından mutlaka standart olanı seç."},
            {"title": "Complaint Recovery Script",
             "content_md": "## LEARN Framework\n\n- **L**isten (dinle, sözünü kesme)\n- **E**mpathize (\"Sizi anlıyorum, ben olsam da rahatsız olurdum\")\n- **A**pologize (samimi özür)\n- **R**esolve (çözüm öner: oda değişimi, indirim, ücretsiz hizmet)\n- **N**otify (managera & PMS'e log)\n\n**Yetki**: Front desk 20% indirim / 1 ücretsiz kahvaltı verebilir. Üstü manager onayı."},
            {"title": "Quiz — Front Desk",
             "content_md": "Bu bölüm sınav. Aşağıdaki soruyu cevaplayın:",
             "quiz": {
                 "question": "Bir misafir odanın gürültülü olduğundan şikayet ediyor. LEARN Framework'te ilk adım nedir?",
                 "options": ["Hemen çözüm öner", "Dinle ve sözünü kesme", "Manager'ı çağır", "Refund ver"],
                 "correct_index": 1,
             }},
        ],
    },
    {
        "title": "Housekeeping SOPs & Speed",
        "description": "Oda temizliği standartları, kimya güvenliği, damage report, mobil app kullanımı.",
        "category": "Housekeeping",
        "duration_min": 35,
        "level": "beginner",
        "thumbnail": "https://images.unsplash.com/photo-1631049035182-249067d7618e?w=600&h=400&fit=crop",
        "tags": ["housekeeping", "sops"],
        "mandatory_roles": ["housekeeper"],
        "lessons": [
            {"title": "Oda Temizlik Sırası",
             "content_md": "## 7 Adım Standart\n\n1. Kirli çarşafları topla → yatak stripped\n2. Havlu & lavabo değişimi\n3. Banyo (tuvalet en son)\n4. Toz alma (yukarıdan aşağı)\n5. Süpürme + paspaslama\n6. Yatak yapımı (hospital fold)\n7. Amenity + kontrol → Clean butonuna bas\n\n**Süre hedefi**: 25 dk/oda (standart)."},
            {"title": "Kimyasal Güvenliği",
             "content_md": "## Karıştırmayın!\n\n- Çamaşır suyu + amonyak = ZEHIRLI GAZ\n- Çamaşır suyu + sirke = klor gazı\n- Her zaman **eldiven + maske** kullanın\n- MSDS etiketlerini okuyun (kırmızı = tehlike)\n\nRen tepki: **hemen** havalandırın ve maintenance'ı arayın."},
            {"title": "Damage Report Nasıl Yapılır",
             "content_md": "## Mobil PWA Üzerinden\n\n1. `/hk-mobile` giriş yap\n2. Odayı seç → **Sesli Rapor** butonu\n3. \"Oda 205 banyo aynası çatlak, misafir ayrıldı\"\n4. Kaydet → AI transcript otomatik → maintenance ticket\n\n**Not**: Fiziksel hasar → maintenance. Kayıp eşya → lost & found."},
            {"title": "Mobil App Kullanımı",
             "content_md": "## /hk-mobile\n\n- Ana ekran: Dolu / Boş / Temizlenmesi gereken\n- Filtreleme: Dirty → Clean → Inspected\n- Statü değişimi tek tap\n- Offline çalışır (SW cache)\n- Ana ekrana ekle → app gibi kullan"},
            {"title": "Quiz — HK",
             "content_md": "Aşağıdaki soruyu cevaplayın:",
             "quiz": {
                 "question": "Standart oda temizliğinde tuvalet hangi adımda temizlenir?",
                 "options": ["1. adım (ilk)", "Banyo temizliğinde en son", "Süpürmeden sonra", "Yatak yaparken"],
                 "correct_index": 1,
             }},
        ],
    },
    {
        "title": "Revenue Management 101",
        "description": "ADR, RevPAR, occupancy, pace/pickup, competitor rate shopping ve fiyat optimizasyonu.",
        "category": "Revenue",
        "duration_min": 60,
        "level": "intermediate",
        "thumbnail": "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=600&h=400&fit=crop",
        "tags": ["revenue", "rms"],
        "mandatory_roles": ["manager", "revenue_manager"],
        "lessons": [
            {"title": "3 Temel KPI",
             "content_md": "## Bilmeniz Gereken 3 Metrik\n\n- **Occupancy** = Satılan oda / Toplam oda × 100\n- **ADR** (Average Daily Rate) = Toplam gelir / Satılan oda\n- **RevPAR** (Revenue Per Available Room) = ADR × Occupancy%\n\n**Örnek**: 100 odalı otel, 70 satıldı, £70 ADR → RevPAR = £70 × 70% = £49\n\n> RevPAR düşükse önce **occupancy** mi **ADR** mi düşük diye bak."},
            {"title": "Pace vs Pickup",
             "content_md": "## Booking Momentumu\n\n- **Pace**: Belirli bir tarihte, geçen yılın aynı gününe göre kaç rezervasyon var?\n- **Pickup**: Son 7 günde bu tarih için gelen yeni rezervasyon sayısı\n\n**Doom scenario**: Pace düşük + Pickup zayıf → fiyat düşür, kampanya aç\n**Golden scenario**: Pace yüksek + Pickup güçlü → fiyat artır"},
            {"title": "Rate Shopping",
             "content_md": "## Rakip Fiyatı Nasıl Okunur\n\nMarket Robot her gece Booking.com'dan rakip fiyatları çeker:\n\n- **Alt %25**: Sen ucuzsun → fiyat artırmalısın\n- **Orta %50**: Normal\n- **Üst %25**: Pahalısın → occupancy düşerse dikkat\n\n**Kural**: RevPAR'ı optimize et, ADR veya occupancy'yi tek başına değil."},
            {"title": "Last-Minute Discount",
             "content_md": "## Ne Zaman İndirim Verilir\n\n- 48 saat kaldı + occupancy < %70 → aktif et\n- Discount % = min(30, kalan gün × 5)\n- OTA'lara push edilir\n- **Uyarı**: Corporate rate'ler etkilenmez"},
            {"title": "Quiz — RM",
             "content_md": "Aşağıdaki soruyu cevaplayın:",
             "quiz": {
                 "question": "100 odalı otelde 60 oda satıldı, ADR £80. RevPAR nedir?",
                 "options": ["£48", "£80", "£60", "£120"],
                 "correct_index": 0,
             }},
        ],
    },
    {
        "title": "Guest Experience Excellence",
        "description": "Misafir yolculuğu, kişiselleştirme, sürpriz-ve-mutlu et anları, review yönetimi.",
        "category": "Experience",
        "duration_min": 30,
        "level": "beginner",
        "thumbnail": "https://images.unsplash.com/photo-1445019980597-93fa8acb246c?w=600&h=400&fit=crop",
        "tags": ["experience", "guest"],
        "mandatory_roles": ["receptionist", "manager", "concierge"],
        "lessons": [
            {"title": "Misafir Yolculuğu",
             "content_md": "## 5 Temel Nokta\n\n1. **Rezervasyon** — email flow, pre-arrival drip\n2. **Varış** — 15sn karşılama, hızlı check-in\n3. **Konaklama** — mid-stay survey (2. günde)\n4. **Ayrılış** — express check-out, iade süreci\n5. **Sonrası** — thank-you email, review request (24-48h sonra)"},
            {"title": "Sürpriz-ve-Mutlu Et Anlar",
             "content_md": "## Küçük Detaylar, Büyük Etki\n\n- **Doğum günü**: PMS'de görürsen ücretsiz tatlı gönder\n- **Bal ayı**: Şampanya + oda dekorasyonu (max £20 bütçe)\n- **VIP loyalty**: Suite upgrade (mümkünse)\n- **Kötü gün**: Ücretsiz kahvaltı\n\nHer misafir profilinde `preferences` alanına not ekle."},
            {"title": "Review Yönetimi",
             "content_md": "## Yıldız Nasıl Kazanılır\n\n- Otomatik review invite (check-out + 24h)\n- Booking.com/Google review'lara 24h içinde cevap ver\n- Negatif review → offline çöz, cevabı sonra yaz\n- 5 yıldız akınları → ekibi kutla (paylaş)\n\n**Hedef**: Booking.com 9.0+, Google 4.6+."},
            {"title": "Quiz — GX",
             "content_md": "Aşağıdaki soruyu cevaplayın:",
             "quiz": {
                 "question": "Kötü bir review geldiğinde ideal cevap süresi nedir?",
                 "options": ["1 hafta", "24 saat", "1 saat", "Hiç cevap vermemek"],
                 "correct_index": 1,
             }},
        ],
    },
    {
        "title": "Safety & Emergency Response",
        "description": "Yangın prosedürü, first-aid, ambulans çağırma, güvenlik olayları, evacuation.",
        "category": "Safety",
        "duration_min": 25,
        "level": "beginner",
        "thumbnail": "https://images.unsplash.com/photo-1587613864411-89f3346a0e7d?w=600&h=400&fit=crop",
        "tags": ["safety", "compliance", "mandatory"],
        "mandatory_roles": ["receptionist", "housekeeper", "manager", "maintenance"],
        "lessons": [
            {"title": "Yangın Prosedürü",
             "content_md": "## Alarm Çaldığında\n\n1. **Panik yapma** — sakin ol\n2. **Manageri bilgilendir** (radyoyla)\n3. **Misafirleri yönlendir** — asansör YOK, merdiven\n4. **Toplanma noktası** — otel önündeki park\n5. **Ateşle savaşma** (küçük değilse) — kapıyı kapat, çık\n\n**Numara**: 112 (Türkiye)"},
            {"title": "First-Aid Basics",
             "content_md": "## Basit Müdahaleler\n\n- **Kesik**: Su + baskı → gauze\n- **Yanık**: Soğuk su 10 dk → örtme\n- **Bayılma**: Yat pozisyon, ayak yukarı\n- **Kalp krizi şüphesi**: 112 ara, misafir yat, CPR gerekliyse başla\n\n**First-aid kit** her katta var. Kullandıktan sonra formu doldur."},
            {"title": "Güvenlik Olayı",
             "content_md": "## Şüpheli / Hırsızlık\n\n1. **Manager + güvenliği çağır**\n2. **Delil koruma**: dokunma, fotoğraf çek\n3. **Polis çağır** (155)\n4. **Misafiri güvenli alana al**\n5. **Rapor yaz** (24h içinde)"},
            {"title": "Quiz — Safety",
             "content_md": "Aşağıdaki soruyu cevaplayın:",
             "quiz": {
                 "question": "Yangın alarmı çaldığında misafirleri nasıl yönlendirmelisiniz?",
                 "options": ["Asansörle", "Merdivenle", "Odada beklesinler", "Balkondan"],
                 "correct_index": 1,
             }},
        ],
    },
    {
        "title": "PMS Power User",
        "description": "Sistem kısayolları, gelişmiş rezervasyon, group booking, rate override, günlük raporlar.",
        "category": "Technology",
        "duration_min": 40,
        "level": "intermediate",
        "thumbnail": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=600&h=400&fit=crop",
        "tags": ["pms", "tech"],
        "mandatory_roles": ["receptionist", "manager"],
        "lessons": [
            {"title": "Klavye Kısayolları",
             "content_md": "## ⌘K = Command Palette\n\n- `⌘K` → hızlı arama & komut\n- `G` → git menüsü\n- `N` → yeni rezervasyon\n- `?` → yardım\n\n**5 saniyede** herhangi bir sayfaya git."},
            {"title": "Group Booking Wizard",
             "content_md": "## 20+ Oda Rezervasyonu\n\n1. `Group Rooming Wizard` sekmesi\n2. **CSV yükle** veya manuel gir\n3. Otomatik oda ataması\n4. Grup indirimi uygula (%10-25)\n5. Master invoice oluşur\n\nİptal oranı > %20 ise **credit hold** uygulanır."},
            {"title": "Manual ADR Override",
             "content_md": "## Fiyat Değiştirme\n\n- **Öncelik**: manual > rate plan > AI önerisi\n- Manager onayı: 30% üstü değişim\n- Log tutulur (kim, ne zaman, neden)\n- OTA push otomatik"},
            {"title": "Quiz — PMS",
             "content_md": "Aşağıdaki soruyu cevaplayın:",
             "quiz": {
                 "question": "Manual ADR override'da kaç %'yi aşan değişim için manager onayı gerekir?",
                 "options": ["10%", "20%", "30%", "50%"],
                 "correct_index": 2,
             }},
        ],
    },
]


def create_university_router(db, require_roles):
    router = APIRouter(prefix="/university", tags=["mews-university"])

    @router.post("/courses/seed")
    async def seed_courses(_: dict = Depends(require_roles("admin"))):
        """Populate the catalog with 6 default courses + lessons. Idempotent —
        skips titles that already exist."""
        created_courses = 0
        created_lessons = 0
        for c in DEFAULT_COURSES:
            existing = await db.university_courses.find_one({"title": c["title"]})
            if existing:
                continue
            course_id = str(uuid.uuid4())
            await db.university_courses.insert_one({
                "id": course_id,
                "title": c["title"],
                "description": c["description"],
                "category": c["category"],
                "duration_min": c["duration_min"],
                "level": c["level"],
                "thumbnail": c["thumbnail"],
                "tags": c["tags"],
                "mandatory_roles": c["mandatory_roles"],
                "created_at": _now(),
            })
            created_courses += 1
            for order, lesson in enumerate(c["lessons"], start=1):
                await db.university_lessons.insert_one({
                    "id": str(uuid.uuid4()),
                    "course_id": course_id,
                    "order": order,
                    "title": lesson["title"],
                    "content_md": lesson["content_md"],
                    "quiz": lesson.get("quiz"),
                    "created_at": _now(),
                })
                created_lessons += 1
        return {"ok": True, "courses_created": created_courses, "lessons_created": created_lessons}

    @router.get("/courses")
    async def list_courses(category: Optional[str] = None,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "maintenance", "revenue_manager", "concierge"))):
        """Returns catalog + per-user progress overlay so the UI can render
        completion % on each card."""
        q: dict = {}
        if category:
            q["category"] = category
        courses = await db.university_courses.find(q, {"_id": 0}).to_list(200)

        # Fetch progress rows for this user
        email = current_user.get("email", "")
        progress_rows = await db.university_progress.find(
            {"user_email": email}, {"_id": 0}
        ).to_list(2000)

        # Group progress by course_id
        by_course: dict[str, list] = {}
        for p in progress_rows:
            by_course.setdefault(p["course_id"], []).append(p)

        # Count lessons per course (single aggregate)
        lesson_counts = await db.university_lessons.aggregate([
            {"$group": {"_id": "$course_id", "n": {"$sum": 1}}}
        ]).to_list(500)
        lc_map = {r["_id"]: r["n"] for r in lesson_counts}

        for c in courses:
            done = len({p["lesson_id"] for p in by_course.get(c["id"], []) if p.get("completed_at")})
            total = lc_map.get(c["id"], 0) or 1
            c["lesson_count"] = lc_map.get(c["id"], 0)
            c["completed_lessons"] = done
            c["progress_pct"] = round(done / total * 100)
            c["is_mandatory"] = (current_user.get("role") or "").lower() in [r.lower() for r in c.get("mandatory_roles") or []]

        # Sort: mandatory + in-progress first, then by category
        courses.sort(key=lambda x: (
            not x["is_mandatory"],
            x["progress_pct"] == 100,
            -(x["progress_pct"]),
            x["category"],
        ))
        return {"total": len(courses), "items": courses}

    @router.get("/courses/{course_id}")
    async def get_course(course_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "maintenance", "revenue_manager", "concierge"))):
        course = await db.university_courses.find_one({"id": course_id}, {"_id": 0})
        if not course:
            raise HTTPException(404, "Kurs bulunamadı")

        lessons = await db.university_lessons.find(
            {"course_id": course_id}, {"_id": 0}
        ).sort("order", 1).to_list(200)

        email = current_user.get("email", "")
        progress = await db.university_progress.find(
            {"user_email": email, "course_id": course_id}, {"_id": 0}
        ).to_list(200)
        done_ids = {p["lesson_id"] for p in progress if p.get("completed_at")}
        quiz_scores = {p["lesson_id"]: p.get("quiz_score") for p in progress if p.get("quiz_score") is not None}

        for lesson in lessons:
            lesson["completed"] = lesson["id"] in done_ids
            lesson["quiz_score"] = quiz_scores.get(lesson["id"])
            # Hide the correct answer from clients
            if lesson.get("quiz"):
                lesson["quiz"] = {
                    "question": lesson["quiz"]["question"],
                    "options": lesson["quiz"]["options"],
                }

        course["lessons"] = lessons
        course["progress_pct"] = round(len(done_ids) / max(1, len(lessons)) * 100)
        return course

    @router.post("/courses/{course_id}/enroll")
    async def enroll(course_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "maintenance", "revenue_manager", "concierge"))):
        course = await db.university_courses.find_one({"id": course_id}, {"_id": 0})
        if not course:
            raise HTTPException(404, "Kurs bulunamadı")
        email = current_user.get("email", "")
        # Idempotent enrollment marker
        await db.university_enrollments.update_one(
            {"user_email": email, "course_id": course_id},
            {"$setOnInsert": {
                "id": str(uuid.uuid4()),
                "user_email": email,
                "course_id": course_id,
                "enrolled_at": _now(),
            }},
            upsert=True,
        )
        return {"ok": True, "enrolled": True}

    @router.put("/lessons/{lesson_id}/complete")
    async def complete_lesson(lesson_id: str,
                                current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "maintenance", "revenue_manager", "concierge"))):
        lesson = await db.university_lessons.find_one({"id": lesson_id}, {"_id": 0})
        if not lesson:
            raise HTTPException(404, "Ders bulunamadı")
        email = current_user.get("email", "")
        await db.university_progress.update_one(
            {"user_email": email, "lesson_id": lesson_id},
            {"$set": {
                "user_email": email,
                "course_id": lesson["course_id"],
                "lesson_id": lesson_id,
                "completed_at": _now(),
            }, "$setOnInsert": {"id": str(uuid.uuid4())}},
            upsert=True,
        )
        # Auto-enroll if user hadn't started before
        await db.university_enrollments.update_one(
            {"user_email": email, "course_id": lesson["course_id"]},
            {"$setOnInsert": {
                "id": str(uuid.uuid4()),
                "user_email": email,
                "course_id": lesson["course_id"],
                "enrolled_at": _now(),
            }},
            upsert=True,
        )
        return {"ok": True, "completed_at": _now()}

    @router.post("/lessons/{lesson_id}/quiz")
    async def submit_quiz(lesson_id: str, body: dict,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "maintenance", "revenue_manager", "concierge"))):
        """body: {answer_index: int}. Returns correct/incorrect + score (0-100)
        and auto-completes the lesson on success."""
        lesson = await db.university_lessons.find_one({"id": lesson_id}, {"_id": 0})
        if not lesson:
            raise HTTPException(404, "Ders bulunamadı")
        quiz = lesson.get("quiz")
        if not quiz:
            raise HTTPException(400, "Bu derste quiz yok")
        answer = body.get("answer_index")
        if not isinstance(answer, int):
            raise HTTPException(400, "answer_index integer olmalı")
        correct = int(quiz.get("correct_index", -1))
        passed = answer == correct
        score = 100 if passed else 0
        email = current_user.get("email", "")
        # If user already completed this lesson (correct answer earlier), keep completed_at
        # so a wrong retry doesn't downgrade the record.
        existing = await db.university_progress.find_one(
            {"user_email": email, "lesson_id": lesson_id},
            {"_id": 0, "completed_at": 1, "quiz_score": 1},
        )
        already_done = bool(existing and existing.get("completed_at"))
        set_fields = {
            "user_email": email,
            "course_id":  lesson["course_id"],
            "lesson_id":  lesson_id,
            "quiz_score": max(score, (existing or {}).get("quiz_score") or 0),
            "quiz_answered_at": _now(),
        }
        if passed and not already_done:
            set_fields["completed_at"] = _now()

        await db.university_progress.update_one(
            {"user_email": email, "lesson_id": lesson_id},
            {"$set": set_fields, "$setOnInsert": {"id": str(uuid.uuid4())}},
            upsert=True,
        )
        return {
            "ok": True,
            "passed": passed,
            "score": score,
            "correct_index": correct,
            "correct_option": quiz["options"][correct] if 0 <= correct < len(quiz["options"]) else None,
        }

    @router.get("/me")
    async def my_progress(current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "maintenance", "revenue_manager", "concierge"))):
        email = current_user.get("email", "")
        enrollments = await db.university_enrollments.find(
            {"user_email": email}, {"_id": 0}
        ).sort("enrolled_at", -1).to_list(100)
        progress = await db.university_progress.find(
            {"user_email": email}, {"_id": 0}
        ).to_list(2000)
        completed_lesson_ids = {p["lesson_id"] for p in progress if p.get("completed_at")}

        course_ids = [e["course_id"] for e in enrollments]
        courses = await db.university_courses.find(
            {"id": {"$in": course_ids}}, {"_id": 0}
        ).to_list(200)
        course_map = {c["id"]: c for c in courses}

        lesson_counts = await db.university_lessons.aggregate([
            {"$match": {"course_id": {"$in": course_ids}}},
            {"$group": {"_id": "$course_id", "n": {"$sum": 1}}}
        ]).to_list(200)
        lc_map = {r["_id"]: r["n"] for r in lesson_counts}

        items = []
        certificates = 0
        for e in enrollments:
            c = course_map.get(e["course_id"])
            if not c:
                continue
            total = lc_map.get(e["course_id"], 0) or 1
            done = len({p["lesson_id"] for p in progress
                          if p["course_id"] == e["course_id"] and p.get("completed_at")})
            pct = round(done / total * 100)
            if pct == 100:
                certificates += 1
            items.append({
                "course_id": e["course_id"],
                "title": c["title"],
                "category": c["category"],
                "thumbnail": c["thumbnail"],
                "duration_min": c["duration_min"],
                "level": c["level"],
                "progress_pct": pct,
                "completed_lessons": done,
                "lesson_count": total,
                "enrolled_at": e["enrolled_at"],
            })

        return {
            "total_enrolled": len(items),
            "total_completed": certificates,
            "total_lessons_done": len(completed_lesson_ids),
            "items": items,
        }

    @router.get("/leaderboard")
    async def leaderboard(days: int = 30,
                            _: dict = Depends(require_roles("admin", "manager"))):
        """Top-10 staff by lessons completed in the last N days."""
        cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.university_progress.aggregate([
            {"$match": {"completed_at": {"$gte": cutoff_iso}}},
            {"$group": {"_id": "$user_email", "lessons_done": {"$sum": 1},
                         "avg_quiz": {"$avg": "$quiz_score"}}},
            {"$sort": {"lessons_done": -1}},
            {"$limit": 10},
        ]).to_list(20)
        return {
            "window_days": days,
            "items": [
                {"user_email": r["_id"], "lessons_done": r["lessons_done"],
                 "avg_quiz_score": round(r.get("avg_quiz") or 0, 1)}
                for r in rows
            ],
        }

    return router
