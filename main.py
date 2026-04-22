import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# --- SOZLAMALAR ---
API_TOKEN = '8750077178:AAFgDf_LDL11-cYvg_KGZUboTnkH-oWPFak'
ADMIN_ID = 8213426436 
KARTA_MA_LUMOTI = "💳 **Karta:** `4439 2000 2522 5029`\n👤 **Ism:** Mutabbarhon M. (Eskhata Visa)"

# Mahsulotlarni va foydalanuvchilarni saqlash (Vaqtincha xotira)
products = {} 
users = set()

class BotStates(StatesGroup):
    # Mahsulot qo'shish bosqichlari
    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_photo = State()
    # Rassilka bosqichi
    waiting_for_broadcast = State()
    # To'lov bosqichi
    waiting_for_receipt = State()

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- ASOSIY MENYU ---
def main_menu(user_id):
    kb = [[types.KeyboardButton(text="🛍 Mahsulotlar")]]
    if user_id == ADMIN_ID:
        kb.append([types.KeyboardButton(text="➕ Mahsulot qo'shish"), types.KeyboardButton(text="📢 Rassilka")])
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    users.add(message.from_user.id)
    await message.answer(
        "Bee School do'koniga xush kelibsiz! 🐝\nPastdagi menyudan foydalaning:", 
        reply_markup=main_menu(message.from_user.id)
    )

# --- MAHSULOT QO'SHISH (FAQAT ADMIN) ---
@dp.message(F.text == "➕ Mahsulot qo'shish", F.from_user.id == ADMIN_ID)
async def add_product(message: types.Message, state: FSMContext):
    await message.answer("Mahsulot nomini yozing:")
    await state.set_state(BotStates.waiting_for_name)

@dp.message(BotStates.waiting_for_name)
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Narxini yozing (masalan: 50 somoni):")
    await state.set_state(BotStates.waiting_for_price)

@dp.message(BotStates.waiting_for_price)
async def get_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text)
    await message.answer("Mahsulot rasmini yuboring:")
    await state.set_state(BotStates.waiting_for_photo)

@dp.message(BotStates.waiting_for_photo, F.photo)
async def get_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    p_id = str(len(products) + 1)
    products[p_id] = {
        "name": data['name'],
        "price": data['price'],
        "photo": message.photo[-1].file_id
    }
    await message.answer(f"✅ Mahsulot qo'shildi!\nNomi: {data['name']}\nNarxi: {data['price']}", reply_markup=main_menu(ADMIN_ID))
    await state.clear()

# --- MAHSULOTLAR RO'YXATI (TUGMALAR) ---
@dp.message(F.text == "🛍 Mahsulotlar")
async def show_products_list(message: types.Message):
    if not products:
        await message.answer("Hozircha do'konda mahsulotlar yo'q.")
        return
    
    keyboard_buttons = []
    for p_id, p_info in products.items():
        button_text = f"{p_info['name']} — {p_info['price']}"
        keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"view_{p_id}")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.answer("Kerakli mahsulotni tanlang:", reply_markup=kb)

# --- MAHSULOTNI KO'RSATISH ---
@dp.callback_query(F.data.startswith("view_"))
async def view_product(callback: types.CallbackQuery):
    p_id = callback.data.split("_")[1]
    product = products[p_id]
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Sotib olish", callback_data=f"pay_{p_id}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_list")]
    ])
    
    await callback.message.answer_photo(
        photo=product['photo'], 
        caption=f"📦 **{product['name']}**\n💰 Narxi: {product['price']}",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await callback.message.delete()
    await callback.answer()

@dp.callback_query(F.data == "back_to_list")
async def back_to_list(callback: types.CallbackQuery):
    await show_products_list(callback.message)
    await callback.message.delete()
    await callback.answer()

# --- TO'LOV BOSQICHI ---
@dp.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: types.CallbackQuery, state: FSMContext):
    p_id = callback.data.split("_")[1]
    product = products[p_id]
    await state.update_data(p_name=product['name'])
    
    text = (
        f"Siz tanladingiz: **{product['name']}**\n\n"
        f"{KARTA_MA_LUMOTI}\n"
        f"💰 **To'lov summasi:** {product['price']}\n\n"
        "To'lovni amalga oshirgach, chekni (skrinshotni) shu yerga rasm ko'rinishida yuboring!"
    )
    await callback.message.answer(text, parse_mode="Markdown")
    await state.set_state(BotStates.waiting_for_receipt)
    await callback.answer()

@dp.message(BotStates.waiting_for_receipt, F.photo)
async def handle_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await message.answer("Rahmat! Chek adminga yuborildi. Tasdiqlangach, siz bilan bog'lanamiz.")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ To'lovni tasdiqlash", callback_data=f"accept_{message.from_user.id}_{data['p_name']}")]
    ])
    
    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=message.photo[-1].file_id,
        caption=f"🔔 **Yangi buyurtma!**\n📦 Mahsulot: {data['p_name']}\n👤 Mijoz: @{message.from_user.username}",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await state.clear()

# --- ADMIN TASDIQLASHI ---
@dp.callback_query(F.data.startswith("accept_"))
async def approve_order(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    user_id = int(parts[1])
    p_name = parts[2]
    
    await bot.send_message(user_id, f"Sizning '{p_name}' uchun to'lovingiz tasdiqlandi! ✅\nTez orada kurerimiz bog'lanadi.")
    await callback.answer("Tasdiqlandi!")
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ **TASTIQLANDI**", parse_mode="Markdown")

# --- RASSILKA ---
@dp.message(F.text == "📢 Rassilka", F.from_user.id == ADMIN_ID)
async def broadcast_start(message: types.Message, state: FSMContext):
    await message.answer("Barcha foydalanuvchilarga yuboriladigan xabarni (matn, rasm yoki video) kiriting:")
    await state.set_state(BotStates.waiting_for_broadcast)

@dp.message(BotStates.waiting_for_broadcast, F.from_user.id == ADMIN_ID)
async def broadcast_send(message: types.Message, state: FSMContext):
    count = 0
    for u_id in users:
        try:
            await message.copy_to(chat_id=u_id)
            count += 1
        except: pass
    await message.answer(f"Xabar {count} kishiga muvaffaqiyatli yuborildi. ✅")
    await state.clear()

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
