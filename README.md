# 30 kunlik SMS yuboruvchi Telegram bot

Admin kiritgan SMS xabarni `/start` bergan mijozlarga har **30 kunda bir marta**
yuborib turadi. Python 3.11, aiogram 3, SQLite, APScheduler.

## Imkoniyatlar

- Mijoz `/start` → «📱 Raqamni yuborish» → raqam admin ro'yxatida bo'lsa obuna
  bo'ladi, darhol joriy SMS ni oladi, keyin har 30 kunda qayta oladi.
- Har bir raqam uchun alohida hisob: `last_sent` bazada saqlanadi.
- Scheduler har kuni **10:00 (Asia/Tashkent)** da muddati o'tganlarga yuboradi.
- Bloklagan mijoz `Forbidden` da `nofaol` qilinadi, bot yiqilmaydi.
- Admin panel (`/admin`, faqat `ADMIN_IDS` uchun):
  1. 📝 Yuboriladigan SMS xabar (ko'rish, tahrirlash, tasdiqlash bilan saqlash)
  2. ➕ Yangi raqam kiritish (bitta/ko'plab, ro'yxat, o'chirish, start holati)
  3. 🎵 Yangi musiqa va kliplar (matn/media tahrirlash)
  4. 🛠 Bizning xizmatlar (matn/media tahrirlash)

## Loyiha tuzilmasi

```
main.py            — ishga tushirish nuqtasi
config.py          — .env dan sozlama o'qish (BOT_TOKEN, ADMIN_IDS)
db.py              — SQLite: settings, numbers, subscribers
handlers/user.py   — mijoz tomoni (/start, kontakt, info tugmalar)
handlers/admin.py  — admin panel (/admin, FSM)
scheduler.py       — kunlik tekshiruv (APScheduler)
requirements.txt
.env.example
README.md
```

## Ishga tushirish

```bash
# 1) Virtual muhit (ixtiyoriy, lekin tavsiya etiladi)
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
# source venv/bin/activate

# 2) Kutubxonalar
pip install -r requirements.txt

# 3) Sozlama
copy .env.example .env
# .env ni ochib BOT_TOKEN va ADMIN_IDS ni yozing
# (ADMIN_IDS ni @userinfobot dan bilib oling)

# 4) Ishga tushirish
python main.py
```

## Foydalanish

1. Admin `/admin` → «➕ Yangi raqam» → raqamlarni kiritadi.
2. Admin «📝 SMS xabar» → matnni kiritib tasdiqlaydi.
3. Mijoz `/start` → «📱 Raqamni yuborish» → obuna bo'ladi, SMS oladi.
4. Har kuni 10:00 da 30 kuni to'lganlarga avtomatik qayta yuboriladi.
5. «🎵 Musiqa» va «🛠 Xizmatlar» bo'limlari admin paneldan to'ldiriladi,
   mijoz menyudagi tugmalar orqali ko'radi.

## Eslatmalar

- Token hech qachon kodga yozilmaydi — faqat `.env` da.
- Baza `bot.db` faylida saqlanadi — bot qayta ishga tushsa hisob yo'qolmaydi.
- Raqamlar `+998XXXXXXXXX` formatga avtomatik keltirib solishtiriladi.
