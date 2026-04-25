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

db = Database('bot_system_v_final.db')

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
    choosing_type = State(); bc_message = State(); bc_test = State()
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

# --- ASOSIY MENYU ORQAGA ---
@dp_t.message(F.text == "🔙 Orqaga")
async def back_universal(m: types.Message, state: FSMContext):
    # FSM ni tozalash va bosh menyuga qaytish
    await state.clear()
    await m.answer("Asosiy menyuga qaytdik", reply_markup=main_kb_t(m.from_user.id))

# --- TEST YECHISH VA AVTOMATIKA ---
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
        rem = await db.execute("SELECT id FROM tests WHERE id NOT IN (SELECT test_id FROM solved WHERE user_id=?)", (data['user_id'],), fetch=True)
        if not rem: await bot_t.send_message(data['user_id'], "🎊 Tabriklayman! Barcha testlarni to'g'ri yechib bo'ldingiz! ✅")
    active_tests.pop(quiz.poll_id, None)
    
    await asyncio.sleep(1.5)
    fake_msg = types.Message(message_id=0, date=None, chat=types.Chat(id=data['user_id'], type="private"), from_user=types.User(id=data['user_id'], is_bot=False, first_name="User"), text="Test yechish 📝")
    await take_test(fake_msg)

# --- SO'ZLAR OMBORI ---
@dp_t.message(F.text == "So'zlar ombori 📚")
async def word_menu(m: types.Message, state: FSMContext):
    await state.set_state(WordStates.main)
    await m.answer("📚 Lug'at bo'limi", reply_markup=word_menu_kb)

@dp_t.message(WordStates.main, F.text == "Umumiy so'zlar soni")
async def w_cnt(m: types.Message):
    c = await db.execute("SELECT COUNT(*) as c FROM words WHERE user_id=?", (m.from_user.id,), fetch=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👁 Ko'rish", callback_data="v_0")]])
    await m.answer(f"So'zlaringiz: {c[0]['c']} ta", reply_markup=kb)

@dp_t.callback_query(F.data.startswith("v_"))
async def v_words(c: types.CallbackQuery):
    off = int(c.data.split("_")[1])
    words = await db.execute("SELECT word FROM words WHERE user_id=? LIMIT 20 OFFSET ?", (c.from_user.id, off), fetch=True)
    if not words: return await c.answer("Tugadi")
    txt = "📖 Ro'yxat:\n\n"
    for i, w in enumerate(words, off+1): txt += f"{i}. {w['word']}\n"
    b = []
    if off >= 20: b.append(InlineKeyboardButton(text="⬅️", callback_data=f"v_{off-20}"))
    if len(words) == 20: b.append(InlineKeyboardButton(text="➡️", callback_data=f"v_{off+20}"))
    await c.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=[b]) if b else None)

# KERAKLI SO'ZNI O'CHIRISH (TUSHIB QOLGAN QISM QAYTARILDI)
@dp_t.message(WordStates.main, F.text == "Kerakli so'zni o'chirish")
async def del_word_start(m: types.Message, state: FSMContext):
    await state.set_state(WordStates.deleting)
    await m.answer("O'chirmoqchi bo'lgan so'zingizni yozing:")

@dp_t.message(WordStates.deleting)
async def process_del_w(m: types.Message, state: FSMContext):
    if m.text == "🔙 Orqaga":
        await state.set_state(WordStates.main)
        await m.answer("So'zlar menyusiga qaytdik", reply_markup=word_menu_kb)
        return
    await db.execute("DELETE FROM words WHERE user_id=? AND word=?", (m.from_user.id, m.text))
    await m.answer(f"🗑 '{m.text}' so'zi o'chirildi.")
    await state.set_state(WordStates.main)

@dp_t.message(WordStates.main, F.text)
async def auto_save(m: types.Message):
    if m.text in ["Umumiy so'zlar soni", "Kerakli so'zni o'chirish"]: return
    a, d = 0, 0
    for word in m.text.split("\n"):
        cl = word.strip()
        if cl:
            chk = await db.execute("SELECT id FROM words WHERE user_id=? AND word=?", (m.from_user.id, cl), fetch=True)
            if chk: d += 1
            else: await db.execute("INSERT INTO words (user_id, word) VALUES (?, ?)", (m.from_user.id, cl)); a += 1
    res = await m.answer(f"✅ {a} ta qo'shildi. ⚠️ {d} ta bor."); await asyncio.sleep(2)
    try: await res.delete(); await m.delete()
    except: pass

# --- TEST BOT ADMIN QISMI ---
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

@dp_t.message(F.text == "🗑 Test o'chirish", IsAdmin())
async def del_t_list(m: types.Message, state: FSMContext):
    tests = await db.execute("SELECT id, q FROM tests ORDER BY id DESC LIMIT 10", fetch=True)
    if not tests: return await m.answer("Test yo'q.")
    txt = "O'chirish uchun ID yuboring:\n\n"
    for t in tests: txt += f"🆔 {t['id']}: {t['q'][:30]}...\n"
    await m.answer(txt); await state.set_state(AdminStates.del_t)

@dp_t.message(AdminStates.del_t)
async def del_t_final(m: types.Message, state: FSMContext):
    if m.text.isdigit():
        await db.execute("DELETE FROM tests WHERE id=?", (int(m.text),))
        await m.answer("✅ O'chirildi."); await state.clear()
    else: await m.answer("Faqat raqam yozing!")

@dp_t.message(F.text == "📊 Statistika", IsAdmin())
async def show_stats(m: types.Message):
    u = await db.execute("SELECT COUNT(*) as c FROM test_users", fetch=True)
    t = await db.execute("SELECT COUNT(*) as c FROM tests", fetch=True)
    await m.answer(f"Foydalanuvchilar: {u[0]['c']}\nTestlar: {t[0]['c']}")

# TEST BOT RASSILKA (TUSHIB QOLGAN QISM QAYTARILDI)
@dp_t.message(F.text == "📢 Rassilka", IsAdmin())
async def t_bc_choice(m: types.Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Oddiy xabar", callback_data="bt_msg"), InlineKeyboardButton(text="🗳 Test", callback_data="bt_poll")]
    ])
    await m.answer("Test botda nimani tarqatamiz?", reply_markup=kb)
    await state.set_state(AdminStates.choosing_type)

@dp_t.callback_query(AdminStates.choosing_type, F.data.startswith("bt_"))
async def t_bc_st(c: types.CallbackQuery, state: FSMContext):
    if c.data == "bt_msg":
        await c.message.answer("Xabar matnini yuboring:"); await state.set_state(AdminStates.bc_message)
    else:
        await c.message.answer("Testni (Poll) yuboring:"); await state.set_state(AdminStates.bc_test)
    await c.answer()

@dp_t.message(AdminStates.bc_message)
async def t_bc_m_send(m: types.Message, state: FSMContext):
    users = await db.execute("SELECT user_id FROM test_users", fetch=True)
    c = 0
    for u in users:
        try: await m.copy_to(u['user_id']); c += 1; await asyncio.sleep(0.05)
        except: continue
    await m.answer(f"✅ {c} ta foydalanuvchiga xabar yetdi."); await state.clear()

@dp_t.message(AdminStates.bc_test, F.poll)
async def t_bc_p_send(m: types.Message, state: FSMContext):
    users = await db.execute("SELECT user_id FROM test_users", fetch=True)
    c = 0
    for u in users:
        try: await m.forward(u['user_id']); c += 1; await asyncio.sleep(0.05)
        except: continue
    await m.answer(f"✅ {c} ta foydalanuvchiga test yetdi."); await state.clear()


# ==========================================
#         SHOP BOT HANDLERLARI
# ==========================================
@dp_s.message(Command("start"))
async def shop_start(m: types.Message):
    await db.execute("INSERT OR IGNORE INTO shop_users (user_id) VALUES (?)", (m.from_user.id,))
    kb = [[KeyboardButton(text="🛒 Guruhlar")]]
    if m.from_user.id in ADMIN_LIST:
        kb.append([KeyboardButton(text="📢 Rassilka"), KeyboardButton(text="➕ Guruh qo'shish")])
    await m.answer("Sotuv botiga xush kelibsiz!", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp_s.message(F.text == "🛒 Guruhlar")
async def show_shop_groups(m: types.Message):
    groups = await db.execute("SELECT link, price, admin FROM shop_groups", fetch=True)
    if not groups: return await m.answer("Hozircha guruhlar yo'q.")
    text = "<b>🚀 Sotuvdagi guruhlar:</b>\n\n"
    for g in groups: text += f"📢 {g['link']}\n💰 Narxi: {g['price']}\n👤 Admin: {g['admin']}\n\n"
    await m.answer(text, parse_mode="HTML", disable_web_page_preview=True)

# SHOP BOT GURUH QO'SHISH (TUSHIB QOLGAN QISM QAYTARILDI)
@dp_s.message(F.text == "➕ Guruh qo'shish", IsAdmin())
async def shop_add_start(m: types.Message, state: FSMContext):
    await m.answer("Guruh linkini yuboring:"); await state.set_state(ShopStates.link)

@dp_s.message(ShopStates.link)
async def shop_add_link(m: types.Message, state: FSMContext):
    await state.update_data(link=m.text); await m.answer("Narxini yozing (Masalan: 50,000 so'm):"); await state.set_state(ShopStates.price)

@dp_s.message(ShopStates.price)
async def shop_add_price(m: types.Message, state: FSMContext):
    data = await state.get_data()
    admin_tag = f"@{m.from_user.username}" if m.from_user.username else f"ID: {m.from_user.id}"
    await db.execute("INSERT INTO shop_groups (link, price, admin) VALUES (?, ?, ?)", (data['link'], m.text, admin_tag))
    await m.answer("✅ Guruh muvaffaqiyatli saqlandi!"); await state.clear()

# SHOP BOT RASSILKA
@dp_s.message(F.text == "📢 Rassilka", IsAdmin())
async def s_bc_start(m: types.Message, state: FSMContext):
    await m.answer("Tarqatish uchun xabarni yuboring:"); await state.set_state(ShopStates.bc)

@dp_s.message(ShopStates.bc)
async def s_bc_send(m: types.Message, state: FSMContext):
    users = await db.execute("SELECT user_id FROM shop_users", fetch=True)
    count = 0
    for u in users:
        try: await m.copy_to(u['user_id']); count += 1; await asyncio.sleep(0.05)
        except: continue
    await m.answer(f"✅ {count} ta foydalanuvchiga yuborildi."); await state.clear()

async def main():
    await init_db()
    print("SISTEMA 100% TO'LIQ ISHLAMOQDA. BARCHA HANDLERLAR JOYIDA!")
    await asyncio.gather(dp_s.start_polling(bot_s), dp_t.start_polling(bot_t))

if __name__ == '__main__':
    asyncio.run(main())