import asyncio
import requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

API_TOKEN = '8799283771:AAEThxn1O3emdhtEr5h4LbjmBhNHcrAXS8Y'
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
user_data = {}

# Қитъалар
CONTINENTS = {"🌍 Africa": "Africa", "🌎 Americas": "Americas", "🌏 Asia": "Asia", "🇪🇺 Europe": "Europe", "🏝 Oceania": "Oceania"}

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🇺🇿 O'zbek"), KeyboardButton(text="🇷🇺 Русский")],
        [KeyboardButton(text="🇬🇧 English"), KeyboardButton(text="🇹🇯 Тоҷикӣ")]
    ], resize_keyboard=True)
    await message.answer("Assalomu alaykum! Tilni tanlang / Выберите язык:", reply_markup=kb)

@dp.message(F.text.in_(["🇺🇿 O'zbek", "🇷🇺 Русский", "🇬🇧 English", "🇹🇯 Тоҷикӣ"]))
async def main_menu(message: types.Message):
    user_data[message.from_user.id] = {"lang": message.text}
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=k, callback_data=f"cont_{v}")] for k, v in CONTINENTS.items()
    ])
    text = {
        "🇺🇿 O'zbek": "Qit'ani tanlang yoki davlat nomini inglizcha yozing:",
        "🇷🇺 Русский": "Выберите континент или напишите название страны на английском:",
        "🇬🇧 English": "Choose a continent or write the country name in English:",
        "🇹🇯 Тоҷикӣ": "Қитъаро интихоб кунед ё номи кишварро бо англисӣ нависед:"
    }
    await message.answer(text[message.text], reply_markup=kb)

@dp.message(F.text)
async def manual_search(message: types.Message):
    """Исм орқали қидириш (AI-сиз)"""
    name = message.text.strip()
    res = requests.get(f"https://restcountries.com/v3.1/name/{name}")
    if res.status_code == 200:
        await send_details(message, res.json()[0])
    else:
        await message.answer("❌ Топилмади. Номни инглизча ёзиб кўринг (масалан: Uzbekistan).")

@dp.callback_query(F.data.startswith("cont_"))
async def list_countries(call: types.CallbackQuery):
    continent = call.data.split("_")[1]
    res = requests.get(f"https://restcountries.com/v3.1/region/{continent}").json()
    countries = sorted([c['name']['common'] for c in res])
    
    # Биринчи 15 та давлатни чиқарамиз (Pagination учун намуна)
    btns = [[InlineKeyboardButton(text=c, callback_data=f"info_{c}")] for c in countries[:15]]
    btns.append([InlineKeyboardButton(text="🏠 Menu", callback_data="back")])
    await call.message.edit_text(f"{continent} davlatlari:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("info_"))
async def country_info(call: types.CallbackQuery):
    name = call.data.split("_")[1]
    res = requests.get(f"https://restcountries.com/v3.1/name/{name}?fullText=true").json()[0]
    await send_details(call.message, res)
    await call.answer()

async def send_details(target, data):
    lang = user_data.get(target.chat.id, {}).get("lang", "🇺🇿 O'zbek")
    
    # Маълумотларни йиғиш
    name = data['name']['common']
    cap = data.get('capital', ['N/A'])[0]
    pop = f"{data.get('population', 0):,}"
    area = f"{data.get('area', 0):,}"
    maps = data['maps']['googleMaps']
    flag = data.get('flag', '📍')

    titles = {
        "🇺🇿 O'zbek": ["Davlat", "Poytaxt", "Aholi", "Maydon", "Xarita"],
        "🇷🇺 Русский": ["Страна", "Столица", "Население", "Площадь", "Карта"],
        "🇬🇧 English": ["Country", "Capital", "Population", "Area", "Map"],
        "🇹🇯 Тоҷикӣ": ["Кишвар", "Пойтахт", "Аҳолӣ", "Масоҳат", "Харита"]
    }
    t = titles.get(lang, titles["🇺🇿 O'zbek"])

    msg = (f"{flag} **{t[0]}: {name}**\n\n"
           f"🏙 **{t[1]}:** {cap}\n"
           f"👥 **{t[2]}:** {pop}\n"
           f"📏 **{t[3]}:** {area} km²\n"
           f"📍 **{t[4]}:** [Google Maps]({maps})")
    await target.answer(msg, parse_mode="Markdown")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
