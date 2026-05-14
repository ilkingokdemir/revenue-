"""
Brand Voice Studio — central tone-of-voice service.

Each property defines its brand voice profile:
  - tone: formal, playful, luxury, friendly, professional (or custom)
  - personality_traits[]: e.g. ["warm","witty","elegant"]
  - dos: writing rules to follow
  - donts: writing rules to avoid
  - sample_sentences: 1-3 example sentences in the desired voice
  - sign_off: closing phrase
  - language: tr / en (default tr)

The `/generate` endpoint takes a `purpose` + `context` and returns text in
that voice. Purposes are pre-configured templates:
  - email_confirmation, email_pre_arrival, email_post_stay, email_win_back
  - review_response_positive, review_response_negative
  - social_caption, video_prompt, web_concierge_reply
  - guest_apology, voucher_offer

Endpoints
---------
  GET  /api/brand-voice/profile/{property_id}     — get or auto-seed default profile
  POST /api/brand-voice/profile/{property_id}     — upsert profile
  GET  /api/brand-voice/purposes                  — list available purposes
  POST /api/brand-voice/generate                  — body: {property_id, purpose, context, language?}
  POST /api/brand-voice/preview                   — body: {profile (inline), purpose, context}
                                                    — generate WITHOUT saving profile (for live editing)
  GET  /api/brand-voice/history/{property_id}     — last N generations
"""
from datetime import datetime, timezone
import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


PURPOSES = {
    "email_confirmation": {
        "label": "Rezervasyon Onayı E-postası",
        "system_addition": ("Misafire rezervasyonun onaylandığını teyit et. "
                            "Otelde göreceği 1-2 detaya değin, gelmeden önce "
                            "hatırlanması gerekenleri kısa belirt."),
        "max_words": 120,
    },
    "email_pre_arrival": {
        "label": "Geliş Öncesi E-postası",
        "system_addition": ("Misafire 3 gün kala gönderiliyor. Heyecanı artır, "
                            "varış lojistiği (saat, ulaşım, parkur) öner, "
                            "özel istek var mı sor."),
        "max_words": 140,
    },
    "email_post_stay": {
        "label": "Konaklama Sonrası Teşekkür",
        "system_addition": ("Konaklama bitiminden 1 gün sonra. Teşekkür et, "
                            "yorum bırakması için kısa rica, sadakat programına "
                            "yumuşak yönlendirme."),
        "max_words": 110,
    },
    "email_win_back": {
        "label": "Geri Kazanım E-postası",
        "system_addition": ("90 gündür gelmemiş misafire. Kişisel ton, küçük "
                            "bir teşvik (örn. %10 dönüş indirimi), düşük baskı."),
        "max_words": 120,
    },
    "review_response_positive": {
        "label": "Olumlu Yorum Yanıtı",
        "system_addition": ("Misafire teşekkür et, en az 1 spesifik detayı "
                            "yorumdan tekrar et, tekrar davet et."),
        "max_words": 80,
    },
    "review_response_negative": {
        "label": "Olumsuz Yorum Yanıtı",
        "system_addition": ("Önce özür dile, sorumluluğu üstlen, somut adım "
                            "bahset, telefon veya e-posta ile sorunu çözmek "
                            "için iletişim öner. Savunmacı OLMA."),
        "max_words": 100,
    },
    "social_caption": {
        "label": "Sosyal Medya Caption",
        "system_addition": ("Instagram/TikTok caption. 2-3 cümle, 3-5 hashtag, "
                            "1 emoji (markaya uygunsa). Aksiyon davet et."),
        "max_words": 60,
    },
    "video_prompt": {
        "label": "Sora 2 Video Üretimi için Prompt",
        "system_addition": ("Sora 2'ye verilecek İNGİLİZCE sinematik video prompt'u "
                            "üret. Kamera hareketi, ışık, atmosfer, set detayları "
                            "açık olsun. Marka tonu video kompozisyonuna yansısın."),
        "max_words": 120,
    },
    "web_concierge_reply": {
        "label": "Web Concierge AI Yanıtı",
        "system_addition": ("Misafirin web sitesindeki sorusuna kısa, sıcak "
                            "yanıt. Bilmediğini uydurma, rezervasyona yönlendir."),
        "max_words": 60,
    },
    "guest_apology": {
        "label": "Misafir Özür Mesajı",
        "system_addition": ("Konaklama sırasında yaşanmış spesifik bir soruna "
                            "anlık özür. Empati + somut çözüm önerisi."),
        "max_words": 80,
    },
    "voucher_offer": {
        "label": "Voucher / İndirim Teklifi",
        "system_addition": ("Misafire voucher öner. Değer, kullanım koşulları "
                            "(geçerlilik, koşul), nazik kapanış."),
        "max_words": 90,
    },
}

DEFAULT_PROFILE = {
    "tone": "warm_luxury",
    "personality_traits": ["sıcak", "zarif", "saygılı", "detaycı"],
    "dos": [
        "Misafire 'Sayın {{name}}' ile başla",
        "Kısa, akıcı cümleler kullan",
        "Otelin manzarasına/karakterine 1 atıf yap",
    ],
    "donts": [
        "Klişe ifadelerden kaçın ('aileniz gibi karşılıyoruz' gibi)",
        "Otomatik/robotik dilden kaçın",
        "Aşırı ünlem ve emoji kullanma",
    ],
    "sample_sentences": [
        "Sayın Yılmaz, Antalya'nın güneşli sabahı sizin için hazır — anahtarınızı resepsiyonda bulacaksınız.",
        "Konaklamanız boyunca bahçemizde olgunlaşan limonlardan günlük taze limonata sunuyoruz.",
    ],
    "sign_off": "Saygılarımızla,\nMisafir İlişkileri Ekibi",
    "language": "tr",
}


async def _llm_generate(system_prompt: str, user_prompt: str,
                         session_id: str, max_tokens_hint: int = 400) -> str:
    """Best-effort LLM call. Falls back to a template if LLM unavailable."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        llm_key = os.environ.get("EMERGENT_LLM_KEY")
        if not llm_key:
            return None
        client = LlmChat(
            api_key=llm_key,
            session_id=session_id,
            system_message=system_prompt,
        ).with_model("openai", "gpt-4o-mini")
        return await client.send_message(UserMessage(text=user_prompt))
    except Exception as e:
        logger.warning(f"Brand Voice LLM call failed: {e}")
        return None


def _build_system_prompt(profile: dict, purpose: dict, language: str = "tr") -> str:
    traits = ", ".join(profile.get("personality_traits", []))
    dos = "\n".join([f"  • {d}" for d in profile.get("dos", [])])
    donts = "\n".join([f"  • {d}" for d in profile.get("donts", [])])
    samples = "\n".join([f"  • {s}" for s in profile.get("sample_sentences", [])])
    sign_off = profile.get("sign_off", "")
    tone = profile.get("tone", "warm_professional")
    lang_label = "Türkçe" if language == "tr" else "İngilizce"
    return (
        f"Sen bir otel markası adına {lang_label} yazan kıdemli misafir iletişim "
        f"uzmanısın.\n\n"
        f"MARKA SESİ:\n"
        f"- Genel ton: {tone}\n"
        f"- Kişilik özellikleri: {traits}\n\n"
        f"YAPMAN GEREKEN:\n{dos}\n\n"
        f"YAPMAMAN GEREKEN:\n{donts}\n\n"
        f"ÖRNEK CÜMLELER (ton referansı):\n{samples}\n\n"
        f"AMAÇ: {purpose['label']}\n"
        f"AMAÇ KURALI: {purpose['system_addition']}\n\n"
        f"FORMAT KURALLARI:\n"
        f"  • Maksimum {purpose.get('max_words', 100)} kelime\n"
        f"  • İmzayı '{sign_off}' olarak bitir (gerekiyorsa)\n"
        f"  • Yalnızca metni döndür, açıklama YAZMA"
    )


def create_brand_voice_router(db, require_roles):
    router = APIRouter()

    async def _get_or_seed_profile(property_id: str) -> dict:
        p = await db.brand_voice_profiles.find_one(
            {"property_id": property_id}, {"_id": 0}
        )
        if p:
            return p
        prop = await db.properties.find_one(
            {"id": property_id}, {"_id": 0, "name": 1}
        )
        new = {
            "property_id": property_id,
            "property_name": (prop or {}).get("name", ""),
            **DEFAULT_PROFILE,
            "created_at": _now_iso(),
            "seeded": True,
        }
        await db.brand_voice_profiles.insert_one(new)
        new.pop("_id", None)
        return new

    @router.get("/brand-voice/purposes")
    async def purposes(_: dict = Depends(require_roles("admin", "manager"))):
        return {"items": [{"id": k, **v} for k, v in PURPOSES.items()]}

    @router.get("/brand-voice/profile/{property_id}")
    async def get_profile(property_id: str,
                          _: dict = Depends(require_roles("admin", "manager"))):
        return await _get_or_seed_profile(property_id)

    @router.post("/brand-voice/profile/{property_id}")
    async def upsert_profile(property_id: str, body: dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        allowed = {"tone", "personality_traits", "dos", "donts",
                   "sample_sentences", "sign_off", "language", "property_name"}
        update = {k: v for k, v in body.items() if k in allowed}
        if not update:
            raise HTTPException(400, "Nothing to update")
        update["updated_at"] = _now_iso()
        update["updated_by"] = current_user.get("name", "")
        await db.brand_voice_profiles.update_one(
            {"property_id": property_id},
            {"$set": {**update, "property_id": property_id}},
            upsert=True,
        )
        return await _get_or_seed_profile(property_id)

    @router.post("/brand-voice/generate")
    async def generate(body: dict,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        property_id = body.get("property_id") or ""
        purpose_key = body.get("purpose") or ""
        context = (body.get("context") or "").strip()
        language = body.get("language") or "tr"
        if not property_id or purpose_key not in PURPOSES:
            raise HTTPException(400, "property_id and valid purpose required")
        profile = await _get_or_seed_profile(property_id)
        sys_prompt = _build_system_prompt(profile, PURPOSES[purpose_key], language)
        user_prompt = (f"BAĞLAM:\n{context}\n\n"
                       f"Yukarıdaki bağlam ve marka sesi kurallarına göre metni üret.")
        gen_id = str(uuid.uuid4())
        text = await _llm_generate(sys_prompt, user_prompt, session_id=gen_id)
        if not text:
            # Template fallback so the endpoint never breaks
            text = (f"[{PURPOSES[purpose_key]['label']}]\n"
                    f"{context[:200]}\n\n{profile.get('sign_off','')}")
        record = {
            "id": gen_id,
            "property_id": property_id,
            "purpose": purpose_key,
            "purpose_label": PURPOSES[purpose_key]["label"],
            "context_input": context[:1000],
            "output": text,
            "language": language,
            "profile_tone": profile.get("tone"),
            "generated_at": _now_iso(),
            "generated_by": current_user.get("name", ""),
        }
        await db.brand_voice_history.insert_one(record)
        record.pop("_id", None)
        return record

    @router.post("/brand-voice/preview")
    async def preview(body: dict,
                      _: dict = Depends(require_roles("admin", "manager"))):
        profile = body.get("profile") or {}
        purpose_key = body.get("purpose") or ""
        context = (body.get("context") or "").strip()
        language = body.get("language") or "tr"
        if purpose_key not in PURPOSES:
            raise HTTPException(400, "valid purpose required")
        # Merge with default for any missing keys
        merged = {**DEFAULT_PROFILE, **profile}
        sys_prompt = _build_system_prompt(merged, PURPOSES[purpose_key], language)
        user_prompt = f"BAĞLAM:\n{context}\n\nMetni üret."
        text = await _llm_generate(sys_prompt, user_prompt,
                                   session_id=f"preview-{uuid.uuid4().hex[:8]}")
        return {"preview": text or "[LLM unavailable — fallback would apply on /generate]"}

    @router.get("/brand-voice/history/{property_id}")
    async def history(property_id: str, purpose: str = "", limit: int = 30,
                      _: dict = Depends(require_roles("admin", "manager"))):
        q: dict = {"property_id": property_id}
        if purpose:
            q["purpose"] = purpose
        items = await db.brand_voice_history.find(q, {"_id": 0}).sort(
            "generated_at", -1
        ).to_list(min(limit, 200))
        return {"items": items, "count": len(items)}

    return router
