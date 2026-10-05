# db.py — SQLite bilan barcha bazaviy amallar (aiosqlite, async)
import json
import re
import aiosqlite
from datetime import datetime, timezone

DB_PATH = "bot.db"

# Standart sozlama kalitlari (texnik talabga muvofiq)
KEY_SMS = "sms_text"
KEY_MUSIC = "music_content"        # JSON: {"text":..., "file_id":..., "file_type":...}
KEY_SERVICES = "services_content"  # JSON: {"text":..., "file_id":..., "file_type":...}

DEFAULT_SMS = "Assalomu alaykum! Bu oylik eslatma xabari."
DEFAULT_EMPTY_CONTENT = json.dumps(
    {"text": "", "file_id": None, "file_type": None}, ensure_ascii=False
)


# ---------- Telefon raqamni normallashtirish ----------

def normalize_phone(raw: str) -> str | None:
    """Har qanday kiritilgan raqamni +998XXXXXXXXX formatga keltiradi.

    Qabul qiladi: +998901234567, 998901234567, 901234567,
    bo'shliq/chiziq/qavs bilan yozilgan variantlar.
    Noto'g'ri bo'lsa None qaytaradi.
    """
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw.strip())
    if digits.startswith("998") and len(digits) == 12:
        phone = "+" + digits
    elif len(digits) == 9 and digits[0] in "35789":
        phone = "+998" + digits
    elif len(digits) == 10 and digits.startswith("0"):
        phone = "+998" + digits[1:]
    else:
        return None
    if re.fullmatch(r"\+998\d{9}", phone):
        return phone
    return None


def utcnow_iso() -> str:
    """Hozirgi UTC vaqtni ISO satrda qaytaradi (bazada saqlash uchun)."""
    return datetime.now(timezone.utc).isoformat()


# ---------- Baza init ----------

async def init_db(db_path: str = DB_PATH) -> None:
    """Jadvallarni yaratadi va standart sozlamalarni qo'yadi."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """CREATE TABLE IF NOT EXISTS settings(
                   key TEXT PRIMARY KEY,
                   value TEXT NOT NULL
               )"""
        )
        await db.execute(
            """CREATE TABLE IF NOT EXISTS numbers(
                   phone TEXT PRIMARY KEY,
                   added_at TEXT NOT NULL
               )"""
        )
        await db.execute(
            """CREATE TABLE IF NOT EXISTS subscribers(
                   chat_id INTEGER PRIMARY KEY,
                   phone TEXT NOT NULL,
                   active INTEGER NOT NULL DEFAULT 1,
                   last_sent TEXT
               )"""
        )
        for key, default in (
            (KEY_SMS, DEFAULT_SMS),
            (KEY_MUSIC, DEFAULT_EMPTY_CONTENT),
            (KEY_SERVICES, DEFAULT_EMPTY_CONTENT),
        ):
            await db.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
                (key, default),
            )
        await db.commit()


# ---------- settings (kalit-qiymat) ----------

async def get_setting(key: str, db_path: str = DB_PATH) -> str:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else ""


async def set_setting(key: str, value: str, db_path: str = DB_PATH) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        await db.commit()


def parse_content(raw: str) -> dict:
    """music/services JSON ni xavfsiz o'qish. Eski format (oddiy matn) ni ham qo'llaydi."""
    if not raw:
        return {"text": "", "file_id": None, "file_type": None}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {
                "text": data.get("text") or "",
                "file_id": data.get("file_id"),
                "file_type": data.get("file_type"),
            }
    except (json.JSONDecodeError, TypeError):
        pass
    return {"text": raw, "file_id": None, "file_type": None}


def dump_content(text: str = "", file_id: str | None = None,
                 file_type: str | None = None) -> str:
    return json.dumps(
        {"text": text or "", "file_id": file_id, "file_type": file_type},
        ensure_ascii=False,
    )


# ---------- numbers (ruxsat etilgan raqamlar) ----------

async def add_number(phone: str, db_path: str = DB_PATH) -> bool:
    """Raqam qo'shadi. Yangi bo'lsa True, takroriy bo'lsa False."""
    async with aiosqlite.connect(db_path) as db:
        try:
            await db.execute(
                "INSERT INTO numbers(phone, added_at) VALUES(?, ?)",
                (phone, utcnow_iso()),
            )
            await db.commit()
            return True
        except Exception:
            return False  # PRIMARY KEY takrori


async def remove_number(phone: str, db_path: str = DB_PATH) -> bool:
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute("DELETE FROM numbers WHERE phone=?", (phone,))
        await db.commit()
        return cur.rowcount > 0


async def list_numbers(db_path: str = DB_PATH) -> list[str]:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT phone FROM numbers ORDER BY phone") as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def is_number_allowed(phone: str, db_path: str = DB_PATH) -> bool:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT 1 FROM numbers WHERE phone=?", (phone,)) as cur:
            return await cur.fetchone() is not None


# ---------- subscribers (obunachilar) ----------

async def upsert_subscriber(chat_id: int, phone: str, db_path: str = DB_PATH) -> None:
    """Obunani yaratadi/yangilaydi, active=1 qiladi, last_sent=hozir."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """INSERT INTO subscribers(chat_id, phone, active, last_sent)
               VALUES(?, ?, 1, ?)
               ON CONFLICT(chat_id) DO UPDATE SET
                 phone=excluded.phone, active=1, last_sent=excluded.last_sent""",
            (chat_id, phone, utcnow_iso()),
        )
        await db.commit()


async def get_subscriber(chat_id: int, db_path: str = DB_PATH) -> dict | None:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT chat_id, phone, active, last_sent FROM subscribers WHERE chat_id=?",
            (chat_id,),
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            return {"chat_id": row[0], "phone": row[1],
                    "active": bool(row[2]), "last_sent": row[3]}


async def set_subscriber_active(chat_id: int, active: bool,
                                db_path: str = DB_PATH) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE subscribers SET active=? WHERE chat_id=?",
            (1 if active else 0, chat_id),
        )
        await db.commit()


async def update_last_sent(chat_id: int, when_iso: str | None = None,
                           db_path: str = DB_PATH) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE subscribers SET last_sent=?, active=1 WHERE chat_id=?",
            (when_iso or utcnow_iso(), chat_id),
        )
        await db.commit()


async def get_due_subscribers(days: int = 30, db_path: str = DB_PATH) -> list[dict]:
    """last_sent dan `days` kun o'tgan faol obunachilar ro'yxati."""
    now = datetime.now(timezone.utc)
    due: list[dict] = []
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT chat_id, phone, last_sent FROM subscribers WHERE active=1"
        ) as cur:
            async for row in cur:
                chat_id, phone, last_sent = row
                try:
                    sent = datetime.fromisoformat(last_sent) if last_sent else None
                    if sent is None:
                        due.append({"chat_id": chat_id, "phone": phone})
                        continue
                    if sent.tzinfo is None:
                        sent = sent.replace(tzinfo=timezone.utc)
                    if (now - sent).total_seconds() >= days * 86400:
                        due.append({"chat_id": chat_id, "phone": phone})
                except (ValueError, TypeError):
                    due.append({"chat_id": chat_id, "phone": phone})
    return due


async def phones_with_start(db_path: str = DB_PATH) -> set[str]:
    """Hech bo'lmasa bir marta start bergan (subscribers da bor) raqamlar."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT DISTINCT phone FROM subscribers") as cur:
            rows = await cur.fetchall()
            return {r[0] for r in rows}


async def get_active_subscribers(db_path: str = DB_PATH) -> list[dict]:
    """Barcha faol obunachilar (darhol yuborish uchun)."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT chat_id, phone FROM subscribers WHERE active=1"
        ) as cur:
            return [{"chat_id": r[0], "phone": r[1]} async for r in cur]


async def get_stats(days: int = 30, db_path: str = DB_PATH) -> dict:
    """Admin statistikasi: raqamlar, obunachilar, muddati kelganlar."""
    numbers = await list_numbers(db_path)
    started = await phones_with_start(db_path)
    total = active = 0
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT COUNT(*), SUM(active) FROM subscribers") as cur:
            row = await cur.fetchone()
            total = row[0] or 0
            active = row[1] or 0
    due = await get_due_subscribers(days=days, db_path=db_path)
    return {
        "numbers_total": len(numbers),
        "numbers_started": len(started & set(numbers)),
        "subs_total": total,
        "subs_active": active,
        "subs_inactive": total - active,
        "due_now": len(due),
    }
