import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from geopy.distance import geodesic
from datetime import datetime
from aiohttp import web

from db import Database

logging.basicConfig(level=logging.INFO )
TOKEN = "8724037162:AAHoxj_-NSO96BnoL7O85WlPDiBYSmQFqUU"
db = Database("arena_go.db")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Render Port Fix ---
async def handle(request): return web.Response(text="Bot is running!")
async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- States ---
class Registration(StatesGroup): choosing_role = State()
class AddStadium(StatesGroup): name = State(); address = State(); location = State(); price = State(); work_hours = State(); description = State(); photo = State()
class BookingProcess(StatesGroup): selecting_stadium = State(); selecting_date = State(); selecting_time = State()
class TeamFinder(StatesGroup): stadium_name = State(); game_date = State(); game_time = State(); needed_players = State(); description = State()

# --- Keyboards ---
def get_role_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Mijoz (Futbolchi)"), KeyboardButton(text="Stadion Egasi")]], resize_keyboard=True)

def get_main_menu(is_owner=False):
    if is_owner:
        return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Mening Stadionlarim")], [KeyboardButton(text="Stadion Qo'shish")], [KeyboardButton(text="Profil")]], resize_keyboard=True)
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Yaqin Stadionlar", request_location=True)], [KeyboardButton(text="Barcha Stadionlar")], [KeyboardButton(text="Jamoa 🤝")], [KeyboardButton(text="Mening Bronlarim")], [KeyboardButton(text="Profil")]], resize_keyboard=True)

# --- Handlers ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    if not user:
        db.add_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
        await message.answer(f"Assalomu alaykum! ArenaGo botiga xush kelibsiz.\nSiz kimsiz?", reply_markup=get_role_keyboard())
        await state.set_state(Registration.choosing_role)
    else:
        await message.answer("Xush kelibsiz!", reply_markup=get_main_menu(bool(user[3])))

@dp.message(Registration.choosing_role)
async def process_role(message: types.Message, state: FSMContext):
    is_owner = 1 if message.text == "Stadion Egasi" else 0
    db.update_user_role(message.from_user.id, is_owner)
    await message.answer(f"Siz {message.text} sifatida ro'yxatdan o'tdingiz.", reply_markup=get_main_menu(bool(is_owner)))
    await state.clear()

# --- Location Handler (Yaqin stadionlarni ko'rsatish) ---
@dp.message(F.location)
async def handle_location(message: types.Message):
    lat, lon = message.location.latitude, message.location.longitude
    db.update_user_location(message.from_user.id, lat, lon)
    stadiums = db.get_all_stadiums()
    if not stadiums:
        await message.answer("Hozircha stadionlar yo'q.")
        return
    
    nearby = sorted([(geodesic((lat, lon), (s[4], s[5])).km, s) for s in stadiums], key=lambda x: x[0])[:5]
    await message.answer("📍 Sizga eng yaqin stadionlar:")
    for dist, s in nearby:
        caption = f"🏟 {s[2]}\n📏 Masofa: {dist:.2f} km\n💰 {s[6]:,} so'm\n⏰ {s[9]}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Bron qilish", callback_data=f"book_{s[0]}")], [InlineKeyboardButton(text="📍 Lokatsiya", callback_data=f"loc_{s[0]}") ]])
        await message.answer_photo(s[8], caption=caption, reply_markup=kb)

@dp.callback_query(F.data.startswith("loc_"))
async def send_stadium_loc(callback: types.CallbackQuery):
    s = db.get_stadium_by_id(int(callback.data.split("_")[1]))
    await bot.send_location(callback.from_user.id, s[4], s[5])
    await callback.answer()

# --- Jamoa (Team Finder) ---
@dp.message(F.text == "Jamoa 🤝")
async def team_menu(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ E'lon qoldirish", callback_data="add_team")], [InlineKeyboardButton(text="🔍 E'lonlarni ko'rish", callback_data="view_teams")]])
    await message.answer("Jamoa bo'limi:", reply_markup=kb)

@dp.callback_query(F.data == "view_teams")
async def view_teams(callback: types.CallbackQuery):
    teams = db.get_all_teams()
    if not teams: await callback.message.answer("E'lonlar yo'q."); await callback.answer(); return
    for t in teams:
        text = f"🤝 **Jamoaga taklif!**\n🏟 Stadion: {t[2]}\n📅 {t[3]} | ⏰ {t[4]}\n👥 Kerak: {t[5]} ta | ✅ Qo'shildi: {t[6]} ta\n📝 {t[7]}\n👤 Muallif: {t[9]}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Qo'shilish ➕", callback_data=f"join_{t[0]}")]])
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("join_"))
async def join_team_handler(callback: types.CallbackQuery):
    t = db.get_team_by_id(int(callback.data.split("_")[1]))
    u = db.get_user(callback.from_user.id)
    if t and t[1] != callback.from_user.id:
        db.join_team(t[0])
        # E'lon egasiga xabar
        owner_msg = f"🔔 Jamoangizga yangi odam qo'shildi!\n👤 Ism: {u[1]}\n🆔 ID: {u[0]}\n🔗 Username: @{u[2] if u[2] else 'yoq'}"
        await bot.send_message(t[1], owner_msg)
        # Qo'shilgan odamga lokatsiya
        s = db.get_stadium_by_name(t[2])
        await callback.message.answer(f"✅ Siz jamoaga qo'shildingiz!")
        if s: await bot.send_location(callback.from_user.id, s[4], s[5])
    else:
        await callback.answer("O'z e'loningizga qo'shila olmaysiz!", show_alert=True)
    await callback.answer()

# --- Profil ---
@dp.message(F.text == "Profil")
async def show_profile(message: types.Message):
    u = db.get_user(message.from_user.id)
    role = "Stadion Egasi" if u[3] else "Mijoz (Futbolchi)"
    await message.answer(f"👤 **Sizning profilingiz:**\n\n🆔 ID: {u[0]}\n👤 Ism: {u[1]}\n🎭 Rol: {role}\n🔗 Username: @{u[2] if u[2] else 'yoq'}")

# --- Boshqa handlerlar (Stadion qo'shish va Bron qilish - qisqartirildi, lekin main.py'da bo'lishi kerak) ---
# (Eski main.py dagi AddStadium va BookingProcess handlerlarini bu yerga qo'shib qo'ying)

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
