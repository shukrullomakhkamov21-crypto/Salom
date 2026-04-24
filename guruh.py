import logging
import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

# --- SOZLAMALAR ---
API_TOKEN = '8737514748:AAEeJwwzVf6e0yzYlwXRT8N0UrvsULGCapI'
ADMIN_ID = 8213426436  # O'zingizning Telegram ID-ingizni yozing

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- BAZA BILAN ISHLASH ---
def init_db():
    conn = sqlite3.connect('groups_shop_v3.db')
    cursor = conn.cursor()
    # Guruhlar jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS groups 
                      (group_link TEXT, price TEXT, admin_user TEXT)''')
    # Foydalanuvchilar jadvali (reklama yuborish uchun)
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY)''')
    conn.commit()
    conn.close()

def add_user_to_db(user_id):
    conn = sqlite3.connect('groups_shop_v3.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

# --- HOLATLAR (States) ---
class AddGroup(StatesGroup):
    group_link = State()
    price = State()

# --- KLAVIATURA ---
def get_main_kb(user_id):
    kb = [
        [types.KeyboardButton(text="🛒 Sotiladigan guruhlar")]
    ]
    if user_id == ADMIN_ID:
        kb.append([types.KeyboardButton(text="➕ Guruh qo'shish")])
    
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    add_user_to_db(message.from_user.id)
    bot_info = await bot.get_me()
    await message.answer(
        f"👋 Salom! <b>@{bot_info.username}</b> botiga xush kelibsiz.\n\n"
        f"🤖 Bu bot orqali sotuvdagi guruhlarni ko'rishingiz mumkin.",
        reply_markup=get_main_kb(message.from_user.id),
        parse_mode="HTML"
    )

# 1. Sotuvdagi guruhlar ro'yxatini chiqarish
@dp.message(F.text == "🛒 Sotiladigan guruhlar")
async def show_groups(message: types.Message):
    conn = sqlite3.connect('groups_shop_v3.db')
    cursor = conn.cursor()
    cursor.execute("SELECT group_link, price, admin_user FROM groups")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await message.answer("⚠️ Hozircha sotuvda guruhlar yo'q.")
        return

    bot_info = await bot.get_me()
    res = f"🚀 <b>@{bot_info.username} – Sotuvdagi guruhlar:</b>\n\n"
    
    for row in rows:
        # HTML formatda linklar va pastki chiziqlar (_) xato bermaydi
        res += (f"📢 <b>Guruh:</b> {row[0]}\n"
                f"💰 <b>Narxi:</b> {row[1]}\n"
                f"👤 <b>Admin:</b> {row[2]}\n"
                f"──────────────────\n")
    
    await message.answer(res, parse_mode="HTML")

# 2. Guruh qo'shish jarayoni (Faqat admin uchun)
@dp.message(F.text == "➕ Guruh qo'shish")
async def start_add(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("📌 Sotiladigan guruh userini yoki linkini yuboring:")
        await state.set_state(AddGroup.group_link)
    else:
        await message.answer("❌ Bu tugma faqat admin uchun.")

@dp.message(AddGroup.group_link)
async def process_link(message: types.Message, state: FSMContext):
    await state.update_data(g_link=message.text)
    await message.answer("💰 Guruh narxini kiriting:")
    await state.set_state(AddGroup.price)

@dp.message(AddGroup.price)
async def process_price(message: types.Message, state: FSMContext):
    data = await state.get_data()
    group_link = data['g_link']
    price = message.text
    admin_tag = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"
    
    # Bazaga saqlash
    conn = sqlite3.connect('groups_shop_v3.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO groups (group_link, price, admin_user) VALUES (?, ?, ?)", 
                   (group_link, price, admin_tag))
    
    # Barcha foydalanuvchilar ro'yxatini olish (reklama uchun)
    cursor.execute("SELECT user_id FROM users")
    all_users = cursor.fetchall()
    conn.commit()
    conn.close()

    await message.answer("✅ Guruh bazaga qo'shildi va foydalanuvchilarga xabar yuborilmoqda...")
    await state.clear()

    # --- AVTOMATIK REKLAMA (MAILING) ---
    bot_info = await bot.get_me()
    announcement = (
        f"🔔 <b>Yangi guruh sotuvga chiqdi!</b>\n\n"
        f"📌 <b>Guruh:</b> {group_link}\n"
        f"💰 <b>Narxi:</b> {price}\n"
        f"👤 <b>Sotuvchi:</b> {admin_tag}\n"
        f"──────────────────\n"
        f"🤖 Bot: @{bot_info.username}"
    )

    for user in all_users:
        try:
            await bot.send_message(user[0], announcement, parse_mode="HTML")
            await asyncio.sleep(0.05) # Telegram bloklamasligi uchun
        except Exception:
            continue

# --- ASOSIY ISHGA TUSHIRISH ---
async def main():
    init_db()
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot to'xtatildi")