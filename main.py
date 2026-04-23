import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Bot tokeni
API_TOKEN = 'SIZNING_BOT_TOKENINGIZ'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Baza bilan ishlash
conn = sqlite3.connect('dictionary.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS words 
                  (user_id INTEGER, word TEXT, UNIQUE(user_id, word))''')
conn.commit()

# Tugmalar
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Yodlangan so'zlar 📚")]],
    resize_keyboard=True
)

inline_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="Lug'atlarni ko'rish 👁‍🗨", callback_data="show_list")]]
)

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Salom! So'zlarni yuboring, men ularni eslab qolaman.", reply_markup=main_keyboard)

@dp.message(F.text == "Yodlangan so'zlar 📚")
async def count_words(message: types.Message):
    cursor.execute("SELECT COUNT(*) FROM words WHERE user_id=?", (message.from_user.id,))
    count = cursor.fetchone()[0]
    await message.answer(f"📊 Sizning lug'atingizda jami {count} ta so'z bor.", reply_markup=inline_keyboard)

@dp.callback_query(F.data == "show_list")
async def show_list(callback: types.CallbackQuery):
    cursor.execute("SELECT word FROM words WHERE user_id=?", (callback.from_user.id,))
    rows = cursor.fetchall()
    
    if not rows:
        await callback.answer("Ro'yxat bo'sh!", show_alert=True)
        return

    res = "📖 Lug'atlar ro'yxati:\n\n"
    for i, row in enumerate(rows, 1):
        res += f"{i}. {row[0]}\n"
    
    await callback.message.answer(res)
    await callback.answer()

@dp.message()
async def add_words(message: types.Message):
    if not message.text: return
    
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
    await message.answer(f"✅ {added} ta yangi so'z qo'shildi.\n⚠️ {skipped} ta so'z avval bor edi.")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
