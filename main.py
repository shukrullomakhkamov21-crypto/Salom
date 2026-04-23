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

# --- HOLATLAR ---
class Form(StatesGroup):
    waiting_for_words = State() # Ko'p so'zlar uchun holat

class TestCreate(StatesGroup):
    waiting_for_question = State()
    waiting_for_v1 = State()
    waiting_for_v2 = State()
    waiting_for_v3 = State()

# --- TUGMALAR ---
def get_main_menu(user_id):
    buttons = [[KeyboardButton(text="Testlar 📝"), KeyboardButton(text="Lug'atlar ombori 📚")]]
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
    await message.answer("Xush kelibsiz! Bo'limni tanlang:", reply_markup=get_main_menu(message.from_user.id))

# --- LUG'ATLAR OMBORI ---
@dp.message(F.text == "Lug'atlar ombori 📚")
async def vocab_home(message: types.Message):
    await message.answer("Lug'atlar bo'limi. Tanlang:", reply_markup=get_vocab_menu())

@dp.message(F.text == "Orqaga ⬅️")
async def go_back(message: types.Message):
    await message.answer("Asosiy menyu:", reply_markup=get_main_menu(message.from_user.id))

# --- BIRDANIGA KO'P SO'Z QO'SHISH ---
@dp.message(F.text == "So'z qo'shish ➕")
async def add_words_start(message: types.Message, state: FSMContext):
    await message.answer(
        "So'zlarni kiriting. Bir nechta so'zni birdaniga qo'shish uchun har birini yangi qatordan yozing.\n\n"
        "Masalan:\nApple\nBook\nComputer"
    )
    await state.set_state(Form.waiting_for_words)

@dp.message(Form.waiting_for_words)
async def process_multi_words(message: types.Message, state: FSMContext):
    raw_text = message.text.strip().split('\n') # Xabarni qatorlarga bo'lamiz
    added_count = 0
    skipped_count = 0
    
    for line in raw_text:
        word = line.strip().lower()
        if word:
            try:
                cursor.execute("INSERT INTO words (user_id, word) VALUES (?, ?)", (message.from_user.id, word))
                added_count += 1
            except sqlite3.IntegrityError:
                skipped_count += 1
    
    conn.commit()
    
    result_msg = f"Natija:\n✅ {added_count} ta yangi so'z qo'shildi."
    if skipped_count > 0:
        result_msg += f"\n⚠️ {skipped_count} ta so'z ro'yxatda borligi uchun tashlab ketildi."
        
    await message.answer(result_msg, reply_markup=get_vocab_menu())
    await state.clear()

# --- SO'ZLAR SONI VA O'CHIRISH (AVVALGI KODDAGIDEK) ---
@dp.message(F.text == "So'zlar soni 📊")
async def count_words(message: types.Message):
    cursor.execute("SELECT word FROM words WHERE user_id=?", (message.from_user.id,))
    rows = cursor.fetchall()
    if not rows:
        await message.answer("Lug'atingiz bo'sh.")
    else:
        text = f"Sizda {len(rows)} ta yodlangan so'z bor. Oxirgi 30 tasi:\n\n"
        text += "\n".join([f"• {r[0]}" for r in rows[-30:]])
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
    await callback.message.delete()
    await callback.message.answer(f"✅ '{word}' lug'atdan olib tashlandi.")

# --- TESTLAR BO'LIMI VA ADMIN (O'ZGARISHSIZ QOLADI) ---
# ... (Yuqoridagi koddagi testlar va admin qismini shu yerga qo'shing)

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
