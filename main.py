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
cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)')
conn.commit()

# --- HOLATLAR (FSM) ---
class Form(StatesGroup):
    waiting_for_words = State()

class TestCreate(StatesGroup):
    waiting_for_question = State()
    waiting_for_v1 = State()
    waiting_for_v2 = State()
    waiting_for_v3 = State()

class Broadcast(StatesGroup):
    waiting_for_msg = State()

# --- TUGMALAR ---
def get_main_menu(user_id):
    buttons = [[KeyboardButton(text="Testlar 📝"), KeyboardButton(text="Lug'atlar ombori 📚")]]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="Test qo'shish ➕"), KeyboardButton(text="Testni o'chirish 🗑")])
        buttons.append([KeyboardButton(text="Rassilka 📢")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_vocab_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="So'z qo'shish ➕"), KeyboardButton(text="So'zlar soni 📊")],
            [KeyboardButton(text="So'zni o'chirish 🗑"), KeyboardButton(text="Orqaga ⬅️")]
        ],
        resize_keyboard=True
    )

# --- ASOSIY HANDLERLAR ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    await message.answer(f"Salom {message.from_user.first_name}! Bo'limni tanlang:", 
                         reply_markup=get_main_menu(message.from_user.id))

# --- LUG'ATLAR OMBORI ---
@dp.message(F.text == "Lug'atlar ombori 📚")
async def vocab_home(message: types.Message):
    await message.answer("Lug'atlar bo'limi. Tanlang:", reply_markup=get_vocab_menu())

@dp.message(F.text == "Orqaga ⬅️")
async def go_back(message: types.Message):
    await message.answer("Asosiy menyu:", reply_markup=get_main_menu(message.from_user.id))

@dp.message(F.text == "So'z qo'shish ➕")
async def add_words_start(message: types.Message, state: FSMContext):
    await message.answer("So'zlarni kiriting (Bir nechta bo'lsa har birini yangi qatordan yozing):")
    await state.set_state(Form.waiting_for_words)

@dp.message(Form.waiting_for_words)
async def process_multi_words(message: types.Message, state: FSMContext):
    if message.text in ["Orqaga ⬅️", "So'zlar soni 📊", "So'zni o'chirish 🗑", "Testlar 📝", "Lug'atlar ombori 📚"]:
        await state.clear()
        return

    raw_text = message.text.strip().split('\n')
    added, skipped = 0, 0
    for line in raw_text:
        word = line.strip().lower()
        if word:
            try:
                cursor.execute("INSERT INTO words (user_id, word) VALUES (?, ?)", (message.from_user.id, word))
                added += 1
            except sqlite3.IntegrityError:
                skipped += 1
    conn.commit()
    await message.answer(f"✅ {added} ta qo'shildi. ⚠️ {skipped} ta bor edi.", reply_markup=get_vocab_menu())
    await state.clear()

@dp.message(F.text == "So'zlar soni 📊")
async def count_words(message: types.Message):
    cursor.execute("SELECT word FROM words WHERE user_id=?", (message.from_user.id,))
    rows = cursor.fetchall()
    if not rows:
        await message.answer("Lug'at bo'sh.")
    else:
        text = f"Jami: {len(rows)} ta so'z.\n\n" + "\n".join([f"• {r[0]}" for r in rows[-20:]])
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
    await message.answer("O'chirish uchun tanlang:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("del_"))
async def delete_call(callback: types.CallbackQuery):
    word = callback.data.split("_")[1]
    cursor.execute("DELETE FROM words WHERE user_id=? AND word=?", (callback.from_user.id, word))
    conn.commit()
    await callback.answer(f"{word} o'chirildi")
    await callback.message.answer(f"🗑 '{word}' olib tashlandi.")

# --- TESTLAR BO'LIMI ---
@dp.message(F.text == "Testlar 📝")
async def send_test(message: types.Message):
    cursor.execute("SELECT * FROM tests")
    tests = cursor.fetchall()
    if not tests:
        await message.answer("Hozircha testlar yo'q.")
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
        await callback.message.edit_text(f"✅ To'g'ri! Javob: {correct}")
    else:
        await callback.answer(f"❌ Noto'g'ri variant!", show_alert=True)

# --- ADMIN: TEST QO'SHISH ---
@dp.message(F.text == "Test qo'shish ➕", F.from_user.id == ADMIN_ID)
async def t_start(message: types.Message, state: FSMContext):
    await message.answer("Savolni kiriting:")
    await state.set_state(TestCreate.waiting_for_question)

@dp.message(TestCreate.waiting_for_question)
async def t_v1(message: types.Message, state: FSMContext):
    await state.update_data(q=message.text)
    await message.answer("1-noto'g'ri variant:")
    await state.set_state(TestCreate.waiting_for_v1)

@dp.message(TestCreate.waiting_for_v1)
async def t_v2(message: types.Message, state: FSMContext):
    await state.update_data(v1=message.text)
    await message.answer("2-noto'g'ri variant:")
    await state.set_state(TestCreate.waiting_for_v2)

@dp.message(TestCreate.waiting_for_v2)
async def t_v3(message: types.Message, state: FSMContext):
    await state.update_data(v2=message.text)
    await message.answer("3-TO'G'RI variant:")
    await state.set_state(TestCreate.waiting_for_v3)

@dp.message(TestCreate.waiting_for_v3)
async def t_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute("INSERT INTO tests (question, v1, v2, v3, correct) VALUES (?,?,?,?,?)",
                   (data['q'], data['v1'], data['v2'], message.text, message.text))
    conn.commit()
    await message.answer("✅ Test saqlandi!", reply_markup=get_main_menu(ADMIN_ID))
    await state.clear()

# --- ADMIN: TESTNI O'CHIRISH ---
@dp.message(F.text == "Testni o'chirish 🗑", F.from_user.id == ADMIN_ID)
async def show_tests_to_delete(message: types.Message):
    cursor.execute("SELECT id, question FROM tests")
    rows = cursor.fetchall()
    if not rows:
        await message.answer("O'chirish uchun testlar yo'q.")
        return
    builder = InlineKeyboardBuilder()
    for r in rows:
        short_q = (r[1][:20] + '...') if len(r[1]) > 20 else r[1]
        builder.add(InlineKeyboardButton(text=f"🗑 {short_q}", callback_data=f"deltest_{r[0]}"))
    builder.adjust(1)
    await message.answer("O'chirmoqchi bo'lgan testni tanlang:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("deltest_"))
async def delete_test_callback(callback: types.CallbackQuery):
    test_id = callback.data.split("_")[1]
    cursor.execute("DELETE FROM tests WHERE id=?", (test_id,))
    conn.commit()
    await callback.answer("Test o'chirildi")
    await callback.message.edit_text("✅ Tanlangan test bazadan olib tashlandi.")

# --- ADMIN: RASSILKA ---
@dp.message(F.text == "Rassilka 📢", F.from_user.id == ADMIN_ID)
async def bc_start(message: types.Message, state: FSMContext):
    await message.answer("Yubormoqchi bo'lgan xabaringizni yozing:")
    await state.set_state(Broadcast.waiting_for_msg)

@dp.message(Broadcast.waiting_for_msg)
async def bc_send(message: types.Message, state: FSMContext):
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    count = 0
    for u in users:
        try:
            await bot.send_message(u[0], message.text)
            count += 1
        except: continue
    await message.answer(f"📢 {count} ta odamga yuborildi.", reply_markup=get_main_menu(ADMIN_ID))
    await state.clear()

# --- MAIN ---
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass