import os, logging, asyncio, random, aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- SOZLAMALAR ---
TOKEN_SHOP = '8737514748:AAEeJwwzVf6e0yzYlwXRT8N0UrvsULGCapI'
TOKEN_TEST = '8750077178:AAFgDf_LDL11-cYvg_KGZUboTnkH-oWPFak'
ADMIN_LIST = [8213426436, 8562020437]

bot_s, bot_t = Bot(token=TOKEN_SHOP), Bot(token=TOKEN_TEST)
dp_s, dp_t = Dispatcher(storage=MemoryStorage()), Dispatcher(storage=MemoryStorage())

# --- DATABASE ---
class Database:
    def __init__(self, db_path): self.db_path = db_path
    async def execute(self, sql, params=(), fetch=False):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(sql, params)
            if fetch: return await cursor.fetchall()
            await db.commit()

db = Database('bot_system_v11.db')

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
class AdminStates(StatesGroup): q=State(); v1=State(); v2=State(); v3=State(); bc=State(); del_t=State()
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

# --- SHOP BOT (Xatolik tuzatilgan: Markdown o'rniga HTML) ---
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
    for g in groups:
        # HTML rejimida pastki chiziqlar muammo tug'dirmaydi
        text += f"📢 {g[0]}\n💰 Narxi: {g[1]}\n👤 Admin: {g[2]}\n\n"
    await m.answer(text, parse_mode="HTML", disable_web_page_preview=True)

# --- TEST BOT ---
@dp_t.message(Command("start"))
async def test_start(m: types.Message, state: FSMContext):
    await state.clear()
    await db.execute("INSERT OR IGNORE INTO test_users (user_id, name) VALUES (?, ?)", (m.from_user.id, m.from_user.full_name))
    await m.answer("Bilim botiga xush kelibsiz!", reply_markup=main_kb_t(m.from_user.id))

# --- SO'ZLAR OMBORI MANTIQI ---
@dp_t.message(F.text == "So'zlar ombori 📚")
async def word_storage_main(m: types.Message, state: FSMContext):
    await state.set_state(WordStates.main)
    await m.answer("📚 So'zlar omboriga xush kelibsiz! Bu yerda yangi so'zlar yuborishingiz yoki borlarini boshqarishingiz mumkin.", reply_markup=word_menu_kb)

@dp_t.message(WordStates.main, F.text == "Umumiy so'zlar soni")
async def word_count(m: types.Message):
    count = await db.execute("SELECT COUNT(*) FROM words WHERE user_id=?", (m.from_user.id,), fetch=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="So'zlarni ko'rish 👁", callback_data="view_words_0")]])
    await m.answer(f"Sizning lug'atingizda jami <b>{count[0][0]}</b> ta so'z bor.", parse_mode="HTML", reply_markup=kb)

@dp_t.callback_query(F.data.startswith("view_words_"))
async def view_words_numbered(c: types.CallbackQuery):
    offset = int(c.data.split("_")[2])
    words = await db.execute("SELECT word FROM words WHERE user_id=? LIMIT 20 OFFSET ?", (c.from_user.id, offset), fetch=True)
    if not words: return await c.answer("Boshqa so'z yo'q")
    
    text = f"📖 <b>Lug'atingiz ({offset+1}-{offset+len(words)}):</b>\n\n"
    for i, w in enumerate(words, start=offset + 1):
        text += f"{i}. {w[0]}\n"
    
    btns = []
    if offset >= 20: btns.append(InlineKeyboardButton(text="⬅️", callback_data=f"view_words_{offset-20}"))
    if len(words) == 20: btns.append(InlineKeyboardButton(text="➡️", callback_data=f"view_words_{offset+20}"))
    kb = InlineKeyboardMarkup(inline_keyboard=[btns]) if btns else None
    await c.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@dp_t.message(WordStates.main, F.text == "Kerakli so'zni o'chirish")
async def delete_word_prompt(m: types.Message, state: FSMContext):
    await state.set_state(WordStates.deleting)
    await m.answer("O'chirmoqchi bo'lgan so'zingizni aynan o'zini yuboring (yoki bekor qilish uchun '🔙 Orqaga' ni bosing):")

@dp_t.message(WordStates.deleting)
async def process_word_delete(m: types.Message, state: FSMContext):
    if m.text == "🔙 Orqaga":
        await state.set_state(WordStates.main)
        return await m.answer("Amal bekor qilindi.", reply_markup=word_menu_kb)
    
    res = await db.execute("DELETE FROM words WHERE user_id=? AND word=?", (m.from_user.id, m.text))
    await m.answer(f"🗑 So'z tekshirildi va lug'atdan o'chirildi (agar mavjud bo'lsa).")
    await state.set_state(WordStates.main)

@dp_t.message(WordStates.main, F.text == "🔙 Orqaga")
async def back_to_main(m: types.Message, state: FSMContext):
    await state.clear()
    await m.answer("Asosiy menyu", reply_markup=main_kb_t(m.from_user.id))

# Faqat WordStates.main holatidagina so'z qo'shish
@dp_t.message(WordStates.main, F.text)
async def auto_save_words(m: types.Message):
    if m.text in ["Umumiy so'zlar soni", "Kerakli so'zni o'chirish", "🔙 Orqaga"]: return
    
    added_count = 0
    for word in m.text.split("\n"):
        clean_word = word.strip()
        if clean_word:
            try:
                await db.execute("INSERT OR IGNORE INTO words (user_id, word) VALUES (?, ?)", (m.from_user.id, clean_word))
                added_count += 1
            except: pass
    
    msg = await m.answer(f"✅ {added_count} ta yangi so'z saqlandi!")
    await asyncio.sleep(2)
    try: await msg.delete(); await m.delete()
    except: pass

# --- TEST O'CHIRISH (Admin uchun) ---
@dp_t.message(F.text == "🗑 Test o'chirish", IsAdmin())
async def del_test_cmd(m: types.Message, state: FSMContext):
    tests = await db.execute("SELECT id, q FROM tests ORDER BY id DESC LIMIT 10", fetch=True)
    if not tests: return await m.answer("Bazada test yo'q.")
    txt = "O'chirish uchun Test ID raqamini yuboring:\n\n"
    for t in tests: txt += f"🆔 <code>{t[0]}</code>: {t[1][:30]}...\n"
    await m.answer(txt, parse_mode="HTML"); await state.set_state(AdminStates.del_t)

@dp_t.message(AdminStates.del_t)
async def process_del_t(m: types.Message, state: FSMContext):
    if m.text.isdigit():
        await db.execute("DELETE FROM tests WHERE id=?", (int(m.text),))
        await m.answer("✅ Test o'chirildi!"); await state.clear()
    else: await m.answer("Faqat raqam yuboring!")

# (Qolgan rassilka va shop handlerlari yuqoridagi kod bilan bir xil...)
# --- MAIN ---
async def main():
    await init_db()
    print("BOTLAR ISHGA TUSHDI! (Markdown bug fix + New Dictionary Logic)")
    await asyncio.gather(dp_s.start_polling(bot_s), dp_t.start_polling(bot_t))

if __name__ == '__main__':
    try: asyncio.run(main())
    except: pass