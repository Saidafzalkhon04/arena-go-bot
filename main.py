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
from aiohttp import web  # Render uchun portni band qilishga kerak

from db import Database

# Logging sozlamalari
logging.basicConfig(level=logging.INFO )

# Bot tokeni
TOKEN = "8724037162:AAHoxj_-NSO96BnoL7O85WlPDiBYSmQFqUU"

# Ma'lumotlar bazasi
db = Database("arena_go.db")

# Bot va Dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Render uchun soxta web-server (Port xatosini tuzatish uchun) ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render beradigan PORTni ishlatamiz, bo'lmasa 10000
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Web server started on port {port}")

# --- States (FSM) ---
class Registration(StatesGroup):
    choosing_role = State()

class AddStadium(StatesGroup):
    name = State()
    address = State()
    location = State()
    price = State()
    work_hours = State()
    description = State()
    photo = State()

class BookingProcess(StatesGroup):
    selecting_stadium = State()
    selecting_date = State()
    selecting_time = State()

class TeamFinder(StatesGroup):
    stadium_name = State()
    game_date = State()
    game_time = State()
    needed_players = State()
    description = State()

# --- Keyboards ---
def get_role_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Mijoz (Futbolchi)"), KeyboardButton(text="Stadion Egasi")]],
        resize_keyboard=True
    )

def get_main_menu(is_owner=False):
    if is_owner:
        buttons = [
            [KeyboardButton(text="Mening Stadionlarim")],
            [KeyboardButton(text="Stadion Qo'shish")],
            [KeyboardButton(text="Profil")]
        ]
    else:
        buttons = [
            [KeyboardButton(text="Yaqin Stadionlar", request_location=True)],
            [KeyboardButton(text="Barcha Stadionlar")],
            [KeyboardButton(text="Jamoa 🤝")],
            [KeyboardButton(text="Mening Bronlarim")],
            [KeyboardButton(text="Profil")]
        ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# --- Handlers ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    if not user:
        db.add_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
        await message.answer(
            f"Assalomu alaykum, {message.from_user.full_name}! ArenaGo botiga xush kelibsiz.\nSiz kimsiz?",
            reply_markup=get_role_keyboard()
        )
        await state.set_state(Registration.choosing_role)
    else:
        is_owner = bool(user[3])
        await message.answer("Xush kelibsiz!", reply_markup=get_main_menu(is_owner))

@dp.message(Registration.choosing_role)
async def process_role(message: types.Message, state: FSMContext):
    if message.text == "Mijoz (Futbolchi)":
        db.update_user_role(message.from_user.id, 0)
        await message.answer("Siz Mijoz sifatida ro'yxatdan o'tdingiz.", reply_markup=get_main_menu(False))
        await state.clear()
    elif message.text == "Stadion Egasi":
        db.update_user_role(message.from_user.id, 1)
        await message.answer("Siz Stadion Egasi sifatida ro'yxatdan o'tdingiz.", reply_markup=get_main_menu(True))
        await state.clear()
    else:
        await message.answer("Iltimos, tugmalardan birini tanlang.")

# --- Stadion Qo'shish ---
@dp.message(F.text == "Stadion Qo'shish")
async def add_stadium_start(message: types.Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    if user and user[3]:
        await message.answer("Stadion nomini kiriting:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(AddStadium.name)
    else:
        await message.answer("Bu funksiya faqat stadion egalari uchun.")

@dp.message(AddStadium.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Stadion manzilini kiriting:")
    await state.set_state(AddStadium.address)

@dp.message(AddStadium.address)
async def process_address(message: types.Message, state: FSMContext):
    await state.update_data(address=message.text)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Lokatsiyani yuborish", request_location=True)]], resize_keyboard=True)
    await message.answer("Stadion lokatsiyasini yuboring:", reply_markup=kb)
    await state.set_state(AddStadium.location)

@dp.message(AddStadium.location, F.location)
async def process_location(message: types.Message, state: FSMContext):
    await state.update_data(lat=message.location.latitude, lon=message.location.longitude)
    await message.answer("Ish vaqtini kiriting (masalan: 08:00-23:00):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AddStadium.work_hours)

@dp.message(AddStadium.work_hours)
async def process_work_hours(message: types.Message, state: FSMContext):
    await state.update_data(work_hours=message.text)
    await message.answer("Bir soatlik o'yin narxini kiriting (masalan: 100000):")
    await state.set_state(AddStadium.price)

@dp.message(AddStadium.price)
async def process_price(message: types.Message, state: FSMContext):
    if message.text.isdigit():
        await state.update_data(price=int(message.text))
        await message.answer("Stadion haqida qisqacha ma'lumot kiriting:")
        await state.set_state(AddStadium.description)
    else:
        await message.answer("Iltimos, faqat raqam kiriting.")

@dp.message(AddStadium.description)
async def process_desc(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Stadion rasmini yuboring:")
    await state.set_state(AddStadium.photo)

@dp.message(AddStadium.photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photo_id = message.photo[-1].file_id
    db.add_stadium(message.from_user.id, data['name'], data['address'], data['lat'], data['lon'], data['price'], data['description'], photo_id, data['work_hours'])
    await message.answer("Stadion muvaffaqiyatli qo'shildi!", reply_markup=get_main_menu(True))
    await state.clear()

# --- Stadionlarni Ko'rish va Bron Qilish ---
@dp.message(F.text == "Barcha Stadionlar")
async def show_all_stadiums(message: types.Message):
    stadiums = db.get_all_stadiums()
    if not stadiums:
        await message.answer("Hozircha stadionlar mavjud emas.")
        return

    for st in stadiums:
        caption = f"🏟 {st[2]}\n📍 Manzil: {st[3]}\n⏰ Ish vaqti: {st[9]}\n💰 Narxi: {st[6]:,} so'm/soat\n📝 {st[7]}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Bron qilish", callback_data=f"book_{st[0]}")]])
        await message.answer_photo(st[8], caption=caption, reply_markup=kb)

@dp.callback_query(F.data.startswith("book_"))
async def start_booking(callback: types.CallbackQuery, state: FSMContext):
    stadium_id = int(callback.data.split("_")[1])
    await state.update_data(stadium_id=stadium_id)
    await callback.message.answer("Bron qilish sanasini kiriting (masalan: 2024-03-10):")
    await state.set_state(BookingProcess.selecting_date)
    await callback.answer()

@dp.message(BookingProcess.selecting_date)
async def process_booking_date(message: types.Message, state: FSMContext):
    data = await state.get_data()
    stadium = db.get_stadium_by_id(data['stadium_id'])
    bookings = db.get_stadium_bookings(data['stadium_id'], message.text)
    
    booked_times = ", ".join([f"{b[0]}-{b[1]}" for b in bookings]) if bookings else "Hozircha bo'sh"
    text = f"🏟 {stadium[2]}\n⏰ Ish vaqti: {stadium[9]}\n📅 Sana: {message.text}\n🚫 Band vaqtlar: {booked_times}\n\nBron qilish vaqtini kiriting (masalan: 18:00-19:00):"
    
    await state.update_data(date=message.text)
    await message.answer(text)
    await state.set_state(BookingProcess.selecting_time)

@dp.message(BookingProcess.selecting_time)
async def process_booking_time(message: types.Message, state: FSMContext):
    data = await state.get_data()
    time_range = message.text.split("-")
    if len(time_range) == 2:
        start_time, end_time = time_range
        db.add_booking(message.from_user.id, data['stadium_id'], data['date'], start_time, end_time)
        stadium = db.get_stadium_by_id(data['stadium_id'])
        
        await message.answer(f"✅ Broningiz qabul qilindi!\nSana: {data['date']}\nVaqt: {message.text}", reply_markup=get_main_menu(False))
        
        # Egaga xabar yuborish
        owner_msg = f"🔔 Yangi bron!\n🏟 Stadion: {stadium[2]}\n👤 Mijoz: {message.from_user.full_name}\n📅 Sana: {data['date']}\n⏰ Vaqt: {message.text}"
        try:
            await bot.send_message(stadium[1], owner_msg)
        except:
            pass
        await state.clear()
    else:
        await message.answer("Vaqtni to'g'ri formatda kiriting (18:00-19:00).")

# --- Bronni Bekor Qilish ---
@dp.message(F.text == "Mening Bronlarim")
async def my_bookings(message: types.Message):
    bookings = db.get_user_bookings(message.from_user.id)
    if not bookings:
        await message.answer("Sizda hali bronlar mavjud emas.")
        return
    
    for b in bookings:
        text = f"🏟 Stadion: {b[7]}\n🗓 Sana: {b[3]}\n⏰ Vaqt: {b[4]}-{b[5]}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_{b[0]}")]])
        await message.answer(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("cancel_"))
async def cancel_booking_handler(callback: types.CallbackQuery):
    booking_id = int(callback.data.split("_")[1])
    booking = db.get_booking_by_id(booking_id)
    if booking:
        db.cancel_booking(booking_id, callback.from_user.id)
        stadium = db.get_stadium_by_id(booking[2])
        await callback.message.edit_text(f"❌ Bron bekor qilindi: {stadium[2]} ({booking[3]})")
        
        # Egaga xabar yuborish
        owner_msg = f"⚠️ Bron bekor qilindi!\n🏟 Stadion: {stadium[2]}\n👤 Mijoz: {callback.from_user.full_name}\n📅 Sana: {booking[3]}\n⏰ Vaqt: {booking[4]}-{booking[5]}"
        try:
            await bot.send_message(stadium[1], owner_msg)
        except:
            pass
    await callback.answer()

# --- Jamoa (Team Finder) ---
@dp.message(F.text == "Jamoa 🤝")
async def team_menu(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ E'lon qoldirish", callback_data="add_team")],
        [InlineKeyboardButton(text="🔍 E'lonlarni ko'rish", callback_data="view_teams")]
    ])
    await message.answer("Jamoa bo'limi: sheriklar topishingiz mumkin.", reply_markup=kb)

@dp.callback_query(F.data == "add_team")
async def add_team_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Qaysi stadionda o'ynamoqchisiz?")
    await state.set_state(TeamFinder.stadium_name)
    await callback.answer()

@dp.message(TeamFinder.stadium_name)
async def team_stadium(message: types.Message, state: FSMContext):
    await state.update_data(stadium=message.text)
    await message.answer("Sana (masalan: 10-mart):")
    await state.set_state(TeamFinder.game_date)

@dp.message(TeamFinder.game_date)
async def team_date(message: types.Message, state: FSMContext):
    await state.update_data(date=message.text)
    await message.answer("Vaqt (masalan: 19:00):")
    await state.set_state(TeamFinder.game_time)

@dp.message(TeamFinder.game_time)
async def team_time(message: types.Message, state: FSMContext):
    await state.update_data(time=message.text)
    await message.answer("Necha kishi kerak?")
    await state.set_state(TeamFinder.needed_players)

@dp.message(TeamFinder.needed_players)
async def team_players(message: types.Message, state: FSMContext):
    await state.update_data(players=message.text)
    await message.answer("Qo'shimcha ma'lumot:")
    await state.set_state(TeamFinder.description)

@dp.message(TeamFinder.description)
async def team_desc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    db.add_team_post(message.from_user.id, data['stadium'], data['date'], data['time'], data['players'], message.text)
    await message.answer("✅ E'loningiz joylandi!", reply_markup=get_main_menu(False))
    await state.clear()

@dp.callback_query(F.data == "view_teams")
async def view_teams(callback: types.CallbackQuery):
    teams = db.get_all_teams()
    if not teams:
        await callback.message.answer("Hozircha e'lonlar yo'q.")
    else:
        for t in teams:
            text = f"🤝 **Jamoaga taklif!**\n🏟 Stadion: {t[2]}\n📅 Sana: {t[3]}\n⏰ Vaqt: {t[4]}\n👥 Kerakli odam: {t[5]} ta\n📝 {t[6]}\n👤 Muallif: {t[8]}"
            await callback.message.answer(text)
    await callback.answer()

# --- Profil ---
@dp.message(F.text == "Profil")
async def show_profile(message: types.Message):
    user = db.get_user(message.from_user.id)
    role = "Stadion Egasi" if user[3] else "Mijoz (Futbolchi)"
    await message.answer(f"👤 **Profil:**\n🆔 ID: {user[0]}\n👤 Ism: {user[1]}\n🎭 Rol: {role}")

# --- Asosiy ishga tushirish qismi ---
async def main():
    # Render uchun soxta web-serverni ishga tushiramiz
    await start_web_server()
    
    # Botni ishga tushiramiz (Polling)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
