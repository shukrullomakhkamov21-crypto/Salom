import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# --- SOZLAMALAR ---
API_TOKEN = '8750077178:AAFgDf_LDL11-cYvg_KGZUboTnkH-oWPFak'
ADMIN_ID = 8213426436  # Sizning ID raqamingiz o'rnatildi
users = set()  # Foydalanuvchilar bazasi

class BotStates(StatesGroup):
    waiting_for_broadcast = State()  # Rassilka xabarini kutish
    waiting_for_receipt = State()    # Chek rasmiga kutish

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- START KOMANDASI ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    users.add(message.from_user.id)
    kb = [
        [types.KeyboardButton(text="🍅 Pomidor Taymer sotib olish (50 somoni)")],
        [types.KeyboardButton(text="ℹ️ Yordam")]
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Xush kelibsiz! Bee School botiga xush kelibsiz. 🐝\n\nBu yerda siz foydali o'quv qurollarini sotib olishingiz mumkin.", reply_markup=keyboard)

# --- RASSILKA (FAQAT SIZ UCHUN) ---
@dp.message(Command("rassilka"), F.from_user.id == ADMIN_ID)
async def start_broadcast(message: types.Message, state: FSMContext):
    await message.answer("Hamma foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yuboring (matn, rasm yoki fayl):")
    await state.set_state(BotStates.waiting_for_broadcast)

@dp.message(BotStates.waiting_for_broadcast, F.from_user.id == ADMIN_ID)
async def do_broadcast(message: types.Message, state: FSMContext):
    count = 0
    for user_id in users:
        try:
            await message.copy_to(chat_id=user_id)
            count += 1
        except:
            pass
    await message.answer(f"Xabar {count} ta foydalanuvchiga yuborildi. ✅")
    await state.clear()

# --- TO'LOV JARAYONI ---
@dp.message(F.text == "🍅 Pomidor Taymer sotib olish (50 somoni)")
async def buy_timer(message: types.Message, state: FSMContext):
    payment_info = (
        "To'lovni amalga oshirish uchun:\n\n"
        "💳 Karta: 4444 4444 4444 4444 (Eskhata Visa)\n"
        "💰 Summa: 50 somoni\n\n"
        "To'lovdan so'ng, chekni (skrinshotni) shu yerga rasm ko'rinishida yuboring!"
    )
    await message.answer(payment_info)
    await state.set_state(BotStates.waiting_for_receipt)

# --- CHEKNI QABUL QILISH VA SIZGA YUBORISH ---
@dp.message(BotStates.waiting_for_receipt, F.photo)
async def handle_receipt(message: types.Message, state: FSMContext):
    await message.answer("Rahmat! Chek adminga yuborildi. Tasdiqlangach, mahsulot yuboriladi.")
    
    # Sizga (Adminga) tasdiqlash tugmasi bilan boradi
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Tasdiqlash (Fayl yuborish)", callback_data=f"accept_{message.from_user.id}")]
    ])
    
    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=message.photo[-1].file_id,
        caption=f"🔔 Yangi to'lov!\nFoydalanuvchi: @{message.from_user.username}\nID: {message.from_user.id}",
        reply_markup=kb
    )
    await state.clear()

# --- SIZ TASDIQLASANGIZ FAYL KETADI ---
@dp.callback_query(F.data.startswith("accept_"))
async def approve_payment(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    await bot.send_message(user_id, "Sizning to'lovingiz tasdiqlandi! ✅\n\nMana sizning faylingiz:")
    
    # Faylni yuborish qismi (o'zingizni faylingiz havolasini qo'ying)
    await bot.send_document(
        chat_id=user_id,
        document="https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
        caption="Pomodoro o'quv qo'llanmasi. 🍅"
    )
    await callback.answer("Foydalanuvchiga fayl yuborildi!")
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ TASTIQLANDI")

# --- ISHGA TUSHIRISH ---
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.error("Bot to'xtatildi!")
