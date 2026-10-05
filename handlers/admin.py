# handlers/admin.py — faqat ADMIN_IDS uchun /admin paneli
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

import db
from config import CONFIG

log = logging.getLogger(__name__)
router = Router()

PAGE_SIZE = 10  # raqamlar ro'yxati sahifa o'lchami


# ---------- FSM holatlari ----------

class AdminStates(StatesGroup):
    waiting_sms_text = State()      # yangi SMS matni kutilmoqda
    waiting_numbers = State()       # yangi raqam(lar) kutilmoqda
    waiting_content = State()       # music/services uchun yangi kontent kutilmoqda
    waiting_delete_number = State()  # o'chiriladigan raqam kutilmoqda


# ---------- Yordamchilar ----------

def is_admin(user_id: int) -> bool:
    return user_id in CONFIG.admin_ids


def admin_menu_kb() -> InlineKeyboardMarkup:
    """/admin asosiy menyusi: 4 ta tugma."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Yuboriladigan SMS xabar", callback_data="adm:sms")],
        [InlineKeyboardButton(text="➕ Yangi raqam kiritish", callback_data="adm:numbers")],
        [InlineKeyboardButton(text="🎵 Yangi musiqa va kliplar", callback_data="adm:music")],
        [InlineKeyboardButton(text="🛠 Bizning xizmatlar", callback_data="adm:services")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="adm:stats")],
        [InlineKeyboardButton(text="📢 Hammasiga hozir yuborish", callback_data="adm:bc")],
    ])


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="adm:back")]
    ])


async def show_admin_menu(target: Message | CallbackQuery) -> None:
    text = (
        "🛠 <b>Admin panel</b>\n\n"
        "Kerakli bo'limni tanlang:"
    )
    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text, reply_markup=admin_menu_kb())
        except Exception:
            await target.message.answer(text, reply_markup=admin_menu_kb())
        await target.answer()
    else:
        await target.answer(text, reply_markup=admin_menu_kb())


async def show_content_section(msg: Message, key: str, title: str, prefix: str) -> None:
    """music/services bo'limi: joriy kontent + Tahrirlash tugmasi."""
    raw = await db.get_setting(key)
    data = db.parse_content(raw)
    text = (data.get("text") or "").strip()
    file_info = "yo'q"
    if data.get("file_id"):
        file_info = f"bor ({data.get('file_type')})"
    preview = (text[:500] + "…" if len(text) > 500 else text) or "(matn kiritilmagan)"
    await msg.answer(
        f"<b>{title}</b>\n\n📄 Matn:\n{preview}\n\n📎 Media: {file_info}\n\n"
        "O'zgartirish uchun «✏️ Tahrirlash» ni bosing.\n"
        "Yangi matn va/yoki rasm, video, audio yuborishingiz mumkin.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"{prefix}:edit")],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="adm:back")],
        ]),
    )


async def numbers_page_text(page: int) -> tuple[str, InlineKeyboardMarkup]:
    """Raqamlar ro'yxati sahifasi: har birida start holati + o'chirish tugmasi."""
    phones = await db.list_numbers()
    started = await db.phones_with_start()
    total = len(phones)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    chunk = phones[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    if not chunk:
        text = "📋 <b>Raqamlar ro'yxati bo'sh.</b>\n\nYangi raqam qo'shing (har qatorga bittadan)."
    else:
        lines = [f"📋 <b>Raqamlar</b> ({total} ta, {page + 1}/{pages}-sahifa):\n"]
        for i, ph in enumerate(chunk, start=page * PAGE_SIZE + 1):
            mark = "✅ start bergan" if ph in started else "⏳ bermagan"
            lines.append(f"{i}. <code>{ph}</code> — {mark}")
        text = "\n".join(lines)
    kb: list[list[InlineKeyboardButton]] = []
    # Har bir raqam uchun o'chirish tugmasi
    for ph in chunk:
        kb.append([InlineKeyboardButton(text=f"❌ {ph}", callback_data=f"adm:del:{ph}")])
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"adm:nums:{page - 1}"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"adm:nums:{page + 1}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data="adm:back")])
    return text, InlineKeyboardMarkup(inline_keyboard=kb)


# ---------- /admin kirish ----------

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("Sizda admin huquqi yo'q. ⛔")
        return
    await state.clear()
    await show_admin_menu(message)


@router.callback_query(F.data == "adm:back")
async def cb_back(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return
    await state.clear()
    await show_admin_menu(call)


# ---------- 1) SMS xabar bo'limi ----------

@router.callback_query(F.data == "adm:sms")
async def cb_sms(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return
    await state.clear()
    sms = await db.get_setting(db.KEY_SMS)
    await call.message.edit_text(
        f"📝 <b>Joriy SMS matn:</b>\n\n{sms or '(bo‘sh)'}\n\n"
        "O'zgartirish uchun «✏️ Tahrirlash» ni bosing.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Tahrirlash", callback_data="adm:sms_edit")],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="adm:back")],
        ]),
    )
    await call.answer()


@router.callback_query(F.data == "adm:sms_edit")
async def cb_sms_edit(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_sms_text)
    await call.message.answer("✍️ Yangi SMS matnini yuboring:")
    await call.answer()


@router.message(AdminStates.waiting_sms_text)
async def sms_text_received(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    if not (message.text or "").strip():
        await message.answer("Iltimos, matn ko'rinishida yuboring.")
        return
    # Saqlashdan oldin tasdiqlash so'raladi
    await state.update_data(new_sms=message.text.strip())
    await message.answer(
        f"Tasdiqlaysizmi? ✅\n\nYangi matn:\n\n{message.text.strip()}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Saqlash", callback_data="adm:sms_yes")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm:sms_no")],
        ]),
    )


@router.callback_query(F.data == "adm:sms_yes")
async def cb_sms_yes(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return
    data = await state.get_data()
    new_sms = (data.get("new_sms") or "").strip()
    if new_sms:
        await db.set_setting(db.KEY_SMS, new_sms)
        await call.message.answer("✅ SMS matn saqlandi.", reply_markup=back_kb())
    else:
        await call.message.answer("Matn topilmadi.", reply_markup=back_kb())
    await state.clear()
    await call.answer()


@router.callback_query(F.data == "adm:sms_no")
async def cb_sms_no(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return
    await state.clear()
    await call.message.answer("❌ Bekor qilindi.", reply_markup=back_kb())
    await call.answer()


# ---------- 2) Raqamlar bo'limi ----------

@router.callback_query(F.data == "adm:numbers")
async def cb_numbers(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return
    await state.clear()
    text, kb = await numbers_page_text(0)
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.message.answer(
        "➕ <b>Yangi raqam qo'shish:</b>\n"
        "Bitta yoki ko'plab yuboring (har qatorga bittadan).\n"
        "Masalan:\n<code>+998901234567\n998901234568\n901234569</code>\n\n"
        "🗑 O'chirish uchun ro'yxatdagi ❌ tugmani bosing\n"
        "yoki <code>/del +998901234567</code> deb yozing.",
        reply_markup=back_kb(),
    )
    await state.set_state(AdminStates.waiting_numbers)
    await call.answer()


@router.callback_query(F.data.startswith("adm:nums:"))
async def cb_numbers_page(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        page = int(call.data.split(":")[-1])
    except ValueError:
        page = 0
    text, kb = await numbers_page_text(page)
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await call.answer()


@router.callback_query(F.data.startswith("adm:del:"))
async def cb_delete_number(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return
    phone = call.data[len("adm:del:"):]
    ok = await db.remove_number(phone)
    await call.answer("O'chirildi ✅" if ok else "Topilmadi ❌", show_alert=False)
    text, kb = await numbers_page_text(0)
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass


@router.message(Command("del"))
async def cmd_del_number(message: Message) -> None:
    """Qo'lda o'chirish: /del +998901234567"""
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Foydalanish: <code>/del +998901234567</code>")
        return
    phone = db.normalize_phone(parts[1])
    if not phone:
        await message.answer("Raqam formati noto'g'ri.")
        return
    ok = await db.remove_number(phone)
    await message.answer(f"{phone} o'chirildi ✅" if ok else "Bunday raqam topilmadi ❌")


@router.message(AdminStates.waiting_numbers)
async def numbers_received(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    # /admin yoki /del kabi buyruqlarni raqam sifatida qabul qilmaymiz
    if message.text and message.text.startswith("/"):
        return
    if not (message.text or "").strip():
        await message.answer("Raqam(lar)ni matn ko'rinishida yuboring.")
        return
    added, dup, bad = [], [], []
    for line in message.text.splitlines():
        line = line.strip().rstrip(",;")
        if not line:
            continue
        phone = db.normalize_phone(line)
        if not phone:
            bad.append(line)
            continue
        ok = await db.add_number(phone)
        (added if ok else dup).append(phone)
    parts = []
    if added:
        parts.append(f"✅ Qo'shildi ({len(added)}):\n" + "\n".join(f"<code>{p}</code>" for p in added))
    if dup:
        parts.append(f"⚠️ Takroriy, qo'shilmadi ({len(dup)}):\n" + "\n".join(f"<code>{p}</code>" for p in dup))
    if bad:
        parts.append(f"❌ Noto'g'ri format ({len(bad)}):\n" + "\n".join(bad))
    await message.answer(
        "\n\n".join(parts) if parts else "Hech narsa qo'shilmadi.",
        reply_markup=back_kb(),
    )
    # Holatni saqlab qolamiz — admin yana raqam yuborishi mumkin
    await state.set_state(AdminStates.waiting_numbers)


# ---------- 3) Musiqa va 4) Xizmatlar bo'limlari ----------

@router.callback_query(F.data == "adm:music")
async def cb_music(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return
    await state.clear()
    try:
        await call.message.delete()
    except Exception:
        pass
    await show_content_section(
        call.message, db.KEY_MUSIC, "🎵 Yangi musiqa va kliplar", "adm:music"
    )
    await call.answer()


@router.callback_query(F.data == "adm:services")
async def cb_services(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return
    await state.clear()
    try:
        await call.message.delete()
    except Exception:
        pass
    await show_content_section(
        call.message, db.KEY_SERVICES, "🛠 Bizning xizmatlar", "adm:services"
    )
    await call.answer()


@router.callback_query(F.data == "adm:music:edit")
async def cb_music_edit(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_content)
    await state.update_data(content_key=db.KEY_MUSIC, content_title="🎵 Yangi musiqa va kliplar")
    await call.message.answer(
        "✍️ Yangi ma'lumotni yuboring.\n"
        "Matn, havola, rasm, video yoki audio bo'lishi mumkin.\n"
        "Rasm/video/audio ni caption (izoh) bilan yuborsangiz — u matn sifatida saqlanadi."
    )
    await call.answer()


@router.callback_query(F.data == "adm:services:edit")
async def cb_services_edit(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_content)
    await state.update_data(content_key=db.KEY_SERVICES, content_title="🛠 Bizning xizmatlar")
    await call.message.answer(
        "✍️ Yangi ma'lumotni yuboring.\n"
        "Matn, havola, rasm, video yoki audio bo'lishi mumkin."
    )
    await call.answer()


@router.message(AdminStates.waiting_content)
async def content_received(message: Message, state: FSMContext) -> None:
    """Admin yuborgan matn/media ni music/services bo'limiga saqlaydi."""
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.startswith("/"):
        return
    data = await state.get_data()
    key = data.get("content_key")
    title = data.get("content_title", "Bo'lim")
    if key not in (db.KEY_MUSIC, db.KEY_SERVICES):
        await state.clear()
        return
    text = message.text or message.caption or ""
    file_id, file_type = None, None
    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    elif message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.audio:
        file_id = message.audio.file_id
        file_type = "audio"
    elif message.voice:
        file_id = message.voice.file_id
        file_type = "voice"
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"
    if not text.strip() and not file_id:
        await message.answer("Matn yoki media (rasm/video/audio) yuboring.")
        return
    await db.set_setting(key, db.dump_content(text.strip(), file_id, file_type))
    await state.clear()
    await message.answer(f"✅ <b>{title}</b> yangilandi.", reply_markup=back_kb())


# ---------- 5) Statistika ----------

async def stats_text() -> str:
    s = await db.get_stats()
    return (
        "📊 <b>Statistika</b>\n\n"
        f"📋 Raqamlar: {s['numbers_total']} ta "
        f"(start bergan: {s['numbers_started']})\n"
        f"👥 Obunachilar: {s['subs_total']} ta\n"
        f"   ✅ faol: {s['subs_active']}\n"
        f"   ⛔ nofaol (bloklagan): {s['subs_inactive']}\n"
        f"⏰ Muddati kelgan (30 kun): {s['due_now']} ta"
    )


@router.callback_query(F.data == "adm:stats")
async def cb_stats(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        await call.message.edit_text(await stats_text(), reply_markup=back_kb())
    except Exception:
        await call.message.answer(await stats_text(), reply_markup=back_kb())
    await call.answer()


@router.message(Command("stat"))
async def cmd_stat(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    await message.answer(await stats_text())


# ---------- 6) Hammasiga hozir yuborish (broadcast) ----------

@router.callback_query(F.data == "adm:bc")
async def cb_broadcast(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return
    s = await db.get_stats()
    if not s["subs_active"]:
        await call.answer("Faol obunachi yo'q.", show_alert=True)
        return
    await call.message.answer(
        f"📢 <b>{s['subs_active']} ta</b> faol obunachiga joriy SMS hozir yuborilsinmi?\n"
        "Yuborilganlarning 30 kunlik hisobi shu sanadan qayta boshlanadi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Yuborish", callback_data="adm:bc_yes")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm:bc_no")],
        ]),
    )
    await call.answer()


@router.callback_query(F.data == "adm:bc_yes")
async def cb_broadcast_yes(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return
    await call.message.edit_text("⏳ Yuborilmoqda...")
    await call.answer()
    from scheduler import send_broadcast
    res = await send_broadcast(call.bot)
    await call.message.answer(
        "📢 <b>Yakunlandi:</b>\n"
        f"✅ yuborildi: {res['sent']}\n"
        f"⛔ bloklagan (nofaol qilindi): {res['blocked']}\n"
        f"❌ xatolik: {res['failed']}",
        reply_markup=back_kb(),
    )


@router.callback_query(F.data == "adm:bc_no")
async def cb_broadcast_no(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return
    await state.clear()
    await call.message.answer("❌ Bekor qilindi.", reply_markup=back_kb())
    await call.answer()
