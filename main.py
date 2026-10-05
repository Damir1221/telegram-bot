# main.py — botni ishga tushirish nuqtasi
import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web

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


async def run_health_server() -> None:
    """Render bepul Web Service uchun sog'liq tekshiruvi.

    Render ochiq port talab qiladi, UptimeRobot esa shu manzilni
    har 5 daqiqada chaqirib servisni "uxlab" qolishdan saqlaydi.
    PORT ni Render avtomatik beradi, lokalda 10000.
    """
    async def health(_: web.Request) -> web.Response:
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "10000"))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    log.info("Health server %s-portda ishga tushdi.", port)
    # Polling bilan birga yashashi uchun cheksiz kutamiz
    await asyncio.Event().wait()


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
    health_task = asyncio.create_task(run_health_server())
    try:
        await dp.start_polling(bot)
    finally:
        health_task.cancel()
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bot to'xtatildi.")
