# scheduler.py — har kuni 10:00 da 30 kunlik tekshiruv
import asyncio
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

import db

log = logging.getLogger(__name__)


async def send_due_messages(bot: Bot, days: int = 30) -> int:
    """Muddati kelgan faol obunachilarga joriy SMS ni yuboradi.

    Qaytaradi: muvaffaqiyatli yuborilganlar soni.
    Forbidden (bloklagan) bo'lsa — bot yiqilmaydi, mijoz nofaol qilinadi.
    """
    try:
        sms_text = await db.get_setting(db.KEY_SMS)
    except Exception as e:
        log.exception("SMS matnni o'qishda xato: %s", e)
        return 0
    if not sms_text.strip():
        log.warning("sms_text bo'sh — yuborish o'tkazib yuborildi.")
        return 0

    try:
        due = await db.get_due_subscribers(days=days)
    except Exception as e:
        log.exception("Qarzdorlar ro'yxatini olishda xato: %s", e)
        return 0

    sent = 0
    for sub in due:
        chat_id = sub["chat_id"]
        try:
            await bot.send_message(chat_id, sms_text)
            await db.update_last_sent(chat_id)
            sent += 1
        except TelegramForbiddenError:
            # Mijoz botni bloklagan — nofaol deb belgilaymiz
            log.info("Chat %s botni bloklagan, nofaol qilindi.", chat_id)
            try:
                await db.set_subscriber_active(chat_id, False)
            except Exception as e:
                log.exception("Nofaol belgilashda xato: %s", e)
        except TelegramAPIError as e:
            log.warning("Chat %s ga yuborilmadi: %s", chat_id, e)
        except Exception as e:
            log.exception("Chat %s ga yuborishda kutilmagan xato: %s", chat_id, e)
        # Telegram limitiga rioya: xabarlar orasida qisqa kutish
        await asyncio.sleep(0.05)
    if due:
        log.info("Reja bo'yicha yuborildi: %s/%s", sent, len(due))
    return sent


async def send_broadcast(bot: Bot) -> dict:
    """Joriy SMS ni BARCHA faol obunachilarga darhol yuboradi.

    Qaytaradi: {"sent":..., "blocked":..., "failed":...}.
    Yuborilganlarning last_sent yangilanadi (keyingi sana shundan +30 kun).
    """
    result = {"sent": 0, "blocked": 0, "failed": 0}
    try:
        sms_text = await db.get_setting(db.KEY_SMS)
    except Exception as e:
        log.exception("SMS matnni o'qishda xato: %s", e)
        return result
    if not sms_text.strip():
        return result
    try:
        subs = await db.get_active_subscribers()
    except Exception as e:
        log.exception("Obunachilarni olishda xato: %s", e)
        return result
    for sub in subs:
        chat_id = sub["chat_id"]
        try:
            await bot.send_message(chat_id, sms_text)
            await db.update_last_sent(chat_id)
            result["sent"] += 1
        except TelegramForbiddenError:
            log.info("Chat %s bloklagan, nofaol qilindi.", chat_id)
            try:
                await db.set_subscriber_active(chat_id, False)
            except Exception:
                pass
            result["blocked"] += 1
        except TelegramAPIError as e:
            log.warning("Chat %s ga yuborilmadi: %s", chat_id, e)
            result["failed"] += 1
        except Exception as e:
            log.exception("Chat %s ga yuborishda xato: %s", chat_id, e)
            result["failed"] += 1
        await asyncio.sleep(0.05)
    log.info("Broadcast: %s", result)
    return result


def setup_scheduler(bot: Bot, hour: int = 10, minute: int = 0,
                    timezone: str = "Asia/Tashkent", days: int = 30) -> AsyncIOScheduler:
    """Har kuni belgilangan vaqtda tekshiruv ishga tushiradigan scheduler."""
    scheduler = AsyncIOScheduler(timezone=ZoneInfo(timezone))
    scheduler.add_job(
        send_due_messages,
        CronTrigger(hour=hour, minute=minute),
        kwargs={"bot": bot, "days": days},
        id="daily_sms",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    log.info("Scheduler ishga tushdi: har kuni %02d:%02d (%s)", hour, minute, timezone)
    return scheduler
