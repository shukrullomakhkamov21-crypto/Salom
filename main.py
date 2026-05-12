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
REQUIRED_CHANNEL = "@pythontagbot"

bot_s, bot_t = Bot(token=TOKEN_SHOP), Bot(token=TOKEN_TEST)
dp_s, dp_t = Dispatcher(storage=MemoryStorage()), Dispatcher(storage=MemoryStorage())

RESERVED_BUTTONS = ["Test yechish 📝", "So'zlar ombori 📚", "📢 Rassilka", "📊 Statistika", "➕ Test qo'shish", "🗑 Test o'chirish", "Umumiy so'zlar soni", "Kerakli so'zni o'chirish", "🔙 Orqaga", "🛒 Guruhlar", "➕ Guruh qo'shish"]

user_current_test = {} # Poll IDlarini kuzatish uchun

class IsAdmin(BaseFilter):
    async def __call__(self, m: types.Message) -> bool:
        return m.from_user.id in ADMIN_LIST

# --- 2. DATABASE ---
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
    await db.execute('CREATE TABLE IF NOT EXISTS test_users (user_id INTEGER PRIMARY KEY, name TEXT)')
    await db.execute('CREATE TABLE IF NOT EXISTS words (id INTEGER PRIMARY KEY, user_id INTEGER, word TEXT, UNIQUE(user_id, word))')
    await db.execute('CREATE TABLE IF NOT EXISTS tests (id INTEGER PRIMARY KEY AUTOINCREMENT, q TEXT, v1 TEXT, v2 TEXT, v3 TEXT)')
    await db.execute('CREATE TABLE IF NOT EXISTS solved (user_id INTEGER, test_id INTEGER, UNIQUE(user_id, test_id))')

# --- 3. STATES ---
class AdminStates(StatesGroup): bc_message = State(); q=State(); v1=State(); v2=State(); v3=State()
class WordStates(StatesGroup): main = State()

# --- 4. KEYBOARDS ---
def main_kb_t(user_id):
    kb = [[KeyboardButton(text="Test yechish 📝"), KeyboardButton(text="So'zlar ombori 📚")]]
    if user_id in ADMIN_LIST:
        kb.append([KeyboardButton(text="📢 Rassilka"), KeyboardButton(text="📊 Statistika")])
        kb.append([KeyboardButton(text="➕ Test qo'shish"), KeyboardButton(text="🗑 Test o'chirish")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

async def check_sub(user_id: int, bot: Bot):
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        return member.status in ["creator", "administrator", "member"]
    except: return False

def sub_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Kanalga obuna bo'lish 🚀", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}")],
        [InlineKeyboardButton(text="Tekshirish ✅", callback_data="check_sub")]
    ])

# ==========================================
#         TEST BOT HANDLERLARI
# ==========================================

@dp_t.message(Command("start"))
async def test_start(m: types.Message, state: FSMContext):
    await state.clear()
    if not await check_sub(m.from_user.id, bot_t):
        return await m.answer(f"🚀 Botdan foydalanish uchun {REQUIRED_CHANNEL} каналга аъзо бўлинг!", reply_markup=sub_kb())
    await db.execute("INSERT OR IGNORE INTO test_users (user_id, name) VALUES (?, ?)", (m.from_user.id, m.from_user.full_name))
    await m.answer("Билим ботига хуш келибсиз!", reply_markup=main_kb_t(m.from_user.id))

@dp_t.message(F.text == "Test yechish 📝")
async def take_test(m: types.Message):
    tests = await db.execute("SELECT * FROM tests WHERE id NOT IN (SELECT test_id FROM solved WHERE user_id=?)", (m.from_user.id,), fetch=True)
    if not tests: return await m.answer("🎉 Ҳамма тестлар ечилди!")
    t = random.choice(tests)
    opts = [t['v1'], t['v2'], t['v3']]; correct = t['v3']; random.shuffle(opts)
    poll = await m.answer_poll(question=t['q'], options=opts, type='quiz', correct_option_id=opts.index(correct), is_anonymous=False)
    user_current_test[m.from_user.id] = t['id']

@dp_t.poll_answer()
async def handle_poll_answer(quiz: types.PollAnswer):
    t_id = user_current_test.get(quiz.user_id)
    if t_id:
        await db.execute("INSERT OR IGNORE INTO solved (user_id, test_id) VALUES (?, ?)", (quiz.user_id, t_id))

# --- SO'ZLAR OMBORI (Excel "Magic" bilan) ---
@dp_t.message(F.text == "So'zlar ombori 📚")
async def word_menu(m: types.Message, state: FSMContext):
    await state.set_state(WordStates.main)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Umumiy so'zlar soni")], [KeyboardButton(text="🔙 Orqaga")]], resize_keyboard=True)
    await m.answer("Сўзларни ёзинг ёки диапазон юборинг (м-н: 1..50)", reply_markup=kb)

@dp_t.message(WordStates.main, F.text == "Umumiy so'zlar soni")
async def word_count(m: types.Message):
    res = await db.execute("SELECT COUNT(*) as c FROM words WHERE user_id=?", (m.from_user.id,), fetch=True)
    await m.answer(f"Сизда жами {res[0]['c']} та сўз сақланган.")

@dp_t.message(WordStates.main, F.text)
async def save_words_magic(m: types.Message):
    if m.text in RESERVED_BUTTONS: return
    words = []
    if ".." in m.text: # Magic Auto-fill
        try:
            s, e = map(int, m.text.split(".."))
            words = [str(i) for i in range(s, e + 1)]
        except: words = m.text.split("\n")
    else: words = m.text.split("\n")
    
    for w in words:
        if w.strip(): await db.execute("INSERT OR IGNORE INTO words (user_id, word) VALUES (?, ?)", (m.from_user.id, w.strip()))
    await m.answer(f"✅ {len(words)} та элемент қўшилди.")

# --- ADMIN FUNCTIONS ---
@dp_t.message(F.text == "📢 Rassilka", IsAdmin())
async def bc_start(m: types.Message, state: FSMContext):
    await m.answer("Реклама юборинг:"); await state.set_state(AdminStates.bc_message)

@dp_t.message(AdminStates.bc_message, IsAdmin())
async def bc_send(m: types.Message, state: FSMContext):
    users = await db.execute("SELECT user_id FROM test_users", fetch=True)
    for u in users:
        try: await m.copy_to(u['user_id'])
        except: continue
    await m.answer("Тайёр!"); await state.clear()

@dp_t.message(F.text == "🗑 Test o'chirish", IsAdmin())
async def del_test_menu(m: types.Message):
    ts = await db.execute("SELECT id, q FROM tests ORDER BY id DESC LIMIT 10", fetch=True)
    kb = InlineKeyboardBuilder()
    for t in ts: kb.button(text=f"ID: {t['id']}", callback_data=f"del_{t['id']}")
    await m.answer("Ўчириш учун ID танланг:", reply_markup=kb.as_markup())

@dp_t.callback_query(F.data.startswith("del_"))
async def del_test_proc(c: types.CallbackQuery):
    await db.execute("DELETE FROM tests WHERE id=?", (c.data.split("_")[1],))
    await c.answer("Ўчирилди!"); await c.message.delete()

# --- 5. RUN ---
async def main():
    await init_db()
    print("Ботлар ишга тушди...")
    await asyncio.gather(dp_s.start_polling(bot_s), dp_t.start_polling(bot_t))

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())