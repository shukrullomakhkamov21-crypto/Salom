import asyncio
import sqlite3
import random
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- SOZLAMALAR ---
API_TOKEN = '8750077178:AAFgDf_LDL11-cYvg_KGZUboTnkH-oWPFak'
ADMIN_ID = 8213426436 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- BAZA BILAN ISHLASH ---
conn = sqlite3.connect('main_database.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS words (user_id INTEGER, word TEXT, UNIQUE(user_id, word))')
cursor.execute('''CREATE TABLE IF NOT EXISTS tests 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, v1 TEXT, v2 TEXT, v3 TEXT, correct TEXT)''')
cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id PRIMARY KEY)')
conn.commit()

# --- HOLATLAR (FSM) ---
class Form(StatesGroup):
    waiting_for_word = State() # Lug'atga so'z qo'shish holati

class TestCreate(StatesGroup): # Admin uchun test qo'shish holatlari
    waiting_for_question = State()
    waiting_for_v1 = State()
    waiting_for_v2 = State()
    waiting_for_v3 = State()

# --- TUGMALAR ---
def get_main_menu(user_id):
    buttons = [
        [KeyboardButton(text="Testlar 📝"), KeyboardButton(text="Lug'atlar ombori 📚")]
    ]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="Test qo'shish ➕"), KeyboardButton(text="Rassilka 📢")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_vocab_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="So'z qo'shish ➕"), KeyboardButton(text="So'zlar soni 📊")],
            [KeyboardButton(text="So'zni o'chirish 🗑"), KeyboardButton(text="Orqaga ⬅️")]
        ],
        resize_keyboard=True
    )

# --- START ---
@dp.message(Command("start"))
async def start(message: types.Message):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    await message.answer(f"Salom {message.from_user.first_name}! Bo'limni tanlang:", reply_markup=get_main_menu(message.from_user.id))

# --- LUG'ATLAR OMBORI ---
@dp.message(F.text == "Lug'atlar ombori 📚")
async def vocab_home(message: types.Message):
    await message.answer("Lug'atlar bo'limi. Tanlang:", reply_markup=get_vocab_menu())

@dp.message(F.text == "Orqaga ⬅️")
async def go_back(message: types.Message):
    await message.answer("Asosiy menyu:", reply_markup=get_main_menu(message.from_user.id))

# SO'Z QO'SHISH (FSM BOSHLANISHI)
@dp.message(F.text == "So'z qo'shish ➕")
async def add_word_start(message: types.Message, state: FSMContext):
    await message.answer("So'zni kiriting:")
    await state.set_state(Form.waiting_for_word)

@dp.message(Form.waiting_for_word)
async def process_word_add(message: types.Message, state: FSMContext):
    word_text = message.text.strip().lower()
    user_id = message.from_user.id
    
    try:
        cursor.execute("INSERT INTO words (user_id, word) VALUES (?, ?)", (user_id, word_text))
        conn.commit()
        await message.answer(f"✅ '{word_text}' lug'atingizga qo'shildi!")
    except sqlite3.IntegrityError:
        await message.answer(f"⚠️ Bu so'z allaqachon kiritilgan!")
    
    await state.clear() # Holatni yakunlash (menyuga qaytish uchun)

@dp.message(F.text == "So'zlar soni 📊")
async def count_words(message: types.Message):
    cursor.execute("SELECT word FROM words WHERE user_id=?", (message.from_user.id,))
    rows = cursor.fetchall()
    count = len(rows)
    if count == 0:
        await message.answer("Siz hali so'z qo'shmagansiz.")
    else:
        text = f"Sizda {count} ta yodlangan so'z bor:\n\n"
        text += "\n".join([f"• {r[0]}" for r in rows[-20:]]) # Oxirgi 20tasini ko'rsatadi
        await message.answer(text)

@dp.message(F.text == "So'zni o'chirish 🗑")
async def delete_word_list(message: types.Message):
    cursor.execute("SELECT word FROM words WHERE user_id=?", (message.from_user.id,))
    rows = cursor.fetchall()
    if not rows:
        await message.answer("O'chirishga so'z yo'q.")
        return
    builder = InlineKeyboardBuilder()
    for r in rows:
        builder.add(InlineKeyboardButton(text=f"❌ {r[0]}", callback_data=f"del_{r[0]}"))
    builder.adjust(2)
    await message.answer("O'chirmoqchi bo'lgan so'zni tanlang:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("del_"))
async def delete_call(callback: types.CallbackQuery):
    word = callback.data.split("_")[1]
    cursor.execute("DELETE FROM words WHERE user_id=? AND word=?", (callback.from_user.id, word))
    conn.commit()
    await callback.answer(f"{word} o'chirildi")
    await callback.message.answer(f"🗑 '{word}' lug'atdan olib tashlandi.")
    # Ro'yxatni yangilab qayta ko'rsatish mumkin

# --- ADMIN: TEST QO'SHISH BOSQICHLARI ---
@dp.message(F.text == "Test qo'shish ➕", F.from_user.id == ADMIN_ID)
async def t_q(message: types.Message, state: FSMContext):
    await message.answer("Test savolini kiriting:")
    await state.set_state(TestCreate.waiting_for_question)

@dp.message(TestCreate.waiting_for_question)
async def t_v1(message: types.Message, state: FSMContext):
    await state.update_data(q=message.text)
    await message.answer("1-variantni (noto'g'ri) kiriting:")
    await state.set_state(TestCreate.waiting_for_v1)

@dp.message(TestCreate.waiting_for_v1)
async def t_v2(message: types.Message, state: FSMContext):
    await state.update_data(v1=message.text)
    await message.answer("2-variantni (noto'g'ri) kiriting:")
    await state.set_state(TestCreate.waiting_for_v2)

@dp.message(TestCreate.waiting_for_v2)
async def t_v3(message: types.Message, state: FSMContext):
    await state.update_data(v2=message.text)
    await message.answer("3-variantni (TO'G'RI javobni) kiriting:")
    await state.set_state(TestCreate.waiting_for_v3)

@dp.message(TestCreate.waiting_for_v3)
async def t_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute("INSERT INTO tests (question, v1, v2, v3, correct) VALUES (?,?,?,?,?)",
                   (data['q'], data['v1'], data['v2'], message.text, message.text))
    conn.commit()
    await message.answer("✅ Test muvaffaqiyatli saqlandi!", reply_markup=get_main_menu(ADMIN_ID))
    await state.clear()

# --- TESTLARNI TOPSHIRISH ---
@dp.message(F.text == "Testlar 📝")
async def send_test(message: types.Message):
    cursor.execute("SELECT * FROM tests")
    tests = cursor.fetchall()
    if not tests:
        await message.answer("Hozircha testlar mavjud emas.")
        return
    t = random.choice(tests)
    vars = [t[2], t[3], t[4]]
    random.shuffle(vars)
    builder = InlineKeyboardBuilder()
    for v in vars:
        builder.add(InlineKeyboardButton(text=v, callback_data=f"check_{t[0]}_{v}"))
    builder.adjust(1)
    await message.answer(f"📝 {t[1]}", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("check_"))
async def check_ans(callback: types.CallbackQuery):
    _, tid, ans = callback.data.split("_")
    cursor.execute("SELECT correct FROM tests WHERE id=?", (tid,))
    correct = cursor.fetchone()[0]
    if ans == correct:
        await callback.message.edit_text(f"✅ Barakalla! To'g'ri javob: {correct}")
    else:
        await callback.answer(f"❌ Noto'g'ri variant!", show_alert=True)

# --- BOTNI ISHGA TUSHIRISH ---
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())