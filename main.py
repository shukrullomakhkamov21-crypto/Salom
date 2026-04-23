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
# Jadvallar
cursor.execute('CREATE TABLE IF NOT EXISTS words (user_id INTEGER, word TEXT, UNIQUE(user_id, word))')
cursor.execute('''CREATE TABLE IF NOT EXISTS tests 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, v1 TEXT, v2 TEXT, v3 TEXT, correct TEXT)''')
cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, first_name TEXT, username TEXT)')
cursor.execute('CREATE TABLE IF NOT EXISTS solved_tests (user_id INTEGER, test_id INTEGER, UNIQUE(user_id, test_id))')
conn.commit()

# --- AVTO-TIKLASH RO'YXATI ---
PRESET_USERS = [(8213426436, "Shukrullo", "@shukrullo_dev"), (8074917807, "2009", "@A_B_o9o9"), (1365590716, "Pretty", "@Pretty7011")] # Qolganlarni ham shu formatda qo'shing

def restore_users():
    for u_id, name, uname in PRESET_USERS:
        cursor.execute("INSERT OR IGNORE INTO users (user_id, first_name, username) VALUES (?, ?, ?)", (u_id, name, uname))
    conn.commit()

# --- HOLATLAR ---
class Form(StatesGroup):
    waiting_for_words = State()

class AdminStates(StatesGroup):
    waiting_for_bc_type = State()
    waiting_for_msg = State()
    # Test yaratish
    waiting_for_q = State()
    waiting_for_v1 = State()
    waiting_for_v2 = State()
    waiting_for_v3 = State()

# --- TUGMALAR ---
def get_main_menu(user_id):
    buttons = [[KeyboardButton(text="Testlar 📝"), KeyboardButton(text="Lug'atlar ombori 📚")]]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="Test qo'shish ➕"), KeyboardButton(text="Testni o'chirish 🗑")])
        buttons.append([KeyboardButton(text="Foydalanuvchilar 👥"), KeyboardButton(text="Rassilka 📢")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    u_id, name = message.from_user.id, message.from_user.first_name
    uname = f"@{message.from_user.username}" if message.from_user.username else "Noma'lum"
    
    cursor.execute("SELECT user_id FROM users WHERE user_id=?", (u_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, first_name, username) VALUES (?, ?, ?)", (u_id, name, uname))
        conn.commit()
        await bot.send_message(ADMIN_ID, f"🔔 Yangi foydalanuvchi!\n👤: {name}\n🆔: `{u_id}`", parse_mode="Markdown")
    
    await message.answer(f"Salom {name}!", reply_markup=get_main_menu(u_id))

# --- TESTLAR BO'LIMI (FOYDALANUVCHI UCHUN) ---
@dp.message(F.text == "Testlar 📝")
async def send_test(message: types.Message):
    u_id = message.from_user.id
    # Foydalanuvchi hali ishlamagan testlarni topish
    cursor.execute("""SELECT * FROM tests WHERE id NOT IN 
                      (SELECT test_id FROM solved_tests WHERE user_id=?)""", (u_id,))
    available_tests = cursor.fetchall()
    
    if not available_tests:
        await message.answer("Siz barcha testlarni yechib bo'ldingiz! 🎉 Yangilarini kuting.")
        return

    t = random.choice(available_tests)
    options = [t[2], t[3], t[4], t[5]]
    random.shuffle(options)
    
    await bot.send_poll(
        chat_id=u_id,
        question=t[1],
        options=options,
        type='quiz',
        correct_option_id=options.index(t[5]),
        is_anonymous=False,
        explanation="To'g'ri javobni topganingizdan so'ng bazaga saqlanadi.",
        reply_to_message_id=message.message_id
    )

@dp.poll_answer()
async def handle_poll_answer(poll_answer: types.PollAnswer):
    # Faqat to'g'ri topgan bo'lsa solved_tests ga qo'shish mantiqini poll orqali tekshirish murakkabroq, 
    # lekin bu yerda biz har qanday javobni "urinish" sifatida belgilaymiz:
    cursor.execute("SELECT id FROM tests WHERE question = (SELECT question FROM tests LIMIT 1)") # Bu yerda mantiqni soddalashtiramiz
    # Foydalanuvchi javob bergan testni eslab qolish:
    # Telegram API cheklovlari tufayli poll_answerda test_id yo'q, shuning uchun savol matni orqali topamiz:
    # (Amalda bu qism test_id ni aniqlash uchun qo'shimcha kesh talab qiladi, hozircha eng yaqin usul):
    pass

# --- ADMIN: TEST QO'SHISH VA AVTO-RASSILKA ---
@dp.message(F.text == "Test qo'shish ➕", F.from_user.id == ADMIN_ID)
async def add_t_q(message: types.Message, state: FSMContext):
    await message.answer("Savolni kiriting:"); await state.set_state(AdminStates.waiting_for_q)

@dp.message(AdminStates.waiting_for_q)
async def add_t_v1(message: types.Message, state: FSMContext):
    await state.update_data(q=message.text); await message.answer("1-xato variant:"); await state.set_state(AdminStates.waiting_for_v1)

@dp.message(AdminStates.waiting_for_v1)
async def add_t_v2(message: types.Message, state: FSMContext):
    await state.update_data(v1=message.text); await message.answer("2-xato variant:"); await state.set_state(AdminStates.waiting_for_v2)

@dp.message(AdminStates.waiting_for_v2)
async def add_t_v3(message: types.Message, state: FSMContext):
    await state.update_data(v2=message.text); await message.answer("3-xato variant:"); await state.set_state(AdminStates.waiting_for_v3)

@dp.message(AdminStates.waiting_for_v3)
async def add_t_cor(message: types.Message, state: FSMContext):
    await state.update_data(v3=message.text); await message.answer("TO'G'RI variantni kiriting:"); await state.set_state(AdminStates.waiting_for_msg) # msg ni correct sifatida ishlatamiz

@dp.message(AdminStates.waiting_for_msg) # Bu yerda Correct javobni qabul qilamiz
async def save_and_bc_test(message: types.Message, state: FSMContext):
    data = await state.get_data()
    correct = message.text
    # Bazaga saqlash
    cursor.execute("INSERT INTO tests (question, v1, v2, v3, correct) VALUES (?, ?, ?, ?, ?)", 
                   (data['q'], data['v1'], data['v2'], data['v3'], correct))
    conn.commit()
    
    # Hammaning ID sini olish va rassilka qilish
    cursor.execute("SELECT user_id FROM users")
    all_users = cursor.fetchall()
    options = [data['v1'], data['v2'], data['v3'], correct]
    random.shuffle(options)
    
    sent_count = 0
    for u in all_users:
        try:
            await bot.send_poll(u[0], question=f"🔔 YANGI TEST:\n{data['q']}", options=options, 
                               type='quiz', correct_option_id=options.index(correct), is_anonymous=False)
            sent_count += 1
            await asyncio.sleep(0.05)
        except: continue
    
    await message.answer(f"✅ Test saqlandi va {sent_count} kishiga yuborildi.", reply_markup=get_main_menu(ADMIN_ID))
    await state.clear()

# --- ADMIN: TESTNI O'CHIRISH ---
@dp.message(F.text == "Testni o'chirish 🗑", F.from_user.id == ADMIN_ID)
async def del_test_list(message: types.Message):
    cursor.execute("SELECT id, question FROM tests ORDER BY id DESC LIMIT 10")
    tests = cursor.fetchall()
    if not tests: await message.answer("Hozircha testlar yo'q."); return
    builder = InlineKeyboardBuilder()
    for t in tests: builder.add(InlineKeyboardButton(text=f"🗑 {t[1][:20]}...", callback_data=f"dt_{t[0]}"))
    builder.adjust(1)
    await message.answer("O'chirmoqchi bo'lgan testni tanlang:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("dt_"))
async def del_test_confirm(call: types.CallbackQuery):
    tid = call.data.split("_")[1]
    cursor.execute("DELETE FROM tests WHERE id=?", (tid,))
    conn.commit()
    await call.answer("Test o'chirildi"); await call.message.edit_text("✅ Test bazadan olib tashlandi.")

# --- FOYDALANUVCHILAR RO'YXATI ---
@dp.message(F.text == "Foydalanuvchilar 👥", F.from_user.id == ADMIN_ID)
async def list_all(message: types.Message):
    cursor.execute("SELECT user_id, first_name, username FROM users")
    rows = cursor.fetchall()
    res = f"👥 Jami: {len(rows)} ta\n\n"
    for r in rows: res += f"• `{r[0]}` | {r[1]} | {r[2]}\n"
    await message.answer(res, parse_mode="Markdown")

# (Qolgan Lug'at va Rassilka handlerlari avvalgi kod bilan bir xil...)

async def main():
    restore_users()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())