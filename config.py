# config.py — .env dan sozlamalarni o'qish
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()  # .env faylni yuklash


def _parse_admin_ids(raw: str) -> set[int]:
    """'123,456 789' ko'rinishidagi satrni {123,456,789} ga aylantiradi."""
    ids: set[int] = set()
    for part in raw.replace(";", ",").replace(" ", ",").split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: set[int]
    timezone: str = "Asia/Tashkent"
    db_path: str = "bot.db"
    scheduler_hour: int = 10
    scheduler_minute: int = 0
    resend_days: int = 30  # har 30 kunda qayta yuborish


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "BOT_TOKEN topilmadi. .env faylga BOT_TOKEN=... yozing "
            "(.env.example ga qarang)."
        )
    admins = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))
    return Config(bot_token=token, admin_ids=admins)


CONFIG = load_config()
