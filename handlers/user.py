# handlers/user.py — mijoz tomoni: /start, telefon tekshirish, info tugmalar
import logging
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError

import db

log = logging.getLogger(__name__)
router = Router()


def phone_keyboard() -> ReplyKeyboardMarkup:
    """/start da ko'rinadigan 'Raqamni yuborish' tugmasi."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Obuna bo'lgandan keyingi mijoz menyusi."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎵 Yangi musiqa va kliplar")],
            [KeyboardButton(text="🛠 Bizning xizmatlar")],
        ],
        resize_keyboard=True,
    )


async def send_content_message(message: Message, setting_key: str, empty_note: str) -> None:
    """music/services bo'limini mijozga ko'rsatadi (matn + media)."""
    try:
        raw = await db.get_setting(setting_key)
    except Exception as e:
        log.exception("Kontent o'qishda xato: %s", e)
        await message.answer("Hozircha ma'lumot yuklanmadi. Keyinroq urinib ko'ring.")
        return
    data = db.parse_content(raw)
    text = (data.get("text") or "").strip()
    file_id = data.get("file_id")
    file_type = data.get("file_type")
    if not text and not file_id:
        await message.answer(empty_note)
        return
    try:
        if file_id and file_type == "photo":
            await message.answer_photo(file_id, caption=text or None)
        elif file_id and file_type == "video":
            await message.answer_video(file_id, caption=text or None)
        elif file_id and file_type == "audio":
            await message.answer_audio(file_id, caption=text or None)
        elif file_id and file_type == "voice":
            await message.answer_voice(file_id, caption=text or None)
        elif file_id and file_type == "document":
            await message.answer_document(file_id, caption=text or None)
        elif text:
            await message.answer(text, disable_web_page_preview=False)
        else:
            await message.answer(empty_note)
    except (TelegramAPIError, Exception) as e:
        log.exception("Kontent yuborishda xato: %s", e)
        # Fayl yaroqsiz bo'lsa hech bo'lmasa matnni yuboramiz
        if text:
            try:
                await message.answer(text)
            except Exception:
                pass


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """/start: telefon raqamni so'raydi."""
    await message.answer(
        "Assalomu alaykum! 👋\n\n"
        "Botdan foydalanish uchun telefon raqamingizni yuboring.\n"
        "Pastdagi «📱 Raqamni yuborish» tugmasini bosing.",
        reply_markup=phone_keyboard(),
    )


@router.message(F.contact)
async def on_contact(message: Message, bot: Bot) -> None:
    """Kontakt yuborilganda: raqamni tekshirib obuna qiladi."""
    contact = message.contact
    # Faqat o'z raqamini yuborsin (begona kontaktni qabul qilmaymiz)
    if contact.user_id and contact.user_id != message.from_user.id:
        await message.answer(
            "Iltimos, faqat o'z raqamingizni yuboring.", reply_markup=phone_keyboard()
        )
        return
    phone = db.normalize_phone(contact.phone_number)
    if not phone:
        await message.answer(
            "Raqam formati noto'g'ri. Qaytadan urinib ko'ring.",
            reply_markup=phone_keyboard(),
        )
        return
    try:
        allowed = await db.is_number_allowed(phone)
    except Exception as e:
        log.exception("Raqam tekshirishda xato: %s", e)
        await message.answer("Bazada xatolik. Keyinroq urinib ko'ring.")
        return
    if not allowed:
        await message.answer(
            "Raqamingiz topilmadi, administratorga murojaat qiling.",
            reply_markup=phone_keyboard(),
        )
        return
    # Raqam ro'yxatda — obunaga yozamiz
    try:
        await db.upsert_subscriber(message.chat.id, phone)
    except Exception as e:
        log.exception("Obuna saqlashda xato: %s", e)
        await message.answer("Xatolik yuz berdi. Keyinroq urinib ko'ring.")
        return
    # Darhol joriy SMS ni yuboramiz
    try:
        sms_text = await db.get_setting(db.KEY_SMS)
    except Exception as e:
        log.exception("SMS o'qishda xato: %s", e)
        sms_text = ""
    await message.answer(
        "✅ Tabriklaymiz! Siz obunaga yozildingiz.\n"
        "Endi har 30 kunda eslatma xabar olasz.",
        reply_markup=main_menu_keyboard(),
    )
    if sms_text.strip():
        try:
            await bot.send_message(message.chat.id, sms_text)
        except TelegramForbiddenError:
            try:
                await db.set_subscriber_active(message.chat.id, False)
            except Exception:
                pass
        except TelegramAPIError as e:
            log.warning("Darhol SMS yuborilmadi: %s", e)


@router.message(F.text == "🎵 Yangi musiqa va kliplar")
async def show_music(message: Message) -> None:
    await send_content_message(
        message, db.KEY_MUSIC, "Hozircha musiqa va kliplar qo'shilmagan."
    )


@router.message(F.text == "🛠 Bizning xizmatlar")
async def show_services(message: Message) -> None:
    await send_content_message(
        message, db.KEY_SERVICES, "Hozircha xizmatlar qo'shilmagan."
    )


@router.message(F.text.startswith("+998") | F.text.startswith("998"))
async def typed_phone_fallback(message: Message) -> None:
    """Qo'lda yozilgan raqam bo'lsa — tugma orqali yuborishni eslatamiz."""
    phone = db.normalize_phone(message.text or "")
    if phone:
        await message.answer(
            "Iltimos, raqamni yozib emas, «📱 Raqamni yuborish» "
            "tugmasi orqali yuboring.",
            reply_markup=phone_keyboard(),
        )
