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

# --- SOZLAMALAR ---
TOKEN_SHOP = '8737514748:AAEeJwwzVf6e0yzYlwXRT8N0UrvsULGCapI'
TOKEN_TEST = '8750077178:AAFgDf_LDL11-cYvg_KGZUboTnkH-oWPFak'
ADMIN_ID = [8213426436, 8562020437]

logging.basicConfig(level=logging.INFO)
bot_shop, bot_test = Bot(token=TOKEN_SHOP), Bot(token=TOKEN_TEST)
dp_shop, dp_test = Dispatcher(storage=MemoryStorage()), Dispatcher(storage=MemoryStorage())

# --- BAZA FUNKSIYASI ---
def db_query(sql, params=(), fetch=False):
    conn = sqlite3.connect('final_bots_v4.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(sql, params)
    res = cursor.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return res

def init_db():
    db_query('CREATE TABLE IF NOT EXISTS shop_groups (link TEXT, price TEXT, admin TEXT)')
    db_query('CREATE TABLE IF NOT EXISTS shop_users (user_id INTEGER PRIMARY KEY)')
    db_query('CREATE TABLE IF NOT EXISTS test_users (user_id INTEGER PRIMARY KEY, name TEXT)')
    db_query('CREATE TABLE IF NOT EXISTS words (user_id INTEGER, word TEXT, UNIQUE(user_id, word))')
    db_query('CREATE TABLE IF NOT EXISTS tests (id INTEGER PRIMARY KEY AUTOINCREMENT, q TEXT, v1 TEXT, v2 TEXT, v3 TEXT)')
    db_query('CREATE TABLE IF NOT EXISTS solved (user_id INTEGER, test_id INTEGER, UNIQUE(user_id, test_id))')

# --- STATES (HOLATLAR) ---
class ShopStates(StatesGroup): link = State(); price = State()
class WordStates(StatesGroup): waiting = State()
class AdminStates(StatesGroup): q = State(); v1 = State(); v2 = State(); v3 = State(); bc_msg = State()

# --- 1-BOT: SHOP HANDLERLARI ---
@dp_shop.message(Command("start"))
async def shop_start(m: types.Message):
    db_query("INSERT OR IGNORE INTO shop_users (user_id) VALUES (?)", (m.from_user.id,))
    kb = [[KeyboardButton(text="🛒 Sotiladigan guruhlar")]]
    if m.from_user.id == ADMIN_ID: kb.append([KeyboardButton(text="➕ Guruh qo'shish")])
    await m.answer("Sotuvdagi guruhlar botiga xush kelibsiz!", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp_shop.message(F.text == "🛒 Sotiladigan guruhlar")
async def show_groups(m: types.Message):
    rows = db_query("SELECT * FROM shop_groups", fetch=True)
    if not rows: return await m.answer("⚠️ Hozircha guruhlar yo'q.")
    res = "🚀 **Sotuvdagi guruhlar:**\n\n"
    for r in rows: res += f"📢 {r[0]}\n💰 Narxi: {r[1]}\n👤 Admin: {r[2]}\n───\n"
    await m.answer(res, parse_mode="Markdown")

@dp_shop.message(F.text == "➕ Guruh qo'shish", F.from_user.id == ADMIN_ID)
async def shop_add(m: types.Message, state: FSMContext):
    await m.answer("Guruh linkini yuboring:"); await state.set_state(ShopStates.link)

@dp_shop.message(ShopStates.link)
async def shop_link(m: types.Message, state: FSMContext):
    await state.update_data(link=m.text); await m.answer("Narxini yozing:"); await state.set_state(ShopStates.price)

@dp_shop.message(ShopStates.price)
async def shop_price(m: types.Message, state: FSMContext):
    data = await state.get_data()
    db_query("INSERT INTO shop_groups VALUES (?, ?, ?)", (data['link'], m.text, f"@{m.from_user.username}"))
    await m.answer("✅ Guruh qo'shildi!"); await state.clear()

# --- 2-BOT: TEST & WORD HANDLERLARI (RASSILKA BILAN) ---
@dp_test.message(Command("start"))
async def test_start(m: types.Message):
    db_query("INSERT OR IGNORE INTO test_users (user_id, name) VALUES (?, ?)", (m.from_user.id, m.from_user.first_name))
    kb = [[KeyboardButton(text="Testlar 📝"), KeyboardButton(text="So'z ombori 📚")]]
    if m.from_user.id == ADMIN_ID:
        kb.append([KeyboardButton(text="📢 Rassilka"), KeyboardButton(text="➕ Test qo'shish")])
    await m.answer("Bilim sinash botiga xush kelibsiz!", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

# RASSILKA (INLINE TUGMALAR BILAN)
@dp_test.message(F.text == "📢 Rassilka", F.from_user.id == ADMIN_ID)
async def bc_type(m: types.Message):
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Oddiy xabar", callback_data="bc_msg"),
         InlineKeyboardButton(text="📊 Test (Poll) yuborish", callback_data="bc_test")]
    ])
    await m.answer("Rassilka turini tanlang:", reply_markup=ikb)

@dp_test.callback_query(F.data == "bc_msg")
async def bc_msg_step(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer("Xabarni yuboring (rasm, tekst yoki video):")
    await state.set_state(AdminStates.bc_msg); await c.answer()

@dp_test.message(AdminStates.bc_msg)
async def bc_msg_send(m: types.Message, state: FSMContext):
    users = db_query("SELECT user_id FROM test_users", fetch=True)
    count = 0
    for u in users:
        try: await m.copy_to(u[0]); count += 1
        except: continue
    await m.answer(f"✅ Xabar {count} kishiga yuborildi."); await state.clear()

# TEST QO'SHISH VA AVTOMATIK YUBORISH
@dp_test.message(F.text == "➕ Test qo'shish", F.from_user.id == ADMIN_ID)
@dp_test.callback_query(F.data == "bc_test")
async def start_test_add(event, state: FSMContext):
    msg = event.message if isinstance(event, types.CallbackQuery) else event
    await msg.answer("Test savolini yuboring:"); await state.set_state(AdminStates.q)
    if isinstance(event, types.CallbackQuery): await event.answer()

@dp_test.message(AdminStates.q)
async def t_q(m: types.Message, state: FSMContext):
    await state.update_data(q=m.text); await m.answer("1-variantni yuboring (Xato):"); await state.set_state(AdminStates.v1)

@dp_test.message(AdminStates.v1)
async def t_v1(m: types.Message, state: FSMContext):
    await state.update_data(v1=m.text); await m.answer("2-variantni yuboring (Xato):"); await state.set_state(AdminStates.v2)

@dp_test.message(AdminStates.v2)
async def t_v2(m: types.Message, state: FSMContext):
    await state.update_data(v2=m.text); await m.answer("3-variantni yuboring (TO'G'RI):"); await state.set_state(AdminStates.v3)

@dp_test.message(AdminStates.v3)
async def t_v3(m: types.Message, state: FSMContext):
    data = await state.get_data()
    db_query("INSERT INTO tests (q, v1, v2, v3) VALUES (?, ?, ?, ?)", (data['q'], data['v1'], data['v2'], m.text))
    
    # HAMMAGA YUBORISH (POLL)
    users = db_query("SELECT user_id FROM test_users", fetch=True)
    opts = [data['v1'], data['v2'], m.text]; correct_idx = 2; random.shuffle(opts)
    # Yangi indexni topish
    new_idx = opts.index(m.text)
    
    for u in users:
        try: await bot_test.send_poll(u[0], data['q'], opts, type='quiz', correct_option_id=new_idx, is_anonymous=False)
        except: continue
    
    await m.answer("✅ Test saqlandi va barchaga yuborildi!"); await state.clear()

# SO'Z OMBORI (MUKAMMAL)
@dp_test.message(F.text == "So'z ombori 📚")
async def w_menu(m: types.Message):
    kb = [[KeyboardButton(text="📥 So'z qo'shish"), KeyboardButton(text="📊 Jami so'zlar")], [KeyboardButton(text="🔙 Orqaga")]]
    await m.answer("So'z ombori:", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp_test.message(F.text == "📥 So'z qo'shish")
async def w_add(m: types.Message, state: FSMContext):
    await m.answer("So'zlarni yuboring:"); await state.set_state(WordStates.waiting)

@dp_test.message(WordStates.waiting, F.text != "🔙 Orqaga")
async def w_save(m: types.Message):
    if m.text == "📊 Jami so'zlar": return
    for w in m.text.split("\n"):
        if w.strip(): db_query("INSERT OR IGNORE INTO words VALUES (?, ?)", (m.from_user.id, w.strip()))
    await m.answer("✅ Saqlandi.")

@dp_test.message(F.text == "Testlar 📝")
async def send_random_t(m: types.Message):
    tests = db_query("SELECT * FROM tests WHERE id NOT IN (SELECT test_id FROM solved WHERE user_id=?)", (m.from_user.id,), fetch=True)
    if not tests: return await m.answer("🎉 Hamma testlarni yechdingiz!")
    t = random.choice(tests)
    opts = [t[2], t[3], t[4]]; correct = t[4]; random.shuffle(opts)
    await bot_test.send_poll(m.chat.id, t[1], opts, type='quiz', correct_option_id=opts.index(correct), is_anonymous=False)

@dp_test.message(F.text == "🔙 Orqaga")
async def back_to_start(m: types.Message, state: FSMContext): await state.clear(); await test_start(m)

# --- START ---
async def main():
    init_db(); print("Botlar ishga tushdi!")
    await asyncio.gather(dp_shop.start_polling(bot_shop), dp_test.start_polling(bot_test))

if __name__ == '__main__':
    try: asyncio.run(main())
    except: pass