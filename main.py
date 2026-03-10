import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from geopy.distance import geodesic
from aiohttp import web

from db import Database  # db.py ishlatiladi

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO)

# ---------- TOKEN ----------
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    logging.error("❌ BOT_TOKEN environment variable topilmadi!")
    raise RuntimeError("BOT_TOKEN environment variable topilmadi!")

bot = Bot(token=TOKEN)
dp = Dispatcher()
db = Database("arena_go.db")

# ---------- Render Web Server ----------
async def handle(request):
    return web.Response(text="ArenaGo Bot ishlayapti ✅")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Web server running on port {port}")


# ---------- STATES ----------
class Registration(StatesGroup):
    choosing_role = State()


# ---------- KEYBOARDS ----------
def get_role_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton("Mijoz (Futbolchi)"), KeyboardButton("Stadion Egasi")]],
        resize_keyboard=True
    )

def get_main_menu(is_owner=False):
    if is_owner:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton("Mening Stadionlarim")],
                [KeyboardButton("Stadion Qo'shish")],
                [KeyboardButton("Profil")]
            ],
            resize_keyboard=True
        )
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("Yaqin Stadionlar", request_location=True)],
            [KeyboardButton("Barcha Stadionlar")],
            [KeyboardButton("Jamoa 🤝")],
            [KeyboardButton("Mening Bronlarim")],
            [KeyboardButton("Profil")]
        ],
        resize_keyboard=True
    )


# ---------- START HANDLER ----------
@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    if not user:
        db.add_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
        await message.answer("ArenaGo botiga xush kelibsiz!\nSiz kimsiz?", reply_markup=get_role_keyboard())
        await state.set_state(Registration.choosing_role)
    else:
        await message.answer("Xush kelibsiz!", reply_markup=get_main_menu(bool(user[3])))


# ---------- ROLE HANDLER ----------
@dp.message(Registration.choosing_role)
async def process_role(message: types.Message, state: FSMContext):
    is_owner = 1 if message.text == "Stadion Egasi" else 0
    db.update_user_role(message.from_user.id, is_owner)
    await message.answer(f"Siz {message.text} sifatida ro'yxatdan o'tdingiz.", reply_markup=get_main_menu(bool(is_owner)))
    await state.clear()


# ---------- LOCATION HANDLER ----------
@dp.message(F.location)
async def handle_location(message: types.Message):
    lat = message.location.latitude
    lon = message.location.longitude
    db.update_user_location(message.from_user.id, lat, lon)

    stadiums = db.get_all_stadiums()
    if not stadiums:
        await message.answer("Hozircha stadionlar yo'q.")
        return

    nearby = sorted(
        [(geodesic((lat, lon), (s[4], s[5])).km, s) for s in stadiums],
        key=lambda x: x[0]
    )[:5]

    await message.answer("📍 Sizga eng yaqin stadionlar:")
    for dist, s in nearby:
        caption = f"🏟 {s[2]}\n📏 Masofa: {dist:.2f} km\n💰 {s[6]} so'm\n⏰ {s[9]}"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton("📍 Lokatsiya", callback_data=f"loc_{s[0]}")]]
        )
        if s[8]:  # photo_id bo‘lsa
            await message.answer_photo(s[8], caption=caption, reply_markup=kb)
        else:
            await message.answer(caption, reply_markup=kb)


# ---------- STADIUM LOCATION CALLBACK ----------
@dp.callback_query(F.data.startswith("loc_"))
async def send_stadium_location(callback: types.CallbackQuery):
    await callback.answer()
    stadium_id = int(callback.data.split("_")[1])
    s = db.get_stadium_by_id(stadium_id)
    if s:
        await bot.send_location(callback.from_user.id, s[4], s[5])


# ---------- PROFILE ----------
@dp.message(F.text.contains("Profil"))
async def show_profile(message: types.Message):
    u = db.get_user(message.from_user.id)
    role = "Stadion Egasi" if u[3] else "Mijoz (Futbolchi)"
    text = f"👤 Profil\n\n🆔 ID: {u[0]}\n👤 Ism: {u[1]}\n🎭 Rol: {role}\n🔗 Username: @{u[2] if u[2] else 'yoq'}"
    await message.answer(text)


# ---------- MAIN ----------
async def main():
    await start_web_server()
    logging.info("ArenaGo Bot ishga tushdi ✅")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
