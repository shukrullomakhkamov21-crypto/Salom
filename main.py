import asyncio
import sqlite3
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- SOZLAMALAR ---
API_TOKEN = '8750077178:AAFgDf_LDL11-cYvg_KGZUboTnkH-oWPFak'
ADMIN_ID = 8213426436  # <--- O'zingizning ID raqamingizni yozing (BotFather'dan yoki @userinfobot orqali bilish mumkin)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- BAZA BILAN ISHLASH ---
conn = sqlite3.connect('main_data.db', check_same_thread=False)
cursor = conn.cursor()
# Lug'at jadvali
cursor.execute('CREATE TABLE IF NOT EXISTS words (user_id INTEGER, word TEXT, UNIQUE(user_id, word))')
# Testlar jadvali
cursor.execute('''CREATE TABLE IF NOT EXISTS tests 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, v1 TEXT, v2 TEXT, v3 TEXT, correct TEXT)''')
# Foydalanuvchilar jadvali (Rassilka uchun)
cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)')
conn.commit()

# --- HOLATLAR (FSM) ---
class TestCreate(StatesGroup):
    waiting_for_question = State()
    waiting_for_v1 = State()
    waiting_for_v2 = State()
    waiting_for_v3 = State()
    waiting_for_correct = State()

class Broadcast(StatesGroup):
    waiting_for_type = State()
    waiting_for_msg = State()

# --- TUGMALAR ---
def get_main_menu(user_id):
    buttons = [
        [KeyboardButton(text="Testlar 📝"), KeyboardButton(text="Lug'atlar ombori 📚")]
    ]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="Test qo'shish ➕"), KeyboardButton(text="Rassilka 📢")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def start(message: types.Message):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    await message.answer("Xush kelibsiz!", reply_markup=get_main_menu(message.from_user.id))

# --- TESTLARNI TOPSHIRISH ---
@dp.message(F.text == "Testlar 📝")
async def send_test(message: types.Message):
    cursor.execute("SELECT * FROM tests")
    all_tests = cursor.fetchall()
    if not all_tests:
        await message.answer("Hozircha testlar yo'q.")
        return
    
    test = random.choice(all_tests) # Tasodifiy test olish
    builder = InlineKeyboardBuilder()
    variants = [test[2], test[3], test[4]]
    random.shuffle(variants) # Variantlar o'rnini almashtirish
    
    for v in variants:
        builder.add(InlineKeyboardButton(text=v, callback_data=f"answer_{test[0]}_{v}"))
    
    builder.adjust(1)
    await message.answer(f"Savol: {test[1]}", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("answer_"))
async def check_answer(callback: types.CallbackQuery):
    _, test_id, user_answer = callback.data.split("_")
    cursor.execute("SELECT correct FROM tests WHERE id=?", (test_id,))
    correct_answer = cursor.fetchone()[0]
    
    if user_answer == correct_answer:
        await callback.message.edit_text(f"✅ To'g'ri! Javob: {correct_answer}\n\nKeyingi testni boshlash uchun 'Testlar 📝' tugmasini bosing.")
    else:
        await callback.answer(f"❌ Noto'g'ri. Bu: {user_answer} edi.", show_alert=True)

# --- ADMIN: TEST QO'SHISH ---
@dp.message(F.text == "Test qo'shish ➕", F.from_user.id == ADMIN_ID)
async def add_test_start(message: types.Message, state: FSMContext):
    await message.answer("Test savolini kiriting (Masalan: He is ____ to school):")
    await state.set_state(TestCreate.waiting_for_question)

@dp.message(TestCreate.waiting_for_question)
async def process_q(message: types.Message, state: FSMContext):
    await state.update_data(question=message.text)
    await message.answer("1-variantni kiriting:")
    await state.set_state(TestCreate.waiting_for_v1)

@dp.message(TestCreate.waiting_for_v1)
async def process_v1(message: types.Message, state: FSMContext):
    await state.update_data(v1=message.text)
    await message.answer("2-variantni kiriting:")
    await state.set_state(TestCreate.waiting_for_v2)

@dp.message(TestCreate.waiting_for_v2)
async def process_v2(message: types.Message, state: FSMContext):
    await state.update_data(v2=message.text)
    await message.answer("3-variantni kiriting (va bu to'g'ri javob bo'ladi):")
    await state.set_state(TestCreate.waiting_for_v3)

@dp.message(TestCreate.waiting_for_v3)
async def process_v3(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute("INSERT INTO tests (question, v1, v2, v3, correct) VALUES (?, ?, ?, ?, ?)",
                   (data['question'], data['v1'], data['v2'], message.text, message.text))
    conn.commit()
    await message.answer("✅ Test saqlandi!", reply_markup=get_main_menu(ADMIN_ID))
    await state.clear()

# --- ADMIN: RASSILKA ---
@dp.message(F.text == "Rassilka 📢", F.from_user.id == ADMIN_ID)
async def rassilka_start(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="📝 Test yuborish", callback_data="bc_test"))
    builder.add(InlineKeyboardButton(text="✉️ Oddiy xabar", callback_data="bc_msg"))
    await message.answer("Nima yubormoqchisiz?", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "bc_msg")
async def bc_msg(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Xabarni yozing:")
    await state.set_state(Broadcast.waiting_for_msg)

@dp.message(Broadcast.waiting_for_msg)
async def send_broadcast(message: types.Message, state: FSMContext):
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    count = 0
    for user in users:
        try:
            await bot.send_message(user[0], message.text)
            count += 1
        except: continue
    await message.answer(f"📢 {count} ta foydalanuvchiga yuborildi.")
    await state.clear()

# Lug'atlar ombori qismi avvalgi koddagidek qoladi... (joy tejash uchun qisqartirildi)

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())