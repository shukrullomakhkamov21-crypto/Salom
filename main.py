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

bot_s, bot_t = Bot(token=TOKEN_SHOP), Bot(token=TOKEN_TEST)
dp_s, dp_t = Dispatcher(storage=MemoryStorage()), Dispatcher(storage=MemoryStorage())

# Tugmalar ro'yxati (bot adashib lug'atga qo'shib yubormasligi uchun)
RESERVED_BUTTONS = [
    "Test yechish 📝", "So'zlar ombori 📚", "📢 Rassilka", "📊 Statistika", 
    "➕ Test qo'shish", "🗑 Test o'chirish", "Umumiy so'zlar soni", 
    "Kerakli so'zni o'chirish", "🔙 Orqaga", "🛒 Guruhlar", "➕ Guruh qo'shish"
]

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

# ==========================================
#         TEST BOT HANDLERLARI
# ==========================================
active_tests = {}

@dp_t.message(Command("start"))
async def test_start(m: types.Message, state: FSMContext):
    await state.clear()
    user = await db.execute("SELECT user_id FROM test_users WHERE user_id=?", (m.from_user.id,), fetch=True)
    if not user:
        await db.execute("INSERT OR IGNORE INTO test_users (user_id, name) VALUES (?, ?)", (m.from_user.id, m.from_user.full_name))
        for adm in ADMIN_LIST:
            try: await bot_t.send_message(adm, f"🆕 Yangi foydalanuvchi:\nIsm: {m.from_user.full_name}\nID: {m.from_user.id}")
            except: pass
    await m.answer("Bilim botiga xush kelibsiz!", reply_markup=main_kb_t(m.from_user.id))

@dp_t.message(F.text == "🔙 Orqaga")
async def back_universal(m: types.Message, state: FSMContext):
    await state.clear(); await m.answer("Asosiy menyu", reply_markup=main_kb_t(m.from_user.id))

# --- TESTLAR ---
@dp_t.message(F.text == "Test yechish 📝")
async def take_test(m: types.Message):
    tests = await db.execute("SELECT * FROM tests WHERE id NOT IN (SELECT test_id FROM solved WHERE user_id=?)", (m.from_user.id,), fetch=True)
    if not tests: 
        return await m.answer("🎉 Siz hamma testlarni echib bo'ldingiz tabriklayman!")
    
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
    await asyncio.sleep(3) # 3 soniya kutish
    
    # Keyingi testga o'tish
    fake_msg = types.Message(message_id=0, date=None, chat=types.Chat(id=data['user_id'], type="private"), from_user=types.User(id=data['user_id'], is_bot=False, first_name="User"), text="Test yechish 📝")
    await take_test(fake_msg)

# --- SO'ZLAR OMBORI ---
@dp_t.message(F.text == "So'zlar ombori 📚")
async def word_menu(m: types.Message, state: FSMContext):
    await state.set_state(WordStates.main)
    await m.answer("siz bu erga yod olgan soʼzlarinigizni yozasiz men esa eslab qolaman", reply_markup=word_menu_kb)

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
    for w in words:
        builder.button(text=w['word'], callback_data=f"dw_{w['id']}")
    builder.adjust(2)
    await m.answer("O'chirmoqchi bo'lgan so'zingizni tanlang:", reply_markup=builder.as_markup())

@dp_t.callback_query(F.data.startswith("dw_"))
async def del_word_process(c: types.CallbackQuery):
    w_id = c.data.split("_")[1]
    await db.execute("DELETE FROM words WHERE id=?", (w_id,))
    await c.message.edit_text("🗑 So'z o'chirildi."); await c.answer()

@dp_t.message(WordStates.main, F.text)
async def auto_save(m: types.Message):
    if m.text in RESERVED_BUTTONS: return
    for word in m.text.split("\n"):
        cl = word.strip()
        if cl: await db.execute("INSERT OR IGNORE INTO words (user_id, word) VALUES (?, ?)", (m.from_user.id, cl))
    await m.answer("✅ Saqlandi."); await asyncio.sleep(1); await m.delete()

# --- ADMIN: TESTLARNI O'CHIRISH ---
@dp_t.message(F.text == "🗑 Test o'chirish", IsAdmin())
async def del_test_menu(m: types.Message):
    tests = await db.execute("SELECT id, q FROM tests", fetch=True)
    if not tests: return await m.answer("Hali testlar yo'q.")
    builder = InlineKeyboardBuilder()
    for t in tests:
        builder.button(text=f"{t['q'][:20]}...", callback_data=f"dt_{t['id']}")
    builder.adjust(1)
    await m.answer("O'chirish uchun testni tanlang:", reply_markup=builder.as_markup())

@dp_t.callback_query(F.data.startswith("dt_"))
async def del_test_process(c: types.CallbackQuery):
    t_id = c.data.split("_")[1]
    await db.execute("DELETE FROM tests WHERE id=?", (t_id,))
    await db.execute("DELETE FROM solved WHERE test_id=?", (t_id,))
    await c.message.edit_text("✅ Test o'chirildi!"); await c.answer()

# --- ADMIN: STATISTIKA (TEST BOT) ---
@dp_t.message(F.text == "📊 Statistika", IsAdmin())
async def t_stats(m: types.Message):
    users = await db.execute("SELECT u.name, u.user_id, (SELECT COUNT(*) FROM solved WHERE user_id=u.user_id) as score FROM test_users u ORDER BY score DESC", fetch=True)
    txt = "📊 **Foydalanuvchilar reytingi:**\n\n"
    for i, u in enumerate(users, 1):
        txt += f"{i}. {u['name']} (ID: {u['user_id']}) - {u['score']} ta ✅\n"
    await m.answer(txt)

# --- ADMIN: RASSILKA (TEST BOT - TUZATILDI) ---
@dp_t.message(F.text == "📢 Rassilka", IsAdmin())
async def t_bc_choice(m: types.Message, state: FSMContext):
    await state.clear()
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

@dp_t.message(AdminStates.bc_message)
async def t_bc_m_send(m: types.Message, state: FSMContext):
    users = await db.execute("SELECT user_id FROM test_users", fetch=True)
    c = 0
    for u in users:
        try: await m.copy_to(u['user_id']); c += 1; await asyncio.sleep(0.05)
        except: continue
    await m.answer(f"✅ {c} ta xabar yuborildi."); await state.clear()

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
    idx = opts.index(correct)
    users = await db.execute("SELECT user_id FROM test_users", fetch=True)
    c = 0
    for u in users:
        try:
            await bot_t.send_poll(chat_id=u['user_id'], question=d['q'], options=opts, type='quiz', correct_option_id=idx, is_anonymous=False)
            c += 1; await asyncio.sleep(0.05)
        except: continue
    await m.answer(f"✅ Test {c} kishiga yuborildi!"); await state.clear()

# ==========================================
#         SHOP BOT HANDLERLARI
# ==========================================
@dp_s.message(Command("start"))
async def s_st(m: types.Message):
    user = await db.execute("SELECT user_id FROM shop_users WHERE user_id=?", (m.from_user.id,), fetch=True)
    if not user:
        await db.execute("INSERT OR IGNORE INTO shop_users (user_id, name) VALUES (?, ?)", (m.from_user.id, m.from_user.full_name))
        for adm in ADMIN_LIST:
            try: await bot_s.send_message(adm, f"🆕 Shop Bot Yangi foydalanuvchi:\nIsm: {m.from_user.full_name}\nID: {m.from_user.id}")
            except: pass
    
    kb = [[KeyboardButton(text="🛒 Guruhlar")]]
    if m.from_user.id in ADMIN_LIST: 
        kb.append([KeyboardButton(text="📢 Rassilka"), KeyboardButton(text="➕ Guruh qo'shish")])
        kb.append([KeyboardButton(text="📊 Statistika")])
    await m.answer("Shop Bot tayyor!", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp_s.message(F.text == "🛒 Guruhlar")
async def show_g(m: types.Message):
    groups = await db.execute("SELECT link, price, admin FROM shop_groups", fetch=True)
    txt = "<b>Guruhlar:</b>\n\n"
    for g in groups: txt += f"📢 {g['link']}\n💰 {g['price']}\n👤 {g['admin']}\n\n"
    await m.answer(txt, parse_mode="HTML")

@dp_s.message(F.text == "➕ Guruh qo'shish", IsAdmin())
async def s_add_st(m: types.Message, state: FSMContext):
    await m.answer("Guruh linkini yuboring:"); await state.set_state(ShopStates.link)

@dp_s.message(ShopStates.link)
async def s_add_l(m: types.Message, state: FSMContext):
    # _ belgisini Markdown buzmasligi uchun HTML ishlatiladi
    await state.update_data(link=m.text)
    await m.answer(f"Guruh: {m.text}\nNarxini yozing:")
    await state.set_state(ShopStates.price)

@dp_s.message(ShopStates.price)
async def s_add_p(m: types.Message, state: FSMContext):
    d = await state.get_data(); admin = f"@{m.from_user.username}" if m.from_user.username else m.from_user.id
    await db.execute("INSERT INTO shop_groups (link, price, admin) VALUES (?, ?, ?)", (d['link'], m.text, str(admin)))
    await m.answer("✅ Saqlandi!"); await state.clear()

@dp_s.message(F.text == "📊 Statistika", IsAdmin())
async def s_stats(m: types.Message):
    users = await db.execute("SELECT * FROM shop_users", fetch=True)
    txt = f"📊 **Shop Bot statistikasi:**\nJami foydalanuvchilar: {len(users)} ta\n\n**Ro'yxat:**\n"
    for u in users: txt += f"• {u['name']} (ID: {u['user_id']})\n"
    await m.answer(txt)

@dp_s.message(F.text == "📢 Rassilka", IsAdmin())
async def s_bc_st(m: types.Message, state: FSMContext):
    await m.answer("Shop Bot uchun xabar yuboring:"); await state.set_state(ShopStates.bc)

@dp_s.message(ShopStates.bc)
async def s_bc_send(m: types.Message, state: FSMContext):
    users = await db.execute("SELECT user_id FROM shop_users", fetch=True)
    c = 0
    for u in users:
        try: await m.copy_to(u['user_id']); c += 1; await asyncio.sleep(0.05)
        except: continue
    await m.answer(f"✅ {c} ta xabar yuborildi."); await state.clear()

# ==========================================
#         AVTOMATIK VAQT FUNKSIYALARI
# ==========================================
@aiocron.crontab('30 19 * * *') # Har kuni 19:30 da
async def evening_rank():
    users = await db.execute("SELECT name, (SELECT COUNT(*) FROM solved WHERE user_id=test_users.user_id) as score FROM test_users ORDER BY score DESC LIMIT 10", fetch=True)
    if not users: return
    txt = "🏆 **Bugungi TOP 10 bilimdonlar:**\n\n"
    for i, u in enumerate(users, 1):
        txt += f"{i}. {u['name']} - {u['score']} ta ✅\n"
    
    all_users = await db.execute("SELECT user_id FROM test_users", fetch=True)
    for au in all_users:
        try: await bot_t.send_message(au['user_id'], txt)
        except: pass

@aiocron.crontab('00 06 * * *') # Har kuni 06:00 da
async def morning_msg():
    all_users = await db.execute("SELECT user_id FROM test_users", fetch=True)
    for au in all_users:
        try: await bot_t.send_message(au['user_id'], "diqqat diqqat botimiz ishlayapti uygʼoning")
        except: pass

# --- TEST QO'SHISH HANDLERLARI (TEGILMADI) ---
@dp_t.message(F.text == "➕ Test qo'shish", IsAdmin())
async def add_t_st(m: types.Message, state: FSMContext):
    await m.answer("Savol:"); await state.set_state(AdminStates.q)
@dp_t.message(AdminStates.q)
async def add_t_q(m: types.Message, state: FSMContext):
    if m.text in RESERVED_BUTTONS: return
    await state.update_data(q=m.text); await m.answer("1-xato:"); await state.set_state(AdminStates.v1)
@dp_t.message(AdminStates.v1)
async def add_t_v1(m: types.Message, state: FSMContext):
    if m.text in RESERVED_BUTTONS: return
    await state.update_data(v1=m.text); await m.answer("2-xato:"); await state.set_state(AdminStates.v2)
@dp_t.message(AdminStates.v2)
async def add_t_v2(m: types.Message, state: FSMContext):
    if m.text in RESERVED_BUTTONS: return
    await state.update_data(v2=m.text); await m.answer("To'g'ri:"); await state.set_state(AdminStates.v3)
@dp_t.message(AdminStates.v3)
async def add_t_v3(m: types.Message, state: FSMContext):
    if m.text in RESERVED_BUTTONS: return
    d = await state.get_data()
    await db.execute("INSERT INTO tests (q, v1, v2, v3) VALUES (?, ?, ?, ?)", (d['q'], d['v1'], d['v2'], m.text))
    await m.answer("✅ Qo'shildi!"); await state.clear()

# --- ASOSIY ISHGA TUSHIRISH ---
async def main():
    await init_db()
    print("SISTEMA TAYYOR!")
    await asyncio.gather(dp_s.start_polling(bot_s), dp_t.start_polling(bot_t))

if __name__ == '__main__':
    asyncio.run(main())
