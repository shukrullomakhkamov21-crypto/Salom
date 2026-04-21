import asyncio
import requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from googletrans import Translator

# SOZLAMALAR
API_TOKEN = '8799283771:AAEThxn1O3emdhtEr5h4LbjmBhNHcrAXS8Y'
translator = Translator()
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Ma'lumotlarni vaqtinchalik saqlash
user_data = {}

CONTINENTS = {
    "🌍 Africa": "Africa",
    "🌎 Americas": "Americas",
    "🌏 Asia": "Asia",
    "🇪🇺 Europe": "Europe",
    "🏝 Oceania": "Oceania"
}

# --- FUNKSIYALAR ---

def fetch_country_data(name):
    """API dan ma'lumot olish funksiyasi"""
    url = f"https://restcountries.com/v3.1/name/{name}?fullText=true"
    # Agar to'liq nom bilan topilmasa, qidiruv orqali ko'ramiz
    res = requests.get(url)
    if res.status_code != 200:
        res = requests.get(f"https://restcountries.com/v3.1/name/{name}")
    
    if res.status_code == 200:
        return res.json()[0]
    return None

def create_pagination_kb(countries, page=0):
    """Tugmalarni sahifalarga bo'lish"""
    kb = []
    start, end = page * 10, (page + 1) * 10
    current_list = countries[start:end]
    
    for country in current_list:
        kb.append([InlineKeyboardButton(text=country, callback_data=f"country_{country}")])
    
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Back", callback_data=f"prev_{page}"))
    if end < len(countries):
        nav.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"next_{page}"))
    
    if nav: kb.append(nav)
    kb.append([InlineKeyboardButton(text="🏠 Menu", callback_data="back_to_cont")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# --- HANDLERS ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🇺🇿 O'zbek"), KeyboardButton(text="🇷🇺 Русский")],
        [KeyboardButton(text="🇬🇧 English"), KeyboardButton(text="🇹🇯 Тоҷикӣ")]
    ], resize_keyboard=True)
    await message.answer("Tilni tanlang / Choose language:", reply_markup=kb)

@dp.message(F.text.in_(["🇺🇿 O'zbek", "🇷🇺 Русский", "🇬🇧 English", "🇹🇯 Тоҷикӣ"]))
async def main_menu(message: types.Message):
    user_data[message.from_user.id] = {"lang": message.text}
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=k, callback_data=f"cont_{v}")] for k, v in CONTINENTS.items()
    ])
    await message.answer(
        "Qit'ani tanlang yoki davlat nomini yozing:\n"
        "Выберите континент или напишите название страны:", 
        reply_markup=kb
    )

@dp.callback_query(F.data == "back_to_cont")
async def back_to_menu(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=k, callback_data=f"cont_{v}")] for k, v in CONTINENTS.items()
    ])
    await call.message.edit_text("Qit'ani tanlang:", reply_markup=kb)

@dp.callback_query(F.data.startswith("cont_"))
async def continent_click(call: types.CallbackQuery):
    continent = call.data.split("_")[1]
    res = requests.get(f"https://restcountries.com/v3.1/region/{continent}").json()
    countries = sorted([c['name']['common'] for c in res])
    user_data[call.from_user.id]["countries"] = countries
    await call.message.edit_text(f"{continent} davlatlari:", reply_markup=create_pagination_kb(countries, 0))

@dp.callback_query(F.data.startswith("next_") | F.data.startswith("prev_"))
async def nav_click(call: types.CallbackQuery):
    action, page = call.data.split("_")
    new_page = int(page) + 1 if action == "next" else int(page) - 1
    countries = user_data[call.from_user.id]["countries"]
    await call.message.edit_reply_markup(reply_markup=create_pagination_kb(countries, new_page))

@dp.message(F.text)
async def text_handler(message: types.Message):
    """Matn orqali qidirish (Har qanday tilda)"""
    if message.from_user.id not in user_data:
        await message.answer("Avval /start bosing!")
        return
        
    query = message.text.strip()
    # Inglizchaga o'girish
    try:
        translated = translator.translate(query, dest='en')
        search_name = translated.text
    except:
        search_name = query

    data = fetch_country_data(search_name)
    if data:
        await send_country_info(message, data)
    else:
        await message.answer("❌ Topilmadi. Nomni aniqroq yozing.")

@dp.callback_query(F.data.startswith("country_"))
async def country_callback(call: types.CallbackQuery):
    name = call.data.split("_")[1]
    data = fetch_country_data(name)
    if data:
        await send_country_info(call.message, data)
    await call.answer()

async def send_country_info(target, data):
    """Ma'lumotni chiroyli qilib yuborish"""
    lang = user_data.get(target.chat.id, {}).get("lang", "🇺🇿 O'zbek")
    
    name = data['name']['common']
    cap = data.get('capital', ['N/A'])[0]
    pop = f"{data.get('population', 0):,}"
    area = f"{data.get('area', 0):,}"
    maps = data['maps']['googleMaps']
    flag = data.get('flag', '🏳️')
    
    titles = {
        "🇺🇿 O'zbek": ["Davlat", "Poytaxt", "Aholi", "Maydon", "Xarita"],
        "🇷🇺 Русский": ["Страна", "Столица", "Население", "Площадь", "Карта"],
        "🇬🇧 English": ["Country", "Capital", "Population", "Area", "Map"],
        "🇹🇯 Тоҷикӣ": ["Кишвар", "Пойтахт", "Аҳолӣ", "Масоҳат", "Харита"]
    }
    t = titles.get(lang, titles["🇺🇿 O'zbek"])
    
    msg = (
        f"{flag} **{t[0]}: {name}**\n\n"
        f"🏙 **{t[1]}:** {cap}\n"
        f"👥 **{t[2]}:** {pop}\n"
        f"📏 **{t[3]}:** {area} km²\n"
        f"📍 **{t[4]}:** [Google Maps]({maps})"
    )
    await target.answer(msg, parse_mode="Markdown")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
