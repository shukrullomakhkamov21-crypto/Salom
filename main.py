import asyncio
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- SOZLAMALAR ---
API_TOKEN = '8750077178:AAFgDf_LDL11-cYvg_KGZUboTnkH-oWPFak' # <--- Bu yerga tokeningizni qo'ying

# Logging (Xatolarni ko'rish uchun)
logging.basicConfig(level=logging.INFO)

# Bot va Dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- BAZA BILAN ISHLASH ---
conn = sqlite3.connect('dictionary.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS words 
                  (user_id INTEGER, word TEXT, UNIQUE(user_id, word))''')
conn.commit()

# --- TUGMALAR ---
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Yodlangan so'zlar 📚")],
        [KeyboardButton(text="So'zni o'chirish 🗑")]
    ],
    resize_keyboard=True
)

# --- HANDLERLAR ---

# /start komandasi
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        f"Salom, {message.from_user.full_name}! 👋\n\n"
        "Men sizning shaxsiy lug'at botingizman. So'zlarni yuboring, men ularni eslab qolaman.\n"
        "O'chirmoqchi bo'lsangiz, tegishli tugmani bosing.",
        reply_markup=main_keyboard
    )

# So'zlar sonini ko'rish
@dp.message(F.text == "Yodlangan so'zlar 📚")
async def count_words(message: types.Message):
    cursor.execute("SELECT word FROM words WHERE user_id=? ORDER BY word ASC", (message.from_user.id,))
    rows = cursor.fetchall()
    
    if not rows:
        await message.answer("Sizning lug'atingiz hozircha bo'sh. 🧐")
        return

    count = len(rows)
    res = f"📊 Sizda jami {count} ta so'z bor:\n\n"
    
    # So'zlarni ro'yxat qilib chiqarish
    for i, row in enumerate(rows, 1):
        res += f"{i}. {row[0]}\n"
        # Telegram limiti 4096 belgi, shuni hisobga olamiz
        if len(res) > 3900:
            res += "\n...(ro'yxat davomi bor)"
            break
            
    await message.answer(res)

# O'chirish uchun tanlov menyusi
@dp.message(F.text == "So'zni o'chirish 🗑")
async def show_delete_options(message: types.Message):
    cursor.execute("SELECT word FROM words WHERE user_id=? ORDER BY word ASC", (message.from_user.id,))
    rows = cursor.fetchall()

    if not rows:
        await message.answer("O'chirish uchun birorta ham so'z topilmadi.")
        return

    builder = InlineKeyboardBuilder()
    for row in rows:
        # Har bir so'z uchun alohida tugma (callback_data orqali so'z nomi yuboriladi)
        builder.add(InlineKeyboardButton(
            text=f"❌ {row[0]}", 
            callback_data=f"del_{row[0]}"
        ))
    
    builder.adjust(2) # Tugmalarni 2 qatordan teradi
    await message.answer("O'chirmoqchi bo'lgan so'zingizni tanlang:", reply_markup=builder.as_markup())

# O'chirish tugmasi bosilganda
@dp.callback_query(F.data.startswith("del_"))
async def process_delete_callback(callback: types.CallbackQuery):
    word_to_delete = callback.data.split("_")[1]
    
    cursor.execute("DELETE FROM words WHERE user_id=? AND word=?", (callback.from_user.id, word_to_delete))
    conn.commit()
    
    await callback.answer(f"'{word_to_delete}' o'chirildi")
    
    # Ro'yxatni yangilash uchun xabarni tahrirlaymiz
    cursor.execute("SELECT word FROM words WHERE user_id=? ORDER BY word ASC", (callback.from_user.id,))
    rows = cursor.fetchall()

    if not rows:
        await callback.message.edit_text("Lug'at bo'shab qoldi.")
        return

    builder = InlineKeyboardBuilder()
    for row in rows:
        builder.add(InlineKeyboardButton(text=f"❌ {row[0]}", callback_data=f"del_{row[0]}"))
    builder.adjust(2)

    await callback.message.edit_text(
        f"✅ '{word_to_delete}' lug'atdan olib tashlandi. Yana o'chirasizmi?", 
        reply_markup=builder.as_markup()
    )

# Yangi so'z qo'shish (Xabar kelsa)
@dp.message()
async def add_words(message: types.Message):
    if not message.text: return
    
    # Bir nechta qator bo'lib kelsa, har birini alohida so'z deb olamiz
    lines = message.text.split('\n')
    added, skipped = 0, 0
    
    for line in lines:
        word = line.strip().lower()
        if word:
            try:
                cursor.execute("INSERT INTO words (user_id, word) VALUES (?, ?)", (message.from_user.id, word))
                added += 1
            except sqlite3.IntegrityError:
                skipped += 1
    
    conn.commit()
    
    msg = ""
    if added > 0: msg += f"✅ {added} ta so'z qo'shildi. "
    if skipped > 0: msg += f"⚠️ {skipped} ta so'z avval bor edi."
    
    if msg:
        await message.answer(msg)

# Botni ishga tushirish
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi")