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

from database import Database

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

db = Database("arena_go.db")

# ---------- Render Web Server ----------

async def handle(request):
    return web.Response(text="ArenaGo Bot ishlayapti")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)

    await site.start()


# ---------- STATES ----------

class Registration(StatesGroup):
    choosing_role = State()


# ---------- KEYBOARDS ----------

def get_role_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Mijoz (Futbolchi)"),
                KeyboardButton(text="Stadion Egasi")
            ]
        ],
        resize_keyboard=True
    )


def get_main_menu(is_owner=False):

    if is_owner:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Mening Stadionlarim")],
                [KeyboardButton(text="Stadion Qo'shish")],
                [KeyboardButton(text="Profil")]
            ],
            resize_keyboard=True
        )

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Yaqin Stadionlar", request_location=True)],
            [KeyboardButton(text="Barcha Stadionlar")],
            [KeyboardButton(text="Jamoa 🤝")],
            [KeyboardButton(text="Mening Bronlarim")],
            [KeyboardButton(text="Profil")]
        ],
        resize_keyboard=True
    )


# ---------- START ----------

@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):

    user = db.get_user(message.from_user.id)

    if not user:

        db.add_user(
            message.from_user.id,
            message.from_user.full_name,
            message.from_user.username
        )

        await message.answer(
            "ArenaGo botiga xush kelibsiz!\nSiz kimsiz?",
            reply_markup=get_role_keyboard()
        )

        await state.set_state(Registration.choosing_role)

    else:

        await message.answer(
            "Xush kelibsiz!",
            reply_markup=get_main_menu(bool(user[3]))
        )


# ---------- ROLE ----------

@dp.message(Registration.choosing_role)
async def process_role(message: types.Message, state: FSMContext):

    is_owner = 1 if message.text == "Stadion Egasi" else 0

    db.update_user_role(message.from_user.id, is_owner)

    await message.answer(
        f"Siz {message.text} sifatida ro'yxatdan o'tdingiz",
        reply_markup=get_main_menu(bool(is_owner))
    )

    await state.clear()


# ---------- LOCATION ----------

@dp.message(F.location)
async def handle_location(message: types.Message):

    lat = message.location.latitude
    lon = message.location.longitude

    db.update_user_location(message.from_user.id, lat, lon)

    stadiums = db.get_all_stadiums()

    if not stadiums:
        await message.answer("Hozircha stadionlar yo'q")
        return

    nearby = sorted(
        [(geodesic((lat, lon), (s[4], s[5])).km, s) for s in stadiums],
        key=lambda x: x[0]
    )[:5]

    await message.answer("Sizga eng yaqin stadionlar:")

    for dist, s in nearby:

        caption = (
            f"Stadion: {s[2]}\n"
            f"Masofa: {dist:.2f} km\n"
            f"Narx: {s[6]} so'm\n"
            f"Ish vaqti: {s[9]}"
        )

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Lokatsiya",
                        callback_data=f"loc_{s[0]}"
                    )
                ]
            ]
        )

        if s[8]:
            await message.answer_photo(s[8], caption=caption, reply_markup=kb)
        else:
            await message.answer(caption, reply_markup=kb)


# ---------- SEND LOCATION ----------

@dp.callback_query(F.data.startswith("loc_"))
async def send_stadium_loc(callback: types.CallbackQuery):

    await callback.answer()

    stadium_id = int(callback.data.split("_")[1])

    s = db.get_stadium_by_id(stadium_id)

    if s:
        await bot.send_location(callback.from_user.id, s[4], s[5])


# ---------- PROFILE ----------

@dp.message(F.text.contains("Profil"))
async def show_profile(message: types.Message):

    u = db.get_user(message.from_user.id)

    role = "Stadion Egasi" if u[3] else "Mijoz"

    text = (
        f"Sizning profilingiz\n\n"
        f"ID: {u[0]}\n"
        f"Ism: {u[1]}\n"
        f"Rol: {role}\n"
        f"Username: @{u[2] if u[2] else 'yoq'}"
    )

    await message.answer(text)


# ---------- MAIN ----------

async def main():

    await start_web_server()

    logging.info("Bot ishga tushdi")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
