import os, logging, asyncio, random, aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# --- 1. SOZLAMALAR ---
TOKEN_SHOP = '8737514748:AAEeJwwzVf6e0yzYlwXRT8N0UrvsULGCapI'
TOKEN_TEST = '8750077178:AAFgDf_LDL11-cYvg_KGZUboTnkH-oWPFak'
ADMIN_LIST = [8213426436, 8562020437]

bot_s, bot_t = Bot(token=TOKEN_SHOP), Bot(token=TOKEN_TEST)
dp_s, dp_t = Dispatcher(storage=MemoryStorage()), Dispatcher(storage=MemoryStorage())

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

db = Database('bot_system_v_final_secure.db')

async def init_db():
    async with aiosqlite.connect(db.db_path) as _db:
        await _db.execute('PRAGMA journal_mode=WAL;')
    await db.execute('CREATE TABLE IF NOT EXISTS shop_groups (id INTEGER PRIMARY KEY, link TEXT, price TEXT, admin TEXT)')
    await db.execute('CREATE TABLE IF NOT EXISTS shop_users (user_id INTEGER PRIMARY KEY)')
    await db.execute('CREATE TABLE IF NOT EXISTS test_users (user_id INTEGER PRIMARY KEY, name TEXT)')
    await db.execute('CREATE TABLE IF NOT EXISTS words (id INTEGER PRIMARY KEY, user_id INTEGER, word TEXT, UNIQUE(user_id, word))')
    await db.execute('CREATE TABLE IF NOT EXISTS tests (id INTEGER PRIMARY KEY AUTOINCREMENT, q TEXT, v1 TEXT, v2 TEXT, v3 TEXT)')
    await db.execute('CREATE TABLE IF NOT EXISTS solved (user_id INTEGER, test_id INTEGER, UNIQUE(user_id, test_id))')

# --- 3. STATES ---
class ShopStates(StatesGroup): link = State(); price = State(); bc = State()
class AdminStates(StatesGroup):
    choosing_type = State(); bc_message = State()
    bc_q = State(); bc_v1 = State(); bc_v2 = State(); bc_v3 = State() # Rassilka testi uchun
    q=State(); v1=State(); v2=State(); v3=State(); del_t=State()
class WordStates(StatesGroup): main = State(); deleting = State()

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

# ==========================================
#         TEST BOT HANDLERLARI
# ==========================================
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
    if not tests: return await m.answer("🎉 Hamma testlar tugadi!")
    t = random.choice(tests)
    opts = [t['v1'], t['v2'], t['v3']]; correct = t['v3']; random.shuffle(opts)
    sent_poll = await m.answer_poll(question=t['q'], options=opts, type='quiz', correct_option_id=opts.index(correct), is_anonymous=False)
    active_tests[sent_poll.poll.id] = {"user_id": m.from_user.id, "test_id": t['id'], "correct_id": opts.index(correct)}

@dp_t.poll_answer()
async def handle_poll_answer(quiz: types.PollAnswer):
    data = active_tests.get(quiz.poll_id)
    if not data: return
    if quiz.option_ids[0] == data['correct_id']:
        await db.execute("INSERT OR IGNORE INTO solved (user_id, test_id) VALUES (?, ?)", (data['user_id'], data['test_id']))
    active_tests.pop(quiz.poll_id, None)
    await asyncio.sleep(1.5)
    fake_msg = types.Message(message_id=0, date=None, chat=types.Chat(id=data['user_id'], type="private"), from_user=types.User(id=data['user_id'], is_bot=False, first_name="User"), text="Test yechish 📝")
    await take_test(fake_msg)

# --- [MUHIM] RASSILKA TESTINI TO'G'RILASH ---
@dp_t.message(F.text == "📢 Rassilka", IsAdmin())
async def t_bc_choice(m: types.Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📝 Oddiy xabar", callback_data="bt_msg"), InlineKeyboardButton(text="🗳 Test", callback_data="bt_poll")]])
    await m.answer("Test botda nimani tarqatamiz?", reply_markup=kb)
    await state.set_state(AdminStates.choosing_type)

@dp_t.callback_query(AdminStates.choosing_type, F.data.startswith("bt_"))
async def t_bc_st(c: types.CallbackQuery, state: FSMContext):
    if c.data == "bt_msg":
        await c.message.answer("Xabar matnini yuboring:"); await state.set_state(AdminStates.bc_message)
    else:
        await c.message.answer("Rassilka testi uchun SAVOLNI yuboring:"); await state.set_state(AdminStates.bc_q)
    await c.answer()

# Rassilka testi qadamlari (Test qo'shish bilan bir xil mantiq)
@dp_t.message(AdminStates.bc_q)
async def t_bc_q(m: types.Message, state: FSMContext):
    await state.update_data(q=m.text); await m.answer("1-xato variant:"); await state.set_state(AdminStates.bc_v1)

@dp_t.message(AdminStates.bc_v1)
async def t_bc_v1(m: types.Message, state: FSMContext):
    await state.update_data(v1=m.text); await m.answer("2-xato variant:"); await state.set_state(AdminStates.bc_v2)

@dp_t.message(AdminStates.bc_v2)
async def t_bc_v2(m: types.Message, state: FSMContext):
    await state.update_data(v2=m.text); await m.answer("To'g'ri variant:"); await state.set_state(AdminStates.bc_v3)

@dp_t.message(AdminStates.bc_v3)
async def t_bc_v3(m: types.Message, state: FSMContext):
    d = await state.get_data(); correct = m.text
    opts = [d['v1'], d['v2'], correct]; random.shuffle(opts)
    correct_idx = opts.index(correct)
    users = await db.execute("SELECT user_id FROM test_users", fetch=True)
    c = 0
    for u in users:
        try:
            await bot_t.send_poll(chat_id=u['user_id'], question=d['q'], options=opts, type='quiz', correct_option_id=correct_idx, is_anonymous=False)
            c += 1; await asyncio.sleep(0.05)
        except: continue
    await m.answer(f"✅ Test {c} ta foydalanuvchiga yuborildi!"); await state.clear()

@dp_t.message(AdminStates.bc_message)
async def t_bc_m_send(m: types.Message, state: FSMContext):
    users = await db.execute("SELECT user_id FROM test_users", fetch=True)
    c = 0
    for u in users:
        try: await m.copy_to(u['user_id']); c += 1; await asyncio.sleep(0.05)
        except: continue
    await m.answer(f"✅ {c} ta xabar yuborildi."); await state.clear()

# --- QOLGAN BARCHA FUNKSIYALAR TEGILMADI ---
@dp_t.message(F.text == "➕ Test qo'shish", IsAdmin())
async def add_t_st(m: types.Message, state: FSMContext):
    await m.answer("Savol matnini yuboring:"); await state.set_state(AdminStates.q)

@dp_t.message(AdminStates.q)
async def add_t_q(m: types.Message, state: FSMContext):
    await state.update_data(q=m.text); await m.answer("1-xato variant:"); await state.set_state(AdminStates.v1)

@dp_t.message(AdminStates.v1)
async def add_t_v1(m: types.Message, state: FSMContext):
    await state.update_data(v1=m.text); await m.answer("2-xato variant:"); await state.set_state(AdminStates.v2)

@dp_t.message(AdminStates.v2)
async def add_t_v2(m: types.Message, state: FSMContext):
    await state.update_data(v2=m.text); await m.answer("To'g'ri variant:"); await state.set_state(AdminStates.v3)

@dp_t.message(AdminStates.v3)
async def add_t_v3(m: types.Message, state: FSMContext):
    d = await state.get_data()
    await db.execute("INSERT INTO tests (q, v1, v2, v3) VALUES (?, ?, ?, ?)", (d['q'], d['v1'], d['v2'], m.text))
    await m.answer("✅ Qo'shildi!"); await state.clear()

@dp_t.message(F.text == "So'zlar ombori 📚")
async def word_menu(m: types.Message, state: FSMContext):
    await state.set_state(WordStates.main); await m.answer("📚 Lug'at bo'limi", reply_markup=word_menu_kb)

@dp_t.message(WordStates.main, F.text == "Umumiy so'zlar soni")
async def w_cnt(m: types.Message):
    c = await db.execute("SELECT COUNT(*) as c FROM words WHERE user_id=?", (m.from_user.id,), fetch=True)
    await m.answer(f"So'zlaringiz: {c[0]['c']} ta")

@dp_t.message(WordStates.main, F.text == "Kerakli so'zni o'chirish")
async def del_word_start(m: types.Message, state: FSMContext):
    await state.set_state(WordStates.deleting); await m.answer("O'chiriladigan so'zni yozing:")

@dp_t.message(WordStates.deleting)
async def process_del_w(m: types.Message, state: FSMContext):
    await db.execute("DELETE FROM words WHERE user_id=? AND word=?", (m.from_user.id, m.text))
    await m.answer(f"🗑 '{m.text}' o'chirildi."); await state.set_state(WordStates.main)

@dp_t.message(WordStates.main, F.text)
async def auto_save(m: types.Message):
    if m.text in ["Umumiy so'zlar soni", "Kerakli so'zni o'chirish"]: return
    for word in m.text.split("\n"):
        cl = word.strip()
        if cl: await db.execute("INSERT OR IGNORE INTO words (user_id, word) VALUES (?, ?)", (m.from_user.id, cl))
    await m.answer("✅ Saqlandi."); await asyncio.sleep(1); await m.delete()

@dp_s.message(Command("start"))
async def s_st(m: types.Message):
    await db.execute("INSERT OR IGNORE INTO shop_users (user_id) VALUES (?)", (m.from_user.id,))
    kb = [[KeyboardButton(text="🛒 Guruhlar")]]
    if m.from_user.id in ADMIN_LIST: kb.append([KeyboardButton(text="📢 Rassilka"), KeyboardButton(text="➕ Guruh qo'shish")])
    await m.answer("Shop Bot tayyor!", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp_s.message(F.text == "🛒 Guruhlar")
async def show_g(m: types.Message):
    groups = await db.execute("SELECT link, price, admin FROM shop_groups", fetch=True)
    txt = "<b>Guruhlar:</b>\n\n"
    for g in groups: txt += f"📢 {g['link']}\n💰 {g['price']}\n👤 {g['admin']}\n\n"
    await m.answer(txt, parse_mode="HTML")

@dp_s.message(F.text == "➕ Guruh qo'shish", IsAdmin())
async def s_add_st(m: types.Message, state: FSMContext):
    await m.answer("Link:"); await state.set_state(ShopStates.link)

@dp_s.message(ShopStates.link)
async def s_add_l(m: types.Message, state: FSMContext):
    await state.update_data(link=m.text); await m.answer("Narx:"); await state.set_state(ShopStates.price)

@dp_s.message(ShopStates.price)
async def s_add_p(m: types.Message, state: FSMContext):
    d = await state.get_data(); admin = f"@{m.from_user.username}" if m.from_user.username else m.from_user.id
    await db.execute("INSERT INTO shop_groups (link, price, admin) VALUES (?, ?, ?)", (d['link'], m.text, str(admin)))
    await m.answer("✅ Saqlandi!"); await state.clear()

async def main():
    await init_db()
    print("SISTEMA TAYYOR! RASSILKA TESTI TUZATILDI.")
    await asyncio.gather(dp_s.start_polling(bot_s), dp_t.start_polling(bot_t))

if __name__ == '__main__':
    asyncio.run(main())