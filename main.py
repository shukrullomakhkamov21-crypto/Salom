import logging
import sqlite3
import asyncio
import random
from datetime import datetime
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
    cursor = conn.cursor()
    cursor.execute(sql, params)
    res = cursor.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return res

def init_db():
    db_query('CREATE TABLE IF NOT EXISTS shop_groups (id INTEGER PRIMARY KEY, link TEXT, price TEXT, admin TEXT)')
    db_query('CREATE TABLE IF NOT EXISTS shop_users (user_id INTEGER PRIMARY KEY)')
    db_query('CREATE TABLE IF NOT EXISTS test_users (user_id INTEGER PRIMARY KEY, name TEXT)')
    db_query('CREATE TABLE IF NOT EXISTS words (id INTEGER PRIMARY KEY, user_id INTEGER, word TEXT, UNIQUE(user_id, word))')
    db_query('CREATE TABLE IF NOT EXISTS tests (id INTEGER PRIMARY KEY AUTOINCREMENT, q TEXT, v1 TEXT, v2 TEXT, v3 TEXT)')
    db_query('CREATE TABLE IF NOT EXISTS solved (user_id INTEGER, test_id INTEGER, UNIQUE(user_id, test_id))')

# --- STATES ---
class AdminStates(StatesGroup): q=State(); v1=State(); v2=State(); v3=State(); bc=State(); del_w=State(); del_t=State()

# --- ERTALABKI XABAR (5:00 AM) ---
async def morning_alarm():
    users = db_query("SELECT user_id FROM test_users", fetch=True)
    for u in users:
        try: await bot_t.send_message(u[0], "☀️ Diqqat Diqqat uyg'oning!")
        except: pass

# --- ADMIN UCHUN UMUMIY FUNKSIYALAR ---
async def send_new_user_alert(user_id, name, bot_type):
    for admin in ADMINS:
        try: await bot_t.send_message(admin, f"👤 Yangi foydalanuvchi ({bot_type}):\nID: {user_id}\nIsm: {name}")
        except: pass

# --- 1-BOT (SHOP) HANDLERLARI ---
@dp_s.message(Command("start"))
async def shop_start(m: types.Message):
    if db_query("INSERT OR IGNORE INTO shop_users (user_id) VALUES (?)", (m.from_user.id,)):
        await send_new_user_alert(m.from_user.id, m.from_user.full_name, "Shop Bot")
    kb = [[KeyboardButton(text="🛒 Guruhlar")]]
    if m.from_user.id in ADMINS: kb.append([KeyboardButton(text="📢 Rassilka"), KeyboardButton(text="👥 Foydalanuvchilar")])
    await m.answer("Sotuv botiga xush kelibsiz!", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp_s.message(F.text == "📢 Rassilka", F.from_user.id.in_(ADMINS))
async def shop_bc(m: types.Message, state: FSMContext):
    await m.answer("Xabarni yuboring:"); await state.set_state(AdminStates.bc)

@dp_s.message(AdminStates.bc)
async def shop_bc_send(m: types.Message, state: FSMContext):
    users = db_query("SELECT user_id FROM shop_users", fetch=True)
    count = 0
    for u in users:
        try: await m.copy_to(u[0]); count += 1
        except: continue
    await m.answer(f"✅ {count} kishiga yuborildi."); await state.clear()
# --- SHOP BOT: GURUH QO'SHISH FUNKSIYASI ---
@dp_s.message(F.text == "➕ Guruh qo'shish", F.from_user.id.in_(ADMINS))
async def shop_add_start(m: types.Message, state: FSMContext):
    await m.answer("Guruh linkini yuboring:"); await state.set_state(ShopStates.link)

@dp_s.message(ShopStates.link)
async def shop_add_link(m: types.Message, state: FSMContext):
    await state.update_data(link=m.text); await m.answer("Narxini yozing:"); await state.set_state(ShopStates.price)

@dp_s.message(ShopStates.price)
async def shop_add_price(m: types.Message, state: FSMContext):
    data = await state.get_data()
    db_query("INSERT INTO shop_groups (link, price, admin) VALUES (?, ?, ?)", 
             (data['link'], m.text, f"@{m.from_user.username or 'admin'}"))
    await m.answer("✅ Guruh muvaffaqiyatli qo'shildi!"); await state.clear()

# --- 2-BOT (TEST & WORDS) HANDLERLARI ---
@dp_t.message(Command("start"))
async def test_start(m: types.Message):
    db_query("INSERT OR IGNORE INTO test_users (user_id, name) VALUES (?, ?)", (m.from_user.id, m.from_user.full_name))
    kb = [[KeyboardButton(text="Testlar 📝"), KeyboardButton(text="So'z ombori 📚")]]
    if m.from_user.id in ADMINS:
        kb.append([KeyboardButton(text="📢 Rassilka"), KeyboardButton(text="➕ Test qo'shish")])
        kb.append([KeyboardButton(text="🗑 Test o'chirish"), KeyboardButton(text="👥 Foydalanuvchilar")])
    await m.answer("Bilim botiga xush kelibsiz!", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

# SO'Z OMBORI (YANGI MANTIQ)
@dp_t.message(F.text == "So'z ombori 📚")
async def w_menu(m: types.Message, state: FSMContext):
    kb = [[KeyboardButton(text="📊 So'zlar soni"), KeyboardButton(text="🗑 So'z o'chirish")], [KeyboardButton(text="🔙 Orqaga")]]
    await m.answer("So'zlarni shunchaki yuboring (bitta-bitta yoki qatorma-qator).\nBot ularni avtomatik saqlaydi.", 
                   reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))
    await state.set_state(WordStates.waiting if 'WordStates' in globals() else AdminStates.bc) # Fallback

@dp_t.message(F.text == "📊 So'zlar soni")
async def w_count(m: types.Message):
    res = db_query("SELECT COUNT(*) FROM words WHERE user_id=?", (m.from_user.id,), fetch=True)
    ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📖 So'zlarni ko'rish", callback_data="show_words")]])
    await m.answer(f"📊 Sizda jami {res[0][0]} ta so'z bor.", reply_markup=ikb)

@dp_t.callback_query(F.data == "show_words")
async def w_show(c: types.CallbackQuery):
    rows = db_query("SELECT word FROM words WHERE user_id=?", (c.from_user.id,), fetch=True)
    if not rows: return await c.answer("Lug'at bo'sh!")
    msg = "\n".join([f"{i+1}. {r[0]}" for i, r in enumerate(rows)])
    await c.message.answer(f"📖 **Sizning so'zlaringiz:**\n\n{msg}", parse_mode="Markdown")

@dp_t.message(F.text == "🗑 So'z o'chirish")
async def w_del_start(m: types.Message, state: FSMContext):
    await m.answer("O'chirmoqchi bo'lgan so'zingizni yozing:"); await state.set_state(AdminStates.del_w)

@dp_t.message(AdminStates.del_w) # Bu yerda test_bot dispatcher ishlatiladi
async def w_del_done(m: types.Message, state: FSMContext):
    db_query("DELETE FROM words WHERE user_id=? AND word=?", (m.from_user.id, m.text.strip()))
    await m.answer("✅ Agar so'z mavjud bo'lsa, o'chirildi."); await state.clear()

# RASSILKA (TEST BOT)
@dp_t.message(F.text == "📢 Rassilka", F.from_user.id.in_(ADMINS))
async def bc_t_type(m: types.Message):
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Oddiy xabar", callback_data="bc_msg"),
         InlineKeyboardButton(text="📊 Test yuborish", callback_data="bc_test")]
    ])
    await m.answer("Rassilka turi:", reply_markup=ikb)

@dp_t.callback_query(F.data == "bc_msg")
async def bc_t_msg(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer("Xabarni yuboring:"); await state.set_state(AdminStates.bc); await c.answer()

@dp_t.message(AdminStates.bc)
async def bc_t_send(m: types.Message, state: FSMContext):
    users = db_query("SELECT user_id FROM test_users", fetch=True)
    count = 0
    for u in users:
        try: await m.copy_to(u[0]); count += 1
        except: continue
    await m.answer(f"✅ {count} kishiga yuborildi."); await state.clear()

# ADMIN: FOYDHALANUVCHILARNI KO'RISH
@dp_t.message(F.text == "👥 Foydalanuvchilar", F.from_user.id.in_(ADMINS))
async def show_u(m: types.Message):
    u_test = db_query("SELECT COUNT(*) FROM test_users", fetch=True)[0][0]
    u_shop = db_query("SELECT COUNT(*) FROM shop_users", fetch=True)[0][0]
    await m.answer(f"👥 **Foydalanuvchilar:**\n\nTest Bot: {u_test} ta\nShop Bot: {u_shop} ta", parse_mode="Markdown")

# ADMIN: TEST O'CHIRISH
@dp_t.message(F.text == "🗑 Test o'chirish", F.from_user.id.in_(ADMINS))
async def del_t_start(m: types.Message, state: FSMContext):
    tests = db_query("SELECT id, q FROM tests", fetch=True)
    res = "\n".join([f"{t[0]}. {t[1]}" for t in tests])
    await m.answer(f"O'chirish uchun ID raqamini yozing:\n\n{res}"); await state.set_state(AdminStates.del_t)

@dp_t.message(AdminStates.del_t)
async def del_t_done(m: types.Message, state: FSMContext):
    db_query("DELETE FROM tests WHERE id=?", (m.text,))
    await m.answer("✅ Test o'chirildi."); await state.clear()

# AVTOMATIK SO'Z QO'SHISH (Handlerlarga tushmagan hamma tekst so'z deb olinadi)
@dp_t.message(F.text, ~F.text.startswith("/"))
async def auto_word_save(m: types.Message):
    if m.text in ["Testlar 📝", "So'z ombori 📚", "📊 So'zlar soni", "🗑 So'z o'chirish", "🔙 Orqaga"]: return
    added = 0
    for w in m.text.split("\n"):
        word = w.strip()
        if word:
            try:
                db_query("INSERT OR IGNORE INTO words (user_id, word) VALUES (?, ?)", (m.from_user.id, word))
                added += 1
            except: pass
    if added > 0: await m.answer(f"✅ {added} ta so'z lug'atga qo'shildi.")

# --- ISHGA TUSHIRISH ---
async def main():
    init_db()
    scheduler = AsyncIOScheduler(timezone='Asia/Dushanbe')
    scheduler.add_job(morning_alarm, 'cron', hour=5, minute=0)
    scheduler.start()
    print("Botlar va Budilnik ishga tushdi!")
    await asyncio.gather(dp_s.start_polling(bot_s), dp_t.start_polling(bot_t))

if __name__ == '__main__':
    asyncio.run(main())