import os, logging, asyncio, random, aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# --- SOZLAMALAR ---
TOKEN_SHOP = '8737514748:AAEeJwwzVf6e0yzYlwXRT8N0UrvsULGCapI'
TOKEN_TEST = '8750077178:AAFgDf_LDL11-cYvg_KGZUboTnkH-oWPFak'
ADMIN_LIST = [8213426436, 8562020437]

bot_s, bot_t = Bot(token=TOKEN_SHOP), Bot(token=TOKEN_TEST)
dp_s, dp_t = Dispatcher(storage=MemoryStorage()), Dispatcher(storage=MemoryStorage())

# --- DATABASE VA ADMIN FILTR (O'zgarishsiz) ---
class IsAdmin(BaseFilter):
    async def __call__(self, m: types.Message) -> bool:
        return m.from_user.id in ADMIN_LIST

class Database:
    def __init__(self, db_path): self.db_path = db_path
    async def execute(self, sql, params=(), fetch=False):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(sql, params)
            if fetch: return await cursor.fetchall()
            await db.commit()

db = Database('bot_system_v16.db')

async def init_db():
    async with aiosqlite.connect(db.db_path) as _db:
        await _db.execute('PRAGMA journal_mode=WAL;')
    await db.execute('CREATE TABLE IF NOT EXISTS shop_groups (id INTEGER PRIMARY KEY, link TEXT, price TEXT, admin TEXT)')
    await db.execute('CREATE TABLE IF NOT EXISTS shop_users (user_id INTEGER PRIMARY KEY)')
    await db.execute('CREATE TABLE IF NOT EXISTS test_users (user_id INTEGER PRIMARY KEY, name TEXT)')
    await db.execute('CREATE TABLE IF NOT EXISTS words (id INTEGER PRIMARY KEY, user_id INTEGER, word TEXT, UNIQUE(user_id, word))')
    await db.execute('CREATE TABLE IF NOT EXISTS tests (id INTEGER PRIMARY KEY AUTOINCREMENT, q TEXT, v1 TEXT, v2 TEXT, v3 TEXT)')
    await db.execute('CREATE TABLE IF NOT EXISTS solved (user_id INTEGER, test_id INTEGER, UNIQUE(user_id, test_id))')

# --- STATES ---
class ShopStates(StatesGroup): link = State(); price = State(); bc = State()
class AdminStates(StatesGroup):
    choosing_type = State(); bc_message = State(); bc_test = State()
    q=State(); v1=State(); v2=State(); v3=State(); del_t=State()
class WordStates(StatesGroup): main = State(); deleting = State()

# --- KEYBOARDS ---
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

# --- MUHIM: TEST YECHISH MANTIQI (YANGILANGAN) ---
active_tests = {} # Qaysi userga qaysi test yuborilganini eslab qolish uchun

@dp_t.message(F.text == "Test yechish 📝")
async def take_test(m: types.Message):
    tests = await db.execute("SELECT * FROM tests WHERE id NOT IN (SELECT test_id FROM solved WHERE user_id=?)", (m.from_user.id,), fetch=True)
    if not tests: return await m.answer("🎉 Hamma testlar tugadi!")
    
    t = random.choice(tests)
    opts = [t['v1'], t['v2'], t['v3']]; correct = t['v3']; random.shuffle(opts)
    
    sent_poll = await m.answer_poll(
        question=t['q'], 
        options=opts, 
        type='quiz', 
        correct_option_id=opts.index(correct), 
        is_anonymous=False
    )
    
    # User va test ma'lumotlarini vaqtinchalik saqlaymiz
    active_tests[sent_poll.poll.id] = {"user_id": m.from_user.id, "test_id": t['id'], "correct_id": opts.index(correct)}

@dp_t.poll_answer()
async def handle_poll_answer(quiz: types.PollAnswer):
    data = active_tests.get(quiz.poll_id)
    if not data: return
    
    # Agar javob to'g'ri bo'lsa, bazaga "yechildi" deb saqlaymiz
    if quiz.option_ids[0] == data['correct_id']:
        await db.execute("INSERT OR IGNORE INTO solved (user_id, test_id) VALUES (?, ?)", (data['user_id'], data['test_id']))
        
        # Hamma test tugaganini tekshirish
        rem = await db.execute("SELECT id FROM tests WHERE id NOT IN (SELECT test_id FROM solved WHERE user_id=?)", (data['user_id'],), fetch=True)
        if not rem:
            await bot_t.send_message(data['user_id'], "🎊 Tabriklayman! Barcha testlarni to'g'ri yechib bo'ldingiz! ✅")
    
    # Javob berilgach, lug'atdan o'chirib tashlaymiz
    active_tests.pop(quiz.poll_id, None)
    
    # AVTOMATIK KEYINGI TESTGA O'TISH
    await asyncio.sleep(3.0)
    fake_msg = types.Message(message_id=0, date=None, chat=types.Chat(id=data['user_id'], type="private"), from_user=types.User(id=data['user_id'], is_bot=False, first_name="User"), text="Test yechish 📝")
    await take_test(fake_msg)

# --- QOLGAN BARCHA HANDLERLAR (O'zgarishsiz) ---
@dp_s.message(Command("start"))
async def shop_start(m: types.Message):
    await db.execute("INSERT OR IGNORE INTO shop_users (user_id) VALUES (?)", (m.from_user.id,))
    kb = [[KeyboardButton(text="🛒 Guruhlar")]]
    if m.from_user.id in ADMIN_LIST: kb.append([KeyboardButton(text="📢 Rassilka"), KeyboardButton(text="➕ Guruh qo'shish")])
    await m.answer("Sotuv botiga xush kelibsiz!", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp_s.message(F.text == "🛒 Guruhlar")
async def show_shop_groups(m: types.Message):
    groups = await db.execute("SELECT link, price, admin FROM shop_groups", fetch=True)
    if not groups: return await m.answer("Hozircha guruhlar yo'q.")
    txt = "<b>🚀 Sotuvdagi guruhlar:</b>\n\n"
    for g in groups: txt += f"📢 {g['link']}\n💰 Narxi: {g['price']}\n👤 Admin: {g['admin']}\n\n"
    await m.answer(txt, parse_mode="HTML", disable_web_page_preview=True)

@dp_t.message(Command("start"))
async def test_start(m: types.Message, state: FSMContext):
    await state.clear()
    await db.execute("INSERT OR IGNORE INTO test_users (user_id, name) VALUES (?, ?)", (m.from_user.id, m.from_user.full_name))
    await m.answer("Bilim botiga xush kelibsiz!", reply_markup=main_kb_t(m.from_user.id))

@dp_t.message(F.text == "So'zlar ombori 📚")
async def word_storage_main(m: types.Message, state: FSMContext):
    await state.set_state(WordStates.main)
    await m.answer("📚 So'zlar ombori!", reply_markup=word_menu_kb)

@dp_t.message(F.text == "🔙 Orqaga")
async def back_universal(m: types.Message, state: FSMContext):
    await state.clear(); await m.answer("Asosiy menyu", reply_markup=main_kb_t(m.from_user.id))

@dp_t.message(WordStates.main, F.text == "Umumiy so'zlar soni")
async def word_count(m: types.Message):
    count = await db.execute("SELECT COUNT(*) as c FROM words WHERE user_id=?", (m.from_user.id,), fetch=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👁 Ko'rish", callback_data="view_0")]])
    await m.answer(f"Sizda {count[0]['c']} ta so'z bor.", reply_markup=kb)

@dp_t.message(WordStates.main, F.text)
async def auto_save(m: types.Message):
    if m.text in ["Umumiy so'zlar soni", "Kerakli so'zni o'chirish"]: return
    a, d = 0, 0
    for w in m.text.split("\n"):
        c_w = w.strip()
        if c_w:
            chk = await db.execute("SELECT id FROM words WHERE user_id=? AND word=?", (m.from_user.id, c_w), fetch=True)
            if chk: d += 1
            else: await db.execute("INSERT INTO words (user_id, word) VALUES (?, ?)", (m.from_user.id, c_w)); a += 1
    res = await m.answer(f"✅ {a} ta qo'shildi. ⚠️ {d} ta bor."); await asyncio.sleep(3)
    try: await res.delete(); await m.delete()
    except: pass

@dp_t.message(F.text == "📊 Statistika", IsAdmin())
async def stats(m: types.Message):
    u = await db.execute("SELECT COUNT(*) as c FROM test_users", fetch=True)
    t = await db.execute("SELECT COUNT(*) as c FROM tests", fetch=True)
    await m.answer(f"Userlar: {u[0]['c']}\nTestlar: {t[0]['c']}")

async def main():
    await init_db()
    print("SISTEMA 100/100 ISHLAYAPTI!")
    await asyncio.gather(dp_s.start_polling(bot_s), dp_t.start_polling(bot_t))

if __name__ == '__main__':
    asyncio.run(main())