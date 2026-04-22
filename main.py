import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# --- SOZLAMALAR ---
API_TOKEN = '8750077178:AAFgDf_LDL11-cYvg_KGZUboTnkH-oWPFak'
ADMIN_ID = 8213426436  # Sizning Telegram ID raqamingiz
users = set()  # Foydalanuvchilar bazasi (bot o'chguncha saqlanadi)

class BotStates(StatesGroup):
    waiting_for_broadcast = State()  # Rassilka uchun
    waiting_for_receipt = State()    # Chek yuborish uchun

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
    welcome_text = (
        "Xush kelibsiz! Bee School botiga xush kelibsiz. 🐝\n\n"
        "Bu yerda siz o'qish uchun eng foydali materiallarni va "
        "Pomodoro taymerlarini sotib olishingiz mumkin."
    )
    await message.answer(welcome_text, reply_markup=keyboard)

# --- RASSILKA KOMANDASI (FAQAT SIZ UCHUN) ---
@dp.message(Command("rassilka"), F.from_user.id == ADMIN_ID)
async def start_broadcast(message: types.Message, state: FSMContext):
    await message.answer("Hamma foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yuboring (matn, rasm, video yoki fayl):")
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
        "💳 **Karta:** `4439 2000 2522 5029` (Eskhata Visa)\n"
        "👤 **Ism:** Mutabbarhon M.\n"
        "💰 **Summa:** 50 somoni\n\n"
        "⚠️ To'lovni amalga oshirgach, chekni (skrinshotni) shu yerga rasm ko'rinishida yuboring!"
    )
    await message.answer(payment_info, parse_mode="Markdown")
    await state.set_state(BotStates.waiting_for_receipt)

# --- CHEKNI QABUL QILISH VA ADMINGA YUBORISH ---
@dp.message(BotStates.waiting_for_receipt, F.photo)
async def handle_receipt(message: types.Message, state: FSMContext):
    await message.answer("Rahmat! Chek adminga yuborildi. Tasdiqlangach, mahsulot yuboriladi.")
    
    # Adminga (Sizga) tasdiqlash tugmasi bilan boradi
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Tasdiqlash (Fayl yuborish)", callback_data=f"accept_{message.from_user.id}")]
    ])
    
    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=message.photo[-1].file_id,
        caption=f"🔔 **Yangi to'lov!**\nFoydalanuvchi: @{message.from_user.username}\nID: {message.from_user.id}",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await state.clear()

# --- ADMIN TASDIQLASA FAYL KETADI ---
@dp.callback_query(F.data.startswith("accept_"))
async def approve_payment(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    
    # Foydalanuvchiga xabar yuborish
    await bot.send_message(user_id, "Sizning to'lovingiz tasdiqlandi! ✅\n\nMana sizning faylingiz:")
    
    # PDF yoki boshqa faylni yuborish (Namuna sifatida dummy PDF ishlatilgan)
    await bot.send_document(
        chat_id=user_id,
        document="https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
        caption="Pomodoro o'quv qo'llanmasi. 🍅"
    )
    
    # Admin panelida xabarni yangilash
    await callback.answer("Foydalanuvchiga fayl yuborildi!")
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ **TASTIQLANDI**", parse_mode="Markdown")

# --- ISHGA TUSHIRISH ---
async def main():
    logging.basicConfig(level=logging.INFO)
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.error("Bot to'xtatildi!")
