import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from geopy.distance import geodesic
from aiohttp import web
from datetime import datetime

from db import Database

logging.basicConfig(level=logging.INFO )
TOKEN = "8724037162:AAHoxj_-NSO96BnoL7O85WlPDiBYSmQFqUU"
db = Database("arena_go.db")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Render Fix ---
async def handle(r): return web.Response(text="Running")
async def start_server():
    app = web.Application(); app.router.add_get("/", handle)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000))).start()

# --- States ---
class Reg(StatesGroup): role = State()
class AddSt(StatesGroup): name = State(); link = State(); loc = State(); price = State(); hours = State(); photo = State()
class Book(StatesGroup): sid = State(); date = State(); slot = State()

# --- Keyboards ---
def main_menu(is_owner=False):
    kb = []
    if is_owner:
        kb.append([KeyboardButton(text="Mening Stadionlarim"), KeyboardButton(text="Stadion Qo'shish")])
    else:
        kb.append([KeyboardButton(text="Yaqin Stadionlar", request_location=True), KeyboardButton(text="Barcha Stadionlar")])
        kb.append([KeyboardButton(text="Jamoa 🤝"), KeyboardButton(text="Mening Bronlarim")])
    kb.append([KeyboardButton(text="Profil")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- Handlers ---
@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    db.add_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
    await message.answer("Xush kelibsiz! Rolni tanlang:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Mijoz"), KeyboardButton(text="Stadion Egasi")]], resize_keyboard=True))
    await state.set_state(Reg.role)

@dp.message(Reg.role)
async def set_role(message: types.Message, state: FSMContext):
    is_owner = 1 if message.text == "Stadion Egasi" else 0
    db.cursor.execute("UPDATE users SET is_owner=? WHERE id=?", (is_owner, message.from_user.id))
    db.connection.commit()
    await message.answer(f"Siz {message.text} bo'lib kirdingiz.", reply_markup=main_menu(is_owner))
    await state.clear()

# --- Stadium List ---
@dp.message(F.text == "Barcha Stadionlar")
@dp.message(F.location)
async def list_st(message: types.Message):
    stadiums = db.get_all_stadiums()
    u_loc = (message.location.latitude, message.location.longitude) if message.location else None
    
    found = False
    for s in stadiums:
        dist = geodesic(u_loc, (s[4], s[5])).km if u_loc else None
        if message.location and dist > 5: continue # 5km radius
        
        found = True
        text = f"🏟 {s[2]}\n💰 {s[6]:,} so'm\n⏰ {s[7]}\n📍 [Xarita Link]({s[3]})"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Bron qilish 📅", callback_data=f"book_{s[0]}")]])
        await message.answer_photo(s[8], caption=text, reply_markup=kb, parse_mode="Markdown")
    
    if not found: await message.answer("Stadionlar topilmadi.")

# --- Booking with Slots ---
@dp.callback_query(F.data.startswith("book_"))
async def start_book(cb: types.CallbackQuery, state: FSMContext):
    await state.update_data(sid=int(cb.data.split("_")[1]))
    await cb.message.answer("Sanani kiriting (masalan: 2024-03-10):")
    await state.set_state(Book.date)

@dp.message(Book.date)
async def book_date(message: types.Message, state: FSMContext):
    d = await state.get_data()
    s = db.get_stadium_by_id(d['sid'])
    booked = db.get_booked_slots(d['sid'], message.text)
    
    # Ish vaqtini bo'lish (masalan 09:00-21:00)
    try:
        start_h, end_h = map(int, s[7].split("-")[0].split(":")[0]), map(int, s[7].split("-")[1].split(":")[0])
        start_h, end_h = list(start_h)[0], list(end_h)[0]
    except: start_h, end_h = 9, 22

    kb = []
    for h in range(start_h, end_h):
        slot = f"{h:02d}:00-{(h+1):02d}:00"
        if slot not in booked:
            kb.append([InlineKeyboardButton(text=slot, callback_data=f"slot_{slot}")])
    
    await state.update_data(date=message.text)
    await message.answer("Bo'sh vaqtni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await state.set_state(Book.slot)

@dp.callback_query(F.data.startswith("slot_"))
async def book_slot(cb: types.CallbackQuery, state: FSMContext):
    slot = cb.data.split("_")[1]
    d = await state.get_data()
    db.add_booking(cb.from_user.id, d['sid'], d['date'], slot)
    await cb.message.edit_text(f"✅ Bron qilindi: {d['date']} | {slot}")
    await state.clear()

# --- Other Commands ---
@dp.message(F.text == "Jamoa 🤝")
async def team(message: types.Message): await message.answer("Tez orada...")

@dp.message(F.text == "Mening Bronlarim")
async def my_books(message: types.Message):
    books = db.get_user_bookings(message.from_user.id)
    if not books: return await message.answer("Bronlar yo'q.")
    for b in books:
        await message.answer(f"🏟 {b[2]}\n📅 {b[0]} | ⏰ {b[1]}\n📍 [Xarita]({b[3]})", parse_mode="Markdown")

@dp.message(F.text == "Profil")
async def profile(message: types.Message):
    u = db.get_user(message.from_user.id)
    await message.answer(f"👤 {u[1]}\n🎭 Rol: {'Egasi' if u[3] else 'Mijoz'}")

# --- Owner Add Stadium ---
@dp.message(F.text == "Stadion Qo'shish")
async def add_st_start(message: types.Message, state: FSMContext):
    await message.answer("Stadion nomi:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AddSt.name)

@dp.message(AddSt.name)
async def add_st_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text); await message.answer("Google Maps linki:"); await state.set_state(AddSt.link)

@dp.message(AddSt.link)
async def add_st_link(message: types.Message, state: FSMContext):
    await state.update_data(link=message.text); await message.answer("Lokatsiya yuboring:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📍 Lokatsiya", request_location=True)]], resize_keyboard=True)); await state.set_state(AddSt.loc)

@dp.message(AddSt.loc, F.location)
async def add_st_loc(message: types.Message, state: FSMContext):
    await state.update_data(lat=message.location.latitude, lon=message.location.longitude); await message.answer("Narxi:", reply_markup=ReplyKeyboardRemove()); await state.set_state(AddSt.price)

@dp.message(AddSt.price)
async def add_st_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text); await message.answer("Ish vaqti (09:00-22:00):"); await state.set_state(AddSt.hours)

@dp.message(AddSt.hours)
async def add_st_hours(message: types.Message, state: FSMContext):
    await state.update_data(hours=message.text); await message.answer("Rasm yuboring:"); await state.set_state(AddSt.photo)

@dp.message(AddSt.photo, F.photo)
async def add_st_photo(message: types.Message, state: FSMContext):
    d = await state.get_data()
    db.add_stadium(message.from_user.id, d['name'], d['link'], d['lat'], d['lon'], d['price'], d['hours'], message.photo[-1].file_id)
    await message.answer("✅ Qo'shildi!", reply_markup=main_menu(True)); await state.clear()

async def main():
    await start_server()
    await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
