import os, logging, asyncio, random, aiosqlite, aiocron
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- 1. SOZLAMALAR ---
TOKEN_SHOP = '8737514748:AAEeJwwzVf6e0yzYlwXRT8N0UrvsULGCapI'
TOKEN_TEST = '8750077178:AAFgDf_LDL11-cYvg_KGZUboTnkH-oWPFak'
ADMIN_LIST = [8213426436, 8562020437]
REQUIRED_CHANNEL = "@pythontagbot"  # Sening kanaling

bot_s, bot_t = Bot(token=TOKEN_SHOP), Bot(token=TOKEN_TEST)
dp_s, dp_t = Dispatcher(storage=MemoryStorage()), Dispatcher(storage=MemoryStorage())

RESERVED_BUTTONS = ["Test yechish 📝", "So'zlar ombori 📚", "📢 Rassilka", "📊 Statistika", "➕ Test qo'shish", "🗑 Test o'chirish", "Umumiy so'zlar soni", "Kerakli so'zni o'chirish", "🔙 Orqaga", "🛒 Guruhlar", "➕ Guruh qo'shish"]

class IsAdmin(BaseFilter):
    async def __call__(self, m: types.Message) -> bool:
        return m.from_user.id in ADMIN_LIST

# --- 2. OBUNANI TEKSHIRISH FUNKSIYASI ---
async def check_sub(user_id: int, bot: Bot):
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        if member.status in ["creator", "administrator", "member"]:
            return True
        return False
    except:
        return False

def sub_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Kanalga obuna bo'lish 🚀", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}")],
        [InlineKeyboardButton(text="Tekshirish ✅", callback_data="check_sub")]
    ])

# --- 3. DATABASE ---
class Database:
    def __init__(self, db_path): self.db_path = db_path
    async def execute(self, sql, params=(), fetch=False):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(sql, params)
            if fetch: return await cursor.fetchall()
            await db.commit()

db = Database('bot_system_v_pythontag.db')

async def init_db():
    await db.execute('CREATE TABLE IF NOT EXISTS shop_groups (id INTEGER PRIMARY KEY, link TEXT, price TEXT, admin TEXT)')
    await db.execute('CREATE TABLE IF NOT EXISTS shop_users (user_id INTEGER PRIMARY KEY, name TEXT)')
    await db.execute('CREATE TABLE IF NOT EXISTS test_users (user_id INTEGER PRIMARY KEY, name TEXT)')
    await db.execute('CREATE TABLE IF NOT EXISTS words (id INTEGER PRIMARY KEY, user_id INTEGER, word TEXT, UNIQUE(user_id, word))')
    await db.execute('CREATE TABLE IF NOT EXISTS tests (id INTEGER PRIMARY KEY AUTOINCREMENT, q TEXT, v1 TEXT, v2 TEXT, v3 TEXT)')
    await db.execute('CREATE TABLE IF NOT EXISTS solved (user_id INTEGER, test_id INTEGER, UNIQUE(user_id, test_id))')

# --- 4. STATES ---
class ShopStates(StatesGroup): link = State(); price = State(); bc = State()
class AdminStates(StatesGroup): choosing_type = State(); bc_message = State(); q=State(); v1=State(); v2=State(); v3=State()
class WordStates(StatesGroup): main = State()

# --- 5. KEYBOARDS ---
def main_kb_t(user_id):
    kb = [[KeyboardButton(text="Test yechish 📝"), KeyboardButton(text="So'zlar ombori 📚")]]
    if user_id in ADMIN_LIST:
        kb.append([KeyboardButton(text="📢 Rassilka"), KeyboardButton(text="📊 Statistika")])
        kb.append([KeyboardButton(text="➕ Test qo'shish"), KeyboardButton(text="🗑 Test o'chirish")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# ==========================================
#         TEST BOT HANDLERLARI
# ==========================================
@dp_t.message(Command("start"))
async def test_start(m: types.Message, state: FSMContext):
    await state.clear()
    if not await check_sub(m.from_user.id, bot_t):
        return await m.answer(f"🚀 Botdan foydalanish uchun {REQUIRED_CHANNEL} kanaliga a'zo bo'ling!", reply_markup=sub_kb())
    
    await db.execute("INSERT OR IGNORE INTO test_users (user_id, name) VALUES (?, ?)", (m.from_user.id, m.from_user.full_name))
    await m.answer("Bilim botiga xush kelibsiz!", reply_markup=main_kb_t(m.from_user.id))

@dp_t.callback_query(F.data == "check_sub")
async def check_sub_btn(c: types.CallbackQuery):
    if await check_sub(c.from_user.id, bot_t):
        await c.message.delete()
        await c.message.answer("Rahmat! Endi foydalanishingiz mumkin.", reply_markup=main_kb_t(c.from_user.id))
    else:
        await c.answer("Siz hali kanalga a'zo emassiz! ❌", show_alert=True)

@dp_t.message(F.text == "Test yechish 📝")
async def take_test(m: types.Message):
    if not await check_sub(m.from_user.id, bot_t):
        return await m.answer("Iltimos, avval kanalga obuna bo'ling!", reply_markup=sub_kb())
    
    tests = await db.execute("SELECT * FROM tests WHERE id NOT IN (SELECT test_id FROM solved WHERE user_id=?)", (m.from_user.id,), fetch=True)
    if not tests: return await m.answer("🎉 Hamma testlar yechildi!")
    t = random.choice(tests)
    opts = [t['v1'], t['v2'], t['v3']]; correct = t['v3']; random.shuffle(opts)
    await m.answer_poll(question=t['q'], options=opts, type='quiz', correct_option_id=opts.index(correct), is_anonymous=False)

# --- SO'ZLAR OMBORI ---
@dp_t.message(F.text == "So'zlar ombori 📚")
async def word_menu(m: types.Message, state: FSMContext):
    if not await check_sub(m.from_user.id, bot_t): return await m.answer("Obuna bo'ling!", reply_markup=sub_kb())
    await state.set_state(WordStates.main)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Umumiy so'zlar soni")], [KeyboardButton(text="🔙 Orqaga")]], resize_keyboard=True)
    await m.answer("So'zlarni yozing, men saqlayman.", reply_markup=kb)

@dp_t.message(WordStates.main, F.text == "🔙 Orqaga")
async def back_t(m: types.Message, state: FSMContext):
    await state.clear(); await m.answer("Asosiy menyu", reply_markup=main_kb_t(m.from_user.id))

@dp_t.message(WordStates.main, F.text)
async def save_w(m: types.Message):
    if m.text in RESERVED_BUTTONS: return
    for w in m.text.split("\n"):
        if w.strip(): await db.execute("INSERT OR IGNORE INTO words (user_id, word) VALUES (?, ?)", (m.from_user.id, w.strip()))
    await m.answer("✅ Saqlandi.")

# --- SHOP BOT HANDLERLARI ---
@dp_s.message(Command("start"))
async def s_st(m: types.Message):
    if not await check_sub(m.from_user.id, bot_s):
        return await m.answer(f"Obuna bo'ling: {REQUIRED_CHANNEL}", reply_markup=sub_kb())
    kb = [[KeyboardButton(text="🛒 Guruhlar")]]
    if m.from_user.id in ADMIN_LIST: kb.append([KeyboardButton(text="➕ Guruh qo'shish")])
    await m.answer("Shop bot ishga tushdi!", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp_s.message(F.text == "🛒 Guruhlar")
async def show_g(m: types.Message):
    groups = await db.execute("SELECT * FROM shop_groups", fetch=True)
    txt = "Guruhlar:\n\n"
    for g in groups: txt += f"📢 {g['link']}\n💰 {g['price']}\n\n"
    await m.answer(txt)

# --- ADMIN FUNKSIYALARI ---
@dp_t.message(F.text == "📊 Statistika", IsAdmin())
async def stats(m: types.Message):
    u = await db.execute("SELECT COUNT(*) as c FROM test_users", fetch=True)
    await m.answer(f"Jami foydalanuvchilar: {u[0]['c']} ta")

@dp_t.message(F.text == "➕ Test qo'shish", IsAdmin())
async def add_test(m: types.Message, state: FSMContext):
    await m.answer("Savolni yuboring:"); await state.set_state(AdminStates.q)

@dp_t.message(AdminStates.q)
async def q_get(m: types.Message, state: FSMContext):
    await state.update_data(q=m.text); await m.answer("1-xato javob:"); await state.set_state(AdminStates.v1)

@dp_t.message(AdminStates.v1)
async def v1_get(m: types.Message, state: FSMContext):
    await state.update_data(v1=m.text); await m.answer("2-xato javob:"); await state.set_state(AdminStates.v2)

@dp_t.message(AdminStates.v2)
async def v2_get(m: types.Message, state: FSMContext):
    await state.update_data(v2=m.text); await m.answer("To'g'ri javob:"); await state.set_state(AdminStates.v3)

@dp_t.message(AdminStates.v3)
async def v3_get(m: types.Message, state: FSMContext):
    d = await state.get_data()
    await db.execute("INSERT INTO tests (q, v1, v2, v3) VALUES (?, ?, ?, ?)", (d['q'], d['v1'], d['v2'], m.text))
    await m.answer("✅ Test qo'shildi!"); await state.clear()

# --- ISHGA TUSHIRISH ---
async def main():
    await init_db()
    print("Botlar @pythontagbot kanali bilan ishlamoqda!")
    await asyncio.gather(dp_s.start_polling(bot_s), dp_t.start_polling(bot_t))

if __name__ == '__main__':
    asyncio.run(main())