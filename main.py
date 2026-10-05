# main.py — botni ishga tushirish nuqtasi
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import db
from config import CONFIG
from handlers import admin as admin_handlers
from handlers import user as user_handlers
from scheduler import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("bot")


async def main() -> None:
    # 1) Baza jadvallarini tayyorlash (qayta ishga tushsa ham saqlanadi)
    await db.init_db(CONFIG.db_path)

    # 2) Bot va dispatcher
    bot = Bot(
        token=CONFIG.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    # Admin router birinchi: /admin va admin callbacklar ustuvor
    dp.include_router(admin_handlers.router)
    dp.include_router(user_handlers.router)

    # 3) Scheduler: har kuni 10:00 (Asia/Tashkent) da muddati o'tganlarga yuborish
    scheduler = setup_scheduler(
        bot,
        hour=CONFIG.scheduler_hour,
        minute=CONFIG.scheduler_minute,
        timezone=CONFIG.timezone,
        days=CONFIG.resend_days,
    )

    log.info("Bot ishga tushdi. Adminlar: %s", sorted(CONFIG.admin_ids) or "yo'q")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bot to'xtatildi.")
