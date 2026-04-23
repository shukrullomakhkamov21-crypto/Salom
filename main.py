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
cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, first_name TEXT, username TEXT)')
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
        buttons.append([KeyboardButton(text="Foydalanuvchilar 👥"), KeyboardButton(text="Rassilka 📢")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_vocab_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="So'z qo'shish ➕"), KeyboardButton(text="So'zlar soni 📊")],
            [KeyboardButton(text="So'zni o'chirish 🗑"), KeyboardButton(text="Orqaga ⬅️")]
        ],
        resize_keyboard=True
    )

# --- TEST YUBORISH FUNKSIYASI ---
async def send_random_test(message_or_query, is_new=True):
    cursor.execute("SELECT * FROM tests")
    tests = cursor.fetchall()
    
    is_callback = isinstance(message_or_query, types.CallbackQuery)
    target = message_or_query.message if is_callback else message_or_query

    if not tests:
        await target.answer("Hozircha testlar yo'q.")
        return

    # is_new=False bo'lsa, savolni o'zgartirmaslik kerak (lekin bu oddiy quiz bot, 
    # shuning uchun agar hato bo'lsa xabarni o'zgartirmaymiz)
    t = random.choice(tests)
    vars = [t[2], t[3], t[4]]
    random.shuffle(vars)
    
    builder = InlineKeyboardBuilder()
    for v in vars:
        builder.add(InlineKeyboardButton(text=v, callback_data=f"check_{t[0]}_{v}"))
    builder.adjust(1)
    
    text = f"📝 {t[1]}"
    if is_callback:
        await target.edit_text(text, reply_markup=builder.as_markup())
    else:
        await target.answer(text, reply_markup=builder.as_markup())

# --- ASOSIY HANDLERLAR ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = f"@{message.from_user.username}" if message.from_user.username else "Noma'lum"

    # Yangi foydalanuvchini tekshirish
    cursor.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    user_exists = cursor.fetchone()

    if not user_exists:
        cursor.execute("INSERT INTO users (user_id, first_name, username) VALUES (?, ?, ?)", 
                       (user_id, first_name, username))
        conn.commit()
        # Adminga xabar yuborish
        await bot.send_message(ADMIN_ID, f"🔔 **Yangi foydalanuvchi!**\n\n👤 Ism: {first_name}\n🆔 ID: {user_id}\n🔗 Username: {username}")

    await message.answer(f"Salom {first_name}!", reply_markup=get_main_menu(user_id))

@dp.message(F.text == "Testlar 📝")
async def start_testing(message: types.Message):
    await send_random_test(message)

@dp.callback_query(F.data.startswith("check_"))
async def check_ans(callback: types.CallbackQuery):
    _, tid, ans = callback.data.split("_")
    cursor.execute("SELECT correct FROM tests WHERE id=?", (tid,))
    correct = cursor.fetchone()[0]
    
    if ans == correct:
        await callback.answer("✅ To'g'ri!", show_alert=False)
        await send_random_test(callback) # To'g'ri bo'lsa keyingisi
    else:
        # Hato bo'lsa savol almashmaydi, faqat ogohlantirish beradi
        await callback.answer("❌ Noto'g'ri! Qayta urinib ko'ring.", show_alert=True)

# --- ADMIN: FOYDALANUVCHILAR ---
@dp.message(F.text == "Foydalanuvchilar 👥", F.from_user.id == ADMIN_ID)
async def list_users(message: types.Message):
    cursor.execute("SELECT first_name, username FROM users")
    rows = cursor.fetchall()
    if not rows:
        await message.answer("Foydalanuvchilar hali yo'q.")
        return
    
    text = f"👥 **Jami foydalanuvchilar:** {len(rows)} ta\n\n"
    for r in rows[:30]: # Dastlabki 30 tasini ko'rsatish
        text += f"• {r[0]} ({r[1]})\n"
    await message.answer(text)

# --- LUG'ATLAR OMBORI ---
@dp.message(F.text == "Lug'atlar ombori 📚")
async def vocab_home(message: types.Message):
    await message.answer("Lug'atlar bo'limi:", reply_markup=get_vocab_menu())

@dp.message(F.text == "Orqaga ⬅️")
async def go_back(message: types.Message):
    await message.answer("Asosiy menyu:", reply_markup=get_main_menu(message.from_user.id))

@dp.message(F.text == "So'z qo'shish ➕")
async def add_words_start(message: types.Message, state: FSMContext):
    await message.answer("So'zlarni kiriting (har birini yangi qatordan):")
    await state.set_state(Form.waiting_for_words)

@dp.message(Form.waiting_for_words)
async def process_multi_words(message: types.Message, state: FSMContext):
    if message.text in ["Orqaga ⬅️", "So'zlar soni 📊", "So'zni o'chirish 🗑"]:
        await state.clear()
        return
    raw_text = message.text.strip().split('\n')
    added = 0
    for line in raw_text:
        word = line.strip().lower()
        if word:
            try:
                cursor.execute("INSERT INTO words (user_id, word) VALUES (?, ?)", (message.from_user.id, word))
                added += 1
            except: continue
    conn.commit()
    await message.answer(f"✅ {added} ta qo'shildi.", reply_markup=get_vocab_menu())
    await state.clear()

# --- QOLGAN ADMIN FUNKSIYALARI (TEST QO'SHISH/O'CHIRISH/RASSILKA) ---
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

@dp.message(F.text == "Testni o'chirish 🗑", F.from_user.id == ADMIN_ID)
async def show_tests_to_delete(message: types.Message):
    cursor.execute("SELECT id, question FROM tests")
    rows = cursor.fetchall()
    if not rows:
        await message.answer("Testlar yo'q.")
        return
    builder = InlineKeyboardBuilder()
    for r in rows:
        builder.add(InlineKeyboardButton(text=f"🗑 {r[1][:20]}...", callback_data=f"dt_{r[0]}"))
    builder.adjust(1)
    await message.answer("O'chirish uchun tanlang:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("dt_"))
async def delete_test_callback(callback: types.CallbackQuery):
    tid = callback.data.split("_")[1]
    cursor.execute("DELETE FROM tests WHERE id=?", (tid,))
    conn.commit()
    await callback.answer("O'chirildi")
    await callback.message.edit_text("✅ Test olib tashlandi.")

@dp.message(F.text == "Rassilka 📢", F.from_user.id == ADMIN_ID)
async def bc_start(message: types.Message, state: FSMContext):
    await message.answer("Xabarni yozing:")
    await state.set_state(Broadcast.waiting_for_msg)

@dp.message(Broadcast.waiting_for_msg)
async def bc_send(message: types.Message, state: FSMContext):
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    for u in users:
        try: await bot.send_message(u[0], message.text)
        except: continue
    await message.answer("📢 Yuborildi.", reply_markup=get_main_menu(ADMIN_ID))
    await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())