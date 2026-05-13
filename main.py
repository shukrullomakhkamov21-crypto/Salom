import sqlite3
import logging
import pandas as pd
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- SOZLAMALAR h---
API_TOKEN = '8070963688:AAHdfx56F0syWuE5txVIVOPUWZHpi7DPwrQ'
SUPER_ADMIN_ID = 8213426436  # O'zingizning ID raqamingiz
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
scheduler = AsyncIOScheduler()

# --- MA'LUMOTLAR BAZASI ---
def init_db():
    conn = sqlite3.connect('ent_medical.db')
    cursor = conn.cursor()
    # Doktorlar: ID, Ism, Yo'nalish
    cursor.execute('''CREATE TABLE IF NOT EXISTS doctors 
                      (id INTEGER PRIMARY KEY, name TEXT, specialty TEXT)''')
    # Navbatlar: ID, UserID, UserName, DoktorID, Vaqt, Status
    cursor.execute('''CREATE TABLE IF NOT EXISTS appointments 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
                       user_name TEXT, doctor_id INTEGER, time TEXT, confirmed INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

init_db()

# --- ADMIN FUNKSIYALARI ---

@dp.message_handler(commands=['add_doc'])
async def add_doctor(message: types.Message):
    """Doktor qo'shish: /add_doc ID|Ism|Yo'nalish"""
    if message.from_user.id != SUPER_ADMIN_ID: return
    try:
        parts = message.get_args().split('|')
        doc_id, name, spec = int(parts[0]), parts[1], parts[2]
        conn = sqlite3.connect('ent_medical.db')
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO doctors VALUES (?, ?, ?)", (doc_id, name, spec))
        conn.commit()
        conn.close()
        await message.reply(f"✅ Doktor bazaga qo'shildi: {name}")
    except:
        await message.reply("Xato! Format: `/add_doc ID|Ism|Yo'nalish`")

@dp.message_handler(commands=['excel'])
async def export_to_excel(message: types.Message):
    """Hamma navbatlarni Excel qilib beradi"""
    if message.from_user.id != SUPER_ADMIN_ID: return
    
    conn = sqlite3.connect('ent_medical.db')
    df = pd.read_sql_query("""
        SELECT doctors.name as 'Doktor', appointments.user_name as 'Bemor', 
               appointments.time as 'Vaqt', doctors.specialty as 'Soha'
        FROM appointments 
        JOIN doctors ON appointments.doctor_id = doctors.id
    """, conn)
    conn.close()
    
    file_path = "hisobot.xlsx"
    df.to_excel(file_path, index=False)
    
    with open(file_path, "rb") as file:
        await message.answer_document(file, caption="📊 Klinika bo'yicha umumiy hisobot")

# --- DOKTOR FUNKSIYALARI ---

@dp.message_handler(commands=['my_clients'])
async def my_clients(message: types.Message):
    """Doktor o'z navbatlarini ko'rishi uchun"""
    doc_id = message.from_user.id
    conn = sqlite3.connect('ent_medical.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_name, time FROM appointments WHERE doctor_id=? AND confirmed=0", (doc_id,))
    data = cursor.fetchall()
    conn.close()
    
    if not data:
        await message.reply("Sizda hozircha faol navbatlar yo'q.")
        return
    
    text = "👨‍⚕️ Sizning bugungi bemorlaringiz:\n\n"
    for name, time in data:
        text += f"🕒 {time} | {name}\n"
    await message.reply(text)

# --- FOYDALANUVCHI (BEMOR) QISMI ---

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    conn = sqlite3.connect('ent_medical.db')
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT specialty FROM doctors")
    specs = cursor.fetchall()
    conn.close()
    
    kb = InlineKeyboardMarkup(row_width=2)
    for s in specs:
        kb.add(InlineKeyboardButton(text=s[0], callback_data=f"spec_{s[0]}"))
    
    await message.answer("🏥 **Ent Medical**\nYo'nalishni tanlang:", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data.startswith('spec_'))
async def show_docs(call: types.CallbackQuery):
    spec = call.data.split('_')[1]
    conn = sqlite3.connect('ent_medical.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM doctors WHERE specialty=?", (spec,))
    docs = cursor.fetchall()
    conn.close()
    
    kb = InlineKeyboardMarkup(row_width=2)
    for d in docs:
        kb.add(InlineKeyboardButton(text=d[1], callback_data=f"doc_{d[0]}"))
    await call.message.edit_text(f"👨‍⚕️ {spec} shifokorini tanlang:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('doc_'))
async def select_time(call: types.CallbackQuery):
    doc_id = call.data.split('_')[1]
    # Ish vaqtlari (Buni ham bazaga ulasa bo'ladi)
    times = ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00"]
    
    kb = InlineKeyboardMarkup(row_width=3)
    for t in times:
        kb.insert(InlineKeyboardButton(text=t, callback_data=f"book_{doc_id}_{t}"))
    await call.message.edit_text("Qulay vaqtni belgilang:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('book_'))
async def book_final(call: types.CallbackQuery):
    _, doc_id, time = call.data.split('_')
    user_id = call.from_user.id
    user_name = call.from_user.full_name

    conn = sqlite3.connect('ent_medical.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO appointments (user_id, user_name, doctor_id, time) VALUES (?, ?, ?, ?)", 
                   (user_id, user_name, doc_id, time))
    conn.commit()
    conn.close()

    await call.message.edit_text(f"✅ Navbat olindi!\nDoktorga xabar yuborildi.")
    
    # DOKTORGA XABAR
    confirm_kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Keldi", callback_data=f"confirm_{user_id}"))
    try:
        await bot.send_message(doc_id, f"🔔 Yangi bemor:\n👤 {user_name}\n🕒 Soat: {time}", reply_markup=confirm_kb)
    except:
        await bot.send_message(SUPER_ADMIN_ID, f"⚠️ Doktor (ID: {doc_id}) botni start qilmagan!")

@dp.callback_query_handler(lambda c: c.data.startswith('confirm_'))
async def confirm_visit(call: types.CallbackQuery):
    uid = call.data.split('_')[1]
    conn = sqlite3.connect('ent_medical.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE appointments SET confirmed=1 WHERE user_id=? AND confirmed=0", (uid,))
    conn.commit()
    conn.close()
    await call.message.edit_text("✅ Bemor kelgani tasdiqlandi.")
    await bot.send_message(uid, "Sizning kelganingiz tasdiqlandi. Salomat bo'ling!")

if __name__ == '__main__':
    scheduler.start()
    executor.start_polling(dp, skip_updates=True)