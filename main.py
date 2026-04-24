import os
import logging
import asyncio
import random
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- SOZLAMALAR ---
TOKEN_SHOP = '8737514748:AAEeJwwzVf6e0yzYlwXRT8N0UrvsULGCapI'
TOKEN_TEST = '8750077178:AAFgDf_LDL11-cYvg_KGZUboTnkH-oWPFak'
ADMIN_LIST = [8213426436, 8562020437]

# Loglarni faylga yozish
logging.basicConfig(level=logging.INFO, filename='bot_final.log', filemode='a',
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

bot_s, bot_t = Bot(token=TOKEN_SHOP), Bot(token=TOKEN_TEST)
dp_s, dp_t = Dispatcher(storage=MemoryStorage()), Dispatcher(storage=MemoryStorage())

# --- ASINXRON MA'LUMOTLAR BAZASI ---
class Database:
    def __init__(self, db_path):
        self.db_path = db_path

    async def execute(self, sql, params=(), fetch=False):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(sql, params)
            if fetch:
                res = await cursor.fetchall()
                return res
            await db.commit()

db = Database('bot_system_v10.db')

async def init_db():
    # Bazani qulflanib qolishidan himoya qilish (WAL rejimi)
    async with aiosqlite.connect(db.db_path) as _db:
        await _db.execute('PRAGMA journal_mode=WAL;')
        await _db.commit()
        
    await db.execute('CREATE TABLE IF NOT EXISTS shop_groups (id INTEGER PRIMARY KEY, link TEXT, price TEXT, admin TEXT)')
    await db.execute('CREATE TABLE IF NOT EXISTS shop_users (user_id INTEGER PRIMARY KEY)')
    await db.execute('CREATE TABLE IF NOT EXISTS test_users (user_id INTEGER PRIMARY KEY, name TEXT)')
    await db.execute('CREATE TABLE IF NOT EXISTS words (id INTEGER PRIMARY KEY, user_id INTEGER, word TEXT, UNIQUE(user_id, word))')
    await db.execute('CREATE TABLE IF NOT EXISTS tests (id INTEGER PRIMARY KEY AUTOINCREMENT, q TEXT, v1 TEXT, v2 TEXT, v3 TEXT)')
    await db.execute('CREATE TABLE IF NOT EXISTS solved (user_id INTEGER, test_id INTEGER, UNIQUE(user_id, test_id))')

# --- ADMIN FILTRI ---
class IsAdmin(BaseFilter):
    async def __call__(self, m: types.Message) -> bool:
        return m.from_user.id in ADMIN_LIST

# --- FSM STATES ---
class ShopStates(StatesGroup): link = State(); price = State(); bc = State()
class AdminStates(StatesGroup): q=State(); v1=State(); v2=State(); v3=State(); bc=State(); del_t=State()

# --- XAVFSIZ RASSILKA ---
async def safe_broadcast(bot: Bot, users: list, message: types.Message):
    count = 0
    for u in users:
        try:
            await message.copy_to(u[0])
            count += 1
            await asyncio.sleep(0.05)
        except (TelegramForbiddenError, Exception): continue
    return count

# --- SHOP BOT (bot_s) HANDLERLARI ---
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
    text = "🚀 **Sotuvdagi guruhlar:**\n\n"
    for g in groups: text += f"📢 {g[0]}\n💰 Narxi: {g[1]}\n👤 Admin: {g[2]}\n\n"
    await m.answer(text, parse_mode="Markdown")

@dp_s.message(F.text == "📢 Rassilka", IsAdmin())
async def s_bc_start(m: types.Message, state: FSMContext):
    await m.answer("Shop bot foydalanuvchilariga yuboriladigan xabarni yozing:"); await state.set_state(ShopStates.bc)

@dp_s.message(ShopStates.bc)
async def s_bc_send(m: types.Message, state: FSMContext):
    users = await db.execute("SELECT user_id FROM shop_users", fetch=True)
    sent = await safe_broadcast(bot_s, users, m)
    await m.answer(f"📢 Rassilka yakunlandi!\n✅ {sent} ta foydalanuvchiga yetkazildi."); await state.clear()

@dp_s.message(F.text == "➕ Guruh qo'shish", IsAdmin())
async def shop_add_start(m: types.Message, state: FSMContext):
    await m.answer("Guruh linkini yuboring:"); await state.set_state(ShopStates.link)

@dp_s.message(ShopStates.link)
async def shop_add_link(m: types.Message, state: FSMContext):
    await state.update_data(link=m.text); await m.answer("Narxini yozing:"); await state.set_state(ShopStates.price)

@dp_s.message(ShopStates.price)
async def shop_add_price(m: types.Message, state: FSMContext):
    data = await state.get_data()
    admin_tag = f"@{m.from_user.username}" if m.from_user.username else f"ID: {m.from_user.id}"
    await db.execute("INSERT INTO shop_groups (link, price, admin) VALUES (?, ?, ?)", (data['link'], m.text, admin_tag))
    await m.answer("✅ Guruh saqlandi!"); await state.clear()

# --- TEST BOT (bot_t) HANDLERLARI ---
@dp_t.message(Command("start"))
async def test_start(m: types.Message):
    await db.execute("INSERT OR IGNORE INTO test_users (user_id, name) VALUES (?, ?)", (m.from_user.id, m.from_user.full_name))
    kb = [[KeyboardButton(text="Test yechish 📝"), KeyboardButton(text="Lug'atim 📚")]]
    if m.from_user.id in ADMIN_LIST:
        kb.append([KeyboardButton(text="📢 Rassilka"), KeyboardButton(text="📊 Statistika")])
        kb.append([KeyboardButton(text="➕ Test qo'shish"), KeyboardButton(text="🗑 Test o'chirish")])
    await m.answer("Bilim botiga xush kelibsiz!", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp_t.message(F.text == "📊 Statistika", IsAdmin())
async def show_stats(m: types.Message):
    u = await db.execute("SELECT COUNT(*) FROM test_users", fetch=True)
    t = await db.execute("SELECT COUNT(*) FROM tests", fetch=True)
    w = await db.execute("SELECT COUNT(*) FROM words", fetch=True)
    await m.answer(f"📈 **Bot statistikasi:**\n\n👤 Userlar: {u[0][0]}\n📝 Testlar: {t[0][0]}\n📚 So'zlar: {w[0][0]}", parse_mode="Markdown")

@dp_t.message(F.text == "Lug'atim 📚")
async def show_first_words(m: types.Message):
    words = await db.execute("SELECT word FROM words WHERE user_id=? LIMIT 20", (m.from_user.id,), fetch=True)
    if not words: return await m.answer("Lug'atingiz hali bo'sh.")
    text = f"📖 **Sizning lug'atingiz (1-{len(words)}):**\n\n" + "\n".join([f"🔹 {w[0]}" for w in words])
    kb = None
    if len(words) == 20:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Keyingi ➡️", callback_data="words_20")]])
    await m.answer(text, parse_mode="Markdown", reply_markup=kb)

@dp_t.callback_query(F.data.startswith("words_"))
async def words_pagination(c: types.CallbackQuery):
    offset = int(c.data.split("_")[1])
    words = await db.execute("SELECT word FROM words WHERE user_id=? LIMIT 20 OFFSET ?", (c.from_user.id, offset), fetch=True)
    if not words: return await c.answer("Boshqa so'z yo'q", show_alert=True)
    text = f"📖 **Lug'atingiz ({offset+1}-{offset+len(words)}):**\n\n" + "\n".join([f"🔹 {w[0]}" for w in words])
    btns = []
    if offset >= 20: btns.append(InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"words_{offset-20}"))
    if len(words) == 20: btns.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"words_{offset+20}"))
    kb = InlineKeyboardMarkup(inline_keyboard=[btns]) if btns else None
    await c.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)

@dp_t.message(F.text == "Test yechish 📝")
async def take_test(m: types.Message):
    tests = await db.execute("SELECT * FROM tests WHERE id NOT IN (SELECT test_id FROM solved WHERE user_id=?)", (m.from_user.id,), fetch=True)
    if not tests: return await m.answer("🎉 Hamma testlar yechildi!")
    t = random.choice(tests)
    opts = [t[2], t[3], t[4]]; correct = t[4]; random.shuffle(opts)
    await m.answer_poll(question=t[1], options=opts, type='quiz', correct_option_id=opts.index(correct), is_anonymous=False)
    await db.execute("INSERT OR IGNORE INTO solved (user_id, test_id) VALUES (?, ?)", (m.from_user.id, t[0]))

@dp_t.poll_answer()
async def check_finished(pa: types.PollAnswer):
    left = await db.execute("SELECT COUNT(*) FROM tests WHERE id NOT IN (SELECT test_id FROM solved WHERE user_id=?)", (pa.user.id,), fetch=True)
    if left[0][0] == 0:
        await asyncio.sleep(1)
        await bot_t.send_message(pa.user.id, "🎉 **Tabriklaymiz!** Siz bazadagi barcha testlarni yechib bo'ldingiz. Yangilarini kutib qoling! 💪", parse_mode="Markdown")

@dp_t.message(F.text == "➕ Test qo'shish", IsAdmin())
async def add_t_start(m: types.Message, state: FSMContext):
    await m.answer("Savolni yuboring:"); await state.set_state(AdminStates.q)

@dp_t.message(AdminStates.q)
async def add_t_q(m: types.Message, state: FSMContext):
    await state.update_data(q=m.text); await m.answer("1-xato variant:"); await state.set_state(AdminStates.v1)

@dp_t.message(AdminStates.v1)
async def add_t_v1(m: types.Message, state: FSMContext):
    await state.update_data(v1=m.text); await m.answer("2-xato variant:"); await state.set_state(AdminStates.v2)

@dp_t.message(AdminStates.v2)
async def add_t_v2(m: types.Message, state: FSMContext):
    await state.update_data(v2=m.text); await m.answer("TO'G'RI variantni yozing:"); await state.set_state(AdminStates.v3)

@dp_t.message(AdminStates.v3)
async def add_t_v3(m: types.Message, state: FSMContext):
    d = await state.get_data()
    await db.execute("INSERT INTO tests (q, v1, v2, v3) VALUES (?, ?, ?, ?)", (d['q'], d['v1'], d['v2'], m.text))
    await m.answer("✅ Test qo'shildi!"); await state.clear()

@dp_t.message(F.text == "🗑 Test o'chirish", IsAdmin())
async def del_t_start(m: types.Message, state: FSMContext):
    tests = await db.execute("SELECT id, q FROM tests ORDER BY id DESC LIMIT 10", fetch=True)
    if not tests: return await m.answer("Bazada testlar yo'q.")
    text = "O'chirmoqchi bo'lgan testning **ID raqamini** yuboring:\n\n"
    for t in tests: text += f"🆔 `{t[0]}`: {t[1][:40]}...\n"
    await m.answer(text, parse_mode="Markdown"); await state.set_state(AdminStates.del_t)

@dp_t.message(AdminStates.del_t)
async def del_t_process(m: types.Message, state: FSMContext):
    if not m.text.isdigit(): return await m.answer("Faqat ID raqam yuboring!")
    await db.execute("DELETE FROM tests WHERE id = ?", (int(m.text),))
    await m.answer(f"✅ Test o'chirildi."); await state.clear()

@dp_t.message(F.text == "📢 Rassilka", IsAdmin())
async def t_bc_start(m: types.Message, state: FSMContext):
    await m.answer("Test bot foydalanuvchilariga xabar yozing:"); await state.set_state(AdminStates.bc)

@dp_t.message(AdminStates.bc)
async def t_bc_send(m: types.Message, state: FSMContext):
    users = await db.execute("SELECT user_id FROM test_users", fetch=True)
    sent = await safe_broadcast(bot_t, users, m)
    await m.answer(f"📢 Rassilka yakunlandi!\n✅ {sent} ta foydalanuvchiga yetkazildi."); await state.clear()

@dp_t.message(F.text, ~F.text.startswith("/"))
async def auto_save(m: types.Message, state: FSMContext):
    if await state.get_state() is not None: return
    ignored = ["Test yechish 📝", "Lug'atim 📚", "➕ Test qo'shish", "📢 Rassilka", "🗑 Test o'chirish", "📊 Statistika"]
    if m.text in ignored: return
    for word in m.text.split("\n"):
        if word.strip(): await db.execute("INSERT OR IGNORE INTO words (user_id, word) VALUES (?, ?)", (m.from_user.id, word.strip()))
    
    # UX: Xabarni chiqarish va 3 soniyadan keyin o'chirish
    res = await m.answer("✅ Lug'atga saqlandi!")
    await asyncio.sleep(3)
    try:
        await res.delete()
        await m.delete()
    except: pass

# --- MAIN ---
async def main():
    await init_db()
    sch = AsyncIOScheduler(timezone='Asia/Dushanbe')
    sch.start()
    print("MUKAMMAL BOTLAR ISHGA TUSHDI! 100/100")
    await asyncio.gather(dp_s.start_polling(bot_s), dp_t.start_polling(bot_t))

if __name__ == '__main__':
    try: asyncio.run(main())
    except (KeyboardInterrupt, SystemExit): logging.info("Bot to'xtadi")