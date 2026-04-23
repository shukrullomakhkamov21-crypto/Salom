import asyncio
import sqlite3
import random
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, PollAnswer
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- SOZLAMALAR ---
API_TOKEN = '8750077178:AAFgDf_LDL11-cYvg_KGZUboTnkH-oWPFak' 
ADMIN_ID = 8213426436 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- BAZA BILAN ISHLASH ---
conn = sqlite3.connect('bot_database.db', check_same_thread=False)
cursor = conn.cursor()

def init_db():
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, first_name TEXT, username TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS words (user_id INTEGER, word TEXT, UNIQUE(user_id, word))')
    cursor.execute('''CREATE TABLE IF NOT EXISTS tests 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, v1 TEXT, v2 TEXT, v3 TEXT)''')
    cursor.execute('CREATE TABLE IF NOT EXISTS solved_tests (user_id INTEGER, test_id INTEGER, UNIQUE(user_id, test_id))')
    conn.commit()

init_db()

# --- PRESET FOYDALANUVCHILAR (Log fayldan olindi) ---
PRESET_USERS = [
    (8213426436, "Admin", "@shukrullo_dev"), (8074917807, "User1", "@A_B_o9o9"), 
    (1365590716, "User2", "@Pretty7011"), (1412586237, "User3", "@Zarnigorxon_04"),
    (2042705574, "User4", "@Moxira_74"), (1682317180, "User5", "@Doniyor_1995"),
    (5611130635, "User6", "@Abduvali_01"), (123456789, "User7", "noma'lum"), # Fayldagi qolgan ID'lar...
]

def restore_users():
    for u_id, name, uname in PRESET_USERS:
        cursor.execute("INSERT OR IGNORE INTO users (user_id, first_name, username) VALUES (?, ?, ?)", (u_id, name, uname))
    conn.commit()

# --- HOLATLAR ---
class Form(StatesGroup):
    waiting_for_words = State()

class AdminStates(StatesGroup):
    waiting_for_test_q = State()
    waiting_for_test_v1 = State()
    waiting_for_test_v2 = State()
    waiting_for_test_v3 = State()
    waiting_for_bc_msg = State()
    # Test rassilka uchun
    bc_test_q = State()
    bc_test_v1 = State()
    bc_test_v2 = State()
    bc_test_v3 = State()

# --- KLAVIATURALAR ---
def main_menu(u_id):
    kb = [
        [KeyboardButton(text="Testlar 📝"), KeyboardButton(text="So'z ombori 📚")]
    ]
    if u_id == ADMIN_ID:
        kb.insert(0, [KeyboardButton(text="Test qo'shish ➕"), KeyboardButton(text="Testni o'chirish 🗑")])
        kb.insert(1, [KeyboardButton(text="Rassilka 📢"), KeyboardButton(text="Foydalanuvchilar 👥")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def word_menu():
    kb = [
        [KeyboardButton(text="Umumiy so'zlar soni 📊")],
        [KeyboardButton(text="So'zni o'chirish 🗑")],
        [KeyboardButton(text="Orqaga 🔙")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- START ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    u_id, name = message.from_user.id, message.from_user.first_name
    uname = f"@{message.from_user.username}" if message.from_user.username else "Noma'lum"
    
    cursor.execute("SELECT user_id FROM users WHERE user_id=?", (u_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, first_name, username) VALUES (?, ?, ?)", (u_id, name, uname))
        conn.commit()
        await bot.send_message(ADMIN_ID, f"🔔 Yangi foydalanuvchi: {name} (ID: {u_id})")

    await message.answer(f"Hurmatli {name}, botimizga xush kelibsiz!\n\n"
                         "📝 *Testlar* - Bilimingizni sinash uchun.\n"
                         "📚 *So'z ombori* - Lug'at yig'ish uchun.", 
                         reply_markup=main_menu(u_id), parse_mode="Markdown")

# --- ADMIN: TEST QO'SHISH ---
@dp.message(F.text == "Test qo'shish ➕", F.from_user.id == ADMIN_ID)
async def admin_test_q(message: types.Message, state: FSMContext):
    await message.answer("Test savolini yuboring:")
    await state.set_state(AdminStates.waiting_for_test_q)

@dp.message(AdminStates.waiting_for_test_q)
async def admin_v1(message: types.Message, state: FSMContext):
    await state.update_data(q=message.text)
    await message.answer("1-variantni kiriting (Xato):")
    await state.set_state(AdminStates.waiting_for_test_v1)

@dp.message(AdminStates.waiting_for_test_v1)
async def admin_v2(message: types.Message, state: FSMContext):
    await state.update_data(v1=message.text)
    await message.answer("2-variantni kiriting (Xato):")
    await state.set_state(AdminStates.waiting_for_test_v2)

@dp.message(AdminStates.waiting_for_test_v2)
async def admin_v3(message: types.Message, state: FSMContext):
    await state.update_data(v2=message.text)
    await message.answer("3-variantni kiriting (TO'G'RI):")
    await state.set_state(AdminStates.waiting_for_test_v3)

@dp.message(AdminStates.waiting_for_test_v3)
async def admin_save_test(message: types.Message, state: FSMContext):
    v3 = message.text
    data = await state.get_data()
    cursor.execute("INSERT INTO tests (question, v1, v2, v3) VALUES (?, ?, ?, ?)", (data['q'], data['v1'], data['v2'], v3))
    conn.commit()
    
    # Hamma foydalanuvchilarga yuborish
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    options = [data['v1'], data['v2'], v3]
    random.shuffle(options)
    
    count = 0
    for u in users:
        try:
            await bot.send_poll(u[0], question=data['q'], options=options, type='quiz', correct_option_id=options.index(v3), is_anonymous=False)
            count += 1
        except: continue
    
    await message.answer(f"✅ Test saqlandi va {count} kishiga yuborildi.", reply_markup=main_menu(ADMIN_ID))
    await state.clear()

# --- ADMIN: RASSILKA ---
@dp.message(F.text == "Rassilka 📢", F.from_user.id == ADMIN_ID)
async def bc_type(message: types.Message):
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Oddiy xabar", callback_data="bc_msg"),
         InlineKeyboardButton(text="Test yuborish", callback_data="bc_test")]
    ])
    await message.answer("Rassilka turini tanlang:", reply_markup=ikb)

@dp.callback_query(F.data == "bc_msg")
async def bc_msg_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Xabarni yuboring:")
    await state.set_state(AdminStates.waiting_for_bc_msg)

@dp.message(AdminStates.waiting_for_bc_msg)
async def bc_msg_send(message: types.Message, state: FSMContext):
    cursor.execute("SELECT user_id FROM users")
    users = [u[0] for u in cursor.fetchall()]
    count = 0
    for uid in users:
        try:
            await message.copy_to(uid)
            count += 1
        except: continue
    await message.answer(f"✅ Xabar {count} kishiga yuborildi.")
    await state.clear()

# --- TESTLAR (FOYDALANUVCHI) ---
@dp.message(F.text == "Testlar 📝")
async def user_test(message: types.Message):
    u_id = message.from_user.id
    cursor.execute("SELECT * FROM tests WHERE id NOT IN (SELECT test_id FROM solved_tests WHERE user_id=?)", (u_id,))
    available = cursor.fetchall()
    
    if not available:
        await message.answer("🎉 Tabriklayman, hamma testlarni yechib bo'ldingiz, yangi test ertaga qo'shiladi.")
        return

    t = random.choice(available)
    options = [t[2], t[3], t[4]]
    correct = t[4]
    random.shuffle(options)
    
    # Keshga test_id ni saqlash (PollAnswer bilan tekshirish uchun)
    await bot.send_poll(u_id, question=t[1], options=options, type='quiz', correct_option_id=options.index(correct), is_anonymous=False)

# --- SO'Z OMBORI ---
@dp.message(F.text == "So'z ombori 📚")
async def word_ombor(message: types.Message, state: FSMContext):
    await message.answer("Bu yerga siz yodlagan so'zingizni yozasiz, bot saqlab qoladi!!!\n"
                         "Format:\napple\nBook\nSummer", reply_markup=word_menu())
    await state.set_state(Form.waiting_for_words)

@dp.message(Form.waiting_for_words, F.text != "Orqaga 🔙")
async def save_words(message: types.Message):
    if message.text in ["Umumiy so'zlar soni 📊", "So'zni o'chirish 🗑"]: return
    
    words = message.text.split('\n')
    added = 0
    for w in words:
        if w.strip():
            cursor.execute("INSERT OR IGNORE INTO words (user_id, word) VALUES (?, ?)", (message.from_user.id, w.strip()))
            if cursor.rowcount > 0: added += 1
    conn.commit()
    await message.answer(f"✅ {added} ta yangi so'z saqlandi.")

@dp.message(F.text == "Umumiy so'zlar soni 📊")
async def word_count(message: types.Message):
    cursor.execute("SELECT COUNT(*) FROM words WHERE user_id=?", (message.from_user.id,))
    await message.answer(f"📊 Jami so'zlaringiz: {cursor.fetchone()[0]} ta")

@dp.message(F.text == "Orqaga 🔙")
async def go_back(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Asosiy menyu:", reply_markup=main_menu(message.from_user.id))

# --- ISHGA TUSHIRISH ---
async def main():
    restore_users()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())