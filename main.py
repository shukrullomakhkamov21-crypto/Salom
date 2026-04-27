import os, logging, asyncio, random, aiosqlite, aiocron
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- 1. SOZLAMALAR (TOKENLAR KOD ICHIDA) ---
TOKEN_SHOP = '8737514748:AAEeJwwzVf6e0yzYlwXRT8N0UrvsULGCapI'
TOKEN_TEST = '8750077178:AAFgDf_LDL11-cYvg_KGZUboTnkH-oWPFak'
ADMIN_LIST = [8213426436, 8562020437]

bot_s, bot_t = Bot(token=TOKEN_SHOP), Bot(token=TOKEN_TEST)
dp_s, dp_t = Dispatcher(storage=MemoryStorage()), Dispatcher(storage=MemoryStorage())

RESERVED_BUTTONS = [
    "Test yechish 📝", "So'zlar ombori 📚", "📢 Rassilka", "📊 Statistika", 
    "➕ Test qo'shish", "🗑 Test o'chirish", "Umumiy so'zlar soni", 
    "Kerakli so'zni o'chirish", "🔙 Orqaga", "🛒 Guruhlar", "➕ Guruh qo'shish"
]

class IsAdmin(BaseFilter):
    async def __call__(self, m: types.Message) -> bool:
        return m.from_user.id in ADMIN_LIST

# --- 2. DATABASE (YANGI NOM BILAN) ---
class Database:
    def __init__(self, db_path): self.db_path = db_path
    async def execute(self, sql, params=(), fetch=False):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(sql, params)
            if fetch: return await cursor.fetchall()
            await db.commit()

db = Database('cleansystem_v1.db')

async def init_db():
    async with aiosqlite.connect(db.db_path) as _db:
        await _db.execute('PRAGMA journal_mode=WAL;')
    await db.execute('CREATE TABLE IF NOT EXISTS shop_groups (id INTEGER PRIMARY KEY, link TEXT, price TEXT, admin TEXT)')
    await db.execute('CREATE TABLE IF NOT EXISTS shop_users (user_id INTEGER PRIMARY KEY, name TEXT)')
    await db.execute('CREATE TABLE IF NOT EXISTS test_users (user_id INTEGER PRIMARY KEY, name TEXT)')
    await db.execute('CREATE TABLE IF NOT EXISTS words (id INTEGER PRIMARY KEY, user_id INTEGER, word TEXT, UNIQUE(user_id, word))')
    await db.execute('CREATE TABLE IF NOT EXISTS tests (id INTEGER PRIMARY KEY AUTOINCREMENT, q TEXT, v1 TEXT, v2 TEXT, v3 TEXT)')
    await db.execute('CREATE TABLE IF NOT EXISTS solved (user_id INTEGER, test_id INTEGER, UNIQUE(user_id, test_id))')

# --- 3. STATES ---
class ShopStates(StatesGroup): link = State(); price = State(); bc = State()
class AdminStates(StatesGroup):
    choosing_type = State(); bc_message = State()
    bc_q = State(); bc_v1 = State(); bc_v2 = State(); bc_v3 = State()
    q=State(); v1=State(); v2=State(); v3=State()
class WordStates(StatesGroup): main = State()

# --- 4. KEYBOARDS ---
def main_kb_t(user_id):
    kb = [[KeyboardButton(text="Test yechish 📝"), KeyboardButton(text="So'zlar ombori 📚")]]
    if user_id in ADMIN_LIST:
        kb.append([KeyboardButton(text="📢 Rassilka"), KeyboardButton(text="📊 Statistika")])
        kb.append([KeyboardButton(text="➕ Test qo'shish"), KeyboardButton(text="🗑 Test o'chirish")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

word_menu_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="Umumiy so'zlar soni"), KeyboardButton(text="Kerakli so'zni o'chirish")],
    [KeyboardButton(text="🔙 Orqaga")]
], resize_keyboard=True)

# --- TEST BOT HANDLERLARI ---
active_tests = {}

@dp_t.message(Command("start"))
async def test_start(m: types.Message, state: FSMContext):
    await state.clear()
    await db.execute("INSERT OR IGNORE INTO test_users (user_id, name) VALUES (?, ?)", (m.from_user.id, m.from_user.full_name))
    await m.answer("Bilim botiga xush kelibsiz!", reply_markup=main_kb_t(m.from_user.id))

@dp_t.message(F.text == "🔙 Orqaga")
async def back_universal(m: types.Message, state: FSMContext):
    await state.clear(); await m.answer("Asosiy menyu", reply_markup=main_kb_t(m.from_user.id))

@dp_t.message(F.text == "Test yechish 📝")
async def take_test(m: types.Message):
    tests = await db.execute("SELECT * FROM tests WHERE id NOT IN (SELECT test_id FROM solved WHERE user_id=?)", (m.from_user.id,), fetch=True)
    if not tests: return await m.answer("🎉 Siz hamma testlarni echib bo'ldingiz tabriklayman!")
    t = random.choice(tests)
    opts = [t['v1'], t['v2'], t['v3']]; correct = t['v3']; random.shuffle(opts)
    sent_poll = await m.answer_poll(question=t['q'], options=opts, type='quiz', correct_option_id=opts.index(correct), is_anonymous=False)
    active_tests[sent_poll.poll.id] = {"user_id": m.from_user.id, "test_id": t['id'], "correct_id": opts.index(correct)}

@dp_t.poll_answer()
async def handle_poll_answer(quiz: types.PollAnswer):
    data = active_tests.get(quiz.poll_id)
    if data:
        if quiz.option_ids[0] == data['correct_id']:
            await db.execute("INSERT OR IGNORE INTO solved (user_id, test_id) VALUES (?, ?)", (data['user_id'], data['test_id']))
        active_tests.pop(quiz.poll_id, None)

@dp_t.message(F.text == "So'zlar ombori 📚")
async def word_menu(m: types.Message, state: FSMContext):
    await state.set_state(WordStates.main)
    await m.answer("So'zlarni yuboring, men eslab qolaman", reply_markup=word_menu_kb)

@dp_t.message(WordStates.main, F.text == "Umumiy so'zlar soni")
async def w_cnt(m: types.Message):
    c = await db.execute("SELECT COUNT(*) as c FROM words WHERE user_id=?", (m.from_user.id,), fetch=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="So'zlarni ko'rish", callback_data="show_my_words")]])
    await m.answer(f"So'zlaringiz soni: {c[0]['c']} ta", reply_markup=kb)

@dp_t.callback_query(F.data == "show_my_words")
async def show_words_cb(c: types.CallbackQuery):
    words = await db.execute("SELECT word FROM words WHERE user_id=?", (c.from_user.id,), fetch=True)
    if not words: return await c.answer("Hali so'zlar yo'q")
    txt = "📚 **Sizning so'zlaringiz:**\n\n" + "\n".join([f"• {w['word']}" for w in words])
    await c.message.answer(txt); await c.answer()

@dp_t.message(WordStates.main, F.text == "Kerakli so'zni o'chirish")
async def del_word_start(m: types.Message):
    words = await db.execute("SELECT id, word FROM words WHERE user_id=?", (m.from_user.id,), fetch=True)
    if not words: return await m.answer("O'chirishga so'z yo'q.")
    builder = InlineKeyboardBuilder()
    for w in words: builder.button(text=w['word'], callback_data=f"dw_{w['id']}")
    builder.adjust(2)
    await m.answer("O'chirmoqchi bo'lgan so'zingizni tanlang:", reply_markup=builder.as_markup())

@dp_t.callback_query(F.data.startswith("dw_"))
async def del_word_process(c: types.CallbackQuery):
    await db.execute("DELETE FROM words WHERE id=?", (c.data.split("_")[1],))
    await c.message.edit_text("🗑 So'z o'chirildi."); await c.answer()

@dp_t.message(WordStates.main, F.text)
async def auto_save(m: types.Message):
    if m.text in RESERVED_BUTTONS: return
    for word in m.text.split("\n"):
        if word.strip(): await db.execute("INSERT OR IGNORE INTO words (user_id, word) VALUES (?, ?)", (m.from_user.id, word.strip()))
    await m.answer("✅ Saqlandi.")

# --- SHOP BOT HANDLERLARI ---
@dp_s.message(Command("start"))
async def s_st(m: types.Message):
    await db.execute("INSERT OR IGNORE INTO shop_users (user_id, name) VALUES (?, ?)", (m.from_user.id, m.from_user.full_name))
    kb = [[KeyboardButton(text="🛒 Guruhlar")]]
    if m.from_user.id in ADMIN_LIST: kb.append([KeyboardButton(text="📢 Rassilka"), KeyboardButton(text="➕ Guruh qo'shish")])
    await m.answer("Shop Bot tayyor!", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp_s.message(F.text == "🛒 Guruhlar")
async def show_g(m: types.Message):
    groups = await db.execute("SELECT link, price, admin FROM shop_groups", fetch=True)
    txt = "<b>Guruhlar:</b>\n\n"
    for g in groups: txt += f"📢 {g['link']}\n💰 {g['price']}\n👤 {g['admin']}\n\n"
    await m.answer(txt, parse_mode="HTML")

# --- MAIN ---
async def main():
    await init_db()
    print("REKLAMASIZ TOZA BOT YONDI!")
    await asyncio.gather(dp_s.start_polling(bot_s), dp_t.start_polling(bot_t))

if __name__ == '__main__':
    asyncio.run(main())