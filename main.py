import logging
import sqlite3
import asyncio
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- SOZLAMALAR ---
TOKEN_SHOP = '8737514748:AAEeJwwzVf6e0yzYlwXRT8N0UrvsULGCapI'
TOKEN_TEST = '8750077178:AAFgDf_LDL11-cYvg_KGZUboTnkH-oWPFak'
ADMINS = [8213426436, 8562020437]

logging.basicConfig(level=logging.INFO)
bot_s, bot_t = Bot(token=TOKEN_SHOP), Bot(token=TOKEN_TEST)
dp_s, dp_t = Dispatcher(storage=MemoryStorage()), Dispatcher(storage=MemoryStorage())

# --- BAZA MANTIQI ---
def db_query(sql, params=(), fetch=False):
    conn = sqlite3.connect('final_pro_v5.db', check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        res = cursor.fetchall() if fetch else None
        conn.commit()
        return res
    finally:
        conn.close()

def init_db():
    db_query('CREATE TABLE IF NOT EXISTS shop_groups (id INTEGER PRIMARY KEY, link TEXT, price TEXT, admin TEXT)')
    db_query('CREATE TABLE IF NOT EXISTS shop_users (user_id INTEGER PRIMARY KEY)')
    db_query('CREATE TABLE IF NOT EXISTS test_users (user_id INTEGER PRIMARY KEY, name TEXT)')
    db_query('CREATE TABLE IF NOT EXISTS words (id INTEGER PRIMARY KEY, user_id INTEGER, word TEXT, UNIQUE(user_id, word))')
    db_query('CREATE TABLE IF NOT EXISTS tests (id INTEGER PRIMARY KEY AUTOINCREMENT, q TEXT, v1 TEXT, v2 TEXT, v3 TEXT)')
    db_query('CREATE TABLE IF NOT EXISTS solved (user_id INTEGER, test_id INTEGER, UNIQUE(user_id, test_id))')

# --- STATES ---
class ShopStates(StatesGroup): link = State(); price = State(); bc = State()
class AdminStates(StatesGroup): q=State(); v1=State(); v2=State(); v3=State(); bc=State(); del_t=State(); del_w=State()

# --- ERTALABKI BUDILNIK (05:00) ---
async def morning_alarm():
    users = db_query("SELECT user_id FROM test_users", fetch=True)
    for u in users:
        try: await bot_t.send_message(u[0], "☀️ Diqqat Diqqat uyg'oning!")
        except: pass

# --- 1-BOT (SHOP) ---
@dp_s.message(Command("start"))
async def shop_start(m: types.Message):
    db_query("INSERT OR IGNORE INTO shop_users (user_id) VALUES (?)", (m.from_user.id,))
    kb = [[KeyboardButton(text="🛒 Guruhlar")]]
    if m.from_user.id in ADMINS:
        kb.append([KeyboardButton(text="📢 Rassilka"), KeyboardButton(text="➕ Guruh qo'shish")])
        kb.append([KeyboardButton(text="👥 Foydalanuvchilar")])
    await m.answer("Sotuv botiga xush kelibsiz!", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp_s.message(F.text == "🛒 Guruhlar")
async def show_shop_groups(m: types.Message):
    groups = db_query("SELECT link, price, admin FROM shop_groups", fetch=True)
    if not groups: return await m.answer("Hozircha guruhlar yo'q.")
    text = "🚀 **Sotuvdagi guruhlar:**\n\n"
    for g in groups: text += f"📢 {g[0]}\n💰 Narxi: {g[1]}\n👤 Admin: {g[2]}\n\n"
    await m.answer(text, parse_mode="Markdown")

@dp_s.message(F.text == "➕ Guruh qo'shish", F.from_user.id.in_(ADMINS))
async def shop_add_start(m: types.Message, state: FSMContext):
    await m.answer("Guruh linkini yuboring:"); await state.set_state(ShopStates.link)

@dp_s.message(ShopStates.link)
async def shop_add_link(m: types.Message, state: FSMContext):
    await state.update_data(link=m.text); await m.answer("Narxini yozing:"); await state.set_state(ShopStates.price)

@dp_s.message(ShopStates.price)
async def shop_add_price(m: types.Message, state: FSMContext):
    data = await state.get_data()
    db_query("INSERT INTO shop_groups (link, price, admin) VALUES (?, ?, ?)", (data['link'], m.text, f"@{m.from_user.username or 'admin'}"))
    await m.answer("✅ Guruh qo'shildi!"); await state.clear()

# --- 2-BOT (TEST & WORDS) ---
@dp_t.message(Command("start"))
async def test_start(m: types.Message):
    db_query("INSERT OR IGNORE INTO test_users (user_id, name) VALUES (?, ?)", (m.from_user.id, m.from_user.full_name))
    kb = [[KeyboardButton(text="Testlar 📝"), KeyboardButton(text="So'z ombori 📚")]]
    if m.from_user.id in ADMINS:
        kb.append([KeyboardButton(text="📢 Rassilka"), KeyboardButton(text="➕ Test qo'shish")])
        kb.append([KeyboardButton(text="🗑 Test o'chirish"), KeyboardButton(text="👥 Foydalanuvchilar")])
    await m.answer("Bilim botiga xush kelibsiz!", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp_t.message(F.text == "Testlar 📝")
async def send_test(m: types.Message):
    tests = db_query("SELECT * FROM tests WHERE id NOT IN (SELECT test_id FROM solved WHERE user_id=?)", (m.from_user.id,), fetch=True)
    if not tests: return await m.answer("🎉 Hamma testlarni yechib bo'ldingiz!")
    t = random.choice(tests)
    opts = [t[2], t[3], t[4]]; correct = t[4]; random.shuffle(opts)
    await bot_t.send_poll(m.chat.id, t[1], opts, type='quiz', correct_option_id=opts.index(correct), is_anonymous=False)
    db_query("INSERT OR IGNORE INTO solved (user_id, test_id) VALUES (?, ?)", (m.from_user.id, t[0]))

@dp_t.message(F.text == "So'z ombori 📚")
async def word_menu(m: types.Message):
    kb = [[KeyboardButton(text="📊 So'zlar soni"), KeyboardButton(text="🗑 So'z o'chirish")], [KeyboardButton(text="🔙 Orqaga")]]
    await m.answer("So'zlarni shunchaki yuboring, bot saqlaydi.", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp_t.callback_query(F.data == "show_words")
async def show_words_cb(c: types.CallbackQuery):
    rows = db_query("SELECT word FROM words WHERE user_id=?", (c.from_user.id,), fetch=True)
    if not rows: return await c.answer("Lug'at bo'sh!", show_alert=True)
    msg = "📖 **Sizning so'zlaringiz:**\n\n" + "\n".join([f"{i+1}. {r[0]}" for i, r in enumerate(rows)])
    await c.message.answer(msg, parse_mode="Markdown"); await c.answer()

@dp_t.message(F.text == "➕ Test qo'shish", F.from_user.id.in_(ADMINS))
async def add_test_start(m: types.Message, state: FSMContext):
    await m.answer("Savolni yuboring:"); await state.set_state(AdminStates.q)

@dp_t.message(AdminStates.q)
async def add_test_q(m: types.Message, state: FSMContext):
    await state.update_data(q=m.text); await m.answer("1-xato variant:"); await state.set_state(AdminStates.v1)

@dp_t.message(AdminStates.v1)
async def add_test_v1(m: types.Message, state: FSMContext):
    await state.update_data(v1=m.text); await m.answer("2-xato variant:"); await state.set_state(AdminStates.v2)

@dp_t.message(AdminStates.v2)
async def add_test_v2(m: types.Message, state: FSMContext):
    await state.update_data(v2=m.text); await m.answer("3-TO'G'RI variant:"); await state.set_state(AdminStates.v3)

@dp_t.message(AdminStates.v3)
async def add_test_v3(m: types.Message, state: FSMContext):
    d = await state.get_data()
    db_query("INSERT INTO tests (q, v1, v2, v3) VALUES (?, ?, ?, ?)", (d['q'], d['v1'], d['v2'], m.text))
    await m.answer("✅ Test qo'shildi!"); await state.clear()

@dp_t.message(F.text, ~F.text.startswith("/"))
async def auto_save(m: types.Message, state: FSMContext):
    btns = ["Testlar 📝", "So'z ombori 📚", "📊 So'zlar soni", "🗑 So'z o'chirish", "🔙 Orqaga", "📢 Rassilka", "➕ Test qo'shish"]
    if m.text in btns or await state.get_state(): return
    for w in m.text.split("\n"):
        if w.strip(): db_query("INSERT OR IGNORE INTO words (user_id, word) VALUES (?, ?)", (m.from_user.id, w.strip()))
    await m.answer("✅ Saqlandi.")

# --- MAIN ---
async def main():
    init_db()
    sch = AsyncIOScheduler(timezone='Asia/Dushanbe')
    sch.add_job(morning_alarm, 'cron', hour=5, minute=0)
    sch.start()
    await asyncio.gather(dp_s.start_polling(bot_s), dp_t.start_polling(bot_t))

if __name__ == '__main__':
    asyncio.run(main())